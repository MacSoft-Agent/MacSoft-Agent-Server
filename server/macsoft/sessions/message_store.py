from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from macsoft.security import new_id, utc_now_iso
from macsoft.sessions.session_store import touch_session


MAX_AI_CONTEXT_MESSAGES = 41
MAX_AI_CONTEXT_ESTIMATED_TOKENS = 12_000
AI_CONTEXT_CANDIDATE_LIMIT = 123


@dataclass(frozen=True)
class AIContextWindow:
    messages: list[dict[str, Any]]
    estimated_tokens: int
    candidate_count: int
    total_stored_messages: int


def _row_to_message(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["message_id"],
        "message_id": row["message_id"],
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "role": row["role"],
        "content": row["content"],
        "text": row["content"],
        "status": row["status"],
        "model": row["model"],
        "created_at": row["created_at"],
    }


def save_message(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: str,
    owner_device_id: str,
    role: str,
    content: str,
    status: str = "completed",
    model: str | None = None,
    message_id: str | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    prefix = "msg_user" if role == "user" else "msg_assistant"
    resolved_message_id = message_id or new_id(prefix)

    cursor = conn.execute(
        """
        INSERT INTO messages (
            message_id,
            session_id,
            user_id,
            role,
            content,
            status,
            model,
            created_at
        )
        SELECT ?, ?, ?, ?, ?, ?, ?, ?
        WHERE EXISTS (
            SELECT 1
            FROM sessions
            WHERE session_id = ?
              AND user_id = ?
              AND owner_device_id = ?
              AND status = 'active'
              AND deleted_at IS NULL
        )
        """,
        (
            resolved_message_id,
            session_id,
            user_id,
            role,
            content,
            status,
            model,
            now,
            session_id,
            user_id,
            owner_device_id,
        ),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError("session_not_found")
    conn.commit()

    if status != "generating":
        touch_session(
            conn,
            session_id=session_id,
            preview=content,
        )

    row = conn.execute(
        """
        SELECT
            message_id,
            session_id,
            user_id,
            role,
            content,
            status,
            model,
            created_at
        FROM messages
        WHERE message_id = ?
        """,
        (resolved_message_id,),
    ).fetchone()

    if row is None:
        raise RuntimeError("Failed to save message.")

    return _row_to_message(row)


def create_pending_assistant_message(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: str,
    owner_device_id: str,
    message_id: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Create a pending assistant row without changing visible session metadata."""

    return save_message(
        conn,
        session_id=session_id,
        user_id=user_id,
        owner_device_id=owner_device_id,
        role="assistant",
        content="",
        status="generating",
        model=model,
        message_id=message_id,
    )


def complete_pending_assistant_message(
    conn: sqlite3.Connection,
    *,
    message_id: str,
    session_id: str,
    user_id: str,
    owner_device_id: str,
    content: str,
    failed: bool = False,
) -> dict[str, Any]:
    status = "failed" if failed else "completed"
    cursor = conn.execute(
        """
        UPDATE messages
        SET content = ?, status = ?
        WHERE message_id = ?
          AND session_id = ?
          AND user_id = ?
          AND role = 'assistant'
          AND status = 'generating'
          AND EXISTS (
              SELECT 1
              FROM sessions
              WHERE sessions.session_id = messages.session_id
                AND sessions.user_id = ?
                AND sessions.owner_device_id = ?
                AND sessions.status = 'active'
                AND sessions.deleted_at IS NULL
          )
        """,
        (
            content,
            status,
            message_id,
            session_id,
            user_id,
            user_id,
            owner_device_id,
        ),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError("pending_message_not_found")
    conn.commit()
    touch_session(conn, session_id=session_id, preview=content)
    row = conn.execute(
        """
        SELECT message_id, session_id, user_id, role, content, status, model, created_at
        FROM messages
        WHERE message_id = ?
        """,
        (message_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to complete pending message.")
    return _row_to_message(row)


def list_messages_for_session(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: str,
    owner_device_id: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            messages.message_id,
            messages.session_id,
            messages.user_id,
            messages.role,
            messages.content,
            messages.status,
            messages.model,
            messages.created_at
        FROM messages
        INNER JOIN sessions
            ON sessions.session_id = messages.session_id
        WHERE messages.session_id = ?
          AND messages.user_id = ?
          AND sessions.user_id = ?
          AND sessions.owner_device_id = ?
          AND sessions.status = 'active'
          AND sessions.deleted_at IS NULL
          AND messages.status IN ('completed', 'failed')
        ORDER BY messages.created_at ASC
        """,
        (session_id, user_id, user_id, owner_device_id),
    ).fetchall()

    messages = [_row_to_message(row) for row in rows]
    if not messages:
        return messages

    artifacts_by_message: dict[str, list[dict[str, Any]]] = {}
    artifact_rows = conn.execute(
        """
        SELECT
            artifacts.artifact_id,
            artifacts.assistant_message_id,
            artifacts.kind,
            artifacts.status,
            artifacts.revision,
            artifacts.title,
            artifacts.summary,
            artifacts.metadata_json,
            artifacts.expired_at
        FROM artifacts
        INNER JOIN sessions ON sessions.session_id = artifacts.session_id
        WHERE artifacts.session_id = ?
          AND artifacts.owner_user_id = ?
          AND artifacts.owner_device_id = ?
          AND artifacts.deleted_at IS NULL
          AND sessions.deleted_at IS NULL
        ORDER BY artifacts.created_at ASC
        """,
        (session_id, user_id, owner_device_id),
    ).fetchall()
    for artifact_row in artifact_rows:
        artifact_id = str(artifact_row["artifact_id"])
        revision = int(artifact_row["revision"])
        file_rows = conn.execute(
            """
            SELECT file_id, format, role, filename, content_type, size_bytes
            FROM artifact_files
            WHERE artifact_id = ?
              AND revision = ?
              AND status = 'available'
              AND deleted_at IS NULL
            ORDER BY CASE format WHEN 'png' THEN 0 ELSE 1 END
            """,
            (artifact_id, revision),
        ).fetchall()
        files = [dict(file_row) for file_row in file_rows]
        preview = next((item for item in files if item["role"] == "preview"), None)
        downloads = [item for item in files if item["role"] == "download" or item["format"] == "png"]
        artifact = {
            "artifact_id": artifact_id,
            "kind": artifact_row["kind"],
            "status": artifact_row["status"],
            "revision": revision,
            "title": artifact_row["title"],
            "summary": artifact_row["summary"],
            "preview": preview,
            "downloads": downloads,
            "metadata": json.loads(str(artifact_row["metadata_json"])),
            "expired_at": artifact_row["expired_at"],
        }
        if artifact_row["status"] == "expired":
            artifact["preview"] = None
            artifact["downloads"] = []
        artifacts_by_message.setdefault(str(artifact_row["assistant_message_id"]), []).append(artifact)

    for message in messages:
        message["artifacts"] = artifacts_by_message.get(str(message["message_id"]), [])
    return messages


def estimate_message_tokens(content: str) -> int:
    byte_count = len(content.encode("utf-8"))
    return max(1, (byte_count + 2) // 3)


def list_ai_context_messages_for_session(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: str,
    owner_device_id: str,
    current_message_id: str,
    max_messages: int = MAX_AI_CONTEXT_MESSAGES,
    max_estimated_tokens: int = MAX_AI_CONTEXT_ESTIMATED_TOKENS,
) -> AIContextWindow:
    total_stored_messages = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM messages
            INNER JOIN sessions
                ON sessions.session_id = messages.session_id
            WHERE messages.session_id = ?
              AND messages.user_id = ?
              AND sessions.user_id = ?
              AND sessions.owner_device_id = ?
              AND sessions.status = 'active'
              AND sessions.deleted_at IS NULL
            """,
            (session_id, user_id, user_id, owner_device_id),
        ).fetchone()[0]
    )
    rows = conn.execute(
        """
        SELECT
            messages.message_id,
            messages.session_id,
            messages.user_id,
            messages.role,
            messages.content,
            messages.status,
            messages.model,
            messages.created_at
        FROM messages
        INNER JOIN sessions
            ON sessions.session_id = messages.session_id
        WHERE messages.session_id = ?
          AND messages.user_id = ?
          AND sessions.user_id = ?
          AND sessions.owner_device_id = ?
          AND sessions.status = 'active'
          AND sessions.deleted_at IS NULL
              AND messages.role IN ('user', 'assistant')
              AND messages.status = 'completed'
              AND TRIM(messages.content) <> ''
        ORDER BY messages.rowid DESC
        LIMIT ?
        """,
        (
            session_id,
            user_id,
            user_id,
            owner_device_id,
            AI_CONTEXT_CANDIDATE_LIMIT,
        ),
    ).fetchall()
    messages_desc = [_row_to_message(row) for row in rows]
    current_index = next(
        (
            index
            for index, message in enumerate(messages_desc)
            if message["message_id"] == current_message_id
            and message["role"] == "user"
        ),
        None,
    )
    if current_index is None:
        raise ValueError("current_message_not_found")

    current_message = messages_desc[current_index]
    estimated_tokens = estimate_message_tokens(str(current_message["content"]))
    if estimated_tokens > max_estimated_tokens:
        raise ValueError("current_message_too_large")

    complete_pairs_desc: list[tuple[dict[str, Any], dict[str, Any]]] = []
    pending_assistant: dict[str, Any] | None = None
    for message in messages_desc[current_index + 1 :]:
        role = str(message["role"])
        if pending_assistant is None:
            if role == "assistant":
                pending_assistant = message
            continue
        if role != "user":
            continue

        pair_tokens = estimate_message_tokens(
            str(message["content"])
        ) + estimate_message_tokens(str(pending_assistant["content"]))
        if (
            1 + (len(complete_pairs_desc) + 1) * 2 > max_messages
            or estimated_tokens + pair_tokens > max_estimated_tokens
        ):
            break
        complete_pairs_desc.append((message, pending_assistant))
        estimated_tokens += pair_tokens
        pending_assistant = None

    selected: list[dict[str, Any]] = []
    for user_message, assistant_message in reversed(complete_pairs_desc):
        selected.extend((user_message, assistant_message))
    selected.append(current_message)

    print(
        "[MACSOFT_CHAT] AI context selected. "
        f"stored_count={total_stored_messages} "
        f"candidate_count={len(messages_desc)} "
        f"selected_count={len(selected)} "
        f"estimated_tokens={estimated_tokens}"
    )
    return AIContextWindow(
        messages=selected,
        estimated_tokens=estimated_tokens,
        candidate_count=len(messages_desc),
        total_stored_messages=total_stored_messages,
    )
