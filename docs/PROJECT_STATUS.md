# MacSoft Agent project status

Status date: 2026-07-27

This is the current coordination record. It does not replace code, schemas,
tests, contracts, or architecture documents.

## Accepted development baseline

| Item | Value |
| --- | --- |
| Program stage | Stage 5 - Desktop test baseline complete; awaiting acceptance |
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
- Stage 4 established the repository collaboration foundation and the
  evidence-based release-readiness map.
- Stage 5 separated renderer, Electron, and packaging-script test ownership,
  corrected test-only baseline debt, and restored a deterministic Desktop
  regression gate without changing product behavior.
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

Stage 5 is complete. The next Product Owner decision is whether to accept the
new HEAD as the development-baseline candidate.

After acceptance, the recommended next bounded task is clean reproducible
packaging from the accepted commit. It must not begin automatically. External
release policy still requires later decisions on installer signing/trusted
distribution and whether installer-only updates are acceptable for the first
release.
