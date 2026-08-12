# Payment Case Continuation

The PostgreSQL Case, not the chat transcript, is the shared continuation authority.

The source channel is provenance, not ownership. A payment record created from WhatsApp may be continued from Client, another authorized WhatsApp conversation, another session/device, or another staff member. Never require the user to return to the original chat when the durable record and current evidence can be resolved in the same company/account-book scope.

## Finding the Case

Search within the trusted company/account book using evidence ID/source event, payment reference, amount/currency, payer/debtor hint, date range, and current status. Prefer exact stable evidence identity. Never search across tenants merely to find a match.

When one candidate is clearly supported, load its current version and summarize what is complete, pending, and required next. When several candidates remain, present distinguishing facts and ask the user rather than merging.

## Continuing safely

- Link later bank evidence, corrections, or invoice instructions to the current Case version.
- Trust each later attachment from its own current transport message. Do not require the later attachment to share the original message ID, chat ID, trusted-media list, or temporary path.
- Preserve prior facts and their provenance; update the working conclusion rather than rewriting history.
- Use optimistic version checks so two employees cannot silently overwrite each other.
- On version conflict, reload, explain the newer change, and reapply only still-valid work.
- After restart/session/device change, re-read the Case and live AutoCount state.

When Bank Transaction/Statement evidence arrives in Client after a WhatsApp Payment Slip:

1. resolve the current Client actor and configured company/account book;
2. register the current bank attachment from the current message;
3. search `waiting_bank` records in that scope;
4. match business facts and attach the bank evidence to one supported record;
5. continue bank judgement, invoice allocation, preview, approval, execution, and read-back.

If no record is found, say that no matching pending payment was found in the current company/account book. If several are found, show distinguishing facts. If the current file registration fails, report that failure. Never replace these diagnoses with a generic claim that the previous trusted conversation cannot be continued.

## Terminal and duplicate Cases

Do not reopen a completed/cancelled Case for the same evidence without an explicit correction procedure. If duplicate Cases are discovered, do not merge or delete automatically; identify the authoritative Case and mark/escalate the duplicate according to supported workspace behavior.

Any material continuation change invalidates an approval tied to the older Case version.
