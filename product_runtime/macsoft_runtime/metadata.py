from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProductMetadata:
    product: str
    product_version: str
    channel: str
    runtime_base_version: str
    runtime_base_commit: str
    runtime_contract_version: int
    runtime_metadata_schema_version: int
    build_date: str
    build_id: str
    data_schema_version: int
    protected_resource_version: int
    update_manifest_url: str | None
    update_manifest_public_key: str | None


def _required_text(data: dict[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Product metadata field {name!r} must be non-empty text.")
    return value.strip()


def _required_positive_int(data: dict[str, Any], name: str) -> int:
    value = data.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"Product metadata field {name!r} must be a positive integer.")
    return value


def load_product_metadata(program_root: Path | str) -> ProductMetadata:
    path = Path(program_root).resolve() / "product.json"
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("product.json must contain an object.")

    manifest_url = data.get("update_manifest_url")
    if manifest_url is not None:
        if not isinstance(manifest_url, str) or not manifest_url.startswith("https://"):
            raise ValueError("update_manifest_url must be null or an HTTPS URL.")
        manifest_url = manifest_url.strip()

    manifest_public_key = data.get("update_manifest_public_key")
    if manifest_public_key is not None:
        if not isinstance(manifest_public_key, str) or not manifest_public_key.strip():
            raise ValueError(
                "update_manifest_public_key must be null or a non-empty base64 SPKI public key."
            )
        manifest_public_key = manifest_public_key.strip()

    runtime_base_commit = _required_text(data, "runtime_base_commit")
    if not re.fullmatch(r"[0-9a-f]{40}", runtime_base_commit):
        raise ValueError("runtime_base_commit must be a 40-character lowercase Git SHA.")

    return ProductMetadata(
        product=_required_text(data, "product"),
        product_version=_required_text(data, "product_version"),
        channel=_required_text(data, "channel"),
        runtime_base_version=_required_text(data, "runtime_base_version"),
        runtime_base_commit=runtime_base_commit,
        runtime_contract_version=_required_positive_int(data, "runtime_contract_version"),
        runtime_metadata_schema_version=_required_positive_int(
            data,
            "runtime_metadata_schema_version",
        ),
        build_date=_required_text(data, "build_date"),
        build_id=_required_text(data, "build_id"),
        data_schema_version=int(data["data_schema_version"]),
        protected_resource_version=int(data["protected_resource_version"]),
        update_manifest_url=manifest_url,
        update_manifest_public_key=manifest_public_key,
    )
