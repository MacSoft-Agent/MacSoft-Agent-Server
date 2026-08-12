---
name: autocount-local-direct-payment-knockoff
description: Execute and verify the final AutoCount Receive Payment/Knock-Off only after an existing PharmaRise Payment Case already has verified bank evidence, a resolved debtor, live invoice allocation, stable action identity, and fresh approval. Never use for a newly uploaded Payment Slip or incomplete payment request.
---

# Local Direct Payment Knock-Off

## Responsibility

Perform the final accounting action only after upstream payment verification and allocation are complete. It never bypasses the Case, live-read, approval, audit, or recovery controls.

A raw Payment Slip, a slip marked successful, a slip naming an invoice, or a user saying only "record this payment" must not trigger this Skill. Route all such intake to `autocount-payment-knockoff-automation` and wait for bank-side evidence.

Do not repeat fuzzy bank investigation here. If bank evidence, debtor, account book, or allocation is incomplete, route to `autocount-payment-knockoff-automation`.

## Required inputs

Require one company/account book, authenticated authorized actor, current Payment Case and version, registered evidence, verified bank conclusion, resolved debtor, live selected invoices, payment date/method/reference, exact allocation, stable action ID, action digest, and fresh approval. Resolve authorization according to the current transport: authenticated Client session permissions for Client, and WhatsApp sender mapping for WhatsApp. Never require a Client actor to have a WhatsApp identifier.

## Execution sequence

1. Load the current Case and verify its version/digest equal the approval event.
2. Re-read live debtor and every selected outstanding document.
3. Confirm document identity, currency, eligibility, and outstanding balances still support the exact allocation.
4. If anything changed, stop, update the Case, and return to a new preview/approval.
5. Retrieve the current `create-ar-payment` schema and validate the exact payload where supported.
6. Construct `knockOffs` only from freshly read `docType`, `docKey`, `docNo`, and approved amount. Never invent internal keys.
7. Persist execution-started with the same stable action ID.
8. Execute once.
9. Read back the payment using the supported receipt/payment read operation and refresh outstanding documents.
10. Verify debtor, total, reference, allocation, and resulting balances against the approved draft.
11. Preserve the current Case `working_data`, merge the real document/reference and verification facts into it, update using the current Case version, then re-read the Case before reporting completion. Payment DocNo/DocKey, action ID, allocation and read-back belong inside `values.working_data`; do not invent unsupported top-level Case fields.

## Recovery

On timeout or disconnect, never retry immediately. Search Case events and live AutoCount by the stable action/reference and compare invoice balances. Record success only when read-back proves it. If the outcome remains uncertain, escalate for manual verification.

If execution returns `workflow_approval_required`, `workflow_context_invalid`, or `workflow_approval_stale_or_invalid`, the final action is not ready. Do not retry or switch command paths. Return to `autocount-payment-knockoff-automation` for a current preview and approval. A local Workflow error is not evidence of an AutoCount license failure; only report licensing when AutoCount explicitly rejects the submitted command for that reason.

Keep the customer reply natural and short. Say what is ready, what still needs confirmation, or what was saved and verified. Do not expose workflow-context fields, action digests, Tool names, or Case mechanics unless the user explicitly asks for technical detail.

## Never

- execute for an actor denied by the authorization system of the current transport;
- treat an authenticated Client actor as an unmapped WhatsApp sender or show the WhatsApp external-sender Admin reply in Client;
- use approval from another Case version/digest;
- replace an invalid explicit invoice with FIFO silently;
- modify allocation under the old approval;
- claim success from validation or an intermediate response;
- create a second payment to recover from an unknown first result.
