# WP-004 — Built-In Update

## Objective

Provide a trusted, installer-managed Windows update flow inside the existing
Hermes-native **Settings → About** page while preserving customer state and
preventing source/Git update behavior in packaged MacSoft runtime.

## Implemented source scope

- signed manifest schema and strict version/channel rules;
- Ed25519 verification with an embedded public key;
- bounded HTTPS manifest retrieval;
- streaming installer download with byte-count and SHA-256 verification;
- mandatory Windows Authenticode validation before execution;
- existing About component, update store, preload and IPC reuse;
- explicit user confirmation and installer handoff;
- Program Files recovery backup outside Program Files;
- installer rollback after installation or health failure;
- health checks for Host, Config Backend, AI Service, Server, and Hermes
  compatibility;
- release manifest build helper.

No new About page, update store, standalone window, Thin Client API or
persistent-data migration was introduced.

## Current verification

- focused trust/download/Authenticode Electron tests;
- full Desktop UI, Electron, script and TypeScript baseline;
- Product Runtime packaging/metadata/compatibility/Host tests;
- PowerShell parser checks;
- NSIS compilation using a disposable test payload;
- `git diff --check`.

## Release gates still open

- Product Owner has not selected the public HTTPS release endpoint.
- The production Ed25519 public key is not embedded.
- The installer is not yet proven Authenticode-signed and timestamped.
- No full-size release installer was built from the dedicated packaging clone.
- Clean-install, real overlay-update, forced rollback, packaged compatibility,
  and real Thin Client reconnect acceptance remain pending.

Until the first three trust inputs are approved and configured,
`product.json` remains fail-closed with null update settings.

## Authority

See `docs/contracts/MACSOFT_UPDATE_CONTRACT.md` for the durable contract.
Implementation details remain authoritative in:

- `hermes/apps/desktop/electron/macsoft-update-*.ts`
- `hermes/apps/desktop/electron/main.ts`
- `hermes/apps/desktop/src/app/settings/about-settings.tsx`
- `packaging/installer/MacSoft-Agent.nsi`
- `packaging/installer/maintenance.ps1`
- `packaging/installer/verify-health.ps1`
