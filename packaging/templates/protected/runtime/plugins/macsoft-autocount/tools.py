"""Profile-scoped AutoCount connection loading for optional workflow state tools."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_PLUGIN_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _PLUGIN_DIR / "config.json"


class AutoCountToolError(RuntimeError):
    """Raised when a workflow cannot resolve an AutoCount company connection."""


def _active_hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except ImportError:
        configured = os.environ.get("HERMES_HOME")
        return Path(configured) if configured else Path.home() / ".hermes"


def _connection_store_path() -> Path:
    return _active_hermes_home() / "autocount" / "connections.json"


def _read_connection_store() -> dict[str, Any]:
    path = _connection_store_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {"schemaVersion": 1, "defaultCompanyId": "", "connections": {}}
    except json.JSONDecodeError as exc:
        raise AutoCountToolError("AutoCount connection store is invalid JSON.") from exc
    if not isinstance(value, dict) or not isinstance(value.get("connections"), dict):
        raise AutoCountToolError("AutoCount connection store is invalid.")
    return value


def _validate_config(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise AutoCountToolError("AutoCount connection must be a JSON object.")
    required = ("baseUrl", "apiKey", "connectorId", "companyId")
    missing = [name for name in required if not str(config.get(name, "")).strip()]
    if missing:
        raise AutoCountToolError("AutoCount config is missing: " + ", ".join(missing))
    return dict(config)


def _load_config(company_id: str | None = None) -> dict[str, Any]:
    """Load one LLM-maintained profile connection, with legacy fallback."""
    selector = str(company_id or "").strip()
    store = _read_connection_store()
    connections = store.get("connections", {})
    selected = selector or str(store.get("defaultCompanyId", "")).strip()
    if selected and isinstance(connections.get(selected), dict):
        return _validate_config(connections[selected])
    if selector:
        raise AutoCountToolError(f"AutoCount company connection is not configured: {selector}")

    try:
        legacy = json.loads(_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise AutoCountToolError("AutoCount configuration is unavailable.") from exc
    except json.JSONDecodeError as exc:
        raise AutoCountToolError("AutoCount legacy config is invalid JSON.") from exc
    return _validate_config(legacy)
