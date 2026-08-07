from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from macsoft.config import AppConfig
from macsoft.security import utc_now_iso


logger = logging.getLogger("macsoft.db")


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row["name"])
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _migrate_device_ownership(conn: sqlite3.Connection) -> dict[str, int]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        if "owner_device_id" not in _table_columns(conn, "sessions"):
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN owner_device_id TEXT "
                "REFERENCES devices(device_id)"
            )

        skill_sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'client_skills'"
        ).fetchone()
        skill_sql = "" if skill_sql_row is None else str(skill_sql_row["sql"] or "")
        normalized_skill_sql = "".join(skill_sql.lower().split())
        if (
            "owner_device_id" not in _table_columns(conn, "client_skills")
            or "unique(owner_device_id,slug)" not in normalized_skill_sql
        ):
            existing_columns = _table_columns(conn, "client_skills")
            owner_expression = "owner_device_id" if "owner_device_id" in existing_columns else "NULL"
            conn.execute("DROP TABLE IF EXISTS client_skills_device_v2")
            conn.execute(
                """
                CREATE TABLE client_skills_device_v2 (
                    skill_id TEXT PRIMARY KEY,
                    owner_user_id TEXT NOT NULL,
                    owner_device_id TEXT,
                    slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    content TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(owner_device_id, slug),
                    FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
                    FOREIGN KEY(owner_device_id) REFERENCES devices(device_id)
                )
                """
            )
            conn.execute(
                f"""
                INSERT INTO client_skills_device_v2 (
                    skill_id, owner_user_id, owner_device_id, slug, name,
                    description, content, enabled, created_at, updated_at
                )
                SELECT
                    skill_id, owner_user_id, {owner_expression}, slug, name,
                    description, content, enabled, created_at, updated_at
                FROM client_skills
                """
            )
            conn.execute("DROP TABLE client_skills")
            conn.execute("ALTER TABLE client_skills_device_v2 RENAME TO client_skills")

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_device_active
            ON sessions(user_id, owner_device_id, status, deleted_at, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_client_skills_owner
            ON client_skills(owner_user_id, owner_device_id, updated_at DESC)
            """
        )

        active_devices = conn.execute(
            """
            SELECT device_id, user_id
            FROM devices
            WHERE status = 'active'
              AND revoked_at IS NULL
            ORDER BY device_id
            """
        ).fetchall()
        sessions_backfilled = 0
        skills_backfilled = 0
        if len(active_devices) == 1:
            device_id = str(active_devices[0]["device_id"])
            user_id = str(active_devices[0]["user_id"])
            sessions_backfilled = conn.execute(
                """
                UPDATE sessions
                SET owner_device_id = ?
                WHERE owner_device_id IS NULL
                  AND user_id = ?
                """,
                (device_id, user_id),
            ).rowcount
            skills_backfilled = conn.execute(
                """
                UPDATE client_skills
                SET owner_device_id = ?
                WHERE owner_device_id IS NULL
                  AND owner_user_id = ?
                """,
                (device_id, user_id),
            ).rowcount

        sessions_unassigned = int(
            conn.execute(
                "SELECT COUNT(*) AS count FROM sessions WHERE owner_device_id IS NULL"
            ).fetchone()["count"]
        )
        skills_unassigned = int(
            conn.execute(
                "SELECT COUNT(*) AS count FROM client_skills WHERE owner_device_id IS NULL"
            ).fetchone()["count"]
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    counts = {
        "active_devices": len(active_devices),
        "sessions_backfilled": sessions_backfilled,
        "skills_backfilled": skills_backfilled,
        "sessions_unassigned": sessions_unassigned,
        "skills_unassigned": skills_unassigned,
    }
    logger.info(
        "device_ownership_migration active_devices=%s sessions_backfilled=%s "
        "skills_backfilled=%s sessions_unassigned=%s skills_unassigned=%s",
        counts["active_devices"],
        counts["sessions_backfilled"],
        counts["skills_backfilled"],
        counts["sessions_unassigned"],
        counts["skills_unassigned"],
    )
    return counts


def resolve_db_path(config: AppConfig) -> Path:
    configured_path = getattr(config, "config_path", None)
    config_root = (
        Path(configured_path).resolve().parent
        if configured_path
        else Path(__file__).resolve().parents[1]
    )
    db_path = Path(config.database.path)

    if not db_path.is_absolute():
        db_path = config_root / db_path

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _resolve_db_path(config: AppConfig) -> Path:
    """Backward-compatible alias for existing internal callers."""
    return resolve_db_path(config)


def connect_db(config: AppConfig) -> sqlite3.Connection:
    db_path = resolve_db_path(config)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(config: AppConfig) -> None:
    conn = connect_db(config)

    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                device_token TEXT NOT NULL UNIQUE,
                client_name TEXT NOT NULL,
                client_version TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                paired_at TEXT NOT NULL,
                last_seen_at TEXT,
                revoked_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS pairing_codes (
                pairing_code TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                claimed_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS client_skills (
                skill_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                owner_device_id TEXT,
                slug TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                content TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(owner_device_id, slug),
                FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
                FOREIGN KEY(owner_device_id) REFERENCES devices(device_id)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                owner_device_id TEXT,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0,
                last_message_preview TEXT NOT NULL DEFAULT '',
                hermes_stored_session_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(owner_device_id) REFERENCES devices(device_id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                model TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );


            CREATE TABLE IF NOT EXISTS uploaded_files (
                file_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                owner_device_id TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                media_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
                FOREIGN KEY(owner_device_id) REFERENCES devices(device_id)
            );

            CREATE TABLE IF NOT EXISTS admin_sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS admin_messages (
                message_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                model TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES admin_sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS message_attachments (
                message_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                PRIMARY KEY(message_id, file_id),
                FOREIGN KEY(message_id) REFERENCES messages(message_id),
                FOREIGN KEY(file_id) REFERENCES uploaded_files(file_id)
            );

            CREATE TABLE IF NOT EXISTS admin_uploaded_files (
                file_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                message_id TEXT,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                media_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES admin_sessions(session_id)
            );
            """
        )
        admin_file_columns = {row["name"] for row in conn.execute("PRAGMA table_info(admin_uploaded_files)")}
        if "message_id" not in admin_file_columns:
            conn.execute("ALTER TABLE admin_uploaded_files ADD COLUMN message_id TEXT")

        session_columns = _table_columns(conn, "sessions")
        if "deleted_at" not in session_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN deleted_at TEXT")

        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user_active
            ON sessions(user_id, status, deleted_at, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_messages_session_user
            ON messages(session_id, user_id, created_at ASC);

            CREATE INDEX IF NOT EXISTS idx_uploaded_files_owner
            ON uploaded_files(owner_user_id, owner_device_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_message_attachments_file
            ON message_attachments(file_id, message_id);

            CREATE INDEX IF NOT EXISTS idx_admin_sessions_active
            ON admin_sessions(deleted_at, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_admin_messages_session
            ON admin_messages(session_id, created_at ASC);

            CREATE INDEX IF NOT EXISTS idx_admin_uploaded_files_session
            ON admin_uploaded_files(session_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_admin_uploaded_files_message
            ON admin_uploaded_files(message_id, created_at ASC);
            """
        )

        now = utc_now_iso()

        conn.execute(
            """
            INSERT OR IGNORE INTO users (
                user_id,
                display_name,
                role,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "user_admin",
                "MacSoft Admin",
                "Admin",
                "active",
                now,
                now,
            ),
        )

        conn.commit()
        _migrate_device_ownership(conn)
    finally:
        conn.close()
