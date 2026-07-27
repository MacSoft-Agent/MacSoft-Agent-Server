# Architecture decision records

This directory is for durable decisions that a future developer could
otherwise reverse without understanding the product consequence.

Create a decision record for:

- persistent or customer-data ownership and migration;
- public API, protocol, or cross-team contracts;
- authentication, authorization, secrets, or other security boundaries;
- installer, update, rollback, and release architecture;
- long-lived Hermes integration and upstream maintenance strategy;
- AutoCount write authorization or other durable business-control boundaries;
- a major component ownership decision or deliberate irreversible trade-off.

Do not create a record for a normal bug fix, routine refactor, temporary
investigation, test correction, or implementation detail that creates no
durable contract. Work Package evidence and the commit are sufficient for those
changes.

## Naming and lifecycle

Use `NNNN-short-title.md`, starting at `0001`. A record should be one of
`Proposed`, `Accepted`, `Superseded`, or `Rejected`. Do not rewrite an accepted
decision to hide history; add a superseding record and link both.

The Product Owner accepts decisions involving customer-visible policy, public
contracts, persistent data, security, installer/update/rollback policy, product
versioning, Hermes baseline, or release risk. Technical reviewers may accept
internal design decisions when those boundaries are unchanged.

## Minimal record

```markdown
# NNNN - Decision title

- Status:
- Date:
- Owners/reviewers:
- Related Work Package:

## Context

## Decision

## Consequences

## Alternatives considered

## Verification or follow-up
```

Architecture documents explain the system; decision records explain why a
specific durable choice was made. Do not duplicate a full architecture
description here.
