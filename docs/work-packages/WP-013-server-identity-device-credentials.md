# WP-013 - Server identity and device credential contract

## Status

Implementing

## Owner

- Product Owner: User (approved 2026-08-08)
- Execution owner: Codex

## Objective

Give each persisted MacSoft Server database a stable public UUID and distinguish
credentials rejected by the current Server from an expiring token.

## Evidence and current behavior

- Device authentication requires `Authorization: Bearer <device_token>` plus
  `X-Device-Id`; it has no token-expiry field.
- The Client maps every HTTP 401 to `token_expired`, although a changed URL can
  reach a different Server database.
- `/health` exposes host and port but no stable Server identity.

## Scope

- Persist and expose a database-owned Server UUID.
- Standardize protected Client authentication failures as
  `device_credentials_rejected`.
- Add persistence and contract regression tests.

## Non-scope

- Changes to the separately owned Client credential store.
- Credential migration across distinct Server databases.
- Pairing-code error behavior.

## Architectural boundaries

- The UUID is public identity metadata, not a secret or Client authority.
- The database remains the owner of durable Server identity.
- URL, network, hostname, and port are transport configuration only.

## Acceptance criteria

1. `/health` returns a valid stable UUID as `server_id`.
2. Restart, network/URL changes, and a restored database retain the ID.
3. Protected Client routes return the agreed 401 envelope for rejected device
   credentials.
4. Pairing failures retain `invalid_pairing_code`.

## Verification plan

- Focused identity and pairing-security tests.
- Full `scripts/verify-development.ps1` before completion.

## Implementation result

- Added the database-owned single-row `server_identity` UUID record. It is
  provisioned during database initialization and cached on the FastAPI app.
- Added `server_id` to the existing `/health` response without removing its
  existing fields.
- Normalized every Server-protected Client device-authentication response to
  `device_credentials_rejected`; pairing code errors remain unchanged.
- Documented the Client credential namespace contract without modifying the
  separately owned Client implementation.

## Verification evidence

- Added and ran `server/tests/test_server_identity.py`: UUID generation,
  restart/reopen stability, copied-database restore stability, and health
  exposure (3 passed).
- Added rejected-token and mismatched-device-ID assertions to
  `server/tests/test_pairing_security.py` (8 passed).
- Ran `python -m unittest discover -s server/tests` using the repository
  virtual environment (145 passed).
- Ran `scripts/verify-development.ps1` on 2026-08-08 (passed): Server 145,
  Desktop UI 1222, Electron 392, script tests 9, and TypeScript checks.
