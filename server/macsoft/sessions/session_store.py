from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from macsoft.security import new_id, utc_now_iso


@dataclass(frozen=True)
class SessionDeleteResult:
    deleted: bool
    deleted_at: str


def _row_to_session(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["session_id"],
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "source": row["source"],
        "status": row["status"],
        "archived": bool(row["archived"]),
        "last_message_preview": row["last_message_preview"],
        "hermes_stored_session_id": row["hermes_stored_session_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_session(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    owner_device_id: str,
    title: str,
    source: str = "client",
) -> dict[str, Any]:
    now = utc_now_iso()
    session_id = new_id("sess")
    clean_title = (title or "New Chat").strip()[:80] or "New Chat"

    conn.execute(
        """
        INSERT INTO sessions (
            session_id,
            user_id,
            owner_device_id,
            title,
            source,
            status,
            archived,
            last_message_preview,
            hermes_stored_session_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            user_id,
            owner_device_id,
            clean_title,
            source,
            "active",
            0,
            "",
            None,
            now,
            now,
        ),
    )
    conn.commit()

    row = get_session_for_owner(
        conn,
        session_id=session_id,
        user_id=user_id,
        owner_device_id=owner_device_id,
    )

    if row is None:
        raise RuntimeError("Failed to create session.")

    return _row_to_session(row)


def list_sessions_for_owner(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    owner_device_id: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            session_id,
            user_id,
            title,
            source,
            status,
            archived,
            last_message_preview,
            hermes_stored_session_id,
            created_at,
            updated_at
        FROM sessions
        WHERE user_id = ?
          AND owner_device_id = ?
          AND status = 'active'
          AND deleted_at IS NULL
        ORDER BY updated_at DESC
        """,
        (user_id, owner_device_id),
    ).fetchall()

    return [_row_to_session(row) for row in rows]


def get_session_for_owner(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: str,
    owner_device_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            session_id,
            user_id,
            title,
            source,
            status,
            archived,
            last_message_preview,
            hermes_stored_session_id,
            created_at,
            updated_at
        FROM sessions
        WHERE session_id = ?
          AND user_id = ?
          AND owner_device_id = ?
          AND status = 'active'
          AND deleted_at IS NULL
        """,
        (session_id, user_id, owner_device_id),
    ).fetchone()


def require_session_for_owner(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: str,
    owner_device_id: str,
) -> sqlite3.Row:
    session = get_session_for_owner(
        conn,
        session_id=session_id,
        user_id=user_id,
        owner_device_id=owner_device_id,
    )

    if session is None:
        raise ValueError("session_not_found")

    return session


def get_session_including_deleted(
    conn: sqlite3.Connection,
    *,
    session_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            session_id,
            user_id,
            owner_device_id,
            status,
            deleted_at,
            updated_at
        FROM sessions
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()


def soft_delete_session(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    user_id: str,
    owner_device_id: str,
) -> SessionDeleteResult:
    deleted_at = utc_now_iso()
    cursor = conn.execute(
        """
        UPDATE sessions
        SET deleted_at = ?,
            updated_at = ?
        WHERE session_id = ?
          AND user_id = ?
          AND owner_device_id = ?
          AND deleted_at IS NULL
        """,
        (deleted_at, deleted_at, session_id, user_id, owner_device_id),
    )
    conn.commit()

    if cursor.rowcount == 1:
        return SessionDeleteResult(deleted=True, deleted_at=deleted_at)

    session = get_session_including_deleted(conn, session_id=session_id)
    if (
        session is not None
        and str(session["user_id"]) == user_id
        and str(session["owner_device_id"] or "") == owner_device_id
        and session["deleted_at"]
    ):
        return SessionDeleteResult(
            deleted=False,
            deleted_at=str(session["deleted_at"]),
        )

    raise ValueError("session_not_found")


def touch_session(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    preview: str,
) -> None:
    clean_preview = (preview or "").replace("\n", " ").strip()[:160]

    conn.execute(
        """
        UPDATE sessions
        SET updated_at = ?,
            last_message_preview = ?
        WHERE session_id = ?
          AND deleted_at IS NULL
        """,
        (utc_now_iso(), clean_preview, session_id),
    )
    conn.commit()
