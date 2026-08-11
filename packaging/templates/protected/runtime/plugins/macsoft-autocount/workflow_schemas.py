"""Hermes schemas for PharmaRise workflow workspace tools."""

CASE_PROPERTIES = {
    "case_type": {"type": "string", "enum": ["payment", "receiving"]},
    "company_id": {"type": "string", "minLength": 1},
    "account_book_id": {"type": "string", "minLength": 1},
}

WORKFLOW_CASE_WORKSPACE = {
    "name": "workflow_case_workspace",
    "description": "Create, read, search, or version-update one isolated PharmaRise payment or receiving Case in PostgreSQL.",
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["create", "get", "search", "update"]},
            **CASE_PROPERTIES,
            "case_id": {"type": "string"},
            "expected_version": {"type": "integer", "minimum": 1},
            "source_channel": {"type": "string"},
            "source_event_key": {"type": "string"},
            "source_media_path": {"type": "string"},
            "status": {"type": "string"},
            "statuses": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            "reference": {"type": "string"},
            "amount": {"type": ["number", "string"]},
            "currency": {"type": "string"},
            "date_from": {"type": "string", "format": "date"},
            "date_to": {"type": "string", "format": "date"},
            "payer": {"type": "string"},
            "invoice_reference": {"type": "string"},
            "values": {"type": "object", "additionalProperties": True},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
        "required": ["operation", "case_type"],
        "additionalProperties": False,
    },
}

WORKFLOW_RESOLVE_WHATSAPP_IDENTIFIER = {
    "name": "workflow_resolve_whatsapp_identifier",
    "description": "Resolve one trusted WhatsApp chat or sender identifier to its active company, account book, purpose, and internal user mapping.",
    "parameters": {
        "type": "object",
        "properties": {
            "identifier_type": {"type": "string", "enum": ["chat", "user"]},
            "identifier_value": {"type": "string", "minLength": 1},
        },
        "required": ["identifier_type", "identifier_value"],
        "additionalProperties": False,
    },
}

WORKFLOW_CURRENT_CONTEXT = {
    "name": "workflow_current_context",
    "description": "Return the trusted current WhatsApp workflow scope and whether the sender is staff or external. The sender's identity mapping never determines the account-book scope.",
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

WORKFLOW_SET_STAFF_PHONE = {
    "name": "workflow_set_staff_phone",
    "description": "Admin-only registration or deactivation of a WhatsApp staff phone number. Accepts a human-formatted phone number and stores its canonical digits-only identity.",
    "parameters": {
        "type": "object",
        "properties": {
            "phone_number": {"type": "string", "minLength": 8},
            "active": {"type": "boolean"},
        },
        "required": ["phone_number"],
        "additionalProperties": False,
    },
}

WORKFLOW_FIFO_ALLOCATE = {
    "name": "workflow_fifo_allocate",
    "description": "Prepare a deterministic oldest-invoice-first allocation with partial knock-off support; this does not judge bank evidence or write AutoCount.",
    "parameters": {
        "type": "object",
        "properties": {
            "payment_amount": {"type": ["number", "string"]},
            "documents": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        },
        "required": ["payment_amount", "documents"],
        "additionalProperties": False,
    },
}

WORKFLOW_INTAKE_PAYMENT = {
    "name": "workflow_intake_payment",
    "description": "Atomically preserve the current trusted Payment Slip and create or reuse its durable payment job for cross-message continuation, duplicate prevention, and recovery.",
    "parameters": {
        "type": "object",
        "properties": {
            "source_path": {"type": "string", "minLength": 1},
            "payment_facts": {"type": "object", "additionalProperties": True},
            "initial_status": {
                "type": "string",
                "enum": ["waiting_bank", "captured"],
                "default": "waiting_bank"
            },
        },
        "required": ["source_path", "payment_facts"],
        "additionalProperties": False,
    },
}

WORKFLOW_APPROVE_AUTOCOUNT_ACTION = {
    "name": "workflow_approve_autocount_action",
    "description": "Use the existing Hermes human-confirmation gate to approve one exact AutoCount action. Approval follows the action payload digest, not unrelated payment-job updates.",
    "parameters": {
        "type": "object",
        "properties": {
            **CASE_PROPERTIES,
            "case_id": {"type": "string", "minLength": 1},
            "case_version": {"type": "integer", "minimum": 1},
            "action_type": {"type": "string", "minLength": 1},
            "command_type": {"type": "string", "minLength": 1},
            "payload": {"type": "object", "additionalProperties": True},
            "preview": {"type": "string", "minLength": 1},
        },
        "required": [
            "case_type", "company_id", "account_book_id", "case_id",
            "case_version", "action_type", "command_type", "payload", "preview"
        ],
        "additionalProperties": False,
    },
}

WORKFLOW_ARCHIVE_EVIDENCE = {
    "name": "workflow_archive_evidence",
    "description": "Archive one trusted current Gateway attachment and link it to a versioned PharmaRise Case.",
    "parameters": {
        "type": "object",
        "properties": {
            **CASE_PROPERTIES,
            "case_id": {"type": "string", "minLength": 1},
            "case_version": {"type": "integer", "minimum": 1},
            "source_path": {"type": "string", "minLength": 1},
            "evidence_kind": {"type": "string", "minLength": 1},
        },
        "required": [
            "case_type", "company_id", "account_book_id", "case_id",
            "case_version", "source_path", "evidence_kind"
        ],
        "additionalProperties": False,
    },
}

WORKFLOW_SEND_APPROVED_SUPPLIER_MESSAGE = {
    "name": "workflow_send_approved_supplier_message",
    "description": "Approve and send one exact WhatsApp supplier message for the current version of a PharmaRise receiving Case.",
    "parameters": {
        "type": "object",
        "properties": {
            "company_id": {"type": "string", "minLength": 1},
            "account_book_id": {"type": "string", "minLength": 1},
            "case_id": {"type": "string", "minLength": 1},
            "case_version": {"type": "integer", "minimum": 1},
            "recipient": {"type": "string", "minLength": 1},
            "message": {"type": "string", "minLength": 1},
        },
        "required": [
            "company_id", "account_book_id", "case_id", "case_version",
            "recipient", "message"
        ],
        "additionalProperties": False,
    },
}
