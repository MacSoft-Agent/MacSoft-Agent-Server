from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from gateway.config import PlatformConfig
from gateway.platforms.api_server import (
    APIServerAdapter,
    _resolve_macsoft_profile_home,
)
from hermes_constants import get_hermes_home


class _Request:
    def __init__(
        self,
        *,
        api_key: str,
        profile_id: str = "",
        admin_scope: str = "",
        match_info=None,
        body=None,
    ):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
        }
        if profile_id:
            self.headers["X-MacSoft-Profile-Id"] = profile_id
        if admin_scope:
            self.headers["X-MacSoft-Admin-Scope"] = admin_scope
        self.match_info = match_info or {}
        self._body = body or {}
        self.remote = "127.0.0.1"

    async def json(self):
        return self._body


class MacSoftProfileApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.shared_home = root / "shared"
        self.profile_root = self.shared_home / "profiles"
        self.shared_home.mkdir(parents=True)
        (self.shared_home / "config.yaml").write_text("{}\n", encoding="utf-8")
        self.profile_ids = [
            "prof_0123456789abcdef0123456789abcdef",
            "prof_fedcba9876543210fedcba9876543210",
        ]
        for profile_id in self.profile_ids:
            home = self.profile_root / profile_id
            (home / "memories").mkdir(parents=True)
            (home / "skills" / "learned").mkdir(parents=True)
            (home / "skills" / "private").mkdir(parents=True)
            (home / "config.yaml").write_text("{}\n", encoding="utf-8")
        self.old_profile_root = os.environ.get("MACSOFT_PROFILE_ROOT")
        self.old_hermes_home = os.environ.get("HERMES_HOME")
        os.environ["MACSOFT_PROFILE_ROOT"] = str(self.profile_root)
        os.environ["HERMES_HOME"] = str(self.shared_home)
        (self.shared_home / "admin").mkdir()
        self.adapter = APIServerAdapter(
            PlatformConfig(enabled=True, extra={"key": "internal-secret"})
        )

    async def asyncTearDown(self) -> None:
        await self.adapter.disconnect()
        if self.old_profile_root is None:
            os.environ.pop("MACSOFT_PROFILE_ROOT", None)
        else:
            os.environ["MACSOFT_PROFILE_ROOT"] = self.old_profile_root
        if self.old_hermes_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self.old_hermes_home
        self.temp.cleanup()

    async def test_executor_scopes_are_isolated_under_concurrency(self) -> None:
        barrier = threading.Barrier(2)

        def operation(expected: Path, marker: str):
            barrier.wait(timeout=5)
            actual = get_hermes_home()
            (actual / "memories" / "MEMORY.md").write_text(marker, encoding="utf-8")
            learned = actual / "skills" / "learned"
            (learned / f"skill-{marker}" / "SKILL.md").parent.mkdir(parents=True)
            (learned / f"skill-{marker}" / "SKILL.md").write_text(marker, encoding="utf-8")
            (learned / ".usage.json").write_text(
                json.dumps({f"skill-{marker}": {"created_by": "agent", "use_count": 1}}),
                encoding="utf-8",
            )
            (learned / ".curator_state").write_text(
                json.dumps({"profile_marker": marker}), encoding="utf-8"
            )
            barrier.wait(timeout=5)
            return (
                str(actual),
                (actual / "memories" / "MEMORY.md").read_text(encoding="utf-8"),
                json.loads((learned / ".usage.json").read_text(encoding="utf-8")),
                json.loads((learned / ".curator_state").read_text(encoding="utf-8")),
            )

        homes = [self.profile_root / profile_id for profile_id in self.profile_ids]
        results = await asyncio.gather(
            self.adapter._run_profile_operation(homes[0], lambda: operation(homes[0], "A")),
            self.adapter._run_profile_operation(homes[1], lambda: operation(homes[1], "B")),
        )
        self.assertEqual(results[0], (str(homes[0]), "A", {"skill-A": {"created_by": "agent", "use_count": 1}}, {"profile_marker": "A"}))
        self.assertEqual(results[1], (str(homes[1]), "B", {"skill-B": {"created_by": "agent", "use_count": 1}}, {"profile_marker": "B"}))
        self.assertEqual((homes[0] / "memories" / "MEMORY.md").read_text(), "A")
        self.assertEqual((homes[1] / "memories" / "MEMORY.md").read_text(), "B")
        self.assertFalse((homes[0] / "skills" / "learned" / "skill-B").exists())
        self.assertFalse((homes[1] / "skills" / "learned" / "skill-A").exists())

    async def test_admin_scope_is_derived_and_removed_training_scope_is_rejected(self) -> None:
        admin, admin_error = _resolve_macsoft_profile_home(
            _Request(api_key="internal-secret", admin_scope="admin")
        )
        self.assertIsNone(admin_error)
        self.assertEqual(admin, self.shared_home / "admin")

        removed, removed_error = _resolve_macsoft_profile_home(
            _Request(api_key="internal-secret", admin_scope="global-training:admin_sess_0123456789abcdef0123456789abcdef")
        )
        self.assertIsNone(removed)
        self.assertEqual(removed_error.status, 400)

    async def test_scope_headers_conflict_and_run_binding_cannot_cross_scope(self) -> None:
        _home, conflict = _resolve_macsoft_profile_home(
            _Request(
                api_key="internal-secret",
                profile_id=self.profile_ids[0],
                admin_scope="admin",
            )
        )
        self.assertEqual(conflict.status, 400)

        run_id = "run_admin_scope"
        self.adapter._run_profile_homes[run_id] = self.shared_home / "admin"
        self.adapter._set_run_status(run_id, "running")
        wrong = await self.adapter._handle_get_run(
            _Request(
                api_key="internal-secret",
                profile_id=self.profile_ids[0],
                match_info={"run_id": run_id},
            )
        )
        self.assertEqual(wrong.status, 404)
        owned = await self.adapter._handle_get_run(
            _Request(
                api_key="internal-secret",
                admin_scope="admin",
                match_info={"run_id": run_id},
            )
        )
        self.assertEqual(owned.status, 200)

    async def test_pin_only_accepts_learned_skill(self) -> None:
        profile_id = self.profile_ids[0]
        home = self.profile_root / profile_id
        private = home / "skills" / "private" / "uploaded" / "SKILL.md"
        private.parent.mkdir(parents=True)
        private.write_text("private", encoding="utf-8")
        request = _Request(
            api_key="internal-secret",
            profile_id=profile_id,
            match_info={"skill_id": "uploaded"},
            body={"pinned": True},
        )
        response = await self.adapter._handle_macsoft_skill_pin(request)
        self.assertEqual(response.status, 404)
        self.assertEqual(private.read_text(encoding="utf-8"), "private")

    async def test_restore_rejects_learned_skill_without_agent_provenance(self) -> None:
        profile_id = self.profile_ids[0]
        home = self.profile_root / profile_id
        manual = home / "skills" / "learned" / "manual" / "SKILL.md"
        manual.parent.mkdir(parents=True)
        manual.write_text("---\nname: manual\n---\nmanual", encoding="utf-8")
        request = _Request(
            api_key="internal-secret",
            profile_id=profile_id,
            match_info={"skill_id": "manual"},
        )
        response = await self.adapter._handle_macsoft_skill_restore(request)
        self.assertEqual(response.status, 403)
        self.assertEqual(manual.read_text(encoding="utf-8"), "---\nname: manual\n---\nmanual")

    async def test_backup_list_never_exposes_paths(self) -> None:
        profile_id = self.profile_ids[0]
        home = self.profile_root / profile_id
        learned = home / "skills" / "learned"
        skill = learned / "example" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: example\n---\n", encoding="utf-8")
        snapshot_request = _Request(api_key="internal-secret", profile_id=profile_id)
        snapshot = await self.adapter._handle_macsoft_backup_snapshot(snapshot_request)
        self.assertEqual(snapshot.status, 200)
        listed = await self.adapter._handle_macsoft_backups(snapshot_request)
        payload = json.loads(listed.text)
        self.assertTrue(payload["backups"])
        self.assertNotIn("path", payload["backups"][0])

    async def test_run_control_plane_rejects_another_profile(self) -> None:
        run_id = "run_0123456789abcdef"
        self.adapter._run_profile_homes[run_id] = self.profile_root / self.profile_ids[0]
        self.adapter._set_run_status(run_id, "running")

        wrong = await self.adapter._handle_get_run(
            _Request(
                api_key="internal-secret",
                profile_id=self.profile_ids[1],
                match_info={"run_id": run_id},
            )
        )
        self.assertEqual(wrong.status, 404)

        owned = await self.adapter._handle_get_run(
            _Request(
                api_key="internal-secret",
                profile_id=self.profile_ids[0],
                match_info={"run_id": run_id},
            )
        )
        self.assertEqual(owned.status, 200)

    async def test_run_completion_does_not_wait_for_profile_learning_callback(self) -> None:
        profile_id = self.profile_ids[0]
        home = self.profile_root / profile_id

        class Agent:
            session_prompt_tokens = 0
            session_completion_tokens = 0
            session_total_tokens = 0

            def __init__(self, stream_delta_callback):
                self.stream_delta_callback = stream_delta_callback
                self.background_review_callback = None
                self.background_review_lifecycle_callback = None

            def run_conversation(self, **_kwargs):
                self.stream_delta_callback("answer")

                def finish_learning():
                    time.sleep(0.2)
                    self.background_review_lifecycle_callback(
                        "completed", "native review completed"
                    )

                threading.Thread(target=finish_learning, daemon=True).start()
                return {"final_response": "answer"}

            def interrupt(self, _message):
                return None

        self.adapter._create_agent = lambda **kwargs: Agent(
            kwargs["stream_delta_callback"]
        )
        response = await self.adapter._handle_runs(
            _Request(
                api_key="internal-secret",
                profile_id=profile_id,
                body={"input": "learn this", "session_id": "session-a"},
            )
        )
        payload = json.loads(response.text)
        run_id = payload["run_id"]

        for _ in range(50):
            if self.adapter._run_statuses.get(run_id, {}).get("status") == "completed":
                break
            await asyncio.sleep(0.01)
        self.assertEqual(self.adapter._run_statuses[run_id]["status"], "completed")
        event = home / "logs" / "learning-events" / f"{run_id}.json"
        self.assertFalse(event.exists(), "foreground run waited for background learning")

        for _ in range(50):
            if event.exists():
                break
            await asyncio.sleep(0.01)
        self.assertTrue(event.is_file())
        self.assertFalse(
            (
                self.profile_root
                / self.profile_ids[1]
                / "logs"
                / "learning-events"
                / f"{run_id}.json"
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
