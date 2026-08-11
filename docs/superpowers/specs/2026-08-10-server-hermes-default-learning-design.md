# Server Hermes Default Learning Design

## Goal

Remove the MacSoft-specific Global Training product and reconnect Server
Desktop learning to Hermes' native default learning lifecycle. Client device
profiles remain isolated and continue to learn independently. Clients may read
approved, shareable Server learning, but Client conversations never train the
Server Home.

## Runtime Boundaries

- Thin Clients connect only to MacSoft Server on port 8787.
- MacSoft Server authenticates the device, assembles protected context, and
  calls the internal Hermes API service on port 8642 through `/v1/runs`.
- Server Desktop ordinary chat runs in the Server Hermes Home.
- Each paired Client run remains scoped to its device Profile Home.
- A Client request performs one primary model run. The Server layer is context
  assembly and policy enforcement, not a second model response.

## Server Desktop Learning

Server Desktop ordinary Messaging sessions use the Server Hermes Home and the
native Hermes lifecycle:

- native background review prompts and cadence;
- Memory Manager, `USER.md`, and `MEMORY.md`;
- `skill_manage` creation and improvement;
- skill usage, Curator, Journey, archive, backup, and restore;
- `native_after_run` after successful runs.

MacSoft does not replace or customize the native review algorithm or prompts.
Product branding remains Mac Soft AI Agent in customer-visible identity text.

## Client Learning

The existing device framework remains:

`device_id -> profile_id -> isolated HERMES_HOME`

Each device retains independent Memory, Progress Skills, usage, Curator state,
Journey, sessions, logs, and backups. Successful Client runs invoke native
learning only in that device Profile Home. Failed and interrupted runs do not
learn.

Private Skills remain device-owned read-only instructions. Core, Company, and
Workflow Skills remain protected. Device learning cannot change AutoCount
permissions or protected skills.

## Shared Server Learning

Clients may consume Server Home learning only as a read-only context layer.
Client conversations do not run Server Home `native_after_run` and cannot call
Server Home mutation tools.

The effective Client context order is:

1. system security policy;
2. protected Core, Company, and Workflow Skills;
3. shareable Server Home Memory and learned Skills, read-only;
4. device Memory;
5. device Private Skills, read-only;
6. device Progress Skills;
7. request-scoped instructions and the current request.

Shared Server state is snapshotted when a new Client session starts so the
system prompt remains stable for that conversation and Hermes prompt caching is
preserved.

## Global Training Removal

Remove all Global Training UI, session creation, enable/disable controls,
workflow targeting, proposal review, and Desktop transport types. Remove the
Server Global Learning routes, gate, staging homes, proposal services, custom
review prompts, workflow overlay mutation rules, and Hermes global-training
admin scope.

Existing Global Learning database tables are left in place but become unused.
This avoids an unsafe destructive migration and preserves upgrade and rollback
compatibility. Existing runtime Global Training files are not deleted by the
upgrade.

## Safety Invariants

- Client traffic cannot select or mutate the Server Home.
- Server Desktop traffic cannot enter a device Profile Home.
- Client traffic cannot trigger Server Home background review.
- Server shared learning is read-only in Client runs.
- Private, Core, Company, Workflow, and AutoCount authorization resources
  remain outside native learned-skill mutation roots.
- Profile paths are derived by the Server and never accepted from a Client.

## Verification

- Global Training is absent from Desktop UI and transport contracts.
- Ordinary Server Desktop chat executes native `native_after_run` in Server
  Home with the unmodified Hermes review prompts.
- Client chat still enters through port 8787 and invokes Hermes on port 8642.
- A Client run reads Server shared learning without changing Server Home.
- Two devices retain isolated Memory, Skills, usage, Curator, and Journey.
- Failed and interrupted runs do not learn.
- Existing Client chat and learning-management APIs remain compatible.
- Relevant Server, Hermes API, product runtime, and Desktop suites pass.
