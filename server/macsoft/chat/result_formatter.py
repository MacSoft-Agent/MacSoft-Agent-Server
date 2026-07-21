from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


MAX_JSON_REPLY_LENGTH = 1_000_000
MAX_TABLE_ROWS = 50
MAX_TABLE_COLUMNS = 8
MAX_CELL_LENGTH = 160

_JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)
_BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_ -]?key|authorization|device[_ -]?token|password|secret)"
    r"\s*[:=]\s*[^\s,;]+"
)
_WINDOWS_PATH = re.compile(r"(?i)\b[a-z]:\\[^\s]+")
_SENSITIVE_KEYS = {
    "apikey",
    "api_key",
    "authorization",
    "headers",
    "password",
    "secret",
    "token",
    "device_token",
    "devicetoken",
    "system_prompt",
    "systemprompt",
    "developer_prompt",
    "developerprompt",
    "stacktrace",
    "traceback",
    "commandid",
    "command_id",
}
_INTERNAL_KEYS = {
    "ok",
    "type",
    "status",
    "commandtype",
    "command_type",
    "lastresponse",
}
_JSON_REQUEST = re.compile(
    r"(?i)(?:\bas\s+json\b|\bjson\s+only\b|\breturn\s+(?:it\s+)?(?:(?:as|in)\s+)?json\b|"
    r"\braw\s+json\b|(?:仅|只)(?:返回|要)?\s*json|以\s*json\s*(?:格式)?(?:返回|输出))"
)


@dataclass(frozen=True)
class UserReadableError:
    title: str
    detail: str
    action: str


def map_user_readable_error(
    message: str,
    *,
    service: str | None = None,
    kind: str | None = None,
    status_code: int | None = None,
) -> UserReadableError:
    clean = " ".join((message or "").split())
    lowered = clean.lower()

    if service == "ai_service":
        if kind == "authentication" or status_code == 401:
            return UserReadableError(
                title="Server Model/Provider login is required",
                detail="The Server AI Service rejected its current Model/Provider authentication.",
                action="Open Server Settings > Model and sign in to the configured Provider again.",
            )
        if kind == "timeout":
            return UserReadableError(
                title="The Server AI Service timed out",
                detail="The internal AI Service did not return a final response within the allowed time.",
                action="Check the Server AI Service and configured Model, then try again.",
            )
        if kind == "unavailable":
            return UserReadableError(
                title="The Server AI Service is unavailable",
                detail="MacSoft Server could not reach its internal AI Service.",
                action="Start or restart the AI Service from Server Settings, then try again.",
            )

    if re.search(r"\b401\b", clean) or "unauthorized" in lowered or "authentication" in lowered:
        return UserReadableError(
            title="AutoCount authentication failed",
            detail="The configured AutoCount credentials were not accepted.",
            action="Check that the configured API key is valid and has not been revoked.",
        )

    if "connector" in lowered and ("offline" in lowered or "not online" in lowered):
        return UserReadableError(
            title="AutoCount Connector is offline",
            detail="The configured Local Connector is not currently available.",
            action="Start the Local Connector and verify the configured Connector ID.",
        )

    if "company" in lowered and any(word in lowered for word in ("unavailable", "not found", "mapping")):
        return UserReadableError(
            title="The configured company is unavailable",
            detail="MacSoft Agent could not access the configured AutoCount company.",
            action="Check the Company ID and its Connector mapping.",
        )

    item_match = re.search(
        r"(?i)item(?:\s+code)?\s+([a-z0-9._/-]+).*?(?:does not exist|not found|unknown)"
        r"|(?:does not exist|not found|unknown).*?item(?:\s+code)?\s+([a-z0-9._/-]+)",
        clean,
    )
    if item_match:
        item_code = item_match.group(1) or item_match.group(2)
        return UserReadableError(
            title="Invoice validation failed",
            detail=f"Item code {item_code} does not exist.",
            action="Confirm the item code and try again.",
        )

    if "timed out" in lowered or "timeout" in lowered:
        return UserReadableError(
            title="The AutoCount request timed out",
            detail="AutoCount did not return a final result within the allowed time.",
            action="Check the Connector status, then try again.",
        )

    if "payload" in lowered and "validation" in lowered:
        return UserReadableError(
            title="AutoCount payload validation failed",
            detail="The supplied information does not match the current official command schema.",
            action="Review the reported missing, unknown, type, or Master/Detail fields and try again.",
        )

    if "not an exact current official catalog command" in lowered:
        return UserReadableError(
            title="AutoCount command could not be resolved",
            detail="The requested command name is not an exact entry in the current official catalog.",
            action="Review the suggested catalog matches and select one exact command.",
        )

    if "cannot connect" in lowered or "connection refused" in lowered:
        return UserReadableError(
            title="MacSoft Agent service is unavailable",
            detail="MacSoft Agent could not reach a required internal service.",
            action="Try again. If the problem continues, contact your administrator.",
        )

    return UserReadableError(
        title="The request could not be completed",
        detail="MacSoft Agent received an error while processing the request.",
        action="Review the information provided and try again. If the problem continues, contact your administrator.",
    )


def format_error_markdown(error: UserReadableError) -> str:
    return (
        f"## {error.title}\n\n"
        f"**Reason**\n\n{error.detail}\n\n"
        f"**Recommended action**\n\n{error.action}"
    )


def _extract_json(text: str) -> Any | None:
    candidate = text.strip()
    fence = _JSON_FENCE.fullmatch(candidate)
    if fence:
        candidate = fence.group(1).strip()

    if len(candidate) > MAX_JSON_REPLY_LENGTH or not candidate.startswith(("{", "[")):
        return None

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _key_id(key: Any) -> str:
    return re.sub(r"[^a-z0-9_]", "", str(key).lower())


def _is_sensitive_key(key: Any) -> bool:
    return _key_id(key) in _SENSITIVE_KEYS


def _display_label(key: Any) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(key))
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(word.capitalize() for word in text.split())


def _cell(value: Any) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = "Yes" if value else "No"
    elif isinstance(value, (dict, list)):
        text = f"{len(value)} records" if isinstance(value, list) else "Details available"
    else:
        text = str(value)
    text = _BEARER_TOKEN.sub("Bearer [redacted]", text)
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    text = _WINDOWS_PATH.sub("[local path removed]", text)
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")[:MAX_CELL_LENGTH]


def _find_error_message(value: Any) -> str:
    if isinstance(value, dict):
        error = value.get("error")
        if isinstance(error, dict):
            for key in ("message", "detail", "reason"):
                if error.get(key):
                    return str(error[key])
        elif error:
            return str(error)
        for key in ("message", "detail", "reason"):
            if value.get(key):
                return str(value[key])
    return ""


def _command_title(value: dict[str, Any]) -> str:
    command_type = str(value.get("commandType") or value.get("command_type") or "").lower()
    if "invoice" in command_type:
        return "Sales Invoice result"
    if any(word in command_type for word in ("debtor", "customer")):
        return "Customer records"
    return "AutoCount result"


def user_requested_json(message: str) -> bool:
    return bool(_JSON_REQUEST.search(message or ""))


def _looks_like_business_rows(value: Any) -> bool:
    if isinstance(value, dict):
        candidates = [value]
        for key in ("data", "result", "rows", "items", "customers", "debtors", "documents"):
            nested = value.get(key)
            if isinstance(nested, dict):
                candidates.append(nested)
            elif isinstance(nested, list):
                candidates.extend(item for item in nested[:3] if isinstance(item, dict))
    elif isinstance(value, list):
        candidates = [item for item in value[:3] if isinstance(item, dict)]
    else:
        return False

    business_keys = {
        "debtorcode",
        "companyname",
        "customercode",
        "customername",
        "documentnumber",
        "docno",
        "invoiceno",
        "invoice_number",
    }
    return any(
        business_keys.intersection({_key_id(key) for key in candidate})
        for candidate in candidates
    )


def _is_recognized_autocount_result(value: Any) -> bool:
    if not isinstance(value, dict):
        return _looks_like_business_rows(value)

    command_type = str(value.get("commandType") or value.get("command_type") or "").lower()
    if command_type and any(
        word in command_type
        for word in (
            "debtor",
            "customer",
            "creditor",
            "invoice",
            "sales-order",
            "purchase-order",
            "stock",
            "item",
            "payment",
            "receipt",
        )
    ):
        return True

    if value.get("ok") is False:
        error = value.get("error")
        error_type = ""
        if isinstance(error, dict):
            error_type = str(error.get("type") or "")
        message = _find_error_message(value)
        lowered = message.lower()
        known_error = (
            re.search(r"\b401\b", message) is not None
            or "autocount" in lowered
            or ("connector" in lowered and ("offline" in lowered or "not online" in lowered))
            or ("company" in lowered and any(word in lowered for word in ("unavailable", "not found", "mapping")))
            or ("item" in lowered and any(word in lowered for word in ("does not exist", "not found", "unknown")))
            or ("payload" in lowered and "validation" in lowered)
            or "not an exact current official catalog command" in lowered
            or "timed out" in lowered
            or "timeout" in lowered
        )
        return error_type.lower().startswith("autocount") or known_error

    return _looks_like_business_rows(value)


def _business_value(value: Any) -> Any:
    current = value
    for _ in range(5):
        if not isinstance(current, dict):
            break
        next_value = None
        for key in ("result", "rows", "items", "customers", "debtors", "documents", "data"):
            candidate = current.get(key)
            if isinstance(candidate, (dict, list)):
                next_value = candidate
                break
        if next_value is None:
            break
        current = next_value
    return current


def _table(rows: list[dict[str, Any]]) -> str:
    safe_rows = [row for row in rows if isinstance(row, dict)]
    if not safe_rows:
        return "No records were returned."

    columns: list[str] = []
    for row in safe_rows:
        for key in row:
            if _is_sensitive_key(key) or _key_id(key) in _INTERNAL_KEYS:
                continue
            if key not in columns and not isinstance(row.get(key), (dict, list)):
                columns.append(key)
            if len(columns) >= MAX_TABLE_COLUMNS:
                break
        if len(columns) >= MAX_TABLE_COLUMNS:
            break

    if not columns:
        return f"Found {len(safe_rows)} records."

    header = "| " + " | ".join(_display_label(column) for column in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(_cell(row.get(column)) for column in columns) + " |"
        for row in safe_rows[:MAX_TABLE_ROWS]
    ]
    suffix = ""
    if len(safe_rows) > MAX_TABLE_ROWS:
        suffix = f"\n\nShowing the first {MAX_TABLE_ROWS} of {len(safe_rows)} records."
    return f"Found {len(safe_rows)} records.\n\n{header}\n{divider}\n" + "\n".join(body) + suffix


def _summary(value: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, item in value.items():
        if _is_sensitive_key(key) or _key_id(key) in _INTERNAL_KEYS:
            continue
        if isinstance(item, (dict, list)):
            continue
        lines.append(f"**{_display_label(key)}:** {_cell(item)}")
        if len(lines) >= 12:
            break
    return "\n\n".join(lines) or "The request completed successfully."


def format_assistant_reply(text: str, *, preserve_json: bool = False) -> str:
    """Format only recognized AutoCount business JSON as readable Markdown.

    Ordinary text and Markdown are returned byte-for-byte so the Server does
    not reinterpret a normal Agent answer.
    """

    if preserve_json:
        return text

    parsed = _extract_json(text)
    if parsed is None or not _is_recognized_autocount_result(parsed):
        return text

    if isinstance(parsed, dict) and parsed.get("ok") is False:
        return format_error_markdown(map_user_readable_error(_find_error_message(parsed)))

    title = _command_title(parsed) if isinstance(parsed, dict) else "Result"
    business = _business_value(parsed)

    if isinstance(business, list):
        dictionaries = [item for item in business if isinstance(item, dict)]
        content = _table(dictionaries) if dictionaries else "\n".join(f"- {_cell(item)}" for item in business[:MAX_TABLE_ROWS])
    elif isinstance(business, dict):
        nested_rows = next(
            (
                item
                for key, item in business.items()
                if not _is_sensitive_key(key)
                and isinstance(item, list)
                and all(isinstance(row, dict) for row in item)
            ),
            None,
        )
        content = _table(nested_rows) if nested_rows is not None else _summary(business)
    else:
        content = _cell(business)

    return f"## {title}\n\n{content}"
