# Bank Verification

## Principle

The Agent makes the professional match judgement. Tools may extract rows, normalize text/dates/amounts, and present deterministic comparison facts. They must not decide that two records are the same payment.

## Compare these facts

- exact currency and amount;
- transaction/reference number, including clearly explained bank prefixes or formatting differences;
- payer/account-holder name versus debtor and Payment Slip name;
- booking date, transfer date, value date, weekends, and bank processing delay;
- recipient account/company/account book;
- transaction description, invoice number, phone, or customer code;
- bank state: cleared/posted versus pending/reversed/rejected;
- duplicate same-amount transactions near the same date.

Normalize spacing, punctuation, case, common company suffixes, and obvious bank formatting only for comparison. Keep original values in the explanation.

## Classifications

### Strong match

Use when amount/currency agree, a unique strong identifier agrees, the date is plausible, the recipient is correct, and no conflicting candidate exists.

### Reasonable fuzzy match

Use when strong facts agree but a non-critical difference has a credible explanation—for example a normalized company suffix, bank posting one business day later, or payer name belonging to a known director. Explain both supporting and differing facts. Do not hide the inference.

### Ambiguous

Use when two or more bank rows could fit, a unique reference is absent, payer identity cannot be connected safely, or an important field has multiple readings. Ask the smallest discriminating question or request better evidence.

### Conflicting

Use when amount/currency/recipient/reference materially conflicts, the transaction is reversed, or the evidence cannot describe the same transfer. Do not proceed.

### Unmatched

Use when no suitable cleared bank row is found. Keep the Case pending and report the search scope/date range rather than claiming non-payment forever.

## Special cases

- One transfer paying several invoices: one Payment Case may allocate across invoices after the bank transfer is verified.
- One transfer covering several debtor accounts: require explicit accounting direction; do not split based on names alone.
- Third-party payer: require a credible link or user confirmation to the debtor and record the explanation.
- Amount differs due to bank fee/FX: do not auto-adjust; ask for the accounting treatment.
- Screenshot says “successful” but no bank statement row: still claimed evidence unless policy explicitly accepts that source as bank authority.
- Same reference appears twice: investigate reversal/repost or duplication before proceeding.

## Explanation format

State: classification, matched slip/case, matched bank row, agreeing facts, differences, why differences are or are not acceptable, and the next action. Keep the explanation concise enough for an accountant to verify.

Any correction to material match facts changes the Case version and invalidates prior allocation approval.
