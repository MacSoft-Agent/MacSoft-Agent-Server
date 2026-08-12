# PO Creation, Correction, and Direct PI

## Prove the PO state

Search AutoCount for a matching PO even if the supplier document has no PO number. Use exact PO reference when present plus creditor, Item lines, remaining quantity, prices/amount, dates, and open/transfer state.

Preserve displayed identifiers. If a command needs an internal key, obtain it from a live result; never derive it from a formatted PO number. An incompatible lookup means unresolved, not absent.

## Authoritatively no PO

Offer both valid paths:

1. create a PO first;
2. proceed directly to PI.

If the user chooses direct PI, record that decision and continue to Batch/Expiry checks. Do not force PO creation or leave the workflow stuck merely because no PO exists.

If PO creation is chosen:

1. resolve live creditor, Item, UOM, quantities, prices, tax, dates, and required codes;
2. prepare and validate the exact PO payload;
3. show a concise header/line/total preview;
4. obtain confirmation;
5. create once and read back;
6. compare the created PO against accepted supplier facts;
7. continue to Batch/Expiry and PI rather than treating PO creation as completion.

## Existing PO correction

If staff decides the PO is wrong/outdated:

1. re-read current PO and lines;
2. show exact before/after values and impact;
3. preserve unchanged fields;
4. validate, confirm, update once, and read back;
5. compare again and continue to PI when aligned.

If PO edit is unsupported or its state prevents editing, state the exact manual action. Do not create a duplicate PO to imitate an edit without explicit instruction.

## Partial receiving

When staff confirms partial receiving is intentional, use only accepted lines/quantities for the current PI and preserve the remaining PO quantity. Do not mark the whole PO received unless live business facts support it.
