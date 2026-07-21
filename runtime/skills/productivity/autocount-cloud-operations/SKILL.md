---
name: autocount-cloud-operations
description: Use when reading or writing AutoCount data through the official AutoCount Cloud connector. Resolve the exact official command first, fetch the live schema before every execution, and report only real saved records or official errors.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [autocount, accounting, connector, debtor, creditor, schema-driven, macsoft]
    related_skills: [airtable, notion]
---

# AutoCount Cloud Operations

## Overview

Use this skill for any task that touches AutoCount through the official AutoCount Cloud tools. The core discipline is schema-first execution: identify the exact official command, read the live schema for that command immediately before execution, fill the payload exactly as the live contract expects, and trust only the final official result.

This skill exists to prevent three common mistakes: inventing command names, skipping live schema lookup because a command feels familiar, and claiming success before the connector returns a saved record or official error.

## When to Use

Use when:
- The user asks to check AutoCount connector status, company/database binding, or account-book availability.
- The user asks to list, read, create, update, void, delete, validate, or report AutoCount records.
- You need to discover the correct debtor, creditor, stock, sales, purchase, AR, AP, or report command.
- You need to confirm whether a write really saved.

Do not use for:
- Direct database SQL against AutoCount tables.
- Browser-driving the AutoCount UI.
- Terminal scripts or generated Python that try to bypass the official AutoCount command surface.

## Core Workflow

1. Clarify only the minimum needed to identify the intended AutoCount object or action.
Completion criterion: you know exactly what business object the user wants and whether the task is read, write, edit, delete, void, validate, or report.

2. Check command identity.
- If the exact official command type is uncertain, call `autocount_search_commands` with a natural-language query.
- Never invent command names from memory.
Completion criterion: you have one exact official `command_type`.

3. Read the live schema immediately before execution.
- Call `autocount_get_command_schema` for the chosen `command_type` every time, even if you used the command earlier in the session.
- Use the returned fields and aliases as the only payload contract.
Completion criterion: required fields and accepted aliases are known from the live schema you just fetched.

4. Resolve required business data.
- If codes are missing and an official read/list command can discover them, use AutoCount reads instead of asking the user to know internal codes.
- Ask the user only for business data that cannot be discovered automatically.
Completion criterion: every required payload value is present or the missing value has been explicitly requested.

5. Execute through the official command executor only.
- Use `autocount_execute_command` with the exact `command_type` and a payload built from the live schema.
- For writes, do not add a second confirmation turn once the request is unambiguous and complete.
Completion criterion: AutoCount returns a final result, not merely a queued command.

6. Verify the result based on operation type.
- Reads: confirm the returned rows, fields, or document details.
- Writes: report success only if the final result says it saved or updated. When practical, verify with an official read command.
- Failures: return the official error message and the command id.
Completion criterion: the user gets grounded output tied to the actual result.

## Status and Capability Checks

For connector-health questions:
- Start with `autocount_get_connector_status`.
- Report whether the connector is online, which companies are configured, which database/server each company uses, and whether the company is active/default.
- Surface license uncertainty explicitly. `writeApiLicenseStatus: unknown` means read access may work while create/edit/void/delete may still fail.

Good response shape:
- Connector online/offline status
- Connector id
- Last heartbeat / age
- Version vs latest version
- Company id
- Database and SQL Server
- Active/default flags
- Write-license status if present

## Read Patterns

For list/read requests:
- Prefer the narrowest official read command that answers the question.
- When the command returns only summary columns, tell the user exactly which fields were returned instead of implying richer data exists.
- If the user wants fields absent from the list response, switch to the appropriate detail command and say you are doing so.

Example pattern:
- `read-debtors` for account codes and company names.
- `get-debtor-detail` when the user needs full debtor fields.

## Write Patterns

For create/update operations:
- Build the payload from the live schema, but prefer field aliases that match the connector's accepted command-value names when aliases are provided.
- After a successful write, report the key saved identifiers immediately: account code, document number, record key, company name, saved/updated flags, and command id.
- When practical, follow with an official read command to verify the record that was written.

Reference: see `references/create-debtor-aliases.md` for an observed live payload-alias quirk on debtor creation.

## Response Style for AutoCount Work

- Be concise and operational.
- Lead with the result first: online/offline, found/not found, saved/failed.
- Then give the key business fields the user asked for.
- Include the company/database when it helps orient the user.
- Include `commandId` on writes and on meaningful failures.
- Do not pad the reply with process explanation unless the user asks.

## Common Pitfalls

1. Skipping command discovery.
Fix: if the exact official command type is not certain, run `autocount_search_commands` first.

2. Reusing an old schema from memory.
Fix: call `autocount_get_command_schema` immediately before every execution.

3. Treating schema field labels as the only acceptable payload keys.
Fix: inspect aliases and prefer the live alias form the connector expects; when a write fails with a missing command value for a lower-camel alias, retry with the schema alias form instead of abandoning the operation.

4. Claiming a write succeeded because the command reached `done`.
Fix: inspect the nested result and confirm `ok: true` plus saved or updated indicators.

5. Hiding license uncertainty.
Fix: when write license status is unknown, say so plainly; do not promise writes will work until the command actually succeeds.

6. Over-asking the user for internal codes.
Fix: use official read/list commands to discover debtor, creditor, stock, or document identifiers whenever possible.

## Verification Checklist

- [ ] Exact official command identified
- [ ] Live schema fetched for this exact command immediately before execution
- [ ] Payload built from returned fields/aliases rather than memory
- [ ] Result reported from actual command output, not expectation
- [ ] Writes confirmed by saved/updated indicators and, when practical, an official follow-up read
- [ ] Reply includes the key business identifiers and relevant command id
