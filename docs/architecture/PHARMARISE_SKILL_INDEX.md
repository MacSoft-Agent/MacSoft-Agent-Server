# PharmaRise Skill Index

This index describes the responsibility and routing boundaries of the MacSoft
Skills that participate in PharmaRise workflows. It is a maintainer map, not a
second copy of the business instructions. The referenced `SKILL.md` and
`references/` files remain authoritative for Agent behavior.

## Business workflow Skills

| Skill | Use it for | Hands off to / reads | Must not do |
|---|---|---|---|
| `pharmarise-company-configuration` | Resolve company, account book, contacts, storage and WhatsApp purpose | Its four customer-owned configuration references | Act as a second identity or permission system |
| `autocount-payment-knockoff-automation` | Module 1: Payment Slip intake, pending continuation, later bank matching, debtor/invoice resolution, allocation and approval | Payment references; final action goes to `autocount-local-direct-payment-knockoff` | Treat a Payment Slip as cleared funds or begin invoice work before bank evidence |
| `autocount-local-direct-payment-knockoff` | Execute and read back one already verified and approved AR payment/Knock-Off | Generic `autocount-operations` command boundary | Handle raw Payment Slips or incomplete Cases |
| `autocount-bank-reconciliation` | Reconcile a GL bank/cash account to a statement using AutoCount bank-reconciliation commands | Generic `autocount-operations` command boundary | Replace Module 1 Payment Slip-to-bank verification |
| `autocount-receiving-supplier-invoice-automation` | Module 2: supplier/receiving intake, PO branches, discrepancies, CN, Batch/Expiry and PI approval | Receiving references; final action goes to `autocount-local-direct-purchase-invoice` | Treat OCR as accepted facts or silently resolve discrepancies |
| `autocount-local-direct-purchase-invoice` | Execute and read back one accepted and approved Purchase Invoice | Generic `autocount-operations` command boundary | Bypass Receiving Case, PO/discrepancy decisions or connector limitations |
| `autocount-operations` | Official AutoCount command discovery, schema, validation, execution and read-back | Live AutoCount catalog and connector | Replace the owning Module 1/2 business workflow with generic command choices |

## Presentation Skills

| Skill | Responsibility | Boundary |
|---|---|---|
| `macsoft-chart-visualization` | Produce an explicit prompt-requested chart for the Client | Does not own accounting workflow decisions |
| `macsoft-chart-dashboard` | Produce MacSoft dashboard HTML/output | Does not own payment or receiving state |
| `data-storytelling` | Explain data clearly | Does not establish accounting truth |
| `kpi-dashboard-design` | Guide KPI dashboard composition | Does not trigger financial writes |
| `web-design-engineer` | Guide general web presentation | Does not own PharmaRise business logic |

## Module 1 reference map

| Reference | Purpose |
|---|---|
| `payment-intake-and-pending.md` | Recognize a Payment Slip, create/reuse a pending Case, and tell the user to send bank-side evidence later |
| `payment-case-continuation.md` | Resume the same Case across sessions, people, devices or days |
| `bank-verification.md` | Agent judgement for strong, fuzzy, ambiguous, conflicting or unmatched bank evidence |
| `invoice-matching-and-fifo.md` | Explicit invoice handling, Invoice-Date FIFO, partial payments and unapplied balance |
| `whatsapp-payment-workflow.md` | Trusted WhatsApp identity, fragmented messages and group behavior |
| `configuration-usage-and-escalation.md` | Company/account-book reuse, notifications and escalation |
| `exceptions-and-recovery.md` | Duplicate evidence, stale approvals and uncertain-write recovery |
| `examples.md` | Positive and negative business scenarios |
| `official-autocount-ai-sources.md` | Exact official discovery sources and authority order |

## Routing invariant

Payment Slip intake and bank-side verification are two different stages of one
Module 1 Case. A Payment Slip is recorded as pending immediately. Only a later
acceptable Bank Transaction or Statement match allows debtor lookup, live
invoice reads, explicit-invoice/FIFO allocation and Knock-Off approval.

When behavior is wrong, update the owning business Skill or its focused
reference first. Extend Tools or persistence only when a demonstrated workflow
step cannot be performed through the existing boundary.
