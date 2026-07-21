# MacSoft Client session concurrency fix handoff

## Scope

This document is for the Client-side AI/maintainer. The Server repository does
not modify the external Client. The Server keeps the existing
`POST /api/chat/stream` contract.

## Confirmed Client root cause

The packaged renderer currently keeps one set of mutable chat-run state for the
whole window instead of one set per session. In the inspected bundle
`resources/app.asar.unpacked/dist/assets/index-CshunjK6.js`, the MacSoft chat
hook (`sxn` in the current bundle) has one:

- messages state;
- `AbortController`;
- in-flight session ID;
- assistant message ID;
- activity sequence/state;
- text-seen flag;
- sending/activity status.

This causes two independent failures.

### 1. Switching back to an in-flight session displays another session

`openSession(targetSessionId)` detects that the target is the current in-flight
session and then skips both cached-message hydration and the Server response
assignment. The global messages state therefore remains populated by the
session that was viewed immediately before it.

The UI must never use “this session is in flight” as a reason to leave another
session's messages on screen.

### 2. Concurrent runs overwrite or abort each other

SSE callbacks update the single global messages array and its last assistant
message. Starting or switching work replaces the single controller/run
identity. Starting a fresh session explicitly aborts that controller.

Consequences:

- a newer session can receive an older session's callback;
- cleanup from an older request can clear the newer request's state;
- starting a new session can abort a valid older request;
- an older completed answer can appear blank until the session is reloaded.

Separate HTTP/SSE requests are not the problem. The collision is in the Client
window's shared mutable state.

## Required minimal Client design

Keep chat and run state keyed by `sessionId`, for example:

```ts
type SessionRun = {
  controller: AbortController;
  assistantMessageId: string;
  isSending: boolean;
  activityStatus: ActivityStatus | null;
  activitySequence: number;
  textSeen: boolean;
};

const messagesBySession = new Map<string, Message[]>();
const runsBySession = new Map<string, SessionRun>();
```

Implementation requirements:

1. `openSession(sessionId)` must always render that session's cached messages
   immediately, including when that session has an active run. It may then
   reconcile with the Server response for that same session.
2. Every SSE callback must capture its request's `sessionId` and update only
   `messagesBySession.get(sessionId)`.
3. Only mirror that session's messages into the visible React state when
   `activeSessionIdRef.current === sessionId`.
4. Cache writes must use the captured session's message snapshot, not the
   current global visible array.
5. Cleanup must be identity-safe:

   ```ts
   if (runsBySession.get(sessionId)?.controller === controller) {
     runsBySession.delete(sessionId);
   }
   ```

6. “New session” must not abort other sessions if concurrent sessions are a
   supported feature. “Stop generating” should stop only the active session's
   controller.
7. Do not change Server URL, authentication headers, pairing, session ownership,
   SSE field names, or error contracts for this fix.

## Server-side protection already applied

Once Hermes has produced the complete formatted assistant reply, the Server now
commits that assistant message before emitting completion activity,
`token_delta`, or `message_done`. This prevents a downstream disconnect during
final delivery from discarding an already completed reply.

This Server protection does not repair the Client's wrong-session display. Both
changes are required for the complete user-visible fix.

## Client acceptance scenarios

1. Start a reply in session 1, switch to completed session 3, then switch back
   to session 1. Session 1 must immediately show only its own messages and its
   live pending/reply state.
2. Start replies in sessions 1 and 2. Both final replies must be nonblank and
   stored under the correct session.
3. While session 1 is replying, create session 2. Session 1 must continue unless
   the user explicitly stops session 1.
4. Completion/cleanup from session 1 must not clear session 2's sending or
   activity state.
5. Reload each session from the Server after completion and confirm the visible
   transcript matches the Server transcript.
6. Run two separate Client devices concurrently and confirm each remains
   isolated by its existing device/session ownership.

