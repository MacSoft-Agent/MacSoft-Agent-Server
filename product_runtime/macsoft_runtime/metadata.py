from __future__ import annotations

import json
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
    build_date: str
    build_id: str
    data_schema_version: int
    protected_resource_version: int
    update_manifest_url: str | None


def _required_text(data: dict[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Product metadata field {name!r} must be non-empty text.")
    return value.strip()


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

    return ProductMetadata(
        product=_required_text(data, "product"),
        product_version=_required_text(data, "product_version"),
        channel=_required_text(data, "channel"),
        runtime_base_version=_required_text(data, "runtime_base_version"),
        runtime_base_commit=_required_text(data, "runtime_base_commit"),
        build_date=_required_text(data, "build_date"),
        build_id=_required_text(data, "build_id"),
        data_schema_version=int(data["data_schema_version"]),
        protected_resource_version=int(data["protected_resource_version"]),
        update_manifest_url=manifest_url,
    )
