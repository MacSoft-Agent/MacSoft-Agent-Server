# MacSoft-to-Hermes Compatibility Contract

Status: Batch 1 evidence for technical review

Product authority: `product.json`

Accepted Hermes baseline: `v2026.7.7.2` at
`79f12748022817a7c4f3fee747e45e9e6979214a`

## Purpose and scope

This document records the Hermes boundaries that the current MacSoft Agent
code actually depends on. It is narrower than the whole MacSoft product
contract: pairing, Thin Client authorization, Server session isolation,
AutoCount business rules, and customer data ownership remain MacSoft
contracts. They are listed here only when a Hermes change can regress their
execution path.

The current code, schemas, tests, lock files, and `product.json` remain
authoritative. This document is updated whenever the accepted Hermes baseline
or a boundary below changes.

## Runtime topology

The installed product has four Host-managed local services:

| Port | Owner | Process/entry point | Purpose |
| --- | --- | --- | --- |
| `8766` | MacSoft Host | `product_runtime.macsoft_runtime.service` | Authenticated lifecycle and diagnostic control |
| `8643` | Hermes-derived configuration backend | `python -m hermes_cli.main serve` | Model, provider, authentication, and configuration only |
| `8642` | Hermes API Server | `python -m hermes_cli.main gateway run` | Agent execution used by MacSoft Server |
| `8787` | MacSoft Server | `python -m macsoft.server` | Thin Client and Server Desktop Admin API |

`product_runtime/macsoft_runtime/host.py::build_service_specs` is the authority
for commands, working directories, environment variables, health identities,
and ports. The Host starts the configuration backend before the AI Service and
starts both before MacSoft Server.

## A. Direct Hermes boundary contracts

### A1. Host to Hermes process and path contract

**Caller**

- `product_runtime/macsoft_runtime/host.py::build_service_specs`
- `product_runtime/macsoft_runtime/host.py::MacSoftAgentHost`

**Hermes implementations**

- `hermes/hermes_cli/main.py::cmd_dashboard` for `serve`
- `hermes/hermes_cli/main.py` gateway command dispatch
- `hermes/hermes_cli/web_server.py` for the configuration backend
- `hermes/gateway/platforms/api_server.py::APIServerAdapter` for AI Service

**Inputs**

- Python interpreter and `PYTHONPATH` selected by `ProductPaths`.
- `HERMES_HOME` points to the MacSoft-owned writable runtime directory.
- `MACSOFT_PRODUCT_METADATA` points to the immutable installed
  `product.json`.
- Configuration backend additionally receives `HERMES_CONFIG_ONLY=1` and
  `HERMES_DASHBOARD_SESSION_TOKEN`.
- MacSoft Server receives the API Server key through
  `MACSOFT_HERMES_API_KEY`.

**Development mode**

- Program root: repository root.
- Hermes code and working directory: `<repo>/hermes`.
- Interpreter: `<repo>/hermes/venv/Scripts/python.exe`.
- Writable runtime: `<repo>/runtime`.
- Server data/config: `<repo>/server`.

**Packaged mode**

- Program root: normally `C:\Program Files\MacSoft Agent`.
- Hermes code and working directory: `<program>\ai-service`.
- Interpreter: `<program>\python\python.exe`.
- Writable runtime: `C:\ProgramData\MacSoft Agent\runtime`.
- Server data/config: `C:\ProgramData\MacSoft Agent\server`.
- Logs, Host state, backups, and configuration are under ProgramData.

**Failure behavior**

- A required port already owned by an unrelated process is not adopted or
  killed.
- A child that exits or fails its identity health check is stopped and reported
  as an error.
- Host restart attempts are bounded to three within five minutes.
- Child output is written to bounded, redacted logs.

**Tests**

- `product_runtime/tests/test_host.py`
- `product_runtime/tests/test_metadata_paths.py`
- `product_runtime/tests/test_initializer.py`
- `product_runtime/tests/test_packaging_contract.py`

**Affected behavior if changed**

All installed service startup, Desktop settings access, AI execution, Server
chat, and packaged writable-state isolation.

### A2. Host to Hermes health contract

**Configuration backend**

- Request: `GET http://127.0.0.1:8643/api/status`
- Authentication: Host-generated bearer token.
- Required identity: JSON field `runtime_mode` equals `config-only`.
- Current implementation:
  `hermes/hermes_cli/web_server.py::get_status`.

**AI Service**

- Request: `GET http://127.0.0.1:8642/health`
- Authentication: none for this liveness route.
- Required identity: `status == "ok"` and
  `platform == "hermes-agent"`.
- Current response also contains the Hermes version.
- Current implementation:
  `hermes/gateway/platforms/api_server.py::_handle_health`.

**Timing**

- Host service startup health deadline: 60 seconds.
- Individual health request timeout: 1.5 seconds.
- Desktop waits up to 45 seconds for the configuration backend.

**Current limitation**

These checks prove identity and liveness, not exact MacSoft compatibility. A
different Hermes build that retains the same fields can pass.

**Tests**

- `product_runtime/tests/test_host.py`
- `hermes/tests/gateway/test_api_server.py` health tests
- `hermes/apps/desktop/electron/backend-ready.test.ts`
- `hermes/apps/desktop/electron/macsoft-host-client.test.ts`

### A3. MacSoft configuration-only Hermes backend

**Caller**

- `hermes/apps/desktop/electron/main.ts::ensureBackend`
- Renderer calls through `hermes:api`.

**Implementation**

- `hermes/hermes_cli/main.py::cmd_dashboard`
- `hermes/hermes_cli/web_server.py::_config_only_http_path_allowed`
- `hermes/hermes_cli/web_server.py::config_only_route_boundary`

**Allowed HTTP surface in config-only mode**

- `GET /api/status`
- `/api/config`
- `/api/config/defaults`
- `/api/config/schema`
- `/api/env`
- `/api/env/reveal`
- `/api/providers/validate`
- `/api/providers/oauth`
- `/api/model/*`
- `/api/providers/oauth/*`

The exact HTTP verb and schema for each settings call remain defined by its
handler in `web_server.py` and by the Renderer caller. All other HTTP paths
return `404` in config-only mode. Embedded chat, PTY, filesystem, session, Tool,
Skill, and Agent execution surfaces are disabled. Gateway warming, PTY
initialization, and the PTY reaper are also skipped.

**Authentication**

The Host control secret is reused as the localhost-only dashboard session
token. Electron main reads it from the Host control file and adds it to backend
requests. It is not exposed to the Renderer.

**Desktop request behavior**

- `hermes:api` resolves the Host-managed connection and proxies JSON requests.
- Default request timeout is 15 seconds.
- Local token mode uses the authenticated Node HTTP request path.
- Failures reject the IPC request and are surfaced by the relevant settings
  store/page.

**Tests**

- `hermes/apps/desktop/electron/dashboard-token.test.ts`
- `hermes/apps/desktop/electron/backend-ready.test.ts`
- `hermes/apps/desktop/electron/macsoft-customer-runtime.test.ts`
- `hermes/apps/desktop/src/app/settings/model-settings.test.tsx`
- Hermes configuration, model, provider, and OAuth route tests.

**Affected behavior if changed**

Provider accounts, API keys, model selection, configuration loading, and the
security property that the settings process cannot execute an Agent.

### A4. Desktop to Host IPC and control API

**Renderer-to-Electron IPC**

- `hermes:macsoft-host:status`
- `hermes:macsoft-host:service-action`
- `hermes:macsoft-host:set-autostart`
- `hermes:server-autocount:*`
- `hermes:macsoft-desktop-chat:status`
- `hermes:macsoft-admin:*`

The preload implementation is
`hermes/apps/desktop/electron/preload.ts`. The Electron handlers are in
`hermes/apps/desktop/electron/main.ts`.

**Electron-to-Host HTTP**

- `GET /v1/status`
- `GET /v1/pairing-code`
- `POST /v1/autostart`
- `POST /v1/services/{service}/{start|stop|restart}`

Implementation:
`product_runtime/macsoft_runtime/control.py::HostControlServer`.

All routes bind to loopback and require the Host bearer token. Electron uses a
75-second control timeout. Host failures return a bounded, path- and
credential-sanitized error.

**Tests**

- `product_runtime/tests/test_host.py`
- `hermes/apps/desktop/electron/macsoft-host-client.test.ts`
- `hermes/apps/desktop/electron/server-autocount-config.test.ts`
- `hermes/apps/desktop/electron/macsoft-admin-chat-ipc-contract.test.ts`

### A5. MacSoft Server to Hermes Chat Completions

**Caller**

- `server/macsoft/chat/hermes_client.py::request_hermes_reply`
- `server/macsoft/chat/hermes_client.py::stream_hermes_reply_events`
- Client chat routes in `server/macsoft/gateway/routes_chat.py`

**Hermes implementation**

- `hermes/gateway/platforms/api_server.py::_handle_chat_completions`

**Request**

`POST /v1/chat/completions` with bearer authentication:

```json
{
  "model": "hermes-agent",
  "messages": [
    {"role": "system|user|assistant", "content": "text or supported user blocks"}
  ],
  "stream": true
}
```

The MacSoft caller accepts non-empty system/user/assistant messages. User
content may be the normalized multimodal block list created by the Server file
pipeline.

**Non-stream response dependency**

```json
{
  "choices": [
    {"message": {"content": "non-empty assistant text"}}
  ]
}
```

**Stream response dependency**

- SSE `data:` records in OpenAI-compatible `choices[0].delta.content` form.
- Optional `event: hermes.tool.progress` records with string `tool` and
  `status` equal to `running` or `completed`.
- `[DONE]` terminates the stream.
- At least one non-whitespace text delta is required.

**Timeout and errors**

- Server timeout is configured by
  `hermes.request_timeout_seconds`, currently defaulting to 180 seconds.
- `401` maps to authentication error.
- connection, timeout, HTTP, malformed JSON/SSE, missing choices, and empty
  assistant text are classified separately by `HermesApiError`.

**Tests**

- `server/tests/test_chat_boundaries.py`
- `server/tests/test_activity_protocol.py`
- `hermes/tests/gateway/test_api_server.py`
- `hermes/tests/gateway/test_api_server_multimodal.py`

### A6. MacSoft Server to interruptible Hermes Runs

**Caller**

- `server/macsoft/chat/hermes_client.py::_start_hermes_run`
- `stream_interruptible_hermes_reply_events`
- `interrupt_hermes_run`
- Admin chat routes in `server/macsoft/gateway/routes_admin.py`

**Hermes implementation**

- `hermes/gateway/platforms/api_server.py::_handle_runs`
- `_handle_run_events`
- `_handle_stop_run`

**Start request**

`POST /v1/runs` with bearer authentication:

```json
{
  "model": "hermes-agent",
  "input": "latest user content",
  "conversation_history": [
    {"role": "user|assistant", "content": "text"}
  ],
  "instructions": "joined system instructions",
  "session_id": "MacSoft Admin session id"
}
```

**Start response**

- HTTP `202`.
- JSON `run_id` must be text beginning with `run_`.
- Current Hermes also returns `status: "started"`.

**Event stream**

`GET /v1/runs/{run_id}/events` returns SSE data objects. MacSoft consumes:

- `message.delta` with string `delta`
- `tool.started` / `tool.completed` with `tool` or `tool_name`
- `run.cancelled`
- `run.failed` with an error

**Interrupt**

`POST /v1/runs/{run_id}/stop` with `{}`. A `404` means the run is not active;
other transport failures are reported. The Hermes handler requests Agent
interrupt, cancels the task, and bounds its wait to five seconds.

**Tests**

- `server/tests/test_admin_stage3_interrupt.py`
- `hermes/tests/gateway/test_api_server_runs.py`
- `hermes/tests/gateway/test_sse_agent_cancel.py`

### A7. Product metadata and writable-state contract

`product.json` is the MacSoft product authority. It declares product version,
build ID, channel, expected Hermes tag/commit, runtime contract version,
runtime metadata schema version, data schema, protected resource version, and
update manifest URL.

`product_runtime/macsoft_runtime/initializer.py::initialize_product_data`
creates mutable templates once, synchronizes only the Host-owned local API key,
preserves customer settings, and updates protected resources only when their
previous hash proves they were not locally changed.

Hermes must continue to honor `HERMES_HOME`. It must not redirect provider
credentials, auth files, runtime configuration, Skills, or session state back
into Program Files or a user-profile default during packaged operation.

## B. Product regression flows affected by Hermes

These are not new Hermes APIs. They are end-to-end MacSoft flows whose result
depends on the direct contracts above.

| Flow | Hermes dependency | MacSoft ownership | Principal tests |
| --- | --- | --- | --- |
| Client session/chat | Chat Completions, multimodal normalization, tool events | Device isolation, Server DB, response/SSE contract | `server/tests/test_chat_boundaries.py`, session and activity suites |
| Server Desktop Admin chat | Runs start/events/stop | Admin auth, Admin sessions/messages, active-run registry | `test_admin_stage3_interrupt.py`, Desktop Admin chat tests |
| SSE Activity v1 | Hermes text/tool lifecycle inputs | Privacy-safe Client event mapping | `test_activity_protocol.py` |
| Tools and Skills | Hermes Agent tool resolution and runtime paths | MacSoft allowlist, public/private Skill ownership | Server capability/Skill tests plus Hermes API Server tests |
| OCR and attachments | Chat Completions user content blocks | Upload validation, storage, extraction, size/type policy | file/OCR and chat boundary tests |
| AutoCount | Hermes plugin/tool loading and HERMES_HOME | Validation, confirmation, unknown-outcome policy, result formatting | AutoCount and packaging contract tests |
| Model/provider/auth | Config-only Hermes routes and runtime YAML | Host secret, ProgramData ownership, customer settings UI | Desktop model/provider and configuration tests |

No future Hermes upgrade is accepted solely because `/health` passes. These
regression flows must remain green in source and installed modes.

## Compatibility metadata implemented in Batch 2

The first compatibility implementation should use exact matching, not generic
capability negotiation.

**MacSoft product declaration (`product.json`)**

- `runtime_base_version`
- `runtime_base_commit`
- `runtime_contract_version`
- `runtime_metadata_schema_version`

**Hermes runtime declaration (`hermes/macsoft-runtime.json`)**

- `runtime`
- `runtime_base_version`
- `runtime_base_commit`
- `runtime_contract_version`
- `runtime_metadata_schema_version`

Expected and detected values must be loaded from different artifacts:

- Expected values: installed root `product.json`.
- Detected values: a Hermes-owned runtime declaration bundled inside
  `ai-service`, generated or audited from the selected Hermes tree.

The AI Service must not report expected values by rereading `product.json`.
That would allow a replaced or mismatched runtime to confirm itself falsely.

## Handshake boundary implemented in Batch 2

1. Before starting Hermes, Host reads and validates the runtime declaration
   under the Hermes program root.
2. Host requires exact baseline, contract, and metadata-schema matches.
3. If preflight passes, Host starts the AI Service.
4. AI Service health reports its own runtime declaration.
5. Host compares that detected response with the already loaded product
   expectation.
6. Host exposes only sanitized expected/detected diagnostic values.

Initial fail-closed behavior:

- Desktop control surface and authenticated Host diagnostics remain available.
- Unknown or mismatched AI runtime is not started.
- MacSoft Server is not started when its required AI boundary is incompatible.
- No customer configuration, database, auth file, or protected resource is
  migrated or rewritten as part of compatibility failure handling.

Whether any non-AI Server function can safely remain available is unresolved;
the current Host start order and Server chat ownership do not prove that
partial operation is safe.

## Acceptance requirements

### Development/source mode

- Exact accepted runtime declaration passes preflight and health handshake.
- Missing, malformed, unknown, and mismatched declarations fail closed.
- `start-test.bat` still owns ports `8766`, `8643`, `8642`, `8787`, and Desktop
  Vite port `5174`.
- Existing runtime, Server, Desktop, and Hermes focused tests remain green.

### Packaged/installed Windows mode

- Runtime declaration is present inside the staged `ai-service` payload.
- Expected product declaration is present at the installed product root.
- Program Files remains immutable product code; ProgramData remains writable
  customer state.
- Bundled Python can import both declarations without development paths.
- Windows Service starts only an accepted runtime.
- Configuration/auth storage and Host control token remain under ProgramData.
- Installer health verification includes the compatibility result.
- Clean install and overlay upgrade are tested on a real Windows installation.

## Change rule

Any change to a direct contract in section A requires:

1. an explicit contract diff;
2. caller and implementation tests;
3. source-mode acceptance;
4. packaged acceptance when paths, lifecycle, native dependencies, or service
   startup are affected;
5. technical review before updating the accepted Hermes pin.
