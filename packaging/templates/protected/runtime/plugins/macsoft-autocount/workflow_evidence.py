"""Trusted workflow-evidence archival for native Gateway attachments."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

from . import workflow_store


MAX_EVIDENCE_BYTES = 20 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/csv",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _trusted_media() -> list[dict[str, str]]:
    try:
        from gateway.session_context import get_session_env

        raw = get_session_env("MACSOFT_SESSION_MEDIA_JSON", "")
        value = json.loads(raw or "[]")
    except (ImportError, TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _selected_source(source_path: str) -> tuple[Path, str]:
    try:
        requested = Path(source_path).expanduser().resolve(strict=True)
    except OSError as exc:
        raise workflow_store.WorkflowStoreError(
            "The trusted workflow attachment is no longer available."
        ) from exc
    for item in _trusted_media():
        candidate_raw = str(item.get("path") or "").strip()
        if not candidate_raw:
            continue
        try:
            candidate = Path(candidate_raw).expanduser().resolve(strict=True)
        except OSError:
            continue
        if candidate == requested:
            media_type = str(item.get("media_type") or "").split(";", 1)[0].strip().lower()
            if media_type not in ALLOWED_MEDIA_TYPES:
                raise workflow_store.WorkflowStoreError(
                    "The trusted attachment media type is not supported as workflow evidence."
                )
            return candidate, media_type
    raise workflow_store.WorkflowStoreError(
        "The evidence path is not part of the trusted current Gateway message."
    )


def _root(config: dict[str, Any]) -> Path:
    configured = str(config.get("workflowEvidenceRoot") or "").strip()
    if configured:
        root = Path(configured).expanduser().resolve()
    else:
        hermes_home = os.getenv("HERMES_HOME", "").strip()
        if not hermes_home:
            raise workflow_store.WorkflowConfigurationError(
                "workflowEvidenceRoot or HERMES_HOME is required for evidence archival."
            )
        root = (Path(hermes_home).expanduser().resolve() / "workflow" / "evidence")
    root.mkdir(parents=True, exist_ok=True)
    return root


def archive_current_media(config: dict[str, Any], *, source_path: str) -> dict[str, Any]:
    source, media_type = _selected_source(source_path)
    size = source.stat().st_size
    if size < 1 or size > MAX_EVIDENCE_BYTES:
        raise workflow_store.WorkflowStoreError("Workflow evidence must be between 1 byte and 20 MiB.")
    evidence_id = f"evidence_{uuid.uuid4().hex}"
    suffix = source.suffix.lower()[:16]
    target = _root(config) / f"{evidence_id}{suffix}"
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    digest = hashlib.sha256()
    written = 0
    try:
        with source.open("rb") as input_file, temporary.open("xb") as output_file:
            while True:
                block = input_file.read(1024 * 1024)
                if not block:
                    break
                written += len(block)
                if written > MAX_EVIDENCE_BYTES:
                    raise workflow_store.WorkflowStoreError("Workflow evidence exceeds 20 MiB.")
                digest.update(block)
                output_file.write(block)
            output_file.flush()
            os.fsync(output_file.fileno())
        if written != size:
            raise workflow_store.WorkflowStoreError("Workflow evidence changed while it was archived.")
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise
    return {
        "evidence_id": evidence_id,
        "sha256": digest.hexdigest(),
        "size_bytes": written,
        "media_type": media_type,
        "original_filename": source.name,
        "stored_path": str(target),
    }


def trusted_media_source_key(*, message_id: str, source_path: str) -> str:
    """Build a channel-neutral idempotency key from trusted message and bytes."""
    source, _ = _selected_source(source_path)
    if not message_id:
        raise workflow_store.WorkflowStoreError("A trusted source message ID is required.")
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as input_file:
        while True:
            block = input_file.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            if size > MAX_EVIDENCE_BYTES:
                raise workflow_store.WorkflowStoreError("Workflow evidence exceeds 20 MiB.")
            digest.update(block)
    return f"{message_id}:{digest.hexdigest()}"
