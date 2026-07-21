# MacSoft Agent Production Runtime Foundation

## Product and version ownership

`C:\MacSoft-Agent\product.json` is the authoritative product metadata source.
MacSoft Agent starts at product version `0.1.0`, channel `stable`, build ID
`macsoft-agent-0.1.0-stable.20260714.1`. The Desktop package version is checked
against this file during staging construction.

The pinned runtime base is `v2026.7.7.2` at commit
`79f12748022817a7c4f3fee747e45e9e6979214a`. This pin is administrator/build
diagnostic data. Normal About UI shows only `MacSoft Agent` and `Version 0.1.0`.

## Customer update boundary

Customer builds are installer-managed. The About page has no branch, commit,
change count, source check, or Update now action. The legacy update IPC surface
returns `installer-managed` and does not invoke the source/Git updater. Renderer
startup and focus handling do not poll either the Desktop source updater or the
runtime update API.

`update_manifest_url` is currently `null`. Therefore no update network request
is made and there is no fallback to another repository. A future MacSoft-owned
HTTPS manifest may be added behind this field; full-installer installation
remains the only approved first-release update mechanism.

Packaged Desktop is a Host management console. It does not probe a system CLI,
system Python, or a user runtime and cannot enter the legacy bootstrap downloader.
It does not create a second chat/Agent execution path. Client chat continues to
use MacSoft Server on port 8787. If the Host is not installed or is stopped, the
Desktop remains available, skips the legacy gateway boot and customer startup
overlays, and routes the root view to Server & AutoCount Settings. The missing
Host is presented through service status instead of a Desktop boot failure.

## Central path model

Python owns the production path contract in `product_runtime/macsoft_runtime/paths.py`.
Electron uses the matching focused resolver in
`hermes/apps/desktop/electron/macsoft-product.ts`. Both resolvers are covered by
the same development/packaged assertions.

| Responsibility | Development | Packaged |
| --- | --- | --- |
| Program root | `C:\MacSoft-Agent` | `C:\Program Files\MacSoft Agent` |
| Writable data root | `C:\MacSoft-Agent` | `C:\ProgramData\MacSoft Agent` |
| AI runtime | `C:\MacSoft-Agent\runtime` | `C:\ProgramData\MacSoft Agent\runtime` |
| Server data/config | `C:\MacSoft-Agent\server` | `C:\ProgramData\MacSoft Agent\server` |
| Logs | development root | `C:\ProgramData\MacSoft Agent\logs` |
| Backup | `C:\MacSoft-Agent\backup` | `C:\ProgramData\MacSoft Agent\backup` |
| Host state | Server development data | `C:\ProgramData\MacSoft Agent\config\host` |

Mutable state is never written to Program Files. Packaged Desktop ignores the
legacy `%LOCALAPPDATA%\hermes` runtime location. `MACSOFT_DATA_ROOT` and explicit
resolver arguments exist for staging/tests; installed defaults remain ProgramData.

## First-run and upgrade behavior

`initialize_product_data()` is idempotent. A first run creates runtime, server,
config, logs, backup, Host state, and an empty SQLite file. It installs:

- a clean AI Service configuration with a generated local API key;
- the default MacSoft Agent SOUL;
- blank AutoCount connection settings;
- MacSoft-owned AutoCount plugin code and its protected System Skill;
- a clean MacSoft Server configuration.

It never imports active development runtime state. In particular it does not
copy `auth.json`, OAuth state, AutoCount credentials, connector/company IDs,
sessions, messages, Client Skills, logs, backups, or test data.

Mutable templates are create-once. Protected resources use
`protected-resources.json` plus `initialization.json` version/hash records. An
unmodified older protected resource can be migrated explicitly; a locally
modified protected file is preserved and reported as a conflict. Customer data
is not overwritten during an upgrade.

## Bundled Python decision and dependency audit

Both development virtual environments reference the separately installed
Python 3.12.10 base and are not portable. A frozen executable was rejected for
this batch because the AI runtime uses dynamic providers, plugin discovery,
Skills, native extensions, and subprocess entry points.

Staging therefore contains an isolated Python 3.12.10 runtime with:

- the base DLLs and standard library, including `DLLs` in `python312._pth`;
- the audited AI environment site-packages;
- FastAPI, Uvicorn, YAML, SQLite, SSL, Pydantic, aiohttp, cryptography,
  pywin32, psutil, and native extensions;
- `certifi` CA data explicitly assigned to `SSL_CERT_FILE` and
  `REQUESTS_CA_BUNDLE` by the Host;
- `PYTHONNOUSERSITE`-compatible isolation and no dependency on registry/user
  packages.

The AI environment already supplies every MacSoft Server distribution. Its
tested `websockets==15.0.1` is retained rather than overlaying the Server
environment's transitive `16.0`. The merged runtime passes `pip check` and all
49 Server tests.

## MacSoft Agent Host

`MacSoftAgentHost` coordinates both processes:

1. initialize/preserve ProgramData;
2. start AI Service with `HERMES_HOME` set to ProgramData and bind it to
   `127.0.0.1`;
3. require the expected AI health identity;
4. start MacSoft Server with its ProgramData configuration;
5. require the expected Server health identity.

It records PID and process creation time, stops only owned process trees, refuses
to adopt a matching but unowned service, and refuses to kill an unrelated port
owner. A file lock prevents duplicate Host instances. Unexpected exits use a
maximum of three restarts per five minutes. Host and child logs are sanitized
and bounded to 5 MiB with five rotations.

The Windows Service-compatible entry point is `macsoft_runtime.service` with
service name `MacSoftAgentHost`. Final service registration belongs to the final
installer batch. The staging console entry point exercises the same Host core.

Control is HTTP JSON bound only to `127.0.0.1:8766`, authenticated by a generated
token stored under Host state. It exposes status, Start, Stop, Restart, and the
auto-start preference only. It is not a LAN administration API. The final
installer must apply the approved ProgramData ACL while registering the service.

## Desktop service controls

The existing Server & AutoCount page now follows:

```text
Settings -> preload -> Electron main -> loopback Host control -> owned services
```

It displays AI Service and MacSoft Server states, Start/Stop/Restart, Refresh
Status, auto-start, readable last errors, and collapsed PID/version diagnostics.
The renderer never reads the control token, process table, or configuration
files and never spawns or terminates a process.

## Staging distribution

The final staging output for this batch is:

`C:\MacSoft-Agent\staging\MacSoft-Agent-0.1.0-20260714.5`

Layout:

```text
product.json
desktop/
macsoft_runtime/
ai-service/
server/
python/
templates/
staging-manifest.json
```

The manifest contains 12,646 hashed program files (607,885,298 bytes including
the generated manifest). Audit found zero Git
directories, active databases, auth files, logs, backups, development paths, or
build-user paths. The unpacked Desktop reports file version `0.1.0.0`.

Build command:

```powershell
scripts\build-staging.ps1 -Output <new-empty-directory>
```

The script intentionally refuses a non-empty output directory. It does not
construct NSIS/MSI.

## Clean-environment smoke procedure and evidence

The staging directory was copied to a non-development Documents workspace and
run with PATH limited to bundled Python. Node.js, npm, and Git were not visible.
The packaged Desktop smoke used a dedicated Electron user-data directory so an
unrelated existing desktop profile or single-instance lock could not affect the
result; this is test isolation and is not a customer launch requirement.

Verified results:

- all 12,646 manifest hashes matched;
- bundled Python prefix/base prefix/executable resolved inside staging;
- `pip check` reported no broken requirements;
- AI Service health passed and listened only on `127.0.0.1:8642`;
- MacSoft Server health passed on `0.0.0.0:8787`, version `0.1.0`;
- SSL variables pointed to staged `certifi\cacert.pem`;
- pairing, device authentication, session creation, message persistence,
  Activity v1, token output, completion, session deletion, and Client Skill
  creation passed;
- SSE did not contain the device token;
- Server Stop/Start changed the owned PID; AI Restart passed; duplicate Host
  exited with code 1;
- auto-start preference round-tripped;
- packaged Desktop remained alive, and closing it did not stop either service;
- with no Host running, packaged Desktop remained alive, emitted no Desktop boot
  failure or bootstrap log, and did not create a false Host state;
- the complete `%LOCALAPPDATA%\hermes` file metadata fingerprint was unchanged;
- Host-owned AI and Server logs were created through bounded, sanitized child
  output capture.

The clean template intentionally has no model OAuth credential, so the smoke
chat validates the sanitized failure/final-message path rather than a paid live
model response. No real AutoCount write was attempted.

Final automated evidence: 15/15 production-runtime tests, 49/49 Server tests,
15/15 focused Electron product/Host/update/config tests, 29/29 focused renderer
settings/update tests, Desktop typecheck, production build, and unpacked
electron-builder output passed. The broader inherited Electron platform run was
also executed: 313 passed, 3 failed, and 2 were skipped out of 318. Its failures
are the existing Windows path expectation in `update-relaunch.test.ts` and two
tests that require a Bash executable on Windows; none is in the focused customer
runtime surface. They remain visible rather than being reported as a full pass.

## Development-only paths

`C:\MacSoft-Agent\start-*.bat`, `start-all.bat`, `stop-all.bat`, source venvs,
Vite port 5174, and `scripts\stop-runtime.ps1` remain development/recovery tools.
They are not copied into staging and are not the customer startup model.

## Upgrade preservation and final-installer boundary

Full-installer upgrades replace Program Files and preserve ProgramData. Before
replacement, the installer must stop `MacSoftAgentHost` and wait for owned child
processes. It must not delete ProgramData during a normal upgrade.

The final installer batch still owns:

- per-machine NSIS construction and administrator elevation;
- Windows Service registration, automatic start, recovery settings, and ACLs;
- Start Menu/Desktop shortcuts and registered uninstall behavior;
- optional firewall rule for port 8787 only;
- upgrade stop/start sequencing and uninstall data-retention choice;
- code signing and final clean-machine installer acceptance.

It does not own silent updates, delta updates, automatic rollback, AutoCount
Connector redistribution, or production AutoCount write testing.
