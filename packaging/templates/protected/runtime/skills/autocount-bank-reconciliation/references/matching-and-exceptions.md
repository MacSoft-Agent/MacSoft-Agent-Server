# Bank Statement Matching and Exceptions

## Matching order

Compare normalized facts without changing source identifiers:

1. exact bank reference, cheque number, document reference, or transaction reference;
2. debit/credit direction and exact amount;
3. transaction/value date within the allowed banking delay;
4. payer/payee or description;
5. supporting document and known customer/supplier relationship.

An exact unique reference plus compatible direction and amount is normally a strong match. Amount and date alone are insufficient when competing rows exist.

## Classifications

### Matched

The Bank Statement row and one AutoCount row identify the same transaction with no credible competitor. Include its `BankTransKey` in the proposed complete tick set.

### Review needed

Evidence is plausible but ambiguous, such as equal amounts on the same date, shortened descriptions, unclear references, bank fees, combined deposits, split deposits, or date differences outside the normal delay. Do not change its tick until resolved.

### Statement only

The bank shows a transaction but no matching AutoCount bank transaction exists. Do not tick or create an accounting transaction. Report the statement row for separate investigation or bookkeeping.

### AutoCount only

AutoCount shows a relevant unticked transaction but the statement does not. Leave it unticked and report it as not found on the statement. It may be uncleared, dated incorrectly, recorded to the wrong bank, duplicated, or absent from the supplied statement period.

## Existing tick handling

- Preserve a current tick when the statement supports it.
- Propose unticking when the current tick is contradicted by the supplied authoritative statement, but show this prominently and require approval.
- Do not silently preserve all old ticks when preparing an update; the update selection replaces the saved selection.
- Do not silently remove a tick because extraction failed or a statement page is missing.

## Date handling

- Use value date when the statement distinguishes transaction date and value date.
- Allow normal posting delays only when other facts strongly identify the row.
- Include prior-period uncleared AutoCount rows when the current statement contains their eventual clearing entry.
- A Connector ignoring `startDate` is a filtering defect, not proof that all returned rows belong to the requested month. Filter locally and report abnormal volume technically when relevant.

## Amount handling

- Preserve debit/credit direction.
- Never match a receipt to a payment solely because absolute amounts agree.
- Do not hide bank charges, FX differences, combined deposits, partial receipts, or split settlements. Classify them for review unless supported business rules resolve them.

## Batch response

For a large statement, return a compact summary, for example:

> July statement matched: 42
> Needs review: 2
> Bank-only: 1
> AutoCount-only: 3
>
> I found two ambiguous RM1,000 receipts. Please confirm their references before I prepare the final tick update.

Do not dump every successful row into WhatsApp.

## Failures

- Account not found: stop; do not guess another GL account.
- Reconciliation read not found: use create path only after the exact account/date read says not found.
- Connector timeout after save: read back before any retry.
- Write license rejected: report the exact Connector/AutoCount error; retain the approved preview but do not claim ticks were saved.
- Read-back differs: report which keys or balance differ and stop.
