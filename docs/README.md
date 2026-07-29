# MacSoft Agent documentation

New contributors should begin with the root
[`CONTRIBUTING.md`](../CONTRIBUTING.md), then use this map for deeper product
context.

For a new clone or replacement development machine, follow
[`development/FRESH_CLONE_SETUP.md`](development/FRESH_CLONE_SETUP.md) before
debugging source or configuration.

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
- [`release/PRODUCTION_RELEASE_CONTROL.md`](release/PRODUCTION_RELEASE_CONTROL.md) -
  production distribution, trust-gate, and non-secret evidence controls
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
- `release/PRODUCTION_RELEASE_CONTROL.md` - approved release-location, signing,
  trust-provisioning, and publication controls; never a secret store
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

- `work-packages/WP-003-hermes-compatibility.md` - current Hermes compatibility
  investigation, evidence, risks, and gated implementation scope
- `work-packages/WP-004-built-in-update.md` - trusted installer update scope,
  verification evidence, and remaining installed-product gates
- `work-packages/WP-005-production-release-policy-and-trust.md` - approved
  production release policy, trust decisions, roles, sequencing, and gates

## Decisions

`decisions/` is for durable architecture decisions that future developers
should not unknowingly reverse. It is not for ordinary bug-fix notes.

- `decisions/0001-production-release-and-update-trust.md` - source/release
  separation, stable update trust, immutable publication, and recovery policy

## Contracts

`contracts/` contains versioned cross-component behavior contracts.

- `MACSOFT_CLIENT_ACTIVITY_PROTOCOL_V1.md`
- `MACSOFT_HERMES_COMPATIBILITY_CONTRACT.md` - code-derived Host, Desktop,
  Server, and Hermes runtime boundaries
- `MACSOFT_UPDATE_CONTRACT.md` - signed release, download, installer,
  persistence, rollback, and acceptance boundary

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

- `MACSOFT_HERMES_PATCH_INVENTORY.md` - point-in-time comparison with the
  pinned upstream Hermes commit for upgrade reconciliation
