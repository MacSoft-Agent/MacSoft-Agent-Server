# WP-001 - Desktop test-runner and test-baseline remediation

## Status

Complete - awaiting Product Owner acceptance

## Owner

- Product Owner: MacSoft Agent Product Owner
- Execution owner: Codex
- Reviewer: Codex separate final review pass

## Baseline

- Repository/branch: `C:\MacSoft-Agent-Github\MacSoft-Agent` /
  `debug/skill-runtime-c6afbc9`
- Starting commit: `4d164620d2890bc5e72994016ca0210ebd94b4d1`
- Accepted baseline: `baseline-0.1.0-20260727` /
  `03e66401e06de51afd1cc47d89671f258e899401`
- Product/Hermes: `0.1.0` /
  `macsoft-agent-0.1.0-stable.20260722.1` / `v2026.7.7.2`
- Starting working-tree state: clean

## Objective

Restore a deterministic Desktop automated-test baseline without changing
intended product behavior.

## User or operational outcome

Developers can run clearly separated renderer and Electron suites from a fresh
checkout and trust failures as release-readiness signals rather than runner
miscollection, duplicate files, stale mocks, or obsolete assertions.

## Evidence and current behavior

The initial `npm run test:ui --workspace apps/desktop` run:

- collected renderer Vitest files, Electron `node:test` files, script
  `node:test` files, and two `src` `node:test` files together;
- reported 28 renderer test failures;
- reported 46 file-level collection/parse failures, including `No test suite
  found` for the wrong runner;
- had no generated JavaScript test files, so duplicate generated tests are not
  a current cause.

The existing `test:desktop:platforms` command ran 342 Electron tests from a
manual file list: 337 passed, 3 failed, and 2 were skipped. The list omitted
eight Electron test files. Running all `electron/*.test.ts` files exposed one
Vitest file in the Electron directory plus three Windows portability failures
in a Linux relaunch test.

Confirmed renderer categories include MacSoft branding assertions that still
expect Hermes, `model.options` assertions missing the current
`explicit_only` policy, a Model Settings mock missing
`setApiRequestProfile`, missing JSDOM `CSS.escape`, stale pane persistence and
other direct output assertions, plus timeouts that still require isolation.

## Scope

- Desktop Vitest configuration and package test commands
- renderer/Electron runner ownership
- directly related test setup, mocks, fixtures, assertions, and portability
- this Work Package and the current project/release status after verification

Expected files are guidance. Necessary adjacent test-only changes remain
allowed when supported by evidence.

## Non-scope

- Customer-visible behavior, UI redesign, or new Desktop features
- Server/Thin Client contracts, installer/ACL/update behavior, ports, Host
  ownership, AutoCount, Hermes baseline, packaging, or Release Candidate work

## Architectural boundaries

Renderer/UI tests belong to Vitest/jsdom. Electron and packaging-script tests
belong to Node's test runner through `tsx` where TypeScript is required. Test
configuration must not hide valid source tests or allow generated JavaScript.
Current product code is the behavioral authority when code, architecture, and
multiple current tests consistently agree.

## Proposed direction

1. Establish explicit non-overlapping runner patterns.
2. Normalize the three misplaced framework imports to their directory owner.
3. Replace the brittle Electron file list with a complete pattern and keep
   script tests explicit.
4. Add only missing browser-test primitives to shared Vitest setup.
5. Correct mocks and expectations proven stale by current implementation.
6. Isolate remaining failures and stop if any exposes a genuine product
   regression.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Exclusion hides a valid test | False green baseline | Narrow `src` include and complete `electron/*.test.ts` pattern; compare discovered counts |
| Test updated to bless a regression | Product defect hidden | Trace current code, comments, and sibling tests before changing expectations |
| Global setup changes isolation | Flaky or coupled tests | Add only standards-compatible browser primitives; rerun complete suite |
| Platform-specific test silently stops testing | Linux regression hidden | Keep structural checks cross-platform and explicitly report platform-only syntax checks |

## Product Owner decisions required

None at the investigation checkpoint. Any genuine customer-visible regression
will be reported before product behavior changes.

## Acceptance criteria

1. Vitest collects only intended `src` renderer/UI tests.
2. Electron and packaging-script Node tests run through explicit commands.
3. No generated JavaScript or duplicate test is executed.
4. No wrong-runner collection error remains.
5. In-scope stale mocks/assertions and test isolation issues are resolved.
6. Desktop renderer tests, Electron tests, script tests, and typecheck pass, or
   every remaining failure is individually evidenced and outside scope.
7. No intended product behavior changes.
8. Cleanliness and diff checks pass and the final working tree is clean.

## Verification plan

- Focused: rerun each corrected failing file while investigating.
- Component: `test:ui`, complete Electron Node tests, script Node tests, and
  Desktop typecheck.
- Repository: generated-test inventory, cleanliness, staged/unstaged
  `git diff --check`.
- Manual installed-product acceptance: not required; no product behavior is
  intended to change.
- Independent review: separate final diff/evidence pass before commit.

## Implementation result

The Desktop test surfaces now have explicit, non-overlapping ownership:

- Vitest collects the 153 TypeScript renderer tests under `src/` and uses
  JSDOM plus a standards-compatible `CSS.escape` test shim.
- Node's test runner, through `tsx`, collects all 43
  `electron/*.test.ts` files instead of a manually maintained subset.
- Node's test runner collects the 2 packaging-script test files through a
  separate command.
- `test:baseline` runs renderer, Electron, script, and typecheck gates in one
  deterministic sequence.

Three misplaced test files were converted to the runner owned by their
directory. Established MacSoft branding, model policy, pane persistence,
renderer APIs, and direct output contracts were reflected in stale tests and
mocks. Linux relaunch-script structure remains tested on Windows, while the
two Bash syntax checks run only when Bash is available.

No production source, Server/Client contract, installer, runtime, port,
AutoCount, Hermes pin, or customer-visible behavior was changed.

## Verification evidence

- `npm run test:baseline --workspace apps/desktop`: passed
  - Vitest: 153 files and 1,211 tests passed
  - Electron: 377 tests; 373 passed, 4 explicitly skipped, 0 failed
  - packaging scripts: 9 passed
  - Desktop TypeScript typecheck: passed
- Targeted ESLint over every changed TypeScript/TSX test and test-setup file:
  passed with zero errors and zero warnings.
- Runner inventory:
  - 153 `src` TypeScript tests
  - 43 Electron TypeScript tests
  - 0 generated JavaScript tests
  - 0 `src` tests importing `node:test`
  - 0 Electron tests importing Vitest
- `git diff --check`: passed before the implementation commit.
- Implementation commit: `edf42fa` -
  `test(desktop): restore reliable test baseline`.

## Unexpected findings

- The old Electron command omitted eight maintained test files because it used
  a manual list.
- Two renderer-directory tests used `node:test`, while one Electron-directory
  test used Vitest.
- The Linux relaunch tests assumed a Unix absolute path and an installed Bash,
  so three failures on Windows were test portability defects rather than
  product failures.
- JSDOM prints two informational `HTMLCanvasElement.getContext` messages during
  the UI suite. They do not fail tests and do not justify adding a production
  or test dependency in this Work Package.

## Remaining risks

- The two Bash syntax checks were skipped because Bash is unavailable on this
  Windows machine. Their platform-independent script-content assertions passed;
  Linux CI or a Linux verification machine must execute the syntax checks.
- Installed-product, packaging, Client, and AutoCount acceptance remain outside
  this Work Package and are still required by release readiness.

## Final status

All Stage 5 acceptance criteria are met. The Work Package is complete and the
result is an accepted-baseline candidate, not a Release Candidate.

## Related commits and documents

- Commits: `edf42fa` (implementation); this Stage 5 evidence/status commit
- Decision records: none expected
- Status: `docs/PROJECT_STATUS.md`
- Release evidence: `docs/release/RELEASE_READINESS.md`
