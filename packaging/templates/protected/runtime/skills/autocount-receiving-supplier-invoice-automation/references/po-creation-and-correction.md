# PO Creation and Correction

## Resolve before declaring absence

Keep the supplier's displayed PO number unchanged. A formatted document number and an AutoCount internal numeric key are different identifiers unless a live result maps them. If direct lookup cannot accept the displayed value, execute a supported list/search operation and exact-match its returned document-number field; only then use the returned internal key. Reading a schema does not query business data. An incompatible interface means unresolved, not missing.

## No PO

Tell the user no suitable live PO was found and ask whether AI should prepare one. If the user declines, preserve the Case for manual PO creation or later information.

If accepted:

1. resolve creditor, Item, UOM, quantities, price, tax, dates, location, and required live schema fields;
2. do not invent a new Item merely because document text is close to no existing Item;
3. resolve internal codes from live AutoCount reads; never use a human category such as `Stock` as `itemType` unless live AutoCount returned `Stock` as the exact code;
4. omit an unresolved optional field, but stop and report a missing required code rather than guessing it;
5. validate the exact PO payload;
6. preview header, every line, totals, source evidence, and assumptions;
7. obtain fresh user approval tied to the exact preview;
8. when required by the active Tool contract, use its exposed approval capability (currently `workflow_approve_autocount_action` when available) and pass the returned Case version, action ID, action digest, scope, and other required values unchanged as execution `workflow_context`;
9. create the PO once; do not execute if required workflow context is absent or the payload differs from the approved payload;
10. read back PO number, status, lines, and totals.

After successful read-back, the newly created PO joins the normal receiving path: Batch No/Expiry/Short Expiry review, PI preview, approval, PI creation, and PI read-back.

## Existing PO correction

First ask whether the PO is truly outdated/wrong or the supplier document/delivery differs legitimately. If correction is chosen:

1. re-read current PO and lines;
2. show exact before/after values and downstream impact;
3. preserve fields not being changed;
4. validate supported update schema;
5. obtain fresh approval;
6. execute once and read back;
7. re-run supplier-document comparison.

If the corrected PO now agrees with the accepted supplier document, return to the same normal receiving path. A PO correction is not an endpoint and does not automatically create a CN.

If PO update is unsupported or PO state prevents safe editing, state the exact manual operation. Do not recreate a second PO to simulate an edit without explicit approval.

User-provided corrected PO information is input, not automatic write authority. Validate it against live Item/UOM/schema facts and preview it.
