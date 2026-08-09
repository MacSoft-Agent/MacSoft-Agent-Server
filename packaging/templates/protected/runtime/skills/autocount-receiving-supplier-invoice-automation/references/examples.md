# Receiving Workflow Examples

## 1. Perfect PO match

Supplier invoice matches live creditor, PO, Item/UOM, quantity, price, tax, and total. Verify Item batch control and extracted batch/expiry. Preview PI, highlight connector-blocked manual batch/expiry entry, approve, create/transfer, and read back.

## 2. No PO

No live candidate exists. Ask whether AI should create one. If yes, resolve all Item/UOM/schema facts, show exact PO preview, approve, create and read back, then continue PI. If no, keep Case pending/manual.

## 3. Partial delivery

PO quantity is 10 and supplier document quantity is 6. Do not label it wrong automatically. Ask whether 6 is intended partial delivery, then prepare PI for the accepted received quantity while preserving remaining PO state.

## 4. PO outdated price

PO price is 10; supplier invoice is 11. User confirms newly agreed price 11. Show PO before/after, approve update, read back, recompare, then prepare PI.

## 5. Supplier document wrong and CN required

Same 10 versus 11 difference, but user confirms supplier invoice is wrong. Draft exact message to trusted supplier contact requesting CN/correction, show recipient/reason/text, approve and send. Keep Case waiting. Register later CN and ask whether that exact version is accepted.

## 6. CN accepted but status unsupported

User accepts CN. The live connector has no verified CN-status operation. Record acceptance, mark AutoCount status manual/connector-blocked, and do not invent a command or Purchase Return.

## 7. Multiple batches

Item A: batch B1 qty 4 expiry 2027-10-01; B2 qty 2 expiry 2026-10-01. Keep pairs. Compute Short Expiry for each against receiving date and show separate warnings/manual entries.

## 8. Ambiguous handwritten expiry

Evidence could read 03/04/2027 or 04/03/2027 and the distinction affects Short Expiry. Ask for confirmation; do not normalize silently.

## 9. Duplicate invoice after timeout

PI creation response is lost. Query by creditor/supplier invoice/reference/action facts and read live PI before retry. If it exists and matches, record success; never create a second PI.

## 10. Another employee continues

Employee A uploads invoice and sends supplier query. Employee B receives CN tomorrow. Resolve the same Case from trusted evidence/supplier/PO, show current state, and continue without requiring old chat context.

## 11. Known Case lookup appears empty

The prompt names Case `2bd...` but a lookup returns no Case. Do not create another receiving Case. Recheck `case_type=receiving`, the original canonical company/account-book IDs, and evidence/source identity. Continue the recovered Case or stop with a scope mismatch. A display label such as `PharmaRise / PR-M2` is not a valid substitute for stored identifiers.

## 12. Item category label is not an ItemType code

The supplier document describes a product as “Stock,” while `read-item-types` returns no `Stock` code. Do not submit `itemType="Stock"`. Inspect the live `create-item` schema: omit `itemType` if optional, or stop for AutoCount configuration/manual resolution if required. Never discover validity by performing a consequential write.
