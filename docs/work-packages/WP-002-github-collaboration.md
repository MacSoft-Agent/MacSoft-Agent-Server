# WP-002 - GitHub multi-developer collaboration

## Status

Complete - awaiting Product Owner acceptance

## Owner

- Product Owner: MacSoft Agent Product Owner
- Execution owner: Codex
- Reviewer: Codex independent final review

## Baseline

- Repository/branch: `C:\MacSoft-Agent-Github\MacSoft-Agent` /
  `debug/skill-runtime-c6afbc9`
- Starting commit: `a41ca104e815aabdce6883be058a92126b5889d1`
- Product/Hermes: `0.1.0` /
  `macsoft-agent-0.1.0-stable.20260722.1` / `v2026.7.7.2`
- Starting working-tree state: clean

## Objective

Make a GitHub clone sufficient for a new developer to restore dependencies,
understand repository authority and boundaries, run the verified baseline,
create a scoped branch, and submit a reviewable pull request without private
chat history.

## User or operational outcome

Contributors receive one concise entry point, deterministic setup and
verification commands, a practical pull-request contract, and CI signals that
match the current repository baseline.

## Evidence and current behavior

- GitHub `main` currently points to `c6afbc96c4b340b69fa06a96ae1e44a9d4ab5a7f`.
- The approved Stage 6 starting HEAD is seven commits ahead and is not
  published.
- The remote has no published baseline tag.
- The root had no `.github`, pull-request template, CI workflow, CODEOWNERS, or
  MacSoft-specific `CONTRIBUTING.md`.
- Locked inputs exist for Hermes Python, Server Python, and the root Node
  workspace.
- The full Desktop lint command currently reports existing baseline debt and
  cannot be made a required green gate in this collaboration-only task.
- No `.gitmodules`, tracked LFS objects, or root GitHub configuration existed.

## Scope

- concise contributor, branch, review, and ownership guidance
- deterministic Windows dependency bootstrap and contributor verification
- minimum GitHub Actions validation for repository hygiene, Windows baseline,
  and Linux Electron/Bash contracts
- one pull-request template
- fresh-clone, secrets/hygiene, remote-state, and collaboration evidence
- project and release status updates

## Non-scope

- Product behavior, APIs, schemas, installer, ports, lifecycle, AutoCount,
  updater, version, Build ID, Hermes pin, release build, or Release Candidate
- GitHub settings, collaborators, pushes, tags, releases, or branch protection
- broad lint remediation

## Architectural boundaries

Root guidance remains authoritative for MacSoft product work.
`hermes/AGENTS.md` remains authoritative for Hermes-specific work. CI verifies
source contracts only and must not claim installed-product, Thin Client,
provider, or live AutoCount acceptance.

## Proposed direction

1. Add one MacSoft contributor guide and one pull-request template.
2. Add Windows bootstrap/verification scripts based on committed lockfiles.
3. Add three diagnostic CI jobs: hygiene, Windows baseline, and Linux Electron
   contracts.
4. Document role-based ownership because no maintainer identities are
   established.
5. Prove the workflow from an isolated local clone of the approved local
   commit, while separately recording the older published remote state.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| CI claims more than it proves | False release confidence | Explicit source-only boundaries and separate release-readiness evidence |
| Fresh clone accidentally reuses local environments | Invalid reproducibility claim | Clone without local dependencies and restore only from locks |
| Misleading CODEOWNERS | Wrong or absent review | Do not create it until GitHub identities are owner-approved |
| Existing lint debt is hidden | Weak quality signal | Record exact failure and exclude it explicitly rather than marking optional |
| CI cost grows unnecessarily | Slow contribution loop | One full Windows baseline plus a narrow Linux Electron job |

## Product Owner decisions required

- Configure protected `main` settings after accepting this local result.
- Assign actual GitHub users or teams before a CODEOWNERS file is created.
- Decide whether to publish the local commits and whether to create a new
  accepted baseline tag.

## Acceptance criteria

The sixteen Stage 6 acceptance criteria in the authorized task apply without
creating separate Work Packages.

## Verification plan

- Validate scripts and workflow syntax/references.
- Restore dependencies in an isolated clone without copying local state.
- Run product-runtime, Server, Desktop, typecheck, Linux Bash, hygiene, and
  whitespace checks where the available platform permits.
- Inspect tracked paths, ignore controls, Git history path names, and likely
  secret patterns without printing secret contents.
- Perform a separate final diff and collaboration-usability review.

## Implementation result

The repository now has a compact MacSoft-specific collaboration surface:

- `CONTRIBUTING.md` defines authority, boundaries, locked dependency restore,
  verification, branch/PR workflow, approval triggers, forbidden files, and
  role-based review responsibilities.
- one pull-request template requires scope, risk, verification, and decision
  evidence;
- one GitHub Actions workflow provides repository hygiene, the complete
  Windows contributor baseline, and a narrow Ubuntu Electron job that executes
  the Bash syntax contracts;
- Windows bootstrap and verification scripts restore from committed locks and
  run the established product-runtime, Server, Desktop, and hygiene gates;
- contributor and worktree navigation no longer depends on a historical
  machine-specific development path;
- the AutoCount validator test now loads the tracked protected plugin template
  instead of an ignored runtime copy.

CODEOWNERS and issue templates were deliberately not created. No accurate
GitHub owner identities are established, and an additional issue form would
not materially improve the current lightweight workflow.

## Verification evidence

- Repository identity matched the approved start:
  `debug/skill-runtime-c6afbc9` at
  `a41ca104e815aabdce6883be058a92126b5889d1`, clean.
- Remote query:
  - default branch `main`
  - published HEAD `c6afbc96c4b340b69fa06a96ae1e44a9d4ab5a7f`
  - local start seven commits ahead
  - no remote tags
- PowerShell parser accepted both new scripts.
- PyYAML parsed the workflow and all referenced repository paths existed.
- Current checkout contributor verification passed:
  - product-runtime: 40
  - Server: 92
  - renderer/UI: 1,211
  - Electron: 373 passed, 4 explicit platform skips
  - packaging scripts: 9
  - Desktop typecheck: passed
- Isolated clone:
  - source commit `098d4997c1904c11281161fcc8e5d65aa49b7b9d`
  - clone used `--no-local --no-hardlinks` and Windows long-path support
  - Python was restored with uv 0.11.16 from `hermes/uv.lock`
  - Node was restored with `npm ci` from `hermes/package-lock.json`
  - no local venv, node_modules, ProgramData, database, auth, or runtime state
    was copied
  - all contributor verification counts above passed and Git remained clean
  - with Git Bash available, Electron recorded 375 passed, 2 Windows symlink
    skips, and both Bash syntax tests passed
- Repository cleanliness and `git diff --check` passed during implementation.

## Unexpected findings

- **In scope, corrected:** Windows checkout initially failed on three maintained
  Hermes documentation paths due the legacy path limit. Contributor clone
  instructions now set repository-local long-path support.
- **In scope, corrected:** one Server test depended on ignored
  `runtime/plugins/macsoft-autocount`; it now uses the tracked protected
  template and the fresh-clone Server suite passes.
- **Related security blocker:** historical `runtime/auth.json` contains four
  long, non-placeholder-looking string values. Commit
  `0aaf3fd19f61f654a3be036de25edff0f75f5abc`, which contained the file, is an
  ancestor of the published remote `main`. Values were not printed. Treat all
  credentials from that file as exposed.
- **Related dependency risk:** fresh `npm ci` reported 10 audit findings:
  1 low, 8 high, and 1 critical. No lockfile or product dependency was changed
  in this collaboration task.
- **Related non-blocking debt:** full Desktop lint reports 23 errors and
  240 warnings. It is documented as a non-passing baseline and was not hidden
  or repaired through unrelated production edits.

## Remaining risks

- Revoke/rotate credentials represented by historical `runtime/auth.json`
  before any further publication. Product Owner approval is required before
  history remediation or force-pushing rewritten history.
- The GitHub Actions workflow is locally parsed and its commands are verified,
  but cannot run on GitHub until the commits are safely published.
- Ubuntu-hosted execution remains unobserved locally; Git Bash executed both
  Bash syntax tests, and the Ubuntu job is designed to provide the durable
  Linux signal.
- Dependency audit and Desktop lint debt require separate scoped work.
- CODEOWNERS requires Product Owner-approved GitHub users or teams.

## Final status

All Stage 6 repository-preparation criteria are met locally. Remote
collaboration must not be activated until the historical credential exposure
is contained. This result changes no product behavior, API, version, Build ID,
Hermes baseline, accepted baseline tag, or GitHub setting.

## Related commits and documents

- Commits: `098d499` (collaboration/CI/fresh-clone correction); Stage 6
  evidence/status commit
- Decision records: none; no durable product architecture decision changed
- Status: `docs/PROJECT_STATUS.md`
- Release evidence: `docs/release/RELEASE_READINESS.md`
