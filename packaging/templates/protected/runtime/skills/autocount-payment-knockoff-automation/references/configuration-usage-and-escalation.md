# Configuration Usage and Escalation

Read stable company facts from `pharmarise-company-configuration`; do not duplicate values here.

Resolve company first, then account-book alias to canonical account book. If several account books fit or the mapping is missing, ask the user before any accounting operation. A one-time explicit destination may override a default only when the actor is authorized and the destination is valid.

Use an explicitly requested authorized notification recipient when supplied. Otherwise use the configured notification/escalation recipient. The default admin is not automatically the approver.

Escalate when debtor/account book cannot be resolved, bank evidence remains genuinely ambiguous, accounting treatment for overpayment/fees/FX is unknown, AutoCount cannot verify the intended action, or an authorized approver is unavailable. State the Case reference and exact unresolved decision without exposing secrets.
