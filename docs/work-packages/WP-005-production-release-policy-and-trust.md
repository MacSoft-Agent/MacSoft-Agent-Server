# WP-005 - Production Release Policy and Trust Decisions

## Status

- Independent technical review: passed
- Product Owner decision: policy accepted for merge
- Release state: implementation, trust provisioning, and production release remain gated

## Owner

- Product Owner: MacSoft Agent Repository Owner
- Execution owner: Codex
- Reviewer: Independent technical reviewer; security review required at later gates

## Baseline

- Repository: `https://github.com/MacSoft-Agent/MacSoft-Agent-Server`
- Starting branch/commit: `main` at
  `88782137d59c7c7eaf35905dec9faa5a0225f15d`
- Product: `0.1.0`, build `macsoft-agent-0.1.0-stable.20260722.1`
- Hermes: `v2026.7.7.2`,
  `79f12748022817a7c4f3fee747e45e9e6979214a`
- Starting tree: one excluded Product Owner change in
  `docs/development/FRESH_CLONE_SETUP.md`; it is not part of WP-005

## Objective

Establish the durable production release, distribution, signing, update trust,
recovery, and approval policy required before MacSoft Agent can provision
production trust or build updater-enabled customer releases.

## User or operational outcome

Future release work has an explicit order and authority boundary. A developer
cannot mistake merged updater source for production readiness, place signing
secrets in source/CI, publish a mutable installer, or build a production
activation package from unmerged or dirty code.

## Evidence and current behavior

Confirmed from current code and tests:

- WP-004 provides signed-manifest, HTTPS, version/channel, byte-count, SHA-256,
  Authenticode, user-confirmation, installer recovery, and health gates.
- `product.json` has null manifest URL/public key, so no update network request
  or installation is possible.
- Manifest schema v1 has no signed disabled state.
- Missing manifest and HTTP 404/410 fail closed with an update-check error.
- Update checking clears any previously trusted release before fetching.
- A policy test proves same-version returns `MacSoft Agent is up to date.`;
  the About UI has no focused same-version rendering test.
- The current trust metadata accepts one manifest public key.
- Same-version and downgrade installers are rejected.
- Build scripts require an exact merged commit, a clean dedicated packaging
  clone, locked dependencies, new staging, and artifact hash evidence.
- Production signing, timestamping, public distribution, trust provisioning,
  and real installed acceptance are not complete.

## Scope

- private source/public release separation;
- 0.1.1 activation and 0.1.2 update bootstrap;
- stable-only pilot controls;
- long-lived manifest and immutable artifact URL policy;
- Ed25519 and Authenticode custody requirements;
- release roles and approval authority;
- emergency withdrawal, forward-fix, and key-compromise policy;
- Production Trust Provisioning Gate;
- WP-006 through WP-009 boundaries;
- supported-environment placeholders and later-gate decisions.

## Non-scope

- creating the release repository or endpoint;
- generating keys or configuring certificates;
- changing `product.json`;
- enabling update configuration;
- building, signing, uploading, or publishing an installer or manifest;
- runtime, Server, installer, Client, Hermes, AutoCount, port, or schema changes;
- dependency remediation;
- WP-006 implementation.

## Policy decisions

### Distribution

`MacSoft-Agent/MacSoft-Agent-Server` remains private. Customer releases use a
separate public release-only HTTPS location, with
`MacSoft-Agent/MacSoft-Agent-Releases` as the current candidate. Customers
receive no repository credentials. Owner-authorized Release Distribution Setup
must establish endpoint ownership, administrator/write roles, anonymous
download, immutable naming, the stable locator, withdrawal, and audit evidence
before WP-006.

### Versions and channel

V1 uses `stable` only. Version 0.1.1 is the manually distributed
updater-activation build; 0.1.2 is the first real Settings -> About update.
Version 0.1.0 is not reused. Build IDs are unique and approved at the relevant
release gate.

Pilot control is the recorded distribution of 0.1.1, not repository access.
The stable manifest remains unavailable until 0.1.2 and its acceptance
environment are ready. Once published, every configured 0.1.1 installation can
discover 0.1.2.

### Locator and artifacts

The product embeds one long-lived stable locator. Proposed GitHub pattern:

```text
https://github.com/MacSoft-Agent/MacSoft-Agent-Releases/releases/latest/download/macsoft-agent-stable-manifest-v1.json
```

Only an approved non-draft stable release may control latest. Draft, test, and
incomplete pilot releases cannot become latest. The locator is anonymously
downloaded and verified before promotion.

Installer pattern:

```text
https://github.com/MacSoft-Agent/MacSoft-Agent-Releases/releases/download/v{version}/MacSoft-Agent-Setup-{version}.exe
```

Referenced installers are immutable and never overwritten.

### Publication and trust

Build exact merged source in a clean `MacSoft-Agent-Packaging` clone; sign and
timestamp; verify; calculate final bytes/SHA-256; upload; anonymously
re-download and verify; generate/sign the manifest from that installer; publish
the stable manifest last.

The Product Owner controls production Ed25519 material in an approved offline
or protected signing environment. Private keys and certificate secrets never
enter Git, product/customer state, ordinary CI, reports, public storage, or
developer/Codex workspaces. Test and production trust are separate.

Production installers require valid Authenticode and trusted timestamping.
Publisher/thumbprint pinning is defence in depth rather than a V1 blocker; its
residual risk belongs to Product Owner/security review.

### Data and recovery

Versions 0.1.1 and 0.1.2 keep the current data schema and introduce no
irreversible migration. Installation/health failure uses Program Files
rollback while ProgramData remains preserved. Post-install defects use a
higher-version forward fix, not remote downgrade or same-version replacement.

### Emergency behavior

Schema v1 cannot represent a signed disabled state. Emergency pause makes the
stable manifest asset unavailable (404/410) while retaining the release and
verifying latest cannot resolve to an older unintended release. This is
fail-closed and may display an update-check error.

The single-key V1 pilot uses a manually distributed trusted bridge installer
after manifest-key compromise. Overlapping-key support requires a separate
high-risk Work Package or explicit risk acceptance before broad deployment.

## Release roles

| Role | Responsibility | Authority |
| --- | --- | --- |
| Product Owner | product scope, version, risk, release | final go/no-go |
| Release Manager | exact build, signing ceremony, publication, evidence | no unilateral risk acceptance |
| Security Reviewer | key/certificate custody and dependency risk | security gate |
| Technical Reviewer | source, build, update and Hermes contracts | technical gate |
| Installed QA | clean/overlay/update/rollback/preservation | acceptance evidence |
| Thin Client Owner | reconnect, token, sessions, SSE and files | Client acceptance |
| AutoCount Reviewer | approved business-operation matrix | AutoCount acceptance |

One person must not unilaterally control production signing, publication, and
independent approval.

## Required now for WP-005 approval

- distribution direction;
- ownership/access authority;
- manifest locator and immutable artifact policy;
- key custody policy;
- Authenticode requirement;
- limited-pilot single-key risk acceptance;
- release approval roles.

## Later-gate Product Owner decisions

These do not block the WP-005 documentation PR:

- exact 0.1.1 and 0.1.2 Build IDs;
- certificate provider and timestamp endpoint;
- production operational custodian/signing personnel;
- public key ID/fingerprint after protected provisioning;
- pilot device list and readiness;
- supported Windows/network/AV/disk details;
- Thin Client acceptance build;
- AutoCount acceptance scope;
- final dependency-risk disposition;
- broad-deployment overlapping-key decision.

## Work sequence

1. WP-005 documentation approval.
2. Owner-authorized Release Distribution Setup.
3. WP-006 signing and artifact-finalization implementation.
4. Product Owner/Security-owned Production Trust Provisioning Gate.
5. WP-007 source PR for 0.1.1, then post-merge build/sign/manual distribution.
6. WP-008 source PR for 0.1.2, then stable-manifest and installed acceptance.
7. WP-009 pilot promotion, production go/no-go, publication, and withdrawal
   rehearsal.

WP-007 production artifacts are never built from a feature branch or dirty
workspace. Per-release immutable evidence is retained with the release or in
an approved internal audit location, not solely in a mutable control document.

## Acceptance criteria

1. Durable policy is recorded in ADR 0001.
2. Release-control status/evidence template contains no secret fields.
3. Current status/readiness documents describe WP-004 as implemented but
   production-disabled.
4. Manifest locator, immutable artifact and emergency behavior match code.
5. Immediate and later-gate owner decisions are separated.
6. WP-006 through WP-009 boundaries and distribution/trust gates are explicit.
7. No code, product metadata, installer, key, credential, release, or runtime
   artifact changes.
8. The owner-owned fresh-clone documentation change is excluded.
9. Documentation checks and independent review pass before merge.

## Verification plan

- inspect the exact documentation diff and tracked paths;
- run `git diff --check`;
- run repository cleanliness checks;
- scan changed files for secrets, runtime/customer data, and generated output;
- run documentation PR CI;
- obtain independent review before merge.

No installed-product acceptance belongs to this documentation-only Work
Package. Installed acceptance remains mandatory in WP-007/WP-008.

## Remaining risks

- release endpoint and production trust are not yet provisioned;
- GitHub latest behavior must be controlled operationally;
- 404/410 pause is fail-closed but not a friendly maintenance state;
- one public key remains the current runtime limit;
- signing-provider, supported-environment and dependency decisions remain at
  their later gates;
- source tests do not prove Windows update/rollback/customer-state behavior.

## Final status

Approved for merge. WP-005 completes when this documentation PR is merged.
The merge does not authorize Release Distribution Setup, production key
generation or provisioning, WP-006, or customer production release.

## Related commits and documents

- `docs/decisions/0001-production-release-and-update-trust.md`
- `docs/release/PRODUCTION_RELEASE_CONTROL.md`
- `docs/contracts/MACSOFT_UPDATE_CONTRACT.md`
- `docs/work-packages/WP-004-built-in-update.md`
- `docs/release/RELEASE_READINESS.md`
