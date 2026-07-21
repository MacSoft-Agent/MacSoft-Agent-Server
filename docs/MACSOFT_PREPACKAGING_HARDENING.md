# MacSoft Pre-packaging Hardening

## Scope

This batch adds authenticated, idempotent session soft deletion and a protected
capability boundary for live external information. It does not change the
external Client repository, add a weather/Web provider, create a second Agent
execution path, or execute an AutoCount write.

The product request path remains:

```text
Client -> MacSoft Server :8787 -> AI Service :8642
-> MacSoft AutoCount plugin -> AutoCount Cloud -> Local Connector
-> AutoCount Accounting -> MacSoft Server -> Client SSE
```

## Session soft-delete API

`DELETE /api/sessions/{session_id}` requires the existing device headers:

```text
Authorization: Bearer <device-token>
X-Device-Id: <device-id>
```

Successful response:

```json
{
  "ok": true,
  "action": "delete_session",
  "session_id": "session_123",
  "deleted": true,
  "delete_mode": "soft",
  "deleted_at": "2026-07-14T12:00:00+00:00"
}
```

Deleting the same owned session again returns `ok: true`, `deleted: false`,
`reason: already_deleted`, and the original `deleted_at` value. Unknown sessions
return `404 session_not_found`;
sessions owned by another authenticated user return `403 permission_denied`;
invalid or revoked devices continue returning `401 invalid_device_token`.

Soft deletion sets nullable `sessions.deleted_at` and updates `updated_at`.
Session and message rows remain physically present. Normal session listing,
message history, session lookup, chat execution, and message append operations
all require `deleted_at IS NULL`. This makes deleted sessions inaccessible to
the normal Client while preserving data for future administrator retention or
purge policy.

## Database migration and rollback

`macsoft.db.init_db()` is the single schema owner. It creates sessions/messages
for a new installation and adds `deleted_at` with SQLite `ALTER TABLE` when an
existing database lacks the column. Existing rows receive `NULL`, so all
existing sessions remain active. The legacy `fix_stage3_schema.py` delegates to
`init_db()` and no longer contains a competing DDL copy.

Before this batch, the active database and affected configuration/source files
were copied to:

```text
C:\MacSoft-Agent\backup\pre_session_capability_hardening_20260714_114550
```

After confirming ports `8787` and `8642` were not listening, the same tested
migration was applied to the active database. Normal MacSoft Server startup also
runs this idempotent migration. To roll back, stop MacSoft Server, verify the
timestamped snapshot, restore the database and matching source/configuration,
then restart. Do not restore while SQLite is in use.

## Protected capability boundary

MacSoft Server prepends one protected system instruction to every authenticated
chat request. It has higher precedence than Public Skills, request-scoped Client
Skills, and user content. Client Skill content is included in the same system
instruction as explicitly untrusted declarative guidance.

The policy allows general explanations, writing, office assistance, analysis of
user-provided information, and approved AutoCount operations. It prohibits a
claim about current weather, news, market prices, exchange rates, traffic,
sports results, or another external fact unless a category-approved Tool from
the same Agent run produced a verified successful result.

Model memory, a Skill instruction, a raw Tool call, and transport-level Tool
completion are not accepted as success evidence. No general live-data Tool is
approved in this batch. Therefore the Server replaces a model-generated live
claim with concise Markdown explaining the limitation and a safe next action
before emitting `token_delta` or persisting the assistant message.

The final check is not a single keyword denylist. It requires a recognized live
external category plus an explicit current-time intent or a category-specific
live-query form. Requests for static explanation, templates, examples, and
analysis of attached/provided text remain allowed. The model policy and runtime
Tool allowlist are the primary controls; final-response classification is
defense in depth.

## Packaged Tool boundary

The AI Service default `hermes-api-server` composite includes Web
search/extraction, browser automation, terminal/process execution, file reads
and writes, Skill management, memory, delegation, image generation, automation,
and other general Tools. Those are not approved for the MacSoft packaged Client
chat surface.

Both active and example runtime configuration now declare:

```yaml
platform_toolsets:
  api_server:
    - macsoft_autocount
```

Runtime resolution must produce exactly these Tools:

- `autocount_get_connector_status`
- `autocount_search_commands`
- `autocount_get_command_schema`
- `autocount_validate_command`
- `autocount_execute_command`

Web search, browser, terminal, process, file mutation, Skill management, memory,
delegation, and automation must remain absent unless a future reviewed product
requirement explicitly approves a narrower integration.

## SSE and compatibility

Session deletion adds an independent REST route. The chat route remains
`POST /api/chat/stream`, and the Client still connects only to port `8787`.
The existing `message_start`, `token_delta`, and `message_done` event names and
payload meanings do not change. `activity-v1` negotiation and Tool Activity
remain additive. Capability enforcement runs before the final text is emitted
and persisted in both legacy and `activity-v1` paths.

No Activity claims a live Tool result that was not observed in the same Agent
run. No hidden reasoning, prompts, secrets, raw Tool payloads, stack traces, or
local paths are exposed.

## Client implementation reference

The Client may add a delete action that calls the Server route with its existing
device authentication. On success it should remove the session from its local
list and navigate away if that session is open. Repeating the request is safe.
No Client change is required for chat or SSE fallback.

The Client should render Server Markdown limitations normally. It must not
interpret them as Tool Activity or attempt to contact port `8642` directly.

## Test procedure

1. Start from a copied legacy database without `deleted_at`; run `init_db()` and
   confirm sessions/messages and contents are unchanged.
2. Delete an owned session; verify success and a stable timestamp on repeat.
3. Verify list, history, chat, and direct message append no longer expose or
   modify the deleted session.
4. Verify session/message rows remain physically present.
5. Verify another owner receives `403`, an unknown ID receives `404`, and an
   invalid device receives `401`.
6. Run legacy and `activity-v1` chats with a mocked confident live-weather
   answer; verify a limitation is emitted and persisted.
7. Select a conflicting Client Skill and verify it cannot override the protected
   boundary.
8. Resolve the active API Server Toolsets and verify only the five AutoCount
   Tools above are present.
9. Run the full MacSoft Server test suite and compile every Server Python file
   without writing bytecode.

## Future work

A future live-data integration needs an explicit product decision, a narrowly
scoped Tool, credential/host controls, sanitized result schema, category mapping,
and a verified success event from the same Agent run. Only then may that Tool be
added to both the runtime allowlist and `APPROVED_LIVE_TOOLS_BY_CAPABILITY`.

Administrator retention, restore, audit, and permanent purge policy for deleted
sessions remains a separate batch. Physical purge must never be added to the
normal Client delete route.
