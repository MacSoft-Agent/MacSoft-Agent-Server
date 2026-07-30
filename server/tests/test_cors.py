from __future__ import annotations

import asyncio
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


DEV_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
}


async def asgi_request(
    app,
    *,
    method: str,
    path: str,
    headers: dict[str, str],
) -> tuple[int, dict[str, str], bytes]:
    sent: list[dict] = []
    receive_messages = [
        {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }
    ]

    async def receive() -> dict:
        if receive_messages:
            return receive_messages.pop(0)
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (name.lower().encode("ascii"), value.encode("ascii"))
            for name, value in headers.items()
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8787),
    }
    await app(scope, receive, send)

    start = next(message for message in sent if message["type"] == "http.response.start")
    response_headers = {
        name.decode("latin-1").lower(): value.decode("latin-1")
        for name, value in start["headers"]
    }
    body = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    return int(start["status"]), response_headers, body


class CorsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        config_path = root / "macsoft-server.yaml"
        database_path = (root / "macsoft-server.db").as_posix()
        config_path.write_text(
            "\n".join(
                [
                    "server:",
                    '  host: "127.0.0.1"',
                    "  port: 8787",
                    "database:",
                    f'  path: "{database_path}"',
                    "hermes:",
                    '  home: "."',
                    '  api_base_url: "http://127.0.0.1:8642"',
                    '  api_key: "test-only"',
                    "  request_timeout_seconds: 5",
                    "runtime:",
                    '  mode: "minimal"',
                    "autocount:",
                    "  enabled: false",
                    '  catalog_path: "./missing-test-catalog.json"',
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        cls.previous_config = os.environ.get("MACSOFT_SERVER_CONFIG")
        os.environ["MACSOFT_SERVER_CONFIG"] = str(config_path)
        sys.modules.pop("macsoft.server", None)
        cls.server_module = importlib.import_module("macsoft.server")
        cls.app = cls.server_module.app

    @classmethod
    def tearDownClass(cls) -> None:
        sys.modules.pop("macsoft.server", None)
        if cls.previous_config is None:
            os.environ.pop("MACSOFT_SERVER_CONFIG", None)
        else:
            os.environ["MACSOFT_SERVER_CONFIG"] = cls.previous_config
        cls.temp.cleanup()

    def test_health_allows_each_explicit_client_dev_origin(self) -> None:
        self.assertEqual(set(self.server_module.CLIENT_CORS_ORIGINS), DEV_ORIGINS)
        for origin in sorted(DEV_ORIGINS):
            with self.subTest(origin=origin):
                status, headers, _ = asyncio.run(
                    asgi_request(
                        self.app,
                        method="GET",
                        path="/health",
                        headers={"origin": origin},
                    )
                )
                self.assertEqual(status, 200)
                self.assertEqual(headers["access-control-allow-origin"], origin)

    def test_client_me_preflight_allows_required_method_and_headers(self) -> None:
        requested_headers = {
            "authorization",
            "content-type",
            "x-client-version",
            "x-device-id",
            "x-macsoft-client-capabilities",
        }
        status, headers, _ = asyncio.run(
            asgi_request(
                self.app,
                method="OPTIONS",
                path="/api/client/me",
                headers={
                    "origin": "http://127.0.0.1:5175",
                    "access-control-request-method": "GET",
                    "access-control-request-headers": ",".join(
                        sorted(requested_headers)
                    ),
                },
            )
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            headers["access-control-allow-origin"],
            "http://127.0.0.1:5175",
        )
        self.assertIn("GET", headers["access-control-allow-methods"])
        allowed_headers = {
            item.strip().lower()
            for item in headers["access-control-allow-headers"].split(",")
        }
        self.assertTrue(requested_headers <= allowed_headers)

    def test_unlisted_lan_origin_is_not_reflected(self) -> None:
        status, headers, _ = asyncio.run(
            asgi_request(
                self.app,
                method="GET",
                path="/health",
                headers={"origin": "http://192.168.1.99:5174"},
            )
        )
        self.assertEqual(status, 200)
        self.assertNotIn("access-control-allow-origin", headers)


if __name__ == "__main__":
    unittest.main()
