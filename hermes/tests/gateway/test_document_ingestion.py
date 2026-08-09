from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from pypdf import PdfWriter

from gateway.document_ingestion import prepare_pdf_for_agent
from gateway.config import Platform, PlatformConfig
from plugins.platforms.whatsapp.adapter import WhatsAppAdapter


def _write_text_pdf(path: Path) -> None:
    # A minimal, hand-authored PDF whose visible text is independent of the
    # production extraction implementation.
    content = b"BT /F1 12 Tf 72 720 Td (Supplier invoice CPS-2608-337) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode())
        data.extend(obj)
        data.extend(b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.write_bytes(data)


def test_text_pdf_is_extracted_before_the_agent_runs(tmp_path):
    pdf = tmp_path / "supplier_invoice.pdf"
    _write_text_pdf(pdf)

    prepared = prepare_pdf_for_agent(pdf)

    assert "Supplier invoice CPS-2608-337" in prepared.text
    assert prepared.image_paths == []


def test_scanned_pdf_is_rendered_as_images_for_existing_vision_routing(tmp_path):
    pdf = tmp_path / "scanned_invoice.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with pdf.open("wb") as stream:
        writer.write(stream)

    prepared = prepare_pdf_for_agent(pdf)

    assert prepared.text == ""
    assert len(prepared.image_paths) == 1
    assert prepared.image_paths[0].suffix == ".png"
    assert prepared.image_paths[0].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_whatsapp_adapter_injects_pdf_text_and_marks_it_preprocessed(tmp_path, monkeypatch):
    pdf = tmp_path / "supplier_invoice.pdf"
    _write_text_pdf(pdf)
    monkeypatch.setattr(
        "plugins.platforms.whatsapp.adapter._is_allowed_bridge_path",
        lambda _path: True,
    )
    adapter = WhatsAppAdapter.__new__(WhatsAppAdapter)
    adapter.platform = Platform.WHATSAPP
    adapter.config = PlatformConfig(enabled=True)
    adapter._message_handler = AsyncMock()
    adapter._dm_policy = "allowlist"
    adapter._allow_from = {"60123456789"}
    adapter._group_policy = "disabled"
    adapter._group_allow_from = set()
    adapter._mention_patterns = []
    adapter._free_response_chats = set()
    adapter._whatsapp_free_response_chats = lambda: set()
    payload = {
        "messageId": "M1",
        "chatId": "60123456789@s.whatsapp.net",
        "senderId": "60123456789@s.whatsapp.net",
        "senderName": "Accountant",
        "isGroup": False,
        "body": "process this invoice",
        "hasMedia": True,
        "mediaType": "document",
        "mime": "application/pdf",
        "mediaUrls": [str(pdf)],
    }

    event = asyncio.run(adapter._build_message_event(payload))

    assert event is not None
    assert "Supplier invoice CPS-2608-337" in event.text
    assert event.metadata["document_text_extracted_paths"] == [str(pdf)]
