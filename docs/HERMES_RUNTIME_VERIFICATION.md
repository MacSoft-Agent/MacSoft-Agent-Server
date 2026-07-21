# MacSoft Agent Runtime Migration Verification

Date: 2026-07-13

## Result summary

The actual project root is `C:\MacSoft-Agent`; the requested `C:\hermes-agent` path did not exist. The existing `hermes`, `server`, `backup`, and `docs` directory names were preserved. `C:\MacSoft-Agent\runtime` is now the intended `HERMES_HOME`.

| Check | Status | Evidence | Next action |
| --- | --- | --- | --- |
| Runtime copy | Pass | Source, rollback, and target each had 507 files and 17,625,114 bytes at cutover | Keep the rollback snapshot |
| Critical file integrity | Pass | `auth.json`, `config.yaml`, and AutoCount `config.json` matched source SHA-256 after copy | Do not edit during migration closeout |
| User environment | Pass | Interactive User HKCU `HERMES_HOME` is `C:\MacSoft-Agent\runtime` | Sign out/in only if an already-running unrelated process needs the updated environment |
| Python runtime paths | Pass | Config, env, skills, plugins, sessions, state, and logs resolve under the new home | None |
| Plugin discovery | Pass | `macsoft-autocount` was discovered from the new runtime | External connector verification remains pending |
| Gateway | Pass | HTTP 200 at `127.0.0.1:8642` after migration and after restart | Use the root startup script |
| Provider/model/auth | Pass | A new authenticated Gateway session returned HTTP 200 using the preserved configuration | No provider/model change made |
| SOUL identity | Pass | Runtime identity is configured as MacSoft Agent in English and MacSoft 助手 in Chinese | Start a new session after future SOUL changes |
| MacSoft Server | Pass | HTTP 200 at `127.0.0.1:8787` after migration and after restart | Use the root startup script |
| Pairing/session/chat | Pass | Temporary device pairing, client auth, session creation, streamed chat, and persisted user/assistant messages succeeded | Remove the verification rows later only if operational policy requires cleanup |
| Desktop | Pass | Electron started; Desktop backend `/api/status` reported the new runtime and config paths | Launch in foreground with `start-hermes-desktop.bat` |
| Full restart | Pass | Gateway, Server, and Desktop restarted successfully | None |
| Old AppData fallback | Pass | Complete path/size/timestamp signature stayed unchanged across the full restart | Retain until acceptance is complete |
| Runtime ACLs | Pass | Broad local-user access removed; owning User, Administrators, and SYSTEM remain | Reapply after restoring files from media that resets ACLs |
| AutoCount connector status | Pending approval | The post-migration check requires sending the stored API key to AutoCount Cloud | Obtain explicit approval, then run a sanitized status check |
| AutoCount debtor read | Pending approval | The post-migration read requires credential-backed outbound access and returns business data | Obtain explicit approval; report only status/count, not debtor data |

## Distinctions confirmed

- Hermes source remains `C:\MacSoft-Agent\hermes`.
- MacSoft Server remains `C:\MacSoft-Agent\server`.
- MacSoft SQLite remains `C:\MacSoft-Agent\server\data\macsoft-server.db`.
- AutoCount Local Connector installation was not moved.
- `%APPDATA%\Hermes` and `%APPDATA%\MacSoft Assistant` are Electron/Chromium application-data locations, not `HERMES_HOME`.
- Installer references to `%LOCALAPPDATA%\hermes` remain valid defaults for managed installation infrastructure; runtime resolution honors explicit `HERMES_HOME` first.
- No separate branding-and-soul setup script was present in the actual project or the inspected user startup locations.
