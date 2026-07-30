# Production release control

Status: Policy approved; distribution and production trust not provisioned

This document records release policy, control status, and a non-secret evidence
template. It must never contain private keys, certificate passwords, recovery
seeds, access tokens, customer credentials, or sensitive customer data.

This is not the only ledger for production releases. Each release's immutable
installer, signed manifest, hashes, signature verification, installed
acceptance, and go/no-go record must stay with the corresponding release or in
an approved internal audit location.

## Authority and roles

| Role | Responsibility | Approval authority |
| --- | --- | --- |
| Product Owner | customer scope, version, risk, final release | production go/no-go |
| Release Manager | exact-commit build, signing ceremony, publication, evidence | cannot accept product/security risk alone |
| Security Reviewer | key custody, certificate, secrets, dependency risk | security gate |
| Technical Reviewer | source, build, compatibility and update contracts | technical gate |
| Installed-product QA | Windows installation, update, rollback and preservation | acceptance evidence |
| Thin Client Owner | reconnect, token, session, SSE and file flows | Client acceptance |
| AutoCount Reviewer | approved business read/write scope | AutoCount acceptance |

One person must not unilaterally control production signing, publication, and
independent approval.

## Release Distribution Setup

Owner-authorized setup occurs after WP-005 and before WP-006.

| Field | Status/evidence |
| --- | --- |
| Distribution identity | Pending; candidate `MacSoft-Agent/MacSoft-Agent-Releases` |
| Organization owner | Pending |
| Administrators | Pending |
| Release write roles | Pending |
| Anonymous HTTPS download | Pending |
| Immutable artifact policy | Approved |
| Stable manifest locator | Pending endpoint verification |
| Withdrawal procedure | Policy approved; rehearsal pending |
| Audit location | Pending |

Proposed locator:

```text
https://github.com/MacSoft-Agent/MacSoft-Agent-Releases/releases/latest/download/macsoft-agent-stable-manifest-v1.json
```

Proposed immutable installer pattern:

```text
https://github.com/MacSoft-Agent/MacSoft-Agent-Releases/releases/download/v{version}/MacSoft-Agent-Setup-{version}.exe
```

Controls:

- only approved stable releases may control GitHub's latest locator;
- drafts, tests, and incomplete releases must not become latest;
- verify the locator anonymously before promotion;
- publish the signed manifest after the verified installer;
- emergency pause removes/disables only the stable manifest asset;
- do not delete the release if that can resolve latest to an older release.

## Production Trust Provisioning Gate

This operational gate occurs after WP-006 and before WP-007. Values below are
public identifiers or attestations only.

### Manifest signing

| Field | Status/evidence |
| --- | --- |
| Production key generated | Pending |
| Operational key ID | Pending |
| Public-key fingerprint | Pending |
| Custodian role | Pending |
| Authorized signing roles | Pending |
| Protected primary storage attestation | Pending |
| Protected backup attestation | Pending |
| Recovery verification | Pending |
| Test/production separation | Pending |

### Authenticode

| Field | Status/evidence |
| --- | --- |
| Certificate available | Pending |
| Public subject/issuer | Pending |
| Public thumbprint or serial evidence | Pending |
| Validity period | Pending |
| Timestamp service | Pending |
| Signing role | Pending |
| Signature/timestamp verification procedure | Implemented in WP-006; real certificate acceptance pending |
| Test/production separation | Pending |

Codex and ordinary developer workspaces must never receive or retain the
production private key or certificate secret.

## Stable-only pilot control

- Version 0.1.1 is manually distributed only to a recorded activation cohort.
- The cohort record belongs in the approved internal audit location.
- Before 0.1.2 is accepted and the cohort environment is ready, the stable
  manifest locator remains unavailable.
- The update policy has a focused test proving a signed same-version release
  returns `MacSoft Agent is up to date.` without an install action at the
  policy layer. The About UI has no dedicated same-version rendering test;
  therefore V1 does not rely on a 0.1.1 same-version manifest.
- Once the 0.1.2 stable manifest is published, every configured 0.1.1 build can
  discover it.

## Emergency controls

### Pause

A missing endpoint or HTTP 404/410 fails closed. Schema v1 has no signed
updates-disabled state. During an emergency:

1. remove or disable only the stable manifest asset;
2. retain the release and immutable installer evidence;
3. verify the long-lived locator does not fall back to an older release;
4. record affected versions and cohort;
5. publish a higher-version forward fix when ready.

### Manifest-key compromise

1. stop the manifest;
2. stop using the affected key;
3. preserve evidence without exposing secret material;
4. distribute a trusted bridge installer through an independent channel;
5. rotate to a new public key;
6. review overlapping-key support before broad deployment.

## Supported-environment decisions

These are later-gate decisions and do not block the WP-005 documentation PR:

- exact supported 64-bit Windows versions and editions;
- administrator/UAC policy;
- proxy, TLS inspection and regional HTTPS access;
- Domain/Private LAN profile support;
- fixed-port conflict support for 8766, 8643, 8642 and 8787;
- minimum free disk space for installer and recovery payload;
- Defender, third-party antivirus and SmartScreen expectations;
- exact Thin Client acceptance build;
- supported AutoCount versions and operations.

## Per-release immutable evidence

For each production candidate retain outside this mutable control page:

- source commit, version and Build ID;
- staging manifest and hash;
- final signed installer, bytes and SHA-256;
- Authenticode and timestamp verification;
- signed update manifest;
- anonymous-download verification;
- installed acceptance matrix;
- Thin Client and applicable AutoCount evidence;
- go/no-go decision and withdrawal result.
