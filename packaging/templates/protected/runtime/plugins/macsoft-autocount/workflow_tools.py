"""Hermes tool handlers for PharmaRise workflow state and approvals."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from . import workflow_store
from .workflow_evidence import archive_current_media, trusted_media_source_key
from .workflow_logic import action_digest, fifo_allocate, stable_action_id


_FINANCIAL_APPROVER_ROLES = {"admin", "accountant"}
_CONSEQUENTIAL_COMMANDS = {
    "create-ar-payment",
    "update-ar-payment",
    "create-purchase-order",
    "update-purchase-order",
    "create-purchase-invoice",
    "update-purchase-invoice",
    "transfer-purchase-order-to-purchase-invoice",
}


def _response(ok: bool, **values: Any) -> str:
    return json.dumps({"ok": ok, **values}, ensure_ascii=False, default=str)


def _config() -> dict[str, Any]:
    from .tools import _load_config

    return _load_config()


def _session_value(name: str) -> str:
    try:
        from gateway.session_context import get_session_env

        return get_session_env(name, "").strip()
    except Exception:
        return ""


def current_actor() -> dict[str, str]:
    return {
        "user_id": _session_value("HERMES_SESSION_USER_ID"),
        "role": _session_value("MACSOFT_SESSION_USER_ROLE"),
        "platform": _session_value("HERMES_SESSION_PLATFORM"),
        "chat_id": _session_value("HERMES_SESSION_CHAT_ID"),
        "message_id": _session_value("HERMES_SESSION_MESSAGE_ID"),
    }


def _resolve_whatsapp_actor(actor: dict[str, str]) -> dict[str, str]:
    """Map a trusted WhatsApp sender to the existing MacSoft user authority."""
    if actor["platform"] != "whatsapp":
        return actor
    mapping = workflow_store.resolve_whatsapp_identifier(
        _config(), identifier_type="user", identifier_value=actor["user_id"]
    )
    internal_user_id = str((mapping or {}).get("internal_user_id") or "").strip()
    if not internal_user_id:
        return actor
    token = os.getenv("MACSOFT_HOST_CONTROL_TOKEN", "").strip()
    if not token:
        raise workflow_store.WorkflowStoreError(
            "MacSoft user-role lookup is unavailable for this WhatsApp sender."
        )
    request = Request(
        f"http://127.0.0.1:8787/api/internal/users/{quote(internal_user_id, safe='')}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise workflow_store.WorkflowStoreError(
            "MacSoft user-role lookup failed for this WhatsApp sender."
        ) from exc
    user = payload.get("user") if isinstance(payload, dict) else None
    if not isinstance(user, dict) or str(user.get("user_id", "")) != internal_user_id:
        raise workflow_store.WorkflowStoreError("MacSoft user-role lookup returned an invalid identity.")
    return {**actor, "user_id": internal_user_id, "role": str(user.get("role", "")).strip()}


def _require_actor(*, financial: bool = False) -> dict[str, str]:
    actor = _resolve_whatsapp_actor(current_actor())
    if not actor["user_id"]:
        raise workflow_store.WorkflowStoreError(
            "A trusted authenticated MacSoft actor is required for this workflow operation."
        )
    if financial and actor["role"].strip().lower() not in _FINANCIAL_APPROVER_ROLES:
        raise workflow_store.WorkflowStoreError(
            "This financial action requires an authenticated Admin or Accountant role."
        )
    return actor


def _enforce_trusted_scope(
    actor: dict[str, str], company_id: str, account_book_id: str
) -> None:
    """Prevent model arguments from changing a WhatsApp group's configured scope."""
    if actor["platform"] != "whatsapp":
        return
    mapping = workflow_store.resolve_whatsapp_identifier(
        _config(), identifier_type="chat", identifier_value=actor["chat_id"]
    )
    if mapping is None:
        raise workflow_store.WorkflowStoreError(
            "This WhatsApp chat is not mapped to a MacSoft company and account book."
        )
    if (
        str(mapping.get("company_id")) != company_id
        or str(mapping.get("account_book_id")) != account_book_id
    ):
        raise workflow_store.WorkflowStoreError(
            "The requested company/account book does not match the trusted WhatsApp chat mapping."
        )


def workflow_case_workspace(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        operation = str(params.get("operation", "")).strip()
        case_type = str(params.get("case_type", "")).strip()
        company_id = str(params.get("company_id", "")).strip()
        account_book_id = str(params.get("account_book_id", "")).strip()
        if not all((operation, case_type, company_id, account_book_id)):
            raise workflow_store.WorkflowStoreError(
                "operation, case_type, company_id, and account_book_id are required."
            )
        actor = _require_actor()
        _enforce_trusted_scope(actor, company_id, account_book_id)
        config = _config()
        if operation == "create":
            source_channel = actor["platform"]
            source_event_key = actor["message_id"]
            if actor["platform"] == "whatsapp":
                source_event_key = trusted_media_source_key(
                    message_id=actor["message_id"],
                    source_path=str(params.get("source_media_path") or ""),
                )
            if not source_channel or not source_event_key:
                raise workflow_store.WorkflowStoreError(
                    "A trusted source_channel and source_event_key are required for idempotent Case creation."
                )
            case, created = workflow_store.create_case(
                config,
                case_type=case_type,
                company_id=company_id,
                account_book_id=account_book_id,
                source_channel=source_channel,
                source_event_key=source_event_key,
                actor_user_id=actor["user_id"],
                values=params.get("values") if isinstance(params.get("values"), dict) else {},
            )
            workflow_store.append_event(
                config,
                case_type=case_type,
                case_id=str(case["id"]),
                case_version=int(case["version"]),
                company_id=company_id,
                account_book_id=account_book_id,
                event_type="case_created" if created else "case_reused",
                actor_user_id=actor["user_id"],
                actor_role=actor["role"],
                event_data={"source_channel": source_channel, "source_event_key": source_event_key},
            )
            return _response(True, case=case, created=created)
        if operation == "get":
            case_id = str(params.get("case_id", "")).strip()
            if not case_id:
                raise workflow_store.WorkflowStoreError("case_id is required for get.")
            case = workflow_store.get_case(
                config,
                case_type=case_type,
                case_id=case_id,
                company_id=company_id,
                account_book_id=account_book_id,
            )
            return _response(True, case=case)
        if operation == "search":
            cases = workflow_store.search_cases(
                config,
                case_type=case_type,
                company_id=company_id,
                account_book_id=account_book_id,
                status=str(params.get("status", "")).strip() or None,
                reference=str(params.get("reference", "")).strip() or None,
                limit=int(params.get("limit", 50)),
            )
            return _response(True, cases=cases)
        if operation == "update":
            case_id = str(params.get("case_id", "")).strip()
            expected_version = int(params.get("expected_version", 0))
            values = params.get("values")
            if not case_id or expected_version < 1 or not isinstance(values, dict):
                raise workflow_store.WorkflowStoreError(
                    "case_id, expected_version, and values are required for update."
                )
            updated = workflow_store.update_case(
                config,
                case_type=case_type,
                case_id=case_id,
                company_id=company_id,
                account_book_id=account_book_id,
                expected_version=expected_version,
                actor_user_id=actor["user_id"],
                values=values,
            )
            workflow_store.append_event(
                config,
                case_type=case_type,
                case_id=case_id,
                case_version=int(updated["version"]),
                company_id=company_id,
                account_book_id=account_book_id,
                event_type="case_updated",
                actor_user_id=actor["user_id"],
                actor_role=actor["role"],
                event_data={"changed_fields": sorted(values)},
            )
            return _response(True, case=updated)
        raise workflow_store.WorkflowStoreError("Unsupported Case workspace operation.")
    except Exception as exc:
        return _response(False, error={"type": type(exc).__name__, "message": str(exc)})


def workflow_resolve_whatsapp_identifier(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        mapping = workflow_store.resolve_whatsapp_identifier(
            _config(),
            identifier_type=str(params.get("identifier_type", "")).strip(),
            identifier_value=str(params.get("identifier_value", "")).strip(),
        )
        return _response(True, mapping=mapping)
    except Exception as exc:
        return _response(False, error={"type": type(exc).__name__, "message": str(exc)})


def workflow_fifo_allocate(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        documents = params.get("documents")
        if not isinstance(documents, list):
            raise ValueError("documents must be an array.")
        return _response(True, **fifo_allocate(params.get("payment_amount"), documents))
    except Exception as exc:
        return _response(False, error={"type": type(exc).__name__, "message": str(exc)})


def workflow_archive_evidence(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        actor = _require_actor()
        config = _config()
        case_type = str(params["case_type"])
        company_id = str(params["company_id"])
        account_book_id = str(params["account_book_id"])
        _enforce_trusted_scope(actor, company_id, account_book_id)
        case_id = str(params["case_id"])
        case_version = int(params["case_version"])
        current = workflow_store.get_case(
            config,
            case_type=case_type,
            case_id=case_id,
            company_id=company_id,
            account_book_id=account_book_id,
        )
        if current is None or int(current["version"]) != case_version:
            raise workflow_store.WorkflowConflictError(
                "The Case changed before evidence archival. Reload it and try again."
            )
        evidence = archive_current_media(config, source_path=str(params["source_path"]))
        working_data = dict(current.get("working_data") or {})
        evidence_items = list(working_data.get("evidence") or [])
        evidence_items.append({**evidence, "kind": str(params["evidence_kind"])})
        working_data["evidence"] = evidence_items
        try:
            updated = workflow_store.update_case(
                config,
                case_type=case_type,
                case_id=case_id,
                company_id=company_id,
                account_book_id=account_book_id,
                expected_version=case_version,
                actor_user_id=actor["user_id"],
                values={"working_data": working_data},
            )
        except Exception:
            Path(str(evidence["stored_path"])).unlink(missing_ok=True)
            raise
        workflow_store.append_event(
            config,
            case_type=case_type,
            case_id=case_id,
            case_version=int(updated["version"]),
            company_id=company_id,
            account_book_id=account_book_id,
            event_type="evidence_accepted",
            actor_user_id=actor["user_id"],
            actor_role=actor["role"],
            event_data={key: evidence[key] for key in ("evidence_id", "sha256", "size_bytes", "media_type")},
        )
        return _response(True, case=updated, evidence=evidence)
    except Exception as exc:
        return _response(False, error={"type": type(exc).__name__, "message": str(exc)})


def workflow_approve_autocount_action(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    try:
        actor = _require_actor(financial=True)
        config = _config()
        case_type = str(params["case_type"])
        company_id = str(params["company_id"])
        account_book_id = str(params["account_book_id"])
        _enforce_trusted_scope(actor, company_id, account_book_id)
        case_id = str(params["case_id"])
        case_version = int(params["case_version"])
        action_type = str(params["action_type"])
        command_type = str(params["command_type"])
        payload = params["payload"]
        if not isinstance(payload, dict):
            raise workflow_store.WorkflowStoreError("payload must be an object.")
        current = workflow_store.get_case(
            config,
            case_type=case_type,
            case_id=case_id,
            company_id=company_id,
            account_book_id=account_book_id,
        )
        if current is None or int(current["version"]) != case_version:
            raise workflow_store.WorkflowConflictError(
                "The Case changed before approval. Reload it and generate a new preview."
            )
        digest = action_digest(
            case_type=case_type,
            case_id=case_id,
            case_version=case_version,
            action_type=action_type,
            command_type=command_type,
            payload=payload,
        )
        action_id = stable_action_id(
            case_type=case_type,
            case_id=case_id,
            case_version=case_version,
            action_type=action_type,
            digest=digest,
        )
        from tools.approval import request_tool_approval

        decision = request_tool_approval(
            "autocount_execute_command",
            str(params["preview"]),
            rule_key=f"pharmarise:{action_id}:{digest}",
        )
        if not decision.get("approved"):
            return _response(False, approval=decision, actionId=action_id, actionDigest=digest)
        event, created = workflow_store.append_event(
            config,
            case_type=case_type,
            case_id=case_id,
            case_version=case_version,
            company_id=company_id,
            account_book_id=account_book_id,
            event_type="action_approved",
            action_type=action_type,
            action_id=action_id,
            action_digest=digest,
            actor_user_id=actor["user_id"],
            actor_role=actor["role"],
            event_data={"command_type": command_type},
        )
        return _response(
            True,
            approved=True,
            actionId=action_id,
            actionDigest=digest,
            approvalEvent=event,
            eventCreated=created,
        )
    except Exception as exc:
        return _response(False, error={"type": type(exc).__name__, "message": str(exc)})


def workflow_send_approved_supplier_message(params: dict[str, Any], **kwargs: Any) -> str:
    """Approve and send one exact supplier WhatsApp message without exposing a general send tool."""
    del kwargs
    try:
        actor = _require_actor(financial=True)
        config = _config()
        company_id = str(params["company_id"])
        account_book_id = str(params["account_book_id"])
        _enforce_trusted_scope(actor, company_id, account_book_id)
        case_id = str(params["case_id"])
        case_version = int(params["case_version"])
        recipient = str(params["recipient"]).strip()
        message = str(params["message"]).strip()

        current = workflow_store.get_case(
            config,
            case_type="receiving",
            case_id=case_id,
            company_id=company_id,
            account_book_id=account_book_id,
        )
        if current is None or int(current["version"]) != case_version:
            raise workflow_store.WorkflowConflictError(
                "The receiving Case changed before supplier-message approval. Reload it and generate a new preview."
            )

        from tools.send_message_tool import _handle_send, _parse_target_ref

        parsed_recipient, _, is_explicit = _parse_target_ref("whatsapp", recipient)
        if not is_explicit or parsed_recipient != recipient:
            raise workflow_store.WorkflowStoreError(
                "recipient must be one exact WhatsApp JID or E.164 phone number, not a display name."
            )

        payload = {"platform": "whatsapp", "recipient": recipient, "message": message}
        digest = action_digest(
            case_type="receiving",
            case_id=case_id,
            case_version=case_version,
            action_type="supplier_message",
            command_type="send-whatsapp-supplier-message",
            payload=payload,
        )
        action_id = stable_action_id(
            case_type="receiving",
            case_id=case_id,
            case_version=case_version,
            action_type="supplier_message",
            digest=digest,
        )

        sent = workflow_store.find_action_event(
            config,
            action_id=action_id,
            event_type="supplier_message_sent",
            company_id=company_id,
            account_book_id=account_book_id,
        )
        if sent is not None:
            return _response(True, actionId=action_id, actionDigest=digest, alreadySent=True, event=sent)
        started = workflow_store.find_action_event(
            config,
            action_id=action_id,
            event_type="supplier_message_started",
            company_id=company_id,
            account_book_id=account_book_id,
        )
        if started is not None:
            raise workflow_store.WorkflowConflictError(
                "This supplier-message action has an uncertain prior attempt. Inspect the Case and WhatsApp delivery before creating a new preview; it will not be retried automatically."
            )

        from tools.approval import request_tool_approval

        approval_text = (
            "Send this exact supplier WhatsApp message?\n\n"
            f"Recipient: {recipient}\n\nMessage:\n{message}"
        )
        decision = request_tool_approval(
            "workflow_send_approved_supplier_message",
            approval_text,
            rule_key=f"pharmarise:{action_id}:{digest}",
        )
        if not decision.get("approved"):
            return _response(False, approval=decision, actionId=action_id, actionDigest=digest)

        workflow_store.append_event(
            config,
            case_type="receiving",
            case_id=case_id,
            case_version=case_version,
            company_id=company_id,
            account_book_id=account_book_id,
            event_type="action_approved",
            action_type="supplier_message",
            action_id=action_id,
            action_digest=digest,
            actor_user_id=actor["user_id"],
            actor_role=actor["role"],
            event_data=payload,
        )
        workflow_store.append_event(
            config,
            case_type="receiving",
            case_id=case_id,
            case_version=case_version,
            company_id=company_id,
            account_book_id=account_book_id,
            event_type="supplier_message_started",
            action_type="supplier_message",
            action_id=action_id,
            action_digest=digest,
            actor_user_id=actor["user_id"],
            actor_role=actor["role"],
            event_data={"platform": "whatsapp", "recipient": recipient},
        )
        raw_result = _handle_send({"target": f"whatsapp:{recipient}", "message": message})
        try:
            result = json.loads(raw_result)
        except (TypeError, json.JSONDecodeError) as exc:
            result = {"error": f"WhatsApp transport returned an invalid result: {type(exc).__name__}"}
        if not isinstance(result, dict) or not result.get("success"):
            error = str(result.get("error") if isinstance(result, dict) else "Unknown WhatsApp result")
            workflow_store.append_event(
                config,
                case_type="receiving",
                case_id=case_id,
                case_version=case_version,
                company_id=company_id,
                account_book_id=account_book_id,
                event_type="supplier_message_uncertain",
                action_type="supplier_message",
                action_id=action_id,
                action_digest=digest,
                actor_user_id=actor["user_id"],
                actor_role=actor["role"],
                event_data={"error": error},
            )
            raise workflow_store.WorkflowStoreError(
                "Supplier-message delivery was not confirmed. The action is recorded as uncertain and will not be retried automatically."
            )
        event, _ = workflow_store.append_event(
            config,
            case_type="receiving",
            case_id=case_id,
            case_version=case_version,
            company_id=company_id,
            account_book_id=account_book_id,
            event_type="supplier_message_sent",
            action_type="supplier_message",
            action_id=action_id,
            action_digest=digest,
            actor_user_id=actor["user_id"],
            actor_role=actor["role"],
            event_data={
                "platform": "whatsapp",
                "recipient": recipient,
                "message_id": str(result.get("message_id") or ""),
            },
        )
        return _response(
            True,
            actionId=action_id,
            actionDigest=digest,
            messageId=str(result.get("message_id") or ""),
            event=event,
        )
    except Exception as exc:
        return _response(False, error={"type": type(exc).__name__, "message": str(exc)})


def command_requires_workflow_approval(command_type: str, payload: dict[str, Any]) -> bool:
    if command_type in _CONSEQUENTIAL_COMMANDS:
        return True
    return command_type in {"create-item", "update-item"} and "hasBatchNo" in payload


def verify_execution_context(
    *,
    command_type: str,
    payload: dict[str, Any],
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    if not command_requires_workflow_approval(command_type, payload):
        return {}
    if not isinstance(context, dict):
        raise workflow_store.WorkflowStoreError(
            "This consequential AutoCount command requires an approved PharmaRise workflow_context."
        )
    required = {
        "case_type", "case_id", "case_version", "company_id",
        "account_book_id", "action_type", "action_id", "action_digest",
    }
    missing = sorted(required - set(context))
    if missing:
        raise workflow_store.WorkflowStoreError(
            f"workflow_context is missing: {', '.join(missing)}"
        )
    expected = action_digest(
        case_type=str(context["case_type"]),
        case_id=str(context["case_id"]),
        case_version=int(context["case_version"]),
        action_type=str(context["action_type"]),
        command_type=command_type,
        payload=payload,
    )
    if expected != str(context["action_digest"]):
        raise workflow_store.WorkflowConflictError(
            "The AutoCount payload no longer matches the approved action digest."
        )
    expected_id = stable_action_id(
        case_type=str(context["case_type"]),
        case_id=str(context["case_id"]),
        case_version=int(context["case_version"]),
        action_type=str(context["action_type"]),
        digest=expected,
    )
    if expected_id != str(context["action_id"]):
        raise workflow_store.WorkflowConflictError("The action_id is not the stable ID for this action.")
    config = _config()
    current = workflow_store.get_case(
        config,
        case_type=str(context["case_type"]),
        case_id=str(context["case_id"]),
        company_id=str(context["company_id"]),
        account_book_id=str(context["account_book_id"]),
    )
    if current is None or int(current["version"]) != int(context["case_version"]):
        raise workflow_store.WorkflowConflictError(
            "The Case changed after approval. Generate a new preview and approval."
        )
    approval = workflow_store.find_action_event(
        config,
        action_id=expected_id,
        event_type="action_approved",
        company_id=str(context["company_id"]),
        account_book_id=str(context["account_book_id"]),
    )
    if approval is None or approval.get("action_digest") != expected:
        raise workflow_store.WorkflowConflictError("No matching immutable approval event exists.")
    return {**context, "verified_action_id": expected_id}


def append_execution_event(context: dict[str, Any], event_type: str, data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    actor = _require_actor(financial=True)
    return workflow_store.append_event(
        _config(),
        case_type=str(context["case_type"]),
        case_id=str(context["case_id"]),
        case_version=int(context["case_version"]),
        company_id=str(context["company_id"]),
        account_book_id=str(context["account_book_id"]),
        event_type=event_type,
        action_type=str(context["action_type"]),
        action_id=str(context["action_id"]),
        action_digest=str(context["action_digest"]),
        actor_user_id=actor["user_id"],
        actor_role=actor["role"],
        event_data=data,
    )
