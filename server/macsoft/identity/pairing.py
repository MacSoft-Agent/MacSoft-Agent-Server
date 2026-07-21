from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from macsoft.security import generate_pairing_code, utc_now_iso


def create_pairing_code(
    conn: sqlite3.Connection,
    user_id: str,
    ttl_minutes: int = 30,
) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)

    for _ in range(10):
        code = generate_pairing_code()

        try:
            conn.execute(
                """
                INSERT INTO pairing_codes (
                    pairing_code,
                    user_id,
                    status,
                    created_at,
                    expires_at,
                    claimed_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    user_id,
                    "active",
                    now.isoformat(),
                    expires_at.isoformat(),
                    None,
                ),
            )
            conn.commit()
            return code
        except sqlite3.IntegrityError:
            continue

    raise RuntimeError("Failed to generate a unique pairing code.")


def get_or_create_dev_pairing_code(conn: sqlite3.Connection, user_id: str) -> str:
    now = utc_now_iso()

    row = conn.execute(
        """
        SELECT pairing_code
        FROM pairing_codes
        WHERE user_id = ?
          AND status = 'active'
          AND claimed_at IS NULL
          AND expires_at > ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id, now),
    ).fetchone()

    if row is not None:
        return str(row["pairing_code"])

    return create_pairing_code(conn, user_id=user_id)


def claim_pairing_code(conn: sqlite3.Connection, pairing_code: str) -> sqlite3.Row:
    now = utc_now_iso()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            """
            SELECT pairing_code, user_id, status, created_at, expires_at, claimed_at
            FROM pairing_codes
            WHERE pairing_code = ?
            """,
            (pairing_code,),
        ).fetchone()

        if row is None or row["status"] != "active" or row["claimed_at"] is not None:
            conn.rollback()
            raise ValueError("invalid_pairing_code")

        if str(row["expires_at"]) <= now:
            conn.execute(
                """
                UPDATE pairing_codes
                SET status = 'expired'
                WHERE pairing_code = ?
                  AND status = 'active'
                  AND claimed_at IS NULL
                """,
                (pairing_code,),
            )
            conn.commit()
            raise ValueError("invalid_pairing_code")

        cursor = conn.execute(
            """
            UPDATE pairing_codes
            SET status = 'used',
                claimed_at = ?
            WHERE pairing_code = ?
              AND status = 'active'
              AND claimed_at IS NULL
              AND expires_at > ?
            """,
            (now, pairing_code, now),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            raise ValueError("invalid_pairing_code")
        conn.commit()
        return row
    except ValueError:
        raise
    except Exception:
        conn.rollback()
        raise
