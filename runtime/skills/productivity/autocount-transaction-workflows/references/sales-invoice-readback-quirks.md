# Sales invoice read-back quirks

Session-derived notes for AutoCount sales invoice verification.

## Scenario

Created a sales invoice for debtor `111-1111` using the reliable payload shape:
- top-level `debtorCode`
- top-level `docDate`
- line array under `lines`
- each line with `itemCode` and `qty`

Validation and create both succeeded.

## Observed behavior

Create result returned:
- `saved: true`
- `docNo: I-000027`
- `docKey: 287`
- `detailCount: 2`
- both lines saved with requested item codes and qty 3

Attempted read-back with official command `get-sales-invoice` and payload:
- `docNo: "I-000027"`

The command was rejected before submission with:
- `AutoCountPayloadValidationError`
- validation path `$.docNo`
- expected `number`
- actual `string`

This contradicts the live schema/example, which describes `docNo` as a sales invoice document number and shows a string example.

## Reliable fallback

When `get-sales-invoice` has this schema/runtime mismatch:
1. Keep the create result as the primary evidence for saved line structure and totals.
2. Verify existence using `list-sales-invoices` with a small latest-first limit.
3. Match the returned `DocNo` and `DocKey` against the create result.
4. Tell the user plainly that full read-back was blocked by a connector/schema mismatch.

## Pricing note from the same session

Validation and create derived `UnitPrice = 0` for both lines, so:
- `netTotal = 0`
- `finalTotal = 0`

This is a pricing-configuration outcome, not a save failure.
