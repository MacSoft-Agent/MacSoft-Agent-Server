"""Generic AutoCount Cloud tool handlers.

There is intentionally no command-specific Python implementation here.
Every official AutoCount command is discovered and executed dynamically.
"""

from __future__ import annotations

import json
import hashlib
import difflib
import re
import secrets
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .validator import validate_command_payload


_PLUGIN_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _PLUGIN_DIR / "config.json"
_FINAL_STATUSES = {"done", "failed", "cancelled", "canceled", "error"}
_TRANSIENT_HTTP_STATUSES = {429, 502, 503, 504}
_INVALID_FINGERPRINT_LIMIT = 256
_invalid_fingerprints: deque[str] = deque()
_invalid_fingerprint_set: set[str] = set()
_invalid_fingerprint_lock = threading.Lock()

_QUERY_RESULT_TTL_SECONDS = 10 * 60
_QUERY_RESULT_MAX_ENTRIES = 128
_QUERY_RESULT_MAX_ROWS = 10_000
_QUERY_RESULT_MAX_BYTES = 2_000_000
_QUERY_RESULT_LOCK = threading.RLock()
_query_results: dict[str, dict[str, Any]] = {}
_STRUCTURED_QUERY_MODES = {"read", "query", "list"}
_TABULAR_CONTAINER_KEYS = ("rows", "records", "items", "results", "data", "result")


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


def _load_config() -> dict[str, Any]:
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


def _request_json(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    config = _load_config()
    base_url = str(config["baseUrl"]).rstrip("/")
    url = f"{base_url}{path}"
    timeout = int(
        timeout_seconds
        if timeout_seconds is not None
        else config.get("requestTimeoutSeconds", 30)
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
    if re.search(r"\bhttp 401\b", lowered):
        return "AutoCount API HTTP 401. Authentication failed."
    if re.search(r"\bhttp \d{3}\b", lowered):
        return message
    if "connector is offline" in lowered:
        return "AutoCount connector is offline. Command was not queued."
    if "timed out" in lowered or "cannot connect to autocount cloud" in lowered:
        return message
    if lowered.startswith(
        (
            "chart ",
            "result_ref ",
            "autocount_query_data ",
            "the official autocount result ",
            "the autocount result ",
            "the autocount query ",
            "autocount row ",
        )
    ):
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


def _resolve_exact_command(command_type: str) -> dict[str, Any]:
    catalog = _request_json("GET", "/v1/schema/modules")
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


def _load_exact_command_schema(command_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
    command = _resolve_exact_command(command_type)
    encoded = quote(command_type, safe="")
    schema = _request_json("GET", f"/v1/schema/commands/{encoded}")
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


def _query_owner(kwargs: dict[str, Any]) -> tuple[str, str]:
    """Return the Hermes execution scope used to isolate temporary results."""

    task_id = str(kwargs.get("task_id") or "default")
    session_id = str(kwargs.get("session_id") or "default")
    return task_id, session_id


def _purge_query_results(now: float | None = None) -> None:
    current = time.monotonic() if now is None else now
    expired = [
        result_ref
        for result_ref, stored in _query_results.items()
        if current - float(stored["created_at"]) >= _QUERY_RESULT_TTL_SECONDS
    ]
    for result_ref in expired:
        _query_results.pop(result_ref, None)


def _store_query_result(owner: tuple[str, str], data: dict[str, Any]) -> str:
    serialized = _json_text(data).encode("utf-8")
    if len(serialized) > _QUERY_RESULT_MAX_BYTES:
        raise AutoCountToolError(
            "The AutoCount query result is too large to prepare as a chart."
        )

    result_ref = f"acqr_{secrets.token_urlsafe(18)}"
    now = time.monotonic()
    with _QUERY_RESULT_LOCK:
        _purge_query_results(now)
        while len(_query_results) >= _QUERY_RESULT_MAX_ENTRIES:
            _query_results.pop(next(iter(_query_results)))
        _query_results[result_ref] = {
            "owner": owner,
            "created_at": now,
            "data": data,
        }
    return result_ref


def _get_query_result(result_ref: str, owner: tuple[str, str]) -> dict[str, Any]:
    if not result_ref or not re.fullmatch(r"acqr_[A-Za-z0-9_-]{12,64}", result_ref):
        raise AutoCountToolError("result_ref is invalid or expired.")

    with _QUERY_RESULT_LOCK:
        _purge_query_results()
        stored = _query_results.get(result_ref)
        if stored is None or stored["owner"] != owner:
            raise AutoCountToolError("result_ref is invalid or expired.")
        return stored["data"]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _row_list_from_value(value: Any) -> tuple[list[Any], list[str] | None] | None:
    """Find a conventional row container without guessing arbitrary objects."""

    if isinstance(value, list):
        if not value:
            return [], None
        if all(isinstance(row, dict) for row in value):
            return value, None
        if all(isinstance(row, list) for row in value):
            return value, None
        return None

    if not isinstance(value, dict):
        return None

    columns = value.get("columns")
    column_names = (
        [str(column) for column in columns]
        if isinstance(columns, list) and all(isinstance(column, (str, int)) for column in columns)
        else None
    )

    for key in _TABULAR_CONTAINER_KEYS:
        candidate = value.get(key)
        if isinstance(candidate, list):
            rows = _row_list_from_value(candidate)
            if rows is not None:
                return rows[0], column_names or rows[1]

    for nested in value.values():
        found = _row_list_from_value(nested)
        if found is not None:
            return found
    return None


def _column_type(values: list[Any]) -> str:
    non_null = [value for value in values if value is not None]
    if not non_null:
        return "null"
    if all(isinstance(value, bool) for value in non_null):
        return "boolean"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in non_null):
        return "integer"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_null):
        return "number"
    if all(isinstance(value, str) for value in non_null):
        if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in non_null):
            return "date"
        if all(
            re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?", value)
            for value in non_null
        ):
            return "datetime"
        return "string"
    return "mixed"


def _column_semantic(name: str, value_type: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", name.lower())
    if value_type in {"date", "datetime"}:
        return "time"
    if value_type in {"integer", "number"}:
        if normalized.endswith(("id", "code", "no", "number")):
            return "dimension"
        return "measure"
    if value_type in {"string", "boolean"}:
        return "dimension"
    return "unknown"


def _normalize_query_result(response: Any) -> dict[str, Any]:
    found = _row_list_from_value(response)
    if found is None:
        raise AutoCountToolError(
            "The official AutoCount result does not contain a supported tabular row set."
        )

    raw_rows, column_names = found
    if len(raw_rows) > _QUERY_RESULT_MAX_ROWS:
        raise AutoCountToolError(
            f"The AutoCount query returned more than {_QUERY_RESULT_MAX_ROWS} rows."
        )

    rows: list[dict[str, Any]] = []
    discovered_columns: list[str] = []
    for index, raw_row in enumerate(raw_rows):
        if isinstance(raw_row, dict):
            row = {str(key): value for key, value in raw_row.items()}
        elif isinstance(raw_row, list) and column_names is not None:
            if len(raw_row) != len(column_names):
                raise AutoCountToolError(
                    f"AutoCount row {index + 1} does not match the returned columns."
                )
            row = dict(zip(column_names, raw_row))
        else:
            raise AutoCountToolError("The AutoCount result contains unsupported row values.")

        if any(not _is_scalar(value) for value in row.values()):
            raise AutoCountToolError(
                "The AutoCount result contains nested values that cannot be charted safely."
            )
        for key in row:
            if key not in discovered_columns:
                discovered_columns.append(key)
        rows.append(row)

    columns = column_names or discovered_columns
    columns = list(dict.fromkeys(columns))
    descriptors = []
    for name in columns:
        value_type = _column_type([row.get(name) for row in rows])
        descriptors.append(
            {
                "name": name,
                "type": value_type,
                "semantic": _column_semantic(name, value_type),
            }
        )

    data = {"columns": descriptors, "rows": rows}
    if len(_json_text(data).encode("utf-8")) > _QUERY_RESULT_MAX_BYTES:
        raise AutoCountToolError(
            "The AutoCount query result is too large to prepare as a chart."
        )
    return {
        "data": data,
        "shape": {"rows": len(rows), "columns": len(descriptors)},
    }


def autocount_query_data(
    params: dict[str, Any],
    **kwargs: Any,
) -> str:
    """Execute a structured query command and retain its normalized rows temporarily."""

    command_type = str(params.get("command_type", "")).strip()
    payload = params.get("payload", {})
    try:
        if not command_type:
            raise AutoCountToolError("command_type is required.")
        if not isinstance(payload, dict):
            raise AutoCountToolError("payload must be a JSON object.")

        command = _resolve_exact_command(command_type)
        mode = str(command.get("mode", "")).strip().lower()
        normalized_type = command_type.lower()
        if (
            mode not in _STRUCTURED_QUERY_MODES
            or normalized_type.endswith("-html")
            or str(command.get("mutating", "")).lower() == "true"
        ):
            raise AutoCountToolError(
                "autocount_query_data accepts only official structured read, query, "
                "or list commands; HTML and report commands cannot be used as chart data."
            )

        execution = json.loads(autocount_execute_command(params, **kwargs))
        if not isinstance(execution, dict):
            raise AutoCountToolError("AutoCount returned an invalid query response.")
        if not execution.get("ok"):
            return _json_text(execution)

        normalized = _normalize_query_result(execution.get("data", execution))
        result_ref = _store_query_result(_query_owner(kwargs), normalized)
        return _success(
            {
                "result_ref": result_ref,
                "columns": normalized["data"]["columns"],
                "rows": normalized["data"]["rows"],
                "shape": normalized["shape"],
            },
            commandType=command_type,
        )
    except AutoCountCommandResolutionError as exc:
        return _failure(exc, commandType=command_type or None, suggestions=exc.suggestions)
    except Exception as exc:
        return _failure(exc, commandType=command_type or None)


_CHART_REQUIRED_ENCODINGS = {
    "line": ("x", "y"),
    "area": ("x", "y"),
    "bar": ("category", "value"),
    "horizontal_bar": ("category", "value"),
    "pie": ("category", "value"),
    "donut": ("category", "value"),
    "gauge": ("value", "min", "max"),
    "calendar_heatmap": ("date", "value"),
    "scatter": ("x", "y"),
    "table": (),
}
_CHART_ALLOWED_ENCODINGS = {
    "line": {"x", "y", "series"},
    "area": {"x", "y", "series"},
    "bar": {"category", "value", "series"},
    "horizontal_bar": {"category", "value", "series"},
    "pie": {"category", "value"},
    "donut": {"category", "value"},
    "gauge": {"value", "min", "max", "target"},
    "calendar_heatmap": {"date", "value"},
    "scatter": {"x", "y", "series"},
    "table": set(),
}


def _column_descriptor(data: dict[str, Any], field: str) -> dict[str, Any]:
    for column in data.get("columns", []):
        if isinstance(column, dict) and column.get("name") == field:
            return column
    raise AutoCountToolError(f"Chart field '{field}' is not present in the query result.")


def _require_chart_field(
    data: dict[str, Any],
    field: str,
    *,
    semantic: str,
    encoding_name: str,
) -> None:
    descriptor = _column_descriptor(data, field)
    value_type = str(descriptor.get("type", ""))
    if semantic == "numeric" and value_type not in {"integer", "number"}:
        raise AutoCountToolError(
            f"Chart encoding '{encoding_name}' must map to a numeric field."
        )
    if semantic == "date" and value_type not in {"date", "datetime"}:
        raise AutoCountToolError(
            f"Chart encoding '{encoding_name}' must map to a date or datetime field."
        )
    if semantic == "dimension" and value_type in {"null", "mixed"}:
        raise AutoCountToolError(
            f"Chart encoding '{encoding_name}' must map to a consistent field."
        )


def _validate_chart_encodings(
    chart_type: str,
    encodings: Any,
    data: dict[str, Any],
) -> dict[str, str]:
    if not isinstance(encodings, dict):
        raise AutoCountToolError("encodings must be a JSON object.")

    normalized = {}
    allowed = _CHART_ALLOWED_ENCODINGS[chart_type]
    unknown = set(encodings) - allowed
    if unknown:
        raise AutoCountToolError(
            "Unsupported chart encodings: " + ", ".join(sorted(map(str, unknown)))
        )

    for name, field in encodings.items():
        if not isinstance(name, str) or not isinstance(field, str) or not field.strip():
            raise AutoCountToolError("Chart encodings must map names to non-empty field names.")
        normalized[name] = field.strip()

    missing = [name for name in _CHART_REQUIRED_ENCODINGS[chart_type] if name not in normalized]
    if missing:
        raise AutoCountToolError(
            f"Chart type '{chart_type}' requires encodings: " + ", ".join(missing)
        )

    numeric = {"y", "value", "min", "max", "target"}
    date = {"date"}
    for name, field in normalized.items():
        _column_descriptor(data, field)
        if name in numeric:
            _require_chart_field(data, field, semantic="numeric", encoding_name=name)
        elif name in date:
            _require_chart_field(data, field, semantic="date", encoding_name=name)
        else:
            _require_chart_field(data, field, semantic="dimension", encoding_name=name)
    return normalized


def autocount_create_chart(
    params: dict[str, Any],
    **kwargs: Any,
) -> str:
    """Validate a chart mapping and return the renderer-independent payload."""

    try:
        result_ref = str(params.get("result_ref", "")).strip()
        chart_type = str(params.get("type", "")).strip().lower()
        if chart_type not in _CHART_REQUIRED_ENCODINGS:
            raise AutoCountToolError("Chart type is not supported.")

        stored = _get_query_result(result_ref, _query_owner(kwargs))
        data = stored.get("data")
        if not isinstance(data, dict):
            raise AutoCountToolError("result_ref does not contain a valid query result.")
        encodings = _validate_chart_encodings(chart_type, params.get("encodings"), data)

        title = str(params.get("title", "")).strip()[:200]
        payload = {
            "schema_version": 1,
            "chart_id": f"chart_{secrets.token_urlsafe(16)}",
            "chart": {
                "type": chart_type,
                "title": title or f"AutoCount {chart_type.replace('_', ' ')}",
                "encodings": encodings,
                "data": data,
                "summary": {
                    "rows": int(stored.get("shape", {}).get("rows", len(data.get("rows", [])))),
                    "columns": int(stored.get("shape", {}).get("columns", len(data.get("columns", [])))),
                },
            },
        }
        return _success(payload, resultRef=result_ref)
    except Exception as exc:
        return _failure(exc)


def autocount_get_connector_status(
    params: dict[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    del params, kwargs

    try:
        config = _load_config()
        connector_id = quote(str(config["connectorId"]), safe="")
        response = _request_json(
            "GET",
            f"/v1/connectors/{connector_id}/status",
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
        query = str(params.get("query", "")).strip()
        module_filter = str(params.get("module_id", "")).strip().lower()
        mode_filter = str(params.get("mode", "")).strip().lower()
        limit = max(1, min(int(params.get("limit", 20)), 50))

        if not query:
            raise AutoCountToolError("query is required.")

        query_words = _normalize_words(query)
        catalog = _request_json("GET", "/v1/schema/modules")
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
        command_type = str(params.get("command_type", "")).strip()
        if not command_type:
            raise AutoCountToolError("command_type is required.")

        _, response = _load_exact_command_schema(command_type)
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
        if not command_type:
            raise AutoCountToolError("command_type is required.")
        if not isinstance(payload, dict):
            raise AutoCountToolError("payload must be a JSON object.")
        _, schema = _load_exact_command_schema(command_type)
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

    try:
        if not command_type:
            raise AutoCountToolError("command_type is required.")
        if not isinstance(payload, dict):
            raise AutoCountToolError("payload must be a JSON object.")

        # Resolve the exact official command and reject invalid payloads before
        # connector checks or command submission.
        _, schema = _load_exact_command_schema(command_type)
        config = _load_config()
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
        )
        if connector_status.get("online") is False:
            raise AutoCountToolError(
                "AutoCount connector is offline. Command was not queued."
            )

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

        queued_response = _request_json(
            "POST",
            "/v1/commands",
            body=request_body,
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
                600,
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
            )
            status = _command_status(last_response)

            if status in _FINAL_STATUSES:
                return _success(
                    last_response,
                    commandId=command_id,
                    commandType=command_type,
                    status=status,
                )

            time.sleep(poll_interval)

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
        return _failure(
            exc,
            commandType=command_type or None,
        )
