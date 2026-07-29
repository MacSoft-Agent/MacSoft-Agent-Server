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
        },
        "required": ["command_type", "payload"],
        "additionalProperties": False,
    },
}

AUTOCOUNT_QUERY_DATA = {
    "name": "autocount_query_data",
    "description": (
        "Run one official read-only or report AutoCount command and return a bounded "
        "tabular result and result_ref. Analyze the returned real columns and rows to "
        "choose a chart, then use result_ref for charting; the Server retains the "
        "authoritative copy and never accepts model-supplied chart rows. "
        "Do not use this tool for write, edit, delete, or other mutating commands."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command_type": {
                "type": "string",
                "description": "Exact official AutoCount read or report command type.",
            },
            "payload": {
                "type": "object",
                "description": "Payload built exactly from the live official command schema.",
                "additionalProperties": True,
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 5,
                "maximum": 600,
                "description": "Optional total wait time for the final result.",
            },
        },
        "required": ["command_type", "payload"],
        "additionalProperties": False,
    },
}

AUTOCOUNT_CREATE_CHART = {
    "name": "autocount_create_chart",
    "description": (
        "Create a renderer-independent chart payload from a server-side AutoCount "
        "query result_ref. Choose a supported chart type and map only fields that "
        "exist in the query result. Encodings depend on chart type: line/area/scatter "
        "use x and y; bar uses category and value; pie/donut use category and value; "
        "gauge uses value, min, and max; calendar_heatmap uses date and value; table "
        "uses the query columns and rows. Do not return frontend or ECharts code."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "result_ref": {
                "type": "string",
                "description": "Opaque result_ref returned by autocount_query_data.",
            },
            "type": {
                "type": "string",
                "enum": [
                    "line",
                    "area",
                    "bar",
                    "horizontal_bar",
                    "pie",
                    "donut",
                    "gauge",
                    "calendar_heatmap",
                    "scatter",
                    "table",
                ],
                "description": "Supported renderer-independent chart type.",
            },
            "title": {
                "type": "string",
                "description": "Optional customer-readable chart title.",
            },
            "encodings": {
                "type": "object",
                "description": "Chart-type-specific field mapping.",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["result_ref", "type", "encodings"],
        "additionalProperties": False,
    },
}
