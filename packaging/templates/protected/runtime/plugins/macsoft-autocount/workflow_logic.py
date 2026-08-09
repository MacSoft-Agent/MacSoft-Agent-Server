"""Pure PharmaRise workflow rules shared by tools and tests."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


class WorkflowRuleError(ValueError):
    """Raised when a workflow action cannot be prepared safely."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def action_digest(
    *,
    case_type: str,
    case_id: str,
    case_version: int,
    action_type: str,
    command_type: str,
    payload: dict[str, Any],
) -> str:
    document = {
        "case_type": case_type,
        "case_id": case_id,
        "case_version": int(case_version),
        "action_type": action_type,
        "command_type": command_type,
        "payload": payload,
    }
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


def stable_action_id(
    *,
    case_type: str,
    case_id: str,
    case_version: int,
    action_type: str,
    digest: str,
) -> str:
    normalized = "-".join(part.strip().lower().replace("_", "-") for part in (case_type, action_type))
    return f"macsoft-{normalized}-{case_id}-v{int(case_version)}-{digest[:16]}"


def parse_money(value: Any, field: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise WorkflowRuleError(f"{field} must be a valid decimal amount.") from exc
    if amount < 0:
        raise WorkflowRuleError(f"{field} cannot be negative.")
    return amount.quantize(Decimal("0.01"))


def fifo_allocate(payment_amount: Any, documents: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Allocate oldest outstanding documents, allowing one partial final line."""
    remaining = parse_money(payment_amount, "payment_amount")
    ordered = sorted(
        documents,
        key=lambda row: (
            str(row.get("invoice_date") or row.get("docDate") or "9999-12-31"),
            str(row.get("doc_key") or row.get("docKey") or ""),
        ),
    )
    allocations: list[dict[str, Any]] = []
    for document in ordered:
        if remaining == 0:
            break
        outstanding = parse_money(
            document.get("outstanding_amount", document.get("outstandingAmount", 0)),
            "outstanding_amount",
        )
        if outstanding == 0:
            continue
        allocated = min(remaining, outstanding)
        allocations.append(
            {
                "docKey": document.get("doc_key", document.get("docKey")),
                "docNo": document.get("doc_no", document.get("docNo")),
                "invoiceDate": document.get("invoice_date", document.get("docDate")),
                "amount": str(allocated),
                "partial": allocated < outstanding,
            }
        )
        remaining -= allocated
    return {"allocations": allocations, "unappliedAmount": str(remaining)}
