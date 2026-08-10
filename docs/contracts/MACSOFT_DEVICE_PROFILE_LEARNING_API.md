# Device-profile learning API

## Purpose

This contract defines the MacSoft Server learning surface for one paired
device. It is implemented by Server port `8787`; Hermes port `8642` is an
internal Host-owned dependency and is never a Client endpoint.

## Authority and isolation

Every request uses the existing device credentials:

- `Authorization: Bearer <device_token>`
- `X-Device-Id: <device_id>`

Server derives `device_id -> profile_id -> profile home` after authentication.

## Server identity and rejected credentials

`GET /health` returns a durable public `server_id` UUID. It identifies the
persisted Server database and is stable across URL, IP, port, network, process,
upgrade, backup, and restore changes. A new database represents a new Server.

Clients must treat `server_id` as the credential-storage namespace; the Server
URL is transport configuration only. A protected request whose credentials are
unknown, revoked, inactive, or bound to a different `X-Device-Id` returns:

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

This response does not mean a time-based token expiry. Pairing code failures
remain `invalid_pairing_code`.
`profile_id`, `HERMES_HOME`, filesystem paths, credentials, and raw Hermes
state are never Client authority inputs or response fields. A device profile
is one-to-one, persistent across Server/Hermes restart, and frozen when its
device is revoked.

## Endpoints

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/profile` | Safe device-profile display summary. |
| GET | `/api/profile/memory` | Safe Memory summary, timestamp, and card count. |
| GET | `/api/profile/skills` | Progress Skill metadata plus read-only Private Skill metadata. |
| GET | `/api/profile/learning` | Run-linked learning events and safe Journey graph. |
| GET | `/api/profile/curator` | Curator state counts and device-scoped proposals. |
| POST | `/api/profile/curator/dry-run` | Official Hermes Curator preview; no Progress Skill change. |
| POST | `/api/profile/curator/proposals/{id}/approve` | Atomically claim and apply one pending proposal. |
| POST | `/api/profile/curator/proposals/{id}/reject` | Reject one pending proposal. |
| POST | `/api/profile/skills/{id}/pin` | Pin/unpin an agent-created Progress Skill. |
| POST | `/api/profile/skills/{id}/restore` | Restore an agent-created archived Progress Skill. |
| GET | `/api/profile/curator/backups` | List recoverable snapshots without paths. |
| POST | `/api/profile/curator/backups/{id}/rollback` | Restore one snapshot; request body must be `{ "confirm": true }`. |
| POST | `/api/chat/stream` | Existing Client SSE contract, internally routed to Hermes Runs. |
| POST | `/api/chat/interrupt` | Stop only the authenticated device/session's bound Hermes Run. |

All endpoint errors use the normal MacSoft top-level error envelope.

## Skill ownership

- Private Skills remain in `client_skills` and `/api/client/skills`. They are
  injected as read-only request instructions and never copied into the Hermes
  Curator write tree.
- Hermes background review creates and changes Progress Skills only under
  `profiles/<profile>/skills/learned`.
- Core, Company, Workflow, Hub, and external Skills are read-only to a device
  profile. A Progress Skill cannot shadow a protected shared Skill name.
- Pin, restore, archive and Curator actions require Hermes agent provenance;
  a manual or legacy learned file is surfaced read-only.

## Run and learning lifecycle

Server continues to return the existing SSE response immediately. Internally
it creates a Hermes `/v1/runs` Run with an immutable profile binding. A
completed run is recorded as learning-eligible; native background review runs
after the response and writes its lifecycle outcome to that profile. Failed or
cancelled runs are recorded `skipped` and must not learn. Background review has
the hard memory/skills-only tool whitelist, so it cannot call AutoCount write
tools.

## Mutation and recovery

Every Progress Skill mutation uses a profile write lock, pre-change snapshot,
atomic write path, before/after learned-tree hashes, native audit JSON, and
Server audit record. Audit records include profile, device, skill where known,
run where known, source, hashes, timestamp, and result. Rollback is explicit,
creates its own safety snapshot, clears the Skill prompt cache, and is audited.
