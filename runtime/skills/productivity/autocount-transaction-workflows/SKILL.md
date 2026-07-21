---
name: autocount-transaction-workflows
description: Reliable workflows for creating and validating AutoCount transactions through official AutoCount Cloud commands, with payload-shape pitfalls and verification steps.
---

# When to use

Use this skill for AutoCount transaction work such as creating invoices, validating document payloads, and troubleshooting when a write command saves the wrong lines or wrong totals.

# Core rules

1. Use only official AutoCount Cloud tools and commands.
2. If the exact command type is uncertain, search first.
3. Always fetch the live schema before execution, but do not assume the live schema examples are sufficient to predict the connector's accepted payload aliases.
4. For writes, prefer a read -> validate -> create -> read-back workflow.
5. Do not report success from the create response alone when the payload shape is at all uncertain; read the saved document back and inspect line count, item codes, qty, unit price, subtotal, and totals.

# Standard workflow for transaction creation

1. Confirm connector/company status if there is any doubt about connectivity.
2. Search for the exact command type if not already known.
3. Fetch the command schema.
4. Resolve business data using official read commands:
   - debtor/customer details
   - stock/item details
   - UOM and any item-specific defaults
5. Run the matching validate command before create whenever available.
6. If validation returns the intended lines and totals, execute the create command using the same working payload shape.
7. Immediately read the saved document back using the official get command.
8. If the created document does not match intent, correct the record state first (void/cancel/delete as officially supported), then retry with the corrected payload shape.

# Important payload-shape pitfall

For sales invoice work, the live schema may show section-style `Master` and `Details`, but the connector can still behave differently depending on alias shape.

Known reliable pattern from live use:
- top-level `debtorCode`
- line array under `lines` or `items`
- each line with `itemCode` and `qty`

Example working validation shape:
- `debtorCode: 111-1111`
- `lines: [{ itemCode: 00009, qty: 2 }, { itemCode: 00007, qty: 3 }]`

Observed failure mode:
- Using `details` or `Details` produced malformed results in this account book/connector path, including a single blank G/L line or collapsing requested stock lines.

# Sales invoice specific guidance

1. Get debtor detail first and confirm debtor code.
2. Get stock item detail for each requested item and note description and UOM.
3. Validate with a minimal payload first.
4. Inspect validation output carefully:
   - expected number of lines
   - expected item codes
   - expected quantities
   - unit prices actually derived by AutoCount
5. Only then create the invoice.
6. Read the saved invoice back and compare against the validated structure.

# Pricing pitfall

"Use the stock's normal unit price" does not guarantee a non-zero invoice price. If the item master/customer price path has no sale price configured, AutoCount may derive `UnitPrice = 0.00` and subtotal 0.00 even though the stock item exists and validates correctly.

When this happens:
1. Tell the user the invoice was created with zero price because AutoCount derived zero.
2. Offer to re-create or update using explicit unit prices if the user wants.
3. Check price-book/customer-price configuration if the user expects auto pricing.

# Recovery pattern for accidental writes

If exploratory create attempts save malformed documents:
1. Do not hide it.
2. Void/cancel the mistaken document using the official command.
3. Retry only after validation proves the payload shape is correct.
4. Tell the user which mistaken document numbers were cleaned up.

# Verification checklist

Before finishing, confirm:
- saved document number
- debtor code/name
- line count
- each item code and qty
- unit prices and totals as actually saved
- whether any exploratory documents were voided

# Support files

See `references/sales-invoice-payload-quirks.md` for a concrete session-derived payload map and failure signatures.
