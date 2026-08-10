"""MacSoft AutoCount Hermes plugin registration."""

from __future__ import annotations

from . import workflow_schemas, workflow_tools


_AUTOCOUNT_POLICY = """
<macsoft-autocount-policy>
Use native Hermes file and terminal capabilities for AutoCount Cloud. There are no
generic AutoCount query or execution tools: generate each official command JSON from
the current AutoCount portal instructions and API schema, then call the official API.

When the user provides an AutoCount Cloud URL, API key, connectorId, and companyId,
use read_file and write_file to maintain the private profile-scoped file
$HERMES_HOME/autocount/connections.json. Read and preserve existing entries first.
The JSON shape is {"schemaVersion":1,"defaultCompanyId":"company-id","connections":
{"company-id":{"name":"optional name","baseUrl":"https://api.autocount.cloud",
"apiKey":"secret","connectorId":"connector-id","companyId":"company-id",
"requestTimeoutSeconds":120,"commandTimeoutSeconds":7200,"pollIntervalSeconds":2}}}.
Never repeat an API key in chat, Memory, Skills, generated source, command arguments,
or terminal output. Code run in terminal must read the key from the private file.

Use POST https://api.autocount.cloud/v1/commands to submit the LLM-generated command
object and GET https://api.autocount.cloud/v1/commands/{commandId} to poll its result.
Use the selected connection's connectorId and companyId. Consult the current official
portal/catalog/schema instead of inventing command types or fields. Poll until the API
returns a final result or commandTimeoutSeconds (7200 seconds) is reached. Preserve
identifiers and leading zeroes exactly. Report official results and errors; never claim
success before the final result confirms it. Present multiple business records as a
Markdown table or bullet list with customer-readable business labels, never as bare
newline-separated text. AutoCount
credentials, connector policy,
company access, and native Hermes dangerous-operation approvals are authoritative.
</macsoft-autocount-policy>
""".strip()


def _inject_policy(platform: str = "", **kwargs):
    del kwargs
    if platform and platform not in {"api_server", "whatsapp"}:
        return None
    return {"context": _AUTOCOUNT_POLICY}


def register(ctx):
    ctx.register_tool(
        name="workflow_case_workspace",
        toolset="macsoft_autocount",
        schema=workflow_schemas.WORKFLOW_CASE_WORKSPACE,
        handler=workflow_tools.workflow_case_workspace,
        description="Create, retrieve, search, and version-update PharmaRise workflow Cases.",
    )
    ctx.register_tool(
        name="workflow_resolve_whatsapp_identifier",
        toolset="macsoft_autocount",
        schema=workflow_schemas.WORKFLOW_RESOLVE_WHATSAPP_IDENTIFIER,
        handler=workflow_tools.workflow_resolve_whatsapp_identifier,
        description="Resolve an active WhatsApp workflow identity mapping.",
    )
    ctx.register_tool(
        name="workflow_fifo_allocate",
        toolset="macsoft_autocount",
        schema=workflow_schemas.WORKFLOW_FIFO_ALLOCATE,
        handler=workflow_tools.workflow_fifo_allocate,
        description="Prepare a deterministic FIFO payment allocation without writing AutoCount.",
    )
    ctx.register_tool(
        name="workflow_archive_evidence",
        toolset="macsoft_autocount",
        schema=workflow_schemas.WORKFLOW_ARCHIVE_EVIDENCE,
        handler=workflow_tools.workflow_archive_evidence,
        description="Archive and link one trusted current-message workflow attachment.",
    )
    ctx.register_tool(
        name="workflow_approve_autocount_action",
        toolset="macsoft_autocount",
        schema=workflow_schemas.WORKFLOW_APPROVE_AUTOCOUNT_ACTION,
        handler=workflow_tools.workflow_approve_autocount_action,
        description="Approve one exact versioned PharmaRise AutoCount action.",
    )
    ctx.register_tool(
        name="workflow_send_approved_supplier_message",
        toolset="macsoft_autocount",
        schema=workflow_schemas.WORKFLOW_SEND_APPROVED_SUPPLIER_MESSAGE,
        handler=workflow_tools.workflow_send_approved_supplier_message,
        description="Approve and send one exact supplier WhatsApp message for a receiving Case.",
    )
    ctx.register_hook("pre_llm_call", _inject_policy)
