# WP-010 - Device-profile Hermes self-improvement

## Status

Implementing

## Owner

- Product Owner: User (approved 2026-08-05)
- Execution owner: Codex
- Reviewer: Independent review required before integration

## Baseline

- Repository/branch: `C:\MacSoft\server\MacSoft-Agent`, `update/add-new-module-in-server`
- Starting commit: `c3c251c`
- Product and Hermes versions: MacSoft Agent `0.1.5`; Hermes `v2026.7.7.2` at `79f12748022817a7c4f3fee747e45e9e6979214a`
- Starting working-tree state: clean

## Objective

Make each paired Client device own one isolated, Server-hosted Hermes profile
whose native Memory, agent-created Progress Skills, usage metadata, Curator
state, and learning graph can evolve without affecting any other device.

## User or operational outcome

A paired Client receives a persistent device-specific MacSoft Agent that
learns its preferences and repeatable workflows. Client-uploaded Private Skills
remain immutable to Hermes and the Curator. The Client continues to use only
the MacSoft Server API on port 8787.

## Evidence and current behavior

- Server authenticates a `device_token` plus `X-Device-Id`; the current Client
  persists that identity in its Electron user-data store.
- Server sessions and Client Skills already include device ownership, but all
  Client chat currently targets one shared Hermes `HERMES_HOME` through fixed
  API Service port 8642.
- Hermes supplies profile home overrides via `ContextVar`, native Memory,
  background review, agent-created Skills, usage tracking, Curator, and
  learning graph. Its API server does not yet route a MacSoft request to a
  device profile.
- Existing `/api/client/skills` are device-owned, request-scoped Private Skills
  stored in MacSoft SQLite. They are not Curator-managed Hermes Skills.

## Scope

- Device-to-profile registry and safe profile provisioning under MacSoft-owned
  writable runtime state.
- Profile-scoped Hermes API execution with one shared internal API Server as
  the initial runtime model.
- Device-scoped native Memory, Progress Skills, usage, Curator, and Journey.
- Separate immutable Private Skills from Curator-writable Progress Skills.
- Audited, recoverable Progress-Skill mutation path.
- Authenticated Server learning APIs required by the existing Client learning
  page, followed by Client contract alignment in its separate repository.
- Focused regression, concurrency-isolation, and installed-product acceptance
  evidence.

## Non-scope

- Cross-device or user-level profile sharing and migration.
- Client-side LLM, Hermes runtime, HERMES_HOME, Curator, or AutoCount runtime.
- Tenant/organization multi-tenancy beyond preserving a future-compatible
  schema boundary.
- Unconditional scheduled Curator runs.

## Architectural boundaries

- The Client uses only Server port 8787; Hermes ports 8642/8643 and Host port
  8766 remain internal.
- Server owns authentication, profile resolution, authorization, audit, and
  AutoCount policy. Hermes owns native agent, Memory, Skill, and Curator logic.
- Program Files stays immutable; per-device profile state resides in ProgramData.
- A device Profile is resolved exclusively from authenticated device identity;
  no client path or profile ID is an authorization input.
- Private Skills are user-managed, read-only to agent/Curator. Progress Skills
  are agent-created and only those may be changed by native learning.
- Core, Company, Workflow, plugin-owned Skills, tool policy, approvals, and
  AutoCount authority cannot be modified or expanded by personal learning.

## Proposed direction

Introduce a 1:1 `device_id` to `profile_id` registry. Resolve a canonical
profile home below ProgramData, then pass only the opaque profile identifier
over the Server-to-Hermes boundary. Hermes validates and scopes the request by
using its context-local `HERMES_HOME` override. Start with the shared API Server
and require high-concurrency cross-profile isolation tests. A per-profile worker
pool is a contingency, not the initial architecture.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Profile context or module cache leaks across concurrent runs | Customer data disclosure/corruption | Context propagation audit and repeated A/B concurrent isolation tests; switch to worker pool if unsound |
| Learning tools modify protected Skills or invoke AutoCount | Security/business control violation | Separate roots, tool dispatch allowlist, Server mutation boundary, negative tests |
| Profile schema changes lose customer learning data | Persistent-data loss | Versioned provisioning, atomic writes, backups, migration tests, installed upgrade acceptance |
| Client/API mismatch | Learning UI unusable | Versioned Server contract, focused Client integration tests, preserve existing chat APIs |
| Background work causes unexpected operational actions | Safety/reliability issue | Successful-run-only trigger, no scheduled run in v1, review tool restrictions, explicit audit |

## Product Owner decisions required

Approved: Profile ownership is device-level; a new computer or Client reset
gets a new profile. Private Skills are immutable to Hermes and Curator.
Approved: default learning mode is native-after-run, with successful-run-only
background review. Per-profile worker processes are a fallback only if the
single-process isolation suite cannot pass.

## Acceptance criteria

1. An authenticated paired device resolves exactly one provisioned profile;
   no request can select another device's profile or filesystem path.
2. Concurrent device profiles cannot observe or mutate each other's Memory,
   Progress Skills, usage, Curator state, session data, or learning events.
3. Private Skills are loadable but cannot be changed, archived, consolidated,
   or deleted by agent or Curator paths.
4. Native learning updates only the current profile's Memory and Progress
   Skills after a completed run, without delaying the Client response.
5. Background review cannot gain AutoCount write access or modify protected
   Skill roots/policy.
6. All Progress-Skill mutations are atomic, versioned, audited, and recoverable.
7. The Client learning APIs authenticate by the existing device token/header
   and do not expose profile paths, Hermes files, credentials, or raw state.
8. Existing Client chat, SSE, file, voice, and AutoCount flows retain their
   contracts; upgrades retain ProgramData profile state.

## Verification plan

- Focused automated checks: Server database/profile tests, Hermes API routing
  tests, Memory/Skill/Curator negative authorization tests, and repeated
  parallel-device isolation tests.
- Component/regression checks: Server test suite, Hermes affected API/agent
  tests, Client learning API tests after its contract update.
- Manual or installed-product acceptance: paired Client A/B test, Server and
  Hermes restart persistence, profile reset behavior, and packaged clean/overlay
  installation tests.
- Independent review required: yes, before completion due to security,
  persistent-data, public-contract, and runtime-lifecycle changes.

## Implementation result

Implemented in the Server, pinned Hermes runtime, Windows Host, packaging
template, and separately owned Client working tree.

- `device_profiles` provides one opaque `prof_<32 hex>` Profile per device,
  lifecycle status, schema version and timestamps. Pairing provisions it;
  revocation freezes it; restart and overlay upgrade retain it.
- Hermes and Server share the Host-owned `runtime/profiles` root. Each Profile
  has native memories, learned/private skill directories, sessions, logs,
  curator, and backup directories. Profile config copies behavioral settings
  without provider credentials.
- Client chat still calls Server `:8787`; Server internally uses Hermes Runs
  and binds run/device/profile/session/completion/learning state. Runs,
  events, approvals, and stop actions enforce the immutable Profile binding.
- Completed native runs use native-after-run background learning. Response SSE
  finishes before review; failed and cancelled runs are `skipped`; background
  review is memory/skills-only and therefore cannot write through AutoCount.
- Private Skills remain device-owned Server request instructions. Progress
  Skills live only in `skills/learned`; shared/protected names cannot be
  shadowed; Curator and profile actions require agent provenance.
- Native mutation wrappers supply profile/process locks, snapshots, atomic
  audit events, exact learned-tree hashes, cache clearing and rollback. Server
  imports run-linked native audit into its immutable event/audit tables.
- The authenticated `/api/profile/*` contract, safe Journey/Memory summaries,
  Curator preview/approval, pin/restore, backup/rollback, and Client learning
  UI are implemented. The full contract is recorded in
  `docs/contracts/MACSOFT_DEVICE_PROFILE_LEARNING_API.md`.

## Verification evidence

- Server: `python -m unittest discover -s server/tests -v` (125 passed).
- Hermes official parallel runner: Profile API, Progress Skill and multiplex
  authorization files (17 passed), plus direct Learning Graph/Journey tests
  (25 passed). This includes concurrent A/B
  profile memory/skill/usage/Curator state isolation, profile-bound Run
  controls, native review non-blocking lifecycle, AutoCount hard denial,
  audit hash/backup, archive/restore/rollback, and Private Skill protection.
- Windows Host/packaging/upgrade: `python -m unittest discover
  product_runtime/tests -v` (62 passed), including profile-tree byte-for-byte
  overlay upgrade preservation and Host propagation of `MACSOFT_PROFILE_ROOT`.
- Client: Desktop `typecheck` passed and Learning API/component tests passed
  (8 passed). Full Client UI suite currently has 45 pre-existing unrelated
  failures (attachments test-id, gateway reconnect timing, Windows path
  expectations and other non-Learning areas); this work does not change them.
- `git diff --check` passed against the final exact diff.

## Unexpected findings

- In scope: existing Hermes native profiles/multiplexing provides a context-local
  `HERMES_HOME` seam, but its API Server needs an explicit MacSoft profile
  routing boundary before it can be used safely.

## Remaining risks

- A real installed Windows overlay upgrade and paired A/B Client session still
  need operator execution before release acceptance. Automated Host/upgrade
  simulation is passing, but it intentionally does not overwrite a live
  customer installation.
- Full Client UI baseline remains red for unrelated existing failures; the
  focused Learning suite and TypeScript check are green.

## Final status

Source implementation and automated verification complete. Awaiting the
required independent review and real installed-product acceptance; this is not
release approval.

## Related commits and documents

- Commits: pending
- Decision records: `docs/decisions/0001-production-release-and-update-trust.md`
- Contracts/status/release evidence: `docs/contracts/MACSOFT_HERMES_COMPATIBILITY_CONTRACT.md`, `docs/PROJECT_STATUS.md`
