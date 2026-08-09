# Invoice Matching, FIFO, and Partial Allocation

## Always start from live outstanding documents

Resolve the debtor first. Read all relevant current outstanding documents and retain live `docType`, `docKey`, `docNo`, Invoice Date, currency, original total, paid/knocked-off amount, and outstanding balance. Do not use cached balances for execution.

## Explicit invoice instruction

An explicit current instruction takes priority over FIFO only when:

- the invoice belongs to the resolved debtor and account book;
- the exact document exists in the live result;
- it remains outstanding;
- currency and intended amount are compatible;
- the instruction is not contradicted by a later correction.

If the named invoice is missing, fully settled, belongs elsewhere, or is ambiguous, say so and ask. Do not silently fall back to FIFO.

## Invoice-Date FIFO

When there is no valid explicit instruction:

1. include eligible live outstanding invoices only;
2. order by Invoice Date ascending;
3. use a stable tie-breaker such as authoritative document identity only when dates are equal;
4. allocate `min(remaining payment, current outstanding)`;
5. continue until payment is exhausted or no eligible invoice remains.

Document number order, insertion order, and cached chat order are not Invoice-Date FIFO.

## Allocation cases

- Underpayment: partially settle the selected/oldest invoice; show remaining invoice balance.
- Exact payment: settle the selected invoices exactly.
- Multiple invoices: list every allocation separately.
- Overpayment: allocate only eligible balances; show unapplied remainder and ask for approved treatment.
- Credit notes/negative documents: do not include unless the live command and business instruction explicitly support the treatment.
- Foreign currency: do not mix currencies or invent exchange-rate treatment.

## Preview table

For each line show invoice number/date, live outstanding before, proposed allocation, expected outstanding after, and selection reason (`explicit instruction` or `Invoice-Date FIFO`). Also show payment total, total allocated, and unapplied remainder.

## Staleness

Immediately before posting, re-read the selected documents. If a balance, identity, currency, or eligibility changed, recalculate, update the Case, and request a new approval. Never reduce/increase lines silently under an old approval.
