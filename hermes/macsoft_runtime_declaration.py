from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DECLARATION_PATH = Path(__file__).resolve().with_name("macsoft-runtime.json")
_DECLARATION_KEYS = {
    "runtime",
    "runtime_base_version",
    "runtime_base_commit",
    "runtime_contract_version",
    "runtime_metadata_schema_version",
}


def load_macsoft_runtime_declaration() -> dict[str, Any]:
    with DECLARATION_PATH.open("r", encoding="utf-8-sig") as file:
        value = json.load(file)
    if not isinstance(value, dict) or set(value) != _DECLARATION_KEYS:
        raise ValueError("Unsupported MacSoft runtime declaration.")
    if value.get("runtime") != "hermes-agent":
        raise ValueError("Unsupported MacSoft runtime identity.")
    for name in ("runtime_base_version", "runtime_base_commit"):
        item = value.get(name)
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Invalid MacSoft runtime field: {name}.")
    if not re.fullmatch(r"[0-9a-f]{40}", value["runtime_base_commit"]):
        raise ValueError("Invalid MacSoft runtime commit.")
    for name in ("runtime_contract_version", "runtime_metadata_schema_version"):
        item = value.get(name)
        if not isinstance(item, int) or isinstance(item, bool) or item < 1:
            raise ValueError(f"Invalid MacSoft runtime field: {name}.")
    return value
