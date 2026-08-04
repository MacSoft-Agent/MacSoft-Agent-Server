# WP-006 - Server Desktop Font Size

## Status

Complete

## Owner

- Product Owner: approved in Codex task on 2026-07-30
- Execution owner: Codex
- Reviewer: pending

## Baseline

- Repository/branch: MacSoft-Agent-Server / `main`
- Starting commit: `88782137d59c7c7eaf35905dec9faa5a0225f15d`
- Product and Hermes versions: MacSoft Agent 0.1.0; Hermes `v2026.7.7.2`
- Starting working-tree state: existing Admin Chat attachment work and unrelated untracked root `package-lock.json` preserved

## Objective

Allow Server Desktop users to select a readable font-size preset that remains
selected after ordinary reloads, application restarts, and computer restarts.

## User or operational outcome

Server Desktop Appearance settings now provide the same five font-size choices
as Thin Client. Applying a choice updates Server Desktop text and restores the
choice on the next launch.

## Scope

- Add Small, Normal, Large, Extra Large, and Senior font-size presets.
- Add an Appearance setting with an explicit Apply action.
- Persist the selection in Server Desktop local storage.
- Restore and apply the selection during normal Desktop startup.
- Safely fall back to Large (125%) for missing or invalid values.

## Non-scope

- Changing Thin Client settings or files.
- Synchronizing the preference between computers.
- Storing the preference in Server database, Admin sessions, or port 8787.
- Replacing the existing whole-window UI Scale setting.

## Architectural boundaries

- Preference ownership remains inside Server Desktop.
- No Client identity, Admin token, public API, or customer data is involved.
- Existing UI Scale remains an independent Electron window-zoom preference.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| Invalid stored value breaks layout | Low | Normalization falls back to Large (125%). |
| Setting is lost after restart | Medium | Persistent atom uses a stable localStorage key and is loaded from the Desktop controller at startup. |
| Font Size conflicts with UI Scale | Low | The settings are separate and clearly labeled; Font Size changes the base text variable while UI Scale retains Electron zoom ownership. |

## Product Owner decisions required

None. Product Owner explicitly approved local persistence across application
and computer restarts.

## Acceptance criteria

1. Appearance offers five font-size presets from 100% to 150%.
2. Apply updates the Server Desktop font-size CSS variables.
3. The selected preset is stored locally and restored during the next startup.
4. Missing or invalid stored values use Large (125%).
5. Existing UI Scale, Client settings, Server APIs, and Admin security remain unchanged.

## Verification plan

- Focused automated checks: normalization, CSS application, and persisted value.
- Component/regression checks: Desktop TypeScript typecheck and diff check.
- Manual acceptance: select a size, apply, close/reopen Desktop, and confirm it remains.
- Independent review required: no; local reversible UI preference.

## Implementation result

- Added a dedicated persistent Server Desktop font-scale store with a stable
  key and startup subscription.
- Added five Client-aligned presets and an Apply workflow to Appearance.
- Added default CSS variables to avoid a startup size flash.
- Preserved the existing whole-window UI Scale control.

## Verification evidence

- `npm.cmd run typecheck`: passed.
- `npm.cmd run test:ui -- --run src/store/font-scale.test.ts`: 3/3 passed.
- `git diff --check`: passed.

## Remaining risks

- Real close/reopen visual acceptance remains for the Product Owner.
- Clearing Desktop user data or reinstalling with data removal resets the preference.

## Final status

Implementation and automated verification are complete. Manual restart
acceptance remains.

## Related commits and documents

- Commits: pending
- Decision records: this Work Package
