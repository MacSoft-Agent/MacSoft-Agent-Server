# Receiving Case Continuation

The PostgreSQL Case is the shared continuation authority across employees, sessions, devices, restarts, and WhatsApp messages.

Locate within trusted company/account book using evidence/source identity, supplier invoice/DO/CN, PO, supplier, date, and status. Exact evidence identity wins. If several Cases fit, show distinguishing facts and ask; never merge automatically.

## Exact known-Case continuation

When an earlier response, Case event, evidence record, or user supplies a Case ID, continue it using all four exact workspace coordinates:

- `case_type=receiving`;
- the original UUID `case_id`;
- the canonical `company_id` stored on that Case;
- the canonical `account_book_id` stored on that Case.

Display names and shorthand are not workspace identifiers. Do not replace `pharmarise-local-test` with `PharmaRise`, replace an account-book ID with a supplier or document label, or infer a different scope from the current prompt.

If exact `get` returns no Case:

1. verify the four arguments against the trusted company configuration and the earlier Case/evidence result;
2. search the same exact company/account book using the evidence ID, source event key, supplier invoice number, or supplier DO number;
3. if a matching Case exists, continue it;
4. if scope cannot be proven, stop and explain the mismatch.

Do **not** create a replacement Case merely because one lookup returned `null`. New Case creation is allowed only for genuinely new source evidence after duplicate checks. A different session, employee, or direct test run does not make an existing business Case new.

Store coarse current status plus detailed `working_data`: registered evidence, extraction uncertainty, resolved creditor/PO, comparisons, user decisions, supplier-message/CN state, batch/expiry facts, proposed actions, and verified results.

Use optimistic version updates. On conflict, reload the current Case and explain newer changes. A material change to supplier, PO, lines, discrepancy resolution, batch/expiry, or PI payload invalidates old approval.

Later CN/corrected documents should advance the existing Case. Completed/cancelled Cases must not be silently reopened or reused for a new supplier invoice.
