"""Prepare inbound PDF documents before an agent turn starts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparedPdf:
    text: str
    image_paths: list[Path]


def prepare_pdf_for_agent(
    pdf_path: Path,
    *,
    max_text_bytes: int = 100 * 1024,
    max_pages: int = 10,
) -> PreparedPdf:
    """Extract a text PDF, or render a scanned PDF for vision routing."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    chunks: list[str] = []
    for page in reader.pages[:max_pages]:
        text = (page.extract_text() or "").strip()
        if text:
            chunks.append(text)

    extracted = "\n\n".join(chunks).strip()
    if extracted:
        encoded = extracted.encode("utf-8")
        if len(encoded) > max_text_bytes:
            extracted = encoded[:max_text_bytes].decode("utf-8", errors="ignore")
        return PreparedPdf(text=extracted, image_paths=[])

    import pymupdf

    rendered: list[Path] = []
    with pymupdf.open(str(pdf_path)) as document:
        for index, page in enumerate(document[:max_pages], start=1):
            output = pdf_path.with_name(f"{pdf_path.stem}_page_{index}.png")
            page.get_pixmap(dpi=150, alpha=False).save(str(output))
            rendered.append(output)
    return PreparedPdf(text="", image_paths=rendered)
