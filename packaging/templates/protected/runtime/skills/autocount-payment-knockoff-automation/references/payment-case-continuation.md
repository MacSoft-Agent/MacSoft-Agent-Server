# Payment Case Continuation

The PostgreSQL Case, not the chat transcript, is the shared continuation authority.

## Finding the Case

Search within the trusted company/account book using evidence ID/source event, payment reference, amount/currency, payer/debtor hint, date range, and current status. Prefer exact stable evidence identity. Never search across tenants merely to find a match.

When one candidate is clearly supported, load its current version and summarize what is complete, pending, and required next. When several candidates remain, present distinguishing facts and ask the user rather than merging.

## Continuing safely

- Link later bank evidence, corrections, or invoice instructions to the current Case version.
- Preserve prior facts and their provenance; update the working conclusion rather than rewriting history.
- Use optimistic version checks so two employees cannot silently overwrite each other.
- On version conflict, reload, explain the newer change, and reapply only still-valid work.
- After restart/session/device change, re-read the Case and live AutoCount state.

## Terminal and duplicate Cases

Do not reopen a completed/cancelled Case for the same evidence without an explicit correction procedure. If duplicate Cases are discovered, do not merge or delete automatically; identify the authoritative Case and mark/escalate the duplicate according to supported workspace behavior.

Any material continuation change invalidates an approval tied to the older Case version.
