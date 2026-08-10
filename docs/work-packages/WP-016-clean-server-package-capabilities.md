# WP-016 - Clean Server Package Capabilities

## Status

Complete

## Owner

- Product Owner: MacSoft Product Owner
- Execution owner: Codex
- Reviewer: Pending independent review

## Baseline

- Repository/branch: `C:\MacSoft\server\MacSoft-Agent`, `improve/skill`
- Starting commit: `1ef529a9ca0d05da8a9ddf4ffbdf5d88749e7283`
- Product and Hermes versions: MacSoft Agent 0.1.7; Hermes v2026.7.7.2
- Starting working-tree state: clean

## Objective

Produce a clean Windows Server package that omits prebuilt company workflows
while retaining the generic AutoCount connector, invoice/document extraction,
and the complete MacSoft chart-dashboard capability chain.

## User or operational outcome

The packaged Server starts without customer or development state and can be
trained later with company-specific workflows. It still supports AutoCount API
operations, attachment extraction, and dashboard generation out of the box.

## Evidence and current behavior

- `packaging/templates/protected-resources.json` currently deploys the complete
  `protected/runtime/skills` tree, including PharmaRise and accounting workflow
  Skills.
- `product_runtime/macsoft_runtime/staging.py` currently copies the complete
  template tree, so changing only the initializer manifest would still embed
  excluded workflows in the installer payload.
- The AutoCount plugin currently registers five generic AutoCount tools and six
  PharmaRise workflow tools from the same plugin entry point.
- Attachment extraction is Server code backed by Pillow, pypdf, and openpyxl;
  image content is passed to the configured vision-capable model.

## Scope

- Package only the approved dashboard Skill chain.
- Package only generic AutoCount connector tools and its operations Skill.
- Exclude prebuilt company/accounting workflow Skills and PharmaRise workflow
  plugin modules from the staged installer payload.
- Keep protected-resource upgrade reconciliation safe for administrator edits.
- Verify locked Python/Node dependencies and build an unsigned internal Windows
  installer.

## Non-scope

- Installing or launching the generated EXE on this workstation.
- Changing AutoCount Cloud authorization or business rules.
- Adding a local OCR engine.
- Changing product version, Hermes baseline, ports, or public Client contracts.

## Architectural boundaries

- AutoCount Cloud remains the authorization and command-schema authority.
- Customer/runtime state under ProgramData is not staged.
- Administrator-modified protected files survive upgrades as conflicts.
- Hermes upstream runtime and built-in capabilities remain intact.
- The external Thin Client is unchanged.

## Proposed direction

Use explicit packaged capability allowlists in the protected-resource manifest
and staging copier. Keep the full source inventory for development/history, but
exclude non-approved Skills and workflow modules from the installer. Increment
the protected-resource version so the initializer can safely reconcile
unchanged obsolete managed files during upgrade.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| A referenced dashboard Skill is omitted | Dashboard routing fails | Package and test all five Skills and references |
| Generic AutoCount plugin imports an omitted workflow module | Plugin load fails | Remove workflow imports/registrations and import-test staged plugin |
| Upgrade removes an administrator Skill | Customer data loss | Existing hash/conflict rules remain; add reconciliation tests |
| Missing binary dependency | Installed runtime fails | Locked dependency sync and import probes before packaging |
| Unsigned internal installer is mistaken for production | Trust failure | Build as `InternalTestUnsigned` and report it as non-production |

## Product Owner decisions required

None. The Product Owner explicitly approved removing packaged company workflows,
retaining AutoCount/OCR, and retaining the complete dashboard Skill chain.

## Acceptance criteria

1. The staged payload contains only the approved five top-level MacSoft Skills.
2. The staged AutoCount plugin contains and registers only the generic connector
   tools plus `autocount-operations`.
3. No PharmaRise workflow Skill, plugin module, migration, runtime data, secret,
   log, or database is present in staging.
4. Pillow, pypdf, openpyxl, FastAPI, and the packaged runtime imports succeed.
5. Dashboard references and Server `html_document` SSE tests pass.
6. An `InternalTestUnsigned` Windows installer is generated and hashed.
7. Installation and EXE startup are accurately reported as not run.

## Verification plan

- Focused automated checks: packaging contract, staging, initializer, Skill,
  file contract, and AutoCount plugin tests.
- Component/regression checks: repository cleanliness, `git diff --check`,
  locked dependency sync/import probes, Desktop package build.
- Manual or installed-product acceptance: payload inspection only; installation
  and launch explicitly excluded by owner request.
- Independent review required: yes, before completion claim.

## Implementation result

- Protected resource version increased from 4 to 5.
- The managed top-level Skill tree now uses an explicit five-Skill allowlist.
- The packaged AutoCount plugin now exposes only the five generic connector
  tools and the `autocount-operations` Skill.
- Staging excludes company workflow Skills, PharmaRise mutable configuration,
  workflow plugin modules, and the PharmaRise migration.
- Upgrade reconciliation removes obsolete unchanged protected files while
  preserving administrator-modified files as conflicts.
- An unsigned internal installer was built from the exact clean commit.

## Verification evidence

- Build commit: `721ffc89326f2c8eb3cdb3b2b5cae03ecc4891bf`.
- `uv lock --project hermes --check`: passed, 242 packages resolved.
- `uv lock --project server --check`: passed, 51 packages resolved.
- Focused unittest suites: 59 tests passed, including initializer upgrade
  safety, package/staging contracts, file extraction, and HTML SSE behavior.
- Locked-environment imports passed for FastAPI, faster-whisper, httpx,
  openpyxl, pypdf, PyMuPDF, Pillow, psutil, uvicorn, and PyYAML.
- `scripts/check-repository-cleanliness.ps1`: passed.
- `git diff --check`: passed.
- `scripts/build-release.ps1 -ArtifactMode InternalTestUnsigned`: passed.
- Staging contains 16,516 files; forbidden workflow path count: 0; forbidden
  runtime/secret/state file count: 0.
- Staged AutoCount registration probe returned exactly the five approved
  generic tools and `autocount-operations`.
- Installer: `C:\MacSoft\server\MacSoft-Agent-Packaging\release\MacSoft-Agent-Setup-0.1.7.exe`.
- Installer bytes: 230,055,729.
- Installer SHA-256:
  `90d7d37d783f8e3bcee95068f3a6706739754c74c9bfa9173d119671ed8070ce`.
- Installation and EXE startup were not run by explicit Product Owner request.

## Unexpected findings

- Related non-blocking for internal build, blocking for production readiness:
  `npm audit` reports 14 vulnerabilities (2 moderate, 11 high, 1 critical)
  across the current locked Desktop dependency graph.
- The first isolated plugin import probe omitted registration in `sys.modules`
  and failed in the test harness; the corrected probe passed. This was not a
  packaged plugin defect.

## Remaining risks

- Real installed-product startup remains unverified until tested on a disposable
  VM or dedicated test machine.
- The artifact is unsigned, has no RFC 3161 timestamp, and is explicitly not
  production-ready.
- Current npm dependency vulnerabilities require separate remediation and
  regression review before a production release claim.

## Final status

The clean internal-test package is complete and satisfies the approved payload
scope. Production release readiness is not claimed.

## Related commits and documents

- Commits: `721ffc89326f2c8eb3cdb3b2b5cae03ecc4891bf`
- Decision records: Product Owner instructions in the active task
- Contracts/status/release evidence: `docs/release/RELEASE_READINESS.md`
