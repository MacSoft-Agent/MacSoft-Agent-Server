from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from fastapi import HTTPException
from starlette.requests import Request

from macsoft.chat.active_runs import get_active_chat_registry
from macsoft.chat.hermes_client import HermesApiError, _normalized_messages, _raise_transport_error
from macsoft.chat.result_formatter import (
    map_ai_service_response_error,
    map_user_readable_error,
)
from macsoft.gateway.routes_chat import (
    MAX_CHAT_MESSAGE_CHARS,
    ChatStreamRequest,
    chat_stream,
)
from macsoft.gateway.routes_sessions import delete_session
from macsoft.sessions.message_store import save_message as store_message


SCHEMA = """
CREATE TABLE users (user_id TEXT PRIMARY KEY, display_name TEXT, role TEXT, status TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE devices (device_id TEXT PRIMARY KEY, user_id TEXT, device_token TEXT UNIQUE, client_name TEXT, client_version TEXT, display_name TEXT, role TEXT, status TEXT, paired_at TEXT, last_seen_at TEXT, revoked_at TEXT);
CREATE TABLE sessions (session_id TEXT PRIMARY KEY, user_id TEXT, owner_device_id TEXT, title TEXT, source TEXT, status TEXT, archived INTEGER, last_message_preview TEXT, hermes_stored_session_id TEXT, created_at TEXT, updated_at TEXT, deleted_at TEXT);
CREATE TABLE messages (message_id TEXT PRIMARY KEY, session_id TEXT, user_id TEXT, role TEXT, content TEXT, status TEXT, model TEXT, created_at TEXT);
CREATE TABLE client_skills (skill_id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL, owner_device_id TEXT, slug TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL, content TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(owner_device_id, slug));
CREATE TABLE uploaded_files (file_id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL, owner_device_id TEXT NOT NULL, original_name TEXT NOT NULL, stored_name TEXT NOT NULL UNIQUE, media_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL);
"""


def create_database(path: Path) -> None:
    now = "2026-07-17T00:00:00+00:00"
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
            ("user_1", "User", "Admin", "active", now, now),
        )
        conn.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "device_1",
                "user_1",
                "device-token",
                "Client",
                "1.0",
                "Device",
                "Admin",
                "active",
                now,
                now,
                None,
            ),
        )
        for session_id in ("session_1", "session_2"):
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    "user_1",
                    "device_1",
                    session_id,
                    "client",
                    "active",
                    0,
                    "",
                    None,
                    now,
                    now,
                    None,
                ),
            )
        conn.commit()
    finally:
        conn.close()


async def consume(response) -> str:
    parts: list[str] = []
    async for chunk in response.body_iterator:
        parts.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    if response.background is not None:
        await response.background()
    return "".join(parts)


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in filter(str.strip, text.split("\n\n")):
        lines = block.splitlines()
        name = next(line[7:] for line in lines if line.startswith("event: "))
        data = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
        events.append((name, data))
    return events


class ChatBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "chat.db"
        create_database(self.db_path)
        config = SimpleNamespace(
            database=SimpleNamespace(path=str(self.db_path)),
            hermes=SimpleNamespace(
                api_base_url="http://127.0.0.1:8642",
                api_key="key",
                request_timeout_seconds=5,
            ),
        )
        self.request = Request(
            {
                "type": "http",
                "app": SimpleNamespace(state=SimpleNamespace(config=config)),
                "headers": [],
                "client": ("127.0.0.1", 50000),
            }
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def chat(self, body: ChatStreamRequest):
        return chat_stream(
            self.request,
            body,
            authorization="Bearer device-token",
            x_device_id="device_1",
            x_macsoft_client_capabilities="activity-v1",
        )

    def message_count(self, session_id: str = "session_1") -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                    (session_id,),
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def test_same_session_is_busy_while_different_session_can_start(self) -> None:
        with patch(
            "macsoft.gateway.routes_chat.stream_hermes_reply_events",
            return_value=iter([{"type": "text_delta", "text": "Done"}]),
        ):
            first = self.chat(ChatStreamRequest(session_id="session_1", message="First"))
            with self.assertRaises(HTTPException) as busy:
                self.chat(ChatStreamRequest(session_id="session_1", message="Second"))
            self.assertEqual(busy.exception.status_code, 409)
            self.assertEqual(busy.exception.detail["error"]["code"], "session_busy")

            other = self.chat(ChatStreamRequest(session_id="session_2", message="Other"))
            first_events = parse_sse(asyncio.run(consume(first)))
            other_events = parse_sse(asyncio.run(consume(other)))

        self.assertEqual(first_events[-1][0], "message_done")
        self.assertEqual(other_events[-1][0], "message_done")
        self.assertEqual(self.message_count("session_1"), 2)
        self.assertEqual(self.message_count("session_2"), 2)

    def test_delete_is_busy_until_stream_finishes(self) -> None:
        with patch(
            "macsoft.gateway.routes_chat.stream_hermes_reply_events",
            return_value=iter([{"type": "text_delta", "text": "Done"}]),
        ):
            response = self.chat(ChatStreamRequest(session_id="session_1", message="Work"))
            with self.assertRaises(HTTPException) as busy:
                delete_session(
                    "session_1",
                    self.request,
                    authorization="Bearer device-token",
                    x_device_id="device_1",
                )
            self.assertEqual(busy.exception.status_code, 409)
            self.assertEqual(busy.exception.detail["error"]["code"], "session_busy")
            events = parse_sse(asyncio.run(consume(response)))

        self.assertTrue(events[-1][1]["ok"])
        deleted = delete_session(
            "session_1",
            self.request,
            authorization="Bearer device-token",
            x_device_id="device_1",
        )
        self.assertTrue(deleted["deleted"])

    def test_disconnect_cleanup_releases_registry(self) -> None:
        with patch(
            "macsoft.gateway.routes_chat.stream_hermes_reply_events",
            return_value=iter([{"type": "text_delta", "text": "Done"}]),
        ):
            response = self.chat(ChatStreamRequest(session_id="session_1", message="Disconnect"))

            async def disconnect() -> None:
                await response.body_iterator.__anext__()
                await response.body_iterator.aclose()
                if response.background is not None:
                    await response.background()

            asyncio.run(disconnect())

        self.assertFalse(
            get_active_chat_registry(self.request.app).is_active("session_1")
        )

    def test_completed_reply_is_persisted_before_completion_event_disconnect(self) -> None:
        with patch(
            "macsoft.gateway.routes_chat.stream_hermes_reply_events",
            return_value=iter([{"type": "text_delta", "text": "Done"}]),
        ):
            response = self.chat(
                ChatStreamRequest(session_id="session_1", message="Complete")
            )

            async def disconnect_after_completion() -> int:
                async for chunk in response.body_iterator:
                    text = chunk.decode() if isinstance(chunk, bytes) else chunk
                    event_name, data = parse_sse(text)[0]
                    if (
                        event_name == "activity"
                        and data["activity_id"] == "agent_processing"
                        and data["status"] == "completed"
                    ):
                        persisted_count = self.message_count("session_1")
                        await response.body_iterator.aclose()
                        if response.background is not None:
                            await response.background()
                        return persisted_count
                self.fail("Agent completion activity was not emitted.")

            persisted_count = asyncio.run(disconnect_after_completion())

        self.assertEqual(persisted_count, 2)
        self.assertFalse(
            get_active_chat_registry(self.request.app).is_active("session_1")
        )

    def test_missing_attachment_blank_and_oversize_fail_before_save_or_ai(self) -> None:
        cases = [
            (
                ChatStreamRequest(
                    session_id="session_1",
                    message="Has file",
                    uploaded_file_ids=["file_1"],
                ),
                "file_not_found",
            ),
            (ChatStreamRequest(session_id="session_1", message=" \t\n "), "blank_message"),
            (
                ChatStreamRequest(
                    session_id="session_1",
                    message="x" * (MAX_CHAT_MESSAGE_CHARS + 1),
                ),
                "message_too_large",
            ),
        ]
        with patch("macsoft.gateway.routes_chat.request_hermes_reply") as legacy, patch(
            "macsoft.gateway.routes_chat.stream_hermes_reply_events"
        ) as stream:
            for body, code in cases:
                with self.subTest(code=code), self.assertRaises(HTTPException) as caught:
                    self.chat(body)
                self.assertEqual(caught.exception.status_code, 404 if code == "file_not_found" else 422)
                self.assertEqual(caught.exception.detail["error"]["code"], code)
        self.assertEqual(self.message_count(), 0)
        legacy.assert_not_called()
        stream.assert_not_called()

    def test_original_user_whitespace_is_preserved_in_db_and_ai_request(self) -> None:
        original = "  code:\n      indented value\n"
        captured: list[dict[str, str]] = []

        def stream(**kwargs):
            captured.extend(kwargs["messages"])
            return iter([{"type": "text_delta", "text": "Done"}])

        with patch(
            "macsoft.gateway.routes_chat.stream_hermes_reply_events",
            side_effect=stream,
        ):
            response = self.chat(ChatStreamRequest(session_id="session_1", message=original))
            asyncio.run(consume(response))

        conn = sqlite3.connect(self.db_path)
        try:
            stored = conn.execute(
                "SELECT content FROM messages WHERE role = 'user'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(stored, original)
        self.assertEqual(captured[-1], {"role": "user", "content": original})
        self.assertEqual(
            _normalized_messages([{"role": "user", "content": original}])[0]["content"],
            original,
        )

    def test_ai_context_is_bounded_to_newest_complete_turns(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            for index in range(60):
                conn.execute(
                    "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"u{index:02d}",
                        "session_1",
                        "user_1",
                        "user",
                        f"user-{index:02d}",
                        "saved",
                        None,
                        f"2026-07-17T00:{index:02d}:00+00:00",
                    ),
                )
                conn.execute(
                    "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"a{index:02d}",
                        "session_1",
                        "user_1",
                        "assistant",
                        f"assistant-{index:02d}",
                        "saved",
                        "model",
                        f"2026-07-17T00:{index:02d}:30+00:00",
                    ),
                )
            conn.commit()
        finally:
            conn.close()

        captured: list[dict[str, str]] = []

        def stream(**kwargs):
            captured.extend(kwargs["messages"])
            return iter([{"type": "text_delta", "text": "Done"}])

        with patch(
            "macsoft.gateway.routes_chat.stream_hermes_reply_events",
            side_effect=stream,
        ):
            response = self.chat(ChatStreamRequest(session_id="session_1", message="current"))
            asyncio.run(consume(response))

        non_system = [message for message in captured if message["role"] != "system"]
        self.assertEqual(len(non_system), 41)
        self.assertEqual(non_system[0], {"role": "user", "content": "user-40"})
        self.assertEqual(non_system[-1], {"role": "user", "content": "current"})
        for index in range(0, 40, 2):
            self.assertEqual(non_system[index]["role"], "user")
            self.assertEqual(non_system[index + 1]["role"], "assistant")
        self.assertEqual(self.message_count(), 122)

    def test_assistant_persistence_failure_is_controlled_and_releases_busy_state(self) -> None:
        def save_side_effect(conn, **kwargs):
            if kwargs["role"] == "assistant":
                raise sqlite3.OperationalError("simulated locked database path")
            return store_message(conn, **kwargs)

        with patch(
            "macsoft.gateway.routes_chat.stream_hermes_reply_events",
            return_value=iter([{"type": "text_delta", "text": "Done"}]),
        ), patch(
            "macsoft.gateway.routes_chat.save_message",
            side_effect=save_side_effect,
        ):
            response = self.chat(ChatStreamRequest(session_id="session_1", message="Persist"))
            events = parse_sse(asyncio.run(consume(response)))

        self.assertEqual(events[-2][0], "error")
        self.assertEqual(
            events[-2][1]["error"]["code"],
            "assistant_persistence_failed",
        )
        self.assertEqual(events[-1][0], "message_done")
        self.assertFalse(events[-1][1]["ok"])
        self.assertFalse(
            get_active_chat_registry(self.request.app).is_active("session_1")
        )
        self.assertEqual(self.message_count(), 1)

    def test_sanitized_provider_usage_limit_is_returned_as_failed_request(self) -> None:
        provider_error = (
            "Sorry, I encountered an unexpected error. "
            "Your plan's usage limit has been reached. Please wait until it resets."
        )
        with patch(
            "macsoft.gateway.routes_chat.stream_hermes_reply_events",
            return_value=iter([{"type": "text_delta", "text": provider_error}]),
        ):
            response = self.chat(
                ChatStreamRequest(session_id="session_1", message="Hello")
            )
            events = parse_sse(asyncio.run(consume(response)))

        self.assertEqual(events[-1][0], "message_done")
        self.assertFalse(events[-1][1]["ok"])
        reply = next(data["text"] for name, data in events if name == "token_delta")
        self.assertIn("usage limit", reply.lower())
        self.assertIn("MacSoft", reply)
        self.assertIn("Model/Provider", reply)
        self.assertNotIn("Hermes", reply)
        self.assertNotIn("unexpected error", reply.lower())


class StructuredErrorTests(unittest.TestCase):
    def test_ai_usage_limit_response_is_specific_and_safe(self) -> None:
        raw = (
            "Sorry, I encountered an unexpected error. "
            "Your plan's usage limit has been reached. Please wait until it resets."
        )

        readable = map_ai_service_response_error(raw)

        self.assertIsNotNone(readable)
        assert readable is not None
        rendered = readable.title + readable.detail + readable.action
        self.assertIn("usage limit", rendered.lower())
        self.assertIn("MacSoft Agent", rendered)
        self.assertIn("Model/Provider", rendered)
        self.assertNotIn("Hermes", rendered)
        self.assertNotIn("unexpected error", rendered.lower())

    def test_ordinary_usage_limit_discussion_is_not_reclassified(self) -> None:
        self.assertIsNone(
            map_ai_service_response_error(
                "The provider documentation says a usage limit has been reached."
            )
        )

    def test_ai_http_429_has_a_specific_rate_limit_message(self) -> None:
        readable = map_user_readable_error(
            "MacSoft Agent service returned HTTP 429.",
            service="ai_service",
            kind="http_error",
            status_code=429,
        )
        self.assertIn("rate-limiting", readable.title)
        self.assertNotIn("could not be completed", readable.title)

    def test_ai_401_is_structured_and_does_not_point_to_autocount(self) -> None:
        error = HTTPError(
            "http://127.0.0.1:8642/v1/chat/completions",
            401,
            "Unauthorized",
            None,
            None,
        )
        with self.assertRaises(HermesApiError) as caught:
            _raise_transport_error(
                error,
                base_url="http://127.0.0.1:8642",
                timeout_seconds=5,
            )
        self.assertEqual(caught.exception.service, "ai_service")
        self.assertEqual(caught.exception.kind, "authentication")
        self.assertEqual(caught.exception.status_code, 401)
        readable = map_user_readable_error(
            str(caught.exception),
            service=caught.exception.service,
            kind=caught.exception.kind,
            status_code=caught.exception.status_code,
        )
        self.assertIn("Model/Provider", readable.title)
        self.assertNotIn("AutoCount", readable.title + readable.detail + readable.action)

    def test_autocount_401_and_ai_timeout_unavailable_remain_distinct(self) -> None:
        autocount = map_user_readable_error("AutoCount API HTTP 401")
        timeout = map_user_readable_error(
            "timed out",
            service="ai_service",
            kind="timeout",
        )
        unavailable = map_user_readable_error(
            "cannot connect",
            service="ai_service",
            kind="unavailable",
        )
        self.assertIn("AutoCount authentication", autocount.title)
        self.assertIn("timed out", timeout.title)
        self.assertIn("unavailable", unavailable.title)


if __name__ == "__main__":
    unittest.main()
