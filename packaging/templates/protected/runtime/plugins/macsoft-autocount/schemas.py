"""Tool schemas exposed to the Hermes model."""

AUTOCOUT_GET_CONNECTOR_STATUS = {
    "name": "autocount_get_connector_status",
    "description": (
        "Check the official AutoCount Cloud connector and account-book status. "
        "Use this before diagnosing an AutoCount connection or execution problem."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

AUTOCOUNT_SEARCH_COMMANDS = {
    "name": "autocount_search_commands",
    "description": (
        "Search the live official AutoCount command catalog by natural-language "
        "keywords, command type, module, or action. Use this whenever the exact "
        "official command type is not already known. Do not invent command names."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search phrase such as 'sales invoice create', "
                    "'list debtors', 'stock balance', or a command type."
                ),
            },
            "module_id": {
                "type": "string",
                "description": "Optional official module id filter.",
            },
            "mode": {
                "type": "string",
                "description": (
                    "Optional mode filter such as read, write, report, "
                    "validate, create, edit, void, or delete."
                ),
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum number of matching commands to return.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

AUTOCOUNT_GET_COMMAND_SCHEMA = {
    "name": "autocount_get_command_schema",
    "description": (
        "Fetch the current official full payload schema for one AutoCount command. "
        "Call this before executing any command, even if the command seems familiar. "
        "Use the returned field descriptions, sections, and aliases to identify missing "
        "or ambiguous data and to explain each requested value in business language."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command_type": {
                "type": "string",
                "description": "Exact official AutoCount command type.",
            }
        },
        "required": ["command_type"],
        "additionalProperties": False,
    },
}

AUTOCOUNT_VALIDATE_COMMAND = {
    "name": "autocount_validate_command",
    "description": (
        "Validate a candidate payload against the exact current official "
        "AutoCount command schema without submitting it. Use the structured "
        "missing, unknown, type, and location errors plus their official schema "
        "descriptions to request corrections in business language, never by raw key alone."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command_type": {
                "type": "string",
                "description": "Exact official AutoCount command type.",
            },
            "payload": {
                "type": "object",
                "description": "Candidate payload to validate without execution.",
                "additionalProperties": True,
            },
        },
        "required": ["command_type", "payload"],
        "additionalProperties": False,
    },
}

AUTOCOUNT_EXECUTE_COMMAND = {
    "name": "autocount_execute_command",
    "description": (
        "Execute one official AutoCount command through AutoCount Cloud and wait "
        "for the Local Connector result. Use only after reading the live command "
        "schema, validating the payload, and resolving required or ambiguous "
        "business data with the user. The executor repeats exact resolution and "
        "validation before any submission. "
        "This is one generic executor for every official command; never use "
        "terminal, Python generation, or command-specific scripts to operate AutoCount."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command_type": {
                "type": "string",
                "description": "Exact official AutoCount command type.",
            },
            "payload": {
                "type": "object",
                "description": (
                    "Payload built exactly from the live official command schema."
                ),
                "additionalProperties": True,
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 5,
                "maximum": 600,
                "description": "Optional total wait time for the final result.",
            },
            "workflow_context": {
                "type": "object",
                "description": (
                    "Required for consequential PharmaRise financial and Batch-control writes. "
                    "Use the exact actionId and actionDigest returned by "
                    "workflow_approve_autocount_action."
                ),
                "properties": {
                    "case_type": {"type": "string", "enum": ["payment", "receiving"]},
                    "case_id": {"type": "string"},
                    "case_version": {"type": "integer", "minimum": 1},
                    "company_id": {"type": "string"},
                    "account_book_id": {"type": "string"},
                    "action_type": {"type": "string"},
                    "action_id": {"type": "string"},
                    "action_digest": {"type": "string"},
                },
                "required": [
                    "case_type", "case_id", "case_version", "company_id",
                    "account_book_id", "action_type", "action_id", "action_digest"
                ],
                "additionalProperties": False,
            },
        },
        "required": ["command_type", "payload"],
        "additionalProperties": False,
    },
}
