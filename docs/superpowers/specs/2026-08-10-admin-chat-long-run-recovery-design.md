# Admin Chat Long-Run Recovery Design

## Summary

MacSoft Server Admin Chat must tolerate a silent upstream AI interval of up to
two hours, recover the affected session after an SSE disconnect, expose useful
errors instead of collapsing every failure into a generic start error, and
prevent malformed images from poisoning later turns in the same session.

The two-hour value is a per-attempt silent-response/read threshold. It is not a
two-hour total wall-clock guarantee: the existing provider retry policy may
start another attempt after the threshold is reached.

## Confirmed current behavior

- `server/macsoft-server.yaml` and the packaged Server template set
  `hermes.request_timeout_seconds` to 600 seconds.
- Server consumes the Hermes `/v1/runs/{run_id}/events` stream through a
  synchronous `urlopen()` reader using that timeout.
- Hermes normally sends an SSE keepalive every 30 seconds. A severely stalled
  Hermes event loop cannot emit that keepalive, so the Server read can expire.
- Hermes has a separate provider stale-call watchdog. Admin Home does not
  currently receive a product-owned provider timeout matching the Server
  timeout.
- `ActiveChatRunRegistry` reserves `admin:<session_id>` until the Server stream
  generator exits. Electron reports an unexpected stream read failure but does
  not interrupt the corresponding Admin run, so the reservation can remain
  while the upstream reader is still blocked.
- HTTP 409 details are discarded by the Desktop Admin client and the renderer
  displays `Admin chat could not start.`
- image upload validation checks only format signatures. Bytes with a PNG,
  JPEG, or WebP signature can be stored even when no image decoder can read
  them. Historical Admin attachments are reattached on every later request,
  so one malformed image can repeatedly fail the session.

The production log attribution to GIL pressure is diagnostic evidence, not a
proof of the exact CPU-bound operation that held the interpreter. This design
does not claim to eliminate every possible Hermes event-loop stall.

## Goals

1. Make 7200 seconds the MacSoft Admin silent-response/read threshold on new
   and upgraded installations.
2. Apply the same value to the active provider in the isolated Admin Hermes
   Home, for both request and stale-call timeouts.
3. Stop an upstream Admin run when its Desktop SSE stream disconnects and wait
   for bounded, real release of the per-session reservation.
4. Preserve structured Server error status and code through Electron so busy,
   timeout, disconnect, and invalid-image failures have distinct messages.
5. Reject newly uploaded malformed images and allow sessions containing legacy
   malformed images to continue without deleting customer files.

## Non-goals

- Rewriting the full Server-to-Hermes stream transport as asynchronous I/O.
- Changing AutoCount connector timeouts or AutoCount business rules.
- Changing Client chat APIs, Client attachment ownership, ports, model choice,
  provider retry counts, or the Hermes pinned baseline.
- Force-releasing a run solely because a clock expired; that could allow two
  writers to mutate one session concurrently.
- Diagnosing the exact CPU operation responsible for the remote machine's
  reported 1288-second event-loop stall without that machine's profiler data.

## Architecture

### Timeout authority and upgrade

`hermes.request_timeout_seconds` in the MacSoft Server configuration remains
the single MacSoft-owned value. Its shipped value becomes 7200.

The product initializer performs a narrow upgrade migration on the packaged
Server configuration: an exact historical value of 600 is changed to 7200.
Any absent value or value other than 600 is preserved. This intentionally
treats 600 as the historical product default; an administrator who deliberately
kept exactly 600 will receive the new product policy and can set a different
value after upgrade.

At Server startup, `ensure_server_home()` continues copying the product's model
selection into the isolated Admin Home. It also merges only two managed scalar
values into the active provider's Admin configuration:

- `providers.<active-provider>.request_timeout_seconds`
- `providers.<active-provider>.stale_timeout_seconds`

Both values come from `hermes.request_timeout_seconds`. Other provider fields,
credentials, models, memory, skills, and administrator-owned configuration are
preserved. Device profile Homes are not changed.

### Disconnect and lock recovery

Electron keeps ownership of the local Desktop stream. If its response reader
fails unexpectedly, it requests `/api/admin/chat/interrupt` for that stream's
session before final cleanup.

`ActiveChatRunRegistry` gains a condition-backed bounded wait for release.
The interrupt endpoint requests the upstream Hermes stop, then waits briefly
for the existing stream generator's `finally` block to release the reservation.
The endpoint never deletes the reservation itself. If cleanup exceeds the
bounded wait, the run remains truthfully busy and a later request still gets
409 rather than starting a conflicting run.

Normal completion, explicit Stop, malformed requests, and generator failure
retain their existing `finally`-based release paths.

### Error propagation

The Desktop Admin HTTP client reads the existing Server error envelope on
non-success responses and retains the HTTP status plus safe `error.code` and
`error.message`. Electron and the renderer map known codes to customer-facing
messages:

- `admin_session_busy`: the previous reply is still stopping; retry shortly.
- `timeout`: the AI request exceeded the configured two-hour silent threshold.
- `stream_disconnected`: the stream disconnected and the previous run is being
  stopped.
- invalid image codes: identify the affected attachment.

Unknown or malformed responses remain generic and do not expose secrets,
internal paths, provider payloads, or raw stack traces.

### Image validation and legacy recovery

The Server adds Pillow at the same pinned version already used by the bundled
Hermes runtime. Upload validation opens and verifies JPG, PNG, and WebP bytes,
rejects decoder failures and decompression-bomb warnings, and confirms that the
decoded format matches the detected media type before persisting the file.

Current-turn attachments remain strict. When rebuilding historical Admin
context, a legacy malformed image is omitted from the model payload and
replaced with a bounded textual marker that names the unavailable attachment.
The stored file and database record remain unchanged and downloadable; no
customer data is silently deleted.

## Testing

- Product runtime tests prove first-run value 7200, exact 600-to-7200 upgrade,
  preservation of other custom values, and preservation of unrelated YAML
  comments/settings.
- Server Home tests prove the active Admin provider receives both timeout
  values while unrelated provider configuration and device profiles remain
  unchanged.
- Active-run tests prove interrupt waits for a real release, times out safely,
  and permits a subsequent request after release.
- Desktop tests prove unexpected disconnect requests interrupt and that 409
  details no longer become the generic start error.
- File tests use genuinely decodable image fixtures, reject signature-only
  fake images, and prove legacy malformed historical images are omitted while
  the same session can continue.
- Focused Server, product runtime, and Desktop suites run before broader
  component checks. Installed-product acceptance must exercise a long Admin
  run, forced stream interruption, immediate retry, and representative images.

## Risks and mitigations

- A genuinely wedged provider can now consume resources for up to two hours per
  attempt. The value is explicit product policy, existing interrupt remains
  available, and retries are unchanged.
- Upgrade mutates a persistent Server setting. Migration is limited to the
  exact historical default and preserves the rest of the YAML byte structure
  as far as the existing line-oriented initializer permits.
- Waiting for release could delay interrupt responses. The wait is bounded and
  never substitutes an unsafe forced unlock.
- Decoder-based image validation adds Server dependency surface. Pillow is
  already pinned by Hermes; the Server pins the identical version and tests
  decoder failure behavior without network access.

## Acceptance criteria

1. New and upgraded default installations use 7200 seconds for Server Admin
   stream reads and the active Admin provider's request/stale watchdogs.
2. Non-600 custom Server timeout values and unrelated runtime configuration are
   preserved during upgrade.
3. An unexpected Desktop stream disconnect requests upstream interruption and
   the reservation is released when the run actually exits.
4. A released session can submit again without restarting services; an
   unreleased run still returns an accurate 409.
5. Desktop distinguishes busy, timeout, disconnect, and invalid-image failures
   without exposing sensitive internal details.
6. Newly uploaded malformed images are rejected before persistence.
7. A legacy malformed historical image no longer prevents later text-only
   turns in that Admin session and is not silently deleted.
