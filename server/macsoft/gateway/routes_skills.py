from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from macsoft.db import connect_db
from macsoft.gateway.errors import device_credentials_rejected_error
from macsoft.identity.devices import require_device
from macsoft.skills.client_skills import (
    MAX_SKILL_CONTENT_LENGTH,
    MAX_SKILL_DESCRIPTION_LENGTH,
    MAX_SKILL_NAME_LENGTH,
    MAX_SKILL_SLUG_LENGTH,
    create_client_skill,
    delete_client_skill,
    get_client_skill,
    list_client_skills,
    update_client_skill,
    validate_client_skill,
)


router = APIRouter(prefix="/api/client/skills", tags=["client-skills"])


class ClientSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=MAX_SKILL_SLUG_LENGTH)
    name: str = Field(min_length=1, max_length=MAX_SKILL_NAME_LENGTH)
    description: str = Field(default="", max_length=MAX_SKILL_DESCRIPTION_LENGTH)
    content: str = Field(min_length=1, max_length=MAX_SKILL_CONTENT_LENGTH)
    enabled: bool = False


class ClientSkillUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_SKILL_NAME_LENGTH)
    description: str = Field(default="", max_length=MAX_SKILL_DESCRIPTION_LENGTH)
    content: str = Field(min_length=1, max_length=MAX_SKILL_CONTENT_LENGTH)
    enabled: bool = False


def _error(code: str, message: str, *, details: dict | None = None) -> dict:
    if code == "invalid_device_token":
        return device_credentials_rejected_error()
    return {
        "ok": False,
        "error": {"code": code, "message": message, "details": details or {}},
    }


def _authenticated(
    request: Request,
    authorization: str | None,
    device_id: str | None,
):
    conn = connect_db(request.app.state.config)
    try:
        device = require_device(
            conn,
            authorization=authorization,
            device_id=device_id,
        )
    except ValueError:
        conn.close()
        raise HTTPException(
            status_code=401,
            detail=_error(
                "invalid_device_token",
                "Device token is invalid or revoked.",
            ),
        )
    return conn, str(device["user_id"]), str(device["device_id"])


def _validate(
    body: ClientSkillInput | ClientSkillUpdate,
    slug: str | None = None,
):
    result = validate_client_skill(
        slug=slug if slug is not None else body.slug,
        name=body.name,
        description=body.description,
        content=body.content,
    )
    if not result.valid:
        raise HTTPException(
            status_code=422,
            detail=_error(
                "invalid_client_skill",
                "The Client Skill did not pass validation.",
                details=result.as_dict(),
            ),
        )
    return result


@router.get("")
def list_skills(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    conn, user_id, device_id = _authenticated(request, authorization, x_device_id)
    try:
        return {
            "ok": True,
            "skills": list_client_skills(
                conn,
                owner_user_id=user_id,
                owner_device_id=device_id,
            ),
        }
    finally:
        conn.close()


@router.post("/validate")
def validate_skill(
    request: Request,
    body: ClientSkillInput,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    conn, _, _ = _authenticated(request, authorization, x_device_id)
    try:
        values = body.model_dump(exclude={"enabled"})
        return {
            "ok": True,
            "validation": validate_client_skill(**values).as_dict(),
        }
    finally:
        conn.close()


@router.post("", status_code=201)
def create_skill(
    request: Request,
    body: ClientSkillInput,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    conn, user_id, device_id = _authenticated(request, authorization, x_device_id)
    try:
        validation = _validate(body)
        try:
            skill = create_client_skill(
                conn,
                owner_user_id=user_id,
                owner_device_id=device_id,
                **body.model_dump(),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409,
                detail=_error(
                    "client_skill_exists",
                    "A Client Skill with this slug already exists.",
                ),
            )
        return {
            "ok": True,
            "skill": skill,
            "validation": validation.as_dict(),
        }
    finally:
        conn.close()


@router.get("/{slug}")
def get_skill(
    slug: str,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    conn, user_id, device_id = _authenticated(request, authorization, x_device_id)
    try:
        skill = get_client_skill(
            conn,
            owner_user_id=user_id,
            owner_device_id=device_id,
            slug=slug,
        )
        if skill is None:
            raise HTTPException(
                status_code=404,
                detail=_error(
                    "client_skill_not_found",
                    "Client Skill was not found.",
                ),
            )
        return {"ok": True, "skill": skill}
    finally:
        conn.close()


@router.patch("/{slug}")
def update_skill(
    slug: str,
    request: Request,
    body: ClientSkillUpdate,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    conn, user_id, device_id = _authenticated(request, authorization, x_device_id)
    try:
        validation = _validate(body, slug)
        skill = update_client_skill(
            conn,
            owner_user_id=user_id,
            owner_device_id=device_id,
            slug=slug,
            **body.model_dump(),
        )
        if skill is None:
            raise HTTPException(
                status_code=404,
                detail=_error(
                    "client_skill_not_found",
                    "Client Skill was not found.",
                ),
            )
        return {
            "ok": True,
            "skill": skill,
            "validation": validation.as_dict(),
        }
    finally:
        conn.close()


@router.delete("/{slug}")
def remove_skill(
    slug: str,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    conn, user_id, device_id = _authenticated(request, authorization, x_device_id)
    try:
        if not delete_client_skill(
            conn,
            owner_user_id=user_id,
            owner_device_id=device_id,
            slug=slug,
        ):
            raise HTTPException(
                status_code=404,
                detail=_error(
                    "client_skill_not_found",
                    "Client Skill was not found.",
                ),
            )
        return {"ok": True, "deleted": True}
    finally:
        conn.close()
