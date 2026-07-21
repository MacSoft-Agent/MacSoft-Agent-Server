from __future__ import annotations

import sqlite3
from typing import Any

from macsoft.security import new_id, utc_now_iso


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["session_id"],
        "session_id": row["session_id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_admin_session(conn: sqlite3.Connection, title: str) -> dict[str, Any]:
    now = utc_now_iso()
    session_id = new_id("admin_sess")
    clean_title = (title or "New Admin Chat").strip()[:80] or "New Admin Chat"
    conn.execute(
        """
        INSERT INTO admin_sessions (session_id, title, created_at, updated_at, deleted_at)
        VALUES (?, ?, ?, ?, NULL)
        """,
        (session_id, clean_title, now, now),
    )
    conn.commit()
    session = get_admin_session(conn, session_id)
    if session is None:
        raise RuntimeError("Failed to create Admin session.")
    return session


def list_admin_sessions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT session_id, title, created_at, updated_at
        FROM admin_sessions
        WHERE deleted_at IS NULL
        ORDER BY updated_at DESC
        """
    ).fetchall()
    return [_row(row) for row in rows]


def get_admin_session(conn: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT session_id, title, created_at, updated_at
        FROM admin_sessions
        WHERE session_id = ? AND deleted_at IS NULL
        """,
        (session_id,),
    ).fetchone()
    return _row(row) if row is not None else None


def soft_delete_admin_session(conn: sqlite3.Connection, session_id: str) -> bool:
    now = utc_now_iso()
    cursor = conn.execute(
        "UPDATE admin_sessions SET deleted_at = ?, updated_at = ? WHERE session_id = ? AND deleted_at IS NULL",
        (now, now, session_id),
    )
    conn.commit()
    return cursor.rowcount == 1


def touch_admin_session(conn: sqlite3.Connection, session_id: str, preview: str) -> None:
    conn.execute(
        "UPDATE admin_sessions SET updated_at = ?, title = CASE WHEN title = 'New Admin Chat' THEN ? ELSE title END WHERE session_id = ? AND deleted_at IS NULL",
        (utc_now_iso(), preview.replace("\n", " ").strip()[:80] or "New Admin Chat", session_id),
    )
    conn.commit()
