from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from macsoft.artifacts.invoice_chart import (
    build_invoice_count_render_input,
    is_invoice_chart_request,
)
from macsoft.artifacts.renderer import load_render_input, render_chart_png
from macsoft.artifacts.repository import (
    claim_render_job,
    create_generation,
    finalize_render,
    mark_render_failure,
    owns_lease,
)
from macsoft.artifacts.reconciliation import reconcile_artifacts
from macsoft.artifacts.service import create_foundation_mock_job
from macsoft.artifacts.storage import ArtifactStorage
from macsoft.artifacts.worker import ChartRenderWorker, resolve_artifact_storage
from macsoft.config import load_config
from macsoft.db import connect_db, init_db
from macsoft.gateway.errors import register_exception_handlers
from macsoft.gateway.routes_artifacts import router as artifacts_router
from macsoft.sessions.message_store import (
    list_ai_context_messages_for_session,
    list_messages_for_session,
    save_message,
)
from macsoft.sessions.session_store import soft_delete_session


class ChartArtifactFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        config_path = root / "macsoft-server.yaml"
        config_path.write_text(
            "\n".join(
                (
                    "server:",
                    '  host: "127.0.0.1"',
                    "  port: 8787",
                    "database:",
                    '  path: "./data/server.db"',
                    "hermes:",
                    '  home: "../hermes"',
                    '  api_base_url: "http://127.0.0.1:8642"',
                    '  api_key: "test"',
                    "  request_timeout_seconds: 5",
                    "models:",
                    '  default_model: "server-default"',
                    '  fallback_model: "server-fallback"',
                    "runtime:",
                    '  mode: "minimal"',
                    "autocount:",
                    "  enabled: false",
                    '  catalog_path: "./catalog.json"',
                    "chart_artifacts:",
                    "  enabled: false",
                    '  environment: "test"',
                    '  storage_path: "./data/chart-artifacts"',
                    "  worker_max_attempts: 3",
                    "  lease_seconds: 30",
                    "  render_input_ttl_minutes: 60",
                    "  retention_days: 30",
                    "",
                )
            ),
            encoding="utf-8",
        )
        self.config = load_config(str(config_path))
        init_db(self.config)
        conn = connect_db(self.config)
        now = "2026-07-29T00:00:00+00:00"
        try:
            conn.execute(
                """
                INSERT INTO devices (
                    device_id, user_id, device_token, client_name, client_version,
                    display_name, role, status, paired_at, last_seen_at, revoked_at
                ) VALUES ('device-a', 'user_admin', 'token-a', 'Client', '1',
                          'A', 'Admin', 'active', ?, ?, NULL)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO devices (
                    device_id, user_id, device_token, client_name, client_version,
                    display_name, role, status, paired_at, last_seen_at, revoked_at
                ) VALUES ('device-b', 'user_admin', 'token-b', 'Client', '1',
                          'B', 'Admin', 'active', ?, ?, NULL)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, user_id, owner_device_id, title, source, status,
                    archived, last_message_preview, hermes_stored_session_id,
                    created_at, updated_at, deleted_at
                ) VALUES ('session-a', 'user_admin', 'device-a', 'Foundation',
                          'client', 'active', 0, '', NULL, ?, ?, NULL)
                """,
                (now, now),
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def render_input() -> dict:
        return {
            "title": "Demo Sales Invoice Trend",
            "summary": "Foundation test chart.",
            "dataset": {
                "points": [
                    {"key": "2026-07-01", "value": "10.00"},
                    {"key": "2026-07-02", "value": "24.50"},
                    {"key": "2026-07-03", "value": "18.25"},
                ]
            },
            "metadata": {"source": {"type": "mock"}},
        }

    def test_invoice_chart_intent_requires_both_invoice_and_chart_terms(self) -> None:
        self.assertTrue(is_invoice_chart_request("Generate an invoice chart"))
        self.assertTrue(is_invoice_chart_request("我要销售发票趋势图"))
        self.assertFalse(is_invoice_chart_request("Show the latest invoices"))
        self.assertFalse(is_invoice_chart_request("Generate a cashflow chart"))

    def test_invoice_count_dataset_uses_dates_without_claiming_financial_amounts(self) -> None:
        render_input = build_invoice_count_render_input(
            [
                {"DocDate": "2026-06-01T00:00:00", "DocNo": "A"},
                {"DocDate": "2026-06-20T00:00:00", "DocNo": "B"},
                {"DocDate": "2026-07-03T00:00:00", "DocNo": "C"},
            ]
        )
        self.assertEqual(
            render_input["dataset"]["points"],
            [{"key": "2026-06", "value": 2}, {"key": "2026-07", "value": 1}],
        )
        self.assertEqual(render_input["metric"]["name"], "invoice_count")
        self.assertFalse(render_input["metadata"]["financial_amount"])

    def create_job(self, requested_formats: tuple[str, ...] = ("png",)) -> dict[str, str]:
        conn = connect_db(self.config)
        try:
            return create_foundation_mock_job(
                conn,
                self.config,
                request_id="request-a",
                session_id="session-a",
                owner_user_id="user_admin",
                owner_device_id="device-a",
                render_input=self.render_input(),
                requested_formats=requested_formats,
            )
        finally:
            conn.close()

    def test_png_only_worker_publishes_ready_artifact_and_history(self) -> None:
        ids = self.create_job()
        worker = ChartRenderWorker(
            self.config,
            worker_id="worker-a",
            storage=resolve_artifact_storage(self.config),
        )
        self.assertTrue(worker.process_one())

        conn = connect_db(self.config)
        try:
            generation = conn.execute(
                "SELECT status FROM artifact_generations WHERE generation_id = ?",
                (ids["generation_id"],),
            ).fetchone()
            artifact = conn.execute("SELECT * FROM artifacts").fetchone()
            file_row = conn.execute("SELECT * FROM artifact_files").fetchone()
            self.assertEqual(generation["status"], "ready")
            self.assertEqual(artifact["status"], "ready")
            self.assertEqual(file_row["format"], "png")
            messages = list_messages_for_session(
                conn,
                session_id="session-a",
                user_id="user_admin",
                owner_device_id="device-a",
            )
            assistant = next(row for row in messages if row["role"] == "assistant")
            self.assertEqual(assistant["status"], "completed")
            self.assertEqual(assistant["artifacts"][0]["artifact_id"], artifact["artifact_id"])
        finally:
            conn.close()

    def test_requested_pdf_failure_produces_partial_artifact(self) -> None:
        self.create_job(("png", "pdf"))
        ChartRenderWorker(
            self.config,
            worker_id="worker-a",
            storage=resolve_artifact_storage(self.config),
        ).process_one()
        conn = connect_db(self.config)
        try:
            artifact = conn.execute("SELECT status, metadata_json FROM artifacts").fetchone()
            self.assertEqual(artifact["status"], "partial")
            self.assertIn('"missing_formats":["pdf"]', artifact["metadata_json"])
        finally:
            conn.close()

    def test_preview_download_and_device_isolation(self) -> None:
        self.create_job()
        ChartRenderWorker(
            self.config,
            worker_id="worker-a",
            storage=resolve_artifact_storage(self.config),
        ).process_one()
        conn = connect_db(self.config)
        try:
            artifact_id = str(conn.execute("SELECT artifact_id FROM artifacts").fetchone()[0])
            file_id = str(conn.execute("SELECT file_id FROM artifact_files").fetchone()[0])
        finally:
            conn.close()

        app = FastAPI()
        app.state.config = self.config
        register_exception_handlers(app)
        app.include_router(artifacts_router)
        with TestClient(app) as client:
            owner = {"Authorization": "Bearer token-a", "X-Device-Id": "device-a"}
            other = {"Authorization": "Bearer token-b", "X-Device-Id": "device-b"}
            preview = client.get(f"/api/artifacts/{artifact_id}/preview", headers=owner)
            self.assertEqual(preview.status_code, 200)
            self.assertTrue(preview.content.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(preview.headers["content-disposition"], "inline")
            self.assertEqual(preview.headers["content-type"], "image/png")
            self.assertEqual(preview.headers["cache-control"], "private, no-store")
            self.assertEqual(preview.headers["x-content-type-options"], "nosniff")
            download = client.get(
                f"/api/artifacts/{artifact_id}/files/{file_id}", headers=owner
            )
            self.assertEqual(download.status_code, 200)
            self.assertIn("attachment", download.headers["content-disposition"])
            self.assertEqual(download.headers["cache-control"], "private, no-store")
            self.assertEqual(download.headers["x-content-type-options"], "nosniff")
            self.assertEqual(
                client.get(f"/api/artifacts/{artifact_id}/preview", headers=other).status_code,
                404,
            )
            self.assertEqual(client.get("/api/artifacts/unknown/preview", headers=owner).status_code, 404)
            self.assertEqual(
                client.get(
                    f"/api/artifacts/{artifact_id}/files/unknown", headers=owner
                ).status_code,
                404,
            )
            self.assertEqual(
                client.get(
                    f"/api/artifacts/{artifact_id}/preview",
                    headers={"Authorization": "Bearer token-a", "X-Device-Id": "device-b"},
                ).status_code,
                401,
            )

    def test_fencing_token_rejects_zombie_worker(self) -> None:
        self.create_job()
        conn = connect_db(self.config)
        try:
            first = claim_render_job(conn, worker_id="worker-a", lease_seconds=30)
            self.assertIsNotNone(first)
            conn.execute(
                "UPDATE render_jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?",
                (first.job_id,),
            )
            conn.commit()
            second = claim_render_job(conn, worker_id="worker-b", lease_seconds=30)
            self.assertIsNotNone(second)
            self.assertNotEqual(first.lease_token, second.lease_token)
            self.assertFalse(
                owns_lease(
                    conn,
                    job_id=first.job_id,
                    worker_id="worker-a",
                    lease_token=first.lease_token,
                )
            )
            self.assertTrue(
                owns_lease(
                    conn,
                    job_id=second.job_id,
                    worker_id="worker-b",
                    lease_token=second.lease_token,
                )
            )

            storage = resolve_artifact_storage(self.config)
            stale_staging = storage.staging_dir(first.generation_id, first.lease_token)
            stale_output = stale_staging / "chart.png"
            render_chart_png(load_render_input(first.render_input_json), stale_output)
            stale_file = storage.publish(
                stale_output,
                storage_key=f"{first.generation_id}/{first.lease_token}/chart.png",
            )
            with self.assertRaisesRegex(ValueError, "render_lease_lost"):
                finalize_render(
                    conn,
                    job=first,
                    worker_id="worker-a",
                    title="Stale",
                    summary="Must not attach",
                    metadata={},
                    png_file={
                        "filename": "stale.png",
                        "content_type": "image/png",
                        "size_bytes": stale_file.size_bytes,
                        "sha256": stale_file.sha256,
                        "storage_key": stale_file.storage_key,
                    },
                )
            valid_staging = storage.staging_dir(second.generation_id, second.lease_token)
            valid_output = valid_staging / "chart.png"
            render_chart_png(load_render_input(second.render_input_json), valid_output)
            valid_file = storage.publish(
                valid_output,
                storage_key=f"{second.generation_id}/{second.lease_token}/chart.png",
            )
            self.assertNotEqual(stale_file.storage_key, valid_file.storage_key)
            artifact_id, status = finalize_render(
                conn,
                job=second,
                worker_id="worker-b",
                title="Valid",
                summary="Valid fenced result",
                metadata={},
                png_file={
                    "filename": "valid.png",
                    "content_type": "image/png",
                    "size_bytes": valid_file.size_bytes,
                    "sha256": valid_file.sha256,
                    "storage_key": valid_file.storage_key,
                },
            )
            self.assertEqual(status, "ready")
            self.assertEqual(conn.execute("SELECT artifact_id FROM artifacts").fetchone()[0], artifact_id)
            self.assertTrue(storage.remove_if_unreferenced(conn, storage_key=stale_file.storage_key))
            self.assertFalse(stale_file.path.exists())
            self.assertTrue(valid_file.path.exists())
        finally:
            conn.close()

    def test_worker_retry_stops_at_configured_maximum(self) -> None:
        ids = self.create_job()
        conn = connect_db(self.config)
        try:
            for attempt in range(1, 4):
                job = claim_render_job(conn, worker_id=f"worker-{attempt}", lease_seconds=30)
                self.assertIsNotNone(job)
                self.assertEqual(job.attempt_count, attempt)
                self.assertTrue(
                    mark_render_failure(
                        conn,
                        job_id=job.job_id,
                        worker_id=f"worker-{attempt}",
                        lease_token=job.lease_token,
                        code="test_failure",
                        message="Expected retry test failure.",
                    )
                )
            self.assertIsNone(claim_render_job(conn, worker_id="worker-4", lease_seconds=30))
            row = conn.execute(
                "SELECT status, attempt_count, max_attempts FROM render_jobs WHERE job_id = ?",
                (ids["job_id"],),
            ).fetchone()
            self.assertEqual((row["status"], row["attempt_count"], row["max_attempts"]), ("failed", 3, 3))
        finally:
            conn.close()

    def test_session_delete_cancels_queued_job(self) -> None:
        ids = self.create_job()
        conn = connect_db(self.config)
        try:
            result = soft_delete_session(
                conn,
                session_id="session-a",
                user_id="user_admin",
                owner_device_id="device-a",
            )
            self.assertTrue(result.deleted)
            self.assertEqual(
                conn.execute("SELECT status FROM render_jobs WHERE job_id = ?", (ids["job_id"],)).fetchone()[0],
                "cancelled",
            )
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM artifact_generations WHERE generation_id = ?",
                    (ids["generation_id"],),
                ).fetchone()[0],
                "deleted",
            )
        finally:
            conn.close()

    def test_session_deleted_during_render_never_publishes_artifact(self) -> None:
        ids = self.create_job()
        storage = resolve_artifact_storage(self.config)
        conn = connect_db(self.config)
        try:
            claimed = claim_render_job(conn, worker_id="worker-a", lease_seconds=30)
            self.assertIsNotNone(claimed)
            staging = storage.staging_dir(claimed.generation_id, claimed.lease_token)
            output = staging / "chart.png"
            render_chart_png(load_render_input(claimed.render_input_json), output)
            published = storage.publish(
                output,
                storage_key=f"{claimed.generation_id}/{claimed.lease_token}/chart.png",
            )
            soft_delete_session(
                conn,
                session_id="session-a",
                user_id="user_admin",
                owner_device_id="device-a",
            )
            with self.assertRaisesRegex(ValueError, "session_deleted"):
                finalize_render(
                    conn,
                    job=claimed,
                    worker_id="worker-a",
                    title="Race",
                    summary="Must not publish",
                    metadata={},
                    png_file={
                        "filename": "race.png",
                        "content_type": "image/png",
                        "size_bytes": published.size_bytes,
                        "sha256": published.sha256,
                        "storage_key": published.storage_key,
                    },
                )
            self.assertTrue(storage.remove_if_unreferenced(conn, storage_key=published.storage_key))
            self.assertFalse(published.path.exists())
        finally:
            conn.close()
        conn = connect_db(self.config)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0], 0)
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM artifact_generations WHERE generation_id = ?",
                    (ids["generation_id"],),
                ).fetchone()[0],
                "deleted",
            )
        finally:
            conn.close()

    def test_mock_is_hard_blocked_in_production(self) -> None:
        object.__setattr__(self.config.chart_artifacts, "environment", "production")
        conn = connect_db(self.config)
        try:
            with self.assertRaisesRegex(ValueError, "foundation_test_harness_disabled"):
                create_foundation_mock_job(
                    conn,
                    self.config,
                    request_id="blocked",
                    session_id="session-a",
                    owner_user_id="user_admin",
                    owner_device_id="device-a",
                    render_input=self.render_input(),
                )
        finally:
            conn.close()

    def test_persistence_layer_rejects_production_mock(self) -> None:
        conn = connect_db(self.config)
        try:
            from macsoft.sessions.message_store import create_pending_assistant_message

            create_pending_assistant_message(
                conn,
                session_id="session-a",
                user_id="user_admin",
                owner_device_id="device-a",
                message_id="msg-production-block",
            )
            with self.assertRaisesRegex(ValueError, "mock_artifact_forbidden"):
                create_generation(
                    conn,
                    request_id="request-production-block",
                    session_id="session-a",
                    assistant_message_id="msg-production-block",
                    owner_user_id="user_admin",
                    owner_device_id="device-a",
                    source_type="mock",
                    render_input=self.render_input(),
                    environment="production",
                    render_input_ttl_minutes=60,
                )
        finally:
            conn.close()

    def test_no_internal_mock_route_is_registered(self) -> None:
        paths = {getattr(route, "path", "") for route in artifacts_router.routes}
        self.assertFalse(any("mock" in path.lower() for path in paths))

    def test_unknown_environment_fails_closed(self) -> None:
        config_path = Path(self.temp.name) / "invalid-environment.yaml"
        original = Path(self.config.config_path).read_text(encoding="utf-8")
        config_path.write_text(original.replace('environment: "test"', 'environment: "staging-ish"'), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "chart_artifacts.environment"):
            load_config(str(config_path))

    def test_shared_storage_key_is_not_deleted_while_referenced(self) -> None:
        storage = ArtifactStorage(Path(self.temp.name) / "shared-storage")
        target = storage.final_path("same/chart.png")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"png")
        conn = connect_db(self.config)
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                """
                INSERT INTO artifact_files (
                    file_id, artifact_id, revision, format, role, filename,
                    content_type, size_bytes, sha256, storage_key, status, created_at
                ) VALUES ('file-ref', 'artifact-ref', 1, 'png', 'preview', 'x.png',
                          'image/png', 3, 'hash', 'same/chart.png', 'available', ?)
                """,
                ("2026-07-29T00:00:00+00:00",),
            )
            conn.commit()
            self.assertFalse(storage.remove_if_unreferenced(conn, storage_key="same/chart.png"))
            self.assertTrue(target.exists())
            conn.execute("UPDATE artifact_files SET status = 'deleted' WHERE file_id = 'file-ref'")
            conn.commit()
            self.assertTrue(storage.remove_if_unreferenced(conn, storage_key="same/chart.png"))
            self.assertFalse(target.exists())
        finally:
            conn.close()

    def test_old_revision_cleanup_preserves_latest_shared_file_and_preview(self) -> None:
        self.create_job()
        ChartRenderWorker(
            self.config,
            worker_id="worker-a",
            storage=resolve_artifact_storage(self.config),
        ).process_one()
        conn = connect_db(self.config)
        try:
            artifact_id = str(conn.execute("SELECT artifact_id FROM artifacts").fetchone()[0])
            first = conn.execute("SELECT * FROM artifact_files").fetchone()
            conn.execute("UPDATE artifacts SET revision = 2 WHERE artifact_id = ?", (artifact_id,))
            conn.execute(
                """
                INSERT INTO artifact_files (
                    file_id, artifact_id, revision, format, role, filename,
                    content_type, size_bytes, sha256, storage_key, status, created_at
                ) VALUES ('latest-shared', ?, 2, 'png', 'preview', 'latest.png',
                          'image/png', ?, ?, ?, 'available', ?)
                """,
                (artifact_id, first["size_bytes"], first["sha256"], first["storage_key"], first["created_at"]),
            )
            conn.execute("UPDATE artifact_files SET status = 'deleted' WHERE file_id = ?", (first["file_id"],))
            conn.commit()
            storage = resolve_artifact_storage(self.config)
            self.assertFalse(storage.remove_if_unreferenced(conn, storage_key=first["storage_key"]))
        finally:
            conn.close()

        app = FastAPI()
        app.state.config = self.config
        register_exception_handlers(app)
        app.include_router(artifacts_router)
        with TestClient(app) as client:
            response = client.get(
                f"/api/artifacts/{artifact_id}/preview",
                headers={"Authorization": "Bearer token-a", "X-Device-Id": "device-a"},
            )
            self.assertEqual(response.status_code, 200)

    def test_generating_and_failed_messages_are_excluded_from_context_and_legacy_history(self) -> None:
        conn = connect_db(self.config)
        try:
            save_message(conn, session_id="session-a", user_id="user_admin", owner_device_id="device-a", role="assistant", content="pending", status="generating", message_id="pending")
            save_message(conn, session_id="session-a", user_id="user_admin", owner_device_id="device-a", role="assistant", content="failed", status="failed", message_id="failed")
            save_message(conn, session_id="session-a", user_id="user_admin", owner_device_id="device-a", role="user", content="current", message_id="current")
            history = list_messages_for_session(conn, session_id="session-a", user_id="user_admin", owner_device_id="device-a")
            self.assertNotIn("pending", {item["message_id"] for item in history})
            self.assertIn("failed", {item["message_id"] for item in history})
            context = list_ai_context_messages_for_session(conn, session_id="session-a", user_id="user_admin", owner_device_id="device-a", current_message_id="current")
            self.assertEqual([item["message_id"] for item in context.messages], ["current"])
        finally:
            conn.close()

    def test_expired_and_deleted_session_delivery_semantics(self) -> None:
        self.create_job()
        ChartRenderWorker(self.config, worker_id="worker-a", storage=resolve_artifact_storage(self.config)).process_one()
        conn = connect_db(self.config)
        try:
            artifact_id = str(conn.execute("SELECT artifact_id FROM artifacts").fetchone()[0])
            file_id = str(conn.execute("SELECT file_id FROM artifact_files").fetchone()[0])
            conn.execute("UPDATE artifacts SET status = 'expired' WHERE artifact_id = ?", (artifact_id,))
            conn.commit()
        finally:
            conn.close()
        app = FastAPI()
        app.state.config = self.config
        register_exception_handlers(app)
        app.include_router(artifacts_router)
        headers = {"Authorization": "Bearer token-a", "X-Device-Id": "device-a"}
        with TestClient(app) as client:
            self.assertEqual(client.get(f"/api/artifacts/{artifact_id}/preview", headers=headers).status_code, 410)
            self.assertEqual(client.get(f"/api/artifacts/{artifact_id}/files/{file_id}", headers=headers).status_code, 410)
            conn = connect_db(self.config)
            try:
                soft_delete_session(conn, session_id="session-a", user_id="user_admin", owner_device_id="device-a")
            finally:
                conn.close()
            self.assertEqual(client.get(f"/api/artifacts/{artifact_id}/preview", headers=headers).status_code, 404)
            self.assertEqual(client.get(f"/api/artifacts/{artifact_id}/files/{file_id}", headers=headers).status_code, 404)

    def test_storage_rejects_path_traversal_and_invalid_staging_source(self) -> None:
        storage = ArtifactStorage(Path(self.temp.name) / "path-storage")
        with self.assertRaisesRegex(Exception, "invalid_storage_key"):
            storage.final_path("../escape.png")
        outside = Path(self.temp.name) / "outside.png"
        outside.write_bytes(b"png")
        with self.assertRaisesRegex(Exception, "invalid_staging_file"):
            storage.publish(outside, storage_key="safe/chart.png")

    def test_reconciliation_requeues_expired_lease_without_new_generation(self) -> None:
        ids = self.create_job()
        conn = connect_db(self.config)
        try:
            claimed = claim_render_job(conn, worker_id="worker-a", lease_seconds=30)
            self.assertIsNotNone(claimed)
            conn.execute(
                "UPDATE render_jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?",
                (ids["job_id"],),
            )
            conn.commit()
        finally:
            conn.close()

        counts = reconcile_artifacts(self.config, stale_minutes=10_000_000)
        self.assertEqual(counts["leases_requeued"], 1)

        conn = connect_db(self.config)
        try:
            job = conn.execute(
                "SELECT status, attempt_count FROM render_jobs WHERE job_id = ?",
                (ids["job_id"],),
            ).fetchone()
            self.assertEqual(job["status"], "queued")
            self.assertEqual(job["attempt_count"], 1)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM render_jobs").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM artifact_generations").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM artifact_generations WHERE generation_id = ?",
                    (ids["generation_id"],),
                ).fetchone()[0],
                "queued",
            )
        finally:
            conn.close()

    def test_reconciliation_marks_missing_preview_unavailable(self) -> None:
        self.create_job()
        ChartRenderWorker(
            self.config,
            worker_id="worker-a",
            storage=resolve_artifact_storage(self.config),
        ).process_one()
        conn = connect_db(self.config)
        try:
            artifact_id = str(conn.execute("SELECT artifact_id FROM artifacts").fetchone()[0])
            conn.execute(
                "UPDATE artifact_files SET status = 'missing' WHERE artifact_id = ?",
                (artifact_id,),
            )
            conn.commit()
        finally:
            conn.close()

        counts = reconcile_artifacts(self.config, orphan_grace_seconds=10_000_000)
        self.assertEqual(counts["artifacts_unavailable"], 1)
        second_counts = reconcile_artifacts(self.config, orphan_grace_seconds=10_000_000)
        self.assertEqual(sum(second_counts.values()), 0)

        conn = connect_db(self.config)
        try:
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM artifacts WHERE artifact_id = ?", (artifact_id,)
                ).fetchone()[0],
                "unavailable",
            )
        finally:
            conn.close()

    def test_reconciliation_removes_old_orphan_and_staging_data_idempotently(self) -> None:
        storage = resolve_artifact_storage(self.config)
        orphan = storage.final_path("orphan/chart.png")
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_bytes(b"orphan")
        staging = storage.staging_dir("stale-generation", "stale-lease")
        (staging / "chart.png").write_bytes(b"stale")
        counts = reconcile_artifacts(self.config, orphan_grace_seconds=0)
        self.assertEqual(counts["orphan_files_deleted"], 1)
        self.assertEqual(counts["stale_staging_dirs_deleted"], 1)
        self.assertFalse(orphan.exists())
        self.assertFalse(staging.exists())
        second = reconcile_artifacts(self.config, orphan_grace_seconds=0)
        self.assertEqual(sum(second.values()), 0)


if __name__ == "__main__":
    unittest.main()
