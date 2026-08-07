from __future__ import annotations

import time
from threading import RLock


class GlobalLearningGate:
    """Process-local, fail-closed authorization for one training session.

    The canonical enable state is deliberately not persisted: creating a new
    Server process always returns global learning to OFF.
    """

    def __init__(self, *, lease_seconds: float = 30.0) -> None:
        self._lock = RLock()
        self._enabled_session_id: str | None = None
        self._lease_seconds = lease_seconds
        self._lease_expires_at = 0.0

    def _expire_if_needed(self) -> None:
        if self._enabled_session_id is not None and time.monotonic() >= self._lease_expires_at:
            self._enabled_session_id = None
            self._lease_expires_at = 0.0

    def enable(self, session_id: str) -> None:
        with self._lock:
            self._enabled_session_id = session_id
            self._lease_expires_at = time.monotonic() + self._lease_seconds

    def disable(self, session_id: str | None = None) -> None:
        with self._lock:
            self._expire_if_needed()
            if session_id is None or self._enabled_session_id == session_id:
                self._enabled_session_id = None
                self._lease_expires_at = 0.0

    def is_enabled(self, session_id: str) -> bool:
        with self._lock:
            self._expire_if_needed()
            return self._enabled_session_id == session_id

    def touch(self, session_id: str) -> bool:
        """Renew the Desktop-held lease only for its currently enabled session."""
        with self._lock:
            self._expire_if_needed()
            if self._enabled_session_id != session_id:
                return False
            self._lease_expires_at = time.monotonic() + self._lease_seconds
            return True

    def snapshot(self) -> dict[str, str | bool | None]:
        with self._lock:
            self._expire_if_needed()
            return {
                "enabled": self._enabled_session_id is not None,
                "session_id": self._enabled_session_id,
            }
