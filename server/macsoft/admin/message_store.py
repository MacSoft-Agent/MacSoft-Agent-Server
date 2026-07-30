from __future__ import annotations

import sqlite3
from typing import Any

from macsoft.security import new_id, utc_now_iso
from macsoft.admin.session_store import touch_admin_session


MAX_ADMIN_CONTEXT_MESSAGES = 41
MAX_ADMIN_CONTEXT_ESTIMATED_TOKENS = 12_000


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["message_id"],
        "message_id": row["message_id"],
        "session_id": row["session_id"],
        "role": row["role"],
        "content": row["content"],
        "text": row["content"],
        "status": row["status"],
        "model": row["model"],
        "created_at": row["created_at"],
        "attachments": [],
    }


def save_admin_message(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    role: str,
    content: str,
    status: str = "saved",
    model: str | None = None,
    message_id: str | None = None,
) -> dict[str, Any]:
    resolved_id = message_id or new_id("admin_msg")
    now = utc_now_iso()
    cursor = conn.execute(
        """
        INSERT INTO admin_messages (message_id, session_id, role, content, status, model, created_at)
        SELECT ?, ?, ?, ?, ?, ?, ?
        WHERE EXISTS (SELECT 1 FROM admin_sessions WHERE session_id = ? AND deleted_at IS NULL)
        """,
        (resolved_id, session_id, role, content, status, model, now, session_id),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError("admin_session_not_found")
    conn.commit()
    touch_admin_session(conn, session_id, content)
    row = conn.execute("SELECT * FROM admin_messages WHERE message_id = ?", (resolved_id,)).fetchone()
    if row is None:
        raise RuntimeError("Failed to save Admin message.")
    return _row(row)


def list_admin_messages(conn: sqlite3.Connection, session_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT m.* FROM admin_messages m
        INNER JOIN admin_sessions s ON s.session_id = m.session_id
        WHERE m.session_id = ? AND s.deleted_at IS NULL
        ORDER BY m.created_at ASC
        """,
        (session_id,),
    ).fetchall()
    messages = [_row(row) for row in rows]
    by_id = {message["message_id"]: message for message in messages}
    if not by_id:
        return messages
    files = conn.execute(
        "SELECT file_id, message_id, original_name, media_type, size_bytes, created_at FROM admin_uploaded_files WHERE session_id = ? AND message_id IS NOT NULL ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    for file in files:
        message = by_id.get(str(file["message_id"]))
        if message is not None:
            message["attachments"].append({"file_id": str(file["file_id"]), "filename": str(file["original_name"]), "content_type": str(file["media_type"]), "size_bytes": int(file["size_bytes"]), "created_at": str(file["created_at"])})
    return messages


def attach_admin_files_to_message(conn: sqlite3.Connection, *, session_id: str, message_id: str, file_ids: list[str]) -> None:
    if not file_ids:
        return
    placeholders = ",".join("?" for _ in file_ids)
    cursor = conn.execute(f"UPDATE admin_uploaded_files SET message_id = ? WHERE session_id = ? AND message_id IS NULL AND file_id IN ({placeholders})", (message_id, session_id, *file_ids))
    if cursor.rowcount != len(file_ids):
        conn.rollback()
        raise ValueError("admin_file_not_found")
    conn.commit()


def list_admin_context(conn: sqlite3.Connection, session_id: str) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT role, content FROM admin_messages m
        INNER JOIN admin_sessions s ON s.session_id = m.session_id
        WHERE m.session_id = ? AND s.deleted_at IS NULL AND TRIM(content) <> ''
        ORDER BY m.created_at DESC LIMIT ?
        """,
        (session_id, MAX_ADMIN_CONTEXT_MESSAGES),
    ).fetchall()
    selected = [{"role": str(row["role"]), "content": str(row["content"])} for row in reversed(rows)]
    total = 0
    bounded: list[dict[str, str]] = []
    for message in selected:
        estimate = max(1, (len(message["content"].encode("utf-8")) + 2) // 3)
        if total + estimate > MAX_ADMIN_CONTEXT_ESTIMATED_TOKENS:
            break
        bounded.append(message)
        total += estimate
    return bounded
