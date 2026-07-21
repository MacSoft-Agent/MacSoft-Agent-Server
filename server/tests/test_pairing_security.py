from __future__ import annotations

import concurrent.futures
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from macsoft.db import init_db
from macsoft.gateway.errors import register_exception_handlers
from macsoft.gateway.routes_client import router
from macsoft.identity.pairing import claim_pairing_code


class PairingSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "server.db"
        self.config = SimpleNamespace(database=SimpleNamespace(path=str(self.database)))
        init_db(self.config)
        self.app = FastAPI()
        self.app.state.config = self.config
        register_exception_handlers(self.app)
        self.app.include_router(router)

        @self.app.get("/_test/http/{status_code}")
        def http_error(status_code: int) -> None:
            raise HTTPException(status_code=status_code, detail="Request denied")

        @self.app.get("/_test/crash")
        def unexpected_error() -> None:
            raise RuntimeError("Bearer secret-value C:\\private\\customer.txt")

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _pairing_code(self, code: str = "PAIR-123456") -> str:
        conn = sqlite3.connect(self.database)
        try:
            conn.execute(
                """
                INSERT INTO pairing_codes (
                    pairing_code, user_id, status, created_at, expires_at, claimed_at
                ) VALUES (?, 'user_admin', 'active', ?, ?, NULL)
                """,
                (code, "2026-07-17T00:00:00+00:00", "2099-07-17T00:00:00+00:00"),
            )
            conn.commit()
        finally:
            conn.close()
        return code

    def test_lan_pairing_code_route_is_404_with_top_level_envelope(self) -> None:
        response = self.client.get("/api/dev/pairing-code")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {
                "ok": False,
                "error": {"code": "not_found", "message": "Not found", "details": {}},
            },
        )
        self.assertNotIn("pairing_code", response.text)

    def test_pairing_success_aliases_and_me_contract_are_preserved(self) -> None:
        code = self._pairing_code()
        response = self.client.post(
            "/api/client/pair",
            headers={"X-Device-Id": "device-a", "X-Client-Version": "2.0"},
            json={
                "pairing_code": code,
                "device_id": "device-a",
                "client_name": "MacSoft Client",
                "client_version": "2.0",
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["device_id"], "device-a")
        self.assertEqual(body["deviceId"], "device-a")
        self.assertEqual(body["device_token"], body["deviceToken"])
        self.assertEqual(body["paired_user"], body["pairedUser"])
        self.assertEqual(body["paired_at"], body["pairedAt"])

        me = self.client.get(
            "/api/client/me",
            headers={
                "Authorization": f"Bearer {body['device_token']}",
                "X-Device-Id": "device-a",
            },
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["default_model"], "server-hermes-current")

    def test_invalid_and_reused_code_use_top_level_410_envelope(self) -> None:
        code = self._pairing_code()
        payload = {
            "pairing_code": code,
            "device_id": "device-a",
            "client_name": "MacSoft Client",
            "client_version": "2.0",
        }
        self.assertEqual(self.client.post("/api/client/pair", json=payload).status_code, 200)
        reused = self.client.post("/api/client/pair", json=payload)
        self.assertEqual(reused.status_code, 410)
        self.assertEqual(reused.json()["error"]["code"], "invalid_pairing_code")
        self.assertNotIn("detail", reused.json())

    def test_validation_error_is_top_level_and_does_not_echo_input(self) -> None:
        secret = "secret-value-that-must-not-echo"
        response = self.client.post(
            "/api/client/pair",
            json={"pairing_code": secret, "device_id": ""},
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["error"]["code"], "validation_error")
        self.assertNotIn("detail", body)
        self.assertNotIn(secret, response.text)

    def test_standard_http_errors_are_top_level_without_detail_nesting(self) -> None:
        expected = {
            401: "unauthorized",
            403: "permission_denied",
            404: "not_found",
            409: "conflict",
            410: "gone",
        }
        for status_code, code in expected.items():
            with self.subTest(status_code=status_code):
                response = self.client.get(f"/_test/http/{status_code}")
                self.assertEqual(response.status_code, status_code)
                self.assertEqual(
                    response.json(),
                    {
                        "ok": False,
                        "error": {
                            "code": code,
                            "message": "Request denied",
                            "details": {},
                        },
                    },
                )
                self.assertNotIn("detail", response.json())

    def test_unexpected_error_is_sanitized_with_correlation_id(self) -> None:
        response = self.client.get("/_test/crash")
        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["error"]["code"], "internal_error")
        correlation_id = body["error"]["details"]["correlation_id"]
        self.assertEqual(len(correlation_id), 32)
        int(correlation_id, 16)
        self.assertNotIn("secret-value", response.text)
        self.assertNotIn("customer.txt", response.text)
        self.assertNotIn("C:\\private", response.text)

    def test_concurrent_claim_has_exactly_one_winner(self) -> None:
        code = self._pairing_code("PAIR-CONCURRENT")

        def claim() -> bool:
            conn = sqlite3.connect(self.database, timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                claim_pairing_code(conn, code)
                return True
            except ValueError:
                return False
            finally:
                conn.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _: claim(), range(8)))
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual(outcomes.count(False), 7)


if __name__ == "__main__":
    unittest.main()
