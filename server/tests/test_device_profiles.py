from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

from macsoft.db import init_db
from macsoft.profiles.registry import ensure_device_profile, resolve_profile_home


class DeviceProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.database = root / "server.db"
        self.profile_root = root / "runtime" / "profiles"
        self.hermes_home = root / "runtime"
        self.hermes_home.mkdir()
        (self.hermes_home / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "model": {"default": "server-model", "provider": "openai", "api_key": "do-not-copy"},
                    "gateway": {
                        "api_key": "do-not-copy",
                        "accessToken": "do-not-copy",
                        "provider-secret": "do-not-copy",
                        "credentialsFile": "do-not-copy",
                    },
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        self.config = SimpleNamespace(
            database=SimpleNamespace(path=str(self.database)),
            hermes=SimpleNamespace(home=str(self.hermes_home), profile_root=""),
        )
        init_db(self.config)
        self.conn = sqlite3.connect(self.database)
        self.conn.row_factory = sqlite3.Row
        now = "2026-08-05T00:00:00+00:00"
        self.conn.execute(
            "INSERT INTO devices VALUES (?, 'user_admin', ?, 'Client', '1', 'Client', 'Admin', 'active', ?, ?, NULL)",
            ("device-a", "token-a", now, now),
        )
        self.conn.execute(
            "INSERT INTO devices VALUES (?, 'user_admin', ?, 'Client', '1', 'Client', 'Admin', 'active', ?, ?, NULL)",
            ("device-b", "token-b", now, now),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _with_profile_root(self):
        import os

        previous = os.environ.get("MACSOFT_PROFILE_ROOT")
        os.environ["MACSOFT_PROFILE_ROOT"] = str(self.profile_root)
        return previous

    def _restore_profile_root(self, previous: str | None) -> None:
        import os

        if previous is None:
            os.environ.pop("MACSOFT_PROFILE_ROOT", None)
        else:
            os.environ["MACSOFT_PROFILE_ROOT"] = previous

    def test_each_device_is_provisioned_once_with_an_isolated_native_home(self) -> None:
        previous = self._with_profile_root()
        try:
            first = ensure_device_profile(self.conn, config=self.config, device_id="device-a")
            repeated = ensure_device_profile(self.conn, config=self.config, device_id="device-a")
            second = ensure_device_profile(self.conn, config=self.config, device_id="device-b")
        finally:
            self._restore_profile_root(previous)

        self.assertEqual(first["profile_id"], repeated["profile_id"])
        self.assertNotEqual(first["profile_id"], second["profile_id"])
        for profile in (first, second):
            home = self.profile_root / str(profile["profile_id"])
            self.assertTrue((home / "memories" / "USER.md").is_file())
            self.assertTrue((home / "memories" / "MEMORY.md").is_file())
            self.assertTrue((home / "skills" / "private").is_dir())
            self.assertTrue((home / "skills" / "learned").is_dir())
            profile_config = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(profile_config["model"]["default"], "server-model")
            self.assertNotIn("api_key", profile_config["model"])
            self.assertNotIn("api_key", profile_config["gateway"])
            self.assertNotIn("accessToken", profile_config["gateway"])
            self.assertNotIn("provider-secret", profile_config["gateway"])
            self.assertNotIn("credentialsFile", profile_config["gateway"])
            self.assertTrue(profile_config["memory"]["memory_enabled"])
            self.assertEqual(
                profile_config["skills"]["external_dirs"][0],
                str((self.hermes_home / "skills").resolve()),
            )

    def test_profile_path_rejects_untrusted_or_malformed_ids(self) -> None:
        previous = self._with_profile_root()
        try:
            with self.assertRaises(ValueError):
                resolve_profile_home(self.config, profile_id="../../outside")
        finally:
            self._restore_profile_root(previous)

    def test_device_revocation_freezes_and_reactivation_restores_same_profile(self) -> None:
        previous = self._with_profile_root()
        try:
            profile = ensure_device_profile(self.conn, config=self.config, device_id="device-a")
            self.conn.execute("UPDATE devices SET status='revoked', revoked_at='2026-08-05T01:00:00+00:00' WHERE device_id='device-a'")
            self.conn.commit()
            frozen = self.conn.execute("SELECT status FROM device_profiles WHERE device_id='device-a'").fetchone()
            self.assertEqual(frozen["status"], "frozen")

            self.conn.execute("UPDATE devices SET status='active', revoked_at=NULL WHERE device_id='device-a'")
            self.conn.commit()
            restored = ensure_device_profile(self.conn, config=self.config, device_id="device-a")
            self.assertEqual(restored["profile_id"], profile["profile_id"])
            self.assertEqual(restored["status"], "active")
        finally:
            self._restore_profile_root(previous)

    def test_server_restart_reuses_profile_and_preserves_learning_state(self) -> None:
        previous = self._with_profile_root()
        try:
            profile = ensure_device_profile(self.conn, config=self.config, device_id="device-a")
            home = self.profile_root / str(profile["profile_id"])
            memory = home / "memories" / "MEMORY.md"
            skill = home / "skills" / "learned" / "reconcile" / "SKILL.md"
            memory.write_text("persistent memory", encoding="utf-8")
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: reconcile\n---\npersistent skill", encoding="utf-8")

            self.conn.close()
            self.conn = sqlite3.connect(self.database)
            self.conn.row_factory = sqlite3.Row
            restarted = ensure_device_profile(
                self.conn, config=self.config, device_id="device-a"
            )

            self.assertEqual(restarted["profile_id"], profile["profile_id"])
            self.assertEqual(memory.read_text(encoding="utf-8"), "persistent memory")
            self.assertIn("persistent skill", skill.read_text(encoding="utf-8"))
        finally:
            self._restore_profile_root(previous)


if __name__ == "__main__":
    unittest.main()
