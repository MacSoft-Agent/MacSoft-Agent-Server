# Contributing to MacSoft Agent

MacSoft Agent is a Windows server product built from the MacSoft Server,
the pinned Hermes runtime, the Windows Host and Server Desktop, packaging, and
AutoCount integration. The Thin Client is owned separately and is not part of
this repository.

Start with [AGENTS.md](AGENTS.md), [the documentation map](docs/README.md), and
[the current project status](docs/PROJECT_STATUS.md). Do not rely on private
chat history as project authority.

## Development requirements

- Windows 11 for the complete product development runtime
- Git for Windows
- PowerShell 7 or Windows PowerShell 5.1
- Node.js 24 and npm
- Python 3.12.13
- [uv](https://docs.astral.sh/uv/) 0.11.16 or a compatible newer version

NSIS and a dedicated packaging clone are required only for release work. They
are not required for the contributor verification baseline.

## Restore a fresh checkout

Clone the repository into any normal development path. Do not copy
`node_modules`, virtual environments, ProgramData, databases, credentials, or
runtime output from another machine.

```powershell
git -c core.longpaths=true clone https://github.com/NatsunagiYu/MacSoft-Agent.git
cd MacSoft-Agent
git config core.longpaths true
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap-development.ps1
```

The bootstrap script creates `hermes\venv` from the committed `uv.lock` and
installs the root Node workspaces from `hermes\package-lock.json`. Both
directories are local, ignored development state.

The long-path setting is required on Windows because maintained Hermes
documentation contains paths that can exceed the legacy 260-character limit.

Run the complete contributor baseline:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-development.ps1
```

This runs repository hygiene, product-runtime tests, Server tests, Desktop
renderer tests, Electron tests, packaging-script tests, and Desktop typecheck.
It does not run a real installer, Windows Service, Thin Client, provider,
AutoCount company, or customer-data acceptance flow.

The full Desktop lint command currently has known baseline debt and is not a
passing repository gate. Do not describe it as passing or fix unrelated lint
findings inside another change.

## Repository boundaries

| Area | Responsibility |
| --- | --- |
| `product.json` | Product identity, version, Build ID, and Hermes pin |
| `server/` | Client-facing API, auth, sessions, files, chat/SSE, and Server contracts |
| `product_runtime/` | Host ownership, installed paths, lifecycle, and protected resources |
| `hermes/` | Pinned Hermes source and MacSoft Server Desktop integration |
| `hermes/plugins/` and protected packaging templates | Approved integrations, including AutoCount |
| `packaging/` and release scripts | Installer, staging, upgrade, and release evidence |
| `docs/contracts/` and `docs/handoffs/` | Cross-team Thin Client contracts and handoffs |

Root [AGENTS.md](AGENTS.md) applies everywhere. Inside `hermes/`, also follow
`hermes/AGENTS.md`; its Hermes-specific instructions take precedence when they
are more specific.

## Branch workflow

The recommended integration branch is `main`. Keep it protected and use
short-lived scoped branches:

- `feature/<short-name>`
- `fix/<short-name>`
- `test/<short-name>`
- `docs/<short-name>`
- `chore/<short-name>`
- `integration/runtime-<version>` only for a reviewed Hermes candidate

Create branches from an up-to-date `main`:

```powershell
git switch main
git pull --ff-only
git switch -c fix/short-description
```

Do not make broad direct changes on `main`. Release branches should exist only
for active release work, not as a permanent GitFlow layer.

## Scope and approval

Keep one pull request focused on one outcome. If an unrelated bug appears:

1. record the evidence;
2. leave it unchanged unless it blocks the approved outcome;
3. open a separate issue or Work Package;
4. request Product Owner direction when it crosses an authority boundary.

Product Owner approval is required before changing customer-visible scope,
Client/Server contracts, authentication or security boundaries, persistent
data or migrations, installer/update behavior, ports, product version, Build
ID, Hermes baseline, AutoCount business rules, or release acceptance.

Use `docs/work-packages/_TEMPLATE.md` for medium or high-risk work. Routine
small fixes may use a concise investigate/change/verify record.

## Pull requests

Before opening a pull request:

1. inspect the exact diff and remove unrelated changes;
2. run the focused tests for the changed area;
3. run `scripts\verify-development.ps1`, or state precisely why a check could
   not run;
4. run `git diff --check`;
5. confirm no secret, database, runtime data, generated output, or customer
   artifact was added;
6. update contracts, status, or Work Package evidence when the change affects
   them.

The pull request must state:

- the problem and intended outcome;
- scope and explicit non-scope;
- important design or contract effects;
- exact verification commands and results;
- tests not run and why;
- persistent-data, security, installer, Client, AutoCount, or Hermes risks;
- Product Owner decisions still required.

Review responsibility is role-based until the Product Owner assigns GitHub
accounts:

| Change area | Required review responsibility |
| --- | --- |
| Product identity and release metadata | Product Owner plus release reviewer |
| Server API, auth, database, and contracts | Server reviewer; Product Owner for public/persistent boundaries |
| Host and installed runtime | Host/runtime reviewer |
| Hermes subtree and upstream integration | Hermes integration reviewer |
| Desktop | Desktop reviewer |
| External Thin Client contract | Server and Thin Client reviewers |
| Installer, packaging, and update | Release/installer reviewer plus Product Owner |
| AutoCount writes and validation | AutoCount reviewer plus Product Owner for business rules |
| Secrets and sensitive-data boundaries | Security reviewer plus Product Owner |

Do not create or guess CODEOWNERS identities. Until maintainers are assigned,
the pull request author must request the appropriate reviewers explicitly.

## Files that must never be committed

Never commit credentials, provider keys, Host control tokens, AutoCount
credentials, customer data, ProgramData, uploads, attachments, logs,
databases, `.env` files, private keys, signing material, virtual environments,
`node_modules`, runtime directories, staging trees, installers, or generated
Desktop JavaScript. The root `.gitignore` and
`scripts/check-repository-cleanliness.ps1` enforce the common cases, but the
author remains responsible for inspecting every staged file.
