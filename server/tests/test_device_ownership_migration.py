from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from macsoft.db import init_db


LEGACY_SCHEMA = """
CREATE TABLE users (
  user_id TEXT PRIMARY KEY, display_name TEXT, role TEXT, status TEXT,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE devices (
  device_id TEXT PRIMARY KEY, user_id TEXT, device_token TEXT UNIQUE,
  client_name TEXT, client_version TEXT, display_name TEXT, role TEXT,
  status TEXT, paired_at TEXT, last_seen_at TEXT, revoked_at TEXT
);
CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY, user_id TEXT, title TEXT, source TEXT,
  status TEXT, archived INTEGER, last_message_preview TEXT,
  hermes_stored_session_id TEXT, created_at TEXT, updated_at TEXT,
  deleted_at TEXT
);
CREATE TABLE messages (
  message_id TEXT PRIMARY KEY, session_id TEXT, user_id TEXT, role TEXT,
  content TEXT, status TEXT, model TEXT, created_at TEXT
);
CREATE TABLE client_skills (
  skill_id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL, slug TEXT NOT NULL,
  name TEXT NOT NULL, description TEXT NOT NULL, content TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, UNIQUE(owner_user_id, slug)
);
"""


class DeviceOwnershipMigrationTests(unittest.TestCase):
    def _legacy_database(self, path: Path, devices: list[str]) -> None:
        now = "2026-07-17T00:00:00+00:00"
        conn = sqlite3.connect(path)
        try:
            conn.executescript(LEGACY_SCHEMA)
            conn.execute(
                "INSERT INTO users VALUES ('user_admin', 'Admin', 'Admin', 'active', ?, ?)",
                (now, now),
            )
            for device_id in devices:
                conn.execute(
                    "INSERT INTO devices VALUES (?, 'user_admin', ?, 'Client', '1', ?, 'Admin', 'active', ?, ?, NULL)",
                    (device_id, f"token-{device_id}", device_id, now, now),
                )
            conn.execute(
                "INSERT INTO sessions VALUES ('legacy-session', 'user_admin', 'Legacy', 'client', 'active', 0, '', NULL, ?, ?, NULL)",
                (now, now),
            )
            conn.execute(
                "INSERT INTO messages VALUES ('legacy-message', 'legacy-session', 'user_admin', 'user', 'preserve', 'saved', NULL, ?)",
                (now,),
            )
            conn.execute(
                "INSERT INTO client_skills VALUES ('legacy-skill', 'user_admin', 'legacy', 'Legacy', '', 'preserve', 1, ?, ?)",
                (now, now),
            )
            conn.commit()
        finally:
            conn.close()

    def _assert_case(self, devices: list[str], expected_owner: str | None) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "legacy.db"
            self._legacy_database(path, devices)
            config = SimpleNamespace(database=SimpleNamespace(path=str(path)))
            init_db(config)
            init_db(config)

            conn = sqlite3.connect(path)
            try:
                session_owner = conn.execute(
                    "SELECT owner_device_id FROM sessions WHERE session_id='legacy-session'"
                ).fetchone()[0]
                skill_owner = conn.execute(
                    "SELECT owner_device_id FROM client_skills WHERE skill_id='legacy-skill'"
                ).fetchone()[0]
                self.assertEqual(session_owner, expected_owner)
                self.assertEqual(skill_owner, expected_owner)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM client_skills").fetchone()[0], 1)
            finally:
                conn.close()

    def test_zero_device_legacy_data_remains_unassigned_and_retained(self) -> None:
        self._assert_case([], None)

    def test_one_device_legacy_data_is_backfilled_idempotently(self) -> None:
        self._assert_case(["device-a"], "device-a")

    def test_multi_device_legacy_data_remains_unassigned_and_retained(self) -> None:
        self._assert_case(["device-a", "device-b"], None)

    def test_fresh_schema_allows_same_skill_slug_on_two_devices(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fresh.db"
            init_db(SimpleNamespace(database=SimpleNamespace(path=str(path))))
            conn = sqlite3.connect(path)
            try:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(client_skills)")}
                self.assertIn("owner_device_id", columns)
                table_sql = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='client_skills'"
                ).fetchone()[0]
                self.assertIn("UNIQUE(owner_device_id, slug)", table_sql)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
