# MacSoft Agent trusted update contract

This document records the customer update boundary implemented by WP-004. The
runtime code, installer source, `product.json`, and tests remain authoritative.

## Scope

The installed Windows product exposes update controls only through the existing
Hermes-native **Settings → About** page. Packaged customer runtime never falls
back to Hermes Git/source update behavior.

The v1 flow is:

1. fetch a small manifest from the HTTPS URL embedded in `product.json`;
2. verify its Ed25519 signature with the embedded SPKI public key;
3. require exact product and release-channel matching;
4. reject the same version and every lower version;
5. download the installer to the user's temporary update directory;
6. verify exact byte count and SHA-256 before publishing the temporary file;
7. require Windows Authenticode status `Valid`;
8. ask the user for explicit confirmation, then hand the installer to Windows;
9. let the elevated installer stop product processes and services;
10. back up the installed Program Files payload outside Program Files;
11. install and validate Host, Config Backend, AI Service, Server, and the
    Hermes compatibility handshake;
12. remove the recovery copy after success, or restore the previous Program
    Files payload after failure.

No successful verification step authorizes a later step to skip its own
validation.

## Signed manifest v1

The outer JSON object has exactly these fields:

- `envelope_version`: integer `1`
- `algorithm`: string `ed25519`
- `payload`: canonical base64 of the exact signed UTF-8 JSON bytes
- `signature`: canonical base64 Ed25519 signature over those payload bytes

The signed payload has exactly:

- `schema_version`: integer `1`
- `product`: `MacSoft Agent`
- `channel`: the release channel
- `version`: strict numeric `major.minor.patch`
- `build_id`: release build identifier
- `published_at`: canonical UTC ISO-8601 timestamp
- `installer.url`: normalized HTTPS URL without credentials or fragment
- `installer.sha256`: lowercase SHA-256
- `installer.bytes`: positive byte count, at most 2 GiB

The manifest is limited to 64 KiB. Unknown fields, malformed encodings, invalid
keys, invalid signatures, another product/channel, same-version releases and
downgrades fail closed.

`scripts/build-update-manifest.mjs` creates this envelope from an accepted
installer, `product.json`, an HTTPS installer URL and an externally protected
Ed25519 private key. It prints only the public key; it never prints private-key
material.

## Trust ownership

`product.json` supplies two independent installed trust inputs:

- `update_manifest_url`
- `update_manifest_public_key`

Both are currently `null`. Therefore current development builds perform no
update network request and cannot install an update. Enabling customer updates
requires Product Owner approval of:

- a customer-accessible HTTPS release source;
- an offline/protected Ed25519 signing key and its embedded public key;
- an Authenticode certificate and timestamped release installer.

The manifest-signing private key and Authenticode private key must never enter
Git, the installer, ProgramData, logs, CI artifacts, or customer machines.

Key rotation is not automatic in v1. A product signed by the current key must
ship a newly approved embedded public key before releases signed only by the new
key can be accepted.

## Persistence and rollback

The update installer backs up only the current Program Files payload to:

`%ProgramData%\MacSoft Agent Recovery`

The path is fixed and validated before any recursive operation. Normal inherited
Windows permissions are used; no Everyone/Users Full Control workaround is
introduced.

The update does not copy, replace, restore, purge, or migrate:

- `%ProgramData%\MacSoft Agent`;
- credentials or provider authentication;
- device pairing and tokens;
- sessions or databases;
- attachments or customer business data.

Built-In Update v1 must not carry an irreversible persistent-data migration.
ProgramData intentionally remains in place if program rollback is required.

## Installed acceptance boundary

Automated source tests are necessary but do not prove installed-product
acceptance. A release remains blocked until a signed candidate passes:

- clean install;
- overlay update with preserved ProgramData;
- forced health-check failure and automatic Program Files rollback;
- Host `8766`, Config Backend `8643`, AI Service `8642`, and Server `8787`;
- exact packaged Hermes compatibility handshake;
- Thin Client reconnect with the existing device token;
- session creation and chat streaming after reconnect.
