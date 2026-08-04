# WP-007 - Server Desktop AutoCount i18n

## Status

Complete

## Owner

- Product Owner: approved in Codex task on 2026-07-31
- Execution owner: Codex
- Reviewer: pending

## Objective

Make the complete Server & AutoCount settings surface follow the Server
Desktop display language.

## Scope

- Move fixed Server & AutoCount UI copy into the existing Desktop i18n catalog.
- Supply English, Simplified Chinese, Traditional Chinese, and Japanese copy.
- Cover service controls, network and pairing fields, AI Service and AutoCount
  settings, client-side notifications, loading, retry, and save states.
- Preserve raw backend diagnostics, returned test results, and service errors.

## Non-scope

- Changing service lifecycle, AutoCount rules, ports, persistence, or APIs.
- Translating arbitrary backend-generated diagnostic content.
- Changing Thin Client files.

## Acceptance criteria

1. Fixed UI copy follows the selected Desktop language.
2. Service, network, pairing, test, and save behavior remains unchanged.
3. Unknown backend diagnostics remain available verbatim.
4. Desktop typecheck, focused i18n/settings tests, lint, and diff checks pass.

## Verification evidence

- Desktop TypeScript typecheck: passed.
- Focused i18n and Server & AutoCount UI tests: 27/27 passed.
- Focused lint and final diff checks: passed.

## Remaining risk

- Backend-returned test titles, summaries, field labels, warnings, and raw
  service errors may remain in the backend's source language.
- Real installed-product visual acceptance remains for the Product Owner.
