from __future__ import annotations

import sqlite3

from macsoft.security import new_id, utc_now_iso


def record_run_started(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    device_id: str,
    profile_id: str,
    session_id: str,
) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO agent_runs (
            run_id, device_id, profile_id, session_id, completion_status,
            learning_status, created_at, completed_at
        ) VALUES (?, ?, ?, ?, 'running', 'pending', ?, NULL)
        """,
        (run_id, device_id, profile_id, session_id, now),
    )
    conn.commit()


def record_run_finished(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    completion_status: str,
    learning_status: str,
) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        UPDATE agent_runs
        SET completion_status = ?, learning_status = ?, completed_at = ?
        WHERE run_id = ?
        """,
        (completion_status, learning_status, now, run_id),
    )
    if completion_status == "completed":
        conn.execute(
            """
            INSERT INTO learning_events (
                event_id, run_id, profile_id, event_type, status, detail, created_at
            )
            SELECT ?, run_id, profile_id, 'native_after_run', ?, ?, ?
            FROM agent_runs WHERE run_id = ?
            """,
            (new_id("learn"), learning_status, "Hermes native review was eligible after completion.", now, run_id),
        )
    conn.commit()
