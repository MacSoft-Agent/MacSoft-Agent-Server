---
name: autocount-operations
description: Discover, validate, execute, and verify official AutoCount Cloud operations through the configured Connector, while preserving exact identifiers, live schema authority, workflow approval, and real result reporting.
---

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
- `workflow_approve_autocount_action`
- `workflow_execute_approved_autocount_action`

The executor is generic and can run every command that the official live
catalog, API key, connector policy, account book, and AutoCount license allow.

## Workflow

### Company workflow routing takes priority

Before applying the generic ambiguity rule below, identify whether the request
is evidence intake for an established company workflow.

- A newly received customer Payment Slip, transfer proof, or payer-side receipt
  routes to `autocount-payment-knockoff-automation`. It creates the pending
  payment record and waits for bank-side evidence; do not replace this with a
  menu of accounting commands.
- A later Bank Transaction or Bank Statement for customer-payment verification
  also routes to `autocount-payment-knockoff-automation`, which searches pending
  records before invoice allocation.
- Supplier invoice, delivery, receiving, PO, CN, Batch, or Expiry evidence routes
  to `autocount-receiving-supplier-invoice-automation`.

The generic command workflow applies only after the owning business Skill
reaches an AutoCount read or write step.

1. Understand the user's business intent.
2. When wording is ambiguous, ask which document or operation they mean.
3. Search the live command catalog only when the canonical command is uncertain. A command explicitly named by an active packaged workflow Skill is already resolved.
4. Fetch the live full schema for a newly prepared action; reuse the established schema for that same action.
5. Build a candidate payload only from official fields and aliases.
6. Validate the candidate without submission.
7. Resolve internal codes with official read/list commands when possible.
8. Ask the user only for schema-reported missing or ambiguous business information.
9. For a consequential workflow write, persist/approve the exact action, then execute it by stable `action_id` only. For ordinary commands, execute directly without an extra confirmation.
10. Wait for the final command result.
11. Report real identifiers and official errors accurately.

## Identifier and payload resolution

The live command schema is authoritative for accepted payload shape and type, but a type requirement does not prove that two business identifiers are equivalent.

| Identifier | Meaning | Rule |
|---|---|---|
| `docNo` / displayed document number | Human-visible value such as `PO-000001` | Preserve the complete value, including prefix, punctuation, and leading zeroes. |
| `docKey` / `autoKey` | Internal numeric record key | Use only a value returned by an authoritative live read for that exact record. |
| line/detail key | Internal line identity | Use only the key returned with the resolved parent document and line. |

When evidence supplies a displayed identifier but a detail command accepts only a numeric internal key:

1. do not strip the prefix, parse the numeric suffix, hash, truncate, or otherwise coerce the displayed value;
2. execute an available official list/search/read command that accepts compatible criteria;
3. exact-match the returned displayed identifier and relevant company/account-book context;
4. use only the internal key returned by that matched record;
5. if no supported command establishes the mapping, report the record as unresolved because of an interface limitation, not absent.

Reading `autocount_get_command_schema` discovers capability; it does not query business records. Passing `autocount_validate_command` proves payload conformance only; it does not prove identifier meaning, record existence, or business correctness. Never claim a search ran after only reading or validating its schema.

## Official discovery sources

When general AutoCount documentation is too broad, consult these exact official
machine-readable sources instead of browsing the site at random:

- `https://api.autocount.cloud/developers/recipes.json` for supported business recipes and sequences.
- `https://api.autocount.cloud/ai/manifest.json` for the AI command catalog, payload guidance, aliases, and examples.
- `https://api.autocount.cloud/ai/autocount-ontology.json` for AutoCount business terms and relationships.
- `https://api.autocount.cloud/openapi.json` for the HTTP contract.

Use them for discovery and explanation. When preparing a new action, the current
live command schema and its validator remain authoritative. Do not rediscover
metadata after the exact action is persisted and approved. If an example or static
document advertises a field that the live validator rejects, report the
connector mismatch and do not force the field into a write.

## Conversation and evidence handling

- Treat the user like a business colleague. Use plain business language first;
  include an AutoCount field name only in parentheses when it helps diagnosis.
- State what was understood, what is still missing, and the next action. Ask one
  focused question at a time when that is enough to continue.
- Use short numbered steps, bullets, or a Markdown table for records and
  comparisons. Do not return a dense paragraph of codes and values.
- For a received image, screenshot, scan, PDF, or spreadsheet, inspect the
  actual attached media before relying on its contents. Preserve leading zeros
  and clearly mark unreadable or uncertain values.
- If the channel reports that media could not be downloaded, or no usable media
  path/content is present, say that the attachment was not received and ask the
  user to resend it. Do not describe, extract, match, or post from an image that
  was never available to the Agent.
- A caption or filename is context, not proof of the document contents.
- When extracted evidence could cause an accounting write, show a compact draft
  of the material facts and obtain the applicable workflow approval before the
  write.
- Distinguish clearly between `received`, `read`, `matched`, `validated`,
  `approved`, `submitted`, and `verified`. Never collapse these into
  "completed".

## Important behavior

- Do not invent debtor, creditor, item, UOM, location, tax, account, payment
  method, document, or project codes.
- Do not ask the user for a raw field name such as `accNo` without context.
  Explain the business meaning established by the current command and live
  schema, then show the technical key in parentheses. If the schema does not
  establish the meaning, say so and do not guess.
- Prefer official read/list commands to resolve internal codes. Ask for the
  business choice only when AutoCount cannot resolve it safely.
- Treat document numbers, record keys, and line keys as opaque and distinct.
  Never change an identifier merely to satisfy a schema type. Resolve any
  mapping through an executed authoritative read.
- Present multiple business records as a Markdown table or bullet list. Never
  use bare newline-separated records because Markdown renderers may collapse
  them into one paragraph. Use customer-readable business labels and, when
  useful, include the AutoCount term or technical field in parentheses.
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
