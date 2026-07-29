# Chart Artifact Server Foundation Work Package

## Status

Ready for independent review

## Owner

- Product Owner: MacSoft project owner
- Execution owner: Server team
- Reviewer: Technical reviewer

## Baseline

- Repository: `C:\MacSoft-Agent`
- Starting commit: `8878213`
- Product version: `0.1.0`
- Runtime base: `v2026.7.7.2`
- Starting Server working tree: clean

## Objective

Build the Server-only storage, lifecycle, worker, protected delivery, and
recovery foundation for future chart Artifacts without enabling a real
AutoCount chart feature.

## Scope

- Message lifecycle migration and pending-message helpers.
- Artifact Generation, Render Job, Artifact, and Artifact File persistence.
- Fenced single-worker SQLite render queue.
- Same-volume staging and immutable file publication.
- Authenticated preview and download routes.
- History Artifact serialization, session-delete handling, and reconciliation.
- Internal test-harness Mock Dataset path with production hard blocks.

## Non-scope

- Hermes, AutoCount Plugin, Local Connector, or Client changes.
- Real AutoCount data, financial metric definitions, or production chat entry.
- Production ECharts/Chromium packaging. The included deterministic PNG backend
  verifies the lifecycle only; visual-engine acceptance remains a later gate.

## Architectural boundaries

- Existing Client chat behavior remains unchanged while the feature is disabled.
- Artifacts remain Device-, Session-, Message-, and User-scoped.
- Mock data cannot be persisted in the production environment.
- Reconciliation never calls Hermes or AutoCount and never recreates business data.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Zombie renderer publishes stale output | Incorrect Artifact | Fencing token checked before DB publication |
| Session deleted during render | Deleted data reappears | Generation deletion plus publish-time session check |
| Shared file deleted with old revision | Latest revision breaks | Cleanup checks every live `storage_key` reference |
| Legacy Message status conflicts | Existing chat regression | Migrate legacy values to `completed`; full Server suite |
| Mock reaches production | False business output | Test-only harness plus persistence-layer hard block |

## Acceptance criteria

1. PNG-only lifecycle completes as `ready` from Mock Dataset through protected retrieval.
2. When PNG and PDF are requested, successful PNG plus failed PDF produces
   `partial`; PDF absence does not downgrade a PNG-only request.
3. Fencing, retry counts, session deletion, and shared-file references are tested.
4. History returns only completed/failed messages and latest Artifact files.
5. Existing Server tests remain green.
6. No production route generates a Mock Artifact or invokes AutoCount.

## Verification plan

- Focused: 19/19 passed with
  `python -m unittest tests.test_chart_artifact_foundation -v`.
- Regression: 111/111 passed with
  `python -m unittest discover -s tests -v`.
- Static: `python -m compileall` and `git diff --check` passed.
- Installed-product/visual acceptance: not performed; production renderer is out of scope.

## Implementation result

Implemented the Server Foundation persistence, fenced queue, lifecycle PNG
backend, protected Artifact routes, History serialization, deletion safeguards,
and deterministic reconciliation rules. No user-facing chart generation path is
enabled.

## Remaining risks

- ECharts/Chromium deployment and visual QA are not implemented by this Work Package.
- Real integration remains blocked on Hermes/Plugin contracts, Connector upgrade,
  data-completeness evidence, approved financial definitions, and Client support.

## Final status

Server team verification reported as passed. Independent verification remains
pending before this foundation is integrated or any production feature flag is
enabled.
