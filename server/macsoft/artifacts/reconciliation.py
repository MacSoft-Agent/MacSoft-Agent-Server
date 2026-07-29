from __future__ import annotations

import time
import shutil
from datetime import datetime, timedelta, timezone

from macsoft.artifacts.worker import resolve_artifact_storage
from macsoft.db import connect_db
from macsoft.security import utc_now_iso


def reconcile_artifacts(config, *, stale_minutes: int = 10, orphan_grace_seconds: int = 300) -> dict[str, int]:
    """Apply deterministic close/cleanup rules; never regenerates business data."""

    conn = connect_db(config)
    storage = resolve_artifact_storage(config)
    now = utc_now_iso()
    stale_before = (datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)).isoformat()
    counts = {
        "stale_messages_failed": 0,
        "leases_requeued": 0,
        "leases_failed": 0,
        "artifacts_unavailable": 0,
        "generations_failed": 0,
        "deleted_session_artifacts": 0,
        "orphan_files_deleted": 0,
        "stale_staging_dirs_deleted": 0,
    }
    try:
        conn.execute("BEGIN IMMEDIATE")
        stale = conn.execute(
            """
            SELECT messages.message_id, generations.generation_id
            FROM messages
            LEFT JOIN artifact_generations AS generations
              ON generations.assistant_message_id = messages.message_id
            WHERE messages.status = 'generating' AND messages.created_at < ?
            """,
            (stale_before,),
        ).fetchall()
        for row in stale:
            conn.execute(
                "UPDATE messages SET status = 'failed', content = ? WHERE message_id = ?",
                ("Chart generation was interrupted.", row["message_id"]),
            )
            counts["stale_messages_failed"] += 1
            if row["generation_id"]:
                conn.execute(
                    """
                    UPDATE artifact_generations SET status = 'failed', error_code = ?,
                        error_message = ?, updated_at = ?, completed_at = ?
                    WHERE generation_id = ? AND status NOT IN ('ready','partial','failed','deleted')
                    """,
                    ("generation_stale", "Generation did not complete before its TTL.", now, now, row["generation_id"]),
                )

        expired_jobs = conn.execute(
            """
            SELECT job_id, generation_id, attempt_count, max_attempts
            FROM render_jobs
            WHERE status = 'rendering' AND lease_expires_at < ?
            """,
            (now,),
        ).fetchall()
        for job in expired_jobs:
            terminal = int(job["attempt_count"]) >= int(job["max_attempts"])
            conn.execute(
                """
                UPDATE render_jobs SET status = ?, worker_id = NULL, lease_token = NULL,
                    lease_expires_at = NULL, last_error_code = 'lease_expired',
                    last_error_message = 'Renderer lease expired.', updated_at = ?,
                    completed_at = CASE WHEN ? THEN ? ELSE NULL END
                WHERE job_id = ? AND status = 'rendering'
                """,
                ("failed" if terminal else "queued", now, terminal, now, job["job_id"]),
            )
            conn.execute(
                """
                UPDATE artifact_generations SET status = ?, error_code = 'lease_expired',
                    error_message = 'Renderer lease expired.', updated_at = ?,
                    completed_at = CASE WHEN ? THEN ? ELSE NULL END
                WHERE generation_id = ? AND status = 'rendering'
                """,
                ("failed" if terminal else "queued", now, terminal, now, job["generation_id"]),
            )
            counts["leases_failed" if terminal else "leases_requeued"] += 1

        expired_inputs = conn.execute(
            """
            SELECT generation_id, assistant_message_id
            FROM artifact_generations
            WHERE status IN ('data_ready','queued') AND render_input_expires_at < ?
            """,
            (now,),
        ).fetchall()
        for generation in expired_inputs:
            conn.execute(
                """
                UPDATE artifact_generations SET status = 'failed',
                    error_code = 'render_input_expired',
                    error_message = 'Validated render input expired before rendering.',
                    updated_at = ?, completed_at = ? WHERE generation_id = ?
                """,
                (now, now, generation["generation_id"]),
            )
            conn.execute(
                """
                UPDATE render_jobs SET status = 'failed',
                    last_error_code = 'render_input_expired',
                    last_error_message = 'Validated render input expired before rendering.',
                    updated_at = ?, completed_at = ?
                WHERE generation_id = ? AND status = 'queued'
                """,
                (now, now, generation["generation_id"]),
            )
            conn.execute(
                """
                UPDATE messages SET status = 'failed', content = ?
                WHERE message_id = ? AND status = 'generating'
                """,
                ("Chart generation input expired before rendering.", generation["assistant_message_id"]),
            )
            counts["generations_failed"] += 1

        missing_previews = conn.execute(
            """
            SELECT artifacts.artifact_id, artifacts.generation_id
            FROM artifacts
            LEFT JOIN artifact_files ON artifact_files.artifact_id = artifacts.artifact_id
              AND artifact_files.revision = artifacts.revision
              AND artifact_files.format = 'png' AND artifact_files.status = 'available'
              AND artifact_files.deleted_at IS NULL
            WHERE artifacts.status IN ('ready','partial') AND artifact_files.file_id IS NULL
            """
        ).fetchall()
        for artifact in missing_previews:
            conn.execute(
                "UPDATE artifacts SET status = 'unavailable', updated_at = ? WHERE artifact_id = ?",
                (now, artifact["artifact_id"]),
            )
            conn.execute(
                """
                UPDATE artifact_generations SET error_code = 'preview_missing',
                    error_message = 'Ready Artifact has no preview PNG.', updated_at = ?
                WHERE generation_id = ?
                """,
                (now, artifact["generation_id"]),
            )
            counts["artifacts_unavailable"] += 1

        missing_artifacts = conn.execute(
            """
            SELECT generations.generation_id
            FROM artifact_generations AS generations
            LEFT JOIN artifacts ON artifacts.generation_id = generations.generation_id
            WHERE generations.status IN ('ready','partial') AND artifacts.artifact_id IS NULL
            """
        ).fetchall()
        for generation in missing_artifacts:
            conn.execute(
                """
                UPDATE artifact_generations SET status = 'failed', error_code = 'artifact_missing',
                    error_message = 'Generation completed without an Artifact.', updated_at = ?, completed_at = ?
                WHERE generation_id = ?
                """,
                (now, now, generation["generation_id"]),
            )
            counts["generations_failed"] += 1

        deleted = conn.execute(
            """
            SELECT artifacts.artifact_id
            FROM artifacts INNER JOIN sessions ON sessions.session_id = artifacts.session_id
            WHERE sessions.deleted_at IS NOT NULL AND artifacts.status <> 'deleted'
            """
        ).fetchall()
        for artifact in deleted:
            conn.execute(
                "UPDATE artifacts SET status = 'deleted', deleted_at = ?, updated_at = ? WHERE artifact_id = ?",
                (now, now, artifact["artifact_id"]),
            )
            conn.execute(
                "UPDATE artifact_files SET status = 'deleted', deleted_at = ? WHERE artifact_id = ?",
                (now, artifact["artifact_id"]),
            )
            counts["deleted_session_artifacts"] += 1

        conn.commit()

        referenced = {
            str(row["storage_key"])
            for row in conn.execute(
                "SELECT DISTINCT storage_key FROM artifact_files WHERE status = 'available' AND deleted_at IS NULL"
            ).fetchall()
        }
        cutoff = time.time() - orphan_grace_seconds
        for path in storage.files_root.rglob("*"):
            if not path.is_file() or path.stat().st_mtime > cutoff:
                continue
            key = path.relative_to(storage.files_root).as_posix()
            if key not in referenced:
                path.unlink(missing_ok=True)
                counts["orphan_files_deleted"] += 1
        for generation_dir in storage.staging_root.iterdir():
            if not generation_dir.is_dir():
                continue
            for attempt_dir in generation_dir.iterdir():
                if attempt_dir.is_dir() and attempt_dir.stat().st_mtime <= cutoff:
                    shutil.rmtree(attempt_dir, ignore_errors=True)
                    counts["stale_staging_dirs_deleted"] += 1
            if generation_dir.exists() and not any(generation_dir.iterdir()):
                generation_dir.rmdir()
        return counts
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
