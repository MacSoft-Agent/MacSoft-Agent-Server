from __future__ import annotations

import sqlite3
import tempfile
import unittest
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from macsoft.db import connect_db, init_db
from macsoft.chat.hermes_client import HermesApiError
from macsoft.gateway.errors import register_exception_handlers
from macsoft.gateway.routes_client import router as client_router
from macsoft.gateway.routes_profile_learning import router as learning_router
from macsoft.server import create_app
from macsoft.profiles.registry import ensure_device_profile, resolve_profile_home


class ProfileLearningApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.config = SimpleNamespace(
            config_path=str(root / "server.yaml"),
            database=SimpleNamespace(path=str(root / "server.db")),
            hermes=SimpleNamespace(
                home=str(root / "runtime"),
                profile_root=str(root / "profiles"),
                api_base_url="http://127.0.0.1:1",
                api_key="test-key",
                request_timeout_seconds=1,
            ),
        )
        (root / "runtime").mkdir()
        init_db(self.config)
        conn = connect_db(self.config)
        now = "2026-08-05T00:00:00+00:00"
        for device_id, token in (("device-a", "token-a"), ("device-b", "token-b")):
            conn.execute("INSERT INTO devices VALUES (?, 'user_admin', ?, 'Client', '1', ?, 'Admin', 'active', ?, ?, NULL)", (device_id, token, device_id, now, now))
            conn.commit()
            profile = ensure_device_profile(conn, config=self.config, device_id=device_id)
            home = resolve_profile_home(self.config, profile_id=str(profile["profile_id"]))
            (home / "memories" / "MEMORY.md").write_text(f"memory-{device_id}", encoding="utf-8")
        conn.commit()
        conn.close()

        app = FastAPI()
        app.state.config = self.config
        register_exception_handlers(app)
        app.include_router(client_router)
        app.include_router(learning_router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_each_device_reads_only_its_own_memory(self) -> None:
        conn = connect_db(self.config)
        ids = {
            row["profile_id"]: row["device_id"]
            for row in conn.execute("SELECT profile_id, device_id FROM device_profiles")
        }
        conn.close()

        def graph_for_profile(*_args, **kwargs):
            device_id = ids[kwargs["profile_id"]]
            return {"memory": [{"title": f"memory-{device_id}", "source": "memory"}]}

        with patch(
            "macsoft.gateway.routes_profile_learning.call_profile_operation",
            side_effect=graph_for_profile,
        ):
            a = self.client.get("/api/profile/memory", headers={"Authorization": "Bearer token-a", "X-Device-Id": "device-a"})
            b = self.client.get("/api/profile/memory", headers={"Authorization": "Bearer token-b", "X-Device-Id": "device-b"})
        self.assertEqual(a.status_code, 200)
        self.assertEqual(b.status_code, 200)
        self.assertIn("memory-device-a", a.json()["summary"])
        self.assertNotIn("memory-device-b", a.json()["summary"])
        self.assertIn("memory-device-b", b.json()["summary"])

    def test_profile_summary_and_private_skill_contract_expose_no_authority(self) -> None:
        conn = connect_db(self.config)
        now = "2026-08-05T00:00:00+00:00"
        conn.execute(
            """
            INSERT INTO client_skills (
                skill_id, owner_user_id, owner_device_id, slug, name,
                description, content, enabled, created_at, updated_at
            ) VALUES ('private-a', 'user_admin', 'device-a', 'private-a',
                      'Private A', 'Read only', 'secret instruction', 1, ?, ?)
            """,
            (now, now),
        )
        conn.commit()
        conn.close()

        headers = {"Authorization": "Bearer token-a", "X-Device-Id": "device-a"}
        summary = self.client.get("/api/profile", headers=headers)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(set(summary.json()), {"display_name", "memory_updated_at"})

        skills = self.client.get("/api/profile/skills", headers=headers)
        self.assertEqual(skills.status_code, 200)
        private = skills.json()["private_skills"][0]
        self.assertEqual(private["id"], "private-a")
        self.assertEqual(private["origin"], "private")
        self.assertNotIn("content", private)
        self.assertNotIn("profile_id", skills.json())

    def test_profile_summary_route_is_registered_once(self) -> None:
        with patch("macsoft.server.load_config", return_value=self.config):
            app = create_app()
        matches = [
            route
            for route in app.routes
            if getattr(route, "path", None) == "/api/profile"
            and "GET" in getattr(route, "methods", set())
        ]
        self.assertEqual(len(matches), 1)

    def test_token_cannot_select_another_device(self) -> None:
        response = self.client.get("/api/profile/memory", headers={"Authorization": "Bearer token-a", "X-Device-Id": "device-b"})
        self.assertEqual(response.status_code, 401)

    def test_curator_preview_proposal_is_device_scoped_and_rejectable(self) -> None:
        preview = {
            "result": {
                "started_at": "2026-08-05T00:00:00+00:00",
                "auto_transitions": {"checked": 1},
            }
        }
        with patch(
            "macsoft.gateway.routes_profile_learning.call_profile_operation",
            return_value=preview,
        ):
            response = self.client.post(
                "/api/profile/curator/dry-run",
                headers={"Authorization": "Bearer token-a", "X-Device-Id": "device-a"},
            )
        self.assertEqual(response.status_code, 200)
        proposals = response.json()["proposals"]
        self.assertEqual(len(proposals), 1)
        proposal_id = proposals[0]["id"]

        cross_device = self.client.post(
            f"/api/profile/curator/proposals/{proposal_id}/reject",
            headers={"Authorization": "Bearer token-b", "X-Device-Id": "device-b"},
        )
        self.assertEqual(cross_device.status_code, 404)

        rejected = self.client.post(
            f"/api/profile/curator/proposals/{proposal_id}/reject",
            headers={"Authorization": "Bearer token-a", "X-Device-Id": "device-a"},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["status"], "rejected")

    def test_curator_proposal_can_be_applied_only_once_under_concurrency(self) -> None:
        conn = connect_db(self.config)
        profile_id = conn.execute(
            "SELECT profile_id FROM device_profiles WHERE device_id='device-a'"
        ).fetchone()["profile_id"]
        now = "2026-08-05T00:00:00+00:00"
        conn.execute(
            """
            INSERT INTO curator_proposals (
                proposal_id, profile_id, device_id, kind, target_id,
                payload_json, status, created_at, decided_at
            ) VALUES ('proposal_once', ?, 'device-a', 'curator_run', NULL,
                      '{}', 'pending', ?, NULL)
            """,
            (profile_id, now),
        )
        conn.commit()
        conn.close()
        entered = threading.Event()
        release = threading.Event()

        def mutation(*_args, **_kwargs):
            entered.set()
            release.wait(timeout=5)
            return ({"result": {}}, {"id": "audit_once"})

        headers = {"Authorization": "Bearer token-a", "X-Device-Id": "device-a"}
        with patch(
            "macsoft.gateway.routes_profile_learning.audited_profile_mutation",
            side_effect=mutation,
        ) as mocked:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(
                    self.client.post,
                    "/api/profile/curator/proposals/proposal_once/approve",
                    headers=headers,
                )
                self.assertTrue(entered.wait(timeout=5))
                second = pool.submit(
                    self.client.post,
                    "/api/profile/curator/proposals/proposal_once/approve",
                    headers=headers,
                )
                second_response = second.result(timeout=5)
                release.set()
                first_response = first.result(timeout=5)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 409)
        self.assertEqual(mocked.call_count, 1)

    def test_pin_uses_audited_native_operation_for_learned_skill(self) -> None:
        conn = connect_db(self.config)
        profile = conn.execute(
            "SELECT profile_id FROM device_profiles WHERE device_id='device-a'"
        ).fetchone()
        home = resolve_profile_home(self.config, profile_id=str(profile["profile_id"]))
        learned = home / "skills" / "learned"
        skill = learned / "reconcile" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\nname: reconcile\ndescription: Learned reconciliation\n---\n",
            encoding="utf-8",
        )
        usage_path = learned / ".usage.json"
        usage_path.write_text(
            json.dumps({"reconcile": {"created_by": "agent", "state": "active"}}),
            encoding="utf-8",
        )
        conn.close()

        def native_call(*_args, **kwargs):
            if kwargs["operation_path"].endswith("/pin"):
                usage_path.write_text(
                    json.dumps(
                        {"reconcile": {"created_by": "agent", "state": "active", "pinned": True}}
                    ),
                    encoding="utf-8",
                )
            return ({"ok": True}, {"id": "audit_test"})

        with patch(
            "macsoft.gateway.routes_profile_learning.audited_profile_mutation",
            side_effect=native_call,
        ):
            response = self.client.post(
                "/api/profile/skills/reconcile/pin",
                json={"pinned": True},
                headers={"Authorization": "Bearer token-a", "X-Device-Id": "device-a"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["pinned"])

    def test_manual_learned_skill_is_read_only_to_profile_actions(self) -> None:
        conn = connect_db(self.config)
        profile = conn.execute(
            "SELECT profile_id FROM device_profiles WHERE device_id='device-a'"
        ).fetchone()
        home = resolve_profile_home(self.config, profile_id=str(profile["profile_id"]))
        skill = home / "skills" / "learned" / "manual" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: manual\n---\nmanual", encoding="utf-8")
        conn.close()
        headers = {"Authorization": "Bearer token-a", "X-Device-Id": "device-a"}
        with patch(
            "macsoft.gateway.routes_profile_learning.audited_profile_mutation",
            side_effect=HermesApiError("forbidden", status_code=403, kind="http_error"),
        ):
            response = self.client.post(
                "/api/profile/skills/manual/pin", json={"pinned": True}, headers=headers
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "skill_not_agent_created")

        skills = self.client.get("/api/profile/skills", headers=headers)
        manual = next(item for item in skills.json()["skills"] if item["id"] == "manual")
        self.assertEqual(manual["origin"], "manual")

    def test_rollback_requires_explicit_confirmation(self) -> None:
        response = self.client.post(
            "/api/profile/curator/backups/backup_1/rollback",
            headers={"Authorization": "Bearer token-a", "X-Device-Id": "device-a"},
        )
        self.assertEqual(response.status_code, 422)

    def test_background_review_event_reconciles_run_without_crossing_profile(self) -> None:
        conn = connect_db(self.config)
        profile = conn.execute(
            "SELECT profile_id FROM device_profiles WHERE device_id='device-a'"
        ).fetchone()
        profile_id = str(profile["profile_id"])
        now = "2026-08-05T00:00:00+00:00"
        conn.execute(
            "INSERT INTO sessions (session_id,user_id,owner_device_id,title,source,status,created_at,updated_at) VALUES ('session-a','user_admin','device-a','A','client','active',?,?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO agent_runs VALUES ('run_0123456789abcdef','device-a',?,'session-a','completed','eligible',?,?)",
            (profile_id, now, now),
        )
        conn.commit()
        home = resolve_profile_home(self.config, profile_id=profile_id)
        event_dir = home / "logs" / "learning-events"
        event_dir.mkdir(parents=True)
        (event_dir / "run_0123456789abcdef.json").write_text(
            json.dumps(
                {
                    "run_id": "run_0123456789abcdef",
                    "session_id": "session-a",
                    "status": "completed",
                    "detail": "review complete",
                    "created_at": 1785888000,
                }
            ),
            encoding="utf-8",
        )
        audit_dir = home / "logs" / "skill-change-audit"
        audit_dir.mkdir(parents=True)
        (audit_dir / "audit_native.json").write_text(
            json.dumps(
                {
                    "audit_id": "audit_native",
                    "profile_id": profile_id,
                    "skill_id": "reconcile",
                    "run_id": "run_0123456789abcdef",
                    "change_source": "skill_manage_patch",
                    "previous_hash": "old",
                    "new_hash": "new",
                    "timestamp": now,
                    "result": "succeeded",
                    "detail": "patched learned skill",
                }
            ),
            encoding="utf-8",
        )
        conn.close()

        response = self.client.get(
            "/api/profile/learning",
            headers={"Authorization": "Bearer token-a", "X-Device-Id": "device-a"},
        )
        self.assertEqual(response.status_code, 200)
        events = response.json()["events"]
        self.assertEqual({event["kind"] for event in events}, {"background_review", "skill_updated"})
        self.assertTrue(all(event["session_id"] == "session-a" for event in events))
        skill_event = next(event for event in events if event["kind"] == "skill_updated")
        self.assertEqual(skill_event["skill_id"], "reconcile")
        background_event = next(event for event in events if event["kind"] == "background_review")
        self.assertIsNone(background_event["skill_id"])
        conn = connect_db(self.config)
        audit = conn.execute(
            "SELECT * FROM skill_change_audit WHERE audit_id='audit_native'"
        ).fetchone()
        conn.close()
        self.assertEqual(audit["device_id"], "device-a")
        self.assertEqual(audit["previous_hash"], "old")
        self.assertEqual(audit["new_hash"], "new")

        other = self.client.get(
            "/api/profile/learning",
            headers={"Authorization": "Bearer token-b", "X-Device-Id": "device-b"},
        )
        self.assertEqual(other.status_code, 200)
        self.assertEqual(other.json()["events"], [])


if __name__ == "__main__":
    unittest.main()
