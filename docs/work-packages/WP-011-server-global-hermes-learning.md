# WP-011 - Server-global Hermes learning

## Status

Implemented in working tree; installed-product acceptance pending

## Owner

- Product Owner: User (approved 2026-08-06)
- Execution owner: Codex
- Reviewer: Independent review required before integration

## Baseline

- Repository/branch: `C:\MacSoft\server\MacSoft-Agent`,
  `update/add-new-module-in-server`
- Starting commit: `1f2fa5b`
- Accepted product baseline remains
  `baseline-0.1.0-collaboration-safe-20260727`
- Starting worktree contains the separately requested dashboard HTML contract
  fix in `server/macsoft/gateway/routes_chat.py` and its focused test. It must
  be preserved and is not part of this work package.

## Objective

Restore the original single-home Hermes self-improvement experience for a
Server-owned global learning scope. Only an authenticated Server Desktop
Global Training session may invoke that scope. Approved global Memory and
Progress Skills are read-only inputs to every paired Client profile.

MacSoft controls scope, authorization, approval and audit. Hermes continues to
own the learning algorithm and native `native_after_run`, Background Review,
Memory Manager, Skill Manager, usage, Curator, Journey and backup behavior.

## Product decisions

- Server Desktop exposes a dedicated Global Training entry. Ordinary Admin
  chat cannot enable global learning.
- Global learning is off by default and returns to off when the Desktop leaves
  the training session or the Server restarts.
- Native learning runs against an isolated Server-owned Global Hermes Home.
- Native changes are surfaced as proposals and require Admin approval before
  they enter the canonical Global Home.
- Client conversations never trigger Server-global learning. They only read
  approved global Memory and Progress Skills and continue writing solely to
  their device profile.
- Global review is instructed to retain only reusable procedures, validation,
  failure prevention, decision rules and workflow improvements. Personal or
  customer-specific material must yield `no_change`.

## Scope

- Provision native Admin and Global Hermes Homes under the Host-owned runtime
  root without copying secrets.
- Persist Global Training session identity, native-result proposals, versions
  and audit metadata in the Server database.
- Add an in-memory, restart-closed training enable gate bound to an
  authenticated Admin training session.
- Route Global Training runs to the Global Hermes Home and ordinary Admin runs
  away from it.
- Preserve the native Hermes learning lifecycle; proposal handling wraps its
  output and does not replace its reasoning or mutation implementation.
- Add Server Desktop Global Training navigation, persistent warning state,
  enable confirmation, proposal review and native state views.
- Load approved Global Memory and Global Progress Skills read-only in new
  paired-Client conversations.

## Non-scope

- Learning from, summarizing or promoting paired-Client conversations into the
  global scope.
- Allowing a Client to enable global learning or address an Admin/Global path.
- Replacing Hermes Memory, Background Review, Skill Manager, Curator, Journey,
  backup or rollback logic.
- Changing AutoCount business rules or granting a review process AutoCount
  write tools.

## Security and persistence boundaries

- Runtime paths are derived by the Host/Server. Request bodies never carry a
  filesystem path or authorization-relevant profile identifier.
- Only the local authenticated Server Desktop Admin API can create and enable a
  Global Training session.
- The enable state is process-local and defaults closed after restart.
- Global review may mutate only a staging copy of Global native Memory,
  Server-owned `skills/learned/workflow-improvements` overlay, usage, Curator
  and Journey state. Approval promotes a
  validated diff into the canonical Global Home with snapshot and audit.
- Core, Company, Workflow, plugin-owned, Private and device Progress Skills are
  outside the Global Curator writable root.
- AutoCount write tools are absent from Global review execution.
- Workflow Improvement overlays are Server-owned files. Plugin, Company and
  original Workflow Skill directories remain read-only and are never patch
  targets. Targeted sessions enforce their category in the Hermes Skill
  Manager; General sessions permit one classified Workflow overlay or one
  General Memory change, never a cross-target combined change.

## Acceptance criteria

1. Ordinary Server Desktop chat cannot change canonical Global Memory, Skills,
   usage or Curator state.
2. A Global Training run requires an authenticated training session plus the
   process-local enable gate; forged session IDs or request fields fail closed.
3. A successful enabled run invokes the unchanged native Hermes learning
   lifecycle against the global staging Home and can produce `no_change`,
   Memory, Skill or Curator changes.
4. Unapproved changes are invisible to paired Clients. Approval is atomic,
   audited, versioned and recoverable.
5. New Client conversations load approved Global Memory and Skills read-only;
   existing prompt-cached conversations are not mutated mid-session.
6. Client runs cannot modify Global state or trigger Global Background Review.
7. Global review cannot use AutoCount writes or modify protected/device roots.
8. Server restart disables Global Training while retaining canonical Global
   state, proposals, audit and backups.

## Verification plan

- Focused Server database, provisioning, Admin authorization and restart-gate
  tests.
- Hermes scope, unchanged native lifecycle, tool denial and canonical/staging
  isolation tests.
- Parallel device/global isolation and read-only inheritance tests.
- Desktop component/contract tests for navigation, warning, confirmation and
  proposal actions.
- Server, affected Hermes, Host/packaging and Desktop focused regression suites.
- Real installed-product acceptance remains required before release approval.

## Implementation evidence (2026-08-07)

- Server provisions separate native `runtime/admin`, `runtime/global`, and
  session-scoped `runtime/global-staging/<admin-session>` homes. Secrets are
  not copied into any scoped configuration.
- Global Training runs carry an internal Admin scope to Hermes. The existing
  ContextVar-based profile runtime scope creates and runs the native Agent in
  that staging home; native `native_after_run` writes its lifecycle marker
  there. A non-blocking Server observer snapshots only completed native output
  as a pending proposal.
- The Desktop lease renews every 10 seconds and expires after 30 seconds if
  Desktop disappears, so a closed or crashed Desktop fails closed even if the
  Server itself remains running. Switching away from the session disables the
  gate immediately; Server restart always starts with it disabled.
- Approval validates hashes, snapshots the old canonical mutable state, applies
  the approved snapshot atomically per file and audits/version-records it.
  Restore is linear and refuses to overwrite a newer canonical version.
- Focused verification passed:

  - 36 Server tests covering provisioning, gating, automatic native proposal
    capture, approval/rejection/restore, policy ordering, device profiles and
    existing Admin interrupt behavior.
  - 10 Hermes gateway tests covering concurrent scope isolation, global staging
    Server-owned overlay-only write access, Targeted category rejection,
    cross-scope rejection and non-blocking learning.
  - Desktop `typecheck`, `typecheck:release`, and the focused Admin chat Hook
    test (8 assertions) passed.
