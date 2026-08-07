# WP-009: Hermes Local STT Alignment

## Status

Completed on 2026-08-06.

## Owner decision

On 2026-08-06, Product Owner pxw12 authorized aligning the current workspace
with the newly installed Hermes local STT and removing the superseded local STT
implementation after alignment.

## Baseline and evidence

- Accepted baseline tag: `baseline-0.1.0-collaboration-safe-20260727`.
- Workspace HEAD before implementation: `33135c899bce2b4716ebaa1f94588f00365f610c`.
- Reference installation: `C:\Users\pxw12\AppData\Local\hermes\hermes-agent` at
  `aaf9688519cca58dd5f76a589a0911aff269b060`.
- The reference log proved local `faster-whisper` model `base` succeeded without
  a provider key after CUDA fallback to CPU `int8`.

## Objective

Replace the older workspace local STT path with the reference implementation's
accuracy and reliability controls while preserving MacSoft request-language
precedence, provider routing, and public web endpoints.

## Scope

- Align local model loading configuration and concurrent cache protection.
- Enable VAD, disable previous-window conditioning, and filter probable silence
  hallucinations using configurable confidence thresholds.
- Align documented/default voice configuration and add focused regression tests.
- Remove the superseded implementation in place; do not retain a parallel copy.

## Non-scope

- No API provider, billing, authentication, installer policy, or product version
  changes.
- No removal of user-created model files or unrelated runtime data.

## Acceptance criteria

- Local STT remains usable without an API key.
- Explicit endpoint language overrides configuration and auto-detection.
- Hardened kwargs reach faster-whisper and silence hallucinations are filtered.
- Existing transcription and packaging contract tests remain green.

## Verification

- `server/.venv/Scripts/python.exe -m pytest` against the focused local STT
  tests and existing transcription suite: 34 passed; one unrelated OpenAI
  provider test could not import the absent optional `openai` package.
- `server/.venv/Scripts/python.exe -m pytest product_runtime/tests/test_packaging_contract.py -q`:
  21 passed.
- `server/.venv/Scripts/python.exe -m py_compile` for the modified Python
  modules: passed.
- `git diff --check`: passed (Git emitted only expected Windows line-ending
  notices).

The old local transcription body was replaced in place. No legacy copy or
parallel STT implementation remains.
