# Server Identity and Device Credential Design

## Decision

MacSoft Server has one durable `server_id`: a UUID stored in its SQLite
database. It is generated only when a database has no identity record. The ID
therefore survives URL, IP, port, network, process, upgrade, backup, and
restore changes. A new or deliberately rebuilt database represents a new
Server identity.

## Contract

`GET /health` retains its existing public fields and adds:

```json
{"ok": true, "server_id": "uuid"}
```

Every protected Client endpoint returns this standard 401 response if a token
is missing, unknown, revoked, bound to another device ID, or owned by an
inactive user:

```json
{
  "ok": false,
  "error": {
    "code": "device_credentials_rejected",
    "message": "This device credential is not accepted by this Server.",
    "details": {}
  }
}
```

Pairing-code failures remain `invalid_pairing_code` and are not device
credential failures.

## Boundaries

- Server owns identity persistence and protected-endpoint error semantics.
- The separate Client will later index device credentials by `server_id`; this
  change does not alter its storage format.
- The server ID is public metadata, not a credential. It is not derived from a
  URL, hostname, IP address, token, or model configuration.

## Verification

Tests prove one-time generation, reopen stability, database-copy stability,
health exposure, and matching rejected-device error envelopes for unknown
tokens and mismatched device IDs.
