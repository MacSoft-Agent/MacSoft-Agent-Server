"""PostgreSQL persistence for PharmaRise workflow Cases and audit events."""

from __future__ import annotations

import json
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator


class WorkflowStoreError(RuntimeError):
    """Base error for workflow persistence."""


class WorkflowConfigurationError(WorkflowStoreError):
    """Raised when PostgreSQL is not configured or available."""


class WorkflowConflictError(WorkflowStoreError):
    """Raised for stale Case versions or idempotency conflicts."""


_SCHEMA_LOCK = threading.Lock()
_SCHEMA_READY: set[str] = set()
_CASE_TABLES = {"payment": "payment_cases", "receiving": "receiving_cases"}


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date, Decimal, uuid.UUID)):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def public_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return json.loads(json.dumps(record, default=_json_default))


def load_dsn(config: dict[str, Any]) -> str:
    dsn = os.getenv("MACSOFT_WORKFLOW_POSTGRES_DSN", "").strip()
    if not dsn:
        dsn = str(config.get("workflowPostgresDsn", "")).strip()
    if not dsn:
        raise WorkflowConfigurationError(
            "PharmaRise workflow PostgreSQL is not configured. Set the protected "
            "machine environment variable MACSOFT_WORKFLOW_POSTGRES_DSN or the "
            "workflowPostgresDsn deployment setting."
        )
    return dsn


def _driver():
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise WorkflowConfigurationError(
            "The locked psycopg runtime dependency is unavailable. Rebuild the "
            "MacSoft runtime dependencies before enabling PharmaRise workflows."
        ) from exc
    return psycopg, dict_row, Jsonb


@contextmanager
def connection(config: dict[str, Any]) -> Iterator[Any]:
    psycopg, dict_row, _ = _driver()
    dsn = load_dsn(config)
    timeout = max(2, min(int(config.get("workflowPostgresConnectTimeoutSeconds", 10)), 60))
    try:
        with psycopg.connect(dsn, connect_timeout=timeout, row_factory=dict_row) as conn:
            yield conn
    except WorkflowStoreError:
        raise
    except Exception as exc:
        raise WorkflowStoreError(f"Workflow PostgreSQL operation failed: {exc}") from exc


def ensure_schema(config: dict[str, Any]) -> None:
    dsn = load_dsn(config)
    cache_key = str(hash(dsn))
    if cache_key in _SCHEMA_READY:
        return
    with _SCHEMA_LOCK:
        if cache_key in _SCHEMA_READY:
            return
        migration = Path(__file__).resolve().parent / "migrations" / "001_pharmarise_workflow.sql"
        sql = migration.read_text(encoding="utf-8")
        with connection(config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
        _SCHEMA_READY.add(cache_key)


def _table(case_type: str) -> str:
    try:
        return _CASE_TABLES[case_type]
    except KeyError as exc:
        raise WorkflowStoreError("case_type must be payment or receiving.") from exc


def create_case(
    config: dict[str, Any],
    *,
    case_type: str,
    company_id: str,
    account_book_id: str,
    source_channel: str,
    source_event_key: str,
    actor_user_id: str,
    values: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    ensure_schema(config)
    table = _table(case_type)
    common = {
        "id": uuid.uuid4(),
        "company_id": company_id,
        "account_book_id": account_book_id,
        "status": str(values.get("status") or "pending"),
        "source_channel": source_channel,
        "source_event_key": source_event_key,
        "working_data": values.get("working_data") or {},
        "created_by": actor_user_id,
        "updated_by": actor_user_id,
    }
    if case_type == "payment":
        fields = ["debtor_code", "amount", "payment_date", "payment_reference"]
    else:
        fields = ["supplier_code", "supplier_invoice_no", "po_no"]
    for field in fields:
        common[field] = values.get(field)

    _, _, Jsonb = _driver()
    columns = list(common)
    parameters = [Jsonb(common[name]) if name == "working_data" else common[name] for name in columns]
    placeholders = ", ".join(["%s"] * len(columns))
    query = f"""
        INSERT INTO {table} ({', '.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (company_id, account_book_id, source_channel, source_event_key)
        DO NOTHING
        RETURNING *
    """
    with connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, parameters)
            created = cursor.fetchone()
            if created is not None:
                return public_record(created) or {}, True
            cursor.execute(
                f"""
                SELECT * FROM {table}
                WHERE company_id = %s AND account_book_id = %s
                  AND source_channel = %s AND source_event_key = %s
                """,
                (company_id, account_book_id, source_channel, source_event_key),
            )
            existing = cursor.fetchone()
    if existing is None:
        raise WorkflowConflictError("Idempotent Case lookup failed after create conflict.")
    return public_record(existing) or {}, False


def get_case(
    config: dict[str, Any],
    *,
    case_type: str,
    case_id: str,
    company_id: str,
    account_book_id: str,
) -> dict[str, Any] | None:
    ensure_schema(config)
    table = _table(case_type)
    with connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT * FROM {table}
                WHERE id = %s AND company_id = %s AND account_book_id = %s
                """,
                (case_id, company_id, account_book_id),
            )
            return public_record(cursor.fetchone())

def search_cases(
    config: dict[str, Any],
    *,
    case_type: str,
    company_id: str,
    account_book_id: str,
    status: str | None = None,
    statuses: list[str] | None = None,
    reference: str | None = None,
    amount: Any | None = None,
    currency: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    payer: str | None = None,
    invoice_reference: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    ensure_schema(config)
    table = _table(case_type)
    clauses = ["company_id = %s", "account_book_id = %s"]
    params: list[Any] = [company_id, account_book_id]
    if statuses:
        normalized_statuses = [str(item).strip() for item in statuses if str(item).strip()]
        if normalized_statuses:
            clauses.append("status = ANY(%s)")
            params.append(normalized_statuses)
    elif status:
        clauses.append("status = %s")
        params.append(status)
    if reference:
        if case_type == "payment":
            clauses.append("payment_reference = %s")
        else:
            clauses.append("(supplier_invoice_no = %s OR po_no = %s)")
            params.append(reference)
        params.append(reference)
    if amount is not None and str(amount).strip():
        clauses.append("amount = %s")
        params.append(amount)
    if date_from:
        clauses.append("payment_date >= %s")
        params.append(date_from)
    if date_to:
        clauses.append("payment_date <= %s")
        params.append(date_to)
    if currency:
        clauses.append("UPPER(COALESCE(working_data #>> '{payment_facts,currency}', '')) = UPPER(%s)")
        params.append(currency)
    if payer:
        clauses.append("COALESCE(working_data #>> '{payment_facts,payer}', working_data #>> '{payment_facts,payer_name}', working_data #>> '{payment_facts,customer_name}', '') ILIKE %s")
        params.append(f"%{payer}%")
    if invoice_reference:
        clauses.append("COALESCE(working_data #>> '{payment_facts,invoice_reference}', working_data #>> '{payment_facts,invoice_no}', '') = %s")
        params.append(invoice_reference)
    params.append(max(1, min(int(limit), 200)))
    with connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {table} WHERE {' AND '.join(clauses)} "
                "ORDER BY updated_at DESC LIMIT %s",
                params,
            )
            return [public_record(row) or {} for row in cursor.fetchall()]


def update_case(
    config: dict[str, Any],
    *,
    case_type: str,
    case_id: str,
    company_id: str,
    account_book_id: str,
    expected_version: int,
    actor_user_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    ensure_schema(config)
    table = _table(case_type)
    allowed = {"status", "working_data"}
    allowed.update(
        {"debtor_code", "amount", "payment_date", "payment_reference"}
        if case_type == "payment"
        else {"supplier_code", "supplier_invoice_no", "po_no"}
    )
    updates = {key: value for key, value in values.items() if key in allowed}
    if not updates:
        raise WorkflowStoreError("No supported Case fields were supplied for update.")
    _, _, Jsonb = _driver()
    assignments: list[str] = []
    params: list[Any] = []
    for name, value in updates.items():
        assignments.append(f"{name} = %s")
        params.append(Jsonb(value) if name == "working_data" else value)
    assignments.extend(["updated_by = %s", "version = version + 1", "updated_at = CURRENT_TIMESTAMP"])
    params.extend([actor_user_id, case_id, company_id, account_book_id, int(expected_version)])
    with connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {table}
                SET {', '.join(assignments)}
                WHERE id = %s AND company_id = %s AND account_book_id = %s
                  AND version = %s
                RETURNING *
                """,
                params,
            )
            updated = cursor.fetchone()
    if updated is None:
        raise WorkflowConflictError(
            "Case version is stale or the Case is outside the selected company/account book."
        )
    return public_record(updated) or {}


def append_event(
    config: dict[str, Any],
    *,
    case_type: str,
    case_id: str,
    case_version: int,
    company_id: str,
    account_book_id: str,
    event_type: str,
    actor_user_id: str,
    actor_role: str,
    action_type: str | None = None,
    action_id: str | None = None,
    action_digest: str | None = None,
    event_data: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    ensure_schema(config)
    _, _, Jsonb = _driver()
    event_id = uuid.uuid4()
    values = (
        event_id,
        case_type,
        case_id,
        int(case_version),
        company_id,
        account_book_id,
        event_type,
        action_type,
        action_id,
        action_digest,
        actor_user_id,
        actor_role or None,
        Jsonb(event_data or {}),
    )
    with connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO workflow_case_events (
                    id, case_type, case_id, case_version, company_id,
                    account_book_id, event_type, action_type, action_id,
                    action_digest, actor_user_id, actor_role, event_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (action_id, event_type) WHERE action_id IS NOT NULL
                DO NOTHING
                RETURNING *
                """,
                values,
            )
            row = cursor.fetchone()
            if row is not None:
                return public_record(row) or {}, True
            if not action_id:
                raise WorkflowConflictError("Append-only event insertion failed.")
            cursor.execute(
                """
                SELECT * FROM workflow_case_events
                WHERE action_id = %s AND event_type = %s
                """,
                (action_id, event_type),
            )
            existing = cursor.fetchone()
    if existing is None:
        raise WorkflowConflictError("Idempotent event lookup failed after conflict.")
    return public_record(existing) or {}, False


def find_action_event(
    config: dict[str, Any],
    *,
    action_id: str,
    event_type: str,
    company_id: str,
    account_book_id: str,
) -> dict[str, Any] | None:
    ensure_schema(config)
    with connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM workflow_case_events
                WHERE action_id = %s AND event_type = %s
                  AND company_id = %s AND account_book_id = %s
                """,
                (action_id, event_type, company_id, account_book_id),
            )
            return public_record(cursor.fetchone())


def resolve_whatsapp_identifier(
    config: dict[str, Any],
    *,
    identifier_type: str,
    identifier_value: str,
) -> dict[str, Any] | None:
    ensure_schema(config)
    with connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM whatsapp_identifiers
                WHERE platform = 'whatsapp' AND identifier_type = %s
                  AND identifier_value = %s AND active = TRUE
                """,
                (identifier_type, identifier_value),
            )
            return public_record(cursor.fetchone())


def get_case_by_source(
    config: dict[str, Any],
    *,
    case_type: str,
    company_id: str,
    account_book_id: str,
    source_channel: str,
    source_event_key: str,
) -> dict[str, Any] | None:
    """Find the durable job created from one trusted source attachment."""
    ensure_schema(config)
    table = _table(case_type)
    with connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT * FROM {table}
                WHERE company_id = %s AND account_book_id = %s
                  AND source_channel = %s AND source_event_key = %s
                """,
                (company_id, account_book_id, source_channel, source_event_key),
            )
            return public_record(cursor.fetchone())


def set_whatsapp_staff_phone(
    config: dict[str, Any],
    *,
    phone: str,
    company_id: str,
    account_book_id: str,
    internal_user_id: str,
    active: bool,
    actor_user_id: str,
) -> dict[str, Any]:
    """Create or update one canonical WhatsApp phone staff registration."""
    ensure_schema(config)
    record_id = uuid.uuid4()
    with connection(config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO whatsapp_identifiers (
                    id, platform, identifier_type, identifier_value,
                    company_id, account_book_id, purpose, internal_user_id,
                    active, created_by, updated_by
                ) VALUES (%s, 'whatsapp', 'user', %s, %s, %s, 'staff', %s, %s, %s, %s)
                ON CONFLICT (platform, identifier_type, identifier_value)
                DO UPDATE SET company_id = EXCLUDED.company_id,
                              account_book_id = EXCLUDED.account_book_id,
                              purpose = 'staff',
                              internal_user_id = EXCLUDED.internal_user_id,
                              active = EXCLUDED.active,
                              updated_by = EXCLUDED.updated_by,
                              updated_at = CURRENT_TIMESTAMP
                RETURNING *
                """,
                (
                    record_id,
                    phone,
                    company_id,
                    account_book_id,
                    internal_user_id,
                    bool(active),
                    actor_user_id,
                    actor_user_id,
                ),
            )
            return public_record(cursor.fetchone()) or {}
