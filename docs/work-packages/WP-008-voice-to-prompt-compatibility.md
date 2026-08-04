# WP-008 - Voice-to-Prompt Compatibility

## Status

Complete

## Owner

- Product Owner: pxw12
- Execution owner: Codex
- Reviewer: Unassigned

## Baseline

- Server repository/commit: `30ae8eebce33f16ef20b5a9dc5b5842238bce685`
- Client repository/commit: `6a44b42c988fd6dce436daba0df0249a7047af41`
- Product baseline: `baseline-0.1.0-collaboration-safe-20260727`
- Starting working-tree state: clean in both repositories

## Objective

Restore the existing Hermes voice-to-text Prompt path in MacSoft Server Desktop and Thin Client without adding voice conversation, text-to-speech, or automatic Prompt submission.

## User or operational outcome

An authenticated user can record speech in either desktop and receive the Hermes transcript in the Prompt editor.

## Evidence and current behavior

- Hermes already implements `POST /api/audio/transcribe` and the desktop Prompt insertion flow.
- Server Desktop reaches the configuration-only backend, whose route boundary currently rejects the audio path with `404 Not Found`.
- Thin Client deliberately supplies no transcription callback in thin-client mode.
- The configuration backend requires its localhost session token for non-public API routes.

## Scope

- Allow only the existing transcription route through the configuration-only boundary.
- Add one device-authenticated MacSoft Server transcription proxy to that localhost route.
- Wire Thin Client's existing recorder to the proxy using the existing request and error infrastructure.
- Add focused route, authentication, forwarding, and client request tests.
- Restore Hermes' existing `voice` dependency extra in the packaged product Python Runtime.

## Non-scope

- Voice conversation, text-to-speech, automatic Prompt submission, new STT providers, or provider configuration changes.
- Broadening any other configuration-only route.

## Architectural boundaries

- Hermes remains the sole transcription implementation and STT configuration owner.
- MacSoft Server authenticates the device before forwarding audio.
- The configuration backend remains loopback-only and session-token protected.
- Existing audio size and MIME validation remains authoritative in Hermes.

## Proposed direction

Allow `/api/audio/transcribe` in the configuration-only route boundary. Add `/api/client/audio/transcribe` to MacSoft Server, authenticate it with the existing paired-device mechanism, and forward the unchanged Hermes payload to the loopback configuration backend with the Host session token. Thin Client calls this route and returns its transcript to the existing recorder callback.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Configuration backend security boundary widened | Sensitive routes could become reachable | Allow one exact path only and retain session-token authentication |
| Unauthenticated audio upload | Resource abuse | Require existing paired-device token and device id before forwarding |
| Oversized payload | Memory pressure | Bound the request model and retain Hermes decoded-audio limit |
| Client/server response drift | Voice UI fails generically | Preserve Hermes response shape and add focused contract tests |

## Product Owner decisions required

The Product Owner explicitly authorized restoring Hermes voice-to-Prompt compatibility for both desktops in this task.

## Acceptance criteria

1. Server Desktop can reach the existing Hermes transcription route in configuration-only mode.
2. Thin Client can call a paired-device authenticated transcription route and receive a transcript.
3. The transcript is inserted into the Prompt editor and is not automatically submitted.
4. Other configuration-only routes remain denied.
5. Invalid or revoked Client credentials are rejected before forwarding.

## Verification plan

- Focused automated checks: Hermes route-boundary test, MacSoft Server audio contract tests, Thin Client API and callback tests.
- Component/regression checks: relevant Python suites and desktop TypeScript checks.
- Manual or installed-product acceptance: required after rebuilding/restarting the affected installed components; not performed by source-only verification.
- Independent review required: not required for this narrowly scoped authenticated restoration, but exact diff and security boundary will be reviewed before completion.

## Implementation result

The existing Hermes transcription handler remains the only STT implementation. The configuration-only boundary now allows exactly `/api/audio/transcribe`. MacSoft Server exposes `/api/client/audio/transcribe`, authenticates the paired device, and forwards the unchanged payload to the loopback configuration backend using the Host session token. Thin Client converts the recorded Blob to the existing data-URL contract and returns the transcript through the existing Prompt dictation callback. Product dependency synchronization now installs Hermes' already-defined and locked `voice` extra, and verifies that `faster_whisper` is importable before staging.

## Verification evidence

- `server/.venv/Scripts/python.exe -m pytest server/tests -q`: 100 passed, 47 subtests passed; one non-functional pytest cache permission warning.
- Focused Hermes web-server audio and boundary selection: 4 passed, 363 deselected.
- `product_runtime/tests/test_host.py -q`: 15 passed.
- Thin Client Vitest voice request contract: 2 passed.
- Thin Client TypeScript `tsc -p apps/desktop --noEmit`: passed.
- Python `py_compile` for all changed Python runtime files: passed.
- `git diff --check` in both repositories: passed.
- Product voice-extra packaging contract: 2 focused tests passed.
- PowerShell parser validation for both modified dependency/build scripts: passed.
- Locked product sync dry-run with `--extra all --extra voice --locked`: resolved successfully and explicitly includes `faster-whisper==1.2.1`, `ctranslate2`, `onnxruntime`, `av`, `tokenizers`, `numpy`, and `sounddevice`.
- Rebuilt the active source Runtime at `hermes/venv` with Python 3.12.13 and the locked `all + voice` extras; 123 packages installed, including `faster-whisper==1.2.1`.
- Active Runtime import/provider check: `faster_whisper=1.2.1`, `_HAS_FASTER_WHISPER=True`, configured and resolved provider both `local`.
- Restarted the source test Runtime; Config Backend, AI Service, MacSoft Server, and Vite health endpoints all returned HTTP 200.
- Targeted Client lint exposed pre-existing import ordering, JSX ordering, Hook dependency, and spacing findings in the large touched files. New import/test findings were corrected; no broad unrelated lint rewrite was performed.

## Unexpected findings

- Related non-blocking: the repository's Hermes test wrapper is a Bash script and Bash is unavailable in this Windows environment. The selected Hermes tests were executed directly with the isolated Server test interpreter instead.
- Related non-blocking: the complete pre-existing packaging-contract file has an unrelated baseline mismatch (`aiohttp==3.14.1` is present in the Hermes MacSoft extra but absent from `server/requirements.txt`). The two voice/release-focused packaging tests pass; this unrelated dependency inventory mismatch was not changed.

## Remaining risks

- Installed-product microphone permission and configured STT provider behavior require manual acceptance after rebuild/restart.
- The first real transcription downloads Hermes' existing default `base` model into the runtime user's Hugging Face cache; that network/model-download acceptance remains manual.

## Final status

Automated source acceptance criteria are met. Installed-product acceptance remains for the Product Owner after rebuilding both affected applications.

## Server automatic STT routing extension (2026-08-03)

The Product Owner authorized a Server-first extension that keeps the existing
authenticated audio contract while allowing Hermes to select an STT backend
without requiring a language model on the Client device. `stt.provider: auto`
now prefers the active chat provider only when that provider is explicitly
known to support STT, then checks other configured cloud STT credentials, and
finally uses the existing local faster-whisper backend when enabled and
available. Text-only and OAuth-only chat providers are not treated as audio
providers. The Client repository remains unchanged in this extension.

The desktop-to-Hermes request and MacSoft Server proxy now use a transcription-
specific 90-second timeout; unrelated API timeouts remain unchanged. Focused
verification passed: 85 Python provider/helper/contract tests, 3 tests against
the synchronized actual Server tree, and 10 Desktop REST helper tests.

## Related commits and documents

- Commits: pending

## Recording quality, cancellation, and temporary-file hygiene extension (2026-08-03)

The Product Owner authorized a narrow follow-up: improve browser microphone
capture constraints, keep Thin Client dictation available beside attachments
and typed text, allow an in-flight Client request to be cancelled without
changing faster-whisper execution, and remove abandoned desktop voice files.
The backend cleanup is limited to regular files in the system temporary
directory whose names begin with `hermes-desktop-voice-` and whose age exceeds
one hour. Normal request cleanup remains in the existing `finally` block.
