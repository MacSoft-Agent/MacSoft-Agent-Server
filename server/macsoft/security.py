from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def generate_pairing_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def generate_device_token() -> str:
    return secrets.token_urlsafe(48)


def parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    parts = authorization.strip().split(" ", 1)

    if len(parts) != 2:
        return None

    scheme, token = parts

    if scheme.lower() != "bearer":
        return None

    token = token.strip()

    return token or None
