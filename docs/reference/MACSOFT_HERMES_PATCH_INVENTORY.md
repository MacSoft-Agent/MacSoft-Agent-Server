# MacSoft Hermes Patch Inventory

Status: WP-01 Batch 1 comparison evidence

Comparison date: 2026-07-28

## Comparison source and method

| Item | Value |
| --- | --- |
| Upstream repository | `https://github.com/NousResearch/hermes-agent.git` |
| Upstream tag recorded by MacSoft | `v2026.7.7.2` |
| Upstream commit checked out | `79f12748022817a7c4f3fee747e45e9e6979214a` |
| MacSoft tree | `hermes/` at starting MacSoft commit `1816fbf53b17c22e9e1220c7da05dd47537ed1c5` |
| Comparison | Path set and SHA-256 content comparison of files tracked by each Git tree |
| Result | 31 added, 75 modified, 30 deleted paths |

The upstream commit was cloned to a separate temporary directory. The MacSoft
repository was not given an upstream remote and its runtime pin was not
changed.

Excluded from comparison:

- `.git` metadata;
- ignored virtual environments, `node_modules`, caches, build output, and
  runtime/customer state;
- files not tracked by either compared Git tree.

The counts describe source divergence, not 136 independent features. Related
paths are grouped below by product behavior and upgrade risk.

## Patch groups

### P1. Configuration-only Hermes backend

**Files**

- `hermes_cli/main.py`
- `hermes_cli/web_server.py`

**Reason and protected behavior**

MacSoft reuses Hermes model/provider/auth/configuration handlers without
exposing a second Agent, PTY, session, filesystem, Tool, or Skill execution
surface. Gateway warming and PTY initialization are disabled in this mode.

**Tests**

- Desktop backend readiness and dashboard-token tests.
- Hermes web server model/provider/config/auth tests.
- Product runtime Host tests.

**Conflict risk:** High. Both files are central upstream entry points.

**Placement**

The launch flag and boundary currently must remain in the Hermes subtree.
Batch 2 should keep the patch narrow. A future upstream-supported
configuration-only mode could replace it; speculative refactoring is not
justified now.

### P2. Host-managed Desktop runtime and product identity

**Added modules**

- `apps/desktop/electron/macsoft-host-client.ts`
- `apps/desktop/electron/macsoft-product.ts`
- `apps/desktop/electron/macsoft-product-initializer.ts`
- corresponding tests

**Modified integration files**

- `apps/desktop/electron/main.ts`
- `apps/desktop/electron/preload.ts`
- `apps/desktop/electron/backend-ready.ts` and test
- `apps/desktop/electron/dashboard-token.ts` and test
- `apps/desktop/electron/hardening.ts`
- `apps/desktop/electron/update-relaunch.test.ts`

**Reason and protected behavior**

The customer Desktop connects to Host-managed services instead of spawning or
updating a user checkout of Hermes. Product metadata, Program Files/ProgramData
paths, Host control, Server settings, and customer runtime identity are exposed
through bounded Electron IPC.

**Tests**

- MacSoft Host, product, initializer, and customer-runtime Electron tests.
- Backend readiness and dashboard-token tests.
- Product runtime path, initialization, and Host suites.

**Conflict risk:** High for `main.ts` and `preload.ts`; low to medium for the
MacSoft-owned modules.

**Placement**

MacSoft-owned modules are already an adapter seam. They remain under the
Desktop subtree because Electron builds them directly. Upstream reconciliation
should avoid spreading product logic back into generic modules.

### P3. Server Desktop Admin chat

**Added modules**

- `apps/desktop/electron/macsoft-desktop-chat-client.ts`
- `apps/desktop/electron/macsoft-desktop-admin-chat-client.ts`
- `apps/desktop/src/app/chat/hooks/use-macsoft-admin-chat.ts`
- `apps/desktop/src/app/chat/hooks/use-macsoft-desktop-chat-status.ts`
- `apps/desktop/src/app/chat/macsoft-admin-route.ts`
- corresponding tests

**Modified areas**

- Desktop controller, chat view, sidebar, composer, and thread loading.
- Route resume, preview routing, prompt action, and message-stream hooks.
- Panes, projects, onboarding, and session-related stores/tests.

**Reason and protected behavior**

Customer runtime chat is owned by MacSoft Server Admin routes, not the native
Hermes gateway UI. It has separate session selection, SSE streaming,
interrupt, loading, and attachment constraints.

**Tests**

- MacSoft Admin client/hook/route/IPC tests.
- Server Admin chat and interrupt tests.
- Renderer session, streaming, composer, and pane regression tests.

**Conflict risk:** High. The patch intersects fast-changing upstream chat and
session state.

**Placement**

The clients and hook are appropriate MacSoft seams. Some integration in
controller, chat, composer, and session routing is unavoidable. Future work
may reduce the touched generic files only when a concrete upstream change
forces reconciliation.

### P4. Server, AutoCount, model, and network settings

**Added modules**

- `apps/desktop/electron/server-autocount-config.ts`
- `apps/desktop/src/app/settings/server-autocount-settings.tsx`
- `apps/desktop/src/app/settings/macsoft-model-settings.tsx`
- corresponding tests

**Modified areas**

- Settings index, constants, types, model settings, and global Desktop types.

**Reason and protected behavior**

MacSoft owns Server port/network display, pairing requests, AutoCount
configuration, AI Service diagnostics, and the selected runtime provider/model.
Writes are validated, backed up, and limited to known YAML/JSON fields.

**Tests**

- Server/AutoCount configuration and settings tests.
- MacSoft and generic model settings tests.

**Conflict risk:** Medium. Added modules are isolated; settings routing and
global types are shared upstream surfaces.

**Placement**

Keep product configuration logic in the MacSoft modules. Do not duplicate
Hermes provider/auth behavior; the configuration-only backend remains its
owner.

### P5. Customer update isolation

**Added modules**

- `apps/desktop/electron/macsoft-update-policy.ts`
- `apps/desktop/electron/macsoft-update-policy.test.ts`

**Modified files**

- `apps/desktop/src/app/settings/about-settings.tsx`
- `apps/desktop/src/store/updates.ts` and test
- `apps/desktop/electron/main.ts`

**Reason and protected behavior**

The upstream Git/rebuild update path is disabled for customer runtime.
MacSoft currently reports installer-managed updates and performs no background
polling or source modification.

**Tests**

- MacSoft update policy, update store, and Electron relaunch tests.

**Conflict risk:** High. Upstream update code remains present but must never be
selected for a customer installation.

**Placement**

The MacSoft policy module is the correct adapter boundary. Built-In Update is a
separate Work Package and must extend this boundary rather than reactivate the
upstream source updater.

### P6. Branding, navigation, and customer-visible surface

**Added modules**

- `apps/desktop/src/app/macsoft-customer-navigation.ts`
- `apps/desktop/src/components/macsoft-wordmark.tsx`
- related tests

**Modified areas**

- Desktop assets, public icons, `index.html`, brand mark, and intro content.
- Settings/customer navigation, i18n, styles, messaging, pet overlay, status
  bar, computer-use, and Skills presentation.
- Desktop package identity and installer metadata.

**Reason and protected behavior**

The installed application is MacSoft Agent and exposes the approved
customer-facing navigation rather than the full upstream Hermes product.

**Tests**

- Customer navigation/native UI and i18n tests.
- Messaging, Skills, pane-shell, and status tests.
- Package metadata/build contract tests.

**Conflict risk:** Medium, with recurring conflicts expected when upstream UI
navigation changes.

### P7. Attachment, streaming, and safety integration

**Modified areas**

- Chat composer attachments and submit behavior.
- Message stream gateway events and assistant streaming/tool status.
- File preview/read helpers and Desktop hardening.

**Reason and protected behavior**

MacSoft Admin chat currently rejects attachments while Thin Client attachments
flow through MacSoft Server. Renderer state must not accidentally use native
Hermes execution or mix session streams. File reads retain size/path
hardening.

**Tests**

- Composer attachment, streaming, preview/file, and hardening tests.
- Server file/OCR/chat boundary tests.

**Conflict risk:** High for chat streaming and composer changes; medium for
isolated hardening helpers.

### P8. Dependency and packaging alignment

**Modified files**

- `pyproject.toml`
- `uv.lock`
- `package-lock.json`
- `apps/desktop/package.json`
- `apps/desktop/vite.config.ts`
- `apps/desktop/src/test/setup.ts` (added)

**Reason and protected behavior**

MacSoft Server and Hermes share the bundled Python runtime and one locked
dependency graph. Desktop build/test ownership and product version metadata are
aligned with MacSoft packaging.

**Tests**

- Clean bootstrap and contributor verification.
- Desktop baseline.
- Product runtime packaging contracts and staging audit.

**Conflict risk:** High for lock files, medium for package configuration.

**Placement**

The shared lock is an intentional packaged-runtime constraint. It must be
regenerated and audited for each accepted Hermes candidate, never hand-merged
without dependency verification.

### P9. Removed upstream reference assets

The 30 deletions are five infographic images, fifteen concept-diagram examples,
two p5js reference/export files, seven web fonts, and one website user-story
data file.

These paths are not part of the packaged AI Service because staging excludes
docs, web, website, and optional development material. No current MacSoft
runtime import references were found.

**Conflict risk:** Low for product runtime; noisy for whole-tree upstream
comparisons.

Treat them as known repository exclusions, not product patches. Reassess only
if an upstream candidate makes one a build or runtime dependency.

## Complete MacSoft-added path list

```text
apps/desktop/electron/macsoft-admin-chat-ipc-contract.test.ts
apps/desktop/electron/macsoft-customer-runtime.test.ts
apps/desktop/electron/macsoft-desktop-admin-chat-client.test.ts
apps/desktop/electron/macsoft-desktop-admin-chat-client.ts
apps/desktop/electron/macsoft-desktop-chat-client.test.ts
apps/desktop/electron/macsoft-desktop-chat-client.ts
apps/desktop/electron/macsoft-host-client.test.ts
apps/desktop/electron/macsoft-host-client.ts
apps/desktop/electron/macsoft-product-initializer.test.ts
apps/desktop/electron/macsoft-product-initializer.ts
apps/desktop/electron/macsoft-product.test.ts
apps/desktop/electron/macsoft-product.ts
apps/desktop/electron/macsoft-update-policy.test.ts
apps/desktop/electron/macsoft-update-policy.ts
apps/desktop/electron/server-autocount-config.test.ts
apps/desktop/electron/server-autocount-config.ts
apps/desktop/src/app/chat/hooks/use-macsoft-admin-chat.test.ts
apps/desktop/src/app/chat/hooks/use-macsoft-admin-chat.ts
apps/desktop/src/app/chat/hooks/use-macsoft-desktop-chat-status.test.ts
apps/desktop/src/app/chat/hooks/use-macsoft-desktop-chat-status.ts
apps/desktop/src/app/chat/macsoft-admin-route.test.ts
apps/desktop/src/app/chat/macsoft-admin-route.ts
apps/desktop/src/app/chat/macsoft-native-ui-contract.test.ts
apps/desktop/src/app/macsoft-customer-navigation.test.ts
apps/desktop/src/app/macsoft-customer-navigation.ts
apps/desktop/src/app/settings/macsoft-model-settings.test.tsx
apps/desktop/src/app/settings/macsoft-model-settings.tsx
apps/desktop/src/app/settings/server-autocount-settings.test.tsx
apps/desktop/src/app/settings/server-autocount-settings.tsx
apps/desktop/src/components/macsoft-wordmark.tsx
apps/desktop/src/test/setup.ts
```

## Candidate reconciliation rule

For a new Hermes candidate:

1. compare the candidate with the accepted upstream commit;
2. replay this inventory against the candidate;
3. classify every conflict by patch group;
4. retain MacSoft-owned adapter modules unless the product requirement changed;
5. prove behavior through the mapped tests;
6. reject the candidate when a direct contract or product security boundary
   cannot be preserved without an approved design change.

This inventory is evidence for reconciliation. It is not permission to
mechanically reapply every old line.
