# WP-006 - Release Signing and Artifact Finalization

## Status

The initial implementation is merged. A bounded follow-up adds independent
RFC 3161 token, message-imprint, and SHA-256 digest-policy verification before
final artifact evidence may be produced. Real-certificate verification and
production trust provisioning remain gated.

## Objective

Make the Windows release pipeline fail closed around an external Authenticode
signing boundary and ensure that release evidence describes the final signed
installer bytes.

## Scope

- explicit `Production` and `InternalTestUnsigned` artifact modes;
- an external signing-command contract that keeps certificate/provider access
  outside the repository and build output;
- Authenticode signer and timestamp validation;
- native `signtool verify /pa /all /v` validation;
- stable post-sign byte-count and SHA-256 evidence;
- final build-report classification and public certificate evidence;
- focused positive and negative finalization tests.

## Non-scope

- production certificate acquisition or provisioning;
- Ed25519 key generation or manifest signing;
- update-manifest URL or public-key changes;
- installer publication or GitHub Release creation;
- NSIS behavior, updater behavior, Hermes compatibility, Client contracts,
  persistence, database, or schema changes.

## Implementation

`scripts/build-release.ps1` now requires an explicit artifact mode.

For `Production`, the caller must supply an external signing command outside
the source repository. The release pipeline invokes that command with only:

```text
-InstallerPath <absolute-installer-path>
```

The external boundary must sign the installer in place, apply an RFC 3161
timestamp, return exit code zero only after success, and avoid writing secrets
to standard output or standard error. It owns all certificate, token, PIN,
provider, HSM, key-vault, and timestamp-service configuration. None of those
values are accepted by the repository script.

After the external command returns, the pipeline independently requires:

1. `Get-AuthenticodeSignature` status `Valid`;
2. a signer certificate;
3. a timestamp certificate;
4. a structurally unambiguous RFC 3161 unsigned attribute in the final PE;
5. successful Windows `CryptVerifyTimeStampSignature` validation of that token
   against the Authenticode signer's signature bytes;
6. RFC 3161 message-imprint digest algorithm SHA-256;
7. successful `signtool verify /pa /all /v`;
8. two matching post-verification byte-count and SHA-256 observations.

Only then may `release/build-report.json` be written. The report records public
certificate subjects/thumbprints, timestamp presence, artifact class, final
byte count, and final SHA-256. It contains no private certificate material.

For `InternalTestUnsigned`, no signing command is accepted. The artifact is
verified as unsigned and the report records:

```text
artifact_class = internal-test-unsigned
production_ready = false
```

This mode exists for internal packaging tests only and cannot be confused with
a production artifact.

## Commands

Internal unsigned packaging:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build-release.ps1 `
  -ExpectedCommit <accepted-40-character-commit> `
  -ArtifactMode InternalTestUnsigned
```

Production finalization after the Production Trust Provisioning Gate:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build-release.ps1 `
  -ExpectedCommit <accepted-40-character-commit> `
  -ArtifactMode Production `
  -SigningCommandPath <absolute-path-outside-repository>
```

`-SignToolPath` may be supplied when `signtool.exe` is not discoverable from
`PATH` or the Windows SDK.

## Fail-closed behavior

Production finalization stops without a new build report when:

- the external signing command is missing, inside the source repository, or
  fails;
- Authenticode status is not `Valid`;
- signer or timestamp evidence is absent;
- only a legacy Authenticode countersignature is present;
- multiple primary, embedded, or nested Authenticode signatures are present;
- RFC 3161 evidence is malformed, ambiguous, unverifiable, or does not use a
  SHA-256 message imprint;
- native signature verification fails;
- final bytes or SHA-256 cannot be produced or change during finalization.

The prior build report is removed before the new installer is finalized so a
failed attempt cannot leave stale evidence that appears to describe the new
artifact.

## Verification

- `scripts/test-release-artifact-finalization.ps1` exercises:
  - explicitly classified unsigned internal output;
  - missing signer failure;
  - signer failure;
  - invalid Authenticode failure;
  - missing timestamp failure;
  - native-verifier failure;
  - post-sign byte/hash evidence;
  - rejection of repository-local signing commands.
- `scripts/test-rfc3161-timestamp-verification.ps1` exercises accepted RFC 3161
  evidence plus missing, legacy-only, ambiguous, malformed, native-verifier
  failure, and non-SHA-256 paths without requiring production signing material.
- `product_runtime/tests/test_packaging_contract.py` preserves the durable
  packaging contract.
- `scripts/verify-development.ps1` runs the focused finalization tests before
  the existing contributor baseline.

## Remaining production prerequisites

- Product Owner/Security Production Trust Provisioning Gate;
- protected production signing operator and external signing command;
- production Authenticode certificate and trusted RFC 3161 timestamp service;
- real signed-installer verification on the supported Windows baseline;
- dedicated clean packaging-clone build from the exact accepted merged commit;
- installed-product acceptance and later WP-007/WP-008 release gates.
