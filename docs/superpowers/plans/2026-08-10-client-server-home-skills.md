# Client Read-Only Server Home Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every device Profile load the Server Desktop's native learned Skills, including supporting files, through Hermes' native Skill Loader while preventing every device run from mutating Server Home.

**Architecture:** Add `runtime/admin/skills` to each device Profile's `skills.external_dirs` so Hermes can index and progressively read complete Server Skills. Keep writes profile-local by adding a scope-aware hard guard in `skill_manage`; retain only Server Memory in the immutable per-session prompt snapshot.

**Tech Stack:** Python, FastAPI Server, pinned Hermes profile ContextVars, YAML profile configuration, unittest/pytest.

## Global Constraints

- Server Desktop remains the only writer to `runtime/admin`.
- Client AI runs remain scoped to `runtime/profiles/prof_*` and learn only there.
- Client still connects only to port 8787.
- Do not alter Hermes' native background-review learning logic.
- Complex Skills may contain `references/`, `templates/`, `scripts/`, and `assets/`.

---

### Task 1: Native shared Skill discovery

**Files:**
- Modify: `server/macsoft/profiles/registry.py`
- Test: `server/tests/test_device_profiles.py`

**Interfaces:**
- Consumes: Server runtime root from `_configured_hermes_home(config)`.
- Produces: device `config.yaml` containing `<runtime>/admin/skills` in `skills.external_dirs` and no legacy global learned directory.

- [ ] Write a failing test asserting new and existing Profiles receive the Server Home Skills directory.
- [ ] Run the focused Server test and confirm it fails because only `<runtime>/skills` is configured.
- [ ] Update Profile provisioning/migration to add `<runtime>/admin/skills` without changing local Profile Skills.
- [ ] Run the focused test and confirm it passes.

### Task 2: Device mutation hard boundary

**Files:**
- Modify: `hermes/tools/skill_manager_tool.py`
- Modify: `hermes/agent/skill_utils.py` only if an existing scope helper cannot identify the local root.
- Test: `hermes/tests/tools/test_macsoft_progress_skills.py`

**Interfaces:**
- Consumes: live profile-scoped Hermes Home and the discovered target Skill path.
- Produces: refusal for device Profile create/patch/edit/delete/write_file/remove_file operations whose target is outside the device Profile's own `skills` tree; Server admin scope remains writable.

- [ ] Write failing tests proving a device can view a multi-file Server Skill but cannot patch or write its supporting files.
- [ ] Run the focused Hermes test and confirm the unauthorized mutation currently succeeds or reaches the external target.
- [ ] Add the smallest scope-aware write guard to the existing `skill_manage` dispatcher.
- [ ] Run focused tests and confirm device-local creation/patch still succeeds and Server external mutation is refused.

### Task 3: Memory-only immutable Client snapshots

**Files:**
- Modify: `server/macsoft/server_home.py`
- Modify: `server/macsoft/chat/capability_policy.py`
- Test: `server/tests/test_server_home.py`
- Test: `server/tests/test_capability_policy.py`

**Interfaces:**
- Consumes: Server `USER.md` and `MEMORY.md`.
- Produces: immutable per-device-session Memory snapshots without concatenated Skill text; corrected read-only system instruction.

- [ ] Write failing tests proving Skills are absent from the prompt snapshot while Server Memory remains present, and the prompt says the snapshot does not grant write authority.
- [ ] Run focused tests and observe the old Skill concatenation and incorrect sentence fail.
- [ ] Restrict snapshot assembly to Server Memory and correct the protected instruction.
- [ ] Run focused tests and confirm they pass.

### Task 4: End-to-end regression and commit

**Files:**
- Verify all changed files and repository state.

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: evidence that native complex Skill loading and isolation coexist.

- [ ] Run focused Server and Hermes tests.
- [ ] Run the complete Server suite, Desktop typecheck/UI suite, and relevant Hermes profile/Skill suites.
- [ ] Run `git diff --check` and `scripts/check-repository-cleanliness.ps1`.
- [ ] Inspect the exact diff, then commit only this work package.
