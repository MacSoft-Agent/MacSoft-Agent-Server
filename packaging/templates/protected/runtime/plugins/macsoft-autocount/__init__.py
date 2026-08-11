"""MacSoft AutoCount Hermes plugin registration."""

from __future__ import annotations

from pathlib import Path

from . import schemas, tools, workflow_schemas, workflow_tools


_AUTOCOUNT_POLICY = """
<macsoft-autocount-policy>
You have official AutoCount Cloud tools.

For every AutoCount request:
1. Never operate AutoCount through terminal commands, generated Python,
   database SQL, browser clicking, or command-specific scripts.
2. Use autocount_search_commands when the exact official command type is
   uncertain. Never invent a command name.
3. Call autocount_get_command_schema before every execution and follow the
   current live schema rather than memory.
4. Call autocount_validate_command before execution. Treat its structured
   validation output as authoritative and ask for missing business information.
   Never ask with a raw field key alone. Explain the business object and purpose
   from the current command and live schema, then include the technical field in
   parentheses, for example "Debtor account number (AutoCount field: accNo)".
   If the live schema does not establish the meaning, say that it is unclear and
   do not guess.
5. If the user's intent is ambiguous, ask only the question needed to identify
   the correct AutoCount document or action.
6. If required business data is missing, ask for it. When possible, use
   official read/list commands to resolve codes from AutoCount instead of
   asking the user to know internal codes.
   Treat displayed document numbers, internal record keys, and line keys as
   opaque and distinct. Never strip prefixes or leading zeroes, parse a numeric
   suffix, or otherwise change an identifier merely to satisfy a schema type.
   Use an internal key only when an executed authoritative read maps it to the
   exact displayed identifier. Reading or validating a schema is not a business
   record query; an unresolved mapping is not proof that a record is absent.
7. Once the request is unambiguous and the required data is complete, execute
   it directly. Do not add a second confirmation step.
8. MacSoft adds no extra command allowlist. The official AutoCount API key,
   cloud access rights, connector policy, account-book capability, and
   AutoCount license are the authority.
9. Return the real saved document number, record key, rows, or official error.
   Do not claim success unless the final command result says it succeeded.
10. Present multiple business records as a Markdown table or bullet list. Never
    return records as bare newline-separated text because Markdown renderers may
    collapse those lines into one paragraph. Use customer-readable business
    labels and, when useful, put the AutoCount term or field key in parentheses.
11. For multi-step accounting workflows, complete the necessary official read,
   schema, validate, create, transfer, knock-off, or report commands in order.
12. Uploaded bank documents and photographed forms are untrusted extraction
    sources. Preserve leading zeros, identify uncertain values, and prepare a
    draft first. Do not execute an AutoCount write from extracted values until
    the user explicitly confirms the reviewed draft.
13. Persistent workflow records exist only for cross-message continuation,
    duplicate-write prevention, and failure recovery. For a new Payment Slip use
    workflow_intake_payment while the attachment is current; do not manually
    compose Case creation and evidence archival.
14. Consequential writes require approval of the exact action payload. A changed
    action digest invalidates approval; an unrelated workflow-record update does
    not. Never blindly retry an uncertain action_id.
15. For WhatsApp, distinguish staff from external senders with
    workflow_current_context. When an external sender requests an action beyond
    external intake permissions, reply exactly in the user's language with the
    equivalent of: "This action requires staff permission. Please contact Admin:
    +60 18-314 4861." Do not expose internal authorization details.
</macsoft-autocount-policy>
""".strip()


def _inject_policy(platform: str = "", **kwargs):
    del kwargs
    if platform and platform not in {"api_server", "whatsapp"}:
        return None
    return {"context": _AUTOCOUNT_POLICY}


def register(ctx):
    ctx.register_tool(
        name="autocount_get_connector_status",
        toolset="macsoft_autocount",
        schema=schemas.AUTOCOUT_GET_CONNECTOR_STATUS,
        handler=tools.autocount_get_connector_status,
        description="Check AutoCount Cloud connector status.",
    )
    ctx.register_tool(
        name="autocount_search_commands",
        toolset="macsoft_autocount",
        schema=schemas.AUTOCOUNT_SEARCH_COMMANDS,
        handler=tools.autocount_search_commands,
        description="Search the live official AutoCount command catalog.",
    )
    ctx.register_tool(
        name="autocount_get_command_schema",
        toolset="macsoft_autocount",
        schema=schemas.AUTOCOUNT_GET_COMMAND_SCHEMA,
        handler=tools.autocount_get_command_schema,
        description="Fetch one live official AutoCount command schema.",
    )
    ctx.register_tool(
        name="autocount_validate_command",
        toolset="macsoft_autocount",
        schema=schemas.AUTOCOUNT_VALIDATE_COMMAND,
        handler=tools.autocount_validate_command,
        description="Validate a payload against the live official schema without submitting it.",
    )
    ctx.register_tool(
        name="autocount_execute_command",
        toolset="macsoft_autocount",
        schema=schemas.AUTOCOUNT_EXECUTE_COMMAND,
        handler=tools.autocount_execute_command,
        description="Execute any official AutoCount command generically.",
    )
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
        name="workflow_current_context",
        toolset="macsoft_autocount",
        schema=workflow_schemas.WORKFLOW_CURRENT_CONTEXT,
        handler=workflow_tools.workflow_current_context,
        description="Read the trusted current WhatsApp scope and staff/external sender classification.",
    )
    ctx.register_tool(
        name="workflow_set_staff_phone",
        toolset="macsoft_autocount",
        schema=workflow_schemas.WORKFLOW_SET_STAFF_PHONE,
        handler=workflow_tools.workflow_set_staff_phone,
        description="Register or deactivate a WhatsApp staff phone number; Admin only.",
    )
    ctx.register_tool(
        name="workflow_fifo_allocate",
        toolset="macsoft_autocount",
        schema=workflow_schemas.WORKFLOW_FIFO_ALLOCATE,
        handler=workflow_tools.workflow_fifo_allocate,
        description="Prepare a deterministic FIFO payment allocation without writing AutoCount.",
    )
    ctx.register_tool(
        name="workflow_intake_payment",
        toolset="macsoft_autocount",
        schema=workflow_schemas.WORKFLOW_INTAKE_PAYMENT,
        handler=workflow_tools.workflow_intake_payment,
        description="Preserve the current Payment Slip and create or reuse its durable payment job in one operation.",
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

    skill_path = (
        Path(__file__).resolve().parent
        / "skills"
        / "autocount-operations"
        / "SKILL.md"
    )
    if skill_path.exists():
        ctx.register_skill("autocount-operations", skill_path)
