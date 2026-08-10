# Global Training Help Design

## Goal

Explain Global Training at the point of use so an administrator understands
its Server-wide impact and approval workflow before enabling it.

## Interaction

- Place a circular question-mark button immediately beside the `Global Training`
  navigation label.
- Clicking the button opens a compact help popover; clicking it again, pressing
  Escape, or clicking outside closes it.
- Automatically open the same popover the first time the administrator enters
  Global Training. Persist only a local acknowledgement flag so it does not
  reopen on every visit.
- The button remains available after acknowledgement.

## Content

The help explains that Global Training:

- creates reusable improvements inherited by all Clients;
- is inactive during ordinary chats;
- requires `Enable Training` before a training message can run;
- produces a Proposal rather than directly changing global state;
- takes effect only after administrator approval;
- uses General mode to classify a Workflow and Targeted mode to constrain one;
- must not receive personal, customer-private, or single-user preference data.

## Boundaries

This is explanatory UI only. It does not change training authorization,
Proposal approval, Global Home, workflow classification, learning logic, or
Client-visible APIs. The popover must use an accessible label, keyboard focus,
and existing Desktop visual primitives.

## Verification

Component tests cover the help trigger, required safety copy, first-visit
automatic opening, acknowledgement persistence, and unchanged Global Training
actions.
