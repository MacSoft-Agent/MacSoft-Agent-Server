from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from macsoft.config import load_config
from macsoft.db import connect_db, init_db
from macsoft.gateway.errors import register_exception_handlers
from macsoft.gateway.routes_audio import router as audio_router


class AudioTranscriptionContractTests(unittest.TestCase):
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
                    '  path: "./data/macsoft-server.db"',
                    "hermes:",
                    '  home: "../hermes"',
                    '  api_base_url: "http://127.0.0.1:8642"',
                    '  api_key: "test-key"',
                    "  request_timeout_seconds: 5",
                    "runtime:",
                    '  mode: "minimal"',
                    "",
                )
            ),
            encoding="utf-8",
        )
        self.config = load_config(str(config_path))
        init_db(self.config)
        conn = connect_db(self.config)
        try:
            now = "2026-08-03T00:00:00+00:00"
            conn.execute(
                """
                INSERT INTO devices (
                    device_id, user_id, device_token, client_name, client_version,
                    display_name, role, status, paired_at, last_seen_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "device_1", "user_admin", "token-1", "Client", "1.0",
                    "Device 1", "Admin", "active", now, now, None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        app = FastAPI()
        app.state.config = self.config
        register_exception_handlers(app)
        app.include_router(audio_router)
        self.client = TestClient(app)
        self.headers = {
            "Authorization": "Bearer token-1",
            "X-Device-Id": "device_1",
        }
        self.payload = {
            "data_url": "data:audio/webm;base64,aGVsbG8=",
            "mime_type": "audio/webm",
            "language": "zh",
        }

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    def test_authenticated_request_forwards_to_hermes_with_host_token(self) -> None:
        upstream = httpx.Response(
            200,
            json={"ok": True, "transcript": "hello from voice", "provider": "test"},
        )
        with patch.dict(
            "os.environ",
            {
                "MACSOFT_HOST_CONTROL_TOKEN": "host-secret",
                "MACSOFT_HERMES_CONFIG_API_URL": "http://127.0.0.1:9999",
            },
        ), patch("macsoft.gateway.routes_audio.httpx.post", return_value=upstream) as post:
            response = self.client.post(
                "/api/client/audio/transcribe",
                headers=self.headers,
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["transcript"], "hello from voice")
        self.assertEqual(post.call_args.args[0], "http://127.0.0.1:9999/api/audio/transcribe")
        self.assertEqual(post.call_args.kwargs["headers"]["X-Hermes-Session-Token"], "host-secret")
        self.assertEqual(post.call_args.kwargs["json"], self.payload)
        self.assertEqual(post.call_args.kwargs["timeout"], 120.0)

    def test_unsupported_language_is_rejected_before_forwarding(self) -> None:
        with patch("macsoft.gateway.routes_audio.httpx.post") as post:
            response = self.client.post(
                "/api/client/audio/transcribe",
                headers=self.headers,
                json={**self.payload, "language": "invalid"},
            )

        self.assertEqual(response.status_code, 422, response.text)
        post.assert_not_called()

    def test_invalid_device_is_rejected_before_forwarding(self) -> None:
        with patch("macsoft.gateway.routes_audio.httpx.post") as post:
            response = self.client.post(
                "/api/client/audio/transcribe",
                headers={"Authorization": "Bearer wrong", "X-Device-Id": "device_1"},
                json=self.payload,
            )

        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(response.json()["error"]["code"], "invalid_device_token")
        post.assert_not_called()

    def test_missing_host_token_reports_service_unavailable(self) -> None:
        with patch.dict("os.environ", {}, clear=True), patch("macsoft.gateway.routes_audio.httpx.post") as post:
            response = self.client.post(
                "/api/client/audio/transcribe",
                headers=self.headers,
                json=self.payload,
            )

        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["error"]["code"], "transcription_unavailable")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
