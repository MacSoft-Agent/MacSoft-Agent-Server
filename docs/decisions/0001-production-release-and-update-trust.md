# 0001 - Production release and update trust

- Status: Proposed
- Date: 2026-07-29
- Owners/reviewers: Product Owner, independent technical reviewer, security reviewer
- Related Work Package: `WP-005-production-release-policy-and-trust.md`

## Context

MacSoft Agent combines a private Server source repository, a pinned
Hermes-derived runtime, a Windows Host and Desktop, an installer, and preserved
customer state. WP-004 implemented a fail-closed installer update path, but
`product.json` intentionally contains no production manifest URL or public key.

Production release requires a durable boundary between private source,
public customer artifacts, signing authority, mutable release selection, and
immutable installers. Unit tests do not replace real installed acceptance.

## Decision

### Source and distribution

`MacSoft-Agent/MacSoft-Agent-Server` remains private. Customer artifacts use a
separate public release-only HTTPS location. The current candidate is
`MacSoft-Agent/MacSoft-Agent-Releases`; its creation and configuration require
separate Product Owner authorization. Customer applications contain no GitHub
credentials.

### Bootstrap and channel

V1 uses only the `stable` channel:

- `0.1.1` is manually distributed to a recorded activation cohort;
- `0.1.2` is the first Settings -> About update candidate;
- version `0.1.0` is not reused;
- every release has a unique approved Build ID.

The public release location is not access control. The pilot is bounded by
restricting 0.1.1 distribution. Before 0.1.2 is ready, the stable manifest
locator remains unavailable and update checks fail closed. Publishing the
0.1.2 stable manifest makes it discoverable to every installed 0.1.1 build
configured with that locator.

### Locator and artifact immutability

The product embeds one long-lived stable manifest locator. For the current
GitHub Releases candidate, the proposed pattern is:

```text
https://github.com/MacSoft-Agent/MacSoft-Agent-Releases/releases/latest/download/macsoft-agent-stable-manifest-v1.json
```

Only an approved, non-draft stable release may control that locator. Draft,
test, and incomplete pilot releases must not become GitHub's latest release.

Installers use immutable version-specific locations:

```text
https://github.com/MacSoft-Agent/MacSoft-Agent-Releases/releases/download/v{version}/MacSoft-Agent-Setup-{version}.exe
```

An installer referenced by a signed manifest is never overwritten. Content
changes require a new version and Build ID.

### Trust and publication

The Product Owner controls the production Ed25519 private key. It exists only
in an approved offline or protected signing environment. It never enters Git,
the product, installer, ProgramData, ordinary CI secrets, developer/Codex
workspaces, reports, or public storage. Test and production keys are separate.
Only approved public verification keys enter source.

Production installers require valid Authenticode signing and trusted
timestamping. Publisher or certificate-thumbprint pinning is defence in depth,
not a V1 release blocker; the Product Owner and security reviewer own the
residual-risk decision.

Publication order is fixed:

1. build the exact merged commit in the dedicated clean packaging clone;
2. Authenticode-sign and timestamp;
3. verify the final signature;
4. calculate final bytes and SHA-256;
5. upload the immutable installer;
6. anonymously download and verify it;
7. create and Ed25519-sign the manifest from that exact installer;
8. publish the stable manifest last.

### Data and recovery

Versions 0.1.1 and 0.1.2 keep the current data schema and introduce no
irreversible database or persistent-data migration. ProgramData, credentials,
pairing, device tokens, sessions, databases, attachments, and customer data
remain outside Program Files rollback.

Installation or health failure uses automatic Program Files rollback. A defect
found after a version is installed and accepted uses a higher-version forward
fix, not remote downgrade or same-version replacement.

### Emergency pause and key compromise

The current manifest schema has no signed disabled state. A missing endpoint
or HTTP 404/410 clears the trusted release and fails closed with an update
check error. Emergency pause removes or disables only the stable manifest
asset while retaining the release; it must not delete the release in a way
that makes the latest locator resolve to an older unintended release.

The current runtime trusts one manifest public key. During the limited pilot,
manifest-key compromise requires withdrawal plus a manually distributed
trusted bridge installer. Before broad deployment, overlapping-key support
must either be implemented in a separate high-risk Work Package or its absence
must receive explicit Product Owner risk acceptance.

## Consequences

- The distribution location must exist before WP-007 can configure a real URL.
- Production trust material is provisioned after signing tooling exists and
  before the 0.1.1 source PR.
- A production installer cannot be built from a feature branch or dirty
  authoritative workspace.
- Stable-only pilot control depends on the recorded 0.1.1 cohort.
- Manifest withdrawal stops further updates but cannot downgrade an installed
  version.
- Per-release immutable evidence belongs with that release or in an approved
  internal audit location, not only in a mutable repository status document.

## Alternatives considered

- Updating from the private source repository was rejected because customers
  must not receive repository credentials or source-update behavior.
- A separate pilot runtime channel was rejected for V1; cohort restriction is
  operational.
- A signed disabled-manifest state was rejected because schema v1 does not
  support it.
- Remote downgrade was rejected in favor of installation rollback and
  higher-version forward fixes.

## Verification or follow-up

The policy is implemented through release-distribution setup, WP-006, the
Production Trust Provisioning Gate, WP-007, WP-008, and WP-009. Production is
blocked until real installed, Thin Client, applicable AutoCount, and
dependency-security evidence is accepted.
