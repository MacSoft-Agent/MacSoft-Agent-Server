# WP-014 - Development Runtime Port Ownership

## Status

Complete

## Owner

- Product Owner: MacSoft Product Owner
- Execution owner: Codex
- Reviewer: Pending

## Baseline

- Repository/branch: `update/add-new-module-in-server`
- Starting commit: `ee6eca7296bdaa490ade3f9a09111757804736b6`
- Product and Hermes versions: MacSoft Agent 0.1.7; Hermes v2026.7.7.2
- Starting working-tree state: clean; ignored local `tmp/` artifacts present

## Objective

Make source development mode safely acquire and release the fixed MacSoft
runtime ports without requiring manual process termination after code updates.

## User or operational outcome

Running `start-test.bat` stops a verified installed MacSoft Host when it owns
the ports. Closing the development Desktop releases the ports, so repeated
development runs do not leave stale listeners.

## Evidence and current behavior

The reported listeners on ports 8766, 8643, 8642, and 8787 were descendants of
the installed `MacSoftAgentHost` service (`pythonservice.exe`). The launcher
previously treated all listeners as unknown and failed before starting.

## Scope

- Verify installed service identity, executable, and listener process tree.
- Stop that service through SCM with narrowly scoped elevation when required.
- Preserve recorded development Host/Desktop shutdown and port-release wait.
- Document ownership and failure behavior.

## Non-scope

- Changing fixed ports, service startup policy, installer behavior, or product version.
- Killing unknown processes or deleting local ignored artifacts.

## Architectural boundaries

Windows SCM remains owner of the installed service. The source launcher owns
only development lifecycle orchestration and never changes persistent service
configuration.

## Proposed direction

Extend `start-test-runtime.ps1` with fail-closed service/process validation and
SCM stop. Re-read listeners after the handoff and retain the existing error for
anything outside the controlled tree.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Wrong service stopped | Installed product interruption | Exact name, executable suffix, and full process-tree ownership are required. |
| Unknown listener killed | Unrelated application loss | Unknown or mixed owners remain an error; no generic process kill is used. |
| Installed service remains off | Installed UI unavailable after development | Intentional owner decision; Windows startup policy remains unchanged. |

## Product Owner decisions required

None. The Product Owner explicitly requested automatic installed-service
handoff and released ports while development mode is off.

## Acceptance criteria

1. A verified installed Host may yield all required ports to source mode.
2. Unknown or mixed owners are not terminated.
3. Desktop exit stops the recorded source runtime and releases its ports.
4. Installed service startup configuration is unchanged and it is not restarted.

## Verification plan

- Focused automated checks: packaging contract tests and PowerShell parser.
- Component/regression checks: product-runtime test suite.
- Manual or installed-product acceptance: run `start-test.bat`, approve UAC, close Desktop, inspect listeners.
- Independent review required: recommended before release integration.

## Implementation result

`start-test-runtime.ps1` now verifies the exact installed service executable
and all conflicting listener PIDs before requesting an SCM stop. It rechecks
the ports after shutdown and retains a fail-closed error for unknown or mixed
owners. The existing recorded source-runtime cleanup remains responsible for
Desktop-exit port release and never restarts the installed service.

## Verification evidence

- Regression test was observed failing before implementation because
  `MacSoftAgentHost` handoff was absent.
- `python -m unittest product_runtime.tests.test_packaging_contract`: 23 tests passed.
- Project virtual environment with `PYTHONPATH=product_runtime`, unittest
  discovery: 66 tests passed.
- PowerShell parser accepted `scripts/start-test-runtime.ps1` with zero errors.

## Unexpected findings

The repository virtual environment references the interactive user's uv Python
and cannot execute under the sandbox identity. The focused standard-library
tests use the available system Python; this does not change repository files.

## Remaining risks

- Real UAC and installed-service behavior requires installed-product acceptance.

## Final status

Automated acceptance criteria are met. Real UAC/service handoff remains an
installed-product manual acceptance item and is not represented as executed.

## Related commits and documents

- Commits: pending
- Decision records: `docs/superpowers/specs/2026-08-09-development-runtime-port-ownership-design.md`
- Plan: `docs/superpowers/plans/2026-08-09-development-runtime-port-ownership.md`
