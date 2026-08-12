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

Require an authenticated authorized actor and the stable `action_id` returned by the exact-payload approval. Company/account book, Case identity, command, payload and digest are persisted with that action and must not be reconstructed from conversation memory. Resolve authorization according to the current transport: authenticated Client session permissions for Client, and WhatsApp sender mapping for WhatsApp. Never require a Client actor to have a WhatsApp identifier.

## Execution sequence

1. Before approval, re-read the debtor and selected outstanding documents, construct `knockOffs` only from authoritative `docType`, `docKey`, `docNo`, and amounts, then validate the exact payload.
2. Call `workflow_approve_autocount_action` once with that exact payload and business preview. Keep the returned stable `action_id`.
3. After approval, call `workflow_execute_approved_autocount_action` with only that `action_id`. Do not reload this Skill, search command catalogs, fetch schemas, check Connector status, reconstruct payloads, or build `workflow_context`.
4. The deterministic executor owns execution-started and uncertain-recovery behavior and submits the exact persisted payload at most once.
5. Read back the payment using the supported receipt/payment read operation and refresh outstanding documents.
6. Verify debtor, total, reference, allocation, and resulting balances against the approved draft.
7. Preserve the current Case `working_data`, merge the real document/reference and verification facts into it, update using the current Case version, then re-read the Case before reporting completion. Payment DocNo/DocKey, action ID, allocation and read-back belong inside `values.working_data`; do not invent unsupported top-level Case fields.

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
