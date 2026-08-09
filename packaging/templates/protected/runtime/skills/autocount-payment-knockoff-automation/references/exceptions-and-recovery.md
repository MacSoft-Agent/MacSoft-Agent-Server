# Payment Exceptions and Recovery

## Intake/read failures

- Unreadable evidence: preserve it, list unreadable critical fields, request a clearer source or typed confirmation.
- Unknown/multiple debtors: show distinguishing live candidates; do not guess.
- Bank unavailable: keep pending and record the failed source/time; do not reinterpret the slip as bank proof.
- AutoCount unavailable: preserve Case and intended next read; do not validate/execute from cache.

## Business ambiguity

- Duplicate slip: link or hold after comparing stable evidence identity; never create a second payment write.
- Same-amount bank candidates: ask for reference/payer/date evidence.
- Invalid explicit invoice: report why; obtain a new instruction rather than silently using FIFO.
- Overpayment, bank fees, or FX difference: request accounting treatment.
- Changed outstanding balance: regenerate allocation and approval.

## Approval and concurrency

- Case version/digest mismatch: approval is stale; re-read and re-preview.
- Another employee updated the Case: reload after optimistic conflict and preserve both actors' evidence.
- Rejected/cancelled approval: keep the Case pending/cancelled as instructed; do not execute.

## Write uncertainty

Persist stable `action_id` and execution-started event before the AutoCount call. On timeout/disconnect:

1. do not retry;
2. inspect meaningful Case events for a completed result;
3. query AutoCount using supported document/reference/action facts;
4. compare live outstanding balances;
5. if success is proven, record/read back and complete;
6. if failure is proven, return to approved execution only when the same action remains valid;
7. if still uncertain, escalate for manual verification.

Never generate a new action ID merely to bypass uncertainty.

## Completed Case correction

Do not edit accounting history by changing Case JSON. Explain the verified posted result and use the approved AutoCount correction/reversal process as a separate consequential action when supported.
