# PO Creation and Correction

## No PO

Tell the user no suitable live PO was found and ask whether AI should prepare one. If the user declines, preserve the Case for manual PO creation or later information.

If accepted:

1. resolve creditor, Item, UOM, quantities, price, tax, dates, location, and required live schema fields;
2. do not invent a new Item merely because document text is close to no existing Item;
3. resolve internal codes from live AutoCount reads; never use a human category such as `Stock` as `itemType` unless live AutoCount returned `Stock` as the exact code;
4. omit an unresolved optional field, but stop and report a missing required code rather than guessing it;
5. validate the exact PO payload;
6. preview header, every line, totals, source evidence, and assumptions;
7. obtain fresh approval tied to Case version/digest/action ID;
8. create the PO once;
9. read back PO number, status, lines, and totals.

## Existing PO correction

First ask whether the PO is truly outdated/wrong or the supplier document/delivery differs legitimately. If correction is chosen:

1. re-read current PO and lines;
2. show exact before/after values and downstream impact;
3. preserve fields not being changed;
4. validate supported update schema;
5. obtain fresh approval;
6. execute once and read back;
7. re-run supplier-document comparison.

If PO update is unsupported or PO state prevents safe editing, state the exact manual operation. Do not recreate a second PO to simulate an edit without explicit approval.

User-provided corrected PO information is input, not automatic write authority. Validate it against live Item/UOM/schema facts and preview it.
