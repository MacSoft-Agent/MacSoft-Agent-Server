# Development Runtime Port Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make source test mode safely take ownership of MacSoft ports and release them when the Desktop exits.

**Architecture:** Extend the PowerShell launcher with installed-service identity and process-tree verification before requesting an SCM stop. Preserve the existing recorded development-runtime cleanup and refusal behavior for unknown listeners.

**Tech Stack:** PowerShell 5.1, Windows SCM/CIM, Python unittest contract tests.

## Global Constraints

- Do not kill arbitrary port owners.
- Do not change ports or Windows service startup policy.
- Do not restart the installed service when development mode exits.

---

### Task 1: Safe installed-host handoff

**Files:**
- Modify: `scripts/start-test-runtime.ps1`
- Test: `product_runtime/tests/test_packaging_contract.py`

**Interfaces:**
- Consumes: required port listener records and `MacSoftAgentHost` SCM state.
- Produces: `Stop-ControlledInstalledHost`, which stops only a verified installed Host.

- [ ] Add a contract test requiring service identity, process-tree validation, SCM elevation, and no shutdown restart.
- [ ] Run the focused test and confirm it fails because the handoff is absent.
- [ ] Implement the verified service handoff and recompute listener ownership.
- [ ] Run the focused and product-runtime test suites.

### Task 2: Operator documentation and repository validation

**Files:**
- Modify: `docs/development/FRESH_CLONE_SETUP.md`
- Create: `docs/work-packages/WP-014-development-runtime-port-ownership.md`

**Interfaces:**
- Consumes: implemented launcher lifecycle.
- Produces: operator guidance and verification evidence.

- [ ] Document automatic installed-service handoff, UAC behavior, and unknown-owner refusal.
- [ ] Record scope, decisions, evidence, and remaining manual acceptance.
- [ ] Run `git diff --check` and repository cleanliness checks.
