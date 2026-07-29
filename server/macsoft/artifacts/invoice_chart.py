from __future__ import annotations

import json
import re
import time
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class InvoiceChartError(RuntimeError):
    pass


_CHART_TERMS = re.compile(r"(?i)\b(chart|dashboard|graph|plot)\b|图表|图标|仪表板|趋势图|柱状图|折线图")
_INVOICE_TERMS = re.compile(r"(?i)\b(invoice|invoices|sales invoice|sales invoices)\b|发票|销售单")


def is_invoice_chart_request(message: str) -> bool:
    text = " ".join((message or "").split())
    return bool(_CHART_TERMS.search(text) and _INVOICE_TERMS.search(text))


def _resolve_plugin_config(config) -> Path:
    path = Path(config.autocount.plugin_config_path)
    if not path.is_absolute():
        path = Path(config.config_path).resolve().parent / path
    return path.resolve()


def _load_cloud_config(config) -> dict[str, Any]:
    if not config.autocount.enabled:
        raise InvoiceChartError("autocount_disabled")
    try:
        value = json.loads(_resolve_plugin_config(config).read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise InvoiceChartError("autocount_configuration_unavailable") from error
    required = ("baseUrl", "apiKey", "connectorId", "companyId")
    if not isinstance(value, dict) or any(not str(value.get(key, "")).strip() for key in required):
        raise InvoiceChartError("autocount_configuration_invalid")
    return value


def _request_json(cloud: dict[str, Any], method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    request = Request(
        str(cloud["baseUrl"]).rstrip("/") + path,
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {cloud['apiKey']}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "MacSoft-Agent-Chart/0.1.0",
        },
    )
    try:
        with urlopen(request, timeout=int(cloud.get("requestTimeoutSeconds", 30))) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8", errors="replace"))
            error_type = str(detail.get("errorType") or detail.get("message") or "autocount_http_error")
        except Exception:
            error_type = "autocount_http_error"
        raise InvoiceChartError(error_type) from error
    except (URLError, TimeoutError) as error:
        raise InvoiceChartError("autocount_unavailable") from error
    parsed = json.loads(raw or "{}")
    if not isinstance(parsed, dict):
        raise InvoiceChartError("autocount_invalid_response")
    return parsed


def _find_invoice_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        rows = [item for item in value if "DocDate" in item and "DocNo" in item]
        if rows:
            return rows
    if isinstance(value, dict):
        for child in value.values():
            rows = _find_invoice_rows(child)
            if rows:
                return rows
    return []


def fetch_latest_sales_invoices(config, *, limit: int = 500) -> list[dict[str, Any]]:
    cloud = _load_cloud_config(config)
    connector_id = quote(str(cloud["connectorId"]), safe="")
    status = _request_json(cloud, "GET", f"/v1/connectors/{connector_id}/status")
    if status.get("online") is False:
        raise InvoiceChartError("autocount_connector_offline")
    command_id = f"macsoft-chart-{int(time.time())}-{uuid.uuid4().hex[:12]}"
    _request_json(
        cloud,
        "POST",
        "/v1/commands",
        {
            "commandId": command_id,
            "connectorId": str(cloud["connectorId"]),
            "companyId": str(cloud["companyId"]),
            "type": "list-sales-invoices",
            "payload": {"limit": max(1, min(limit, 500)), "orderBy": "docDate desc"},
        },
    )
    deadline = time.monotonic() + max(10, min(int(cloud.get("commandTimeoutSeconds", 180)), 300))
    interval = max(0.5, min(float(cloud.get("pollIntervalSeconds", 2)), 5.0))
    while time.monotonic() < deadline:
        result = _request_json(cloud, "GET", f"/v1/commands/{quote(command_id, safe='')}")
        state = str(result.get("status") or result.get("commandStatus") or "").lower()
        if state in {"done", "completed", "succeeded", "success"}:
            return _find_invoice_rows(result)
        if state in {"failed", "error", "cancelled", "canceled", "timed_out", "timeout"}:
            raise InvoiceChartError("autocount_command_failed")
        time.sleep(interval)
    raise InvoiceChartError("autocount_command_timeout")


def build_invoice_count_render_input(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for row in rows:
        raw = str(row.get("DocDate") or "").strip()
        try:
            month = datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m")
        except ValueError:
            match = re.match(r"(\d{4})[-/]?(\d{2})", raw)
            if not match:
                continue
            month = f"{match.group(1)}-{match.group(2)}"
        counts[month] += 1
    if not counts:
        raise InvoiceChartError("invoice_dataset_empty")
    points = [{"key": month, "value": count} for month, count in sorted(counts.items())]
    return {
        "title": "Latest Sales Invoices by Month",
        "summary": f"Count trend for the latest {len(rows)} sales invoices returned by AutoCount.",
        "metric": {"name": "invoice_count", "label": "Invoice count", "unit": "documents"},
        "dataset": {"points": points},
        "metadata": {
            "source": {"type": "autocount", "command": "list-sales-invoices"},
            "bounded": True,
            "row_count": len(rows),
            "financial_amount": False,
        },
    }
