# MacSoft Agent Business Control Layer

## Scope and runtime

This document describes the Server-owned Client Skill API, the generic
AutoCount validator, Sales Invoice readiness, and the internal Tool Activity
bridge. The active runtime remains `C:\MacSoft-Agent\runtime`. The legacy
`%LOCALAPPDATA%\hermes` tree is not used or reactivated.

The product flow remains one Agent execution:

```text
Client -> MacSoft Server :8787 -> AI Service :8642 -> selected Skill
-> generic AutoCount tools -> AutoCount Cloud -> Local Connector
-> AutoCount Accounting -> MacSoft Server -> Client SSE
```

## Actual Skill loader behavior

The AI Service builds its global Skill index from the active home `skills`
directory and configured external Skill directories. This index is process-wide,
not owner-aware. A gateway reload endpoint can refresh the global index, but it
does not add tenant isolation. Plugin Skills are registered with qualified IDs
and are read-only explicit-load resources. The AutoCount plugin also injects its
protected execution policy through its `pre_llm_call` hook.

`SOUL.md` is read from `C:\MacSoft-Agent\runtime\SOUL.md` while the stable
system prompt is built. It owns product identity and global behavior. A Client
Skill never writes this file and cannot replace it.

The physical ownership model follows those loader constraints:

| Scope | Owner | Physical representation | Activation |
| --- | --- | --- | --- |
| System | MacSoft | `runtime\plugins\<plugin>\skills\<skill>\SKILL.md` and protected plugin policy | Plugin registration/startup |
| Public | Server administrator | `runtime\skills\<skill>\SKILL.md` | Global loader; use the existing reload endpoint or restart |
| Client | Authenticated MacSoft Server user | `client_skills` database row containing one Markdown document | Explicit selection for one authenticated chat request |

Public Skills are installed by an administrator only: validate the directory and
`SKILL.md`, place it under the active runtime `skills` directory, then use the
existing AI Service Skill reload function or restart the AI Service. There is no
Client mutation endpoint for System or Public Skills.

## Precedence, conflicts, and isolation

Effective control is:

```text
MacSoft Server protected capability policy
-> SOUL and stable system rules
-> System plugin policy and System Skills
-> administrator Public Skills
-> selected Client preferences
-> current user request
```

Later text cannot cancel protected rules. The Server wraps Client Skill text as
untrusted declarative preferences and states that SOUL, Tool permissions,
authentication, exact catalog/schema validation, secret handling,
no-fabrication, and no-blind-retry rules remain authoritative. IDs are generated
as `client:<authenticated-user-id>:<slug>`; the Client cannot supply an owner or
an effective ID. Selection queries always include the authenticated owner and
`enabled = 1`, so another owner's ID is ignored. A maximum of five Client Skills
and 65,536 selected content characters are injected into one request.

Client Skills are stored in MacSoft Server rather than written to the global
runtime. This avoids global cache leakage, path traversal, symlinks, binary
packages, executable entry points, and plugin registration. Activity and
messages do not persist the selected Skill document.

The packaged AI Service API Server uses an explicit `platform_toolsets`
allowlist containing only `macsoft_autocount`. The broad API Server default
(Web, browser, terminal, process, file mutation, Skill management, delegation,
memory, and automation Tools) is not exposed to MacSoft Client chat. Client
Skills remain Server-injected declarative guidance and do not need a runtime
Skill management Tool.

## Client Skill API

Every route requires the existing `Authorization: Bearer <device-token>` and
`X-Device-Id` headers.

| Method | Route | Responsibility |
| --- | --- | --- |
| `GET` | `/api/client/skills` | List metadata owned by the authenticated user |
| `POST` | `/api/client/skills/validate` | Validate without storing or enabling |
| `POST` | `/api/client/skills` | Create one Client Skill; duplicate owner/slug returns `409` |
| `GET` | `/api/client/skills/{slug}` | Read one owned Skill including content |
| `PATCH` | `/api/client/skills/{slug}` | Replace metadata/content and enable state |
| `DELETE` | `/api/client/skills/{slug}` | Delete one owned Skill |

Create request:

```json
{
  "slug": "concise-invoice-summary",
  "name": "Concise invoice summary",
  "description": "Presentation preference",
  "content": "Use a short Markdown summary after an invoice operation.",
  "enabled": true
}
```

Chat selection uses the existing additive `enabled_private_skills` request field:

```json
{
  "session_id": "session_123",
  "message": "Prepare the invoice summary.",
  "enabled_private_skills": [
    {"id": "client:user_123:concise-invoice-summary"}
  ]
}
```

Unknown, disabled, or differently owned IDs are ignored and never injected.
The Server does not add the Skill to message history or a later request unless
the Client selects it again.

### Declarative safety limits

- slug: 1-64 lowercase letters, numbers, and hyphens;
- name: 1-80 characters;
- description: at most 240 characters;
- content: 1-32,768 characters and at most 65,536 UTF-8 bytes;
- one JSON/UTF-8 Markdown document only;
- unknown package fields such as `files`, `manifest`, and `symlink` are rejected;
- control characters, parent-directory paths, executable-language fences,
  script markers, credential-shaped values, and protected-rule override text are
  rejected;
- duplicate slug is unique only within the authenticated owner scope.

Code fences that are not executable-language fences are reference text and
produce a warning. Client Skills cannot add files, dependencies, Tools, plugins,
network destinations, environment variables, or credentials.

## Generic AutoCount command control

The plugin has one generic sequence for every command:

```text
search official catalog
-> select one exact command type
-> fetch that command's current schema
-> build a candidate payload
-> validate without submission
-> ask for schema-supported missing information
-> execute only when valid
-> poll the official command result
-> report the confirmed result
```

`autocount_validate_command` is a generic Tool. The executor repeats exact
catalog resolution and validation as defense in depth before checking the
Connector or issuing `POST /v1/commands`. No additional MacSoft command allowlist
was introduced; official catalog presence and existing AutoCount authorization
remain authoritative.

An exact command comparison is case-sensitive. A guessed spelling is never run.
At most five similarity suggestions are returned so the Agent can inspect or ask
for clarification.

Validation returns:

```json
{
  "valid": false,
  "missing_fields": [],
  "unknown_fields": [],
  "type_errors": [],
  "location_errors": [],
  "suggestions": []
}
```

The validator supports JSON Schema properties, required fields, nested objects,
arrays, enums, minimum/maximum item counts, nullable values, scalar types, and
date format. It also supports the current descriptive `payloadSchema`, official
aliases, `examplePayload` type evidence, and `nativePayload` Master/Details field
metadata. It does not move values between Master and Details.

The current live `create-sales-invoice` metadata explicitly identifies required
root data and exposes Master/Details field names and types, but it does not mark
every Detail field as required or provide every enum/minimum constraint. The
validator deliberately does not invent missing requirements. The live schema
must be checked again before a controlled write.

## Retry policy

- deterministic validation failure: zero submission and zero automatic retry;
- missing user information: zero submission;
- alternate command spelling: zero execution;
- command `POST`: one attempt, never automatically replayed;
- transient GET (`URLError`, timeout, HTTP 429/502/503/504): one bounded retry;
- polling GET continues only for an already submitted command until a final
  status or the configured timeout.

The in-process invalid identity is SHA-256 over the Connector/Company context,
exact command type, canonical candidate payload, and validation result. Only
the hash is retained, with a 256-entry bound. A repeated identical failure returns
`duplicateSuppressed: true`; it still does not submit. New user data or a changed
official schema produces a different identity.

## Sales Invoice readiness and controlled test

Sales Invoice is the first validation fixture, not a command-specific code path.
Before a real controlled write, obtain:

1. explicit authorization to write to a named test company;
2. the intended Connector ID and Company ID mapping;
3. a known test debtor code;
4. official item codes, UOMs, quantities, prices, tax/location/project values
   only when the current schema requires them;
5. the intended document date and currency behavior;
6. an expected result range and a cleanup/reversal policy;
7. confirmation that no production customer data is used.

Controlled procedure:

1. Call connector status and confirm the approved test company is online.
2. Search the live catalog for Sales Invoice creation.
3. Select the exact returned command type; do not type variants.
4. Fetch its live schema and archive a sanitized schema fingerprint for the test.
5. Build the candidate only from approved test values and official aliases.
6. Call `autocount_validate_command`; stop on every reported issue.
7. Review the exact sanitized validation summary with the authorized tester.
8. Only after explicit write authorization, call the generic executor once.
9. Wait for the official final status; a queued status is not success.
10. Compare the returned document number, debtor, date, and total with AutoCount.
11. Apply the pre-approved cleanup/reversal procedure if required.

This implementation batch performed no real AutoCount write.

## Real Tool Activity bridge

For `activity-v1` requests only, MacSoft Server asks the existing AI Service
Chat Completions endpoint for an internal SSE stream. That stream and the final
assistant text come from the same Agent instance and same execution. Old Clients
continue using the previous non-streaming internal request and receive only the
three original Client events.

The Server parses only `tool`, `status`, and assistant text from the controlled
internal stream. It discards labels, call IDs, arguments, results, prompts, and
unknown events. The Activity Mapper currently recognizes:

- Skill selection;
- Connector status check;
- command catalog load;
- command schema load;
- payload validation;
- command execution.

Unknown Tools are not forwarded. A completion event proves only that the Tool
call returned; it does not prove business success unless the final official
result says so. The current upstream event has no sanitized validation outcome,
so Activity does not claim `validation failed` or `waiting for user` from Tool
completion alone. Coarse request/processing/finalization Activity remains the
truthful fallback when no recognized Tool event is emitted.

The external `activity-v1` schema, limits, ordering, failure isolation, and
ephemeral storage policy are unchanged.

## Result formatter recognition

The fallback formatter now transforms only recognized AutoCount command
envelopes, debtor/customer rows, invoice/document results, and known AutoCount
error envelopes. Arbitrary valid JSON is returned byte-for-byte. If the current
user explicitly requests JSON, even a recognized AutoCount envelope remains
JSON. Ordinary Markdown and prose remain unchanged. Recognized output removes
secret/internal fields and retains existing table/length bounds.

## Client work remaining

- add Client Skill list/create/edit/enable/delete UI against the Server API;
- select owned enabled Skill IDs in `enabled_private_skills` for each request;
- render optional Activity steps by `activity_id` and `sequence`;
- keep the existing loading state when Activity is absent;
- treat `server-hermes-current` only as an opaque protocol model ID and display
  a MacSoft product label instead;
- never connect to port 8642 or interpret internal Tool names.

## Test procedure

From `C:\MacSoft-Agent\server`:

```powershell
.\.venv\Scripts\python.exe -m unittest -v tests.test_client_skills tests.test_autocount_validator tests.test_activity_protocol
```

From `C:\MacSoft-Agent\hermes`, use the repository-required wrapper for the
existing AI Service lifecycle tests:

```bash
bash scripts/run_tests.sh tests/gateway/test_api_server.py -k "tool_lifecycle"
```

All AutoCount command tests use mocks and fixtures. They must not be changed to
perform a real write without explicit authorization.
