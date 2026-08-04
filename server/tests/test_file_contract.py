from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from macsoft.chat.active_runs import ActiveChatRunRegistry
from macsoft.config import load_config
from macsoft.db import connect_db, init_db
from macsoft.gateway.routes_chat import router as chat_router
from macsoft.gateway.errors import register_exception_handlers
from macsoft.gateway.routes_files import router as files_router


PNG = b"\x89PNG\r\n\x1a\n" + b"macsoft-test-image"


class FileContractTests(unittest.TestCase):
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
                    "models:",
                    '  default_model: "server-default"',
                    '  fallback_model: "server-fallback"',
                    "runtime:",
                    '  mode: "minimal"',
                    "autocount:",
                    "  enabled: false",
                    '  catalog_path: "./docs/autocount-api-catalog.json"',
                    "",
                )
            ),
            encoding="utf-8",
        )
        self.config = load_config(str(config_path))
        init_db(self.config)
        conn = connect_db(self.config)
        try:
            now = "2026-07-21T00:00:00+00:00"
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
            conn.execute(
                """
                INSERT INTO devices (
                    device_id, user_id, device_token, client_name, client_version,
                    display_name, role, status, paired_at, last_seen_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "device_2", "user_admin", "token-2", "Client", "1.0",
                    "Device 2", "Admin", "active", now, now, None,
                ),
            )
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, user_id, owner_device_id, title, source, status,
                    archived, last_message_preview, hermes_stored_session_id,
                    created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "session_1", "user_admin", "device_1", "Attachment", "client",
                    "active", 0, "", None, now, now, None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        app = FastAPI()
        app.state.config = self.config
        app.state.active_chat_runs = ActiveChatRunRegistry()
        register_exception_handlers(app)
        app.include_router(files_router)
        app.include_router(chat_router)
        self.client = TestClient(app)
        self.headers_1 = {
            "Authorization": "Bearer token-1",
            "X-Device-Id": "device_1",
        }
        self.headers_2 = {
            "Authorization": "Bearer token-2",
            "X-Device-Id": "device_2",
        }

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    def upload_png(self) -> dict:
        response = self.client.post(
            "/api/files",
            headers=self.headers_1,
            files={"file": ("bank-slip.png", PNG, "image/png")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_upload_download_delete_and_device_isolation(self) -> None:
        uploaded = self.upload_png()
        self.assertEqual(uploaded["file_id"], uploaded["fileId"])
        self.assertEqual(uploaded["content_type"], "image/png")

        downloaded = self.client.get(
            f"/api/files/{uploaded['file_id']}",
            headers=self.headers_1,
        )
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, PNG)
        self.assertEqual(downloaded.headers["cache-control"], "no-store")

        isolated = self.client.get(
            f"/api/files/{uploaded['file_id']}",
            headers=self.headers_2,
        )
        self.assertEqual(isolated.status_code, 404)
        self.assertEqual(isolated.json()["error"]["code"], "file_not_found")

        deleted = self.client.delete(
            f"/api/files/{uploaded['file_id']}",
            headers=self.headers_1,
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["deleted"])
        self.assertEqual(
            self.client.get(f"/api/files/{uploaded['file_id']}", headers=self.headers_1).status_code,
            404,
        )

    def test_chat_bridges_owned_image_to_existing_multimodal_format(self) -> None:
        uploaded = self.upload_png()
        captured: list[dict] = []

        def stream(**kwargs):
            captured.extend(kwargs["messages"])
            return iter([{"type": "text_delta", "text": "Draft ready"}])

        with patch("macsoft.gateway.routes_chat.stream_hermes_reply_events", side_effect=stream):
            response = self.client.post(
                "/api/chat/stream",
                headers={**self.headers_1, "X-MacSoft-Client-Capabilities": "activity-v1"},
                json={
                    "session_id": "session_1",
                    "message": "Extract this bank slip as a draft.",
                    "uploaded_file_ids": [uploaded["file_id"]],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("event: message_done", response.text)
        user_content = next(message["content"] for message in reversed(captured) if message["role"] == "user")
        self.assertIsInstance(user_content, list)
        self.assertEqual(user_content[0]["type"], "text")
        self.assertIn("bank-slip.png", user_content[0]["text"])
        self.assertTrue(user_content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_chat_emits_client_html_document_event_for_complete_html(self) -> None:
        html = "<!doctype html><html><body><h1>Debtor dashboard</h1></body></html>"

        with patch(
            "macsoft.gateway.routes_chat.stream_hermes_reply_events",
            return_value=iter([{"type": "text_delta", "text": html}]),
        ):
            response = self.client.post(
                "/api/chat/stream",
                headers={**self.headers_1, "X-MacSoft-Client-Capabilities": "activity-v1"},
                json={
                    "session_id": "session_1",
                    "message": "Give me a debtor dashboard with a chart.",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("event: message_start", response.text)
        self.assertIn("event: token_delta", response.text)
        self.assertIn("event: html_document", response.text)
        self.assertIn('"mime_type": "text/html"', response.text)
        self.assertIn('"document_id": "msg_assistant', response.text)
        self.assertIn("event: message_done", response.text)

    def test_unsupported_content_is_rejected_even_when_extension_is_allowed(self) -> None:
        response = self.client.post(
            "/api/files",
            headers=self.headers_1,
            files={"file": ("fake.png", b"not-an-image", "image/png")},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "unsupported_file_type")

    def test_csv_bank_statement_is_extracted_before_the_model_request(self) -> None:
        uploaded = self.client.post(
            "/api/files",
            headers=self.headers_1,
            files={"file": ("statement.csv", b"date,reference,amount\n2026-07-21,INV-1,125.50\n", "text/csv")},
        ).json()
        captured: list[dict] = []

        def stream(**kwargs):
            captured.extend(kwargs["messages"])
            return iter([{"type": "text_delta", "text": "Draft ready"}])

        with patch("macsoft.gateway.routes_chat.stream_hermes_reply_events", side_effect=stream):
            response = self.client.post(
                "/api/chat/stream",
                headers={**self.headers_1, "X-MacSoft-Client-Capabilities": "activity-v1"},
                json={
                    "session_id": "session_1",
                    "message": "Prepare a bank reconciliation draft.",
                    "uploaded_file_ids": [uploaded["file_id"]],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        user_content = next(message["content"] for message in reversed(captured) if message["role"] == "user")
        self.assertIsInstance(user_content, str)
        self.assertIn("BEGIN UNTRUSTED ATTACHMENT DATA: statement.csv", user_content)
        self.assertIn("INV-1\t125.50", user_content)

    def test_xlsx_bank_statement_is_extracted_deterministically(self) -> None:
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Bank"
        sheet.append(["Reference", "Amount"])
        sheet.append(["INV-2", 88.25])
        output = BytesIO()
        workbook.save(output)
        workbook.close()
        uploaded = self.client.post(
            "/api/files",
            headers=self.headers_1,
            files={
                "file": (
                    "statement.xlsx",
                    output.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        ).json()
        captured: list[dict] = []

        def stream(**kwargs):
            captured.extend(kwargs["messages"])
            return iter([{"type": "text_delta", "text": "Draft ready"}])

        with patch("macsoft.gateway.routes_chat.stream_hermes_reply_events", side_effect=stream):
            response = self.client.post(
                "/api/chat/stream",
                headers={**self.headers_1, "X-MacSoft-Client-Capabilities": "activity-v1"},
                json={
                    "session_id": "session_1",
                    "message": "Summarize this statement as a draft.",
                    "uploaded_file_ids": [uploaded["file_id"]],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        user_content = next(message["content"] for message in reversed(captured) if message["role"] == "user")
        self.assertIn("[Sheet: Bank]", user_content)
        self.assertIn("INV-2\t88.25", user_content)

    def test_image_only_pdf_is_not_silently_guessed(self) -> None:
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        output = BytesIO()
        writer.write(output)
        uploaded = self.client.post(
            "/api/files",
            headers=self.headers_1,
            files={"file": ("scan.pdf", output.getvalue(), "application/pdf")},
        ).json()
        response = self.client.post(
            "/api/chat/stream",
            headers={**self.headers_1, "X-MacSoft-Client-Capabilities": "activity-v1"},
            json={
                "session_id": "session_1",
                "message": "Read this scan.",
                "uploaded_file_ids": [uploaded["file_id"]],
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "scanned_pdf_requires_images")


if __name__ == "__main__":
    unittest.main()
