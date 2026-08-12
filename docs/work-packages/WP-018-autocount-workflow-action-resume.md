# WP-018 - AutoCount Workflow Action Resume

## Status

Verifying

## Owner

- Product Owner: MacSoft Product Owner
- Execution owner: Codex
- Reviewer: Focused automated regression suite and Product Owner acceptance

## Baseline

- Repository/branch: `MacSoft-Agent` / `feat/expose-native-capabilities`
- Starting commit: `323119a5ec837158f97b2587008d039656e59f11`
- Product and Hermes versions: MacSoft Agent 0.1.7 / Hermes v2026.7.7.2
- Starting working-tree state: only unrelated untracked `.pytest-cache/`

## Objective

Make Client and WhatsApp accounting workflows use one trusted Server-selected
account-book scope and resume an approved exact AutoCount action by stable
`action_id`, without re-discovering or reconstructing the action.

## User or operational outcome

Module 1 and Module 2 keep their current business purpose. A user can prepare,
approve, execute, and recover one accounting action across messages or Client
sessions without being incorrectly required to return to WhatsApp and without
the Agent rebuilding the payload from conversation memory.

## Evidence and current behavior

- `workflow_current_context` rejects every `api_server` session even though
  `_trusted_scope` already resolves the Server-selected account book for it.
- `workflow_case_workspace` auto-fills scope only for WhatsApp.
- `workflow_approve_autocount_action` stores only `command_type` in the approval
  event, not the approved payload or preview.
- Execution therefore requires the model to reconstruct eight context fields
  plus the exact payload after approval.
- Known command execution reloads the official catalog, schema, and connector
  status even when the same metadata was just read.

## Scope

- Unify trusted Client/WhatsApp workflow context and scope enforcement.
- Make Case creation persist supported direct facts as well as nested values.
- Persist immutable prepared action content before approval.
- Add deterministic execution of an approved action by `action_id`.
- Cache live catalog/schema/status metadata for a bounded period.
- Update Module 1 and generic AutoCount Skill instructions to use the fast path.
- Prevent nested duplicate packaged workflow Skills.

## Non-scope

- Changing Module 1 or Module 2 business objectives.
- Changing AutoCount Connector command contracts.
- Changing the external Thin Client API.
- Bypassing user confirmation for consequential accounting writes.

## Architectural boundaries

- PostgreSQL remains the workflow persistence owner.
- The official Connector schema remains authoritative.
- AutoCount writes still pass the existing exact-payload approval gate.
- The Client and WhatsApp are transports; neither owns accounting state.

## Proposed direction

Extend the existing workflow event store. Store an `action_prepared` event with
the exact command, payload, preview, digest, Case and scope. Store approval as a
separate immutable event. A new execution tool accepts only `action_id`, resolves
the trusted scope, reconstructs context from those events, and calls the existing
generic AutoCount executor. Add short bounded metadata caches so known workflows
do not pay repeated discovery latency.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Stale command metadata | Payload validation may use an older schema briefly | Five-minute schema/catalog TTL; live schema remains authoritative after expiry |
| Duplicate submission | Double accounting write | Stable action ID plus existing append-only execution-started event |
| Cross-scope action access | Wrong account book | Resolve and enforce scope from authenticated transport before event lookup |
| Existing Skill behavior regresses | Module workflows become less reliable | Focused workflow and Skill-package regression tests |

## Product Owner decisions required

None. The Product Owner explicitly approved this execution direction and asked
that it not move the Module 1/2 core goals.

## Acceptance criteria

1. Client and WhatsApp both return a trusted workflow context.
2. Case operations automatically use and enforce the Server-selected scope.
3. Prepared action payload and preview are durably stored before approval.
4. An approved action executes from `action_id` without model reconstruction.
5. A started/uncertain action is not submitted a second time.
6. Known command metadata is reused within bounded TTLs.
7. Runtime packaging cannot contain a workflow Skill nested inside itself.
8. Focused and relevant regression tests pass with no diff-check errors.

## Verification plan

- Focused automated checks: workflow, plugin, staging and Skill-package tests.
- Component/regression checks: relevant Python suite and repository cleanliness.
- Manual or installed-product acceptance: live Client/WhatsApp timing remains a
  post-merge operational acceptance because unit tests cannot prove Connector
  queue latency.
- Independent review required: exact diff inspection and automated regression.

## Implementation result

Implemented by extending the existing protected AutoCount plugin and workflow
event store:

- Client and WhatsApp now resolve and enforce one transport-trusted workflow
  scope; Client no longer depends on WhatsApp context.
- Case creation accepts supported direct business facts and maps them into the
  existing Case columns/working data instead of silently dropping them.
- `workflow_approve_autocount_action` appends `action_prepared` with the exact
  command, payload and preview before human confirmation.
- `workflow_execute_approved_autocount_action` takes only `action_id`, resolves
  the trusted scope, restores the immutable action, verifies matching approval,
  and delegates to the existing generic executor/idempotency events.
- Catalog/schema/status metadata uses bounded caches isolated by base URL,
  Connector and company.
- Module 1 and generic AutoCount Skills now prohibit rediscovery and payload
  reconstruction after approval.
- Protected-resource version 7 adds conservative cleanup for byte-identical
  nested Skill copies; changed copies are retained as conflicts.

## Verification evidence

- `python -m unittest ...` focused workflow/Skill/staging/initializer suite:
  89 passed.
- `hermes/venv/Scripts/python.exe -m unittest discover product_runtime/tests`:
  115 passed.
- `hermes/venv/Scripts/python.exe -m unittest server.tests.test_autocount_validator`:
  16 passed.
- Skill Creator `quick_validate.py`: all three changed Skills valid.
- `scripts/check-repository-cleanliness.ps1`: passed; expected pending source
  changes reported for review.
- `git diff --check`: passed (Git emitted Windows line-ending notices only).
- The full Server discovery suite was attempted. Four in-scope validator
  failures were corrected. Two unrelated collection errors remain because the
  local shell environment points server import-time setup at the protected
  legacy path `C:\MacSoft-Agent\runtime\admin\config.yaml`; focused affected
  Server tests pass.

## Unexpected findings

- In scope: the protected plugin's generic `autocount-operations` Skill lacked
  standard frontmatter; it was normalized and validated.
- Related non-blocking: full Server test discovery has a local import-time path
  permission dependency unrelated to this workflow change.

## Remaining risks

- Connector pickup and AutoCount SDK execution latency are external to this work.
- Live Client/WhatsApp timing and one real approved write must still be observed
  after protected resources are refreshed; automated tests cannot prove the
  external Connector queue duration.

## Final status

Implementation and automated verification complete. Live Client/WhatsApp
acceptance remains operational follow-up after AI Service restart.

## Related commits and documents

- Commits: pending
- Decision records: none
- Contracts/status/release evidence: pending
