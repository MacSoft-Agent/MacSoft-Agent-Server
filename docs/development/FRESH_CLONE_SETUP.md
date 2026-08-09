# Fresh Clone Development Setup

This guide is the single setup path for a developer or coding agent starting
from a new clone of MacSoft Agent.

The repository intentionally does not contain downloaded dependencies,
credentials, databases, runtime state, build output, or installers. A correct
clone is therefore expected to be missing `hermes\venv`,
`hermes\node_modules`, local configuration, provider login state, and customer
data. Restore dependencies from the committed lock files; never copy these
directories from another developer's computer.

## 1. Supported development environment

Use a Windows 11 computer for the complete MacSoft runtime.

Install these machine-level prerequisites:

- Git for Windows
- PowerShell 7 or Windows PowerShell 5.1
- Node.js 24 with npm
- Python 3.12.13
- `uv` 0.11.16 or a compatible newer release
- PostgreSQL 17 when developing or running PharmaRise Module 1/2 workflows

NSIS is not required to run or test the source. It is required only for an
installer/release build.

Confirm the tools are available:

```powershell
git --version
node --version
npm --version
py --version
uv --version
```

The expected Node major version is 24. The repository bootstrap asks `uv` to
obtain Python 3.12.13 when it creates the project environment, so a separately
installed matching Python may not be necessary when `uv` can download it.

PostgreSQL is not required for unrelated MacSoft development. It is a real
runtime dependency for PharmaRise payment and receiving Cases; helper tests do
not replace a live PostgreSQL acceptance run.

## 2. Clone the authoritative repository

Run PowerShell in the parent directory where the source should live:

```powershell
git -c core.longpaths=true clone https://github.com/MacSoft-Agent/MacSoft-Agent-Server.git
cd MacSoft-Agent
git config core.longpaths true
```

Windows long-path support is important because maintained files inside the
pinned Hermes tree can exceed the legacy 260-character path limit.

Before continuing, confirm the repository identity:

```powershell
git remote -v
git status --short --branch
```

Both `origin` URLs should point to:

```text
https://github.com/MacSoft-Agent/MacSoft-Agent-Server.git
```

Read these repository instructions before changing code:

1. `AGENTS.md`
2. `CONTRIBUTING.md`
3. `docs\README.md`
4. `docs\PROJECT_STATUS.md`
5. `hermes\AGENTS.md` when working inside `hermes\`

## 3. Restore all required development dependencies

From the repository root, run the maintained bootstrap:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap-development.ps1
```

The script performs the supported dependency restoration:

- verifies the committed product metadata, Python project files, and lock files;
- creates `hermes\venv` with Python 3.12.13;
- restores the locked Hermes and MacSoft Server Python dependencies from
  `hermes\uv.lock`;
- includes the `dev` and `macsoft-server` Python dependency groups;
- runs `npm ci` from `hermes\package-lock.json`;
- restores the root Node workspace, including the Server Desktop.

Do not separately create `server\.venv`. The supported combined development
runtime uses `hermes\venv` for Hermes, MacSoft Server, and product-runtime
tests.

Do not run `npm install` in individual workspace directories. The committed
root lock file and npm workspace layout are the dependency authority.

Expected local generated directories include:

```text
hermes\venv
hermes\node_modules
```

They are ignored by Git and must not be committed.

## 4. Verify the restored checkout

Run the complete source-development baseline:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-development.ps1
```

This checks repository hygiene and runs the maintained product-runtime, Server,
Desktop UI, Electron, packaging-script, and TypeScript verification baseline.
It does not test a real installer, Windows Service, external Thin Client,
provider account, AutoCount company, or customer data.

If this command passes, the clone and its required source dependencies are
ready for normal development.

## 5. Start the isolated development application

First make sure no installed MacSoft product or previous test runtime is using
these development ports:

```text
8766  Windows Host control
8643  Desktop configuration backend
8642  Hermes AI Service
8787  MacSoft Server
5174  Desktop development UI
```

Start the current Git source:

```powershell
.\start-test.bat
```

The script starts the Host, configuration backend, AI Service, MacSoft Server,
and current-Git Server Desktop in isolated test mode. The Desktop is served
from this checkout through Vite; it is not an installed customer application.

Stop the complete test runtime with:

```powershell
.\stop-test.bat
```

Do not mix this source runtime with an installed MacSoft Agent instance on the
same ports. If startup reports occupied ports, identify and stop the previous
test runtime or installed service before trying again.

## 6. Confirm the local services

After `start-test.bat` reports that the runtime is ready:

```powershell
curl.exe --max-time 5 http://127.0.0.1:8766/health
curl.exe --max-time 5 http://127.0.0.1:8643/api/status
curl.exe --max-time 5 http://127.0.0.1:8642/health
curl.exe --max-time 5 http://127.0.0.1:8787/health
```

A healthy local runtime proves that the source services can start. It does not
prove that an AI provider account or AutoCount connection is configured.

## 7. Configuration that Git does not provide

The following data is deliberately excluded from Git and must be configured
locally through the product UI or an approved local example:

- model-provider login or API keys;
- AutoCount URL, company, credentials, and business configuration;
- Host control tokens and other local secrets;
- pairing devices and device tokens;
- sessions, uploads, OCR files, attachments, and databases;
- ProgramData and installed-product state;
- `.env` files and private configuration;
- signing certificates and release credentials.

Safe examples are available in:

```text
server\macsoft-server.yaml.example
runtime.example\config.yaml.example
runtime.example\plugins\macsoft-autocount\config.json.example
hermes\.env.example
```

Copy only the example needed for a specific development task and keep the
result local. Never add a real secret, customer database, attachment, or
runtime file to Git.

The source runtime can start without a provider account, but AI chat and model
operations will remain unavailable until a provider is configured. AutoCount
operations likewise require a valid local AutoCount connection.

### PharmaRise PostgreSQL setup

Install PostgreSQL 17 with its command-line tools. Keep the normal local port
`5432`, then initialize the workflow database from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup-pharmarise-postgres.ps1
```

The script securely prompts for the local PostgreSQL administrator password,
creates a dedicated `macsoft_workflow` database and least-privilege application
role, applies the four-table migration, creates the managed evidence directory,
and writes the generated application DSN only to the ignored local runtime
AutoCount config. It does not print or add database passwords to Git.

To configure an installed test runtime as well as the source runtime, explicitly
pass both local config paths. Never use this example with production customer
credentials:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\setup-pharmarise-postgres.ps1 `
  -ConfigPath @(
    '.\runtime\plugins\macsoft-autocount\config.json',
    'C:\ProgramData\MacSoft Agent\runtime\plugins\macsoft-autocount\config.json'
  )
```

The customer deployment model must explicitly provide PostgreSQL or an approved
managed PostgreSQL connection. A release must not assume that a customer PC
already has PostgreSQL installed.

## 8. Common setup failures

### `hermes\venv is missing`

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap-development.ps1
```

Do not copy a virtual environment from another path or computer.

### `hermes\node_modules is missing`

Run the same bootstrap command. It restores the locked npm workspace with
`npm ci`.

### `uv is required`

Install `uv` 0.11.16 or newer, open a new PowerShell window, confirm
`uv --version`, and rerun the bootstrap.

### `Node.js 24 and npm are required`

Install Node.js 24, open a new PowerShell window, confirm `node --version` and
`npm --version`, and rerun the bootstrap.

### A required port is occupied

Stop this repository's previous runtime first:

```powershell
.\stop-test.bat
```

If the port remains occupied, inspect it without terminating an unknown
process:

```powershell
Get-NetTCPConnection -State Listen |
    Where-Object LocalPort -In 8766,8643,8642,8787,5174 |
    Select-Object LocalAddress,LocalPort,OwningProcess
```

An installed `MacSoftAgentHost` service may own the production ports. Do not
kill or delete it blindly; decide whether the installed product or source test
runtime should be active.

### AI Service is healthy but chat has no model

Dependency setup is complete, but provider configuration is not. Configure a
supported provider/model in the Server Desktop and then retest. Do not treat a
missing provider credential as a missing Python or Node dependency.

### Clone, bootstrap, or npm fails on a long path

Confirm `git config core.longpaths true`. Prefer a short clone location such as
`C:\Work\MacSoft-Agent` if Windows tooling still reaches a path-length limit.

## 9. Release-only requirements

A passing development setup does not make the machine release-ready. Installer
creation additionally requires the repository's release preconditions,
including NSIS and the dedicated packaging workflow.

Release builds are accepted only from a separate clean clone whose directory
name is exactly:

```text
MacSoft-Agent-Packaging
```

Check out the accepted 40-character Git commit in that clone, ensure the
development ports are not occupied, and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build-release.ps1 `
  -ExpectedCommit <accepted-40-character-commit>
```

`ExpectedCommit` is mandatory and must be a full 40-character hexadecimal
commit SHA that exactly matches the packaging clone's `HEAD`. The release
script refuses:

- any directory name other than `MacSoft-Agent-Packaging`;
- a missing source or packaging marker;
- a different `HEAD` from `ExpectedCommit`;
- tracked or untracked working-tree changes;
- listeners on ports `8766`, `8643`, `8642`, `8787`, or `5174`;
- missing `uv` or `npm`;
- missing NSIS `makensis.exe`.

The script recreates the Python 3.12.13 product environment, restores locked
Python and Node dependencies, builds the Desktop, creates a new staging
directory, verifies the staging manifest, and produces the installer and build
report. It may locate `makensis.exe` in the Electron Builder cache or accept an
explicit `-NsisPath`.

Do not manually copy `venv`, `node_modules`, runtime state, or an old staging
directory into a release. Read the release and worktree documentation before
building:

- `docs\release\RELEASE_READINESS.md`
- `docs\development\DEVELOPMENT_AND_RELEASE_WORKTREES.md`

## 10. Definition of setup success

A fresh clone is correctly configured when all of these are true:

1. `origin` points to `MacSoft-Agent/MacSoft-Agent`.
2. `git status` shows no unexpected generated or secret files.
3. `hermes\venv\Scripts\python.exe` exists.
4. `hermes\node_modules` exists.
5. `scripts\verify-development.ps1` passes, or any environment-specific
   exception is recorded precisely.
6. `start-test.bat` makes ports 8766, 8643, 8642, and 8787 healthy and starts
   the current-Git Desktop on port 5174.
7. Missing provider or AutoCount credentials are understood as local product
   configuration, not repository dependency failures.
