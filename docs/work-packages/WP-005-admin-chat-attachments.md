# WP-005 - Admin Chat Attachments

## Status

Verifying

## Owner

- Product Owner: approved in Codex task on 2026-07-29
- Execution owner: Codex
- Reviewer: pending independent review

## Baseline

- Repository/branch: MacSoft-Agent-Server / `main`
- Starting commit: `88782137d59c7c7eaf35905dec9faa5a0225f15d`
- Product and Hermes versions: MacSoft Agent 0.1.0; Hermes `v2026.7.7.2`
- Starting working-tree state: untracked `package-lock.json` preserved and out of scope

## Objective

Allow the local Server Desktop administrator to upload supported attachments,
read them in Admin Chat, download them, and delete them without using the
Client device identity or Client file authorization model.

## Evidence and current behavior

- Client files use `/api/files` and are authorized by `X-Device-Id` plus a
  Client device token.
- Admin Chat rejects every `uploaded_file_ids` request with
  `attachments_not_supported`.
- Existing file validation and content conversion supports JPG, PNG, WebP,
  PDF, CSV, XLSX, and TXT; images are passed as visual input and supported
  documents are converted to bounded, untrusted text.

## Scope

- Separate administrator-owned attachment persistence and storage.
- Local administrator-token-authenticated upload, download, and delete routes.
- Admin Chat validation and content construction using the existing shared
  validation and conversion rules.
- Immediate removal of all attachment records and bytes when their Admin Chat
  session is deleted.
- Server Desktop IPC and renderer integration to submit attachment IDs.
- Focused Server and Desktop tests.

## Non-scope

- Reusing Client device identity, Client upload records, or `/api/files`.
- Automatic time-based attachment expiry. The Product Owner explicitly declined
  it on 2026-07-29.
- OCR for image-only PDFs, Client changes, AutoCount behavior, or installer changes.

## Architectural boundaries

- Admin file routes require the existing loopback-only administrator token.
- Files are bound to an Admin Chat session, not a Client user/device.
- Attachment content remains untrusted and must not alter protected system
  instructions or AutoCount confirmation requirements.
- Client and Admin records and on-disk roots remain distinct.

## Proposed direction

Add `admin_uploaded_files` and an `admin_uploads` storage root. Reuse the
shared format detection, limits, and `build_hermes_user_content` conversion
path through a compatible record model. Admin routes and Desktop IPC use only
the administrator access token. Session deletion removes the bound records and
file bytes in the same operation.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Privileged file disclosure | High | Loopback admin authentication plus per-session ownership checks; separate records and storage root. |
| Stored sensitive files accumulate | Medium | Explicit per-file deletion and immediate session-deletion cleanup; no automatic expiry by Product Owner decision. |
| OCR/vision misreads source data | Medium | Existing content limits and untrusted-data delimiters; no automatic business writes. |

## Product Owner decisions required

None. The Product Owner approved independent Admin authorization and storage,
session-deletion cleanup, and explicitly declined automatic expiry.

## Acceptance criteria

1. A valid local administrator token can upload, download, and delete a supported attachment for an active Admin session.
2. A Client token/device cannot authorize Admin attachment routes, and Admin attachment IDs cannot be used through Client file routes.
3. Admin Chat accepts only files bound to its specified active Admin session and supplies image/document content through the existing safe conversion path.
4. Deleting an Admin session removes its attachment records and bytes.
5. The Server Desktop can select attachments and send their IDs through the separate Admin route.

## Verification plan

- Focused automated checks: Admin route, ownership, chat-content, and session-cleanup tests.
- Component/regression checks: Server test suite; focused Desktop Electron and renderer tests plus typecheck.
- Manual or installed-product acceptance: required before release, using a real local Server Desktop and representative image/document uploads.
- Independent review required: yes, due to authentication and persistent-data changes.

## Implementation result

- Added the independent `admin_uploaded_files` table and `admin_uploads`
  storage root. The Client `uploaded_files` table and `uploads` root are
  unchanged.
- Added local-admin-token routes under
  `/api/admin/sessions/{session_id}/files` for upload, download, and delete.
  Each file is authorized against the active Admin Chat session in its route.
- Admin Chat now validates its own attachment IDs, applies the existing shared
  size/type limits and content conversion, and passes images/documents to
  Hermes through the existing untrusted-content path.
- Corrected the Admin Chat image bridge after runtime evidence showed the
  Hermes Runs API interpreted a top-level multimodal content list as a message
  list. The bridge now wraps the current multimodal turn in an explicit user
  message before requesting a run.
- Admin session deletion first removes all bound Admin attachment records and
  on-disk bytes, then soft-deletes the session.
- Added Desktop main-process upload IPC. The renderer reads selected local
  attachment bytes through the existing narrow bridge; only the main process
  holds the administrator access token and sends the multipart request.
- No automatic expiry was added, by Product Owner decision.

## Verification evidence

- `npm.cmd run typecheck` in `hermes/apps/desktop`: passed.
- `python -m py_compile` for changed Server modules and the new Server test:
  passed.
- Added a focused contract test that asserts a multimodal image remains inside
  the explicit user message sent to the Hermes Runs API.
- `git diff --check`: passed.
- `scripts/check-repository-cleanliness.ps1`: passed; reported the expected
  pending implementation paths and preserved unrelated `package-lock.json`.
- Focused Electron tests could not start: `tsx` failed before test execution
  with `uv_os_get_passwd ENOMEM` in this machine environment.
- Focused Server test could not start: the repository-pinned
  `hermes/venv/Scripts/python.exe` points to a missing Python 3.12 runtime.
  The system Python lacks FastAPI. No test assertion failed in either case.

## Unexpected findings

- Related, non-blocking: current `main` is newer than the accepted baseline
  tag documented in `PROJECT_STATUS.md`; work proceeds on current executable
  code as required by repository authority order.

## Remaining risks

- Automatic expiry is intentionally absent by Product Owner decision.
- Real installed-product acceptance and independent review remain required.

## Final status

Implementation is complete pending independent review and real local
installed-product acceptance. Automated type and syntax checks passed; focused
runtime tests remain blocked by the local development environment.

## Related commits and documents

- Commits: pending
- Contracts/status/release evidence: `docs/PROJECT_STATUS.md`
