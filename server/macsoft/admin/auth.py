from __future__ import annotations

import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request

from macsoft.security import parse_bearer_token


HOST_CONTROL_TOKEN_ENV = "MACSOFT_HOST_CONTROL_TOKEN"
ADMIN_ACCESS_TOKEN_TTL_SECONDS = 8 * 60 * 60
ADMIN_ACCESS_TOKEN_MAX = 64


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _expires_at() -> datetime:
    return _utc_now() + timedelta(seconds=ADMIN_ACCESS_TOKEN_TTL_SECONDS)


class AdminAccessRegistry:
    def __init__(self, *, ttl_seconds: int = ADMIN_ACCESS_TOKEN_TTL_SECONDS, max_tokens: int = ADMIN_ACCESS_TOKEN_MAX) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_tokens = max_tokens
        self._tokens: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def issue(self) -> tuple[str, datetime]:
        now = _utc_now()
        expiry = now + timedelta(seconds=self.ttl_seconds)
        token = secrets.token_urlsafe(48)
        with self._lock:
            self._purge(now)
            if len(self._tokens) >= self.max_tokens:
                oldest = min(self._tokens, key=self._tokens.get)
                self._tokens.pop(oldest, None)
            self._tokens[token] = expiry
        return token, expiry

    def validate(self, token: str | None) -> bool:
        if not token:
            return False
        now = _utc_now()
        with self._lock:
            self._purge(now)
            return any(secrets.compare_digest(token, issued) for issued in self._tokens)

    def _purge(self, now: datetime) -> None:
        for token, expiry in list(self._tokens.items()):
            if expiry <= now:
                self._tokens.pop(token, None)

    def contains(self, token: str) -> bool:
        with self._lock:
            return token in self._tokens


def is_loopback_peer(request: Request) -> bool:
    return request.client is not None and request.client.host in {"127.0.0.1", "::1"}


def _unauthorized(code: str = "admin_unauthorized", message: str = "Admin authentication failed.") -> HTTPException:
    return HTTPException(status_code=401, detail={"ok": False, "error": {"code": code, "message": message, "details": {}}})


def require_loopback(request: Request) -> None:
    if not is_loopback_peer(request):
        raise _unauthorized("loopback_required", "Admin access is limited to the local machine.")


def require_admin(request: Request, authorization: str | None) -> None:
    require_loopback(request)
    token = parse_bearer_token(authorization)
    registry: AdminAccessRegistry = request.app.state.admin_access_registry
    if not registry.validate(token):
        raise _unauthorized()


def require_host_bootstrap(request: Request, authorization: str | None) -> None:
    require_loopback(request)
    expected = os.environ.get(HOST_CONTROL_TOKEN_ENV, "")
    supplied = parse_bearer_token(authorization) or ""
    if not expected or not secrets.compare_digest(supplied, expected):
        raise _unauthorized("invalid_host_control_token", "Host authentication failed.")


def bootstrap_response(request: Request, authorization: str | None) -> dict[str, Any]:
    require_host_bootstrap(request, authorization)
    token, expiry = request.app.state.admin_access_registry.issue()
    return {
        "ok": True,
        "access_token": token,
        "token_type": "Bearer",
        "expires_at": expiry.isoformat(),
    }
