from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from starlette.requests import Request

from macsoft.db import init_db
from macsoft.gateway.routes_chat import ChatStreamRequest, chat_stream
from macsoft.gateway.routes_sessions import (
    CreateSessionRequest,
    create_new_session,
    delete_session,
    get_session_messages,
    list_sessions,
    router as sessions_router,
)
from macsoft.sessions.message_store import save_message


SCHEMA = """
CREATE TABLE users (user_id TEXT PRIMARY KEY, display_name TEXT, role TEXT, status TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE devices (device_id TEXT PRIMARY KEY, user_id TEXT, device_token TEXT UNIQUE, client_name TEXT, client_version TEXT, display_name TEXT, role TEXT, status TEXT, paired_at TEXT, last_seen_at TEXT, revoked_at TEXT);
CREATE TABLE sessions (session_id TEXT PRIMARY KEY, user_id TEXT, owner_device_id TEXT, title TEXT, source TEXT, status TEXT, archived INTEGER, last_message_preview TEXT, hermes_stored_session_id TEXT, created_at TEXT, updated_at TEXT, deleted_at TEXT);
CREATE TABLE messages (message_id TEXT PRIMARY KEY, session_id TEXT, user_id TEXT, role TEXT, content TEXT, status TEXT, model TEXT, created_at TEXT);
"""


def create_database(path: Path) -> None:
    now = "2026-07-14T00:00:00+00:00"
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        for user_id in ("user_a", "user_b"):
            conn.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, user_id, "User", "active", now, now),
            )
        conn.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("device_a", "user_a", "token-a", "Client", "1", "A", "User", "active", now, now, None),
        )
        conn.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("device_b", "user_a", "token-b", "Client", "1", "B", "User", "active", now, now, None),
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("session_a", "user_a", "device_a", "A", "client", "active", 0, "", None, now, now, None),
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("session_b", "user_a", "device_b", "B", "client", "active", 0, "", None, now, now, None),
        )
        conn.execute(
            "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("message_a", "session_a", "user_a", "user", "Keep this", "saved", None, now),
        )
        conn.commit()
    finally:
        conn.close()


class SessionSoftDeleteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "sessions.db"
        create_database(self.db_path)
        config = SimpleNamespace(
            database=SimpleNamespace(path=str(self.db_path)),
            hermes=SimpleNamespace(
                api_base_url="http://127.0.0.1:8642",
                api_key="internal-key",
                request_timeout_seconds=5,
            ),
        )
        self.request = Request(
            {
                "type": "http",
                "app": SimpleNamespace(state=SimpleNamespace(config=config)),
                "headers": [],
            }
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def delete_as_a(self, session_id: str = "session_a") -> dict:
        return delete_session(
            session_id,
            self.request,
            authorization="Bearer token-a",
            x_device_id="device_a",
        )

    def test_delete_route_is_registered_once(self) -> None:
        matches = [
            route
            for route in sessions_router.routes
            if getattr(route, "path", None) == "/api/sessions/{session_id}"
            and "DELETE" in getattr(route, "methods", set())
        ]
        self.assertEqual(len(matches), 1)

    def test_existing_session_create_and_list_shapes_remain_compatible(self) -> None:
        created = create_new_session(
            self.request,
            CreateSessionRequest(title="New session"),
            authorization="Bearer token-a",
            x_device_id="device_a",
        )
        expected_create_fields = {
            "ok",
            "session",
            "id",
            "session_id",
            "title",
            "created_at",
            "updated_at",
            "archived",
            "user_id",
            "status",
            "last_message_preview",
            "hermes_stored_session_id",
        }
        self.assertTrue(expected_create_fields <= set(created))

        listed = list_sessions(
            self.request,
            authorization="Bearer token-a",
            x_device_id="device_a",
        )
        self.assertEqual(set(listed), {"ok", "sessions"})
        session = next(
            item for item in listed["sessions"]
            if item["session_id"] == created["session_id"]
        )
        self.assertEqual(
            set(session),
            {
                "id",
                "session_id",
                "user_id",
                "title",
                "source",
                "status",
                "archived",
                "last_message_preview",
                "hermes_stored_session_id",
                "created_at",
                "updated_at",
            },
        )

    def test_owner_delete_is_idempotent_and_preserves_physical_rows(self) -> None:
        first = self.delete_as_a()
        second = self.delete_as_a()
        self.assertEqual(first["session_id"], "session_a")
        self.assertTrue(first["deleted"])
        self.assertEqual(first["action"], "delete_session")
        self.assertEqual(first["delete_mode"], "soft")
        self.assertFalse(second["deleted"])
        self.assertEqual(second["deleted_at"], first["deleted_at"])
        self.assertEqual(second["reason"], "already_deleted")

        listed = list_sessions(
            self.request,
            authorization="Bearer token-a",
            x_device_id="device_a",
        )
        self.assertEqual(listed["sessions"], [])

        with self.assertRaises(HTTPException) as history_error:
            get_session_messages(
                "session_a",
                self.request,
                authorization="Bearer token-a",
                x_device_id="device_a",
            )
        self.assertEqual(history_error.exception.status_code, 404)

        with self.assertRaises(HTTPException) as chat_error:
            chat_stream(
                self.request,
                ChatStreamRequest(session_id="session_a", message="Hello"),
                authorization="Bearer token-a",
                x_device_id="device_a",
                x_macsoft_client_capabilities=None,
            )
        self.assertEqual(chat_error.exception.status_code, 404)

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions WHERE session_id='session_a'").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM messages WHERE session_id='session_a'").fetchone()[0], 1)
            self.assertIsNotNone(conn.execute("SELECT deleted_at FROM sessions WHERE session_id='session_a'").fetchone()[0])
            with self.assertRaises(ValueError):
                save_message(
                    conn,
                    session_id="session_a",
                    user_id="user_a",
                    owner_device_id="device_a",
                    role="user",
                    content="Must not append",
                )
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM messages WHERE session_id='session_a'").fetchone()[0], 1)
        finally:
            conn.close()

    def test_foreign_unknown_and_unauthenticated_delete_errors_are_distinct(self) -> None:
        with self.assertRaises(HTTPException) as foreign:
            self.delete_as_a("session_b")
        self.assertEqual(foreign.exception.status_code, 404)
        self.assertEqual(foreign.exception.detail["error"]["code"], "session_not_found")

        with self.assertRaises(HTTPException) as unknown:
            self.delete_as_a("missing")
        self.assertEqual(unknown.exception.status_code, 404)
        self.assertEqual(unknown.exception.detail["error"]["code"], "session_not_found")

        with self.assertRaises(HTTPException) as unauthorized:
            delete_session(
                "session_a",
                self.request,
                authorization="Bearer invalid",
                x_device_id="device_a",
            )
        self.assertEqual(unauthorized.exception.status_code, 401)
        self.assertEqual(unauthorized.exception.detail["error"]["code"], "invalid_device_token")

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertIsNone(conn.execute("SELECT deleted_at FROM sessions WHERE session_id='session_b'").fetchone()[0])
        finally:
            conn.close()

    def test_same_user_devices_cannot_cross_session_boundaries(self) -> None:
        listed_b = list_sessions(
            self.request,
            authorization="Bearer token-b",
            x_device_id="device_b",
        )
        self.assertEqual(
            [item["session_id"] for item in listed_b["sessions"]],
            ["session_b"],
        )

        with self.assertRaises(HTTPException) as messages_error:
            get_session_messages(
                "session_a",
                self.request,
                authorization="Bearer token-b",
                x_device_id="device_b",
            )
        self.assertEqual(messages_error.exception.status_code, 404)

        with self.assertRaises(HTTPException) as chat_error:
            chat_stream(
                self.request,
                ChatStreamRequest(session_id="session_a", message="Cross-device"),
                authorization="Bearer token-b",
                x_device_id="device_b",
                x_macsoft_client_capabilities=None,
            )
        self.assertEqual(chat_error.exception.status_code, 404)

        with self.assertRaises(HTTPException) as delete_error:
            delete_session(
                "session_a",
                self.request,
                authorization="Bearer token-b",
                x_device_id="device_b",
            )
        self.assertEqual(delete_error.exception.status_code, 404)

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertIsNone(
                conn.execute(
                    "SELECT deleted_at FROM sessions WHERE session_id='session_a'"
                ).fetchone()[0]
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id='session_a'"
                ).fetchone()[0],
                1,
            )
        finally:
            conn.close()


class SessionMigrationTests(unittest.TestCase):
    def test_existing_database_migrates_without_losing_sessions_or_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "legacy.db"
            conn = sqlite3.connect(db_path)
            now = "2026-07-14T00:00:00+00:00"
            try:
                conn.executescript(
                    """
                    CREATE TABLE users (user_id TEXT PRIMARY KEY, display_name TEXT, role TEXT, status TEXT, created_at TEXT, updated_at TEXT);
                    CREATE TABLE sessions (session_id TEXT PRIMARY KEY, user_id TEXT, title TEXT, source TEXT, status TEXT, archived INTEGER, last_message_preview TEXT, hermes_stored_session_id TEXT, created_at TEXT, updated_at TEXT);
                    CREATE TABLE messages (message_id TEXT PRIMARY KEY, session_id TEXT, user_id TEXT, role TEXT, content TEXT, status TEXT, model TEXT, created_at TEXT);
                    """
                )
                conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", ("legacy_user", "Legacy", "User", "active", now, now))
                conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("legacy_session", "legacy_user", "Legacy", "client", "active", 0, "", None, now, now))
                conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("legacy_message", "legacy_session", "legacy_user", "user", "Preserve", "saved", None, now))
                conn.commit()
            finally:
                conn.close()

            init_db(SimpleNamespace(database=SimpleNamespace(path=str(db_path))))

            conn = sqlite3.connect(db_path)
            try:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
                self.assertIn("deleted_at", columns)
                self.assertIn("owner_device_id", columns)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions WHERE session_id='legacy_session'").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM messages WHERE message_id='legacy_message'").fetchone()[0], 1)
                self.assertIsNone(conn.execute("SELECT deleted_at FROM sessions WHERE session_id='legacy_session'").fetchone()[0])
                self.assertIsNone(conn.execute("SELECT owner_device_id FROM sessions WHERE session_id='legacy_session'").fetchone()[0])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
