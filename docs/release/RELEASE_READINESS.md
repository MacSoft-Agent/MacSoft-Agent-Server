# MacSoft Agent release readiness

Assessment date: 2026-07-27

Baseline: `baseline-0.1.0-20260727` /
`03e66401e06de51afd1cc47d89671f258e899401`

This document maps evidence and missing acceptance. It is not a release
approval and does not claim that an installer built from this baseline exists.

Risk labels:

- **Blocker**: acceptance is required before the first external release.
- **High**: important release risk that needs acceptance or explicit owner
  risk approval.
- **Later**: planned hardening or product capability, not required if the
  first-release policy explicitly excludes it.
- **Information**: known product limitation that must remain visible.

## 1. Verification signal

**Current state:** the trustworthy Desktop regression-gate blocker is resolved.
Server, focused product-runtime, focused integration, Desktop renderer,
Electron, packaging-script, and typecheck evidence is green.

**Evidence:** Stage 2 recorded 40 product-runtime, 92 Server, and 36 focused
tests passing. Stage 5 added a unified Desktop baseline command and recorded
153 renderer files / 1,211 tests passing, all 43 Electron files collected with
373 passing and 4 explicit platform skips, 9 packaging-script tests passing,
and Desktop typecheck passing. Runner ownership is non-overlapping and no
generated JavaScript tests exist.

**Impact and priority:** completed prerequisite. Later release work now has a
credible Desktop regression signal.

**Remaining acceptance:** run the two Bash syntax checks on Linux because Bash
was unavailable on the Windows verification machine. This is a platform
verification requirement, not a Windows test failure.

**Sequence:** complete. Proceed only after Product Owner acceptance to the next
bounded release-readiness Work Package.

## 2. Release identity and reproducible packaging

**Current state:** `product.json` pins product version, Build ID, and Hermes
tag/commit. `scripts/build-release.ps1` requires an expected clean commit,
locked Python dependencies, `npm ci`, free owned ports, new staging, a staging
manifest, and SHA-256 build evidence. It also deliberately requires a dedicated
clone whose directory name is `MacSoft-Agent-Packaging`.

**Evidence:** `product.json`, `scripts/build-release.ps1`,
`scripts/build-staging.ps1`, `packaging/build-installer.ps1`, and
`scripts/check-repository-cleanliness.ps1`.

**Impact and priority:** **Blocker.** The design is present, but no clean
packaging-clone build from the accepted baseline has been recorded.

**Acceptance needed:** build from an exact clean baseline commit in the
required packaging clone; verify dependency locks, staging manifest, file
count, installer size and SHA-256; scan staging for secrets, runtime/customer
data, development paths, and databases; reproduce or explain any hash
difference.

**Sequence:** after the verification gate is trustworthy and before installer
acceptance.

## 3. Installer, upgrade, and persistent data

**Current state:** installer code registers `MacSoftAgentHost`, creates the
Domain/Private 8787 firewall rule, configures inherited ProgramData permissions,
supports pre-install maintenance, preserves ProgramData on normal uninstall,
and offers explicit purge. Packaging contract tests cover these policies. The
current installer contains an inline `icacls` grant for System,
Administrators, Local Service, and Users; it does not grant Everyone or Users
Full Control.

**Evidence:** `packaging/installer/MacSoft-Agent.nsi`,
`packaging/installer/maintenance.ps1`, `packaging/installer/verify-health.ps1`,
packaging contract tests, and protected-resource templates.

**Impact and priority:** **Blocker.** Source assertions cannot prove Windows
service shutdown, file replacement, ACL behavior, reboot fallback, or state
preservation on real supported machines.

**Acceptance needed:** on clean Windows test environments, verify fresh install,
launch and health; overlay upgrade from the previous supported installer;
preserved ProgramData, settings, credentials, sessions, Skills, attachments,
and databases; normal uninstall preservation; explicit purge deletion; locked
file/reboot behavior; and recovery after an interrupted upgrade. Record ACLs
and service identity without exposing secrets.

**Sequence:** after a baseline package exists. Do not redesign permissions or
rollback inside the acceptance task unless evidence creates a separate approved
Work Package.

## 4. Installed runtime lifecycle and fixed ports

**Current state:** the Windows Host owns AI Service 8642, configuration backend
8643, MacSoft Server 8787, and Host control 8766. Development additionally uses
5174. Startup scripts detect occupied ports; installed ownership logic refuses
unrelated listeners. The product does not automatically select replacement
ports.

**Evidence:** Host/runtime source and tests,
`scripts/start-test-runtime.ps1`, `scripts/stop-test-runtime.ps1`, Desktop Host
client code, and operations documents.

**Impact and priority:** **High and part of installed-product acceptance.**
Failing safely is preferable to binding the wrong process, but an ordinary user
may still need actionable UI recovery when another program owns a fixed port.

**Acceptance needed:** boot, stop, restart, Windows auto-start, crash recovery,
foreign-listener detection, log location, and Desktop status/control on an
installed build. Confirm that errors name the conflicting port/process or a
safe next action.

**Before first external release:** lifecycle acceptance is required. Automatic
port selection is a **Later** product decision because it would change
configuration and Client connection behavior.

## 5. Client/Server contract and live product flow

**Current state:** Server tests cover pairing/device authorization, device-owned
sessions and Skills, files, chat/SSE, deletion concurrency, and the Activity v1
contract. The external Thin Client is separately owned and is not in this
repository.

**Evidence:** `server/tests/`, `docs/contracts/`,
`docs/handoffs/`, Server routes and schemas. Stage 2 recorded 92 Server tests
passing.

**Impact and priority:** **Blocker.** Server-only tests do not prove a released
Client can pair and preserve identity, stream concurrent sessions, upload/read/
delete files, recover from errors, or remain isolated across devices.

**Acceptance needed:** a versioned Thin Client matrix against the installed
baseline covering health/pairing, device token reuse, session isolation,
create/delete, concurrent SSE and interrupt, model selection, file/OCR
contract, error responses, reconnection, and multi-device privacy. Record the
exact Client build.

**Sequence:** after installed runtime acceptance; no Client change belongs in a
Server release Work Package unless the owner explicitly coordinates it.

## 6. AutoCount and business-data safety

**Current state:** protected capability policy treats uploads/OCR as untrusted,
requires review and explicit confirmation before document-derived AutoCount
writes, and restricts execution to approved tools and schema validation.
Focused tests cover validation, protected instructions, activity privacy, and
business result formatting.

**Evidence:** `server/macsoft/chat/capability_policy.py`,
AutoCount validator/plugin source, `server/tests/test_autocount_validator.py`,
capability/activity tests, and `docs/architecture/MACSOFT_AGENT_BUSINESS_CONTROL.md`.

**Impact and priority:** **High.** Test doubles do not prove behavior against
supported AutoCount versions, permissions, partial failures, duplicate
submission, or an outcome that becomes unknown after a timeout.

**Acceptance needed:** use a disposable AutoCount company and a reviewed matrix
for read, validation failure, dry-run/draft, explicit confirmation, successful
write, duplicate request, timeout before/after commit, and audit/redaction.
Never use customer production data for release acceptance.

**Before first external release:** accept the exact AutoCount operations being
sold. Unsupported operations remain explicitly unavailable. Generalized
automatic recovery from unknown write outcomes is a separate high-risk design
decision.

## 7. Update, distribution, and Hermes maintenance

**Current state:** customer updates are intentionally installer-managed.
`product.json` has no update manifest URL; update check/apply returns
`installer-managed` without fetching. SHA-256 evidence is generated for release
artifacts. No built-in discovery/apply/rollback service or repository-evidenced
installer code-signing pipeline exists. Hermes is pinned, and a separate
integration-branch compatibility workflow is documented.

**Evidence:** `product.json`,
`hermes/apps/desktop/electron/macsoft-update-policy.ts` and tests,
`scripts/build-release.ps1`, and
`docs/development/MACSOFT_UPSTREAM_MAINTENANCE.md`.

**Impact and priority:**

- Trusted distribution and installer authenticity: **High**, and a blocker for
  broad external distribution unless the Product Owner accepts a narrower
  controlled pilot.
- Built-in update discovery/apply/rollback: **Later** if installer-only delivery
  is an explicit first-release policy; otherwise it becomes a release blocker.
- Hermes upstream automation: **Later**. The pinned baseline is the release
  input; a newer Hermes version must use the documented compatibility branch
  and receive a new MacSoft version/Build ID.

**Acceptance needed:** owner-approved delivery channel and signing policy;
signature and SHA-256 verification; controlled installer upgrade/rollback
instructions; proof that packaged code cannot fetch or move the Hermes pin;
compatibility matrix for every future Hermes candidate.

## Confirmed boundaries and unsupported older conclusions

- A built-in updater is not partially working; it is deliberately unavailable.
- Port handling is not dynamic; current behavior is detect-and-fail.
- Automated installer contract tests do not equal a successful real Windows
  installation or overlay upgrade.
- Passing focused tests does not make the complete Desktop UI suite green.
- Historical architecture reports contain point-in-time absolute paths, build
  IDs, staging names, and test counts. Current metadata and code take
  precedence.
- Earlier conversation reports about ACL, deletion, credentials, pairing, or
  concurrency are not current release facts unless reproduced against this
  baseline. They remain investigation clues only.

## Completed Stage 5 Work Package

**Title:** Desktop test-runner and test-baseline remediation

**Outcome:** created deterministic, non-overlapping commands for
renderer UI tests and Electron `node:test` tests; corrected stale test
expectations/mocks where current product intent was established; made the
relevant suites green without changing product behavior; preserved typecheck and
repository cleanliness.

The Work Package passed its automated acceptance and did not change intended
product behavior.

**Non-scope:** UI/product redesign, Server or Client APIs, installer/ACL/update
logic, ports, runtime ownership, AutoCount behavior, Hermes upgrade, packaging
or Release Candidate creation.

The next sequence, after owner acceptance, is clean reproducible packaging,
real clean-install/overlay acceptance, installed lifecycle acceptance, external
Client compatibility, and scoped AutoCount acceptance. Built-in updates and
dynamic ports require separate Product Owner decisions.
