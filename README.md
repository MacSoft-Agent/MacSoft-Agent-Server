# MacSoft Agent

MacSoft Agent is the Windows server product that hosts the MacSoft Server,
the Hermes-based AI Service, the Server Desktop, and the AutoCount integration.
This repository contains source and reproducible build inputs. It must not
contain customer data, credentials, installed dependencies, runtime state, or
installer output.

## Start here

- [Documentation map](docs/README.md)
- [System architecture](docs/architecture/MACSOFT_AGENT_PRODUCT_FOUNDATION.md)
- [Runtime operations](docs/operations/HERMES_RUNTIME_OPERATIONS.md)
- [Development and release worktrees](docs/development/DEVELOPMENT_AND_RELEASE_WORKTREES.md)
- [Upstream Hermes maintenance](docs/development/MACSOFT_UPSTREAM_MAINTENANCE.md)

## Repository map

| Path | Ownership and purpose |
| --- | --- |
| `server/` | Client-facing MacSoft Server API, pairing, sessions, files, chat bridge, skills, and AutoCount-facing server behavior |
| `product_runtime/` | Windows Host lifecycle, initialization, paths, service control, and protected-resource upgrades |
| `hermes/` | Pinned Hermes source baseline plus the MacSoft Server Desktop integration |
| `packaging/` | Runtime templates, protected resources, NSIS installer, and packaging entry points |
| `scripts/` | Development-runtime, staging, dependency synchronization, and release automation |
| `runtime.example/` | Safe examples only; never real runtime state |
| `docs/` | Architecture, development, operations, contracts, handoffs, reports, and reference material |
| `branding/` | Product-owned visual assets |

The root `start-*.bat` and `stop-*.bat` files are developer conveniences. A
customer installation is started and controlled by the installed Windows Host
and Server Desktop, not by these batch files.

## Local development

Dependencies are intentionally not stored in Git. A checkout must restore the
locked Python and Node environments before use. Once dependencies exist, run:

```powershell
cd C:\path\to\MacSoft-Agent
.\start-test.bat
```

Stop the complete isolated development runtime with:

```powershell
.\stop-test.bat
```

Do not start a second copy when ports `8766`, `8643`, `8642`, `8787`, or `5174`
are already occupied.

## Verification

Check the repository structure before debugging or packaging:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-repository-cleanliness.ps1
```

Run focused Python product tests from the pinned Hermes environment:

```powershell
$env:PYTHONPATH = "$(Join-Path $PWD 'product_runtime');$(Join-Path $PWD 'server')"
.\hermes\venv\Scripts\python.exe -m unittest discover product_runtime\tests
.\hermes\venv\Scripts\python.exe -m unittest discover server\tests
```

Run Desktop checks from the repository root:

```powershell
Push-Location .\hermes
npm.cmd run typecheck --workspace apps/desktop
npm.cmd run test:ui --workspace apps/desktop
Pop-Location
```

## Release build

Release creation is version-driven and clean-commit gated. Use the repository
release script instead of manually copying source or dependencies:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-release.ps1
```

Generated `staging/`, `release/`, `backup/`, and `work/` directories are local
artifacts and are ignored by Git.

## Source-control rules

- Commit source, tests, templates, lock files, and durable documentation.
- Never commit `runtime/`, `server/data/`, `initialization.json`, logs,
  databases, credentials, virtual environments, `node_modules`, installers,
  staging trees, acceptance snapshots, or Desktop-generated JavaScript.
- Treat `hermes/` as a pinned upstream baseline. Upgrade it on a dedicated
  integration branch and run MacSoft compatibility tests before merging.
- Keep unrelated fixes in separate commits so packaging and regressions can be
  traced to an exact Git commit.
