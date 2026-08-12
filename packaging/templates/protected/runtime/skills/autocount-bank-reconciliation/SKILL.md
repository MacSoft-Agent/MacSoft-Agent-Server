---
name: autocount-bank-reconciliation
description: Reconcile an AutoCount bank/cash account from a Bank Statement, including reading an existing reconciliation, matching statement rows to AutoCount bank transactions, proposing tick changes, updating or creating the reconciliation after staff approval, and reading it back. Use for bank recon, bank reconciliation, statement matching, uncleared transactions, missing ticks, or unexplained bank balance differences. This is one of the Agent's two primary accounting workflows.
---

# AutoCount Bank Reconciliation

## Responsibility

Treat Bank Reconciliation as a primary workflow, alongside customer-payment Knock-Off. The Knock-Off workflow records the AR payment and creates the related bank transaction. This workflow later verifies that bank transaction against the company's Bank Statement and controls the reconciliation tick.

Do not create missing accounting transactions from a Bank Statement. Reconciliation verifies existing AutoCount bank transactions; it does not replace AR Payment, AP Payment, Cash Book, or Journal entry creation.

## Non-negotiable rules

- Preserve every identifier exactly as returned by AutoCount. `310-1000` is a string GL account number; never strip punctuation or convert it to `3101000`.
- Read the current live schema before every command.
- Keep `payload` as a JSON object; never send it as a quoted JSON string.
- For an existing account/date reconciliation, use `get-gl-bank-reconciliation` as the authoritative source for saved rows and current `Tick` values.
- Update an existing reconciliation. Create only when an authoritative read proves it does not exist.
- Select only live `BankTransKey` values returned for the same account.
- Never tick a row merely because amount and date are similar when credible competing rows exist.
- Never invent a missing AutoCount transaction from a Bank Statement.
- A match preview is not approval. Validation is not saving. Saving is not success until read-back proves the intended ticks.
- Only staff may approve or save reconciliation changes.
- Bank Recon is not a Payment/Receiving Case. After the staff user confirms the
  match result, save directly; do not request another approval.

## Conversation style

Work quietly. Do not narrate schemas, command names, payloads, identifiers, or internal retries unless the user asks technically.

For a statement containing many rows, report counts first:

- matched and proposed for ticking;
- needs review;
- statement-only;
- AutoCount-only.

Show individual rows only for exceptions or when requested. Ask one decision at a time.

## Workflow

### 1. Read the Bank Statement

Extract:

- bank and account identity;
- statement period and ending date;
- opening and ending balance when present;
- each transaction's date/value date, debit or credit amount, description, reference, payer/payee, and running balance;
- unreadable or uncertain fields.

If the attachment is unavailable or unreadable, stop and ask for a resend or clearer copy. Never claim to have matched an unavailable document.

### 2. Resolve the AutoCount bank account

1. Read `list-gl-bank-cash-accounts` with `{}`.
2. Match the statement's bank/account to one returned account.
3. Preserve the returned `AccNo` exactly.
4. If one account is clear, continue silently. If several are plausible, ask the user to choose. If none matches, stop and report that the bank account is not configured in AutoCount.

### 3. Determine the reconciliation date

Normally use the Bank Statement ending date. If the document covers multiple statement periods or the ending date is unclear, ask for the intended reconciliation date.

### 4. Read existing AutoCount reconciliation state

1. Call `get-gl-bank-reconciliation` with the exact `AccNo` and reconciliation date.
2. If found, retain every line, current `Tick`, `BankTransKey`, source identity, document number/date, amount, description, and saved actual balance. The final action is `update`.
3. If the Connector explicitly returns not found, read `list-gl-bank-reconciliation-uncleared` for candidate transactions. The final action is `create`.
4. Do not infer “not found” from a list summary that omits reconciliation rows.
5. Treat `startDate` as a requested filter, not proof that the Connector applied it. Locally filter returned rows to the relevant period while preserving earlier genuinely uncleared items that may appear on the current statement.

### 5. Match statement rows to AutoCount rows

Read [matching-and-exceptions.md](references/matching-and-exceptions.md) and classify each relevant row as:

- `matched`;
- `review_needed`;
- `statement_only`;
- `autocount_only`.

For an existing reconciliation, preserve currently ticked rows unless the statement comparison proves they should be unticked. The proposed selection is the complete replacement tick set, not only newly matched rows.

### 6. Present the matching result

Show:

- bank account and statement period;
- statement ending balance;
- current system reconciliation balance when returned;
- counts for the four classifications;
- proposed ticks added and removed;
- resulting difference;
- exception rows that need attention.

Ask whether to use the proposed match result. Do not save yet.

If no safe matches exist, do not create an empty reconciliation merely to record the statement balance. Report the exceptions and wait for correction or additional evidence.

### 7. Validate the complete replacement selection

Build the exact payload from live values:

```json
{
  "accNo": "310-1000",
  "reconDate": "2026-07-31",
  "actualBalance": 39006.29,
  "selectedBankTransKeys": [20682, 20683],
  "bankStatementNo": "optional statement reference",
  "description": "Bank reconciliation from reviewed statement"
}
```

Validate with `validate-gl-bank-reconciliation`. For an existing record, the same reviewed selection will be used for `update-gl-bank-reconciliation`; for a missing record, it will be used for `create-gl-bank-reconciliation`.

If validation fails, report the real business problem. Do not normalize identifiers, remove punctuation, retry guessed fields, or claim a Connector failure when the request never reached it.

### 8. Obtain final approval

Show the final replacement selection summary and ask the staff user to confirm the reconciliation save. Any change to account, date, balance, or selected keys requires a new preview and approval.

Do not call `workflow_approve_autocount_action` and do not create a Payment or
Receiving Case for Bank Recon. The staff user's confirmation here is sufficient.

### 9. Save

- Existing reconciliation: call `update-gl-bank-reconciliation`.
- Proven missing reconciliation: call `create-gl-bank-reconciliation`.

Use the exact approved account, date, actual balance, and complete selected key list. Do not turn statement-only rows into accounting entries.

### 10. Read back

Call `get-gl-bank-reconciliation` again using the exact account and date. Confirm:

- the record exists;
- actual statement balance equals the approved value;
- every approved selected key has `Tick = T`;
- every approved unselected key has `Tick = F`;
- the saved reconciliation difference/status is the expected result.

Only then report success. Otherwise report the exact mismatch and do not retry blindly.

## Connection to customer-payment Knock-Off

The two workflows have separate responsibilities:

1. Payment Slip intake creates a durable pending payment.
2. Bank evidence verifies the customer payment.
3. Staff approves invoice allocation and Knock-Off.
4. AutoCount AR Payment creates the bank transaction.
5. A later Bank Statement is reconciled against that transaction here.

Do not require the Payment Case to operate every Bank Recon row. Use durable payment records for cross-message payment continuation and duplicate protection; use live AutoCount reconciliation data as the authority for ticks.
