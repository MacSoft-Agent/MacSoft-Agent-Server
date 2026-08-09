---
name: autocount-local-direct-purchase-invoice
description: Execute and verify an approved AutoCount Purchase Invoice from a fully accepted PharmaRise Receiving Case or complete authenticated local request.
---

# Local Direct Purchase Invoice

## Responsibility

Perform the final PI action after supplier evidence, PO/no-PO decisions, discrepancies, and batch/expiry treatment are accepted. This shorter route may be used for a complete authenticated local request, but it never bypasses the Receiving Case, evidence archive, live reads, exact preview, approval, or read-back.

If supplier/PO facts remain ambiguous, supplier correction/CN is pending, or the user has not accepted discrepancies, route to `autocount-receiving-supplier-invoice-automation`.

## Required inputs

Require company/account book, authorized actor, current Receiving Case/version, registered source evidence, resolved creditor, accepted PO or direct-PI basis, live Item/UOM identities, accepted quantities/prices/tax/totals, documented batch/expiry/manual limitations, stable action ID/digest, and fresh approval.

## Execution sequence

1. Load the current Case and verify approval matches version/digest/action ID.
2. Re-read creditor, relevant PO/lines, and Item batch-control state.
3. Retrieve the current PI or PO-transfer command schema.
4. Confirm live state still matches the accepted draft; otherwise return for a new preview and approval.
5. Validate the exact payload where supported.
6. Persist execution-started and execute the supported `create-purchase-invoice` or `transfer-purchase-order-to-purchase-invoice` once.
7. Read back PI header and lines.
8. Verify creditor, supplier invoice/DO, PO relationship, Items/UOM, quantities, prices, tax, and totals.
9. Persist the real PI number/key and verification result, then report completion.

## Batch, expiry, and UDF behavior

The current direct PI human example and native validator conflict: the example shows `batchNo`, but the active native PI schema rejects it. Do not force Batch No into direct PI; keep it as a named manual/connector-blocked follow-up, or return to the full Receiving Skill when a verified GRN/Stock Receive path is appropriate. Do not write `expiryDate` because no verified field is currently exposed. The deployed PI detail Short Expiry UDF has been read back as `UDF_SHORTEXPIRY`; write it only through the schema's detail `userDefinedFields` convention and verify the saved `T`/`F` value. Preserve unresolved Expiry values in the Case and display exact manual entry/check requirements rather than inventing fields.

## Recovery

After timeout/disconnect, inspect Case events and live PI state using creditor, supplier invoice, PO, reference, and stable action facts. Never create another PI until duplicate execution has been ruled out. A connector status of `done` is not proof of PI creation; require a live read-back that finds exactly one matching PI. If no document exists, revise only the proven invalid/unsupported fields and obtain a new approval for the new payload before retrying.

## Never

- execute with unresolved supplier/PO discrepancy;
- let CN receipt imply acceptance or PI authority;
- invent Item/UOM/batch/expiry/UDF fields;
- reuse stale approval;
- change PI lines under an old digest;
- claim success without read-back;
- create a duplicate PI as timeout recovery.
