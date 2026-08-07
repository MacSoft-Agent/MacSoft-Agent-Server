# WhatsApp Offline Runtime Delivery Design

## Outcome

A clean MacSoft Agent installation can use the existing Hermes WhatsApp setup
from Server Desktop without requiring Node.js to be installed beforehand.
The installer carries Hermes' supported portable Node.js 22 and the bridge
dependencies produced from the committed lock file. First-time WhatsApp setup
therefore requires only normal WhatsApp connectivity and QR pairing, not
access to `nodejs.org` or the npm registry.

## Scope

- Preserve the existing Server Desktop -> Hermes configuration backend ->
  WhatsApp onboarding flow.
- Preserve Hermes' Baileys bridge, QR pairing, bot/self-chat modes, session
  location, gateway routing, LLM behavior, and plugin toolset resolution.
- Include the bridge `package.json`, `package-lock.json`, and release-built
  `node_modules` in staging.
- Include an audited portable Node.js 22 runtime in staging and install it as
  the Hermes-managed Node tree under the active `HERMES_HOME`.
- Build bridge dependencies with `npm ci` during the controlled release build,
  never from mutable developer `node_modules`.
- Keep npm caches, credentials, pairing state, sessions, logs, databases, and
  `.env` out of release inputs and staging.

## Non-goals

- Do not download Node.js or bridge dependencies on the customer machine.
- Do not add a second WhatsApp implementation or route WhatsApp through port
  8787.
- Do not change open, allowlist, pairing, bot, self-chat, group, prompt, policy,
  or toolset semantics.
- Do not automatically enable or pre-pair WhatsApp in a new installation.

## Architecture

The release build resolves a specific Node.js 22 Windows archive from the
official Node 22 release channel, verifies it against authoritative release
metadata, and records the resolved version and checksum in the immutable
artifact manifest. It places the extracted portable runtime in a dedicated
staged payload, then separately runs `npm ci` from the
WhatsApp bridge lock file in a clean build directory and stages that resulting
dependency tree with the bridge package manifests. The generic Hermes copy
filter continues to exclude arbitrary package manifests and developer
`node_modules`; only these explicitly built WhatsApp assets are added.

Installation copies portable Node to the product-managed runtime and exposes it
to Hermes through the existing managed-Node resolution contract. Before the
existing onboarding process starts the bridge, it verifies `node --version`,
`npm --version`, and the required bridge modules, then starts the unchanged QR
pairing process without running npm. Later gateway starts reuse the same
assets.

Upgrade staging is atomic and must not replace a healthy customer WhatsApp
session. Partial Node or dependency payloads must not be treated as healthy.

## Failure behavior

Failures remain local to WhatsApp onboarding and do not stop MacSoft Server,
the configuration backend, port 8787, or other platforms. The Server Desktop
receives an actionable error distinguishing:

- missing or damaged packaged Node runtime;
- unsupported Windows architecture;
- installation or filesystem failure;
- Node/npm verification failure;
- missing or damaged packaged bridge dependency.

Repairing or reinstalling the same release restores product runtime files while
preserving the customer-owned WhatsApp session under the existing upgrade
policy. No silent fallback to an unknown system Node/npm is allowed.

## Security and privacy

- During the release build, download Node only over HTTPS from `nodejs.org` and
  verify the archive using the official Node release checksum before staging.
- Resolve dependency versions during the release build through the committed
  bridge lock file and `npm ci`, not unconstrained `npm install`.
- Record the Node archive identity, checksum, and dependency lock hash in the
  staging manifest so the packaged runtime is auditable.
- Never stage or package WhatsApp `creds.json`, session directories, `.env`,
  pairing records, logs, or runtime databases.
- Customer-created session and dependency state stays in the installed
  customer's runtime and is preserved only by the existing upgrade policy.
- The official Baileys/WhatsApp Web integration remains an unofficial API with
  its existing account-restriction risk.

## Verification

Automated tests must prove:

1. Staging includes the audited Node 22 payload, bridge manifests, and only the
   clean dependency tree produced by the release build while excluding all
   runtime/private artifacts.
2. The build fails closed on a Node checksum mismatch, missing lock file,
   failed `npm ci`, or incomplete dependency output.
3. A staged installation resolves and verifies packaged Node/npm without a
   system Node or network access, and onboarding never invokes npm.
4. Missing or damaged packaged assets return actionable onboarding errors
   without enabling WhatsApp or damaging other runtime state.
5. Existing WhatsApp mode, access-control, toolset, AutoCount policy, and
   staging privacy tests remain green.

Release acceptance additionally requires a clean Windows installation with no
system Node/npm. With `nodejs.org` and the npm registry blocked but WhatsApp
network access available, it must complete QR pairing, one inbound message, one
LLM reply, and one permitted plugin-tool invocation. These manual checks must
not be reported as passed until performed on the actual installer.
