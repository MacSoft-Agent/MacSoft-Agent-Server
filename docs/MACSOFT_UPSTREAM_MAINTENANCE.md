# MacSoft Agent Upstream Runtime Maintenance

Customers update MacSoft Agent only. They never select, fetch, or update the
internal runtime base.

## Current pin

- MacSoft version: `0.1.0`
- Runtime base tag: `v2026.7.7.2`
- Runtime base commit: `79f12748022817a7c4f3fee747e45e9e6979214a`
- Authority: `product.json`

## Branch model

- `macsoft/main`: integrated product source.
- `upstream`: read-only remote for runtime maintenance.
- `integration/runtime-<version>`: temporary compatibility branch.
- `release/<macsoft-version>`: tested MacSoft product release branch.

## Upgrade workflow

1. Fetch tags and commits from the configured internal upstream remote. Never
   run this step in a customer build.
2. Create `integration/runtime-<version>` from `macsoft/main`.
3. Record the candidate tag and commit without changing `product.json` yet.
4. Compare the candidate against every customization area below.
5. Resolve conflicts in the integration branch and run Desktop, Server,
   product-runtime, staging, and clean-environment tests.
6. Reject or postpone the upgrade if Client/Server routing, capability policy,
   dynamic plugin loading, bundled dependencies, or customer update isolation
   cannot be proven.
7. After acceptance, update the runtime pin and create a new MacSoft product
   version/build ID. Never silently move the pin under an existing build ID.
8. Create `release/<macsoft-version>`, build staging, then run the final installer
   acceptance process.

## Security-only fixes

For a critical fix that does not justify a full runtime upgrade:

1. identify the exact upstream security commit and advisories;
2. cherry-pick only the required commit(s) into a dedicated integration branch;
3. record the original commit IDs in release notes/build evidence;
4. run the complete compatibility matrix;
5. publish a new MacSoft Agent patch version and build ID.

Do not change the recorded base tag to imply that the full upstream release was
accepted. The build metadata must remain auditable.

## Customization-area inventory

- branding and customer-visible identity;
- About/version/update boundary;
- Electron customer-runtime and Settings behavior;
- Host ownership, health, control, logs, and service lifecycle;
- MacSoft Server bridge and SSE contract;
- Activity v1 mapping/privacy;
- Client Skill ownership and request isolation;
- AutoCount plugin and generic live-schema validation;
- protected capability/tool policy;
- session soft deletion and persistence;
- development/packaged path resolution;
- first-run data migration;
- bundled Python and native dependencies;
- staging/installer packaging.

## Compatibility acceptance

An upstream candidate is acceptable only if the established Client -> MacSoft
Server -> AI Service -> approved Skill/Tool -> AutoCount -> SSE flow remains the
only Client execution path. Pairing, device auth, sessions/messages, model
selection, Activity v1, Client Skill isolation, generic AutoCount validation,
and API Server tool allowlisting must pass unchanged.

An incompatible upgrade is postponed, not patched directly in a customer build.
