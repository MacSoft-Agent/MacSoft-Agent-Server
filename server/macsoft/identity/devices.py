from __future__ import annotations

import sqlite3
from typing import Any

from macsoft.security import generate_device_token, parse_bearer_token, utc_now_iso


def create_or_replace_device(
    conn: sqlite3.Connection,
    *,
    device_id: str,
    user_id: str,
    display_name: str,
    role: str,
    client_name: str,
    client_version: str,
) -> dict[str, Any]:
    now = utc_now_iso()
    device_token = generate_device_token()

    conn.execute(
        """
        INSERT INTO devices (
            device_id,
            user_id,
            device_token,
            client_name,
            client_version,
            display_name,
            role,
            status,
            paired_at,
            last_seen_at,
            revoked_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            user_id = excluded.user_id,
            device_token = excluded.device_token,
            client_name = excluded.client_name,
            client_version = excluded.client_version,
            display_name = excluded.display_name,
            role = excluded.role,
            status = 'active',
            paired_at = excluded.paired_at,
            last_seen_at = excluded.last_seen_at,
            revoked_at = NULL
        """,
        (
            device_id,
            user_id,
            device_token,
            client_name,
            client_version,
            display_name,
            role,
            "active",
            now,
            now,
            None,
        ),
    )

    conn.commit()

    return {
        "device_id": device_id,
        "device_token": device_token,
        "user_id": user_id,
        "display_name": display_name,
        "role": role,
        "client_name": client_name,
        "client_version": client_version,
        "paired_at": now,
    }


def get_device_by_token(
    conn: sqlite3.Connection,
    *,
    device_token: str,
    device_id: str | None,
) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT
            d.device_id,
            d.user_id,
            d.device_token,
            d.client_name,
            d.client_version,
            d.display_name,
            d.role,
            d.status,
            d.paired_at,
            d.last_seen_at,
            d.revoked_at,
            u.status AS user_status
        FROM devices d
        JOIN users u ON u.user_id = d.user_id
        WHERE d.device_token = ?
        """,
        (device_token,),
    ).fetchone()

    if row is None:
        return None

    if device_id and row["device_id"] != device_id:
        return None

    if row["status"] != "active":
        return None

    if row["revoked_at"] is not None:
        return None

    if row["user_status"] != "active":
        return None

    conn.execute(
        """
        UPDATE devices
        SET last_seen_at = ?
        WHERE device_id = ?
        """,
        (utc_now_iso(), row["device_id"]),
    )
    conn.commit()

    return row


def require_device(
    conn: sqlite3.Connection,
    *,
    authorization: str | None,
    device_id: str | None,
) -> sqlite3.Row:
    token = parse_bearer_token(authorization)

    if token is None:
        raise ValueError("invalid_device_token")

    device = get_device_by_token(
        conn,
        device_token=token,
        device_id=device_id,
    )

    if device is None:
        raise ValueError("invalid_device_token")

    return device
