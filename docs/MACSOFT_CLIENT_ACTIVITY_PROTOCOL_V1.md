# MacSoft Client Activity Protocol v1

## Purpose and architecture

MacSoft Server owns the Client-facing chat protocol. The execution path remains:

```text
Client -> MacSoft Server :8787 -> AI Service :8642
-> MacSoft AutoCount plugin -> AutoCount Cloud -> Local Connector
-> AutoCount Accounting -> MacSoft Server -> Client SSE
```

`POST /api/chat/stream` remains the only Client chat route. The Client must not connect to the internal AI Service. Activity is an optional, ephemeral SSE view of observable Server state. It is not stored as a message and is not a second execution path.

## Capability negotiation

A supporting Client sends:

```http
X-MacSoft-Client-Capabilities: activity-v1
```

The value is a comma-separated, case-insensitive capability list. Unknown values are ignored. Values longer than 512 characters are treated as unsupported. The header was selected instead of `client_info` because it is transport metadata, does not become conversation content, does not revise the request-body schema, and is safely ignored by an older Server. It is included in the CORS allow-list.

| Client | Server | Result |
| --- | --- | --- |
| Old | New | Existing `message_start`, `token_delta`, and `message_done` events only |
| New | Old | Unknown header is ignored; Client uses its normal loading fallback |
| New | New | Existing events plus optional `activity` events |

For requests without `activity-v1`, the Server also retains the previous error transport: an unavailable internal AI Service returns HTTP 502 before SSE starts. Activity-capable requests can instead receive a sanitized failure Activity and final readable assistant message because their stream starts before the internal request.

## Activity Contract v1

```text
event: activity
data: {
  "version": 1,
  "message_id": "msg_assistant_...",
  "activity_id": "agent_processing",
  "sequence": 2,
  "kind": "external_request",
  "status": "started",
  "title": "MacSoft Agent is processing the request",
  "detail": null,
  "progress": null,
  "timestamp": "2026-07-14T02:30:00+00:00"
}
```

| Field | Type | Responsibility |
| --- | --- | --- |
| `version` | integer | Contract version; v1 is always `1` |
| `message_id` | string | Same assistant message ID as `message_start` |
| `activity_id` | string | Stable logical step ID; later events update the same step |
| `sequence` | integer | Strictly increasing within one assistant message |
| `kind` | string | `analysis`, `tool`, `validation`, `external_request`, `finalize`, `warning`, or `user_input` |
| `status` | string | `started`, `updated`, `completed`, `failed`, or `waiting_user` |
| `title` | string | Sanitized user text, maximum 120 characters |
| `detail` | string or null | Optional sanitized explanation, maximum 500 characters |
| `progress` | number or null | Real progress from 0 to 100; `null` when it is not measured |
| `timestamp` | ISO 8601 string | Server timestamp for ordering and administration |

Clients must ignore unknown fields, kinds, and statuses.

## Ordering, failure isolation, and limits

The successful activity-capable flow is:

```text
message_start
activity: Request received
activity: MacSoft Agent is processing the request
activity: MacSoft Agent finished processing
activity: Preparing the response
activity: Response prepared
token_delta
activity: Request completed
message_done
```

- Existing event names, payload fields, and meanings are retained.
- `message_done` remains the final SSE event.
- The mapper closes before `message_done`; Activity cannot appear later.
- The limit is 20 Activity events per message.
- Identical repeated state for one `activity_id` is suppressed.
- Titles are limited to 120 characters and details to 500 characters.
- There is no token-level or Agent-loop-level Activity.
- `progress` stays `null` unless a source reports a real percentage.
- Mapping failure is logged by error type and cannot stop token delivery, final message persistence, or `message_done`.

## Truthful Tool lifecycle integration

For an Activity-capable request, MacSoft Server now consumes the existing
internal AI Service SSE stream. Tool lifecycle and the final assistant text come
from the same Agent run. The Server does not start a second run. Requests without
the capability keep the previous non-streaming internal call and external
contract.

Only recognized observable Tool starts/completions are mapped. The Server drops
internal labels, call IDs, arguments, results, unknown Tools, and reasoning
events. Current mappings cover Skill selection and the generic AutoCount
Connector, catalog, schema, validation, and execution Tools. Coarse processing
stages remain available when no recognized Tool event appears.

A Tool completion means that the Tool call returned. It is not automatically a
business success. The current controlled internal event does not contain a safe
validation outcome, so the Server does not claim `validation failed`,
`waiting_user`, or document success from lifecycle alone. Final business status
comes from the assistant answer based on the official Tool result.

## Security and privacy boundary

Activity is observable state, not model reasoning. It must never contain hidden reasoning, prompts, scratchpads, raw Tool arguments, complete AutoCount payloads, secrets, authentication headers, device tokens, stack traces, local absolute paths, implementation class names, or unnecessary customer data.

The mapper accepts only explicit Server-observed states. It removes control characters, credential-shaped text, Bearer tokens, stack traces, and Windows absolute paths. The chat route logs only the error class for internal AI Service failures.

## Message storage

Activity is ephemeral in v1. The Server continues storing only the normal user message and final assistant Markdown in the existing messages table. No database migration or Activity metadata column is added. Refresh may lose the Activity timeline; existing session history retains the final business result.

## Readable business results

Activity describes what is happening. The final answer describes what was found, created, or rejected.

Normal Markdown from the Agent is preserved. The Server applies the bounded
fallback formatter only to a recognized AutoCount envelope, debtor/customer
result, invoice/document result, or known AutoCount error:

- successful lists become a summary and Markdown table;
- successful objects become short labeled fields;
- known AutoCount failures become a title, reason, and recommended action;
- secret and internal fields are omitted;
- tables are limited to 50 rows, 8 scalar columns, and 160 characters per cell;
- normal prose and Markdown are not reinterpreted.
- arbitrary valid JSON is not reinterpreted;
- an explicit current-user request for JSON preserves recognized business JSON.

Preferred examples:

```markdown
## Customer records

Found 13 records.

| Debtor Code | Company Name |
| --- | --- |
| D-001 | Example Sdn Bhd |
```

```markdown
## AutoCount Connector is offline

**Reason**

The configured Local Connector is not currently available.

**Recommended action**

Start the Local Connector and verify the configured Connector ID.
```

## Client reference and fallback

1. Send the capability header on `POST /api/chat/stream`.
2. Continue handling the three existing events exactly as before.
3. Associate Activity with `message_id` and upsert the visible step by `activity_id`.
4. Order updates by `sequence`; ignore an update older than the displayed state.
5. Ignore unknown fields, kinds, statuses, and capabilities.
6. If no Activity arrives, retain the existing loading state.
7. Do not persist Activity as assistant message text.

## Test procedure

From `C:\MacSoft-Agent\server`:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The focused suite verifies legacy event behavior, negotiation, required fields, monotonic sequence, no Activity after `message_done`, mapping-failure isolation, device authentication, session and message persistence, secret removal, AutoCount error mapping, and JSON-to-Markdown formatting.
