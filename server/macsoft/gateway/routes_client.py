from __future__ import annotations

import ipaddress
import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from macsoft.db import connect_db
from macsoft.gateway.errors import error_response
from macsoft.identity.devices import create_or_replace_device, require_device
from macsoft.identity.pairing import claim_pairing_code, get_or_create_dev_pairing_code
from macsoft.identity.users import get_default_admin, get_user_by_id
from macsoft.profiles.registry import (
    ensure_device_profile,
    require_device_profile,
    resolve_profile_home,
)

router = APIRouter()

SERVER_HERMES_MODEL_ID = "server-hermes-current"
SERVER_HERMES_MODEL_NAME = "MacSoft Server Current Model"


class PairDeviceRequest(BaseModel):
    pairing_code: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    client_name: str = "Unknown Client"
    client_version: str = "dev"


@router.get("/api/dev/pairing-code")
def get_dev_pairing_code(request: Request) -> dict:
    del request
    raise HTTPException(status_code=404, detail="Not found")


def _is_loopback_request(request: Request) -> bool:
    if request.client is None:
        return False
    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        return False


@router.get("/api/internal/pairing-code", include_in_schema=False)
def get_host_pairing_code(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    if not _is_loopback_request(request):
        raise HTTPException(status_code=404, detail="Not found")

    expected_token = os.environ.get("MACSOFT_HOST_CONTROL_TOKEN", "")
    if not expected_token or not secrets.compare_digest(
        authorization or "",
        f"Bearer {expected_token}",
    ):
        raise HTTPException(
            status_code=401,
            detail=error_response(
                "invalid_host_control_token",
                "Host Control authentication failed.",
            ),
        )

    config = request.app.state.config
    conn = connect_db(config)

    try:
        admin = get_default_admin(conn)
        code = get_or_create_dev_pairing_code(conn, str(admin["user_id"]))

        return {
            "ok": True,
            "pairing_code": code,
        }
    finally:
        conn.close()


@router.get("/api/internal/users/{user_id}", include_in_schema=False)
def get_internal_user_identity(
    user_id: str,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Resolve the existing MacSoft role authority for localhost runtimes."""
    if not _is_loopback_request(request):
        raise HTTPException(status_code=404, detail="Not found")
    expected_token = os.environ.get("MACSOFT_HOST_CONTROL_TOKEN", "")
    if not expected_token or not secrets.compare_digest(
        authorization or "", f"Bearer {expected_token}"
    ):
        raise HTTPException(
            status_code=401,
            detail=error_response("invalid_host_control_token", "Host Control authentication failed."),
        )
    conn = connect_db(request.app.state.config)
    try:
        user = get_user_by_id(conn, user_id)
        if user is None or str(user["status"]) != "active":
            raise HTTPException(status_code=404, detail=error_response("user_not_found", "User was not found."))
        return {
            "ok": True,
            "user": {
                "user_id": str(user["user_id"]),
                "display_name": str(user["display_name"]),
                "role": str(user["role"]),
                "status": str(user["status"]),
            },
        }
    finally:
        conn.close()


@router.post("/api/client/pair")
def pair_device(
    request: Request,
    body: PairDeviceRequest,
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_client_version: str | None = Header(default=None, alias="X-Client-Version"),
) -> dict:
    config = request.app.state.config
    conn = connect_db(config)

    try:
        try:
            claimed = claim_pairing_code(conn, body.pairing_code)
        except ValueError:
            raise HTTPException(
                status_code=410,
                detail=error_response(
                    "invalid_pairing_code",
                    "Pairing code is invalid, expired, or already used.",
                ),
            )

        user = get_user_by_id(conn, str(claimed["user_id"]))

        if user is None or user["status"] != "active":
            raise HTTPException(
                status_code=403,
                detail=error_response(
                    "user_not_active",
                    "The paired user is not active.",
                ),
            )

        final_device_id = body.device_id or x_device_id

        if not final_device_id:
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "missing_device_id",
                    "device_id is required.",
                ),
            )

        device = create_or_replace_device(
            conn,
            device_id=final_device_id,
            user_id=str(user["user_id"]),
            display_name=str(user["display_name"]),
            role=str(user["role"]),
            client_name=body.client_name or "Unknown Client",
            client_version=body.client_version or x_client_version or "dev",
        )
        ensure_device_profile(
            conn,
            config=config,
            device_id=str(device["device_id"]),
        )

        return {
            "ok": True,
            "device_id": device["device_id"],
            "deviceId": device["device_id"],
            "device_token": device["device_token"],
            "deviceToken": device["device_token"],
            "paired_user": device["display_name"],
            "pairedUser": device["display_name"],
            "role": device["role"],
            "paired_at": device["paired_at"],
            "pairedAt": device["paired_at"],
        }
    finally:
        conn.close()


@router.get("/api/client/me")
def get_current_client(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    config = request.app.state.config
    conn = connect_db(config)

    try:
        try:
            device = require_device(
                conn,
                authorization=authorization,
                device_id=x_device_id,
            )
        except ValueError:
            raise HTTPException(
                status_code=401,
                detail=error_response(
                    "invalid_device_token",
                    "Device token is invalid or revoked.",
                ),
            )

        return {
            "user_id": device["user_id"],
            "display_name": device["display_name"],
            "role": device["role"],
            "allowed_models": [
                {
                    "id": SERVER_HERMES_MODEL_ID,
                    "name": SERVER_HERMES_MODEL_NAME,
                    "source": "server-hermes",
                }
            ],
            "default_model": SERVER_HERMES_MODEL_ID,
            "allowed_skills": [],
        }
    finally:
        conn.close()


@router.get("/api/profile")
def get_current_device_profile(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    """Return a safe profile display summary with no authority identifiers."""
    config = request.app.state.config
    conn = connect_db(config)
    try:
        try:
            device = require_device(
                conn,
                authorization=authorization,
                device_id=x_device_id,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=401,
                detail=error_response(
                    "invalid_device_token",
                    "Device token is invalid or revoked.",
                ),
            ) from error
        profile = require_device_profile(
            conn,
            config=config,
            device_id=str(device["device_id"]),
        )
        home = resolve_profile_home(config, profile_id=str(profile["profile_id"]))
        mtimes = [
            path.stat().st_mtime
            for path in (home / "memories" / "USER.md", home / "memories" / "MEMORY.md")
            if path.is_file()
        ]
        return {
            "display_name": str(device["display_name"] or device["client_name"]),
            "memory_updated_at": (
                datetime.fromtimestamp(max(mtimes), timezone.utc).isoformat()
                if mtimes
                else None
            ),
        }
    finally:
        conn.close()
