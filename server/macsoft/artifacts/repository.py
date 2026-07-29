from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from macsoft.security import new_id, utc_now_iso


FINAL_GENERATION_STATUSES = {"ready", "partial", "failed", "deleted"}


def _future_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _future_minutes_iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


@dataclass(frozen=True)
class ClaimedRenderJob:
    job_id: str
    generation_id: str
    lease_token: str
    render_input_json: str
    requested_formats: tuple[str, ...]
    attempt_count: int


def create_generation(
    conn: sqlite3.Connection,
    *,
    request_id: str,
    session_id: str,
    assistant_message_id: str,
    owner_user_id: str,
    owner_device_id: str,
    source_type: str,
    render_input: dict[str, Any],
    environment: str,
    render_input_ttl_minutes: int,
    attempt_no: int = 1,
    supersedes_generation_id: str | None = None,
) -> str:
    if source_type == "mock" and environment == "production":
        raise ValueError("mock_artifact_forbidden")
    generation_id = new_id("gen_chart")
    now = utc_now_iso()
    conn.execute("BEGIN IMMEDIATE")
    try:
        session = conn.execute(
            """
            SELECT 1 FROM sessions
            WHERE session_id = ? AND user_id = ? AND owner_device_id = ?
              AND status = 'active' AND deleted_at IS NULL
            """,
            (session_id, owner_user_id, owner_device_id),
        ).fetchone()
        message = conn.execute(
            """
            SELECT 1 FROM messages
            WHERE message_id = ? AND session_id = ? AND user_id = ?
              AND role = 'assistant' AND status = 'generating'
            """,
            (assistant_message_id, session_id, owner_user_id),
        ).fetchone()
        if session is None or message is None:
            raise ValueError("foundation_owner_not_found")
        if supersedes_generation_id:
            updated = conn.execute(
                """
                UPDATE artifact_generations
                SET is_latest = 0, updated_at = ?
                WHERE generation_id = ? AND is_latest = 1
                  AND owner_device_id = ? AND session_id = ?
                  AND request_id = ? AND kind = 'chart'
                """,
                (
                    now,
                    supersedes_generation_id,
                    owner_device_id,
                    session_id,
                    request_id,
                ),
            )
            if updated.rowcount != 1:
                raise ValueError("superseded_generation_not_latest")
        conn.execute(
            """
            INSERT INTO artifact_generations (
                generation_id, request_id, session_id, assistant_message_id,
                owner_user_id, owner_device_id, kind, attempt_no,
                supersedes_generation_id, is_latest, status, source_type,
                render_input_json, render_input_expires_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'chart', ?, ?, 1, 'data_ready', ?, ?, ?, ?, ?)
            """,
            (
                generation_id,
                request_id,
                session_id,
                assistant_message_id,
                owner_user_id,
                owner_device_id,
                attempt_no,
                supersedes_generation_id,
                source_type,
                json.dumps(render_input, ensure_ascii=False, separators=(",", ":")),
                _future_minutes_iso(render_input_ttl_minutes),
                now,
                now,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return generation_id


def enqueue_render_job(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    requested_formats: tuple[str, ...] = ("png", "pdf"),
    max_attempts: int = 3,
) -> str:
    formats = tuple(dict.fromkeys(requested_formats))
    if "png" not in formats or any(item not in {"png", "pdf"} for item in formats):
        raise ValueError("invalid_render_formats")
    job_id = new_id("render_job")
    now = utc_now_iso()
    conn.execute("BEGIN IMMEDIATE")
    try:
        updated = conn.execute(
            """
            UPDATE artifact_generations SET status = 'queued', updated_at = ?
            WHERE generation_id = ? AND status = 'data_ready'
            """,
            (now, generation_id),
        )
        if updated.rowcount != 1:
            raise ValueError("generation_not_data_ready")
        conn.execute(
            """
            INSERT INTO render_jobs (
                job_id, generation_id, requested_formats_json, status,
                attempt_count, max_attempts, created_at, updated_at
            ) VALUES (?, ?, ?, 'queued', 0, ?, ?, ?)
            """,
            (job_id, generation_id, json.dumps(formats), max_attempts, now, now),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return job_id


def claim_render_job(
    conn: sqlite3.Connection,
    *,
    worker_id: str,
    lease_seconds: int,
    job_id: str | None = None,
) -> ClaimedRenderJob | None:
    now = utc_now_iso()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            """
            SELECT jobs.job_id, jobs.generation_id, jobs.requested_formats_json,
                   jobs.attempt_count, jobs.max_attempts,
                   generations.render_input_json
            FROM render_jobs AS jobs
            INNER JOIN artifact_generations AS generations
              ON generations.generation_id = jobs.generation_id
            WHERE (
                    jobs.status = 'queued'
                 OR (jobs.status = 'rendering' AND jobs.lease_expires_at < ?)
            )
              AND (? IS NULL OR jobs.job_id = ?)
              AND jobs.attempt_count < jobs.max_attempts
              AND generations.status NOT IN ('ready', 'partial', 'failed', 'deleted')
              AND generations.render_input_expires_at > ?
            ORDER BY jobs.created_at ASC
            LIMIT 1
            """,
            (now, job_id, job_id, now),
        ).fetchone()
        if row is None:
            conn.commit()
            return None
        lease_token = new_id("lease")
        cursor = conn.execute(
            """
            UPDATE render_jobs
            SET status = 'rendering', attempt_count = attempt_count + 1,
                last_worker_id = worker_id, worker_id = ?, lease_token = ?,
                lease_expires_at = ?, heartbeat_at = ?, updated_at = ?
            WHERE job_id = ?
              AND attempt_count < max_attempts
              AND (status = 'queued' OR (status = 'rendering' AND lease_expires_at < ?))
            """,
            (
                worker_id,
                lease_token,
                _future_iso(lease_seconds),
                now,
                now,
                row["job_id"],
                now,
            ),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return None
        conn.execute(
            """
            UPDATE artifact_generations SET status = 'rendering', updated_at = ?
            WHERE generation_id = ? AND status IN ('queued', 'rendering')
            """,
            (now, row["generation_id"]),
        )
        conn.commit()
        return ClaimedRenderJob(
            job_id=str(row["job_id"]),
            generation_id=str(row["generation_id"]),
            lease_token=lease_token,
            render_input_json=str(row["render_input_json"]),
            requested_formats=tuple(json.loads(str(row["requested_formats_json"]))),
            attempt_count=int(row["attempt_count"]) + 1,
        )
    except Exception:
        conn.rollback()
        raise


def renew_lease(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    worker_id: str,
    lease_token: str,
    lease_seconds: int,
) -> bool:
    now = utc_now_iso()
    cursor = conn.execute(
        """
        UPDATE render_jobs SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
        WHERE job_id = ? AND worker_id = ? AND lease_token = ? AND status = 'rendering'
        """,
        (now, _future_iso(lease_seconds), now, job_id, worker_id, lease_token),
    )
    conn.commit()
    return cursor.rowcount == 1


def owns_lease(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    worker_id: str,
    lease_token: str,
) -> bool:
    return conn.execute(
        """
        SELECT 1 FROM render_jobs
        WHERE job_id = ? AND worker_id = ? AND lease_token = ? AND status = 'rendering'
        """,
        (job_id, worker_id, lease_token),
    ).fetchone() is not None


def mark_render_failure(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    worker_id: str,
    lease_token: str,
    code: str,
    message: str,
) -> bool:
    now = utc_now_iso()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            """
            SELECT generation_id, attempt_count, max_attempts
            FROM render_jobs
            WHERE job_id = ? AND worker_id = ? AND lease_token = ? AND status = 'rendering'
            """,
            (job_id, worker_id, lease_token),
        ).fetchone()
        if row is None:
            conn.rollback()
            return False
        terminal = int(row["attempt_count"]) >= int(row["max_attempts"])
        job_status = "failed" if terminal else "queued"
        conn.execute(
            """
            UPDATE render_jobs
            SET status = ?, last_error_code = ?, last_error_message = ?,
                worker_id = NULL, lease_token = NULL, lease_expires_at = NULL,
                updated_at = ?, completed_at = CASE WHEN ? THEN ? ELSE NULL END
            WHERE job_id = ? AND worker_id = ? AND lease_token = ?
            """,
            (job_status, code, message[:500], now, terminal, now, job_id, worker_id, lease_token),
        )
        conn.execute(
            """
            UPDATE artifact_generations
            SET status = ?, error_code = ?, error_message = ?, updated_at = ?,
                completed_at = CASE WHEN ? THEN ? ELSE NULL END
            WHERE generation_id = ?
            """,
            ("failed" if terminal else "queued", code, message[:500], now, terminal, now, row["generation_id"]),
        )
        if terminal:
            conn.execute(
                """
                UPDATE messages SET status = 'failed', content = ?
                WHERE message_id = (
                    SELECT assistant_message_id FROM artifact_generations WHERE generation_id = ?
                ) AND status = 'generating'
                """,
                ("The chart could not be rendered.", row["generation_id"]),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def finalize_render(
    conn: sqlite3.Connection,
    *,
    job: ClaimedRenderJob,
    worker_id: str,
    title: str,
    summary: str,
    metadata: dict[str, Any],
    png_file: dict[str, Any],
    pdf_file: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Publish DB state only while the caller still owns the fenced lease."""

    now = utc_now_iso()
    conn.execute("BEGIN IMMEDIATE")
    try:
        generation = conn.execute(
            """
            SELECT generations.*, sessions.deleted_at AS session_deleted_at
            FROM artifact_generations AS generations
            INNER JOIN sessions ON sessions.session_id = generations.session_id
            WHERE generations.generation_id = ?
            """,
            (job.generation_id,),
        ).fetchone()
        fenced = conn.execute(
            """
            SELECT 1 FROM render_jobs
            WHERE job_id = ? AND generation_id = ? AND worker_id = ?
              AND lease_token = ? AND status = 'rendering'
            """,
            (job.job_id, job.generation_id, worker_id, job.lease_token),
        ).fetchone()
        if generation is None or fenced is None:
            raise ValueError("render_lease_lost")
        if generation["session_deleted_at"] is not None or generation["status"] == "deleted":
            conn.execute(
                """
                UPDATE render_jobs SET status = 'cancelled', completed_at = ?, updated_at = ?
                WHERE job_id = ? AND worker_id = ? AND lease_token = ?
                """,
                (now, now, job.job_id, worker_id, job.lease_token),
            )
            conn.execute(
                """
                UPDATE artifact_generations
                SET status = 'deleted', deleted_at = ?, updated_at = ?
                WHERE generation_id = ?
                """,
                (now, now, job.generation_id),
            )
            conn.commit()
            raise ValueError("session_deleted")

        artifact_id = new_id("artifact_chart")
        partial = "pdf" in job.requested_formats and pdf_file is None
        status = "partial" if partial else "ready"
        warnings = list(metadata.get("warnings") or [])
        if partial:
            warnings.append(
                {
                    "code": "pdf_render_unavailable",
                    "message": "The chart image is available, but PDF generation is unavailable.",
                }
            )
        metadata = {**metadata, "warnings": warnings, "missing_formats": ["pdf"] if partial else []}
        conn.execute(
            """
            INSERT INTO artifacts (
                artifact_id, generation_id, session_id, assistant_message_id,
                owner_user_id, owner_device_id, kind, status, revision,
                title, summary, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'chart', ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                job.generation_id,
                generation["session_id"],
                generation["assistant_message_id"],
                generation["owner_user_id"],
                generation["owner_device_id"],
                status,
                title[:120],
                summary[:500],
                json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
                now,
                now,
            ),
        )
        files = [("png", "preview", png_file)]
        if pdf_file is not None:
            files.append(("pdf", "download", pdf_file))
        for format_name, role, file_data in files:
            conn.execute(
                """
                INSERT INTO artifact_files (
                    file_id, artifact_id, revision, format, role, filename,
                    content_type, size_bytes, sha256, storage_key, status, created_at
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, 'available', ?)
                """,
                (
                    new_id("artifact_file"),
                    artifact_id,
                    format_name,
                    role,
                    file_data["filename"],
                    file_data["content_type"],
                    file_data["size_bytes"],
                    file_data["sha256"],
                    file_data["storage_key"],
                    now,
                ),
            )
        conn.execute(
            """
            UPDATE render_jobs
            SET status = ?, completed_at = ?, updated_at = ?
            WHERE job_id = ? AND worker_id = ? AND lease_token = ? AND status = 'rendering'
            """,
            ("completed_with_warning" if partial else "completed", now, now, job.job_id, worker_id, job.lease_token),
        )
        conn.execute(
            """
            UPDATE artifact_generations
            SET status = ?, completed_at = ?, updated_at = ?, render_input_json = NULL
            WHERE generation_id = ?
            """,
            (status, now, now, job.generation_id),
        )
        readable = summary.strip() or title.strip()
        conn.execute(
            """
            UPDATE messages SET status = 'completed', content = ?
            WHERE message_id = ? AND status = 'generating'
            """,
            (readable, generation["assistant_message_id"]),
        )
        conn.execute(
            """
            UPDATE sessions SET updated_at = ?, last_message_preview = ?
            WHERE session_id = ? AND deleted_at IS NULL
            """,
            (now, readable.replace("\n", " ")[:160], generation["session_id"]),
        )
        conn.commit()
        return artifact_id, status
    except Exception:
        conn.rollback()
        raise


def get_visible_artifact(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    owner_user_id: str,
    owner_device_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT artifacts.*
        FROM artifacts
        INNER JOIN sessions ON sessions.session_id = artifacts.session_id
        WHERE artifacts.artifact_id = ?
          AND artifacts.owner_user_id = ?
          AND artifacts.owner_device_id = ?
          AND artifacts.deleted_at IS NULL
          AND sessions.deleted_at IS NULL
        """,
        (artifact_id, owner_user_id, owner_device_id),
    ).fetchone()


def get_visible_artifact_file(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    file_id: str,
    owner_user_id: str,
    owner_device_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT files.*, artifacts.status AS artifact_status,
               artifacts.expired_at, artifacts.revision AS artifact_revision
        FROM artifact_files AS files
        INNER JOIN artifacts ON artifacts.artifact_id = files.artifact_id
        INNER JOIN sessions ON sessions.session_id = artifacts.session_id
        WHERE files.file_id = ? AND files.artifact_id = ?
          AND files.revision = artifacts.revision
          AND files.status = 'available' AND files.deleted_at IS NULL
          AND artifacts.owner_user_id = ? AND artifacts.owner_device_id = ?
          AND artifacts.deleted_at IS NULL AND sessions.deleted_at IS NULL
        """,
        (file_id, artifact_id, owner_user_id, owner_device_id),
    ).fetchone()
