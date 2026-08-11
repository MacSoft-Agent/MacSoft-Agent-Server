---
name: pharmarise-company-configuration
description: Resolve PharmaRise companies, account books, contacts, escalation routes, storage paths, and WhatsApp channel purposes before running payment or receiving workflows.
---

# PharmaRise Company Configuration

Load only the references needed for the current request:

- Company contacts and escalation: `references/contacts-and-escalation.md`
- AutoCount account books: `references/account-books.md`
- Managed evidence and archive paths: `references/paths-and-storage.md`
- WhatsApp channel purposes: `references/whatsapp-channels.md`

Treat these references as customer-owned configuration values, not product logic.

## Rules

1. Resolve exactly one `company_id` and `account_book_id` before creating or updating a Case.
2. Resolve WhatsApp identifiers through the authoritative workspace mapping. When no explicit chat mapping exists and Company Configuration contains exactly one complete company/account-book scope, inherit that scope silently. Never infer a company from a display name or choose among multiple scopes.
3. Keep Connector IDs separate from account-book IDs.
4. Do not expose credentials, tokens, database connection strings, or private customer data in replies.
5. If configuration is missing or ambiguous, stop the consequential workflow and report an administrator configuration problem without asking a WhatsApp customer for internal IDs, database setup, channel mapping, or Case handling.
6. Never silently fall back to another company or account book. Single-scope inheritance is permitted only when exactly one complete configured scope exists.
