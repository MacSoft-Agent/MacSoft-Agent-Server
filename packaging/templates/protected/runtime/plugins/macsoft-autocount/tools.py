"""Generic AutoCount Cloud tool handlers.

There is intentionally no command-specific Python implementation here.
Every official AutoCount command is discovered and executed dynamically.
"""

from __future__ import annotations

import json
import hashlib
import difflib
import os
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MIN_REQUEST_TIMEOUT_SECONDS = 120

from .validator import validate_command_payload


_PLUGIN_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _PLUGIN_DIR / "config.json"
_FINAL_STATUSES = {"done", "failed", "cancelled", "canceled", "error"}
_TRANSIENT_HTTP_STATUSES = {429, 502, 503, 504}
_INVALID_FINGERPRINT_LIMIT = 256
_invalid_fingerprints: deque[str] = deque()
_invalid_fingerprint_set: set[str] = set()
_invalid_fingerprint_lock = threading.Lock()
_connection_store_lock = threading.Lock()


class AutoCountToolError(RuntimeError):
    """Raised for HTTP, configuration, or response-contract failures."""


class AutoCountCommandResolutionError(AutoCountToolError):
    """Raised when a requested command is not an exact catalog entry."""

    def __init__(self, command_type: str, suggestions: list[str]) -> None:
        super().__init__(
            f"Command type '{command_type}' is not an exact current official catalog command."
        )
        self.suggestions = suggestions


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _active_hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except ImportError:
        configured = os.environ.get("HERMES_HOME")
        return Path(configured) if configured else Path.home() / ".hermes"


def _is_admin_workspace() -> bool:
    configured = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    try:
        return _active_hermes_home().resolve() == (configured / "admin").resolve()
    except OSError:
        return False


def _connection_store_path() -> Path:
    return _active_hermes_home() / "autocount" / "connections.json"


def _empty_connection_store() -> dict[str, Any]:
    return {"schemaVersion": 1, "defaultCompanyId": "", "connections": {}}


def _read_connection_store() -> dict[str, Any]:
    path = _connection_store_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return _empty_connection_store()
    except json.JSONDecodeError as exc:
        raise AutoCountToolError("AutoCount connection store is invalid JSON.") from exc
    if not isinstance(value, dict) or not isinstance(value.get("connections"), dict):
        raise AutoCountToolError("AutoCount connection store is invalid.")
    return value


def _write_connection_store(value: dict[str, Any]) -> None:
    path = _connection_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(path)


def _public_connections(store: dict[str, Any]) -> dict[str, Any]:
    connections = []
    for company_id, item in sorted(store.get("connections", {}).items()):
        if not isinstance(item, dict):
            continue
        connections.append(
            {
                "companyId": company_id,
                "name": str(item.get("name", "")),
                "baseUrl": str(item.get("baseUrl", "")),
                "connectorId": str(item.get("connectorId", "")),
                "apiKeyConfigured": bool(str(item.get("apiKey", "")).strip()),
            }
        )
    return {
        "defaultCompanyId": str(store.get("defaultCompanyId", "")),
        "connections": connections,
    }


def _validate_cloud_url(value: str) -> str:
    normalized = value.rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or parsed.hostname != "api.autocount.cloud" or parsed.query or parsed.fragment:
        raise AutoCountToolError("base_url must be https://api.autocount.cloud.")
    return normalized


def _load_config(company_id: str | None = None) -> dict[str, Any]:
    selector = str(company_id or "").strip()
    store = _read_connection_store()
    stored_connections = store.get("connections", {})
    selected_company = selector or str(store.get("defaultCompanyId", "")).strip()
    if selected_company and isinstance(stored_connections.get(selected_company), dict):
        return dict(stored_connections[selected_company])
    if selector:
        raise AutoCountToolError(f"AutoCount company connection is not configured: {selector}")

    try:
        with _CONFIG_PATH.open("r", encoding="utf-8-sig") as file:
            config = json.load(file)
    except FileNotFoundError as exc:
        raise AutoCountToolError(f"AutoCount config not found: {_CONFIG_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise AutoCountToolError(f"AutoCount config is invalid JSON: {exc}") from exc

    required = ("baseUrl", "apiKey", "connectorId", "companyId")
    missing = [name for name in required if not str(config.get(name, "")).strip()]
    if missing:
        raise AutoCountToolError(
            "AutoCount config is missing: " + ", ".join(missing)
        )

    return config


def autocount_manage_connections(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        if not _is_admin_workspace():
            raise AutoCountToolError("Only the Server administrator can manage AutoCount connections.")
        action = str(params.get("action", "list")).strip().lower()
        company_id = str(params.get("company_id", "")).strip()
        if action == "test":
            config = _load_config(company_id or None)
            connector_id = quote(str(config["connectorId"]), safe="")
            response = _request_json("GET", f"/v1/connectors/{connector_id}/status", config=config)
            return _success(response, companyId=str(config["companyId"]))
        with _connection_store_lock:
            store = _read_connection_store()
            connections = store["connections"]

            if action == "list":
                return _success(_public_connections(store))
            if action == "save":
                connector_id = str(params.get("connector_id", "")).strip()
                if not company_id or not connector_id:
                    raise AutoCountToolError("company_id and connector_id are required.")
                existing = connections.get(company_id, {})
                api_key = str(params.get("api_key", "")).strip() or str(existing.get("apiKey", "")).strip()
                if not api_key:
                    raise AutoCountToolError("api_key is required for a new connection.")
                connections[company_id] = {
                    "name": str(params.get("name", existing.get("name", ""))).strip(),
                    "baseUrl": _validate_cloud_url(str(params.get("base_url", existing.get("baseUrl", "https://api.autocount.cloud"))).strip()),
                    "apiKey": api_key,
                    "connectorId": connector_id,
                    "companyId": company_id,
                    "requestTimeoutSeconds": max(120, min(int(params.get("request_timeout_seconds", existing.get("requestTimeoutSeconds", 120))), 7200)),
                    "commandTimeoutSeconds": max(5, min(int(params.get("command_timeout_seconds", existing.get("commandTimeoutSeconds", 7200))), 7200)),
                    "pollIntervalSeconds": max(0.5, min(float(existing.get("pollIntervalSeconds", 2)), 10.0)),
                }
                if bool(params.get("set_default")) or not str(store.get("defaultCompanyId", "")):
                    store["defaultCompanyId"] = company_id
                _write_connection_store(store)
                return _success({"saved": True, "companyId": company_id, "default": store["defaultCompanyId"] == company_id})
            if action == "set_default":
                if company_id not in connections:
                    raise AutoCountToolError(f"AutoCount company connection is not configured: {company_id}")
                store["defaultCompanyId"] = company_id
                _write_connection_store(store)
                return _success({"defaultCompanyId": company_id})
            if action == "remove":
                if company_id not in connections:
                    raise AutoCountToolError(f"AutoCount company connection is not configured: {company_id}")
                del connections[company_id]
                if store.get("defaultCompanyId") == company_id:
                    store["defaultCompanyId"] = sorted(connections)[0] if connections else ""
                _write_connection_store(store)
                return _success({"removed": True, "companyId": company_id})
            raise AutoCountToolError("action must be list, save, set_default, remove, or test.")
    except Exception as exc:
        return _failure(exc)


def _request_json(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout_seconds: int | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or _load_config()
    base_url = str(config["baseUrl"]).rstrip("/")
    url = f"{base_url}{path}"
    timeout = max(
        MIN_REQUEST_TIMEOUT_SECONDS,
        int(
            timeout_seconds
            if timeout_seconds is not None
            else config.get("requestTimeoutSeconds", MIN_REQUEST_TIMEOUT_SECONDS)
        ),
    )

    headers = {
        "Authorization": f"Bearer {config['apiKey']}",
        "Accept": "application/json",
        "User-Agent": "MacSoft-Agent-AutoCount/0.1.0",
    }

    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        url=url,
        data=data,
        headers=headers,
        method=method.upper(),
    )

    normalized_method = method.upper()
    max_attempts = 2 if normalized_method == "GET" else 1
    for attempt in range(max_attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
            break
        except HTTPError as exc:
            if exc.code in _TRANSIENT_HTTP_STATUSES and attempt + 1 < max_attempts:
                time.sleep(0.1)
                continue
            print(
                "[MACSOFT_AUTOCOUNT] HTTP request failed. "
                f"status={exc.code} method={normalized_method} path={path}"
            )
            raise AutoCountToolError(
                f"AutoCount API HTTP {exc.code}. The service rejected the request."
            ) from exc
        except URLError as exc:
            if attempt + 1 < max_attempts:
                time.sleep(0.1)
                continue
            raise AutoCountToolError("Cannot connect to AutoCount Cloud.") from exc
        except TimeoutError as exc:
            if attempt + 1 < max_attempts:
                time.sleep(0.1)
                continue
            raise AutoCountToolError("AutoCount API timed out.") from exc

    if not raw.strip():
        return {}

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AutoCountToolError(
            f"AutoCount API returned invalid JSON for {method.upper()} {path}."
        ) from exc

    if not isinstance(result, dict):
        raise AutoCountToolError(
            f"AutoCount API returned a non-object response for "
            f"{method.upper()} {path}."
        )

    return result


def _success(data: Any, **extra: Any) -> str:
    result = {"ok": True, "data": data}
    result.update(extra)
    return _json_text(result)


def _safe_failure_message(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    lowered = message.lower()
    if isinstance(exc, AutoCountCommandResolutionError):
        return message
    if "config not found" in lowered:
        return "AutoCount configuration is unavailable."
    if "config is invalid json" in lowered:
        return "AutoCount configuration is invalid."
    if "config is missing" in lowered:
        return message
    if "company connection is not configured" in lowered:
        return message
    if re.search(r"\bhttp 401\b", lowered):
        return "AutoCount API HTTP 401. Authentication failed."
    if re.search(r"\bhttp \d{3}\b", lowered):
        return message
    if "connector is offline" in lowered:
        return "AutoCount connector is offline. Command was not queued."
    if "only the server administrator" in lowered:
        return message
    if "timed out" in lowered or "cannot connect to autocount cloud" in lowered:
        return message
    if lowered.endswith("is required.") or "must be a json object" in lowered:
        return message
    return "The AutoCount request could not be completed."


def _failure(exc: Exception, **extra: Any) -> str:
    result = {
        "ok": False,
        "error": {
            "type": exc.__class__.__name__,
            "message": _safe_failure_message(exc),
        },
    }
    result.update(extra)
    return _json_text(result)


def _command_status(response: dict[str, Any]) -> str:
    candidates: list[Any] = [
        response.get("status"),
        response.get("commandStatus"),
    ]

    for container_name in ("command", "data", "result"):
        container = response.get(container_name)
        if isinstance(container, dict):
            candidates.extend(
                [
                    container.get("status"),
                    container.get("commandStatus"),
                ]
            )

    for value in candidates:
        if value is not None:
            return str(value).strip().lower()

    return ""


def _normalize_words(value: str) -> list[str]:
    return [
        word
        for word in re.split(r"[^a-z0-9]+", value.lower())
        if word
    ]


def _catalog_entries(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    modules = catalog.get("modules")
    if isinstance(modules, list):
        for module in modules:
            if not isinstance(module, dict):
                continue
            commands = module.get("commands")
            if not isinstance(commands, list):
                continue
            for command in commands:
                if isinstance(command, dict):
                    entries.append(command)

    dictionary = catalog.get("dictionary")
    if isinstance(dictionary, dict):
        commands = dictionary.get("commands")
        if isinstance(commands, dict):
            commands = list(commands.values())
        if isinstance(commands, list):
            for command in commands:
                if isinstance(command, str):
                    entries.append({"type": command})
                elif isinstance(command, dict):
                    entries.append(command)

    unique: dict[str, dict[str, Any]] = {}
    for entry in entries:
        command_type = str(entry.get("type") or entry.get("commandType") or "")
        if command_type and command_type not in unique:
            unique[command_type] = entry
    return list(unique.values())


def _resolve_exact_command(command_type: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = _request_json("GET", "/v1/schema/modules", config=config)
    entries = _catalog_entries(catalog)
    by_type = {
        str(entry.get("type") or entry.get("commandType") or ""): entry
        for entry in entries
    }
    exact = by_type.get(command_type)
    if exact is not None:
        return exact
    suggestions = difflib.get_close_matches(
        command_type,
        [item for item in by_type if item],
        n=5,
        cutoff=0.45,
    )
    raise AutoCountCommandResolutionError(command_type, suggestions)


def _load_exact_command_schema(
    command_type: str,
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    command = _resolve_exact_command(command_type, config)
    encoded = quote(command_type, safe="")
    schema = _request_json("GET", f"/v1/schema/commands/{encoded}", config=config)
    return command, schema


def _mark_invalid_payload(
    command_type: str,
    payload: dict[str, Any],
    validation: dict[str, Any],
    context: dict[str, str],
) -> bool:
    canonical = _json_text(
        {
            "command_type": command_type,
            "context": context,
            "payload": payload,
            "validation": validation,
        }
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with _invalid_fingerprint_lock:
        if fingerprint in _invalid_fingerprint_set:
            return True
        if len(_invalid_fingerprints) >= _INVALID_FINGERPRINT_LIMIT:
            oldest = _invalid_fingerprints.popleft()
            _invalid_fingerprint_set.discard(oldest)
        _invalid_fingerprints.append(fingerprint)
        _invalid_fingerprint_set.add(fingerprint)
    return False


def autocount_get_connector_status(
    params: dict[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    del kwargs

    try:
        config = _load_config(str((params or {}).get("company_id", "")).strip() or None)
        connector_id = quote(str(config["connectorId"]), safe="")
        response = _request_json(
            "GET",
            f"/v1/connectors/{connector_id}/status",
            config=config,
        )
        return _success(response)
    except Exception as exc:
        return _failure(exc)


def autocount_search_commands(
    params: dict[str, Any],
    **kwargs: Any,
) -> str:
    del kwargs

    try:
        company_id = str(params.get("company_id", "")).strip()
        config = _load_config(company_id) if company_id else None
        query = str(params.get("query", "")).strip()
        module_filter = str(params.get("module_id", "")).strip().lower()
        mode_filter = str(params.get("mode", "")).strip().lower()
        limit = max(1, min(int(params.get("limit", 20)), 50))

        if not query:
            raise AutoCountToolError("query is required.")

        query_words = _normalize_words(query)
        catalog = _request_json("GET", "/v1/schema/modules", config=config)
        modules = catalog.get("modules", [])

        if not isinstance(modules, list):
            raise AutoCountToolError(
                "AutoCount schema response does not contain a modules array."
            )

        matches: list[dict[str, Any]] = []

        for module in modules:
            if not isinstance(module, dict):
                continue

            module_id = str(module.get("id", ""))
            module_label = str(module.get("label", ""))
            if module_filter and module_filter not in {
                module_id.lower(),
                module_label.lower(),
            }:
                continue

            commands = module.get("commands", [])
            if not isinstance(commands, list):
                continue

            for command in commands:
                if not isinstance(command, dict):
                    continue

                command_type = str(command.get("type", ""))
                summary = str(command.get("summary", ""))
                mode = str(command.get("mode", ""))

                if mode_filter and mode_filter not in mode.lower():
                    continue

                searchable = " ".join(
                    [
                        command_type,
                        summary,
                        mode,
                        module_id,
                        module_label,
                    ]
                ).lower()

                score = 0
                if query.lower() == command_type.lower():
                    score += 100

                for word in query_words:
                    if word in command_type.lower():
                        score += 8
                    if word in summary.lower():
                        score += 4
                    if word in mode.lower():
                        score += 2
                    if word in module_id.lower() or word in module_label.lower():
                        score += 1

                if query.lower() in searchable:
                    score += 10

                if score <= 0:
                    continue

                native_payload = command.get("nativePayload")
                native_supported = None
                if isinstance(native_payload, dict):
                    native_supported = native_payload.get("supported")

                matches.append(
                    {
                        "score": score,
                        "moduleId": module_id,
                        "moduleLabel": module_label,
                        "type": command_type,
                        "mode": mode,
                        "summary": summary,
                        "nativePayloadSupported": native_supported,
                    }
                )

        matches.sort(
            key=lambda item: (
                -int(item["score"]),
                str(item["type"]),
            )
        )

        selected = matches[:limit]
        for item in selected:
            item.pop("score", None)

        return _success(
            selected,
            query=query,
            matchCount=len(matches),
            returnedCount=len(selected),
        )
    except Exception as exc:
        return _failure(exc)


def autocount_get_command_schema(
    params: dict[str, Any],
    **kwargs: Any,
) -> str:
    del kwargs

    try:
        company_id = str(params.get("company_id", "")).strip()
        config = _load_config(company_id) if company_id else None
        command_type = str(params.get("command_type", "")).strip()
        if not command_type:
            raise AutoCountToolError("command_type is required.")

        _, response = _load_exact_command_schema(command_type, config)
        return _success(response, commandType=command_type)
    except AutoCountCommandResolutionError as exc:
        return _failure(exc, commandType=command_type or None, suggestions=exc.suggestions)
    except Exception as exc:
        return _failure(exc)


def autocount_validate_command(
    params: dict[str, Any],
    **kwargs: Any,
) -> str:
    del kwargs

    command_type = str(params.get("command_type", "")).strip()
    payload = params.get("payload", {})
    try:
        company_id = str(params.get("company_id", "")).strip()
        config = _load_config(company_id) if company_id else None
        if not command_type:
            raise AutoCountToolError("command_type is required.")
        if not isinstance(payload, dict):
            raise AutoCountToolError("payload must be a JSON object.")
        _, schema = _load_exact_command_schema(command_type, config)
        validation = validate_command_payload(schema, payload)
        return _success(validation, commandType=command_type)
    except AutoCountCommandResolutionError as exc:
        return _failure(exc, commandType=command_type or None, suggestions=exc.suggestions)
    except Exception as exc:
        return _failure(exc, commandType=command_type or None)


def autocount_execute_command(
    params: dict[str, Any],
    **kwargs: Any,
) -> str:
    del kwargs

    command_type = str(params.get("command_type", "")).strip()
    payload = params.get("payload", {})
    workflow_context = params.get("workflow_context")
    verified_workflow: dict[str, Any] = {}
    execution_started = False

    try:
        if not command_type:
            raise AutoCountToolError("command_type is required.")
        if not isinstance(payload, dict):
            raise AutoCountToolError("payload must be a JSON object.")

        # Resolve the exact official command and reject invalid payloads before
        # connector checks or command submission.
        config = _load_config(str(params.get("company_id", "")).strip() or None)
        _, schema = _load_exact_command_schema(command_type, config)
        validation = validate_command_payload(schema, payload)
        if not validation["valid"]:
            duplicate = _mark_invalid_payload(
                command_type,
                payload,
                validation,
                {
                    "connectorId": str(config["connectorId"]),
                    "companyId": str(config["companyId"]),
                },
            )
            return _json_text(
                {
                    "ok": False,
                    "error": {
                        "type": "AutoCountPayloadValidationError",
                        "message": "Payload did not pass the current official command schema.",
                    },
                    "commandType": command_type,
                    "validation": validation,
                    "duplicateSuppressed": duplicate,
                    "submitted": False,
                }
            )

        # Follow the official flow by checking connector availability first.
        connector_id = quote(str(config["connectorId"]), safe="")
        connector_status = _request_json(
            "GET",
            f"/v1/connectors/{connector_id}/status",
            config=config,
        )
        if connector_status.get("online") is False:
            raise AutoCountToolError(
                "AutoCount connector is offline. Command was not queued."
            )

        from .workflow_tools import append_execution_event, verify_execution_context

        if not _is_admin_workspace():
            verified_workflow = verify_execution_context(
                command_type=command_type,
                payload=payload,
                context=workflow_context if isinstance(workflow_context, dict) else None,
            )
        command_id = str(verified_workflow.get("verified_action_id") or "")
        if not command_id:
            command_id = (
                f"macsoft-{re.sub(r'[^a-z0-9]+', '-', command_type.lower()).strip('-')}"
                f"-{int(time.time())}-{uuid.uuid4().hex[:10]}"
            )

        request_body = {
            "commandId": command_id,
            "connectorId": str(config["connectorId"]),
            "companyId": str(config["companyId"]),
            "type": command_type,
            "payload": payload,
        }

        if verified_workflow:
            _, execution_started = append_execution_event(
                verified_workflow,
                "execution_started",
                {"command_type": command_type, "command_id": command_id},
            )
        if verified_workflow and not execution_started:
            queued_response = _request_json(
                "GET",
                f"/v1/commands/{quote(command_id, safe='')}",
                config=config,
            )
        else:
            queued_response = _request_json(
                "POST",
                "/v1/commands",
                body=request_body,
                config=config,
            )

        timeout_seconds = max(
            5,
            min(
                int(
                    params.get(
                        "timeout_seconds",
                        config.get("commandTimeoutSeconds", 180),
                    )
                ),
                7200,
            ),
        )
        poll_interval = max(
            0.5,
            min(float(config.get("pollIntervalSeconds", 2)), 10.0),
        )
        deadline = time.monotonic() + timeout_seconds
        last_response: dict[str, Any] = queued_response

        while time.monotonic() < deadline:
            last_response = _request_json(
                "GET",
                f"/v1/commands/{quote(command_id, safe='')}",
                config=config,
            )
            status = _command_status(last_response)

            if status in _FINAL_STATUSES:
                if verified_workflow:
                    append_execution_event(
                        verified_workflow,
                        "execution_completed",
                        {
                            "command_type": command_type,
                            "command_id": command_id,
                            "status": status,
                        },
                    )
                return _success(
                    last_response,
                    commandId=command_id,
                    commandType=command_type,
                    status=status,
                )

            time.sleep(poll_interval)

        if verified_workflow:
            append_execution_event(
                verified_workflow,
                "execution_uncertain",
                {
                    "command_type": command_type,
                    "command_id": command_id,
                    "reason": "timeout",
                },
            )
        return _json_text(
            {
                "ok": False,
                "error": {
                    "type": "AutoCountCommandTimeout",
                    "message": (
                        f"Command did not reach a final status within "
                        f"{timeout_seconds} seconds."
                    ),
                },
                "commandId": command_id,
                "commandType": command_type,
                "lastResponse": last_response,
            }
        )
    except AutoCountCommandResolutionError as exc:
        return _failure(
            exc,
            commandType=command_type or None,
            suggestions=exc.suggestions,
            submitted=False,
        )
    except Exception as exc:
        if verified_workflow and execution_started:
            try:
                from .workflow_tools import append_execution_event

                append_execution_event(
                    verified_workflow,
                    "execution_uncertain",
                    {
                        "command_type": command_type,
                        "command_id": str(verified_workflow.get("verified_action_id", "")),
                        "reason": type(exc).__name__,
                    },
                )
            except Exception:
                pass
        return _failure(
            exc,
            commandType=command_type or None,
        )
