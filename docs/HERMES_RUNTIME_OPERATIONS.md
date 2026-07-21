# MacSoft Agent Runtime Operations

## Directory ownership

`C:\MacSoft-Agent\hermes` is the Hermes source checkout. Branding and application code belong there.

`C:\MacSoft-Agent\server` is the separate MacSoft Server application. Its SQLite database is `server\data\macsoft-server.db`; that database is not Hermes runtime state.

`C:\MacSoft-Agent\runtime` is `HERMES_HOME`. It stores machine-specific configuration, credentials, identity, plugins, sessions, memory, logs, caches, and generated state. It must never contain Hermes source or MacSoft Server source.

`C:\MacSoft-Agent\backup` contains rollback snapshots and must never be committed.

The AutoCount Local Connector installation remains outside this project.

## Runtime configuration and secrets

| Path | Responsibility | Secret handling |
| --- | --- | --- |
| `runtime\config.yaml` | Provider/model selection, API server settings, plugin enablement | May contain API keys; do not commit or paste into tickets |
| `runtime\auth.json` | Provider authentication and OAuth state | Secret; do not commit |
| `runtime\.env` | Optional environment secrets | Secret; currently not present, but protected if created |
| `runtime\SOUL.md` | MacSoft Agent identity and behavior | Not normally secret; changes require a new session |
| `runtime\plugins\macsoft-autocount\config.json` | AutoCount Cloud URL, API key, connectorId, companyId, and timeouts | Secret; do not commit |
| `runtime\state.db*` | Hermes sessions and state | User data; do not commit |
| `runtime\response_store.db*` | Stored API responses | User data; do not commit |
| `runtime\logs` | Runtime logs | May contain sensitive operational data; do not commit |
| `runtime\memories`, `runtime\sessions`, `runtime\skills` | Learned/user-installed state | User data; do not commit |

Safe examples are stored in `runtime.example` and `server\macsoft-server.yaml.example`. Real runtime files are intentionally excluded by the project-root `.gitignore`. The nested `hermes` Git repository cannot see sibling `runtime` or `backup` directories.

Windows ACL inheritance was removed from the active runtime, rollback snapshot, MacSoft database directory, and real server configuration. Only the owning Windows user, Administrators, and SYSTEM have access. Keep the safe examples and operational documentation non-secret.

## Changing configuration

To change the AI Service model API configuration, edit `runtime\config.yaml`. Preserve unrelated keys. Restart the AI Service and MacSoft Agent Desktop, then create a new session.

To change the AutoCount API key, connectorId, or companyId, edit `runtime\plugins\macsoft-autocount\config.json`. Restart the AI Service and MacSoft Agent Desktop after the change. Do not change the AutoCount SQL database mapping as part of this runtime configuration.

To change MacSoft Server settings, copy the safe example to `server\macsoft-server.yaml`, fill in the local values, and restart MacSoft Server.

## Development and recovery startup

The following BAT/PowerShell flow is development/recovery-only. Customer
staging and installed builds use the coordinated MacSoft Agent Host documented
in `MACSOFT_PRODUCTION_RUNTIME_FOUNDATION.md`.

Start in this order:

1. Run `C:\MacSoft-Agent\start-hermes-gateway.bat` and wait for `http://127.0.0.1:8642/health` to return HTTP 200.
2. Run `C:\MacSoft-Agent\start-macsoft-server.bat` and wait for `http://127.0.0.1:8787/health` to return HTTP 200.
3. Run `C:\MacSoft-Agent\start-hermes-desktop.bat`.

`C:\MacSoft-Agent\start-all.bat` performs the same order and health waits. The scripts calculate the project root from their own location and set `HERMES_HOME` explicitly; no Windows username is embedded.

For development recovery, close MacSoft Agent Desktop before stopping the backend processes, then run `C:\MacSoft-Agent\stop-all.bat`. In packaged operation, Desktop closure does not stop services; use Settings or the Windows Service lifecycle.

## Electron and Chromium data

`HERMES_HOME` controls MacSoft Agent configuration, authentication, identity, plugins, sessions, memory, and logs. Electron/Chromium may retain historical GUI cache and window state under old application-data names; those directories are desktop application data, not an active runtime home.

## Migration record

The previous active home was `%LOCALAPPDATA%\hermes`. On 2026-07-13 it was copied, not moved, to:

- Active runtime: `C:\MacSoft-Agent\runtime`
- Rollback snapshot: `C:\MacSoft-Agent\backup\hermes-runtime-pre-migration-20260713-115517`
- Original fallback copy: `%LOCALAPPDATA%\hermes` (retained)

The source, rollback snapshot, and new runtime each contained 507 files and 17,625,114 bytes at cutover. Critical configuration and credential files matched by SHA-256 after both copies.

The copied `SOUL.md` was then corrected in the new runtime to make the required identity explicit. The rollback snapshot and retained AppData copy preserve the original file.

## Rollback

1. Close MacSoft Agent Desktop.
2. Run `C:\MacSoft-Agent\stop-all.bat`.
3. Set the User environment variable `HERMES_HOME` back to `%LOCALAPPDATA%\hermes`:

   `setx HERMES_HOME "%LOCALAPPDATA%\hermes"`

4. Start Gateway, MacSoft Server, and Desktop in the normal order.
5. If the original AppData copy is damaged, restore it from `C:\MacSoft-Agent\backup\hermes-runtime-pre-migration-20260713-115517` while all components are stopped.
6. Do not delete `C:\MacSoft-Agent\runtime` during rollback; retain it for diagnosis until the rollback is verified.

## Verification checklist

- User-scoped `HERMES_HOME` equals `C:\MacSoft-Agent\runtime`.
- Desktop backend inherits the same `HERMES_HOME`.
- `config.yaml`, `auth.json`, `SOUL.md`, and the AutoCount plugin config are loaded from the new runtime.
- Gateway health is HTTP 200 on port 8642.
- MacSoft Server health is HTTP 200 on port 8787.
- A new session identifies as MacSoft Agent (English) or MacSoft 助手 (Chinese).
- The `macsoft-autocount` plugin is discovered from the new runtime.
- AutoCount connector status succeeds.
- A real read-only debtor command succeeds without printing customer data into migration logs.
- Client pairing, sessions, and chat survive a full restart.
- Restarting does not modify the retained `%LOCALAPPDATA%\hermes` fallback.

Run `scripts\export-runtime-inventory.ps1` after intentional runtime changes to refresh `docs\hermes-runtime-inventory.csv`.
