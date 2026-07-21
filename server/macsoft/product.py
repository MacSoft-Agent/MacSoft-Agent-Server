from __future__ import annotations

import json
import os
from pathlib import Path


def product_version() -> str:
    configured = os.environ.get("MACSOFT_PRODUCT_METADATA")
    candidates = [Path(configured)] if configured else []
    candidates.extend(
        [
            Path(__file__).resolve().parents[2] / "product.json",
            Path(__file__).resolve().parents[1] / "product.json",
        ]
    )
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            value = data.get("product_version")
            if isinstance(value, str) and value.strip():
                return value.strip()
        except (OSError, ValueError, TypeError):
            continue
    return "unknown"
