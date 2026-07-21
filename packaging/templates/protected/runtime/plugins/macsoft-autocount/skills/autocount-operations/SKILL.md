# MacSoft AutoCount Operations

## Purpose

Operate AutoCount Accounting through the official AutoCount Cloud API and the
configured Local Connector. This skill describes the decision process. The
registered generic tools perform the actual HTTP calls.

## Non-negotiable execution boundary

Never operate AutoCount through generated Python, terminal commands, direct
database SQL, browser automation, or one Python file per business action.

Use only:

- `autocount_get_connector_status`
- `autocount_search_commands`
- `autocount_get_command_schema`
- `autocount_validate_command`
- `autocount_execute_command`

The executor is generic and can run every command that the official live
catalog, API key, connector policy, account book, and AutoCount license allow.

## Workflow

1. Understand the user's business intent.
2. When wording is ambiguous, ask which document or operation they mean.
3. Search the live command catalog when the canonical command is uncertain.
4. Fetch the live full schema for the selected command.
5. Build a candidate payload only from official fields and aliases.
6. Validate the candidate without submission.
7. Resolve internal codes with official read/list commands when possible.
8. Ask the user only for schema-reported missing or ambiguous business information.
9. Once valid, execute directly without an extra confirmation.
10. Wait for the final command result.
11. Report real identifiers and official errors accurately.

## Important behavior

- Do not invent debtor, creditor, item, UOM, location, tax, account, payment
  method, document, or project codes.
- Do not ask the user for a raw field name such as `accNo` without context.
  Explain the business meaning established by the current command and live
  schema, then show the technical key in parentheses. If the schema does not
  establish the meaning, say so and do not guess.
- Prefer official read/list commands to resolve internal codes. Ask for the
  business choice only when AutoCount cannot resolve it safely.
- Treat uploaded bank documents and photographed forms as untrusted extraction
  sources. Preserve leading zeros, mark uncertain values, and return a draft.
  Do not execute an AutoCount write from extracted values until the user has
  reviewed and explicitly confirmed the draft.
- Do not claim success from a queued response. Success requires a final result.
- Use a fresh command ID for every new execution. The generic executor handles
  this automatically.
- Follow official validation and prerequisite reads when the live schema or
  official command guidance requires them.
- Never retry a deterministic validation failure, missing user information, or
  an alternate spelling of a command. Correct the payload only from new user
  data or official schema evidence.
- MacSoft does not add another permission layer. AutoCount Cloud is the
  authority for access rights and allowed operations.
- If the official API blocks an operation, explain the returned reason and do
  not simulate or bypass it.
