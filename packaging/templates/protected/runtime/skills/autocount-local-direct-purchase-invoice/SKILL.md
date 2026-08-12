---
name: autocount-local-direct-purchase-invoice
description: Execute and read back an accepted AutoCount Purchase Invoice after supplier, PO or direct-PI, discrepancy, batch, expiry, and staff-confirmation decisions are complete.
---

# Local Direct Purchase Invoice

## Responsibility

Perform the final PI write for Module 2. Use only after `autocount-receiving-supplier-invoice-automation` has resolved supplier facts, PO or direct-PI path, discrepancies, accepted quantities, Batch/date data, and the exact staff-confirmed preview.

Do not restart intake, repeat the full supplier document, or impose a PO when direct PI was accepted. If any material fact remains unresolved, return to the full Receiving Skill and keep the Pending Receiving Record open.

## Required inputs

Require the durable pending/action identity, registered evidence, live creditor and Item/UOM identities, accepted PO relationship or direct-PI basis, accepted lines/totals, complete batch-controlled line data, and confirmation of the exact PI preview.

For each batch-controlled line require one tuple:

```text
Item + UOM + quantity + BatchNo + ExpiryDate + CreatedDate
```

Different batches/dates require separate lines, and their quantities must reconcile with the accepted receiving quantity.

## Execution sequence

1. Re-read creditor, relevant PO/lines when applicable, Items, and Batch Control state.
2. Ensure every referenced Batch No already exists for its Item; establish and read back a missing Batch before PI creation.
3. Retrieve the current create/transfer PI contract and build the unchanged confirmed payload.
4. Put native Item/UOM/quantity/price/tax fields and `batchNo` on each PI line.
5. Put dates on each PI detail as:

   ```json
   "userDefinedFields": {
     "ExpiryDate": "YYYY-MM-DD",
     "CreatedDate": "YYYY-MM-DD"
   }
   ```

6. Execute `create-purchase-invoice` or the accepted PO-to-PI transfer exactly once.
7. Read back PI header and detail lines.
8. Verify creditor, references, PO relationship/direct basis, Items/UOMs, quantities, prices, tax, totals, Batch No, `UDF_ExpiryDate`/`Detail_UDF_ExpiryDate`, and `UDF_CreatedDate`/`Detail_UDF_CreatedDate`.
9. Mark the Pending Receiving Record Completed only after all material values match.
10. Report PI number, amount, batch count, and Short Expiry count concisely.

Normalize date/time read-back values to calendar dates before comparing. `saved=true` or a completed command is not proof that the dates or PI were stored correctly.

## Recovery

- If submission is rejected before a command is created, no AutoCount write occurred; report the actual boundary error.
- If the connector returns a final failure with a command ID, keep Pending and report the returned error.
- If response is lost or times out, search live AutoCount using creditor, supplier invoice, PO/reference, amount, and stable action facts before retrying.
- If PI exists but read-back differs, report exact differences and keep exception state; do not claim success.
- If a Batch was newly established but PI failed, reuse it only after verifying it belongs to this Item and no conflicting references/state exist. Do not create a duplicate Batch.
- Any material payload correction requires a fresh preview and confirmation.

## Never

- execute with unresolved supplier/PO discrepancy;
- force PO creation when direct PI was accepted;
- merge different batches or dates into one line;
- omit required `ExpiryDate` or `CreatedDate` UDFs;
- substitute PI creation timestamp for the supplied batch `CreatedDate`;
- create duplicate PI or Batch during recovery;
- claim completion without field-level read-back.
