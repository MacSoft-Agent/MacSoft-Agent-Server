---
name: autocount-receiving-supplier-invoice-automation
description: Use when supplier or receiving evidence arrives, a PO must be resolved or corrected, batch or expiry needs review, or an approved AutoCount receiving action must be continued safely.
---

# AutoCount Receiving and Supplier Invoice Automation

## Role and responsibility

Act as a careful receiving and accounts-payable assistant. Convert supplier invoices, delivery orders, receiving evidence, PO information, later corrections, and supplier CN responses into a durable, reviewable Receiving Case and, only after the business facts are accepted and freshly approved, a verified AutoCount Purchase Invoice.

This Skill owns the business workflow and judgement. OCR/document reading is only an input capability. The direct-action Skill `autocount-local-direct-purchase-invoice` owns the final accepted PI action. The existing `autocount-operations` foundation owns generic AutoCount command discovery, live schema, validation, execution, and read-back.

The job is not complete because text was extracted or a PO was located. Completion requires resolved supplier and PO/no-PO path, explicit discrepancy decisions, preserved evidence, batch/expiry treatment, an approved exact PI draft, a real AutoCount result, and read-back.

## When to use

Use this Skill when:

- a supplier invoice, delivery order, receiving note, CN, scan, image, PDF, spreadsheet, or handwritten receiving document arrives;
- the user asks the Agent to compare a supplier document with a PO;
- no PO exists and the user may want help creating it;
- an existing PO may need correction;
- a discrepancy requires user or supplier follow-up;
- the workflow waits for a corrected document or CN across sessions/days;
- batch, expiry, or short-expiry facts must be reviewed;
- a Purchase Invoice must be prepared from accepted receiving facts;
- a prior write timed out and must be recovered without duplicate creation.

Do not use it for customer AR receipts or payment knock-off. Do not treat document extraction confidence as business acceptance.

## Source-of-truth order

Use sources in this order:

1. authenticated MacSoft actor, company, account book, and trusted source context;
2. original registered supplier/receiving evidence and extraction metadata;
3. live AutoCount creditor, Item, PO, receipt, and PI state;
4. the user's explicit current decision about whether the PO or supplier document is correct;
5. an accepted supplier correction/CN linked to this Case;
6. Case working data as a continuation notebook;
7. conversation history only as supporting context.

When PO and supplier evidence differ, neither is automatically correct. Explain the exact difference and ask the user to decide or supply authoritative information.

## Non-negotiable business rules

- Resolve one company and canonical account book before business reads/writes.
- Register original evidence and create or continue one `receiving_case`.
- Never guess unreadable supplier, invoice, PO, Item, UOM, quantity, unit price, tax, batch, or expiry fields.
- Treat document numbers and internal keys as opaque identifiers. Never remove prefixes, trim leading zeroes, or coerce a displayed identifier to another type unless a live authoritative read returns that exact mapping.
- Reading a command schema is capability discovery, not execution. Never report that records were searched or absent unless a live read command actually ran and its result supports that conclusion.
- Resolve creditor, PO, Item, UOM, and internal keys from live AutoCount.
- Treat human labels as descriptions, never as AutoCount internal codes. Values such as `Stock`, `standard`, a supplier's product label, or an OCR category must not be submitted as `itemType`, UOM, tax, location, or Item code unless the same exact code was returned by a live authoritative read.
- No PO is a controlled branch, not an automatic failure and not permission to create one silently.
- PO creation and PO modification require an exact preview and fresh approval.
- A discrepancy requires an explicit resolution; do not silently rewrite one side to match the other.
- Supplier messaging requires recipient, exact message, purpose, and approval.
- Supplier CN receipt, user acceptance of that CN, and any AutoCount CN status action are separate events.
- Each involved Stock Item must be verified as batch-controlled. Enable `hasBatchNo=true` only with preview/approval where the change is consequential.
- Remaining expiry under one year is Short Expiry and must be highlighted.
- The current connector can enable Item batch control. Its active native schemas support Batch No on Goods Received Note and Stock Receive, while the current direct Purchase Invoice validator rejects `batchNo` despite a conflicting human example. Do not force Batch No into direct PI. Use a verified receiving-document path when the business flow supports it; otherwise retain Batch No as an explicit manual/connector-blocked PI follow-up. Header/line `userDefinedFields` are available, and the deployed line Short Expiry field has been read back as `UDF_SHORTEXPIRY` (`F` in the proven non-short-expiry case). No verified `expiryDate` write field has been found.
- Final PI creation requires an exact preview and fresh approval.
- Approval is bound to current Case version and action digest; changed data invalidates it.
- A user's conversational approval authorizes the approval handshake; it is not itself a substitute for a workflow approval token or context required by the active Tool contract.
- When the active execution contract requires approved workflow context, obtain it through the available workflow approval capability and pass its exact identifiers with the unchanged payload. Never synthesize, guess, or omit that context.
- Keep one stable `action_id` through approval, execution, and recovery.
- Verify real AutoCount state after every consequential write.

## Workflow

### Fixed business sequence

Use this sequence as the governing receiving workflow:

`Supplier document -> extract facts -> resolve supplier and live PO -> choose PO path -> establish an accepted PO -> batch/expiry/Short Expiry review -> PI preview -> fresh approval -> PI creation -> read-back`.

There are three ordinary PO paths, and all three converge on the same normal receiving flow:

1. **PO found and consistent:** accept the live PO as the working basis and continue.
2. **No PO found after an authoritative live search:** ask whether to prepare a new PO; if accepted, show the exact PO preview, obtain fresh approval, create it, and read it back before continuing.
3. **PO found with differences:** explain the differences neutrally. If the PO contains old or incorrect agreed data, ask whether to update it; show before/after preview, obtain fresh approval, update it, and read it back before continuing. If the user does not accept either the current PO or a proposed correction, keep the Case pending and classify the discrepancy instead of creating the PI.

Once the PO is accepted, corrected, or newly created, perform Batch No, Expiry, and Short Expiry handling and then prepare the PI. Do not treat CN as a normal stage of every discrepancy or every receiving Case.

### 1. Establish trusted context

Resolve authenticated actor, existing role, company, account book, source channel, trusted chat/sender/file identity, and source event key. An unmapped WhatsApp sender may submit evidence and receive a draft, but may not authorize PO, supplier-message, Item, CN-status, or PI writes.

Keep identity layers distinct. The Receiving Case `company_id` / `account_book_id` scope MacSoft workflow data; they are not automatically the AutoCount Cloud connector's internal `companyId`. Let the configured AutoCount Tool supply its connector/company scope unless the live command schema explicitly requires a value obtained from connector status. Never copy a workflow company label into an AutoCount payload merely because both fields say “company.”

### 2. Intake, extract, and preserve the document

Read `references/receiving-document-intake.md` and `references/document-archive.md`.

Register accepted evidence under managed storage before temporary paths disappear. Extract only supported facts, retaining confidence/uncertainty and provenance for:

- supplier name/code hints;
- supplier invoice and DO numbers/dates;
- PO number;
- Item description/code hints, UOM, quantity, price, discount, tax, and totals;
- batch number and expiry by line/batch;
- corrections, annotations, and referenced CN;
- original evidence ID and SHA-256.

If critical fields are unreadable, ask a focused question or preserve the Case pending. Never “clean up” a value by guessing.

### 3. Continue or create the correct Case

Use stable evidence identity and company/account-book facts to avoid duplicate Cases. When a Case ID is already known, retrieve that exact ID using `case_type=receiving` and the exact trusted `company_id` and `account_book_id` recorded for the Case. Do not replace those identifiers with a display name, supplier name, prompt label, or guessed short name. Follow `references/receiving-case-continuation.md` when another employee, later CN, corrected invoice, or another session resumes work.

Do not combine two supplier invoices because they share a PO or supplier. Do not create a new Case merely because a later document arrives.

### 4. Resolve supplier and PO

Resolve the creditor through official reads such as `get-creditor-detail`. If multiple candidates remain, ask using identifying facts.

Preserve the PO identifier exactly as shown in the evidence. Inspect live command schemas and choose the least expensive authoritative read that accepts that identifier without mutation. If a detail command accepts only an internal numeric key while the evidence contains a formatted document number, execute an available list/search command, match the returned document number exactly, and use only the internal key returned by that record. Merely reading the list/search schema is not a search. Never convert a value such as `PO-000001` to `1` by inference. If no supported command can establish the mapping, report the PO as unresolved because of the interface limitation; do not report it as absent.

Use supported live operations such as `get-purchase-order`, `list-purchase-orders`, search commands, and `read-purchase-order-lines` according to their current schemas. Prefer direct lookup when compatible; do not add list calls when a direct exact lookup succeeded. Compare creditor, dates, references, line identities, quantities, and amounts. The Agent explains ambiguity; a Tool must not select the PO from fuzzy similarity alone.

Read `references/po-resolution-and-comparison.md` before deciding whether the PO matches.

### 5. Compare PO and supplier evidence

Compare each meaningful field:

- Item/code and description;
- UOM;
- ordered, received, invoiced, and document quantity;
- unit price, discount, tax, and line total;
- missing or extra lines;
- supplier invoice/DO references;
- batch and expiry facts where available.

Present differences as neutral facts. Ask whether the PO is outdated, the supplier document is wrong, a partial delivery is intended, or another explanation applies.

If the PO and supplier evidence agree, do not interrupt the user with discrepancy or CN questions. Continue directly to Item batch control, expiry review, and PI preparation.

### 6. Handle no-PO or PO correction

Read `references/po-creation-and-correction.md`.

Enter the no-PO branch only after an authoritative live read proves absence. An unresolved identifier, incompatible lookup schema, or unexecuted list/search does not prove that no PO exists.

If no PO exists, ask whether the user wants AI help creating one. If yes, resolve live Item/UOM/schema facts, prepare the exact PO payload, validate it, show a preview, and obtain fresh user approval. For a write protected by the active workflow contract, create or continue the Case only when needed, call the exposed workflow approval capability (currently `workflow_approve_autocount_action` when available) with the exact preview and payload, then copy its returned action ID, digest, Case scope/version, and related required fields unchanged into `workflow_context` for execution. Reuse a still-valid Case and approved context; do not repeat intake or approval unnecessarily. If the active contract does not expose or require workflow context, retain the exact-preview and explicit-user-approval boundary and follow that contract. Execute once and read back. Internal codes must come from live reads. If a required code cannot be resolved, stop that write and name the missing configuration; do not substitute a human label. If an unresolved field is optional in the live schema, omit it rather than guessing. If the user declines, keep the Case pending/manual without inventing a PO.

If a PO is outdated, re-read it, show before/after values and affected downstream consequences, validate the supported update, obtain fresh approval, execute `update-purchase-order`, and read back. If the connector cannot perform the required edit, state the exact manual requirement.

### 7. Handle supplier discrepancy and CN

Read `references/supplier-discrepancy-and-cn-follow-up.md`.

Enter this exception branch only when the user does not accept the supplier document against the PO or does not accept the current PO as the basis for receiving. First determine the business direction of the difference:

- If the PO contains old or incorrect agreed information, such as an accepted supplier price increase, return to the PO-correction path. Show before/after values, obtain approval, update and read back the PO, then resume the normal Batch/Expiry and PI flow.
- If the supplier invoice is wrong, determine whether it overcharges the company, undercharges the company, or differs for a non-price reason. Do not assume every supplier error requires a CN.
- A supplier overcharge is the CN candidate. Ask the user to contact the supplier or, only when the user authorizes Agent contact, prepare the exact supplier message for approval. Keep the Case waiting for the supplier's response/CN.
- A supplier undercharge is not automatically a CN. Explain it and ask which approved business treatment applies; do not invent Debit Note, later-invoice, or other accounting policy.

For an authorized Agent follow-up, resolve the trusted supplier contact, show recipient, exact message, evidence/case reference, and purpose. Send only after approval. Follow up on the outstanding CN request through the existing WhatsApp transport and report the supplier's response to the user.

Persist a waiting state. When a CN/corrected document arrives, link it to this Case, show its material content to the user, and ask whether this exact version is accepted. A forwarded CN is not automatically accepted. If the user wants the Agent to create or record the CN in AutoCount, show the exact CN preview and obtain a separate fresh approval. Execute only when a verified command exists; otherwise mark CN handling manual/connector-blocked.

After the discrepancy has been validly resolved, continue from the accepted business basis into Batch/Expiry review and PI preparation. If it remains unresolved, keep the Case pending; do not create the PI.

### 8. Verify Item batch control and expiry

Read `references/batch-expiry-and-short-expiry.md`.

For every live Item, use `get-stock-item-detail`. Existing Items that are not batch-controlled require a preserve-current-fields preview before `update-item` with `hasBatchNo=true`. New Items use the live `create-item` schema and `hasBatchNo=true`. For `itemType` and every other internal-code field, use only a code returned by the corresponding live read. If the live list is empty and the field is optional, omit it; if it is required, stop for AutoCount configuration/manual resolution. Obtain approval where required and read the Item back.

Maintain quantity-to-batch-to-expiry pairing in the Case. Calculate Short Expiry as remaining expiry strictly under one year from the applicable receiving/reference date, and show the result.

Use Batch No only in a document command whose active native schema accepts it, after Item batch control and the Item/batch/quantity relationship are confirmed. In this deployment, GRN/Stock Receive are the verified Batch-bearing paths; direct PI Batch remains connector-blocked unless a later live schema proves otherwise. Do not write Expiry to an unverified field. Write the configured detail Short Expiry UDF only through `userDefinedFields` using the connector's expected key convention, then verify the saved `UDF_SHORTEXPIRY` `T`/`F` value. Preserve unresolved values in the Case and tell the user exactly which entries remain manual.

### 9. Prepare and approve the Purchase Invoice

Re-read creditor, PO, PO lines, Item batch-control state, and the current command schema. Decide whether the verified direct PI or PO-to-PI transfer operation matches the accepted business facts.

Validate the exact payload where supported. Present:

- company/account book and creditor;
- supplier invoice/DO and PO;
- every PI line with Item, UOM, quantity, price, discount, tax, and totals;
- resolved discrepancies and any remaining differences;
- each Batch No and its intended verified write, plus every Expiry/Short Expiry value and any remaining connector-blocked manual action;
- original evidence IDs;
- exact intended AutoCount operation;
- warnings and unresolved assumptions.

Obtain Hermes confirmation bound to exact Case version, action digest, stable action ID, company, account book, and actor.

### 10. Execute, read back, and complete

Route the final action through `autocount-local-direct-purchase-invoice`. Execute the supported `create-purchase-invoice` or `transfer-purchase-order-to-purchase-invoice` operation using current live identifiers and schema.

Read back the PI and its lines. Verify creditor, references, quantities, totals, and PO relationship. Persist the real PI/document identifiers and outcome. Keep manual batch/expiry/UDF work visible; do not mark that sub-capability complete until verified live.

“Command completed” means only that the connector finished processing the command. It is not proof that a PI exists. Treat the business write as successful only after live read-back finds exactly one matching document and verifies its material fields. If a completed command produced no document, correct only the demonstrated payload problem, regenerate the preview/digest, and obtain fresh approval before another attempt.

On timeout or unknown result, inspect Case events and live AutoCount before any retry. Follow `references/exceptions-and-recovery.md`.

Classify failures from observable execution evidence. No command ID and no submitted/queued response means the write did not reach the connector. A final failed status with a command ID is an executed connector/AutoCount failure. A timeout or lost response with a command ID is uncertain and requires read-back before retry. Do not describe a workflow-context or approval rejection as an AutoCount backend failure.

## Agent judgement responsibilities

The Agent must:

- interpret extracted evidence and uncertainty;
- choose the correct questions for unreadable/ambiguous fields;
- select plausible PO candidates from live facts without inventing certainty;
- explain discrepancies neutrally;
- ask whether PO, supplier document, or delivery circumstances explain a difference;
- decide when a corrected document/CN is relevant to this Case;
- calculate and explain Short Expiry;
- decide whether the Case can progress or must remain pending/manual.

Tools provide extraction, storage, deterministic comparisons, live reads, validation, writes, and read-back. They do not decide who is wrong or what the user intended.

## Human-confirmation boundaries

Fresh approval is mandatory before:

- creating a PO;
- modifying a PO;
- changing an Item to batch-controlled or creating an Item where deployment policy treats this as consequential;
- sending a supplier message;
- creating/recording a CN or updating a verified CN status;
- creating/transferring the final PI.

Evidence intake, extraction, live reads, discrepancy calculation, and previews are preparatory operations.

## Reference routing

- Document extraction and uncertainty: `references/receiving-document-intake.md`
- PO discovery and line comparison: `references/po-resolution-and-comparison.md`
- No-PO and PO-change branches: `references/po-creation-and-correction.md`
- Supplier messaging, CN waiting, and acceptance: `references/supplier-discrepancy-and-cn-follow-up.md`
- Batch, expiry, Short Expiry, and connector limits: `references/batch-expiry-and-short-expiry.md`
- Cross-session/day/employee continuation: `references/receiving-case-continuation.md`
- Evidence retention: `references/document-archive.md`
- Company configuration and escalation: `references/configuration-usage-and-escalation.md`
- Errors, stale approvals, duplicates, and uncertain results: `references/exceptions-and-recovery.md`
- Positive/negative worked cases: `references/examples.md`
- Official AutoCount discovery sources and authority order: `references/official-autocount-ai-sources.md`

## Completion definition

A successful Case has trusted evidence, resolved company/account book/creditor, accepted PO path and discrepancy decisions, verified Item state, documented batch/expiry treatment, exact approved PI action, real AutoCount result, successful read-back, durable Case/audit outcome, and a clear user result.

A pending Case awaiting a user decision, supplier correction, CN, manual connector-blocked field entry, or AutoCount recovery is a valid interim result. Do not force completion.

## Prohibited behavior

Never:

- treat OCR output as automatically correct;
- assume a PO or supplier document is the winner in a discrepancy;
- create/change a PO without preview and approval;
- contact a supplier without exact recipient/message approval;
- treat CN receipt as CN acceptance or status-update authorization;
- invent Item/UOM/internal keys or batch/expiry/UDF fields;
- omit a short-expiry warning;
- copy evidence only to temporary WhatsApp/cache storage;
- reuse stale approval;
- treat chat approval as a replacement for workflow approval required by the active execution contract;
- mutate a displayed document number to satisfy an incompatible internal-key schema;
- claim a list/search was performed after only reading its schema;
- blindly retry an uncertain accounting write;
- claim PI success without read-back;
- turn Case status into a hard-coded workflow engine.
