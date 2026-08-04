from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from macsoft.admin.auth import AdminAccessRegistry
from macsoft.chat.active_runs import ActiveChatRunRegistry
from macsoft.config import load_config
from macsoft.db import init_db, resolve_db_path
from macsoft.gateway.errors import register_exception_handlers
from macsoft.gateway.routes_admin import router as admin_router
from macsoft.gateway.routes_files import router as files_router


PNG = b"\x89PNG\r\n\x1a\n" + b"macsoft-admin-test-image"


class AdminFileContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        config_path = root / "macsoft-server.yaml"
        config_path.write_text(
            "\n".join(
                (
                    "database:",
                    '  path: "./data/macsoft-server.db"',
                    "hermes:",
                    '  home: "../hermes"',
                    '  api_base_url: "http://127.0.0.1:8642"',
                    '  api_key: "test-key"',
                    "  request_timeout_seconds: 5",
                    "",
                )
            ),
            encoding="utf-8",
        )
        self.config = load_config(str(config_path))
        init_db(self.config)
        self.previous_host_token = os.environ.get("MACSOFT_HOST_CONTROL_TOKEN")
        os.environ["MACSOFT_HOST_CONTROL_TOKEN"] = "host-token-" + "x" * 32

        app = FastAPI()
        app.state.config = self.config
        app.state.admin_access_registry = AdminAccessRegistry()
        app.state.active_chat_runs = ActiveChatRunRegistry()
        register_exception_handlers(app)
        app.include_router(admin_router)
        app.include_router(files_router)
        self.client = TestClient(app, client=("127.0.0.1", 50000))
        bootstrap = self.client.post(
            "/api/internal/desktop-admin/auth/session",
            headers={"Authorization": f"Bearer {os.environ['MACSOFT_HOST_CONTROL_TOKEN']}"},
        )
        self.assertEqual(bootstrap.status_code, 200, bootstrap.text)
        self.headers = {"Authorization": f"Bearer {bootstrap.json()['access_token']}"}

    def tearDown(self) -> None:
        self.client.close()
        if self.previous_host_token is None:
            os.environ.pop("MACSOFT_HOST_CONTROL_TOKEN", None)
        else:
            os.environ["MACSOFT_HOST_CONTROL_TOKEN"] = self.previous_host_token
        self.temp.cleanup()

    def create_session(self) -> str:
        response = self.client.post("/api/admin/sessions", headers=self.headers, json={"title": "Files"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["session"]["session_id"]

    def upload_png(self, session_id: str) -> dict:
        response = self.client.post(
            f"/api/admin/sessions/{session_id}/files",
            headers=self.headers,
            files={"file": ("receipt.png", PNG, "image/png")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_admin_upload_download_delete_and_session_isolation(self) -> None:
        session_id = self.create_session()
        other_session_id = self.create_session()
        uploaded = self.upload_png(session_id)

        downloaded = self.client.get(
            f"/api/admin/sessions/{session_id}/files/{uploaded['file_id']}", headers=self.headers
        )
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, PNG)
        self.assertEqual(downloaded.headers["cache-control"], "no-store")

        isolated = self.client.get(
            f"/api/admin/sessions/{other_session_id}/files/{uploaded['file_id']}", headers=self.headers
        )
        self.assertEqual(isolated.status_code, 404)
        self.assertEqual(isolated.json()["error"]["code"], "admin_file_not_found")

        client_route = self.client.get(f"/api/files/{uploaded['file_id']}", headers=self.headers)
        self.assertEqual(client_route.status_code, 401)

        deleted = self.client.delete(
            f"/api/admin/sessions/{session_id}/files/{uploaded['file_id']}", headers=self.headers
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["deleted"])

    def test_session_deletion_removes_attachment_bytes_and_record(self) -> None:
        session_id = self.create_session()
        uploaded = self.upload_png(session_id)
        path = resolve_db_path(self.config).parent / "admin_uploads" / f"{uploaded['file_id']}.png"
        self.assertTrue(path.exists())

        deleted = self.client.delete(f"/api/admin/sessions/{session_id}", headers=self.headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertFalse(path.exists())
        self.assertEqual(
            self.client.get(f"/api/admin/sessions/{session_id}/files/{uploaded['file_id']}", headers=self.headers).status_code,
            404,
        )

    def test_admin_chat_uses_admin_owned_attachment_content(self) -> None:
        session_id = self.create_session()
        uploaded = self.upload_png(session_id)
        captured: list[dict] = []

        def stream(**kwargs):
            captured.extend(kwargs["messages"])
            return iter([{"type": "text_delta", "text": "Read"}])

        with patch("macsoft.gateway.routes_admin.stream_interruptible_hermes_reply_events", side_effect=stream):
            response = self.client.post(
                "/api/admin/chat/stream",
                headers=self.headers,
                json={
                    "session_id": session_id,
                    "message": "Read this receipt.",
                    "uploaded_file_ids": [uploaded["file_id"]],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        user_content = next(message["content"] for message in reversed(captured) if message["role"] == "user")
        self.assertIsInstance(user_content, list)
        self.assertIn("receipt.png", user_content[0]["text"])
        self.assertTrue(user_content[1]["image_url"]["url"].startswith("data:image/png;base64,"))
        history = self.client.get(f"/api/admin/sessions/{session_id}/messages", headers=self.headers)
        self.assertEqual(history.status_code, 200, history.text)
        user_message = next(message for message in history.json()["messages"] if message["role"] == "user")
        self.assertEqual(
            user_message["attachments"],
            [
                {
                    "file_id": uploaded["file_id"],
                    "filename": "receipt.png",
                    "content_type": "image/png",
                    "size_bytes": len(PNG),
                    "created_at": uploaded["created_at"],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
