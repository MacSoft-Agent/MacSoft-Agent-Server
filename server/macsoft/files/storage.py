from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path

from macsoft.config import AppConfig
from macsoft.db import resolve_db_path
from macsoft.security import new_id, utc_now_iso


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_MESSAGE = 5
MAX_TOTAL_MESSAGE_BYTES = 25 * 1024 * 1024
MAX_XLSX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "text/csv": ".csv",
    "text/plain": ".txt",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


class UploadValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class UploadedFileRecord:
    file_id: str
    owner_user_id: str
    owner_device_id: str
    original_name: str
    stored_name: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "UploadedFileRecord":
        return cls(
            file_id=str(row["file_id"]),
            owner_user_id=str(row["owner_user_id"]),
            owner_device_id=str(row["owner_device_id"]),
            original_name=str(row["original_name"]),
            stored_name=str(row["stored_name"]),
            media_type=str(row["media_type"]),
            size_bytes=int(row["size_bytes"]),
            sha256=str(row["sha256"]),
            created_at=str(row["created_at"]),
        )


def upload_root(config: AppConfig) -> Path:
    root = resolve_db_path(config).parent / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def stored_path(config: AppConfig, record: UploadedFileRecord) -> Path:
    return upload_root(config) / record.stored_name


def _clean_filename(filename: str | None) -> str:
    name = Path(str(filename or "").replace("\\", "/")).name.strip()
    name = _CONTROL_CHARACTERS.sub("", name)
    if not name:
        name = "upload"
    return name[:255]


def _looks_like_text(data: bytes) -> bool:
    if not data or b"\x00" in data[:4096]:
        return False
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            data.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False


def _is_xlsx(data: bytes) -> bool:
    from io import BytesIO

    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            total_uncompressed = sum(item.file_size for item in archive.infolist())
            return (
                total_uncompressed <= MAX_XLSX_UNCOMPRESSED_BYTES
                and "[Content_Types].xml" in names
                and "xl/workbook.xml" in names
            )
    except (OSError, zipfile.BadZipFile):
        return False


def detect_media_type(data: bytes, filename: str) -> str:
    lowered_name = filename.lower()
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if lowered_name.endswith(".xlsx") and _is_xlsx(data):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if lowered_name.endswith(".csv") and _looks_like_text(data):
        return "text/csv"
    if lowered_name.endswith(".txt") and _looks_like_text(data):
        return "text/plain"
    raise UploadValidationError(
        "unsupported_file_type",
        "Supported files are JPG, PNG, WebP, PDF, CSV, XLSX, and TXT.",
    )


def validate_upload(data: bytes, filename: str | None) -> tuple[str, str]:
    if not data:
        raise UploadValidationError("empty_file", "The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadValidationError(
            "file_too_large",
            f"The uploaded file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )
    clean_name = _clean_filename(filename)
    return clean_name, detect_media_type(data, clean_name)


def create_uploaded_file(
    conn: sqlite3.Connection,
    config: AppConfig,
    *,
    owner_user_id: str,
    owner_device_id: str,
    filename: str | None,
    data: bytes,
) -> UploadedFileRecord:
    original_name, media_type = validate_upload(data, filename)
    file_id = new_id("file")
    stored_name = f"{file_id}{_EXTENSIONS[media_type]}"
    target = upload_root(config) / stored_name
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    digest = hashlib.sha256(data).hexdigest()
    created_at = utc_now_iso()

    try:
        with temporary.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
        conn.execute(
            """
            INSERT INTO uploaded_files (
                file_id, owner_user_id, owner_device_id, original_name,
                stored_name, media_type, size_bytes, sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                owner_user_id,
                owner_device_id,
                original_name,
                stored_name,
                media_type,
                len(data),
                digest,
                created_at,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        target.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
        raise

    return UploadedFileRecord(
        file_id=file_id,
        owner_user_id=owner_user_id,
        owner_device_id=owner_device_id,
        original_name=original_name,
        stored_name=stored_name,
        media_type=media_type,
        size_bytes=len(data),
        sha256=digest,
        created_at=created_at,
    )


def require_owned_file(
    conn: sqlite3.Connection,
    *,
    file_id: str,
    owner_user_id: str,
    owner_device_id: str,
) -> UploadedFileRecord:
    row = conn.execute(
        """
        SELECT * FROM uploaded_files
        WHERE file_id = ? AND owner_user_id = ? AND owner_device_id = ?
        """,
        (file_id, owner_user_id, owner_device_id),
    ).fetchone()
    if row is None:
        raise ValueError("Uploaded file was not found for this device.")
    return UploadedFileRecord.from_row(row)


def require_owned_files(
    conn: sqlite3.Connection,
    *,
    file_ids: list[str],
    owner_user_id: str,
    owner_device_id: str,
) -> list[UploadedFileRecord]:
    normalized = [str(file_id).strip() for file_id in file_ids]
    if any(not file_id for file_id in normalized) or len(set(normalized)) != len(normalized):
        raise UploadValidationError("invalid_file_ids", "Uploaded file IDs must be non-empty and unique.")
    if len(normalized) > MAX_FILES_PER_MESSAGE:
        raise UploadValidationError(
            "too_many_files",
            f"A message can include at most {MAX_FILES_PER_MESSAGE} uploaded files.",
        )
    records = [
        require_owned_file(
            conn,
            file_id=file_id,
            owner_user_id=owner_user_id,
            owner_device_id=owner_device_id,
        )
        for file_id in normalized
    ]
    if sum(record.size_bytes for record in records) > MAX_TOTAL_MESSAGE_BYTES:
        raise UploadValidationError(
            "attachments_too_large",
            f"The combined files exceed the {MAX_TOTAL_MESSAGE_BYTES // (1024 * 1024)} MB message limit.",
        )
    return records


def delete_owned_file(
    conn: sqlite3.Connection,
    config: AppConfig,
    *,
    file_id: str,
    owner_user_id: str,
    owner_device_id: str,
) -> UploadedFileRecord:
    record = require_owned_file(
        conn,
        file_id=file_id,
        owner_user_id=owner_user_id,
        owner_device_id=owner_device_id,
    )
    stored_path(config, record).unlink(missing_ok=True)
    conn.execute(
        "DELETE FROM uploaded_files WHERE file_id = ? AND owner_device_id = ?",
        (file_id, owner_device_id),
    )
    conn.commit()
    return record
