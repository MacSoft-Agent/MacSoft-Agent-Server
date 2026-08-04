# WP-007 - Model settings loading resilience

## Status

Complete

## Owner

- Product Owner: pxw12
- Execution owner: Codex
- Reviewer: Not required for this medium, local UI fix

## Baseline

- Repository/branch: `C:\Users\pxw12\MacSoft-Agent\MacSoft-Agent-Server`, `feature/feijip`
- Starting commit: `50a735e`
- Starting working-tree state: Three unrelated, pre-existing attachment-upload edits were present and are preserved.

## Objective

Prevent the Model settings page from remaining indefinitely on its loading skeleton when optional settings requests fail.

## Evidence and current behavior

The Model page displayed its skeleton indefinitely. Desktop logs record `hermes:api` 404 responses. The current Config settings component hides ModelSettings until generic `/api/config` and `/api/config/schema` requests are both available. ModelSettings also waits for auxiliary model data in the same `Promise.all` as its required main model data. The Downloads reference clone contains an uncommitted targeted fix and regression tests for this exact behavior.

## Scope

- Decouple ModelSettings rendering from the generic config/schema gate.
- Make optional auxiliary and MoA model data non-blocking.
- Cache Model settings per active profile and add focused regressions.

## Non-scope

- Changing backend routes, authentication, packaging, model-selection contracts, or unrelated upload changes.

## Architectural boundaries

Desktop owns this presentation and client-side cache behavior. Existing Hermes REST contracts and MacSoft Host runtime ownership remain unchanged.

## Proposed direction

Adopt the already-established Downloads reference implementation: draw required model controls from independent model endpoints, defer optional panels with safe fallbacks, and retain the last successful profile-scoped snapshot while refreshing.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Stale data after a profile change | Wrong model may be displayed | Scope cache by normalized profile key and discard stale async completions. |
| Optional endpoint failure | Extra panels unavailable | Preserve main model controls and retain/retry cached optional data. |

## Product Owner decisions required

None. The requested fix restores the established Model settings behavior without changing its public contract.

## Acceptance criteria

1. Model controls render without waiting for auxiliary model data.
2. Reopening the Model settings page shows the last successful snapshot while refresh is pending.
3. Config/schema loading failures do not hide ModelSettings behind a permanent skeleton.

## Verification plan

- Focused automated checks: Model settings Vitest tests.
- Component/regression checks: Desktop TypeScript typecheck.
- Manual or installed-product acceptance: Not run unless requested.
- Independent review required: No.

## Implementation result

ModelSettings is now rendered when the Model section is selected even if the
generic config/schema requests are loading or fail. The generic state remains
visible underneath with its existing retry action. Required model info/options
load as a profile-scoped React Query snapshot; auxiliary and MoA data load
afterward with independent failure fallbacks. The shared config-record cache is
also profile-scoped. Focused regressions cover an unresolved optional request
and reopening during a refresh.

## Verification evidence

- `git diff --check`: passed (line-ending warnings only).
- `npm.cmd run test:ui -- src/app/settings/model-settings.test.tsx` from
  `hermes/apps/desktop`: passed, 1 file and 9 tests.
- `node ..\\..\\node_modules\\typescript\\bin\\tsc -p . --noEmit --pretty false`
  from `hermes/apps/desktop`: passed.
- `npm.cmd run typecheck` returned exit code 1 without TypeScript diagnostics in
  this PowerShell environment; the direct equivalent compiler invocation above
  passed.

## Unexpected findings

- Related non-blocking: Existing logs report generic 404 errors without recording the request path. This work prevents optional/general settings failures from blocking Model settings, but does not alter backend routing.

## Remaining risks

- A persistent required `/api/model/info` or `/api/model/options` failure will correctly show an error rather than usable model controls.

## Final status

All acceptance criteria are met by focused automated checks. No installed
desktop manual test was run in this change.

## Related commits and documents

- Commits: Uncommitted implementation.
- Contracts/status/release evidence: `docs/PROJECT_STATUS.md`.
