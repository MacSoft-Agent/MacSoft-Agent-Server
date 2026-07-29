# MacSoft Agent project status

Status date: 2026-07-29

This is the current coordination record. It does not replace code, schemas,
tests, contracts, or architecture documents.

## Accepted development baseline

| Item | Value |
| --- | --- |
| Program stage | Release policy approved; production trust and installed acceptance remain gated |
| Branch | `main` |
| Commit | Resolve `baseline-0.1.0-collaboration-safe-20260727` |
| Annotated tag | `baseline-0.1.0-collaboration-safe-20260727` |
| Product version | `0.1.0` |
| Build ID | `macsoft-agent-0.1.0-stable.20260722.1` |
| Hermes baseline | `v2026.7.7.2` |
| Hermes commit | `79f12748022817a7c4f3fee747e45e9e6979214a` |

This is a development collaboration baseline, not a production release
approval. The annotated tag records the exact accepted commit without requiring
this document to contain its own commit hash.

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
- Final pre-feature preparation removed historical `runtime/auth.json` from
  reachable Git history, replaced the published `main` history under Product
  Owner authorization, and retired the compromised local baseline tag.
- The Product Owner confirmed that the affected OpenAI Codex OAuth credentials
  were revoked and the provider account was logged in again. Current runtime
  credentials differ from the historical values; no credential values were
  recorded in repository evidence.
- GitHub Actions run `30247652261` passed Repository hygiene, Windows
  contributor baseline, and Linux Electron contracts on the cleaned history.
- Stage 4 documented and assessed release readiness without fixing release
  issues or creating a Release Candidate.
- WP-003 added exact, fail-closed Hermes compatibility metadata and handshake
  enforcement without changing the Thin Client contract.
- WP-004 implemented a signed, installer-managed update path in the existing
  Settings -> About surface. It remains disabled because `product.json` has no
  production manifest URL or public key, and real installed acceptance is open.
- WP-005 approved the production release and trust policy: private source,
  separate public release-only distribution, stable-only V1, manual 0.1.1
  activation, first real 0.1.1 -> 0.1.2 update, immutable artifacts, protected
  signing keys, and no irreversible V1 data migration.

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
- Built-in update source is implemented but production-disabled. The release
  distribution location, signing pipeline, production trust provisioning,
  0.1.1 activation package, 0.1.2 update candidate, and installed-product
  acceptance have not completed their gates.
- Installer signing, trusted distribution, and update authenticity evidence is
  not present in the repository.
- The pinned Hermes upgrade process is documented but no newer upstream
  candidate has passed its compatibility matrix.

See `docs/release/RELEASE_READINESS.md` for evidence, priorities, sequencing,
and acceptance needs.

## Active objective and next decision

The cleaned development baseline is published and its source verification is
green. GitHub branch protection and secret-scanning availability are recorded
separately because private-repository plan or token restrictions may prevent
enabling them through the API.

The next approved sequence is: owner-authorized release-distribution setup,
WP-006 signing and artifact-finalization implementation, the Production Trust
Provisioning Gate, WP-007 0.1.1 trust bootstrap, WP-008 0.1.2 installed update
acceptance, and WP-009 pilot promotion and production publication.

No later gate is implied complete by this status. Production remains blocked
until the signed installed-product, Thin Client, applicable AutoCount, and
dependency-security acceptance evidence is reviewed and accepted.
