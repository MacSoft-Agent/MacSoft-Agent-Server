from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from macsoft.admin.auth import AdminAccessRegistry, bootstrap_response
from macsoft.admin.session_store import create_admin_session
from macsoft.chat.active_runs import ActiveChatRunRegistry
from macsoft.chat.hermes_client import interrupt_hermes_run, stream_interruptible_hermes_reply_events
from macsoft.db import connect_db, init_db
from macsoft.gateway.routes_admin import (
    AdminChatRequest,
    AdminInterruptRequest,
    admin_chat_stream,
    interrupt_admin_chat,
)


def make_request(app: FastAPI) -> Request:
    return Request({
        "type": "http",
        "app": app,
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8787),
    })


async def consume(response) -> str:
    chunks: list[str] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    if response.background is not None:
        await response.background()
    return "".join(chunks)


class AdminStage3InterruptTests(unittest.TestCase):
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
        self.app.state.admin_access_registry = AdminAccessRegistry(ttl_seconds=60)
        self.app.state.active_chat_runs = ActiveChatRunRegistry()
        self.request = make_request(self.app)
        self.previous_host_token = os.environ.get("MACSOFT_HOST_CONTROL_TOKEN")
        os.environ["MACSOFT_HOST_CONTROL_TOKEN"] = "host-token-" + "x" * 32
        self.token = bootstrap_response(
            self.request, f"Bearer {os.environ['MACSOFT_HOST_CONTROL_TOKEN']}"
        )["access_token"]
        conn = connect_db(self.config)
        try:
            self.session = create_admin_session(conn, "Interrupt")
            self.other_session = create_admin_session(conn, "Unrelated")
        finally:
            conn.close()

    def tearDown(self) -> None:
        if self.previous_host_token is None:
            os.environ.pop("MACSOFT_HOST_CONTROL_TOKEN", None)
        else:
            os.environ["MACSOFT_HOST_CONTROL_TOKEN"] = self.previous_host_token
        self.temp.cleanup()

    def test_registry_keeps_early_interrupt_and_isolates_run_keys(self) -> None:
        registry = ActiveChatRunRegistry()
        self.assertTrue(registry.reserve("admin:one"))
        self.assertTrue(registry.reserve("client:one"))
        self.assertEqual(registry.request_interrupt("admin:one"), (True, None))
        self.assertTrue(registry.bind_run("admin:one", "run_admin"))
        self.assertFalse(registry.interrupt_requested("client:one"))
        self.assertTrue(registry.is_active("client:one"))

    def test_registry_waits_for_real_release_without_force_unlocking(self) -> None:
        registry = ActiveChatRunRegistry()
        self.assertTrue(registry.reserve("admin:one"))
        releaser = threading.Thread(
            target=lambda: (time.sleep(0.02), registry.release("admin:one")),
            daemon=True,
        )
        releaser.start()

        self.assertTrue(registry.wait_until_released("admin:one", timeout_seconds=0.5))
        releaser.join(timeout=0.5)
        self.assertFalse(registry.is_active("admin:one"))

    def test_registry_wait_timeout_keeps_active_run_owned(self) -> None:
        registry = ActiveChatRunRegistry()
        self.assertTrue(registry.reserve("admin:one"))

        self.assertFalse(registry.wait_until_released("admin:one", timeout_seconds=0.01))
        self.assertTrue(registry.is_active("admin:one"))

    def test_interrupt_endpoint_targets_only_bound_admin_run(self) -> None:
        run_key = f"admin:{self.session['session_id']}"
        registry = self.app.state.active_chat_runs
        registry.reserve(run_key)
        registry.bind_run(run_key, "run_admin_target")
        registry.reserve(f"admin:{self.other_session['session_id']}")
        registry.bind_run(f"admin:{self.other_session['session_id']}", "run_other")
        registry.reserve("client:client_session")

        with patch("macsoft.gateway.routes_admin.interrupt_hermes_run", return_value=True) as stop, patch.object(
            registry, "wait_until_released", return_value=False
        ) as wait_for_release:
            result = interrupt_admin_chat(
                self.request,
                AdminInterruptRequest(session_id=self.session["session_id"]),
                f"Bearer {self.token}",
            )

        self.assertEqual(result["status"], "interrupting")
        wait_for_release.assert_called_once()
        self.assertEqual(stop.call_args.kwargs["run_id"], "run_admin_target")
        self.assertFalse(registry.interrupt_requested(f"admin:{self.other_session['session_id']}"))
        self.assertFalse(registry.interrupt_requested("client:client_session"))

    def test_partial_is_persisted_once_and_same_session_can_send_again(self) -> None:
        run_key = f"admin:{self.session['session_id']}"

        def interrupted_events(**kwargs):
            kwargs["on_run_started"]("run_partial")
            yield {"type": "text_delta", "text": "Partial answer"}
            self.app.state.active_chat_runs.request_interrupt(run_key)
            yield {"type": "interrupted", "run_id": "run_partial"}

        with patch(
            "macsoft.gateway.routes_admin.stream_interruptible_hermes_reply_events",
            side_effect=interrupted_events,
        ):
            response = admin_chat_stream(
                self.request,
                AdminChatRequest(session_id=self.session["session_id"], message="Long answer"),
                f"Bearer {self.token}",
            )
            events = asyncio.run(consume(response))

        self.assertEqual(events.count('event: token_delta'), 1)
        self.assertIn('"interrupted": true', events)
        self.assertFalse(self.app.state.active_chat_runs.is_active(run_key))

        with patch(
            "macsoft.gateway.routes_admin.stream_interruptible_hermes_reply_events",
            return_value=iter([{"type": "text_delta", "text": "Second answer"}]),
        ):
            second = admin_chat_stream(
                self.request,
                AdminChatRequest(session_id=self.session["session_id"], message="Try again"),
                f"Bearer {self.token}",
            )
            asyncio.run(consume(second))

        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT role, content, status FROM admin_messages WHERE session_id = ? ORDER BY created_at",
                (self.session["session_id"],),
            ).fetchall()
            unrelated = conn.execute(
                "SELECT COUNT(*) FROM admin_messages WHERE session_id = ?",
                (self.other_session["session_id"],),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(rows, [
            ("user", "Long answer", "saved"),
            ("assistant", "Partial answer", "interrupted"),
            ("user", "Try again", "saved"),
            ("assistant", "Second answer", "saved"),
        ])
        self.assertEqual(unrelated, 0)

    def test_interrupt_requires_an_active_admin_run(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            interrupt_admin_chat(
                self.request,
                AdminInterruptRequest(session_id=self.session["session_id"]),
                f"Bearer {self.token}",
            )
        self.assertEqual(caught.exception.status_code, 409)


class HermesRunsClientTests(unittest.TestCase):
    class Response:
        def __init__(self, body: bytes = b"", lines: list[bytes] | None = None) -> None:
            self.body = body
            self.lines = lines or []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return self.body

        def __iter__(self):
            return iter(self.lines)

    def test_run_id_is_exposed_and_cancelled_event_allows_empty_partial(self) -> None:
        start = self.Response(json.dumps({"run_id": "run_123", "status": "started"}).encode())
        events = self.Response(lines=[
            b'data: {"event":"message.delta","delta":"Part"}\n',
            b"\n",
            b'data: {"event":"run.cancelled","run_id":"run_123"}\n',
            b"\n",
        ])
        with patch("macsoft.chat.hermes_client.urlopen", side_effect=[start, events]) as open_url:
            received = list(stream_interruptible_hermes_reply_events(
                base_url="http://127.0.0.1:8642",
                api_key="secret",
                messages=[
                    {"role": "system", "content": "policy"},
                    {"role": "user", "content": "hello"},
                ],
                session_id="admin_scope",
                timeout_seconds=5,
                on_run_started=lambda run_id: run_id == "never",
            ))
        self.assertEqual([event["type"] for event in received], ["text_delta", "interrupted"])
        self.assertTrue(open_url.call_args_list[0].args[0].full_url.endswith("/v1/runs"))
        self.assertTrue(open_url.call_args_list[1].args[0].full_url.endswith("/v1/runs/run_123/events"))
        payload = json.loads(open_url.call_args_list[0].args[0].data.decode())
        self.assertEqual(payload["input"], [{"role": "user", "content": "hello"}])

    def test_run_wraps_multimodal_content_as_one_user_message(self) -> None:
        start = self.Response(json.dumps({"run_id": "run_image", "status": "started"}).encode())
        events = self.Response(lines=[
            b'data: {"event":"message.delta","delta":"I can see it."}\n',
            b"\n",
        ])
        image = {"type": "image_url", "image_url": {"url": "data:image/png;base64,UE5H"}}
        with patch("macsoft.chat.hermes_client.urlopen", side_effect=[start, events]) as open_url:
            list(stream_interruptible_hermes_reply_events(
                base_url="http://127.0.0.1:8642",
                api_key="secret",
                messages=[
                    {"role": "system", "content": "policy"},
                    {"role": "user", "content": [{"type": "text", "text": "Read this image."}, image]},
                ],
                session_id="admin_scope",
                timeout_seconds=5,
                on_run_started=lambda _run_id: False,
            ))
        payload = json.loads(open_url.call_args_list[0].args[0].data.decode())
        self.assertEqual(payload["input"], [{"role": "user", "content": [{"type": "text", "text": "Read this image."}, image]}])

    def test_stop_uses_the_existing_hermes_run_endpoint(self) -> None:
        with patch("macsoft.chat.hermes_client.urlopen", return_value=self.Response()) as open_url:
            self.assertTrue(interrupt_hermes_run(
                base_url="http://127.0.0.1:8642",
                api_key="secret",
                run_id="run_abc",
                timeout_seconds=5,
            ))
        request = open_url.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertTrue(request.full_url.endswith("/v1/runs/run_abc/stop"))


if __name__ == "__main__":
    unittest.main()
