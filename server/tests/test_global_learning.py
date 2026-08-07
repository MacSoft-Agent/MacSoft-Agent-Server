from __future__ import annotations

import os
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from macsoft.admin.auth import AdminAccessRegistry
from macsoft.chat.active_runs import ActiveChatRunRegistry
from macsoft.config import load_config
from macsoft.db import connect_db, init_db
from macsoft.gateway.errors import register_exception_handlers
from macsoft.gateway.routes_admin import (
    GLOBAL_LEARNING_SYSTEM_INSTRUCTION,
    _schedule_global_proposal_refresh,
    router,
)
from macsoft.global_learning.gate import GlobalLearningGate
from macsoft.global_learning.homes import (
    ensure_global_training_home,
    ensure_server_hermes_homes,
    global_home,
    read_approved_global_memory,
)


class GlobalLearningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        (self.runtime / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "model": {
                        "provider": "nous",
                        "default": "server-model",
                        "api_key": "must-not-copy",
                    }
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        config_path = self.root / "macsoft-server.yaml"
        config_path.write_text(
            "\n".join(
                (
                    "database:",
                    '  path: "./data/server.db"',
                    "hermes:",
                    f'  home: "{self.runtime.as_posix()}"',
                    f'  profile_root: "{(self.runtime / "profiles").as_posix()}"',
                    '  api_base_url: "http://127.0.0.1:8642"',
                    '  api_key: "internal-test-key"',
                    "  request_timeout_seconds: 5",
                )
            ),
            encoding="utf-8",
        )
        self.config = load_config(str(config_path))
        init_db(self.config)
        self.old_host_token = os.environ.get("MACSOFT_HOST_CONTROL_TOKEN")
        self.old_hermes_home = os.environ.get("HERMES_HOME")
        self.old_profile_root = os.environ.get("MACSOFT_PROFILE_ROOT")
        os.environ["MACSOFT_HOST_CONTROL_TOKEN"] = "host-token-" + "x" * 32
        os.environ["HERMES_HOME"] = str(self.runtime)
        os.environ["MACSOFT_PROFILE_ROOT"] = str(self.runtime / "profiles")

        app = FastAPI()
        app.state.config = self.config
        app.state.admin_access_registry = AdminAccessRegistry()
        app.state.active_chat_runs = ActiveChatRunRegistry()
        app.state.global_learning_gate = GlobalLearningGate()
        register_exception_handlers(app)
        app.include_router(router)
        self.app = app
        self.client = TestClient(app, client=("127.0.0.1", 50000))
        bootstrap = self.client.post(
            "/api/internal/desktop-admin/auth/session",
            headers={"Authorization": f"Bearer {os.environ['MACSOFT_HOST_CONTROL_TOKEN']}"},
        )
        self.assertEqual(bootstrap.status_code, 200, bootstrap.text)
        self.headers = {"Authorization": f"Bearer {bootstrap.json()['access_token']}"}

    def tearDown(self) -> None:
        self.client.close()
        for name, value in (
            ("MACSOFT_HOST_CONTROL_TOKEN", self.old_host_token),
            ("HERMES_HOME", self.old_hermes_home),
            ("MACSOFT_PROFILE_ROOT", self.old_profile_root),
        ):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.temp.cleanup()

    def _create_training_session(self) -> dict:
        response = self.client.post(
            "/api/admin/global-learning/sessions",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["session"]

    def test_native_admin_global_and_staging_homes_are_isolated_without_secrets(self) -> None:
        homes = ensure_server_hermes_homes(self.config)
        self.assertEqual(homes["global"], (self.runtime / "global").resolve())
        self.assertEqual(homes["admin"], (self.runtime / "admin").resolve())
        canonical_memory = homes["global"] / "memories" / "MEMORY.md"
        global_user = homes["global"] / "memories" / "USER.md"
        self.assertIn("not to an individual user", global_user.read_text(encoding="utf-8"))
        canonical_memory.write_text("approved global knowledge", encoding="utf-8")

        session_id = "admin_sess_0123456789abcdef0123456789abcdef"
        staging = ensure_global_training_home(self.config, session_id)
        self.assertEqual(
            (staging / "memories" / "MEMORY.md").read_text(encoding="utf-8"),
            "approved global knowledge",
        )
        (staging / "memories" / "MEMORY.md").write_text("proposal", encoding="utf-8")
        self.assertEqual(canonical_memory.read_text(encoding="utf-8"), "approved global knowledge")

        scoped_config = yaml.safe_load((staging / "config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(scoped_config["model"]["default"], "server-model")
        self.assertNotIn("api_key", scoped_config["model"])
        self.assertTrue((staging / "skills" / "learned").is_dir())

    def test_approved_global_memory_is_optional_without_a_runtime_home(self) -> None:
        config = SimpleNamespace(
            database=SimpleNamespace(path=str(self.root / "legacy.db")),
            hermes=SimpleNamespace(home=""),
        )
        with patch.dict(os.environ, {"HERMES_HOME": "", "MACSOFT_PROFILE_ROOT": ""}):
            self.assertIsNone(read_approved_global_memory(config))

    def test_training_gate_is_restart_closed_and_restricted_to_training_sessions(self) -> None:
        normal = self.client.post(
            "/api/admin/sessions",
            headers=self.headers,
            json={"title": "Daily chat"},
        ).json()["session"]
        denied = self.client.post(
            "/api/admin/global-learning/toggle",
            headers=self.headers,
            json={
                "session_id": normal["session_id"],
                "enabled": True,
                "confirmation": "ENABLE GLOBAL LEARNING",
            },
        )
        self.assertEqual(denied.status_code, 409)

        training = self._create_training_session()
        self.assertEqual(training["session_type"], "global_training")
        disabled_chat = self.client.post(
            "/api/admin/chat/stream",
            headers=self.headers,
            json={"session_id": training["session_id"], "message": "Improve reconciliation."},
        )
        self.assertEqual(disabled_chat.status_code, 409)

        missing_confirmation = self.client.post(
            "/api/admin/global-learning/toggle",
            headers=self.headers,
            json={"session_id": training["session_id"], "enabled": True},
        )
        self.assertEqual(missing_confirmation.status_code, 422)

        enabled = self.client.post(
            "/api/admin/global-learning/toggle",
            headers=self.headers,
            json={
                "session_id": training["session_id"],
                "enabled": True,
                "confirmation": "ENABLE GLOBAL LEARNING",
            },
        )
        self.assertEqual(enabled.status_code, 200, enabled.text)
        self.assertTrue(enabled.json()["enabled"])

        replacement_process_gate = GlobalLearningGate()
        self.assertFalse(replacement_process_gate.is_enabled(training["session_id"]))

    def test_training_gate_fails_closed_after_its_desktop_lease_expires(self) -> None:
        gate = GlobalLearningGate(lease_seconds=0.01)
        gate.enable("admin_sess_0123456789abcdef0123456789abcdef")
        self.assertTrue(gate.is_enabled("admin_sess_0123456789abcdef0123456789abcdef"))
        time.sleep(0.02)
        self.assertFalse(gate.is_enabled("admin_sess_0123456789abcdef0123456789abcdef"))

    def test_enabled_training_run_uses_staging_scope_and_global_review_instruction(self) -> None:
        training = self._create_training_session()
        self.client.post(
            "/api/admin/global-learning/toggle",
            headers=self.headers,
            json={
                "session_id": training["session_id"],
                "enabled": True,
                "confirmation": "ENABLE GLOBAL LEARNING",
            },
        )
        captured: dict = {}

        def stream(**kwargs):
            captured.update(kwargs)
            return iter([{"type": "text_delta", "text": "Reviewed."}])

        with patch(
            "macsoft.gateway.routes_admin.stream_interruptible_hermes_reply_events",
            side_effect=stream,
        ):
            response = self.client.post(
                "/api/admin/chat/stream",
                headers=self.headers,
                json={"session_id": training["session_id"], "message": "Improve reconciliation."},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            captured["admin_scope"],
            f"global-training:{training['session_id']}",
        )
        self.assertIn(GLOBAL_LEARNING_SYSTEM_INSTRUCTION, captured["messages"][0]["content"])
        self.assertTrue(
            (self.runtime / "global-staging" / training["session_id"]).is_dir()
        )
        self.assertTrue(global_home(self.config).is_dir())

    def test_completed_native_review_is_automatically_snapshotted_as_pending_proposal(self) -> None:
        training = self._create_training_session()
        session_id = training["session_id"]
        run_id = "run_globalreview"
        staging = self.runtime / "global-staging" / session_id
        (staging / "memories" / "MEMORY.md").write_text("Reusable validation rule.", encoding="utf-8")
        event_dir = staging / "logs" / "learning-events"
        event_dir.mkdir(parents=True, exist_ok=True)
        (event_dir / f"{run_id}.json").write_text(
            json.dumps({"status": "completed", "run_id": run_id}), encoding="utf-8"
        )
        _schedule_global_proposal_refresh(self.config, session_id, run_id)
        deadline = time.monotonic() + 2
        proposals: list[dict] = []
        while time.monotonic() < deadline:
            proposals = self.client.get(
                "/api/admin/global-learning/proposals", headers=self.headers
            ).json()["proposals"]
            if proposals:
                break
            time.sleep(0.05)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["status"], "pending")
        self.assertEqual(proposals[0]["run_id"], run_id)

    def test_schema_contains_global_proposal_audit_and_version_tables(self) -> None:
        conn = connect_db(self.config)
        try:
            tables = {
                row["name"]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        finally:
            conn.close()
        self.assertTrue(
            {
                "global_learning_proposals",
                "global_learning_audit",
                "global_skill_versions",
            }.issubset(tables)
        )

    def test_native_staging_changes_require_approval_before_global_visibility(self) -> None:
        training = self._create_training_session()
        session_id = training["session_id"]
        staging = self.runtime / "global-staging" / session_id
        canonical = self.runtime / "global"
        learned = staging / "skills" / "learned" / "workflow-improvements" / "reconciliation" / "SKILL.md"
        learned.parent.mkdir(parents=True)
        learned.write_text(
            "---\nname: reconciliation\ndescription: Validate reconciliation.\n---\nCheck totals.",
            encoding="utf-8",
        )

        refreshed = self.client.post(
            "/api/admin/global-learning/proposals/refresh",
            headers=self.headers,
            json={"session_id": session_id, "run_id": "run_native"},
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        proposal = refreshed.json()["proposal"]
        self.assertEqual(proposal["kind"], "skill_create_proposal")
        self.assertFalse((canonical / "skills" / "learned" / "workflow-improvements" / "reconciliation").exists())
        self.assertNotIn("snapshot_path", json.dumps(proposal))

        approved = self.client.post(
            f"/api/admin/global-learning/proposals/{proposal['proposal_id']}/approve",
            headers=self.headers,
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["proposal"]["status"], "approved")
        self.assertTrue(
            (canonical / "skills" / "learned" / "workflow-improvements" / "reconciliation" / "SKILL.md").is_file()
        )
        conn = connect_db(self.config)
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS count FROM global_learning_audit").fetchone()["count"],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS count FROM global_skill_versions").fetchone()["count"],
                1,
            )
        finally:
            conn.close()

    def test_stale_or_rejected_proposal_cannot_change_canonical_global_home(self) -> None:
        training = self._create_training_session()
        session_id = training["session_id"]
        staging_memory = self.runtime / "global-staging" / session_id / "memories" / "MEMORY.md"
        staging_memory.write_text("candidate", encoding="utf-8")
        proposal = self.client.post(
            "/api/admin/global-learning/proposals/refresh",
            headers=self.headers,
            json={"session_id": session_id},
        ).json()["proposal"]
        canonical_memory = self.runtime / "global" / "memories" / "MEMORY.md"
        canonical_memory.write_text("independent approved update", encoding="utf-8")
        stale = self.client.post(
            f"/api/admin/global-learning/proposals/{proposal['proposal_id']}/approve",
            headers=self.headers,
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(
            canonical_memory.read_text(encoding="utf-8"),
            "independent approved update",
        )

        other = self._create_training_session()
        other_memory = self.runtime / "global-staging" / other["session_id"] / "memories" / "MEMORY.md"
        other_memory.write_text("reject me", encoding="utf-8")
        rejected_proposal = self.client.post(
            "/api/admin/global-learning/proposals/refresh",
            headers=self.headers,
            json={"session_id": other["session_id"]},
        ).json()["proposal"]
        rejected = self.client.post(
            f"/api/admin/global-learning/proposals/{rejected_proposal['proposal_id']}/reject",
            headers=self.headers,
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["proposal"]["status"], "rejected")
        self.assertEqual(
            canonical_memory.read_text(encoding="utf-8"),
            "independent approved update",
        )

    def test_approved_proposal_can_be_restored_once_without_overwriting_newer_state(self) -> None:
        training = self._create_training_session()
        session_id = training["session_id"]
        staging_memory = self.runtime / "global-staging" / session_id / "memories" / "MEMORY.md"
        staging_memory.write_text("approved reusable method", encoding="utf-8")
        proposal = self.client.post(
            "/api/admin/global-learning/proposals/refresh",
            headers=self.headers,
            json={"session_id": session_id},
        ).json()["proposal"]
        approved = self.client.post(
            f"/api/admin/global-learning/proposals/{proposal['proposal_id']}/approve",
            headers=self.headers,
        )
        self.assertEqual(approved.status_code, 200, approved.text)

        restored = self.client.post(
            f"/api/admin/global-learning/proposals/{proposal['proposal_id']}/restore",
            headers=self.headers,
        )
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertTrue(restored.json()["restored"])
        canonical_memory = self.runtime / "global" / "memories" / "MEMORY.md"
        self.assertEqual(canonical_memory.read_text(encoding="utf-8"), "")

        stale_restore = self.client.post(
            f"/api/admin/global-learning/proposals/{proposal['proposal_id']}/restore",
            headers=self.headers,
        )
        self.assertEqual(stale_restore.status_code, 409)
        conn = connect_db(self.config)
        try:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM global_learning_audit WHERE change_source='admin_restore'"
                ).fetchone()["count"],
                1,
            )
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()
