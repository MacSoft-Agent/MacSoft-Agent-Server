# WhatsApp–AutoCount Receiving Workflow Test Report

**Date:** 2026-08-10  
**Branch:** `improve/skill`  
**Current HEAD:** `2fde310` (`docs: design WhatsApp document ingestion`)  
**Purpose:** Record the repository, environment, document-ingestion, Skill, AutoCount, and end-to-end receiving work completed during this test cycle.

## 1. Executive summary

The Server branch was updated from the remote baseline, the local development dependencies were repaired, and WhatsApp PDF ingestion was implemented before the LLM boundary. Text PDFs can now be extracted directly; scanned PDFs can be rendered to images and routed through the existing vision path without granting terminal access to the WhatsApp Agent.

The receiving test then progressed successfully through document reading and live AutoCount creditor/Item resolution. It stopped at PO resolution and PO creation. Log inspection proved two separate problems:

1. Hermes converted the displayed PO number `PO-000001` to numeric `1` solely to satisfy a misleading live schema type, then incorrectly treated the failed lookup as proof that the displayed PO did not exist.
2. The attempted `create-purchase-order` call omitted the required approved `workflow_context`. The Server rejected it before submission, returned no command ID, and masked the specific reason as a generic `WorkflowStoreError`.

No PO was created by that failed attempt. The Receiving Skill and the shared `autocount-operations` guidance have now been updated to prevent identifier guessing, distinguish schema inspection from business queries, require the approval handshake when the active Tool contract requires it, and classify failures using command/submission evidence.

The next stage is a clean restart and a new WhatsApp session, followed by an authoritative PO list/search and a repeat of the approval path. Before that test can complete, the stale runtime AutoCount plugin registration must be reconciled with the protected packaging template so that the workflow tools required by the Skill are actually exposed.

## 2. Repository integration completed

- Merged the remote Server/main history into `improve/skill`.
- Merge evidence: commit `8639b75` (`Merge remote-tracking branch 'origin/main' into improve/skill`).
- Current upstream baseline visible in history: `8a68c77`, including the PharmaRise workflow foundation.
- Added and committed the WhatsApp document-ingestion design at `2fde310`.
- Existing unrelated working-tree changes were preserved and were not cleaned, reset, or silently included as part of this work.

## 3. Development environment repaired

The fresh-clone/start-test dependency chain was checked against the repository setup guidance and the runtime used by `start-test.bat`.

Completed environment work:

- Installed/synchronized `psycopg 3.3.4`.
- Restored `pytest 9.0.2` and the locked development extras.
- Installed PostgreSQL 17 and verified the PharmaRise workflow database/tables during the environment test stage.
- Brought the active `hermes\venv` used by the Windows start scripts in line with `uv.lock`.
- Added and installed `PyMuPDF 1.26.3` for scanned-PDF page rendering.
- Final dependency evidence at that stage: `uv sync --active --locked --check --extra macsoft-server --extra dev` reported no changes required.

## 4. WhatsApp PDF/document ingestion implemented

### Original problem

When a PDF arrived through WhatsApp, the adapter preserved only the binary file path. The Gateway then told Hermes to use terminal or the OCR/document Skill. The WhatsApp toolset intentionally did not expose terminal/file/code-execution tools, so Hermes asked the user to paste the invoice text.

### Implemented behavior

- Added a pre-LLM PDF preparation module.
- Text PDF:
  - extracts page text using `pypdf`;
  - caps injected content;
  - injects the extracted text into the same user turn.
- Scanned/image-only PDF:
  - renders up to the configured page cap as PNG using PyMuPDF;
  - appends those PNG files as image attachments;
  - reuses the existing native/text vision routing.
- Preserves the original PDF attachment for evidence/archive use.
- Adds per-message metadata so the Gateway knows whether text or page images are already available.
- Removes the contradictory instruction telling Hermes to use a missing terminal tool when preprocessing already succeeded.

### Files changed for this capability

- `hermes/gateway/document_ingestion.py`
- `hermes/plugins/platforms/whatsapp/adapter.py`
- `hermes/gateway/run.py`
- `hermes/pyproject.toml`
- `hermes/uv.lock`
- `hermes/tests/gateway/test_document_ingestion.py`
- `hermes/tests/gateway/test_document_context_note.py`

### Verification evidence

- Ruff: passed for the changed PDF/Gateway/WhatsApp files.
- Focused PDF, document-note, media-path, owner-message, formatting, and native-delivery suite: **54 passed**.
- PyMuPDF emitted five SWIG deprecation warnings; no functional failure occurred.
- Locked environment check: passed and reported no required changes.

## 5. End-to-end receiving test performed

### Test evidence

The WhatsApp user sent a generated test supplier invoice image containing:

- Creditor: `400-AI903` / `AI Test Supplier 903`
- Invoice: `INV-AI903-260810-001`
- Displayed PO: `PO-000001`
- Item: `PR-M2-TEST-001`
- UOM: `UNIT`
- Quantity: `1`
- Unit price: `MYR 1.00`
- Location: `HQ`
- Batch: `AI903-260810-A01`
- Expiry: `2028-08-31`

### Successful stages

- WhatsApp image was received and processed through vision.
- Receiving Skill was loaded.
- Connector was online for company `testing`, database/account book `AED_Testing`.
- Creditor live read succeeded:
  - active;
  - currency `MYR`;
  - terms `C.O.D.`;
  - not blocked for PO/GRN/PI operations.
- Item live read succeeded:
  - description matched;
  - purchase UOM `UNIT`;
  - `HasBatchNo = true`;
  - current batch table had no existing batch row.
- The proposed PO payload passed the exposed validation after unsupported PO fields were omitted.

### PO lookup defect

The first lookup with `docNo: "PO-000001"` failed schema validation because the deployed command schema required a number. Hermes then guessed:

```json
{"command_type":"get-purchase-order","payload":{"docNo":1}}
```

AutoCount returned:

```text
AutoCount document was not found in master data: 1
```

This result proves only that internal numeric key `1` was not found. It does not prove that displayed document number `PO-000001` is absent. Hermes retrieved the `list-purchase-orders` schema but did not execute the list command, so the live PO state remains unresolved.

### PO creation failure

After the user approved the preview, Hermes called `create-purchase-order` with the business payload but without `workflow_context`.

The Server's safety boundary requires approved workflow context for consequential commands. The call therefore failed before connector submission with:

```text
WorkflowStoreError: This consequential AutoCount command requires an approved PharmaRise workflow_context.
```

The outer Tool response masked that detail as:

```text
The AutoCount request could not be completed.
```

Evidence from the session/logs:

- no command ID was returned;
- no queued/submitted response was returned;
- the failure happened during workflow-context verification;
- therefore no PO was created by this attempt.

## 6. Receiving Skill changes

The current runtime Skill and protected packaging template were updated together.

### Safety rules made strict

- Document numbers and internal keys are opaque, distinct identifiers.
- Prefixes, punctuation, and leading zeroes must be preserved.
- `PO-000001` must never be inferred as internal key `1`.
- Reading a schema is capability discovery, not a business-data query.
- A PO may be declared absent only after an authoritative executed read proves absence.
- Chat approval does not replace workflow approval/context required by the active execution contract.
- Required approval identifiers and digest must be copied unchanged into execution context.
- No-command-ID failures are classified as pre-submission failures.
- Unknown/timeout results with a command ID require read-back before retry.

### Compatibility retained

- Company, account book, connector, PO format, command names, and field names are not hard-coded.
- Direct lookup remains preferred when the live schema accepts the displayed identifier.
- List/search is conditional and used only to resolve an internal key when necessary.
- Existing valid Cases and approval contexts should be reused.
- Deployments that do not expose or require `workflow_context` continue to follow their live Tool contract while retaining explicit preview/user approval.

### Files changed

- `runtime/skills/autocount-receiving-supplier-invoice-automation/SKILL.md`
- `runtime/skills/autocount-receiving-supplier-invoice-automation/references/po-creation-and-correction.md`
- `runtime/skills/autocount-receiving-supplier-invoice-automation/references/exceptions-and-recovery.md`
- Matching files under `packaging/templates/protected/runtime/skills/...`

The runtime Skill files are generated/runtime assets and may be ignored by Git; the protected packaging template is the durable tracked source.

## 7. Shared AutoCount operations guidance added

The identifier rules were promoted into the shared AutoCount foundation so they are not limited to Receiving.

Added guidance:

- distinction between displayed `docNo`, internal `docKey`/`autoKey`, and line/detail keys;
- live schema controls payload shape/type but does not prove semantic equivalence;
- internal keys must come from executed authoritative reads;
- schema inspection and validation do not prove record existence or business correctness;
- unresolved mappings must not be reported as missing records.

Updated:

- `runtime/plugins/macsoft-autocount/skills/autocount-operations/SKILL.md`
- protected template equivalent;
- runtime and protected-template AutoCount pre-LLM policy text.

Structural mirror, Python syntax, and Git diff checks passed for this change.

## 8. Newly discovered blocking issue

The active runtime AutoCount plugin entry point is older than its protected packaging template.

Observed difference:

- protected template imports/registers `workflow_schemas` and `workflow_tools`;
- protected template registers `workflow_case_workspace`, `workflow_approve_autocount_action`, evidence, FIFO, identity, and supplier-message workflow tools;
- active runtime `runtime/plugins/macsoft-autocount/__init__.py` registers only the generic AutoCount tools and does not register those workflow tools.

This is directly relevant: the Receiving Skill now correctly requires the approval handshake when the Tool contract requires it, but the active runtime may not expose the Tool needed to perform that handshake.

This drift has been reported but not silently overwritten in this work package. It needs a deliberate runtime/template synchronization and focused verification.

## 9. Current test stage

| Stage | Status | Evidence / remaining work |
|---|---|---|
| Repository merge | Complete | `8639b75` merged remote main into `improve/skill`. |
| Python/PostgreSQL development environment | Complete for current test setup | Locked runtime previously checked clean; PostgreSQL workflow foundation verified. |
| WhatsApp text PDF ingestion | Implemented and focused-tested | Text extraction tests passed. |
| WhatsApp scanned PDF ingestion | Implemented and focused-tested | PNG rendering/vision-routing tests passed. |
| Invoice image reading | Passed in live WhatsApp test | Invoice fields were extracted successfully. |
| Connector/company resolution | Passed | `testing` / `AED_Testing`, connector online. |
| Creditor resolution | Passed | `400-AI903` live detail returned. |
| Item/UOM/batch-control resolution | Passed | `PR-M2-TEST-001`, `UNIT`, batch-controlled. |
| Exact PO resolution | **Not passed / unresolved** | Hermes queried numeric `1`; no authoritative exact list/search completed. |
| PO preview/validation | Passed at exposed payload-schema level | Does not prove record identity or successful write. |
| Workflow approval handshake | **Blocked** | Runtime plugin registration drift may hide required workflow tools. |
| PO creation | Not submitted | No command ID; rejected before connector submission. |
| GRN/Stock Receive | Not started | Depends on exact PO resolution and approval path. |
| Batch write | Not started | `BatchNo` is expected through verified GRN/Stock Receive path. |
| Expiry write | Connector-blocked | No verified standalone `ExpiryDate` field in current schema; retain as evidence/manual follow-up. |
| Purchase Invoice | Not started | Depends on receiving result and separate preview/approval. |
| Final AutoCount read-back | Not started | Required after every consequential write. |

## 10. Recommended next actions

1. Reconcile active runtime `macsoft-autocount/__init__.py` with the protected template without overwriting unrelated runtime configuration.
2. Restart the test runtime and confirm that workflow tools, especially `workflow_case_workspace` and `workflow_approve_autocount_action`, are exposed to WhatsApp.
3. Start a new WhatsApp session so old Skill content and cached context do not influence the test.
4. Re-send the same fictional invoice.
5. Execute an authoritative PO list/search and exact-match `PO-000001`; do not convert it to `1`.
6. If the PO is proven absent, create/continue the Receiving Case, produce the exact PO preview, obtain user approval, call workflow approval, and execute with returned `workflow_context`.
7. Require command ID plus PO read-back before reporting creation success.
8. Continue to GRN/Stock Receive for Batch No, then separately preview/approve the PI.

## 11. Working-tree caution

The worktree currently contains multiple uncommitted changes beyond this report's PDF and AutoCount Skill scope, including Desktop, WhatsApp bridge/onboarding, Gateway status, and web-server files. Those changes must be reviewed and separated by ownership before staging or committing. Do not use broad staging, destructive reset, or cleanup commands.

---

# WhatsApp and Messaging Implementation Report

**Date:** 2026-08-10  
**Reference branch:** `improve/skill`  
**Reference HEAD:** `2fde310` (`docs: design WhatsApp document ingestion`)  
**Evidence basis:** Current branch history, working-tree diff, and completed verification runs.

## 1. Executive summary

The existing Hermes WhatsApp QR/Node bridge was retained and integrated with
the MacSoft-managed Host, AI Service, LLM policy, plugin, Skill, and AutoCount
runtime. WhatsApp does not enter through the Client-facing port 8787 identity
and session chain, but it now receives the approved MacSoft tool policy and
enabled plugin toolsets within the native Gateway path.

The Hermes Messaging page was restored for the full `start-test.bat` source
test runtime and connected to the existing MacSoft management boundary. The
8643 configuration backend now serves the required Messaging platform APIs,
and restart actions are routed through the MacSoft Host instead of starting or
managing a second Hermes Gateway.

WhatsApp configuration visibility, self-chat behavior, customer branding,
home-channel onboarding, PDF ingestion, and AutoCount receiving guidance were
also corrected. The WhatsApp self-improvement capability discussed after these
changes has not been implemented and is intentionally not recorded as a
delivered feature in this report.

## 2. WhatsApp backend integration

Completed behavior:

- Retained Hermes' original QR pairing and local Node.js WhatsApp bridge.
- Retained the current MacSoft Host-owned AI Service and Gateway lifecycle.
- Supported WhatsApp `self-chat` and `bot` modes.
- Supported pairing, allow-list, open-user, and group-message policies.
- Made `macsoft_autocount` and `skills_readonly` available to WhatsApp.
- Added WhatsApp to `plugin_extensible_platform_toolsets`, allowing toolsets
  from enabled plugins to extend WhatsApp without hard-coding only two fixed
  toolsets.
- Injected the MacSoft AutoCount policy into the WhatsApp LLM execution path.
- Kept WhatsApp outside the Client port 8787 Device Token, Device Profile,
  MacSoft Session ownership, and Client SQLite chat path.
- Did not introduce a parallel Gateway, bridge owner, or persistence owner.

The initial integration is represented by commit `d7fe444` (`whatsapp
features`).

## 3. Installed and development runtime handling

The WhatsApp delivery direction was changed to use the product-bundled runtime
rather than requiring a customer to assemble a separate Hermes installation.

Completed behavior:

- Host initialization prepares the WhatsApp runtime and configuration paths.
- The bridge resolves the product-managed Node.js and npm runtime.
- Bridge dependencies and WhatsApp session files are stored under the active
  MacSoft runtime home.
- A clean customer installation creates its own WhatsApp authentication state;
  development-machine WhatsApp credentials and chat state are not packaging
  inputs.
- QR pairing remains the supported first-time connection mechanism.
- Development mode continues to mean the complete `start-test.bat` source
  chain, including Host, configuration backend, AI Service, Server, and Desktop
  Vite runtime.

Relevant history includes `f3ae47d` (`docs: switch WhatsApp delivery to bundled
runtime`).

## 4. Hermes Messaging page restored in source-test Desktop

The MacSoft Desktop previously hid the upstream Messaging navigation, so
WhatsApp, Telegram, and other Messaging configuration pages were not reachable
when the complete source runtime was launched.

Completed behavior:

- Restored the original Hermes Messaging page in the explicit MacSoft source
  test runtime.
- Limited this navigation decision to the source-test environment used by
  `start-test.bat`.
- Preserved the packaged-customer runtime boundary.
- Restored only the frontend configuration experience; the page does not start
  a second Hermes Gateway or a second WhatsApp bridge.

This work was committed as `da62d6b` (`feat(desktop): restore messaging in
source test runtime`).

## 5. Messaging `Not Found` failure fixed

### Original problem

After the page was restored, it called the upstream Messaging API. The MacSoft
8643 config-only backend rejected that route, producing:

```text
Messaging platforms failed to load
Not Found
```

### Completed correction

- Allowed `/api/messaging/platforms` and its platform-management descendants
  through the 8643 config-only HTTP boundary.
- Kept platform onboarding-start routes blocked so the frontend cannot bypass
  MacSoft runtime ownership and launch another Gateway or bridge.
- Changed the Messaging restart action in MacSoft customer runtime to call the
  existing Host service action for `ai_service` restart.
- Preserved the original generic Hermes Gateway restart behavior outside the
  MacSoft customer runtime.

## 6. Messaging configuration values fixed

### Original problem

The Messaging page knew that a value was saved but treated every saved field
like a secret. Non-secret values such as WhatsApp mode and DM policy therefore
appeared as `***`, making the page unsuitable for configuration management.

### Completed correction

- Added `current_value` for non-secret Messaging fields.
- Loaded supported WhatsApp values from `.env` or `config.yaml`.
- Displayed actual non-secret values such as `self-chat`, `bot`, `pairing`,
  `disabled`, `true`, and `false`.
- Continued to redact tokens, API keys, passwords, and other fields marked as
  secret.
- Added regression coverage proving a token never receives `current_value`.

## 7. Current WhatsApp self-chat configuration

The current development runtime was configured with:

```yaml
platforms:
  whatsapp:
    enabled: true
    mode: self-chat
    dm_policy: pairing
    group_policy: disabled
```

Under this configuration, only messages sent by the paired WhatsApp account to
itself are processed. Other users and groups do not trigger the Agent. The
`/sethome` command remains available.

## 8. Home-channel onboarding hidden from WhatsApp customers

### Original problem

Every fresh WhatsApp session without a configured home target received the
generic Gateway onboarding message:

```text
No home channel is set for Whatsapp...
Type /sethome...
```

This message originated in `gateway/run.py`, not in the Node bridge.

### Completed correction

- Excluded WhatsApp from the automatic new-session home-channel notice.
- Preserved the onboarding behavior for other platforms such as Telegram and
  Slack.
- Preserved `/sethome` command handling and persistence.
- Preserved the ability to use an already configured home target for cron and
  cross-platform delivery.

## 9. WhatsApp customer branding changed to Mac Soft AI Agent

Completed customer-visible branding changes:

- Changed the default self-chat reply prefix to:

  ```text
  ⚕ Mac Soft AI Agent
  ────────────
  ```

- Changed the WhatsApp linked-device/browser identity to `Mac Soft AI Agent`.
- Changed the WhatsApp plugin description to Mac Soft AI Agent.
- Replaced capitalized `Hermes` branding in normal WhatsApp sends and streaming
  edits with `Mac Soft AI Agent`.
- Preserved lowercase operational CLI commands such as `hermes gateway
  restart`; these are real executable commands and must not be renamed.
- Left internal module names, environment variables, cache paths, comments,
  and protocol identifiers unchanged where they are not customer-visible.

## 10. WhatsApp PDF ingestion

### Original problem

When WhatsApp delivered a PDF, the Gateway retained only the binary attachment
path. The restricted WhatsApp toolset correctly omitted Terminal and arbitrary
file access, so the LLM could not read the PDF and could only ask the user to
paste its content.

### Completed behavior

For a text PDF:

- Extract page text before the LLM business-reasoning turn using `pypdf`.
- Bound the amount of injected text.
- Preserve page boundaries and identify the extracted content as untrusted
  attachment evidence.
- Preserve the original PDF for workflow evidence and archive handling.

For a scanned or image-only PDF:

- Render bounded PDF pages to PNG using PyMuPDF.
- Attach the rendered pages to the existing vision-processing path.
- Preserve the original PDF rather than replacing it with derived images.
- Avoid granting Terminal, code execution, or arbitrary filesystem tools to
  WhatsApp.

Security behavior:

- Only the file attached to the current WhatsApp message is processed.
- Existing allowed-cache-root validation remains in force.
- Extracted document content is user evidence, not a system instruction.
- Document ingestion grants no identity, approval, account-book, or AutoCount
  authority.

The design was committed as `2fde310` (`docs: design WhatsApp document
ingestion`). The source implementation is present in the current working tree.

## 11. AutoCount receiving and identifier-safety improvements

### Problem discovered during testing

During the WhatsApp supplier-invoice test, the Agent converted the displayed
PO number `PO-000001` into numeric key `1` merely to satisfy a misleading
schema type. It also treated schema inspection as though a live business search
had been executed.

### Completed Skill and policy changes

- Defined displayed document numbers, internal document keys, and line keys as
  separate opaque identifiers.
- Prohibited removing prefixes, punctuation, or leading zeroes.
- Prohibited guessing an internal key to satisfy a schema type.
- Required internal keys to come from an executed authoritative AutoCount
  read, list, or search that maps to the exact displayed identifier.
- Clarified that reading a command schema is capability discovery, not a
  business-record query.
- Required unresolved mappings to be reported as unresolved rather than as
  proof that a record is absent.
- Clarified the difference between conversational approval and workflow
  approval context required by an active Tool contract.
- Added failure classification based on command ID and submission evidence.
- Prevented pre-submission workflow-context rejection from being described as
  an AutoCount backend execution failure.
- Added read-back requirements before retrying uncertain consequential writes.

The durable protected packaging copies of the Receiving Skill, supporting
references, shared AutoCount operations Skill, and plugin policy were updated
together.

## 12. Verification evidence

Messaging, Gateway, WhatsApp onboarding, branding, and `/sethome` regression
coverage:

```text
74 passed
```

WhatsApp Node bridge verification:

```text
All WhatsApp native bridge helper tests passed
```

Focused PDF/document and WhatsApp ingestion verification recorded during the
implementation cycle:

```text
54 passed
```

Additional completed checks:

- `git diff --check` passed.
- Messaging secrets remained redacted.
- Non-secret Messaging values rendered correctly.
- WhatsApp fresh sessions did not emit the home-channel notice.
- `/sethome` behavior remained functional.
- The Mac Soft AI Agent reply prefix and linked-device identity were covered by
  regression tests.

## 13. Delivered-state boundary

This report records only behavior already present in the current branch,
working tree, or development runtime. WhatsApp self-improvement was discussed
after these changes but has not been implemented and is not part of the
delivered feature set documented above.
