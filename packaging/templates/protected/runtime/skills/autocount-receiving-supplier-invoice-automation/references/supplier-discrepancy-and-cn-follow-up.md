# Supplier Discrepancy and CN Follow-Up

When PO and supplier document differ, first show the exact difference and its quantity or financial effect. Ask whether the agreed terms/PO changed, the delivery is partial, or the supplier document is wrong. Do not assign blame from one source alone and do not classify every discrepancy as a CN.

## Decide whether CN is relevant

- If the PO contains old or incorrect accepted facts, use the PO correction preview/approval path.
- If the supplier document is wrong and the supplier overcharged or owes a credit, a CN may be required.
- If the supplier undercharged, omitted a charge, supplied a corrected invoice, or made a non-financial error, do not call it a CN automatically. Explain the difference and hold the Case until the user selects the accepted accounting treatment.
- If a partial delivery is intentional, preserve the remaining PO state and continue only for the accepted received quantity.

## Supplier follow-up

If the user decides supplier correction is needed, ask whether they will contact the supplier or want the Agent to prepare the follow-up. When the Agent is authorized to contact the supplier, prepare but do not send:

- resolved trusted recipient/contact;
- company/Case/PO/invoice reference;
- concise discrepancy facts;
- requested correction or CN;
- exact message text and purpose.

Show all of these and obtain approval. Supplier-contact mapping is not approval authority. Send using the same approved text; material edits require new approval. Persist sent result and waiting state.

Follow up only through the approved contact path and keep the Case waiting until an authoritative correction or CN arrives.

## CN/corrected document arrives

Resolve it to the Case using trusted source, supplier, invoice/PO, references, amount/lines, and evidence identity. When ambiguous, ask instead of attaching it to the first waiting Case.

Register and extract the document, show its material correction to the user, and ask whether this exact version is accepted. A forwarded CN is not automatically accepted.

## Separate decisions

1. User accepts/rejects the supplier document version.
2. If accepted and the user wants an AutoCount CN created or updated, show an exact CN action preview.
3. Retrieve the live command/schema and execute only after a second fresh approval.

If no verified CN status command/mapping exists, record the accepted CN and clearly mark AutoCount CN status as manual/connector-blocked. Never reinterpret it as a Purchase Return without approved business mapping.

Once the accepted correction resolves the material discrepancy, recompare the effective supplier facts with the PO and return to the normal Batch/Expiry/Short Expiry and PI path.

If the supplier never responds or sends another incorrect version, keep the Case pending and notify/escalate according to configuration.
