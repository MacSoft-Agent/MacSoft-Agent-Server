# MacSoft Agent project status

Status date: 2026-07-27

This is the current coordination record. It does not replace code, schemas,
tests, contracts, or architecture documents.

## Accepted development baseline

| Item | Value |
| --- | --- |
| Program stage | Stage 4 - collaboration foundation and release preparation |
| Branch | `debug/skill-runtime-c6afbc9` |
| Commit | `03e66401e06de51afd1cc47d89671f258e899401` |
| Annotated tag | `baseline-0.1.0-20260727` |
| Product version | `0.1.0` |
| Build ID | `macsoft-agent-0.1.0-stable.20260722.1` |
| Hermes baseline | `v2026.7.7.2` |
| Hermes commit | `79f12748022817a7c4f3fee747e45e9e6979214a` |

The tag resolved to the accepted commit and the working tree was clean at the
start of Stage 4.

## Program history and owner decisions

- Stage 1 current-state backup was explicitly skipped by the Product Owner.
- Stage 2 classified 2,432 pending paths, retained maintained changes, removed
  generated/runtime material, created four coherent commits, and finished clean.
- Stage 3 accepted and tagged the development baseline locally. The tag was not
  pushed.
- Customer updates are currently installer-managed. A built-in update service
  has not been approved or implemented.
- Stage 4 may document and assess release readiness but must not fix a release
  issue or create a Release Candidate.

## Verified evidence carried from Stage 2

- 40 product-runtime tests passed.
- 92 Server tests passed.
- 36 directly related focused tests passed.
- Desktop typecheck passed.
- Repository cleanliness and staged/unstaged `git diff --check` passed.
- Git object verification passed.

The complete Desktop UI suite is not green. After generated JavaScript was
removed, the TypeScript-based run still had 28 failures and collection errors.
Confirmed categories include stale branding and model-option expectations,
outdated component mocks, session and layout assertions, timeouts, and Vitest
collecting Electron `node:test` files. These failures were not corrected in
Stage 2 or Stage 4.

## Current release-readiness limitations

- No release package has been built from the accepted baseline.
- Clean installation, overlay upgrade, ProgramData preservation, uninstall and
  explicit purge behavior have automated contracts but no current real-machine
  acceptance from this baseline.
- Installed Host/AI Service/Server/Desktop lifecycle and fixed-port conflict
  handling have not been accepted as a complete installed workflow.
- The external Thin Client has not completed a recorded acceptance matrix
  against this baseline.
- AutoCount safeguards are covered by focused tests, but production-like
  read/write, confirmation, and unknown-outcome acceptance is not recorded.
- Built-in update discovery/apply/rollback is intentionally unavailable.
- Installer signing, trusted distribution, and update authenticity evidence is
  not present in the repository.
- The pinned Hermes upgrade process is documented but no newer upstream
  candidate has passed its compatibility matrix.

See `docs/release/RELEASE_READINESS.md` for evidence, priorities, sequencing,
and acceptance needs.

## Active objective and next decision

Stage 4 establishes durable collaboration guidance and an evidence-based
release map. Its recommended Stage 5 task is Desktop test-runner and test
baseline remediation, without product behavior changes.

The next Product Owner decision is whether to accept Stage 4 and authorize that
bounded Stage 5 task. External-release policy also requires later decisions on
installer signing/trusted distribution and whether installer-only updates are
acceptable for the first release.
