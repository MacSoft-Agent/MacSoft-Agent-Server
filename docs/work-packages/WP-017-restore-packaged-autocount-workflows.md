# WP-017 - Restore Packaged AutoCount Workflows

## Status

Complete

## Owner

- Product Owner: MacSoft Product Owner
- Execution owner: Codex

## Baseline

- Repository/branch: `C:\MacSoft\server\MacSoft-Agent`, `improve/skill`
- Starting remote commit: `721ffc89326f2c8eb3cdb3b2b5cae03ecc4891bf`
- Product: MacSoft Agent 0.1.7

## Objective

Restore the approved PharmaRise payment-knockoff and supplier-receiving workflow
capabilities to the protected Windows package and repair PR verification without
undoing the clean-package allowlist design.

## Owner decision

The Product Owner explicitly reversed WP-016's exclusion of these workflows and
requested that the workflow tools be restored. Bank reconciliation remains out
of scope.

## Scope

- Restore the workflow plugin modules, migration, registrations, and policy.
- Package payment, receiving, their direct-action Skills, and company configuration.
- Keep an explicit allowlist and preserve all unrelated clean-package changes.
- Increment only the protected-resource schema version required for upgrade sync.

## Risks and controls

- AutoCount writes remain protected by versioned Case approval and action digests.
- Existing administrator-modified protected files remain governed by initializer
  conflict handling.
- Focused workflow, packaging, staging, initializer, and server validator tests
  must pass before push.

## Acceptance criteria

1. The staged plugin includes and registers all six workflow tools.
2. The workflow migration and five approved top-level workflow Skills are staged.
3. Bank reconciliation remains excluded.
4. Product and protected manifest resource versions match.
5. Focused tests, regression tests, cleanliness, and diff checks pass.

## Verification evidence

- Focused workflow/packaging/server-validator suites: 63 tests passed.
- Complete `product_runtime/tests` suite: 87 tests passed.
- Complete `server/tests` suite: 151 tests passed.
- `scripts/check-repository-cleanliness.ps1`: passed (pending changes reviewed).
- `git diff --check`: passed.

## Implementation result

- Protected resource version increased from 5 to 6.
- The six workflow modules/migration resources and six tool registrations are
  restored to the protected package.
- Payment, receiving, both direct-action Skills, and PharmaRise company
  configuration are explicitly allowlisted; bank reconciliation stays excluded.
- The clean staging allowlist and protected-resource reconciliation model remain
  in place.
