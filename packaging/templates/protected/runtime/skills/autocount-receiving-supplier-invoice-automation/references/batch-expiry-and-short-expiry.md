# Batch, UDF Dates, and Short Expiry

## Preserve the line relationship

Treat each tuple as one indivisible PI detail:

```text
Item + BatchNo + batch quantity + CreatedDate + ExpiryDate
```

Split different batches or dates into separate PI lines. Never copy one date across several batches because the source layout is unclear. For every accepted Item quantity, require the sum of batch quantities to equal that quantity.

Preserve original date text and normalized `YYYY-MM-DD`. Ask when DD/MM/YYYY versus MM/DD/YYYY changes the meaning.

## Batch-controlled Item

Read live Item detail. If batch tracking is required and an existing Item has `hasBatchNo=false`, preview the change, obtain confirmation, update while preserving current fields, and read back. Do not create a duplicate Item.

Before PI creation, confirm every referenced Batch No exists for that Item. A PI may reference an existing Batch, but a missing Batch must be established first and read back. If Batch creation succeeds and PI later fails, do not create the Batch again. Inspect whether the first Batch has references or balance before any cleanup/retry.

## PI Detail UDF contract

For each PI line, send:

```json
{
  "batchNo": "BATCH-001",
  "userDefinedFields": {
    "ExpiryDate": "2027-07-31",
    "CreatedDate": "2026-08-01"
  }
}
```

Use UDF keys without the database `UDF_` prefix. `CreatedDate` means the batch creation/manufacturing date supplied by the document or staff under the current deployment convention; do not substitute the PI creation timestamp.

After saving, verify Batch No and both dates from PI detail read-back. Accept either connector read-back naming form:

- `UDF_ExpiryDate` or `Detail_UDF_ExpiryDate`;
- `UDF_CreatedDate` or `Detail_UDF_CreatedDate`.

Normalize returned date/time values to dates for comparison. A command-level `saved=true` without matching field read-back is not success.

## Short Expiry

Use the accepted receiving/PI reference date and calendar arithmetic:

```text
ExpiryDate < reference date + 1 calendar year
```

This is Short Expiry. Exactly one year is not less than one year. Show affected Item, Batch, quantity, and Expiry Date before PI confirmation. Treat it as a warning unless business policy explicitly requires rejection.

## Exceptions

- Missing Batch/date: keep Pending and ask only for missing values.
- Batch quantity mismatch: state exact shortage/excess; do not create PI.
- Item not batch-controlled: confirm and enable it before Batch use.
- Batch absent: establish/read back Batch before PI.
- UDF missing from live deployment: stop before PI and report the missing configuration; do not silently omit Expiry.
- Saved PI has wrong/missing UDF value: keep exception state and report the exact read-back difference.
