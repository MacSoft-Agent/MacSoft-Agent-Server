# MacSoft Agent documentation

This is the navigation entry point for developers, reviewers, and Codex. Current
code, schemas, tests, lock files, and `product.json` remain the primary
authorities.

## Current coordination

- [`../AGENTS.md`](../AGENTS.md) - repository-wide working rules and authority
  order
- [`PROJECT_STATUS.md`](PROJECT_STATUS.md) - accepted baseline, current program
  state, evidence, and next owner decision
- [`release/RELEASE_READINESS.md`](release/RELEASE_READINESS.md) - current
  release risks, sequencing, and acceptance needs
- [`work-packages/_TEMPLATE.md`](work-packages/_TEMPLATE.md) - reusable medium
  and high-value task record
- [`decisions/README.md`](decisions/README.md) - when and how to record durable
  architecture decisions

## Architecture and product foundation

`architecture/` explains the product and component boundaries. It provides
deeper design context, not live version or status authority.

- `MACSOFT_AGENT_PRODUCT_FOUNDATION.md`
- `MACSOFT_PRODUCTION_RUNTIME_FOUNDATION.md`
- `MACSOFT_AGENT_BUSINESS_CONTROL.md`
- `MacSoft-Agent-项目知识地图.md`
- `MacSoft_Agent_Current_System_Architecture_and_Handover_Report.*`

Some documents contain point-in-time paths, builds, staging names, or test
counts. Validate those values against `product.json`, code, tests, and
`PROJECT_STATUS.md`.

## Operations

`operations/` contains runtime startup, verification, and troubleshooting
guidance.

- `HERMES_RUNTIME_OPERATIONS.md`
- `HERMES_RUNTIME_VERIFICATION.md`

## Release and packaging

- `release/RELEASE_READINESS.md` - current evidence and missing acceptance
- `development/DEVELOPMENT_AND_RELEASE_WORKTREES.md` - development/release
  separation; validate historical literal paths before use
- `development/MACSOFT_PREPACKAGING_HARDENING.md` - packaging hardening context
- `development/MACSOFT_UPSTREAM_MAINTENANCE.md` - pinned Hermes maintenance and
  compatibility workflow

Release scripts and installer source remain authoritative over prose.

## Work Packages

`work-packages/` contains reviewable records for active or completed medium and
high-value tasks. Small low-risk tasks may use a lighter report. The template is
not a general backlog.

## Decisions

`decisions/` is for durable architecture decisions that future developers
should not unknowingly reverse. It is not for ordinary bug-fix notes.

## Contracts

`contracts/` contains versioned cross-component behavior contracts.

- `MACSOFT_CLIENT_ACTIVITY_PROTOCOL_V1.md`

## Handoffs

`handoffs/` contains scoped instructions for work owned by the external Thin
Client team. These documents are not Server implementation code.

- `CLIENT_OCR_ATTACHMENT_HANDOFF.md`
- `CLIENT_SESSION_CONCURRENCY_FIX_HANDOFF.md`

## Historical reports

`reports/` contains historical implementation and remediation reports. They
provide context only and do not override current code, tests, contracts, or
status.

## Reference material

`reference/` contains generated or point-in-time inventories such as Hermes API
routes and runtime inventories. Regenerate them for a new Hermes baseline; do
not treat them as permanent API contracts.
