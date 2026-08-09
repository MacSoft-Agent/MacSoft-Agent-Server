# Batch, Expiry, and Short Expiry

## Preserve relationships

For each Item, retain batch number, expiry date, and quantity as a paired structure. Multiple batches require separate quantities. Never attach one expiry to every batch merely because the document layout is ambiguous.

Treat handwritten characters and ambiguous date order carefully. Preserve original text and normalized candidate. Ask when DD/MM/YYYY versus MM/DD/YYYY or similar ambiguity affects the one-year rule.

## Batch-controlled Item

Read live Item detail. If an existing Item is not controlled by batch number, preserve required current fields and preview changing `hasBatchNo` to `true`; execute only with appropriate approval and read it back. New Items must be created through the live schema with `hasBatchNo=true` after Item identity/details are confirmed.

Do not create duplicate Items to avoid updating an existing Item.

## Short Expiry

Use the applicable receiving/reference date and calendar arithmetic. Remaining expiry strictly less than one year is Short Expiry. Exactly one year is not “less than one year.” Show Item, batch, expiry, remaining period, and warning.

## Current connector boundary

Official AutoCount recipes/manifest/OpenAPI plus live schema discovery confirm:

- the current official AutoCount files expose `batchNo` on Purchase Invoice lines, but the active native PI schema in the tested deployment rejects it; this is a connector/catalog capability mismatch and means direct PI Batch is not currently verified on that deployment;
- `create/update-goods-received-note` line examples expose `batchNo` and provide a verified Batch-bearing path;
- `create/update-stock-receive` native fields expose `BatchNo`;
- these document families expose header and line `userDefinedFields` objects;
- UDF keys use the real AutoCount UDF field name without the database `UDF_` prefix;
- no verified `expiryDate` field or separate Expiry command has been found;
- the deployed PI detail Short Expiry field has been read back as `UDF_SHORTEXPIRY` with `F` in the proven non-short-expiry case.

Therefore:

- write Batch No through GRN/Stock Receive only when that document path matches the accepted business flow; do not force it into the current direct PI schema;
- retain the Item/batch/quantity relationship and read the saved document lines back;
- preserve Expiry in the Receiving Case and preview until its exact destination field is verified;
- use the configured Short Expiry UDF through detail `userDefinedFields`, then require live read-back of `UDF_SHORTEXPIRY`; never infer success from command completion alone;
- identify exact remaining manual AutoCount entry/check work;
- do not label Expiry or Short Expiry writes complete without read-back.
