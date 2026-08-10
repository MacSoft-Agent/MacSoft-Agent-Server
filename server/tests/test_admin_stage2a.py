from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from starlette.background import BackgroundTask
from starlette.requests import Request

from macsoft.admin.auth import AdminAccessRegistry, bootstrap_response, require_admin
from macsoft.admin.message_store import list_admin_messages
from macsoft.admin.session_store import create_admin_session, list_admin_sessions, soft_delete_admin_session
from macsoft.db import connect_db, init_db
from macsoft.gateway.routes_admin import AdminChatRequest, admin_chat_stream, get_admin_sessions, post_admin_session
from macsoft.chat.active_runs import ActiveChatRunRegistry
from macsoft.chat.hermes_client import HermesApiError


def make_request(app: FastAPI, host: str = "127.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "app": app,
            "headers": [],
            "client": (host, 50000),
            "server": ("127.0.0.1", 8787),
        }
    )


async def consume(response) -> list[str]:
    chunks: list[str] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    if response.background is not None:
        await response.background()
    return chunks


class AdminStage2ATests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "admin.db"
        self.config = SimpleNamespace(
            database=SimpleNamespace(path=str(self.db_path)),
            hermes=SimpleNamespace(
                api_base_url="http://127.0.0.1:8642",
                api_key="internal-test-key",
                request_timeout_seconds=5,
            ),
        )
        init_db(self.config)
        self.app = FastAPI()
        self.app.state.config = self.config
        self.app.state.admin_access_registry = AdminAccessRegistry(ttl_seconds=1)
        self.app.state.active_chat_runs = ActiveChatRunRegistry()
        self.request = make_request(self.app)
        self.previous_host_token = os.environ.get("MACSOFT_HOST_CONTROL_TOKEN")
        os.environ["MACSOFT_HOST_CONTROL_TOKEN"] = "host-token-" + "x" * 32

    def tearDown(self) -> None:
        if self.previous_host_token is None:
            os.environ.pop("MACSOFT_HOST_CONTROL_TOKEN", None)
        else:
            os.environ["MACSOFT_HOST_CONTROL_TOKEN"] = self.previous_host_token
        self.temp.cleanup()

    def admin_token(self) -> str:
        return bootstrap_response(self.request, f"Bearer {os.environ['MACSOFT_HOST_CONTROL_TOKEN']}")["access_token"]

    def test_bootstrap_requires_loopback_and_host_token(self) -> None:
        token = self.admin_token()
        self.assertNotEqual(token, os.environ["MACSOFT_HOST_CONTROL_TOKEN"])
        require_admin(self.request, f"Bearer {token}")

        with self.assertRaises(HTTPException) as wrong:
            bootstrap_response(self.request, "Bearer device-token")
        self.assertEqual(wrong.exception.status_code, 401)

        with self.assertRaises(HTTPException) as lan:
            bootstrap_response(make_request(self.app, "192.168.1.10"), f"Bearer {os.environ['MACSOFT_HOST_CONTROL_TOKEN']}")
        self.assertEqual(lan.exception.detail["error"]["code"], "loopback_required")

    def test_expiry_and_host_token_are_not_valid_admin_credentials(self) -> None:
        registry = AdminAccessRegistry(ttl_seconds=0)
        token, _ = registry.issue()
        self.assertFalse(registry.validate(token))
        with self.assertRaises(HTTPException):
            require_admin(self.request, f"Bearer {os.environ['MACSOFT_HOST_CONTROL_TOKEN']}")

    def test_admin_sessions_are_isolated_and_soft_deleted(self) -> None:
        token = self.admin_token()
        created = post_admin_session(self.request, SimpleNamespace(title="Admin"), f"Bearer {token}")
        session_id = created["session"]["session_id"]
        self.assertEqual(get_admin_sessions(self.request, f"Bearer {token}")["sessions"][0]["session_id"], session_id)
        conn = connect_db(self.config)
        try:
            self.assertTrue(soft_delete_admin_session(conn, session_id))
            self.assertEqual(list_admin_sessions(conn), [])
        finally:
            conn.close()

    def test_admin_stream_persists_user_then_assistant_and_releases_run(self) -> None:
        token = self.admin_token()
        conn = connect_db(self.config)
        try:
            created = create_admin_session(conn, "Chat")
        finally:
            conn.close()
        body = AdminChatRequest(session_id=created["session_id"], message="Hello")
        with patch(
            "macsoft.gateway.routes_admin.stream_interruptible_hermes_reply_events",
            return_value=iter([{"type": "text_delta", "text": "Hi"}]),
        ):
            response = admin_chat_stream(self.request, body, f"Bearer {token}")
            events = "".join(asyncio.run(consume(response)))

        self.assertIn("event: message_start", events)
        self.assertIn("event: token_delta", events)
        self.assertIn("event: message_done", events)
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("SELECT role, content FROM admin_messages ORDER BY created_at").fetchall()
        finally:
            conn.close()
        self.assertEqual([row[0] for row in rows], ["user", "assistant"])
        self.assertFalse(self.app.state.active_chat_runs.is_active(f"admin:{created['session_id']}"))

    def test_admin_stream_uses_native_hermes_tools_without_client_capability_gate(self) -> None:
        token = self.admin_token()
        conn = connect_db(self.config)
        try:
            created = create_admin_session(conn, "Native tools")
        finally:
            conn.close()
        body = AdminChatRequest(
            session_id=created["session_id"],
            message="What is the weather in Kuala Lumpur today?",
        )
        captured: dict[str, object] = {}

        def native_reply(**kwargs):
            captured.update(kwargs)
            return iter([{"type": "text_delta", "text": "Native live result"}])

        with patch(
            "macsoft.gateway.routes_admin.stream_interruptible_hermes_reply_events",
            side_effect=native_reply,
        ):
            response = admin_chat_stream(self.request, body, f"Bearer {token}")
            events = "".join(asyncio.run(consume(response)))

        messages = captured["messages"]
        self.assertIsInstance(messages, list)
        system_instruction = messages[0]["content"]
        self.assertIn("native Hermes", system_instruction)
        self.assertNotIn("[PERMISSION / TOOL GATE]", system_instruction)
        self.assertIn("Native live result", events)
        self.assertNotIn("no approved live-data Tool", events)

    def test_admin_stream_exposes_specific_provider_usage_limit(self) -> None:
        token = self.admin_token()
        conn = connect_db(self.config)
        try:
            created = create_admin_session(conn, "Usage limit")
        finally:
            conn.close()
        body = AdminChatRequest(session_id=created["session_id"], message="Hello")
        upstream_error = HermesApiError(
            "Error code: 429 - {'error': {'type': 'usage_limit_reached', "
            "'message': 'The usage limit has been reached'}}",
            kind="run_failed",
        )

        with patch(
            "macsoft.gateway.routes_admin.stream_interruptible_hermes_reply_events",
            side_effect=upstream_error,
        ):
            response = admin_chat_stream(self.request, body, f"Bearer {token}")
            events = "".join(asyncio.run(consume(response)))

        self.assertIn("MacSoft Agent Model/Provider usage limit", events)
        self.assertNotIn("The request could not be completed", events)
        self.assertNotIn("Hermes", events)
        self.assertIn('"ok": false', events)

    def test_admin_stream_preserves_unrecognized_redacted_ai_error(self) -> None:
        token = self.admin_token()
        conn = connect_db(self.config)
        try:
            created = create_admin_session(conn, "Provider failure")
        finally:
            conn.close()
        body = AdminChatRequest(session_id=created["session_id"], message="Hello")

        with patch(
            "macsoft.gateway.routes_admin.stream_interruptible_hermes_reply_events",
            side_effect=HermesApiError(
                "Hermes provider rejected model route provider_x",
                kind="run_failed",
            ),
        ):
            response = admin_chat_stream(self.request, body, f"Bearer {token}")
            events = "".join(asyncio.run(consume(response)))

        self.assertIn("provider_x", events)
        self.assertIn("MacSoft Agent", events)
        self.assertNotIn("Hermes", events)
        self.assertNotIn("The request could not be completed", events)
        self.assertIn('"ok": false', events)


if __name__ == "__main__":
    unittest.main()
