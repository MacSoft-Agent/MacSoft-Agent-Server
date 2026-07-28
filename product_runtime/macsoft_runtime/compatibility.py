from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .metadata import ProductMetadata
from .paths import ProductPaths


RUNTIME_DECLARATION_FILENAME = "macsoft-runtime.json"
RUNTIME_NAME = "hermes-agent"
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_DECLARATION_KEYS = {
    "runtime",
    "runtime_base_version",
    "runtime_base_commit",
    "runtime_contract_version",
    "runtime_metadata_schema_version",
}


class RuntimeCompatibilityError(RuntimeError):
    pass


def expected_runtime_metadata(metadata: ProductMetadata) -> dict[str, Any]:
    return {
        "runtime": RUNTIME_NAME,
        "runtime_base_version": metadata.runtime_base_version,
        "runtime_base_commit": metadata.runtime_base_commit,
        "runtime_contract_version": metadata.runtime_contract_version,
        "runtime_metadata_schema_version": metadata.runtime_metadata_schema_version,
    }


def _normalize_runtime_metadata(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Runtime declaration must contain a JSON object.")
    if set(value) != _DECLARATION_KEYS:
        raise ValueError("Runtime declaration fields do not match the supported metadata schema.")

    normalized: dict[str, Any] = {}
    for name in ("runtime", "runtime_base_version", "runtime_base_commit"):
        item = value.get(name)
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Runtime declaration field {name!r} must be non-empty text.")
        normalized[name] = item.strip()
    for name in ("runtime_contract_version", "runtime_metadata_schema_version"):
        item = value.get(name)
        if not isinstance(item, int) or isinstance(item, bool) or item < 1:
            raise ValueError(f"Runtime declaration field {name!r} must be a positive integer.")
        normalized[name] = item

    if normalized["runtime"] != RUNTIME_NAME:
        raise ValueError("Runtime declaration identifies an unsupported runtime.")
    if not _COMMIT_PATTERN.fullmatch(normalized["runtime_base_commit"]):
        raise ValueError("Runtime declaration commit must be a 40-character lowercase Git SHA.")
    return normalized


def load_runtime_metadata(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as file:
            value = json.load(file)
    except FileNotFoundError as error:
        raise ValueError("Hermes runtime declaration is missing.") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Hermes runtime declaration cannot be read as valid JSON.") from error
    return _normalize_runtime_metadata(value)


def _comparison_result(
    *,
    phase: str,
    expected: dict[str, Any],
    detected: dict[str, Any] | None,
    error_code: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    mismatches = [
        name
        for name in sorted(_DECLARATION_KEYS)
        if detected is not None and detected.get(name) != expected.get(name)
    ]
    accepted = detected is not None and not mismatches and error_code is None
    return {
        "status": "accepted" if accepted else "rejected",
        "phase": phase,
        "expected": expected,
        "detected": detected,
        "mismatched_fields": mismatches,
        "error_code": error_code,
        "message": message,
    }


def assess_pre_start_compatibility(
    paths: ProductPaths,
    metadata: ProductMetadata,
) -> dict[str, Any]:
    expected = expected_runtime_metadata(metadata)
    declaration = paths.ai_program_root / RUNTIME_DECLARATION_FILENAME
    try:
        detected = load_runtime_metadata(declaration)
    except ValueError as error:
        return _comparison_result(
            phase="pre_start",
            expected=expected,
            detected=None,
            error_code="runtime_declaration_invalid",
            message=str(error),
        )
    result = _comparison_result(phase="pre_start", expected=expected, detected=detected)
    if result["status"] != "accepted":
        result["error_code"] = "runtime_metadata_mismatch"
        result["message"] = "Hermes runtime metadata does not match this MacSoft Agent build."
    return result


def assess_live_compatibility(
    expected: dict[str, Any],
    health_body: object,
) -> dict[str, Any]:
    runtime_value = health_body.get("macsoft_runtime") if isinstance(health_body, dict) else None
    try:
        detected = _normalize_runtime_metadata(runtime_value)
    except ValueError as error:
        return _comparison_result(
            phase="post_start",
            expected=expected,
            detected=None,
            error_code="runtime_health_metadata_invalid",
            message=str(error),
        )
    result = _comparison_result(phase="post_start", expected=expected, detected=detected)
    if result["status"] != "accepted":
        result["error_code"] = "runtime_health_metadata_mismatch"
        result["message"] = "Running Hermes metadata does not match this MacSoft Agent build."
    return result


def compatibility_error_message(result: dict[str, Any]) -> str:
    message = result.get("message")
    mismatches = result.get("mismatched_fields")
    if isinstance(mismatches, list) and mismatches:
        suffix = ", ".join(str(name) for name in mismatches)
        return f"Hermes runtime compatibility check failed: {message} Fields: {suffix}."
    if isinstance(message, str) and message:
        return f"Hermes runtime compatibility check failed: {message}"
    return "Hermes runtime compatibility check failed."
