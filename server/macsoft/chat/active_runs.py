from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class ActiveChatRun:
    run_id: str | None = None
    interrupt_requested: bool = False


class ActiveChatRunRegistry:
    """Single-process registry for one active chat run per Server session."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, ActiveChatRun] = {}

    def reserve(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                return False
            self._sessions[session_id] = ActiveChatRun()
            return True

    def bind_run(self, session_id: str, run_id: str) -> bool:
        """Bind an upstream run and return whether an early interrupt is pending."""
        with self._lock:
            active = self._sessions.get(session_id)
            if active is None:
                return True
            active.run_id = run_id
            return active.interrupt_requested

    def request_interrupt(self, session_id: str) -> tuple[bool, str | None]:
        with self._lock:
            active = self._sessions.get(session_id)
            if active is None:
                return False, None
            active.interrupt_requested = True
            return True, active.run_id

    def interrupt_requested(self, session_id: str) -> bool:
        with self._lock:
            active = self._sessions.get(session_id)
            return bool(active and active.interrupt_requested)

    def release(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def is_active(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._sessions


def get_active_chat_registry(app: Any) -> ActiveChatRunRegistry:
    registry = getattr(app.state, "active_chat_runs", None)
    if isinstance(registry, ActiveChatRunRegistry):
        return registry
    registry = ActiveChatRunRegistry()
    app.state.active_chat_runs = registry
    return registry
