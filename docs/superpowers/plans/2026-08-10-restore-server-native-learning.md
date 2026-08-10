# Restore Server Native Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove MacSoft Global Training and make ordinary Server Desktop chat use Hermes' native default learning while device Client learning remains isolated.

**Architecture:** Port 8787 remains the Client trust boundary and forwards one profile-scoped run to the internal Hermes API on port 8642. Ordinary Desktop Admin chat is scoped to the Server Home and uses unmodified Hermes background review. Client runs read a stable, read-only snapshot of shareable Server knowledge and learn only inside their device Profile.

**Tech Stack:** Python/FastAPI, Hermes aiohttp API, React/TypeScript/Electron, SQLite, pytest/unittest, Vitest.

## Global Constraints

- Thin Clients connect only to port 8787; port 8642 remains internal.
- Client conversations never invoke Server Home `native_after_run`.
- Server Desktop conversations never enter a device Profile Home.
- Preserve device Profile Memory, Skills, usage, Curator, Journey, and learning APIs.
- Preserve Private/Core/Company/Workflow and AutoCount authorization boundaries.
- Do not customize Hermes' native background-review algorithm or prompts.
- Do not destructively drop legacy Global Learning tables or delete runtime data.
- Preserve unrelated working-tree changes.

---

### Task 1: Remove Global Training from Desktop

**Files:**
- Modify: `hermes/apps/desktop/src/app/desktop-controller.tsx`
- Modify: `hermes/apps/desktop/src/app/chat/index.tsx`
- Modify: `hermes/apps/desktop/src/app/chat/sidebar/index.tsx`
- Modify: `hermes/apps/desktop/src/app/chat/hooks/use-macsoft-admin-chat.ts`
- Modify: `hermes/apps/desktop/electron/macsoft-desktop-admin-chat-client.ts`
- Modify: `hermes/apps/desktop/electron/main.ts`
- Modify: `hermes/apps/desktop/electron/preload.ts`
- Modify: `hermes/apps/desktop/src/global.d.ts`
- Delete: `hermes/apps/desktop/src/app/chat/sidebar/global-training-help.tsx`
- Delete: `hermes/apps/desktop/src/app/chat/sidebar/global-training-help.test.tsx`
- Test: Desktop hook, chat, sidebar, and Electron tests under `hermes/apps/desktop/src`

**Interfaces:**
- Consumes: existing ordinary Admin session IPC and REST methods.
- Produces: a Desktop surface with Messaging only and no Global Training transport types.

- [ ] Write tests asserting no Global Training navigation/control is rendered and ordinary Admin sessions remain usable.
- [ ] Run the focused Vitest files and confirm they fail against the existing UI.
- [ ] Remove Global Training state, callbacks, IPC methods, types, and components without changing ordinary Messaging.
- [ ] Run focused tests, Desktop typecheck, and Electron syntax/type checks.
- [ ] Commit only the Desktop removal files.

### Task 2: Collapse Admin Sessions onto the Server Hermes Home

**Files:**
- Modify: `server/macsoft/admin/session_store.py`
- Modify: `server/macsoft/gateway/routes_admin.py`
- Modify: `server/macsoft/chat/hermes_client.py`
- Modify: `server/macsoft/server.py`
- Modify: `server/macsoft/db.py`
- Modify: `server/tests/test_global_learning.py` or replace it with focused native Server learning tests
- Test: existing Server Admin chat tests

**Interfaces:**
- Consumes: `request_hermes_reply(..., admin_scope="admin")` and existing `admin_sessions` rows.
- Produces: newly created sessions are always `chat`; existing legacy `global_training` rows cannot enable or invoke training routes; Global Learning endpoints are absent.

- [ ] Write failing route tests asserting Global Learning endpoints return 404 and ordinary Admin chat sends `X-MacSoft-Admin-Scope: admin`.
- [ ] Run the focused Server tests and confirm the new assertions fail.
- [ ] Remove Global Learning route models/handlers, gate initialization, proposal imports, and session branching; retain legacy columns/tables as unused compatibility data.
- [ ] Restrict new Admin sessions to `session_type="chat"` and make legacy rows read-only/non-runnable or normalize them at the response boundary.
- [ ] Run focused Admin route, database migration, and Server application tests.
- [ ] Commit only the Server Admin collapse files.

### Task 3: Restore Native Hermes Review for Server Desktop

**Files:**
- Modify: `hermes/gateway/platforms/api_server.py`
- Modify: `hermes/hermes_constants.py`
- Modify: `hermes/tools/skill_manager_tool.py`
- Modify: `hermes/tests/gateway/test_macsoft_profile_api.py`
- Modify: `hermes/tests/tools/test_macsoft_progress_skills.py`

**Interfaces:**
- Consumes: `X-MacSoft-Admin-Scope: admin`, `_profile_runtime_scope`, and native agent `native_after_run` behavior.
- Produces: Admin runs resolve only to `<runtime>/admin` (the Server Home), retain native review prompt class defaults, and use the normal Server Home skill root.

- [ ] Write failing tests proving global-training scopes are rejected and Admin agents do not receive `_MEMORY_REVIEW_PROMPT`, `_SKILL_REVIEW_PROMPT`, or `_COMBINED_REVIEW_PROMPT` overrides.
- [ ] Run focused Hermes tests with `scripts/run_tests.sh` and confirm failure.
- [ ] Delete custom Global review constants/configuration, staging scope resolution, workflow overlay writable-root logic, and Global Training-specific skill-manager policy.
- [ ] Preserve profile-scoped mutation protections for device learned Skills and protected source Skills.
- [ ] Run focused API, background-review, skill-manager, and profile isolation tests.
- [ ] Commit only the Hermes native-review restoration files.

### Task 4: Provision One Server Home and Expose Read-Only Shared Context

**Files:**
- Replace responsibility in: `server/macsoft/global_learning/homes.py` with a focused Server Home module, or move retained functions to `server/macsoft/server_home.py`
- Modify: `server/macsoft/gateway/routes_chat.py`
- Modify: `server/macsoft/chat/capability_policy.py`
- Modify: `server/macsoft/profiles/registry.py`
- Modify: `server/tests/test_capability_policy.py`
- Modify: `server/tests/test_device_profiles.py`
- Add/modify tests for Server Home provisioning and Client read-only inheritance

**Interfaces:**
- Produces: `ensure_server_home(config) -> Path` and `read_shareable_server_context(config) -> str | None`.
- Consumes: the Server Home `memories/USER.md`, `memories/MEMORY.md`, and native learned Skill metadata/content through a bounded read-only snapshot.

- [ ] Write failing tests for one `<runtime>/admin` Server Home, native directory layout, bounded shared context, protected ordering, and no Server Home mutations after a Client run.
- [ ] Run focused Server tests and confirm failure.
- [ ] Provision only the Server Home; stop creating `global`, `global-staging`, workflow indexes, and overlay directories.
- [ ] Build a bounded read-only shared context from Server Memory and eligible learned Skills, excluding archived/private/unsafe paths and credentials.
- [ ] Snapshot the shared layer at new Client-session context construction and insert it after protected Workflow instructions but before device guidance.
- [ ] Run Client chat, capability policy, Profile isolation, private Skill, and session reuse tests.
- [ ] Commit only Server Home and Client read-only inheritance files.

### Task 5: Remove Dead Global Learning Code and Verify End to End

**Files:**
- Delete: `server/macsoft/global_learning/gate.py`
- Delete: `server/macsoft/global_learning/proposals.py`
- Delete or replace: `server/macsoft/global_learning/__init__.py`
- Delete obsolete Global Training tests and documents only when they describe executable behavior; retain historical work-package evidence with a superseded marker.
- Modify: relevant packaging/config documentation if it names `global` or `global-staging` as active runtime homes.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: no executable Global Training code or UI, while legacy persistence remains non-destructively readable by old binaries.

- [ ] Use `rg` to enumerate every executable Global Training symbol and add a cleanliness assertion/test for prohibited UI/API symbols.
- [ ] Delete dead modules/imports and mark WP-011 superseded by the native Server learning design.
- [ ] Run `scripts/run_tests.sh` for the affected Hermes suites, the relevant Server suite, Desktop UI suite, Desktop typecheck, product-runtime tests, and repository cleanliness checks.
- [ ] Run `git diff --check` and inspect the exact diff for generated/runtime/secret/customer data.
- [ ] Verify with tests that `:8787 -> :8642` remains the only Client AI path, Server Desktop native learning persists across restart, Client A/B remain isolated, and Client traffic cannot mutate Server Home.
- [ ] Commit the cleanup and verification evidence without staging unrelated worktree changes.
