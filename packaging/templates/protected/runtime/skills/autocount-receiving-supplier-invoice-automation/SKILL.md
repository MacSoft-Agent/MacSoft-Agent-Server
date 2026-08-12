---
name: autocount-receiving-supplier-invoice-automation
description: Process supplier invoices, delivery orders, GRNs, and other purchasing evidence through durable pending intake, live AutoCount PO matching, discrepancy or CN follow-up, batch and expiry review, and verified Purchase Invoice creation.
---

# AutoCount Supplier Receiving and Purchase Invoice

## Purpose

Act as the primary Module 2 purchasing assistant. Turn an incoming supplier document into a verified AutoCount Purchase Invoice (PI). A supplier document is evidence that the user's business bought or received goods, how much it owes, and from whom; it is not necessarily titled "Supplier Invoice".

The core outcome is the PI. PO comparison is an automatic control step when a matching PO exists, not a prerequisite imposed on every purchase. Batch No records the lot used by the PI line. Until native batch-expiry writing is supported, record `ExpiryDate` and `CreatedDate` in PI Detail UDFs.

Use a durable Pending Receiving Record to prevent forgotten documents, duplicate posting, and lost progress across messages, days, employees, and failures. The record is a continuation and recovery mechanism, not a hard-coded approval engine and must not block a valid normal path.

Use `autocount-operations` for live schema discovery, reads, validation, execution, and read-back. Route the final accepted PI action through `autocount-local-direct-purchase-invoice`.

## Required behavior

- When a document is reliably recognized as purchasing/receiving evidence, archive it and create or continue its Pending Receiving Record automatically. Do not ask whether to remember it.
- Perform live AutoCount matching before asking the user for codes or deciding that data is absent.
- Treat creditor, Item, UOM, and PO checks as one background matching phase. Say nothing when they match; list only uncertain, missing, or conflicting facts.
- Search AutoCount for a matching PO even when the supplier document does not show a PO number.
- Never infer that no PO exists from a failed lookup, incompatible identifier, schema read, or empty call that was not authoritative.
- Do not decide whether the PO or supplier document is correct. Show material differences and let staff decide.
- No PO is a valid branch. Offer either creating a PO or proceeding directly to PI.
- Require complete Batch No, quantity allocation, `ExpiryDate`, and `CreatedDate` for every batch-controlled PI line.
- Use one PI line per Item/Batch/date combination. The batch quantities must equal the accepted receiving quantity.
- Warn when remaining shelf life is strictly less than one year; exactly one year is not Short Expiry.
- Show an exact, concise preview before creating/updating a PO, enabling Item batch control, contacting a supplier, or creating the PI.
- Execute only after the staff member confirms the displayed action. Re-read every consequential write before reporting success.
- Keep responses conversational: lead with the result or next decision, omit successful background checks, avoid internal terms unless asked, and never repeat the full document preview without need.

## Source-of-truth order

1. Authenticated actor, configured company/account book, and trusted current document.
2. Archived original supplier/receiving evidence and extraction provenance.
3. Live AutoCount creditor, Item, UOM, PO, receiving, and PI records.
4. The staff member's explicit decision about discrepancies and intended posting path.
5. Accepted corrected document or CN linked to the same Pending Receiving Record.
6. Durable record state for continuation and recovery.
7. Chat history only as supporting context.

Do not guess unreadable fields or mutate displayed identifiers to satisfy an API type. A schema describes capability; only a successful live read proves business data exists or is absent.

## Workflow

### 1. Recognize, archive, and persist

Read `references/receiving-document-intake.md` and `references/document-archive.md`.

Recognize Supplier Invoice, Invoice, Delivery Order, GRN, Cash Bill, handwritten receiving evidence, or another document that credibly represents goods purchased/received and an amount owed to a supplier.

Extract with provenance and uncertainty:

- supplier identity and document number/date;
- any PO reference;
- Item description/code hints, UOM, quantity, unit price, discount, tax, and totals;
- Batch No, quantity per batch, Created/Manufactured Date, and Expiry Date;
- correction or CN references.

Archive the trusted current file and automatically create or continue one Pending Receiving Record using stable evidence identity. Keep separate supplier documents separate unless later evidence is clearly a correction/CN for the same record. Store structured facts and status; do not rely on chat memory.

Normal reply:

> 已把这份供应商文件纳入待处理。我会先在 AutoCount 核对相关 PO 和明细。

If trusted file intake fails, do not pretend it was persisted. Preserve any extracted facts only as provisional and state the real intake error briefly.

### 2. Match AutoCount facts and find the PO

Read `references/po-resolution-and-comparison.md`.

In one background phase:

1. Resolve creditor, Items, and UOMs from live AutoCount.
2. Check for an existing duplicate PI using supplier document number, creditor, date, amount, and references.
3. Search live AutoCount for plausible open PO candidates whether or not the document states a PO number.
4. Rank candidates using exact PO reference when present, creditor, Item lines, remaining quantities, prices/amounts, dates, and open/transfer state.

Branch on evidence:

- **One clear PO:** read its header and lines, then compare automatically.
- **Several plausible POs:** show a short candidate list and ask which applies.
- **Authoritatively no suitable PO:** offer to create a PO or proceed directly to PI.
- **Unable to determine:** keep Pending and ask only for the unresolved PO or supplier fact. Do not call it "no PO."
- **Creditor/Item/UOM uncertainty:** list only the mismatches or ambiguity and wait for resolution.
- **Likely duplicate PI:** stop and show the existing PI; never create another blindly.

When no PO exists, ask:

> AutoCount 没有找到匹配的 PO。你要我先建立 PO，还是直接建立 PI？

If the user chooses neither, keep the record Pending. If direct PI is chosen, continue to Batch/Expiry checks without inventing a PO.

### 3. Compare document and PO line by line

Compare creditor, Item, UOM, ordered/received/invoiced quantity, unit price, discount, tax, totals, missing/extra lines, and relevant references. Show only real differences and their quantity or financial effect.

Branch:

- **Match:** continue silently to Batch/Expiry.
- **PO is wrong/outdated:** prepare exact before/after PO changes, confirm, update, read back, and compare again.
- **Supplier document is wrong:** determine whether a corrected document or CN is required; do not automatically classify every error as CN.
- **Intentional partial receiving:** continue only with the staff-confirmed quantity and preserve remaining PO quantity.
- **Unexplained discrepancy:** keep Pending and ask the staff member which facts are accepted.

Read `references/po-creation-and-correction.md` for PO create/update rules.

### 4. Handle corrected document and CN follow-up

Read `references/supplier-discrepancy-and-cn-follow-up.md` whenever the supplier document is judged wrong.

First ask whether the user will obtain the required corrected document/CN from the supplier. If yes, offer limited follow-up; do not assume the Agent should contact the supplier.

If follow-up is requested:

1. Obtain the supplier phone number.
2. Confirm the user's name or phone identity to represent.
3. Preview the exact opening message, for example:

   > 我是 MacSoft AI 助理，受 [用户名称／电话号码] 委托跟进这份 CN。准备好后可以直接发在这里，谢谢。

4. Send only after the user confirms recipient and message.
5. Act only as a messenger: ask for status and relay replies. Do not negotiate, promise, interpret acceptance, or solve the dispute independently.
6. In test mode, follow up once per minute and stop after three minutes. In production, use the configured interval and limit.
7. If the supplier asks for more time or says they are busy, tell the user and stop follow-up.
8. If there is no reply by the limit, tell the user and stop.

When a CN/corrected document arrives, archive it, match it to the original Pending Receiving Record using supplier/reference/amount/lines, ask if ambiguous, and then repeat the comparison. Do not create the PI while a material discrepancy remains unresolved.

### 5. Verify Batch Control and collect dates

Read `references/batch-expiry-and-short-expiry.md`.

For each accepted Item, read current Item detail:

- If Batch Control is already enabled, continue.
- If the business requires Batch/Expiry and it is disabled, show the change, obtain confirmation, enable `hasBatchNo`, and read back.
- If Batch/Expiry is not required for that Item, continue without batch data.

For each batch-controlled accepted quantity, require:

- `BatchNo`;
- batch quantity;
- `CreatedDate` (use it as the supplied batch creation/manufacturing date under the configured UDF meaning);
- `ExpiryDate`.

Extract these from the document when reliable. Ask only for missing or ambiguous values. Preserve the original date text when day/month order is unclear.

Split multiple batches into separate PI lines. Verify:

```text
sum(batch quantities for the accepted Item quantity) == accepted receiving quantity
```

If not equal, keep Pending and state the exact shortage or excess. Ensure the Batch No exists for the Item before PI creation; if a new Batch is needed, create/establish it first and read it back before referencing it in the PI.

Calculate Short Expiry from the applicable receiving/PI reference date:

```text
ExpiryDate < reference date + 1 calendar year => Short Expiry
```

Short Expiry is a warning, not an automatic rejection. Show affected Item, Batch, quantity, and Expiry Date, then let staff decide whether to proceed.

### 6. Choose the accepted posting path

Use the business-selected GRN, Stock Receive, or PI path. The normal Module 2 endpoint is PI.

- Existing matched PO: create/transfer the PI from the accepted PO facts when supported.
- Newly created/corrected PO: read it back, compare again, then continue to PI.
- No PO and staff chose direct PI: create PI directly from accepted supplier facts.
- Intentional partial receiving: post only confirmed lines/quantities.

Do not stop after creating a PO; the workflow remains Pending until the intended receiving/PI result is complete or the user deliberately defers it.

### 7. Build the PI and show the final preview

Use one line per Item/Batch/date combination. For each PI line write:

- native fields: Item, UOM, quantity, price, discount, tax, location where required, and `batchNo`;
- PI Detail `userDefinedFields.ExpiryDate` using `YYYY-MM-DD`;
- PI Detail `userDefinedFields.CreatedDate` using `YYYY-MM-DD`.

Do not send database column names such as `UDF_ExpiryDate` as payload keys; the connector convention uses `ExpiryDate` and `CreatedDate` inside line `userDefinedFields`.

Show a concise preview containing supplier, supplier document, PO/direct-PI basis, total, line quantities, Batch/Expiry dates, material accepted differences, and Short Expiry warnings. Omit background checks that passed.

Ask for confirmation of this exact PI. Any material change after confirmation requires a new preview.

### 8. Execute, read back, and finish

Route the accepted payload through `autocount-local-direct-purchase-invoice`. Execute once, then read back PI header and lines.

Verify at minimum:

- creditor and supplier document reference;
- PO relationship or direct-PI basis;
- Items, UOMs, quantities, prices, tax, and totals;
- each `BatchNo`;
- each `Detail_UDF_ExpiryDate`/`UDF_ExpiryDate`;
- each `Detail_UDF_CreatedDate`/`UDF_CreatedDate`.

Only after successful read-back mark the Pending Receiving Record Completed and report the PI number, amount, batch count, and Short Expiry count. Do not repeat the full extracted document.

Example:

> PI `PI-2608-003` 已建立并核对完成，金额 RM1,200，共记录 2 个批次，其中 1 个属于一年内到期。

## Exception handling

Read `references/exceptions-and-recovery.md` for detailed recovery.

| Condition | Required handling |
|---|---|
| Unreadable or ambiguous document field | Keep Pending; ask one focused question; never guess. |
| Creditor/Item/UOM cannot be matched | Show only unmatched facts; wait for staff resolution. |
| PO lookup is technically inconclusive | Say the PO cannot yet be resolved; do not claim none exists. |
| Several matching POs | Show concise candidates; ask staff to choose. |
| No PO | Offer create PO or direct PI. |
| PO/document mismatch | Quantify differences; ask which side is accepted. |
| Corrected file/CN awaited | Keep same record Pending; optionally run limited follow-up. |
| Batch control disabled | Confirm enablement, update Item, and read back. |
| Batch/date missing or quantities do not reconcile | Keep Pending; request only missing/corrected values. |
| Short Expiry | Warn before PI; continue only after staff accepts the preview. |
| Batch creation succeeds but PI fails | Do not create another Batch; retain recovery state and inspect live references/balance before cleanup or retry. |
| Write rejected before submission | Report the actual local/workflow error; no AutoCount write occurred. |
| Connector returns a final failure with command ID | Report the connector/AutoCount error; keep Pending. |
| Timeout or lost response | Treat result as unknown; search AutoCount before retrying. |
| Command says saved but read-back differs | Report the exact discrepancy; keep Pending/exception; do not claim success. |
| Existing matching PI found | Stop duplicate creation and show the existing PI. |

Never blindly retry an accounting write. Reuse the stable Pending record and action identity for recovery. If the payload changes, show a fresh preview.

## Communication standard

Use the user's language. Prefer one short result paragraph plus only the decision-relevant facts. Do not expose `Case`, schema, validator, Gateway, payload digest, or connector internals to a normal business user unless they ask for technical detail.

Good discrepancy reply:

> AutoCount 找到 PO `PO-00128`，但有两项不一致：Item 00001 数量是 100 vs 90，单价是 RM12 vs RM12.50。请确认以 PO 还是供应商文件为准。

Good missing-batch reply:

> 还差 Item 00001 的 Batch No. 和 Expiry Date。补充这两项后我就能准备 PI。

## Reference routing

- Intake and uncertainty: `references/receiving-document-intake.md`
- PO search and comparison: `references/po-resolution-and-comparison.md`
- PO create/update and direct-PI branch: `references/po-creation-and-correction.md`
- CN decision and limited supplier follow-up: `references/supplier-discrepancy-and-cn-follow-up.md`
- Batch, dates, UDFs, and Short Expiry: `references/batch-expiry-and-short-expiry.md`
- Durable continuation: `references/receiving-case-continuation.md`
- Evidence retention: `references/document-archive.md`
- Configuration/escalation: `references/configuration-usage-and-escalation.md`
- Failures, duplicates, and uncertain results: `references/exceptions-and-recovery.md`
- Worked paths: `references/examples.md`

## Prohibited behavior

Never:

- rely on conversation memory instead of creating the Pending record;
- announce successful background matches the user did not need;
- ask the user for AutoCount codes before performing supported live matching;
- assume no PO merely because the document omits its number;
- force PO creation when direct PI is accepted;
- silently choose whether PO or supplier evidence is correct;
- classify every supplier error as CN;
- contact or repeatedly chase a supplier without user authorization and limits;
- negotiate with a supplier or accept a correction for the user;
- merge quantities from different batches into one PI line;
- omit required UDF dates or a Short Expiry warning;
- claim PI completion from `saved`/`done` without field-level read-back;
- recreate a PI while a previous result is uncertain;
- let durable record mechanics block an otherwise valid business workflow.
