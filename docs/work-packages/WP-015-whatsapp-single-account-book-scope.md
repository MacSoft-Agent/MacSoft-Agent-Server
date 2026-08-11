# WP-015 - WhatsApp Single Account Book Scope

## Status

Verifying

## Owner

- Product Owner: User (approved 2026-08-10 in this task)
- Execution owner: Codex
- Reviewer: Required before release integration

## Baseline

- Repository/branch: `C:\MacSoft-Agent-Github\MacSoft-Agent`
- Starting commit: `0551717`
- Product and Hermes versions: product `0.1.7`; protected resource version advanced from 4 to 5 so an installed upgrade can receive the approved protected workflow change
- Starting working-tree state: pre-existing receiving-Skill and workflow-test changes; preserve them

## Objective

Allow WhatsApp workflows to inherit the one configured MacSoft company/account book silently while retaining strict scope isolation and refusing ambiguous multi-account-book selection.

## User or operational outcome

When Server configuration contains exactly one company/account book, WhatsApp can create or continue its internal Case without asking customers to map a chat or understand database identifiers. Customers still provide payment and cleared-bank evidence, review the allocation preview, approve the write, and receive a verified read-back result.

## Evidence and current behavior

- `workflow_case_workspace` calls `_enforce_trusted_scope` before Case persistence.
- WhatsApp currently succeeds only when an active chat row exists in `whatsapp_identifiers`.
- The installed product separately preserves `skills/pharmarise-company-configuration/references/account-books.md` as customer-owned configuration.
- No product path was found that creates a chat mapping during normal WhatsApp setup.
- The Product Owner explicitly approved single-account-book inheritance and customer-hidden Case handling.

## Scope

- Resolve a missing WhatsApp chat mapping from exactly one configured company/account-book scope.
- Keep an explicit active chat mapping authoritative when it exists.
- Reject missing, malformed, or multiple configured scopes instead of guessing.
- Keep Case creation, approval, execution, and read-back safeguards unchanged.
- Add focused contract tests and customer-facing Skill guidance.
- Require preview/approval for every WhatsApp AutoCount mutating command while leaving reads available.
- Return an actionable, non-sensitive workflow authorization reason and whether a command was submitted.
- Remove an unmanaged nested duplicate of the Payment Skill from active discovery and verify one canonical candidate.
- Persist an accepted Payment Slip immediately as a durable `waiting_bank` record and make later bank-evidence lookup deterministic across sessions.

## Non-scope

- Automatic selection among multiple account books.
- Changing AutoCount command payloads or bank-evidence requirements.
- Adding a customer-facing Case or database setup flow.
- Installer, schema migration, product version, or external Client changes.

## Architectural boundaries

- The AutoCount connector `companyId` remains distinct from workflow `company_id` and `account_book_id`.
- Model-supplied scope may never override an explicit trusted WhatsApp mapping.
- Customer-owned company configuration remains mutable and upgrade-preserved.
- Consequential writes still require exact Case version, approval digest, execution, and read-back.

## Proposed direction

Extend the existing plugin scope guard. First use the active chat mapping. If none exists, parse the existing account-book reference and accept it only when it contains exactly one complete unique company/account-book pair matching the requested scope. This introduces no new persistence owner, Tool, or customer configuration surface.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Ambiguous configuration selects the wrong ledger | Cross-account write | Fail closed unless exactly one complete scope exists |
| Model changes scope arguments | Cross-company access | Require exact equality with the trusted resolved scope |
| Existing explicit mapping is bypassed | Security regression | Explicit active chat mapping remains first authority |
| Customer config format varies | Workflow unavailable | Support the established Markdown key/value form and test malformed input; fail closed |

## Product Owner decisions required

None. The Product Owner explicitly selected the single-account-book automatic inheritance behavior and confirmed that Case is internal.

## Acceptance criteria

1. An explicitly mapped WhatsApp chat retains its configured scope.
2. An unmapped WhatsApp chat inherits exactly one configured company/account book.
3. Missing, incomplete, or multiple account-book scopes fail without selecting one.
4. A requested scope mismatch always fails.
5. Customer guidance does not ask users to map WhatsApp, provide database identifiers, or understand Cases.
6. Payment bank-evidence, approval, execution, and read-back rules remain enforced.
7. WhatsApp create/update/edit/void/delete/transfer/post/save/set commands cannot execute without workflow approval.
8. A missing approval returns `workflow_approval_required`, `stage=workflow_authorization`, and `submitted=false` instead of a generic failure.
9. Module 1 customer replies lead with the business conclusion, use a short flat comparison when needed, and ask only for the next required decision.
10. Once the user confirms Knock-Off follow-up, Payment Slip intake is stored before the success reply with status `waiting_bank`.
11. Later Bank Transaction/Statement intake can search pending records by status and stable payment facts without relying on chat memory.

## Verification plan

- Focused automated checks: `product_runtime/tests/test_pharmarise_workflow.py`
- Component/regression checks: product runtime tests plus `git diff --check`
- Manual or installed-product acceptance: required before release; test a fresh WhatsApp session against a real single-account-book installed configuration
- Independent review required: yes, because this changes an AutoCount workflow security boundary

## Implementation result

- Added a fail-closed parser for complete `company_id` / `account_book_id` pairs in the existing customer-owned `account-books.md` reference.
- Kept an active explicit WhatsApp chat mapping as the first authority.
- Added automatic inheritance only when exactly one unique configured scope exists and required the model-requested scope to match it exactly.
- Replaced customer-facing mapping/Case/database instructions with an administrator-setup message.
- Extended the existing execution guard so all WhatsApp mutating command prefixes require the existing workflow approval path; no Tool was added.
- Added structured, safe workflow error reasons so the Agent can distinguish local approval failures from AutoCount/Connector/license failures.
- Added progressive-disclosure and conversational WhatsApp response rules to Module 1 and its final-action Skill.
- Changed Payment Slip intake to default to `waiting_bank`, record the intended Knock-Off continuation, and expose deterministic pending-search filters for later bank matching.
- Added response guidance that avoids repeating the full slip preview after persistence and summarizes bulk bank-statement matching instead of dumping every row.
- Moved the unmanaged nested duplicate Payment Skill to `runtime/quarantine/duplicate-skills/autocount-payment-knockoff-automation-nested-20260810`; the active Skill scan now finds one canonical candidate.
- Synchronized the authoritative protected Plugin/Skill files to the development runtime and restarted the Host-owned AI Service successfully.
- Advanced the protected resource version from 4 to 5 for installed-product delivery.

## Verification evidence

- `python -m unittest product_runtime.tests.test_pharmarise_workflow`: 25 passed.
- `PYTHONPATH=product_runtime python -m unittest product_runtime.tests.test_initializer`: 9 passed.
- `PYTHONPATH=product_runtime hermes/venv/Scripts/python.exe -m unittest discover -s product_runtime/tests -p 'test_*.py'`: 93 passed after the pending-payment persistence and search changes.
- `hermes/venv/Scripts/python.exe -m pytest hermes/tests/gateway/test_session_env.py -q`: 17 passed (one non-failing pytest cache permission warning).
- Active runtime Python compilation passed for `tools.py` and `workflow_tools.py`.
- Active runtime Skill scan returned exactly one `autocount-payment-knockoff-automation` candidate.
- Host control restart reported AI Service `running` before, during, and after restart with a new owned process.
- `git diff --check`: passed; line-ending conversion warnings only.
- Two broader attempts with system/bundled Python reached 69 tests but could not import `psutil`; rerunning with the repository Hermes environment completed all 83 tests.

## Unexpected findings

- In scope: the account-book reference templates are protected/mutable resources and are intentionally absent from normal tracked source contents.
- Unrelated: pre-existing receiving workflow edits are present and will not be reverted or staged broadly.

## Remaining risks

- Installed-product acceptance cannot be replaced by mocked unit tests.
- Independent review has not yet been performed.

## Final status

Implementation and automated verification complete; installed-product acceptance and independent review remain before release integration.

## Related commits and documents

- Originating workflow commit: `73fc529`
- Product Owner approval: current task, 2026-08-10
