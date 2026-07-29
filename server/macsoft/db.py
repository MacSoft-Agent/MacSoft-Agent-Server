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
                status TEXT NOT NULL DEFAULT 'completed'
                    CHECK (status IN ('generating', 'completed', 'failed')),
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

            CREATE TABLE IF NOT EXISTS artifact_generations (
                generation_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                assistant_message_id TEXT NOT NULL,
                owner_user_id TEXT NOT NULL,
                owner_device_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('chart')),
                attempt_no INTEGER NOT NULL DEFAULT 1 CHECK (attempt_no >= 1),
                supersedes_generation_id TEXT,
                is_latest INTEGER NOT NULL DEFAULT 1 CHECK (is_latest IN (0, 1)),
                status TEXT NOT NULL CHECK (
                    status IN (
                        'pending', 'data_ready', 'queued', 'rendering',
                        'ready', 'partial', 'failed', 'deleted'
                    )
                ),
                source_type TEXT NOT NULL CHECK (source_type IN ('mock', 'autocount')),
                render_input_json TEXT,
                render_input_expires_at TEXT,
                error_code TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                deleted_at TEXT,
                UNIQUE(owner_device_id, session_id, request_id, kind, attempt_no),
                FOREIGN KEY(session_id) REFERENCES sessions(session_id),
                FOREIGN KEY(assistant_message_id) REFERENCES messages(message_id),
                FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
                FOREIGN KEY(owner_device_id) REFERENCES devices(device_id),
                FOREIGN KEY(supersedes_generation_id)
                    REFERENCES artifact_generations(generation_id)
            );

            CREATE TABLE IF NOT EXISTS render_jobs (
                job_id TEXT PRIMARY KEY,
                generation_id TEXT NOT NULL,
                requested_formats_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN (
                        'queued', 'rendering', 'completed',
                        'completed_with_warning', 'failed', 'cancelled'
                    )
                ),
                attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
                max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
                worker_id TEXT,
                last_worker_id TEXT,
                lease_token TEXT,
                lease_expires_at TEXT,
                heartbeat_at TEXT,
                last_error_code TEXT,
                last_error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY(generation_id) REFERENCES artifact_generations(generation_id)
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                generation_id TEXT NOT NULL UNIQUE,
                session_id TEXT NOT NULL,
                assistant_message_id TEXT NOT NULL,
                owner_user_id TEXT NOT NULL,
                owner_device_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('chart')),
                status TEXT NOT NULL CHECK (
                    status IN ('ready', 'partial', 'unavailable', 'expired', 'deleted')
                ),
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expired_at TEXT,
                deleted_at TEXT,
                FOREIGN KEY(generation_id) REFERENCES artifact_generations(generation_id),
                FOREIGN KEY(session_id) REFERENCES sessions(session_id),
                FOREIGN KEY(assistant_message_id) REFERENCES messages(message_id),
                FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
                FOREIGN KEY(owner_device_id) REFERENCES devices(device_id)
            );

            CREATE TABLE IF NOT EXISTS artifact_files (
                file_id TEXT PRIMARY KEY,
                artifact_id TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK (revision >= 1),
                format TEXT NOT NULL CHECK (format IN ('png', 'pdf')),
                role TEXT NOT NULL CHECK (role IN ('preview', 'download')),
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                sha256 TEXT NOT NULL,
                storage_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'available'
                    CHECK (status IN ('available', 'missing', 'deleted')),
                created_at TEXT NOT NULL,
                deleted_at TEXT,
                UNIQUE(artifact_id, revision, format),
                FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id)
            );
            """
        )

        session_columns = _table_columns(conn, "sessions")
        if "deleted_at" not in session_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN deleted_at TEXT")

        message_columns = _table_columns(conn, "messages")
        if "status" not in message_columns:
            conn.execute(
                "ALTER TABLE messages ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'"
            )
        conn.execute(
            """
            UPDATE messages
            SET status = 'completed'
            WHERE status IS NULL
               OR status NOT IN ('generating', 'completed', 'failed')
            """
        )

        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user_active
            ON sessions(user_id, status, deleted_at, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_messages_session_user
            ON messages(session_id, user_id, created_at ASC);

            CREATE INDEX IF NOT EXISTS idx_messages_session_status_created
            ON messages(session_id, status, created_at ASC);

            CREATE INDEX IF NOT EXISTS idx_uploaded_files_owner
            ON uploaded_files(owner_user_id, owner_device_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_admin_sessions_active
            ON admin_sessions(deleted_at, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_admin_messages_session
            ON admin_messages(session_id, created_at ASC);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_artifact_generation_latest
            ON artifact_generations (
                owner_device_id, session_id, request_id, kind
            )
            WHERE is_latest = 1;

            CREATE INDEX IF NOT EXISTS idx_artifact_generations_status
            ON artifact_generations(status, updated_at);

            CREATE INDEX IF NOT EXISTS idx_render_jobs_claim
            ON render_jobs(status, lease_expires_at, created_at);

            CREATE INDEX IF NOT EXISTS idx_artifacts_message
            ON artifacts(assistant_message_id, status, revision);

            CREATE INDEX IF NOT EXISTS idx_artifacts_owner
            ON artifacts(owner_user_id, owner_device_id, session_id, status);

            CREATE INDEX IF NOT EXISTS idx_artifact_files_storage
            ON artifact_files(storage_key, status);
            """
        )

        # Existing databases cannot gain a CHECK constraint through ALTER TABLE.
        # Triggers provide the same write-time invariant after legacy values are
        # normalized above. Fresh databases also retain the table-level CHECK.
        conn.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS trg_messages_status_insert
            BEFORE INSERT ON messages
            WHEN NEW.status IS NOT NULL
             AND NEW.status NOT IN ('generating', 'completed', 'failed')
            BEGIN
                SELECT RAISE(ABORT, 'invalid_message_status');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_messages_status_insert_default
            AFTER INSERT ON messages
            WHEN NEW.status IS NULL
            BEGIN
                UPDATE messages SET status = 'completed'
                WHERE message_id = NEW.message_id;
            END;

            CREATE TRIGGER IF NOT EXISTS trg_messages_status_update
            BEFORE UPDATE OF status ON messages
            WHEN NEW.status IS NULL
              OR NEW.status NOT IN ('generating', 'completed', 'failed')
            BEGIN
                SELECT RAISE(ABORT, 'invalid_message_status');
            END;
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
