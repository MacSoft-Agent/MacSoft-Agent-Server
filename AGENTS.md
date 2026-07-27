# MacSoft Agent repository guidance

## Product and baseline

This repository is the authoritative MacSoft Agent product source. It combines
MacSoft Server, the pinned Hermes runtime, the Windows Host and Server Desktop,
AutoCount integration, packaging, and contracts used by the separately owned
Thin Client.

- Repository root: `C:\MacSoft-Agent-Github\MacSoft-Agent`
- Accepted baseline tag: `baseline-0.1.0-collaboration-safe-20260727`
- Accepted baseline commit: resolve the annotated tag above; see
  `docs/PROJECT_STATUS.md` for current evidence
- Product metadata authority: `product.json`
- Current status: `docs/PROJECT_STATUS.md`

Do not silently move the baseline tag or change version metadata. A different
clone path is valid for development, but scripts may impose a dedicated
packaging-clone name or other release preconditions.

## Component boundaries

- `server/`: Client-facing Server, pairing and device authorization, sessions,
  chat/SSE bridge, Skills, file/OCR contract, and AutoCount validation.
- `hermes/`: pinned upstream-derived AI runtime and Server Desktop. The
  `hermes/AGENTS.md` instructions also apply inside this subtree and take
  precedence for Hermes-specific work; do not replace that file.
- `product_runtime/`: Windows Host lifecycle and ownership of the AI Service,
  Server, configuration backend, installed paths, and protected resources.
- `hermes/plugins/` and `packaging/templates/protected/runtime/plugins/`:
  approved runtime integrations and protected product plugin templates,
  including AutoCount.
- `packaging/` and `scripts/`: staging, installer, maintenance, and release
  workflows.
- `docs/contracts/` and `docs/handoffs/`: cross-component contracts and work
  owned by the external Thin Client team. Do not edit the external Client as
  part of Server work unless the Product Owner explicitly expands scope.

Read `docs/README.md` for the documentation map. Use the architecture documents
for deeper design, the operations documents for runtime procedures, and
`docs/release/RELEASE_READINESS.md` for current release evidence.

## Authority order

When sources disagree, use this order:

1. current executable code, schemas, lock files, and version metadata;
2. tests that exercise current behavior;
3. current contracts and `docs/PROJECT_STATUS.md`;
4. architecture and operations guidance;
5. historical reports, handoffs, inventories, and conversation memory.

Historical paths, counts, versions, and staging names are evidence from their
time, not current authority. Report a material conflict instead of selecting
the convenient source.

## Roles

- The Product Owner decides customer-visible scope, release policy, accepted
  risk, public contracts, persistent-data/security policy, and baseline
  acceptance.
- A planner or reviewer challenges scope, evidence, dependencies, and risk.
- Codex investigates, designs, implements, verifies, and reports within the
  authorized work package, retaining implementation discretion where the
  repository establishes intent.

## Working rules

1. Establish repository identity, baseline, and working-tree state before work.
2. Inspect evidence before proposing a fix. Separate confirmed behavior,
   inference, and unknowns.
3. Preserve unrelated changes. Never use destructive Git cleanup to make a
   result appear clean.
4. Prefer the smallest coherent change that preserves component boundaries and
   existing contracts.
5. Treat an expected file list as guidance, not an absolute restriction. Report
   necessary adjacent changes and explain them.
6. Do not introduce a parallel runtime, new framework, new persistence owner,
   or Client/Server path when the established component can own the behavior.
7. Keep code, comments, UI text, commit messages, and Codex-facing repository
   documents in English unless a customer-facing localization explicitly
   requires another language.

### Task size

- Small: local, low-risk, no durable contract or persistence effect. Use a short
  investigate-change-verify report; a Work Package file is optional.
- Medium: crosses files or a component boundary, changes meaningful behavior,
  or needs several acceptance checks. Use the Work Package template.
- High risk: affects public APIs, authentication, persistent/customer data,
  installer/update behavior, runtime ownership, AutoCount writes, or release
  policy. Use a Work Package, explicit owner decisions, stronger verification,
  and independent review or real installed-product acceptance as appropriate.

### Unexpected findings and bugs

Classify every unexpected finding:

- in scope and required for the stated outcome: address it and record evidence;
- related but non-blocking: record it as remaining risk without expanding scope;
- unrelated: report it and leave it unchanged;
- blocking or authority-changing: stop the affected work and request a Product
  Owner decision.

Do not let an unrelated bug silently become the new objective.

Product Owner confirmation is required before changing customer-visible
behavior, public Client/Server contracts, persistent data or migrations,
security boundaries, installer/update/rollback policy, ports, product version,
Hermes baseline, AutoCount business rules, release acceptance, or uncertain
maintained work.

## Verification and reporting

Verification must be proportional to risk and include focused tests plus the
relevant component suite. Installer, service, networking, update, concurrency,
and customer-data changes may require real installed-product acceptance because
unit tests alone cannot prove them. Never report an unperformed manual test as
passed.

Before a release-related commit, inspect the exact diff, run
`scripts/check-repository-cleanliness.ps1`, run `git diff --check`, and confirm
that no generated, runtime, secret, or customer data was added. Record commands,
results, unrun tests, limitations, commits, and final Git state. Do not claim a
release is ready from partial evidence.
