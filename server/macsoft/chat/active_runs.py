from __future__ import annotations

import threading
from typing import Any


class ActiveChatRunRegistry:
    """Single-process registry for one active chat run per Server session."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: set[str] = set()

    def reserve(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                return False
            self._sessions.add(session_id)
            return True

    def release(self, session_id: str) -> None:
        with self._lock:
            self._sessions.discard(session_id)

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
