# WP-012 - Restricted WhatsApp AutoCount tools

## Status

Verifying

## Owner

- Product Owner: repository owner (decision recorded in the initiating request)
- Execution owner: Codex
- Reviewer: pending

## Baseline

- Repository/branch: `update/add-new-module-in-server`
- Accepted baseline tag commit: `e8699b5837b66fac55e599aea5db1d2681248abe`
- Product and Hermes versions: `product.json`; Hermes baseline recorded in `docs/PROJECT_STATUS.md`
- Starting working-tree state: dirty with unrelated in-progress Server/global-learning and Desktop changes; preserved

## Objective

Allow native Hermes WhatsApp conversations to use only the MacSoft AutoCount
toolset and read-only Skills, with the AutoCount policy injected into LLM calls.

## User or operational outcome

An operator can pair WhatsApp through the existing Hermes bridge and use
MacSoft plugin Skills and AutoCount operations without first implementing the
MacSoft Client device, profile, Server session, or Server SQLite identity path.

## Evidence and current behavior

- The product runtime enabled `macsoft_autocount` and `skills_readonly` only for
  `api_server`.
- The AutoCount `pre_llm_call` hook returned no policy for every non-API platform.
- WhatsApp dispatches directly inside Hermes Gateway and bypasses port 8787.

## Scope

- Explicitly allow `macsoft_autocount` and `skills_readonly` for WhatsApp.
- Inject the existing AutoCount policy for `whatsapp` as well as `api_server`.
- Upgrade preserved runtime configuration additively for existing installs.
- Apply the same configuration to the current development runtime for immediate testing.

## Non-scope

- MacSoft Client device-token, device-profile, Server-session, or SQLite integration.
- WhatsApp UI/QR onboarding work.
- Skill improvement or learning behavior.
- Other Hermes tools or other messaging platforms.

## Architectural boundaries

- WhatsApp remains a native Hermes Gateway platform and does not become a port 8787 Client.
- AutoCount validation and confirmation behavior remains owned by the existing protected plugin.
- The WhatsApp core tool list is explicit; enabled plugin toolsets remain extensible,
  while terminal, browser, writable files, delegation, automation, and unrestricted
  Skills are not enabled merely through Hermes platform defaults.

## Proposed direction

Add a narrow `platform_toolsets.whatsapp` base plus a plugin-extensible platform
mode, widen the existing AutoCount policy hook to the two approved platforms, and
use the initializer's additive YAML helper so existing customer settings are preserved.

## Risks

| Risk | Impact | Mitigation/evidence |
| --- | --- | --- |
| WhatsApp identity bypasses MacSoft Server authorization | A paired WhatsApp account can request AutoCount operations | Product Owner explicitly accepted the shorter native path; WhatsApp pairing/allowlist remains required |
| Excess Hermes core tools become visible | Broader host access | Platform keeps only named base toolsets plus normally enabled plugin toolsets |
| AutoCount write requested from WhatsApp | Customer-data mutation | Existing plugin validation and explicit-confirmation policy remains unchanged and is injected |
| Existing runtime config overwritten | Customer configuration loss | Initializer uses additive list insertion only; regression test preserves model customization |

## Product Owner decisions required

None. The Product Owner explicitly selected the native WhatsApp path, accepted
omitting MacSoft Client identity/session restrictions for this phase, and named
the two allowed toolsets.

## Acceptance criteria

1. WhatsApp resolves the named base toolsets and normally enabled plugin toolsets, but not unrelated recovered Hermes core/native toolsets.
2. AutoCount policy injection accepts `api_server` and `whatsapp`, but not another messaging platform.
3. Existing installed runtime configuration gains the WhatsApp allowlist without replacing customer model settings.
4. Future enabled plugin toolsets can extend WhatsApp without reopening unrelated Hermes core/native toolsets.

## Verification plan

- Focused automated checks: initializer tests and AutoCount plugin policy-routing test.
- Component/regression checks: product runtime and AutoCount validator suites where available.
- Manual or installed-product acceptance: pair a real WhatsApp account, inspect exposed tools, perform a read operation, then verify a write requires confirmation.
- Independent review required: yes before release acceptance.

## Implementation result

Pending verification.

## Verification evidence

Pending.

## Unexpected findings

- Related non-blocking: the repository Hermes virtual environment points to an
  unavailable interpreter, so verification may require the bundled workspace runtime.

## Remaining risks

- Real installed-product WhatsApp pairing and AutoCount execution have not yet been exercised.

## Final status

Pending verification.

## Related commits and documents

- Commits: none
- Decision records: this Work Package
- Contracts/status/release evidence: `docs/PROJECT_STATUS.md`
