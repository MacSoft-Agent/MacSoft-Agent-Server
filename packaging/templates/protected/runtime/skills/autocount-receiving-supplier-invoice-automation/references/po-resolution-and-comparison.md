# PO Resolution and Comparison

## Resolve live candidates

Use the resolved creditor and live AutoCount PO reads. Prefer an exact valid PO number. Otherwise compare supplier, account book, date window, supplier reference, open/received state, Item/UOM identities, quantities, and totals. Similar text is candidate evidence, not authority.

If multiple POs could fit, show differentiating PO number/date/status/lines and ask. Do not merge several POs without explicit business instruction.

## Compare line by line

For each supplier-document line identify its live PO counterpart and compare:

- Item code/description and UOM;
- ordered, previously received/invoiced, remaining, and document quantity;
- unit price, discount, tax code/rate, line total;
- missing supplier lines and missing PO lines;
- supplier invoice/DO reference;
- batch/expiry evidence where provided.

Distinguish partial delivery from an error. A PO for 10 and document for 6 may be legitimate partial receipt. Distinguish price rounding/tax presentation from a real commercial difference, but explain the calculation.

## Neutral discrepancy report

Use a compact table: field/line, PO value, supplier value, difference, impact, and required decision. Say “needs resolution,” not “supplier wrong,” until the user decides or authoritative evidence proves it.

Re-read the PO before any correction or PI preview. If PO state changed while pending, refresh comparison and invalidate affected approval.
