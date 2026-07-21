from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask

from macsoft.admin.auth import bootstrap_response, require_admin
from macsoft.admin.message_store import list_admin_context, list_admin_messages, save_admin_message
from macsoft.admin.session_store import (
    create_admin_session,
    get_admin_session,
    list_admin_sessions,
    soft_delete_admin_session,
)
from macsoft.chat.active_runs import get_active_chat_registry
from macsoft.chat.activity import ActivityKind, ActivityMapper, ActivityStatus
from macsoft.chat.capability_policy import build_protected_system_instruction, enforce_capability_boundary
from macsoft.chat.hermes_client import HermesApiError, stream_hermes_reply_events
from macsoft.chat.result_formatter import format_assistant_reply, format_error_markdown, map_user_readable_error, user_requested_json
from macsoft.db import connect_db
from macsoft.gateway.routes_chat import MAX_CHAT_MESSAGE_BYTES, MAX_CHAT_MESSAGE_CHARS, SERVER_HERMES_MODEL_ID, sse_event
from macsoft.security import new_id


router = APIRouter()


class AdminSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "New Admin Chat"


class AdminChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message: str
    uploaded_file_ids: list[str] = Field(default_factory=list)


def _error(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message, "details": {}}}


def _require_session(request: Request, session_id: str):
    conn = connect_db(request.app.state.config)
    try:
        session = get_admin_session(conn, session_id)
    finally:
        conn.close()
    if session is None:
        raise HTTPException(status_code=404, detail=_error("admin_session_not_found", "Admin session does not exist."))
    return session


@router.post("/api/internal/desktop-admin/auth/session")
def bootstrap_admin_session(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    return bootstrap_response(request, authorization)


@router.get("/api/admin/sessions")
def get_admin_sessions(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    require_admin(request, authorization)
    conn = connect_db(request.app.state.config)
    try:
        return {"ok": True, "sessions": list_admin_sessions(conn)}
    finally:
        conn.close()


@router.post("/api/admin/sessions")
def post_admin_session(
    request: Request,
    body: AdminSessionRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    require_admin(request, authorization)
    conn = connect_db(request.app.state.config)
    try:
        return {"ok": True, "session": create_admin_session(conn, body.title)}
    finally:
        conn.close()


@router.get("/api/admin/sessions/{session_id}/messages")
def get_admin_session_messages(
    request: Request,
    session_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    require_admin(request, authorization)
    _require_session(request, session_id)
    conn = connect_db(request.app.state.config)
    try:
        return {"ok": True, "session_id": session_id, "messages": list_admin_messages(conn, session_id)}
    finally:
        conn.close()


@router.delete("/api/admin/sessions/{session_id}")
def delete_admin_session(
    request: Request,
    session_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    require_admin(request, authorization)
    _require_session(request, session_id)
    registry = get_active_chat_registry(request.app)
    run_key = f"admin:{session_id}"
    if registry.is_active(run_key):
        raise HTTPException(status_code=409, detail=_error("admin_session_busy", "Admin session has an active reply."))
    conn = connect_db(request.app.state.config)
    try:
        soft_delete_admin_session(conn, session_id)
        return {"ok": True, "session_id": session_id, "deleted": True}
    finally:
        conn.close()


@router.post("/api/admin/chat/stream")
def admin_chat_stream(
    request: Request,
    body: AdminChatRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> StreamingResponse:
    require_admin(request, authorization)
    config = request.app.state.config
    conn = connect_db(config)
    registry = get_active_chat_registry(request.app)
    run_key = f"admin:{body.session_id}"
    reserved = False

    try:
        if body.uploaded_file_ids:
            raise HTTPException(status_code=422, detail=_error("attachments_not_supported", "Attachments are not supported by Admin chat."))
        if not body.message.strip():
            raise HTTPException(status_code=422, detail=_error("blank_message", "Message must contain non-whitespace content."))
        if len(body.message) > MAX_CHAT_MESSAGE_CHARS or len(body.message.encode("utf-8")) > MAX_CHAT_MESSAGE_BYTES:
            raise HTTPException(status_code=422, detail=_error("message_too_large", "Message exceeds the supported request size."))
        if get_admin_session(conn, body.session_id) is None:
            raise HTTPException(status_code=404, detail=_error("admin_session_not_found", "Admin session does not exist."))
        if not registry.reserve(run_key):
            raise HTTPException(status_code=409, detail=_error("admin_session_busy", "Admin session already has an active reply."))
        reserved = True

        if get_admin_session(conn, body.session_id) is None:
            raise HTTPException(status_code=404, detail=_error("admin_session_not_found", "Admin session does not exist."))

        user_message = save_admin_message(conn, session_id=body.session_id, role="user", content=body.message)
        hermes_messages = [{"role": "system", "content": build_protected_system_instruction(
            None,
            "The user is operating MacSoft Server from the trusted local Server Desktop. "
            "Do not invent privileged management capabilities or claim actions were performed.",
        )}]
        hermes_messages.extend(list_admin_context(conn, body.session_id))
        assistant_message_id = new_id("admin_msg")

        def event_stream() -> Iterator[str]:
            assistant_text = ""
            request_ok = True
            mapper = ActivityMapper(message_id=assistant_message_id, enabled=True)
            try:
                yield sse_event("message_start", {"message_id": assistant_message_id, "session_id": body.session_id, "model": SERVER_HERMES_MODEL_ID})
                activity = mapper.activity(
                    activity_id="request_received",
                    kind=ActivityKind.ANALYSIS,
                    status=ActivityStatus.COMPLETED,
                    title="Request received",
                )
                if activity is not None:
                    yield sse_event("activity", activity)
                try:
                    parts: list[str] = []
                    for internal_event in stream_hermes_reply_events(
                        base_url=config.hermes.api_base_url,
                        api_key=config.hermes.api_key,
                        messages=hermes_messages,
                        timeout_seconds=config.hermes.request_timeout_seconds,
                    ):
                        if internal_event.get("type") == "text_delta":
                            parts.append(str(internal_event.get("text") or ""))
                            continue
                        mapped = mapper.observed_tool_event(internal_event)
                        if mapped is not None:
                            yield sse_event("activity", mapped)
                    assistant_text = enforce_capability_boundary(
                        user_message=body.message,
                        assistant_text=format_assistant_reply(
                            "".join(parts).strip(),
                            preserve_json=user_requested_json(body.message),
                        ),
                    )
                except HermesApiError as error:
                    request_ok = False
                    readable = map_user_readable_error(str(error), service=error.service, kind=error.kind, status_code=error.status_code)
                    assistant_text = format_error_markdown(readable)

                stream_conn = connect_db(config)
                try:
                    assistant_message = save_admin_message(
                        stream_conn,
                        session_id=body.session_id,
                        role="assistant",
                        content=assistant_text,
                        model=SERVER_HERMES_MODEL_ID,
                        message_id=assistant_message_id,
                    )
                except Exception:
                    persistence_error = _error("assistant_persistence_failed", "The generated reply could not be saved.")
                    yield sse_event("error", persistence_error)
                    yield sse_event("message_done", {"ok": False, "session_id": body.session_id, "error": persistence_error["error"]})
                    return
                finally:
                    stream_conn.close()

                yield sse_event("token_delta", {"text": assistant_text})
                yield sse_event("message_done", {
                    "ok": request_ok,
                    "message_id": assistant_message["message_id"],
                    "session_id": body.session_id,
                    "user_message_id": user_message["message_id"],
                    "model": SERVER_HERMES_MODEL_ID,
                })
            except GeneratorExit:
                raise
            except Exception:
                yield sse_event("error", _error("admin_chat_failed", "Admin chat could not complete the request."))
            finally:
                mapper.close()
                registry.release(run_key)

        response = StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            background=BackgroundTask(registry.release, run_key),
        )
        reserved = False
        return response
    finally:
        if reserved:
            registry.release(run_key)
        conn.close()
