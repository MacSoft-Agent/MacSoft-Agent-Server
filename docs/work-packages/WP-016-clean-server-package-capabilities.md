# WP-016 - Clean Server Package Capabilities

## Status

Implementing

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

Pending.

## Verification evidence

Pending.

## Unexpected findings

Pending.

## Remaining risks

- Real installed-product startup remains unverified until tested on a disposable
  VM or dedicated test machine.

## Final status

Pending.

## Related commits and documents

- Commits: Pending
- Decision records: Product Owner instructions in the active task
- Contracts/status/release evidence: `docs/release/RELEASE_READINESS.md`
