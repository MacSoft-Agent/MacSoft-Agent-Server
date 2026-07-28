# WP-003 - Hermes Compatibility

## Status

Design review

Batch 1 investigation is complete. Batch 2 implementation is not started and
requires technical review of the linked evidence.

## Owner

- Product Owner: MacSoft Agent Repository Owner
- Execution owner: Codex
- Reviewer: Independent technical reviewer

## Baseline

- Repository: `https://github.com/MacSoft-Agent/MacSoft-Agent`
- Branch: `docs/wp-003-hermes-compatibility-batch1`
- Starting commit: `1816fbf53b17c22e9e1220c7da05dd47537ed1c5`
- Product: `0.1.0`, build `macsoft-agent-0.1.0-stable.20260722.1`
- Hermes: `v2026.7.7.2`,
  `79f12748022817a7c4f3fee747e45e9e6979214a`
- Starting working tree: clean

## Objective

Establish a code-derived MacSoft-to-Hermes compatibility boundary before
implementing runtime compatibility enforcement or customer Built-In Update.

## Evidence and current behavior

Confirmed:

- Host manages three child services and exposes authenticated control on port
  `8766`.
- Hermes supplies two distinct processes: config-only backend on `8643` and AI
  Service on `8642`.
- MacSoft Server uses both Chat Completions and structured Runs APIs.
- Current Host health checks prove basic identity but not exact compatibility.
- The AI Service `/health` version comes from Hermes code, while the expected
  baseline comes from MacSoft `product.json`.
- Current config-only behavior is a MacSoft patch in Hermes core.
- The customer Desktop bypasses native Hermes execution and uses MacSoft Server
  Admin chat.
- Customer update checks are intentionally disabled and installer-managed.
- Upstream comparison found 31 added, 75 modified, and 30 deleted paths.

No customer-visible runtime behavior was changed in Batch 1.

## Batch 1 deliverables

1. Compatibility contract:
   `docs/contracts/MACSOFT_HERMES_COMPATIBILITY_CONTRACT.md`
2. Hermes patch inventory:
   `docs/reference/MACSOFT_HERMES_PATCH_INVENTORY.md`
3. Existing test mapping in the contract and inventory.
4. Development/packaged dependency map in contract sections A1, A7, and
   Acceptance Requirements.
5. Minimum metadata proposal in the contract.
6. Minimum handshake boundary proposal in the contract.
7. Risks and unresolved evidence below.
8. Recommended Batch 2 scope below.

## Findings that differ from the initial plan

1. **The config backend is a direct Hermes core patch.** It is not merely a
   Host configuration. `hermes_cli/main.py` and `web_server.py` actively
   suppress Agent, gateway, PTY, filesystem, session, Tool, and Skill surfaces.
2. **Desktop Admin chat does not use the native Hermes Desktop gateway.** It
   calls MacSoft Server, which then calls Hermes Runs.
3. **Model selection has two surfaces.** MacSoft's customer model page reads
   and atomically patches runtime YAML, while full provider/account flows use
   the authenticated config-only Hermes API.
4. **Liveness is not compatibility.** Current AI `/health` reports the Hermes
   version, but Host only matches `status` and `platform`.
5. **A compatibility failure cannot safely promise partial Server service.**
   Host startup ordering and Server's AI ownership make “keep all non-AI
   Server functions running” unproven.
6. **Most divergence is Desktop integration.** The Python Hermes core delta is
   concentrated in two files; the highest recurring upstream conflict risk is
   Electron main/preload and chat/session UI.

## Existing test mapping

| Boundary | Primary tests |
| --- | --- |
| Host process, health, ports, token, ownership | `product_runtime/tests/test_host.py` |
| Development/packaged paths and metadata | `test_metadata_paths.py`, `test_initializer.py` |
| Packaging/staging path isolation | `test_packaging_contract.py`, `test_staging.py` |
| AI health and Chat Completions | `hermes/tests/gateway/test_api_server.py` |
| Multimodal user content | `test_api_server_multimodal.py`, Server file/chat tests |
| Structured Runs, events, and stop | `test_api_server_runs.py`, `test_sse_agent_cancel.py` |
| Server chat/SSE error boundary | `server/tests/test_chat_boundaries.py` |
| Admin interrupt/run isolation | `server/tests/test_admin_stage3_interrupt.py` |
| Activity privacy/mapping | `server/tests/test_activity_protocol.py` |
| Desktop Host/config boundary | `macsoft-host-client.test.ts`, `server-autocount-config.test.ts` |
| Desktop Admin chat | MacSoft Admin client/hook/route/IPC tests |
| Config-only model/provider/auth | Desktop model tests and Hermes web server route tests |
| Customer updater isolation | `macsoft-update-policy.test.ts`, `updates.test.ts` |

Batch 2 must add behavior tests for mismatched/missing/malformed runtime
metadata and must not replace this regression mapping with version snapshots.

## Development versus packaged dependency map

| Dependency | Development | Packaged |
| --- | --- | --- |
| Product root | repository root | `C:\Program Files\MacSoft Agent` |
| Hermes program root | `<repo>\hermes` | `<program>\ai-service` |
| Python | `<repo>\hermes\venv\Scripts\python.exe` | `<program>\python\python.exe` |
| Writable Hermes home | `<repo>\runtime` | `C:\ProgramData\MacSoft Agent\runtime` |
| Server config/data | `<repo>\server` | `C:\ProgramData\MacSoft Agent\server` |
| Desktop | Vite `5174` + repository Electron | installed Desktop payload |
| Host | console development process | `MacSoftAgentHost` Windows Service |
| Product metadata | repository `product.json` | installed root `product.json` |
| Auth/config | isolated repository runtime | preserved ProgramData |
| Lifecycle acceptance | `start-test.bat` / `stop-test.bat` | installer, service, Desktop shortcut |

## Recommended Batch 2 implementation scope

### Static declarations

- Add an exact expected compatibility contract version and runtime metadata
  schema to MacSoft product metadata.
- Add a separate Hermes-owned runtime declaration containing detected baseline
  identity/fingerprint, implemented contract version, and schema.
- Package the runtime declaration inside `ai-service`.
- Validate both declarations strictly; do not infer compatibility from a
  version range.

### Host preflight

- Validate the Hermes-owned declaration before starting config backend or AI
  Service.
- Require exact accepted baseline, contract, and schema values.
- Treat missing, malformed, or mismatched values as incompatible.
- Do not initialize/migrate ProgramData when compatibility preflight fails.

### Runtime handshake

- Extend AI health with the runtime's own compatibility fields.
- Compare the live response with the preflight declaration and product
  expectation.
- Keep the health extension additive; do not change Thin Client or Server
  public APIs.

### Diagnostic status

- Add sanitized compatibility state to authenticated Host status.
- Desktop may display expected and detected public version/build identifiers.
- Never include tokens, credentials, customer paths, or configuration values.

### Fail-closed behavior

- Keep Host diagnostics and Desktop control available.
- Do not start an unknown/mismatched Hermes runtime.
- Do not start MacSoft Server when its required AI runtime is incompatible.
- Do not rewrite persistent state in the incompatibility path.

### Verification

- Focused metadata, preflight, health, and status tests.
- Product runtime suite.
- Server suite and Hermes API Server focused suites.
- Desktop Electron/UI baseline and typecheck.
- Development runtime acceptance.
- Staging audit and installer build.
- Real installed Windows clean/overlay acceptance before baseline acceptance.

## Candidate baseline workflow

```text
accepted main
-> integration/runtime-<candidate>
-> candidate runtime declaration
-> patch inventory reconciliation
-> contract and regression tests
-> development acceptance
-> packaged Windows acceptance
-> independent technical review
-> product version/build and product.json pin update
-> merge and Product Owner acceptance
```

Candidate metadata may change on the integration branch for test builds. The
accepted pin on `main` changes only after acceptance. A failed candidate is
discarded or postponed; customers remain on the accepted baseline.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Expected and detected values read from one file | False compatibility | Separate product and Hermes-owned declarations |
| Runtime declaration edited without actual reconciliation | False assurance | Staging fingerprint/audit plus integration review |
| Config-only core patch lost upstream | Second execution surface exposed | Exact patch inventory and boundary tests |
| Host starts Server after AI incompatibility | Broken or unsafe partial product | Fail startup dependency chain closed |
| Exact matching blocks harmless upstream changes | Slower upgrades | Intentional first-version safety; review each candidate |
| Lock-file merge silently changes dependencies | Installed failures | Regenerate and test one audited dependency graph |
| Desktop integration conflicts with upstream session code | Chat/session regressions | MacSoft seams plus complete Desktop regression gate |
| Unit tests pass but installed paths fail | Customer outage | Real Windows clean and overlay acceptance |

## Open technical risks and unresolved evidence

1. The exact runtime fingerprint format should be selected in Batch 2 after
   checking staging-manifest reuse. It must not add a second package manifest
   with overlapping authority.
2. The configuration backend should probably use the same runtime declaration
   as AI Service, but its live handshake shape is not yet selected.
3. Packaged Windows acceptance has not been run from the current baseline.
4. The safest user-visible incompatibility location needs a small Desktop
   design review; Host status is the diagnostic authority.
5. Partial Server availability remains intentionally unsupported until a
   dependency analysis proves it safe.
6. Built-In Update authenticity, rollback, and distribution remain WP-004 and
   are not implemented here.

## Product Owner decisions required

None for Batch 1 documentation.

Before accepting Batch 2:

- approve exact-match, fail-closed behavior;
- approve blocking MacSoft Server when the required Hermes runtime is
  incompatible;
- accept that the compatibility declaration becomes a release-controlled
  metadata contract.

## Acceptance criteria for Batch 1

1. Contracts are derived from actual callers and implementations.
2. Upstream source/tag/commit and comparison method are recorded.
3. MacSoft patches are grouped by behavior, tests, conflict risk, and possible
   adapter placement.
4. Development and packaged dependencies are distinguished.
5. Expected and detected metadata sources are independent.
6. Batch 2 remains small and exact rather than a capability framework.
7. No customer-visible runtime, API, persistence, auth, installer, or update
   behavior changes.
8. Documents pass repository hygiene and Markdown/diff checks.

## Verification plan and evidence

Batch 1 is evidence-only. Verification performed on 2026-07-28:

- Upstream commit was independently cloned and resolved to
  `79f12748022817a7c4f3fee747e45e9e6979214a`.
- Tracked path/content comparison completed: upstream 6,209 paths, MacSoft
  Hermes 6,210 paths, with 31 added, 75 modified, and 30 deleted.
- Referenced route/function and caller/implementation pairs were inspected in
  current source.
- Product-runtime suite: 40 tests passed.
- Server suite: 92 tests passed.
- Desktop Electron suite: 373 passed, 4 platform-restricted tests skipped,
  0 failed.
- Desktop packaging scripts: 9 passed.
- Desktop TypeScript typecheck passed.
- Repository cleanliness check passed with only the four expected Batch 1
  document paths pending.
- `git diff --check` passed.

The full Desktop UI suite did not complete:

- the sandboxed run was blocked from creating `.vite-temp` with `EPERM`;
- an elevated retry ran concurrently with an already active development
  Desktop/Vite runtime, reported two five-second settings-test timeouts, and
  did not terminate normally;
- only the Vitest process tree started by this task was stopped; the existing
  development runtime was left unchanged.

Because Batch 1 changes documentation only, this does not indicate a regression
caused by the Batch 1 diff. It remains an uncompleted verification item and
must be rerun in an idle development environment before Batch 2 implementation
is accepted.

No real installed-product acceptance is required for documentation-only Batch
1. It becomes mandatory in Batch 2.

## Related documents

- `docs/contracts/MACSOFT_HERMES_COMPATIBILITY_CONTRACT.md`
- `docs/reference/MACSOFT_HERMES_PATCH_INVENTORY.md`
- `docs/development/MACSOFT_UPSTREAM_MAINTENANCE.md`
- `docs/release/RELEASE_READINESS.md`
