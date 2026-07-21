from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from macsoft.chat.active_runs import get_active_chat_registry
from macsoft.db import connect_db
from macsoft.identity.devices import require_device
from macsoft.sessions.message_store import list_messages_for_session
from macsoft.sessions.session_store import (
    create_session,
    get_session_including_deleted,
    list_sessions_for_owner,
    require_session_for_owner,
    soft_delete_session,
)

router = APIRouter()


class CreateSessionRequest(BaseModel):
    title: str = "New Chat"


def error_response(code: str, message: str) -> dict:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": {},
        },
    }


def _require_device_from_headers(
    request: Request,
    authorization: str | None,
    x_device_id: str | None,
):
    conn = connect_db(request.app.state.config)

    try:
        device = require_device(
            conn,
            authorization=authorization,
            device_id=x_device_id,
        )
        return conn, device
    except ValueError:
        conn.close()
        raise HTTPException(
            status_code=401,
            detail=error_response(
                "invalid_device_token",
                "Device token is invalid or revoked.",
            ),
        )


@router.get("/api/sessions")
def list_sessions(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    conn, device = _require_device_from_headers(
        request,
        authorization,
        x_device_id,
    )

    try:
        sessions = list_sessions_for_owner(
            conn,
            user_id=str(device["user_id"]),
            owner_device_id=str(device["device_id"]),
        )

        return {
            "ok": True,
            "sessions": sessions,
        }
    finally:
        conn.close()


@router.post("/api/sessions")
def create_new_session(
    request: Request,
    body: CreateSessionRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    conn, device = _require_device_from_headers(
        request,
        authorization,
        x_device_id,
    )

    try:
        session = create_session(
            conn,
            user_id=str(device["user_id"]),
            owner_device_id=str(device["device_id"]),
            title=body.title,
            source="client",
        )

        return {
            "ok": True,
            "session": session,
            "id": session["session_id"],
            "session_id": session["session_id"],
            "title": session["title"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "archived": session["archived"],
            "user_id": session["user_id"],
            "status": session["status"],
            "last_message_preview": session["last_message_preview"],
            "hermes_stored_session_id": session["hermes_stored_session_id"],
        }
    finally:
        conn.close()


@router.get("/api/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    conn, device = _require_device_from_headers(
        request,
        authorization,
        x_device_id,
    )

    try:
        try:
            require_session_for_owner(
                conn,
                session_id=session_id,
                user_id=str(device["user_id"]),
                owner_device_id=str(device["device_id"]),
            )
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=error_response(
                    "session_not_found",
                    "Session does not exist or does not belong to this user.",
                ),
            )

        messages = list_messages_for_session(
            conn,
            session_id=session_id,
            user_id=str(device["user_id"]),
            owner_device_id=str(device["device_id"]),
        )

        return {
            "ok": True,
            "messages": messages,
        }
    finally:
        conn.close()


@router.delete("/api/sessions/{session_id}")
def delete_session(
    session_id: str,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    conn, device = _require_device_from_headers(
        request,
        authorization,
        x_device_id,
    )

    try:
        if get_active_chat_registry(request.app).is_active(session_id):
            raise HTTPException(
                status_code=409,
                detail=error_response(
                    "session_busy",
                    "Session has an active reply in progress.",
                ),
            )

        session = get_session_including_deleted(conn, session_id=session_id)
        if session is None:
            raise HTTPException(
                status_code=404,
                detail=error_response("session_not_found", "Session not found."),
            )

        user_id = str(device["user_id"])
        if (
            str(session["user_id"]) != user_id
            or str(session["owner_device_id"] or "") != str(device["device_id"])
        ):
            raise HTTPException(
                status_code=404,
                detail=error_response(
                    "session_not_found",
                    "Session not found.",
                ),
            )

        result = soft_delete_session(
            conn,
            session_id=session_id,
            user_id=user_id,
            owner_device_id=str(device["device_id"]),
        )
        response = {
            "ok": True,
            "action": "delete_session",
            "session_id": session_id,
            "deleted": result.deleted,
            "delete_mode": "soft",
            "deleted_at": result.deleted_at,
        }
        if not result.deleted:
            response["reason"] = "already_deleted"
        return response
    finally:
        conn.close()
