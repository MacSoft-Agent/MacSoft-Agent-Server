# Server Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each persistent MacSoft Server database a stable public identity and precise device-credential rejection errors.

**Architecture:** SQLite owns a one-row `server_identity` record. App creation caches that ID in application state for `/health`; protected Client routes reuse one standard rejection envelope.

**Tech Stack:** Python 3.12, SQLite, FastAPI, unittest.

## Global Constraints

- Preserve existing pairing-code error semantics.
- Do not derive Server identity from URL, hostname, network, or credentials.
- Do not modify the separately owned Client repository.

---

### Task 1: Persist and expose Server identity

**Files:**
- Modify: `server/macsoft/db.py`
- Modify: `server/macsoft/server.py`
- Modify: `server/macsoft/gateway/routes_health.py`
- Test: `server/tests/test_server_identity.py`

**Interfaces:**
- Produces: `get_server_id(config: AppConfig) -> str`
- Produces: `app.state.server_id: str`

- [ ] Write tests for generation, reopen stability, copied-database stability, and `/health.server_id`.
- [ ] Run focused tests and observe missing identity behavior.
- [ ] Add the one-row table and UUID provisioning under SQLite transaction control.
- [ ] Cache the value during `create_app()` and add it to `/health`.
- [ ] Re-run focused tests.

### Task 2: Standardize rejected device credentials

**Files:**
- Modify: `server/macsoft/identity/devices.py`
- Modify: protected route modules under `server/macsoft/gateway/`
- Test: `server/tests/test_pairing_security.py`
- Test: existing protected-route contract tests

**Interfaces:**
- Produces: `DEVICE_CREDENTIALS_REJECTED_CODE`
- Produces: `device_credentials_rejected_error()` envelope helper

- [ ] Write tests for unknown-token and mismatched-device-ID 401 envelopes.
- [ ] Run focused tests and observe current `invalid_device_token` behavior.
- [ ] Replace protected-route error construction with the standard envelope;
  preserve `invalid_pairing_code`.
- [ ] Re-run focused and Server regression tests.

### Task 3: Verify and record results

**Files:**
- Modify: `docs/work-packages/WP-013-server-identity-device-credentials.md`

- [ ] Run `scripts/verify-development.ps1`.
- [ ] Inspect `git diff --check` and preserve unrelated worktree changes.
- [ ] Record commands and results in the Work Package.
