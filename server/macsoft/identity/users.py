from __future__ import annotations

import sqlite3


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT user_id, display_name, role, status, created_at, updated_at
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()


def get_default_admin(conn: sqlite3.Connection) -> sqlite3.Row:
    user = get_user_by_id(conn, "user_admin")

    if user is None:
        raise RuntimeError("Default admin user does not exist. Run init_db first.")

    return user
