# Payment Workflow Examples

## 0. Payment Slip arrives before bank evidence

Read payer, beneficiary, amount, date, reference, claimed invoice, claimed status, and any sample/test marking. Automatically create or continue the Pending Bank Verification Case, archive the trusted evidence, verify persistence, then show the captured facts and explain that the company's bank receipt is not verified. Tell the user to send a Bank Transaction or Bank Statement when available.

Do not search AutoCount, resolve the debtor, inspect the invoice, prepare an AR receipt, or ask for Knock-Off approval yet. Preserve the payment during the same turn and give a short confirmation without exposing internal tables or commands.

## 1. Normal explicit invoice and partial payment

Slip and cleared bank row both show MYR 200, unique reference, and compatible payer/date. User says “pay I-1001.” Live I-1001 outstanding is MYR 500. Classify strong match, preview MYR 200 to I-1001 and expected remaining MYR 300, approve, post, and read back.

## 2. FIFO without invoice instruction

Cleared payment is MYR 700. Live invoices are I-3 (oldest, 300), I-4 (400), I-5 (newest, 250). Preview 300 to I-3 and 400 to I-4. Do not touch I-5. Show Invoice Dates, not only numbers.

## 3. Fuzzy payer name

Slip says “ABC Trading Sdn Bhd”; bank row says “ABC TRDG” with exact amount/reference and next-business-day posting. If no competing row and debtor relationship is credible, classify reasonable fuzzy match and explain the abbreviation/date difference.

## 4. Ambiguous equal amounts

Two cleared MYR 1,000 rows exist on the same day and the slip has no reference. Do not choose the first. Ask for payer account/reference or clearer proof; keep pending.

## 5. Overpayment

Payment is 1,200; eligible outstanding totals 1,000. Preview invoices totaling 1,000 and an unapplied 200. Ask for approved treatment. Never inflate an invoice allocation.

## 6. Duplicate forwarded slip

Two employees forward the same evidence hash/message object. Continue the same Case and tell the second employee it is already tracked. Do not post twice.

## 7. Bank evidence arrives tomorrow

Automatically preserve today's slip as Pending Bank Verification and show the captured facts. Tomorrow another accountant submits a statement. Show the relevant bank row, locate the recorded payment using evidence/reference/amount and other facts, explain the match conclusion, then continue using live invoices. If the slip's invoice instruction is valid, use it; otherwise apply Invoice-Date FIFO. Show the allocation before requesting Knock-Off approval.

## 8. User correction invalidates approval

Preview was approved for I-1001, then user corrects it to I-1002. Update Case, re-read I-1002, regenerate digest and preview, and obtain new approval. Never reuse the old approval.

## 9. Timeout after posting request

The connector times out. Search by stable action/reference and compare live outstanding. If I-1001 already decreased by the approved amount and payment read-back identifies the document, record success. Otherwise remain uncertain; do not blindly retry.

## 10. Invalid explicit invoice

User names an invoice belonging to another debtor/account book. Reject the allocation and ask for correction. Do not reveal unrelated customer detail beyond what the actor may see, and do not fall back to FIFO without permission.

## 11. Customer or invoice does not match the Payment Slip

Payment Slip shows ABC Tradex Sdn. Bhd., invoice INV-PR2505-0148, and MYR 18,850. AutoCount finds ABC Trading Sdn. Bhd. with only invoice I-2608-047 for MYR 1,200. Do not narrate the lookup sequence, discuss payload validity, quote internal policy, or explain Case state.

Prefer a compact business reply such as:

> The ABC record I found in AutoCount does not match this Payment Slip:
> - AutoCount: ABC Trading Sdn. Bhd. — invoice I-2608-047, MYR 1,200
> - Payment Slip: ABC Tradex Sdn. Bhd. — invoice INV-PR2505-0148, MYR 18,850
>
> I cannot safely Knock-Off the payment until the correct customer and invoice are confirmed.
>
> Please confirm either:
> 1. ABC Tradex Sdn. Bhd.'s correct AutoCount Debtor Code; or
> 2. the actual AutoCount invoice number for INV-PR2505-0148.

If the user is technical or specifically requests the internal identifier, add `DocKey` after the actual AutoCount invoice number. Otherwise omit it.
