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
2. Resolve WhatsApp identifiers through the authoritative workspace mapping; never infer a company from a display name.
3. Keep Connector IDs separate from account-book IDs.
4. Do not expose credentials, tokens, database connection strings, or private customer data in replies.
5. If configuration is missing or ambiguous, stop the consequential workflow and ask for the missing value.
6. Never silently fall back to another company or account book.
