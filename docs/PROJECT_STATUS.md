# MacSoft Agent project status

Status date: 2026-07-27

This is the current coordination record. It does not replace code, schemas,
tests, contracts, or architecture documents.

## Accepted development baseline

| Item | Value |
| --- | --- |
| Program stage | Stage 6 complete locally; awaiting acceptance and safe publication |
| Branch | `debug/skill-runtime-c6afbc9` |
| Commit | `03e66401e06de51afd1cc47d89671f258e899401` |
| Annotated tag | `baseline-0.1.0-20260727` |
| Product version | `0.1.0` |
| Build ID | `macsoft-agent-0.1.0-stable.20260722.1` |
| Hermes baseline | `v2026.7.7.2` |
| Hermes commit | `79f12748022817a7c4f3fee747e45e9e6979214a` |

The tag resolved to the accepted commit and the working tree was clean at the
start of Stage 4.

The Product Owner separately approved
`a41ca104e815aabdce6883be058a92126b5889d1` as the starting development state
for Stage 6. The existing annotated baseline tag was deliberately not moved.

## Program history and owner decisions

- Stage 1 current-state backup was explicitly skipped by the Product Owner.
- Stage 2 classified 2,432 pending paths, retained maintained changes, removed
  generated/runtime material, created four coherent commits, and finished clean.
- Stage 3 accepted and tagged the development baseline locally. The tag was not
  pushed.
- Stage 4 established the repository collaboration foundation and the
  evidence-based release-readiness map.
- Stage 5 separated renderer, Electron, and packaging-script test ownership,
  corrected test-only baseline debt, and restored a deterministic Desktop
  regression gate without changing product behavior.
- Stage 6 added contributor onboarding, locked dependency bootstrap, a unified
  contributor verification command, pull-request guidance, and minimum
  Windows/Linux GitHub Actions validation. An isolated clean clone restored
  dependencies and passed the complete source baseline.
- Customer updates are currently installer-managed. A built-in update service
  has not been approved or implemented.
- Stage 4 documented and assessed release readiness without fixing release
  issues or creating a Release Candidate.

## Verified evidence carried from Stage 2

- 40 product-runtime tests passed.
- 92 Server tests passed.
- 36 directly related focused tests passed.
- Desktop typecheck passed.
- Repository cleanliness and staged/unstaged `git diff --check` passed.
- Git object verification passed.

## Stage 5 verification

- Unified Desktop baseline command passed.
- Renderer/UI: 153 files and 1,211 tests passed.
- Electron: all 43 files were collected; 373 tests passed, 4 platform-specific
  tests were explicitly skipped, and 0 failed.
- Packaging scripts: 9 tests passed.
- Desktop typecheck and targeted changed-file ESLint passed.
- No generated JavaScript tests were present and no wrong-runner imports remain.
- The two Bash syntax checks were skipped because Bash is unavailable on this
  Windows machine; they remain a Linux verification requirement.

## Current release-readiness limitations

- A historical `runtime/auth.json` with likely credential material exists in
  an ancestor of the published GitHub `main`. Relevant credentials must be
  revoked/rotated before further publication; history remediation requires
  Product Owner approval.
- Fresh `npm ci` reported 10 dependency audit findings: 1 low, 8 high, and
  1 critical. They have not been remediated or risk-accepted.
- Full Desktop lint is not green: 23 errors and 240 warnings remain as separate
  baseline debt.
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

Stage 6 is complete locally. The Product Owner must first contain the historical
credential exposure, then decide whether to accept and publish the Stage 6
HEAD, configure protected `main`, and assign reviewer identities.

Clean reproducible packaging remains the next release-readiness task after a
safe published development baseline exists. It must not begin automatically.
