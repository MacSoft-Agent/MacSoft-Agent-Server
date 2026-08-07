# WhatsApp Online Bootstrap Design

## Outcome

A clean MacSoft Agent installation can use the existing Hermes WhatsApp setup
from Server Desktop without requiring Node.js to be installed beforehand.
The first WhatsApp setup remains an online operation: MacSoft Agent downloads
Hermes' supported portable Node.js 22 and installs the bridge dependencies from
the committed lock file before showing the QR code.

## Scope

- Preserve the existing Server Desktop -> Hermes configuration backend ->
  WhatsApp onboarding flow.
- Preserve Hermes' Baileys bridge, QR pairing, bot/self-chat modes, session
  location, gateway routing, LLM behavior, and plugin toolset resolution.
- Include the bridge `package.json` and `package-lock.json` in staging.
- Reuse one Hermes-managed Node installation under the active `HERMES_HOME`.
- Download portable Node.js 22 only when a healthy managed Node/npm is absent.
- Run `npm ci` from the staged lock file when bridge dependencies are absent or
  incomplete.
- Keep Node, npm cache, bridge dependencies, credentials, pairing state,
  sessions, logs, databases, and `.env` out of release source and staging
  inputs except for dependencies created on the customer's machine.

## Non-goals

- Do not bundle Node.js or `node_modules` in the installer.
- Do not add a second WhatsApp implementation or route WhatsApp through port
  8787.
- Do not change open, allowlist, pairing, bot, self-chat, group, prompt, policy,
  or toolset semantics.
- Do not automatically enable or pre-pair WhatsApp in a new installation.

## Architecture

The packaging filter makes a narrow exception for
`ai-service/scripts/whatsapp-bridge/package.json` and
`package-lock.json`; all other Hermes package manifests and every
`node_modules` directory remain excluded.

Before the existing onboarding process starts the bridge, a shared Hermes Node
bootstrap function resolves a healthy managed Node/npm. When neither is
available, it downloads the current Node.js 22 Windows archive from the same
official `nodejs.org` channel used by upstream Hermes, extracts it atomically
under `HERMES_HOME/node`, and verifies `node --version` and `npm --version`.
The onboarding process then runs `npm ci --silent` in the bridge directory and
starts the unchanged QR pairing process. Later gateway starts reuse these
assets.

The bootstrap must be concurrency-safe so two setup requests cannot install or
replace the managed Node tree or bridge dependencies simultaneously. Partial
downloads and partial dependency directories must not be treated as healthy.

## Failure behavior

Failures remain local to WhatsApp onboarding and do not stop MacSoft Server,
the configuration backend, port 8787, or other platforms. The Server Desktop
receives an actionable error distinguishing:

- Node download/network failure;
- unsupported Windows architecture;
- archive/extraction or filesystem failure;
- Node/npm verification failure;
- npm registry/dependency installation failure or timeout.

Retrying setup resumes from the last healthy boundary and replaces incomplete
temporary state. No silent fallback to an unknown system npm is allowed after
a managed Node tree has been created.

## Security and privacy

- Download only over HTTPS from `nodejs.org` using the upstream Hermes Node 22
  channel.
- Resolve dependency versions through the committed bridge lock file and use
  `npm ci`, not unconstrained `npm install`.
- Never stage or package WhatsApp `creds.json`, session directories, `.env`,
  pairing records, logs, or runtime databases.
- Customer-created session and dependency state stays in the installed
  customer's runtime and is preserved only by the existing upgrade policy.
- The official Baileys/WhatsApp Web integration remains an unofficial API with
  its existing account-restriction risk.

## Verification

Automated tests must prove:

1. Staging includes only the two bridge package manifests and excludes every
   `node_modules` directory and runtime/private artifact.
2. Missing managed Node triggers the Node 22 bootstrap; a healthy managed Node
   is reused; an incomplete tree is repaired.
3. Dependency setup uses `npm ci`, the staged lock file, the managed npm, and a
   bounded timeout.
4. Download, verification, and npm failures return actionable onboarding
   errors without enabling WhatsApp or damaging other runtime state.
5. Existing WhatsApp mode, access-control, toolset, AutoCount policy, and
   staging privacy tests remain green.

Release acceptance additionally requires a clean Windows installation with no
system Node/npm, successful online bootstrap, QR pairing, one inbound message,
one LLM reply, and one permitted plugin-tool invocation. A network-blocked run
must fail clearly and succeed after network access is restored. These manual
checks must not be reported as passed until performed on the actual installer.
