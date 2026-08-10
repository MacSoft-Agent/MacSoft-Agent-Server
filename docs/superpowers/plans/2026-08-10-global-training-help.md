# Global Training Help Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an accessible, persistent Global Training explanation beside the Desktop navigation entry.

**Architecture:** A focused `GlobalTrainingHelp` component owns its Radix popover and local acknowledgement flag. The sidebar sends an incrementing entry signal whenever Global Training is opened; the component auto-opens only for the first unacknowledged entry while remaining manually available afterward.

**Tech Stack:** React, TypeScript, Radix Popover, Vitest, Testing Library, localStorage.

## Global Constraints

- Do not change Global Training authorization, learning, Proposal, or API behavior.
- The help trigger is visible only in MacSoft Server Desktop mode.
- Keyboard, Escape, outside-click, and accessible-name behavior use existing Radix primitives.
- Local storage failure must not block navigation or help display.

---

### Task 1: Global Training Help Component

**Files:**
- Create: `hermes/apps/desktop/src/app/chat/sidebar/global-training-help.tsx`
- Create: `hermes/apps/desktop/src/app/chat/sidebar/global-training-help.test.tsx`
- Modify: `hermes/apps/desktop/src/app/chat/sidebar/index.tsx`

**Interfaces:**
- Consumes: `entrySignal: number`, incremented after the Global Training navigation action.
- Produces: a question-mark trigger and explanatory popover with one-time automatic opening.

- [ ] **Step 1: Write failing component tests**

Test that manual click reveals the Server-wide impact and Proposal approval copy; changing `entrySignal` auto-opens once, stores `macsoft.global-training-help-seen.v1=1`, and does not auto-open again after remount.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm run test:ui --workspace apps/desktop -- global-training-help.test.tsx`
Expected: FAIL because `GlobalTrainingHelp` does not exist.

- [ ] **Step 3: Implement the component and sidebar signal**

Use `Popover`, `PopoverTrigger`, and `PopoverContent`; catch localStorage exceptions; place the trigger immediately beside the Global Training label without nesting one button inside another.

- [ ] **Step 4: Run focused and Desktop checks**

Run: `npm run test:ui --workspace apps/desktop -- global-training-help.test.tsx`
Run: `npm run typecheck --workspace apps/desktop`
Expected: all checks pass.

- [ ] **Step 5: Review and commit**

Inspect the exact diff, preserve unrelated working-tree changes, and commit only the component, its test, sidebar integration, and this plan.
