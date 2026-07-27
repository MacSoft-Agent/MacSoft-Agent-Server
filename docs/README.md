# MacSoft Agent documentation

Documents are grouped by their job so a developer can find the authoritative
material without searching through historical artifacts.

## Architecture

`architecture/` explains what the product is and how its major components fit
together.

- `MACSOFT_AGENT_PRODUCT_FOUNDATION.md` — product and component foundation
- `MACSOFT_PRODUCTION_RUNTIME_FOUNDATION.md` — production runtime design
- `MACSOFT_AGENT_BUSINESS_CONTROL.md` — business-control boundaries
- `MacSoft-Agent-项目知识地图.md` — Chinese project knowledge map
- `MacSoft_Agent_Current_System_Architecture_and_Handover_Report.*` — handover report

## Development

`development/` contains contributor and release-maintenance guidance.

- `DEVELOPMENT_AND_RELEASE_WORKTREES.md`
- `MACSOFT_PREPACKAGING_HARDENING.md`
- `MACSOFT_UPSTREAM_MAINTENANCE.md`

## Operations

`operations/` contains runtime startup, verification, and troubleshooting
guidance.

- `HERMES_RUNTIME_OPERATIONS.md`
- `HERMES_RUNTIME_VERIFICATION.md`

## Contracts

`contracts/` contains versioned cross-component behavior contracts.

- `MACSOFT_CLIENT_ACTIVITY_PROTOCOL_V1.md`

## Handoffs

`handoffs/` contains scoped instructions for work owned by the external Client
team. These documents are not Server implementation code.

- `CLIENT_OCR_ATTACHMENT_HANDOFF.md`
- `CLIENT_SESSION_CONCURRENCY_FIX_HANDOFF.md`

## Reports

`reports/` contains historical implementation and remediation reports. They
provide context but are not the source of truth when they disagree with code or
tests.

## Reference

`reference/` contains generated or point-in-time inventories such as Hermes API
route listings and runtime inventories. Regenerate them when validating a new
Hermes baseline; do not treat them as permanent API contracts.
