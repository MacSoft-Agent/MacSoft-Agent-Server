# WP-015 - Admin Chat Long-Run Recovery

## Status

Design review

## Owner

- Product Owner: approved Option B in the Codex task on 2026-08-10
- Execution owner: Codex
- Reviewer: independent review required before release acceptance

## Baseline

- Repository/branch: `C:\MacSoft\server\MacSoft-Agent` / `improve/skill`
- Starting commit: `28111c5d` (`feat: share server home skills with clients`)
- Accepted baseline tag/commit: `baseline-0.1.0-collaboration-safe-20260727` / `e8699b5837b66fac55e599aea5db1d2681248abe`
- Product and Hermes versions: MacSoft Agent 0.1.7; Hermes `v2026.7.7.2` at `79f12748022817a7c4f3fee747e45e9e6979214a`
- Starting working-tree state: clean after an external in-scope branch commit advanced HEAD from `983f5cd` to `28111c5`

## Objective

Make Admin Chat tolerate a two-hour upstream silent interval and recover the
affected session safely after disconnects, while preventing malformed images
from poisoning subsequent turns.

## User or operational outcome

Long Admin operations can remain connected through severe temporary Hermes
stalls. If a stream still disconnects, the old run is stopped and its session
becomes reusable without restarting services. Operators see the real safe
failure category, and malformed image uploads cannot repeatedly break a chat.

## Evidence and current behavior

Confirmed from current code:

- Both Server YAML sources set `hermes.request_timeout_seconds: 600`.
- Server's synchronous Hermes event reader uses that value as its socket
  timeout.
- Hermes `/v1/runs/{run_id}/events` normally emits 30-second SSE keepalives.
- Hermes independently supports per-provider request and stale timeouts, but
  Admin Home provisioning does not currently align them with Server policy.
- Admin stream ownership is reserved under `admin:<session_id>` and released
  only when the stream generator exits.
- Electron emits `stream_disconnected` on a response-reader failure but only
  interrupts when its renderer is destroyed or the user explicitly presses
  Stop.
- Desktop discards non-success Server envelopes and renders a generic start
  error.
- image validation accepts signature-only fake images, and historical Admin
  images are rebuilt into every later request.

Production evidence supplied by the Product Owner reports a 600-second stale
provider kill, retries, a 1288-second Hermes event-loop stall, 40k-84k-token
contexts, a disconnected Desktop stream, and subsequent per-session HTTP 409.
The exact CPU operation behind the event-loop stall remains unknown without
profiling the affected machine.

## Scope

- Two-hour Server and Admin-provider timeout policy.
- Narrow packaged upgrade migration from the historical 600-second default.
- Admin Home propagation for the active provider only.
- Unexpected Desktop disconnect interruption and bounded real lock-release wait.
- Safe structured Admin error propagation through Desktop.
- Decoder-backed image upload validation and legacy historical-image omission.
- Focused Server, product runtime, Hermes Desktop, and dependency-lock changes.

## Non-scope

- AutoCount connector timeout/business-rule changes.
- Client API or external Thin Client changes.
- Provider retry-count, port, model, Hermes baseline, or product-version changes.
- A full async rewrite of the Server-to-Hermes stream.
- Forced TTL deletion of active session locks.
- Deletion or migration of stored customer attachment bytes.

## Architectural boundaries

- MacSoft Server remains the owner of Admin session concurrency and Admin
  attachment authorization.
- Hermes remains the owner of provider request execution and stale detection.
- The timeout is a managed Admin runtime policy, not a credential or `.env`
  setting.
- Device profiles and Client contracts remain unchanged.
- Existing customer YAML and stored files are preserved except for the
  explicitly approved exact 600-to-7200 Server setting migration.
- Error propagation must remain redacted and must not expose provider payloads,
  local paths, tokens, or stack traces.

## Proposed direction

Implement the approved targeted end-to-end design in
`docs/superpowers/specs/2026-08-10-admin-chat-long-run-recovery-design.md`.
Use `hermes.request_timeout_seconds` as the MacSoft authority, merge it into
the active Admin provider's request/stale configuration, interrupt unexpected
Desktop disconnects, wait boundedly for genuine registry release, preserve
safe error codes, and validate images with the existing product's pinned
Pillow decoder. Legacy malformed historical images are omitted with a marker,
not deleted.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| A wedged attempt occupies resources for two hours | High | Explicit Product Owner policy; Stop remains available; installed acceptance exercises recovery. |
| Persistent config migration overwrites an intentional value of exactly 600 | Medium | Migration is limited to the historical shipped default; decision is explicit in the approved design. |
| Forced unlock permits concurrent session writers | High | Never force-release; wait only for the existing generator's real release. |
| Error details expose internal data | High | Allow known safe code/message mappings; unknown errors stay generic. |
| Image decoder expands Server attack surface | Medium | Exact existing product pin, size limit, decompression-bomb rejection, focused malformed-image tests. |

## Product Owner decisions required

None. The Product Owner approved Option B, including the exact historical
600-to-7200 upgrade, lock recovery, structured errors, and image recovery, on
2026-08-10.

## Acceptance criteria

1. New and upgraded default installations apply 7200 seconds to Server Admin reads and active Admin-provider request/stale timeouts.
2. Other custom timeout values and unrelated customer configuration survive upgrade.
3. Unexpected Desktop disconnects request interruption and release the session only when the old run actually exits.
4. The affected session can submit again without service restart after release; a live run continues to receive truthful 409 protection.
5. Desktop distinguishes safe busy, timeout, disconnect, and invalid-image categories.
6. New malformed images are rejected before persistence.
7. Legacy malformed historical images do not block later text-only turns and are not deleted.

## Verification plan

- Focused automated checks: product initializer migration, Admin Home config,
  active registry/interrupt, Admin stream, Desktop client/IPC/renderer, and
  attachment validation/history tests.
- Component/regression checks: Server suite, product runtime suite, relevant
  Hermes tests through `hermes/scripts/run_tests.sh`, Desktop typecheck/tests,
  `git diff --check`, and repository cleanliness.
- Manual or installed-product acceptance: required on Windows with a real
  installed Server/Desktop, a deliberately interrupted Admin run, immediate
  same-session retry, and valid/invalid representative images.
- Independent review required: yes, because this changes installer upgrade
  behavior, persistent configuration, concurrency cleanup, and file validation.

## Implementation result

Not started. Design approval is recorded; implementation begins after written
specification review and implementation planning.

## Verification evidence

- Investigation was performed against clean HEAD `28111c5`.
- Source paths and existing tests were inspected; no production code was
  modified during investigation.

## Unexpected findings

- Related, non-blocking: while investigation was running, another repository
  operation advanced the same branch from `983f5cd` to `28111c5`. The new HEAD
  was clean and was re-inspected before this design was written.
- Related, non-blocking: the production `event loop stalled` warning confirms
  starvation duration but does not identify the exact GIL-holding operation.

## Remaining risks

- Real two-hour installed acceptance is time-consuming and cannot be replaced
  by shortened unit-test clocks.
- Total wall time may exceed two hours when existing provider retries begin a
  new attempt.

## Final status

Design review. No completion claim is made.

## Related commits and documents

- Commits: the initial design commit containing this Work Package
- Decision record: `docs/superpowers/specs/2026-08-10-admin-chat-long-run-recovery-design.md`
- Current product evidence: `docs/PROJECT_STATUS.md`
