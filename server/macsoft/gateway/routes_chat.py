from __future__ import annotations

import json
import re
from collections.abc import Iterator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from macsoft.chat.active_runs import get_active_chat_registry
from macsoft.chat.activity import (
    ActivityKind,
    ActivityMapper,
    ActivityStatus,
    supports_activity_v1,
)
from macsoft.chat.capability_policy import (
    build_protected_system_instruction,
    enforce_capability_boundary,
)
from macsoft.chat.hermes_client import (
    HermesApiError,
    interrupt_hermes_run,
    stream_interruptible_hermes_reply_events,
)
from macsoft.chat.result_formatter import (
    format_assistant_reply,
    format_error_markdown,
    map_ai_service_response_error,
    map_user_readable_error,
    user_requested_json,
)
from macsoft.db import connect_db
from macsoft.gateway.errors import device_credentials_rejected_error
from macsoft.files.content import AttachmentContentError, build_hermes_user_content
from macsoft.files.storage import (
    UploadValidationError,
    attach_owned_files_to_message,
    list_owned_files_for_message,
    require_owned_files,
)
from macsoft.identity.devices import require_device
from macsoft.security import new_id
from macsoft.sessions.message_store import (
    list_ai_context_messages_for_session,
    save_message,
)
from macsoft.sessions.session_store import require_session_for_owner
from macsoft.skills.client_skills import (
    build_client_skill_system_instruction,
    resolve_selected_client_skills,
)

router = APIRouter()

SERVER_HERMES_MODEL_ID = "server-hermes-current"
MAX_CHAT_MESSAGE_CHARS = 16_000
MAX_CHAT_MESSAGE_BYTES = 32_000
_HTML_DOCUMENT_RE = re.compile(
    r"^\s*<!doctype\s+html\s*>\s*<html\b[\s\S]*</html>\s*$",
    re.IGNORECASE,
)
_HTML_DOCUMENT_EXTRACT_RE = re.compile(
    r"(<!doctype\s+html\s*>\s*<html\b[\s\S]*</html\s*>)",
    re.IGNORECASE,
)
from macsoft.profiles.registry import require_device_profile
from macsoft.profiles.runs import record_run_finished, record_run_started
from macsoft.global_learning.homes import read_approved_global_memory

# Keep the established test/extension seam name while routing it through the
# structured Runs implementation.  This is not the legacy chat-completions
# transport: the alias still starts /v1/runs and consumes its event stream.
stream_hermes_reply_events = stream_interruptible_hermes_reply_events


def request_hermes_reply(
    *,
    base_url: str,
    api_key: str,
    profile_id: str,
    messages: list[dict],
    session_id: str,
    timeout_seconds: int,
    on_run_started,
) -> str:
    parts: list[str] = []
    for event in stream_hermes_reply_events(
        base_url=base_url,
        api_key=api_key,
        profile_id=profile_id,
        messages=messages,
        session_id=session_id,
        timeout_seconds=timeout_seconds,
        on_run_started=on_run_started,
    ):
        if event.get("type") == "interrupted":
            raise HermesApiError("MacSoft Agent run was interrupted.", kind="interrupted")
        if event.get("type") == "text_delta":
            parts.append(str(event.get("text") or ""))
    return "".join(parts)


def is_complete_html_document(content: str) -> bool:
    """Match the raw HTML document contract consumed by the Client."""
    return isinstance(content, str) and bool(_HTML_DOCUMENT_RE.match(content))


def extract_complete_html_document(content: str) -> str | None:
    """Extract one complete HTML document from a model response.

    Models sometimes add a short explanation, a ``Code`` label, or a Markdown
    code fence around an otherwise valid dashboard.  The Client dashboard
    renderer must receive only the document, while the normal assistant text
    remains unchanged for transcript compatibility.
    """
    if not isinstance(content, str):
        return None
    match = _HTML_DOCUMENT_EXTRACT_RE.search(content)
    if match is None:
        return None
    document = match.group(1).strip()
    return document if is_complete_html_document(document) else None


class ChatStreamRequest(BaseModel):
    session_id: str
    message: str
    preferred_model_id: str | None = None
    enabled_private_skills: list[dict] = Field(default_factory=list)
    uploaded_file_ids: list[str] = Field(default_factory=list)
    client_info: dict = Field(default_factory=dict)


class ChatInterruptRequest(BaseModel):
    session_id: str


def error_response(code: str, message: str) -> dict:
    if code == "invalid_device_token":
        return device_credentials_rejected_error()
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": {},
        },
    }


def sse_event(event_name: str, data: dict) -> str:
    return (
        f"event: {event_name}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


def activity_sse(
    mapper: ActivityMapper,
    *,
    activity_id: str,
    kind: ActivityKind,
    status: ActivityStatus,
    title: str,
    detail: str | None = None,
) -> str | None:
    try:
        data = mapper.activity(
            activity_id=activity_id,
            kind=kind,
            status=status,
            title=title,
            detail=detail,
        )
        return sse_event("activity", data) if data is not None else None
    except Exception as error:
        print(
            "[MACSOFT_ACTIVITY] mapping failed; continuing chat stream. "
            f"error_type={error.__class__.__name__}"
        )
        return None


@router.post("/api/chat/interrupt")
def interrupt_chat(
    request: Request,
    body: ChatInterruptRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    """Stop only the authenticated device's active Hermes Run."""
    config = request.app.state.config
    conn = connect_db(config)
    try:
        try:
            device = require_device(
                conn, authorization=authorization, device_id=x_device_id
            )
        except ValueError as error:
            raise HTTPException(
                status_code=401,
                detail=error_response(
                    "invalid_device_token", "Device token is invalid or revoked."
                ),
            ) from error
        device_id = str(device["device_id"])
        try:
            require_session_for_owner(
                conn,
                session_id=body.session_id,
                user_id=str(device["user_id"]),
                owner_device_id=device_id,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=404,
                detail=error_response(
                    "session_not_found",
                    "Session does not exist or does not belong to this device.",
                ),
            ) from error
        profile_id = str(
            require_device_profile(conn, config=config, device_id=device_id)["profile_id"]
        )
    finally:
        conn.close()

    active, run_id = get_active_chat_registry(request.app).request_interrupt(
        body.session_id
    )
    if not active:
        raise HTTPException(
            status_code=409,
            detail=error_response(
                "chat_run_not_active", "This session has no active reply."
            ),
        )
    if run_id:
        try:
            interrupt_hermes_run(
                base_url=config.hermes.api_base_url,
                api_key=config.hermes.api_key,
                profile_id=profile_id,
                run_id=run_id,
                timeout_seconds=config.hermes.request_timeout_seconds,
            )
        except HermesApiError as error:
            raise HTTPException(
                status_code=502,
                detail=error_response(
                    "chat_interrupt_failed", "The active Agent run could not be stopped."
                ),
            ) from error
    return {
        "ok": True,
        "session_id": body.session_id,
        "status": "interrupting",
        "upstream_run_bound": run_id is not None,
    }


@router.post("/api/chat/stream")
def chat_stream(
    request: Request,
    body: ChatStreamRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_macsoft_client_capabilities: str | None = Header(
        default=None,
        alias="X-MacSoft-Client-Capabilities",
    ),
) -> StreamingResponse:
    config = request.app.state.config
    conn = connect_db(config)
    registry = get_active_chat_registry(request.app)
    reservation_owned_by_response = False
    session_reserved = False

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

        user_id = str(device["user_id"])
        device_id = str(device["device_id"])
        profile_id = str(
            require_device_profile(conn, config=config, device_id=device_id)["profile_id"]
        )

        try:
            require_session_for_owner(
                conn,
                session_id=body.session_id,
                user_id=user_id,
                owner_device_id=device_id,
            )
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=error_response(
                    "session_not_found",
                    "Session does not exist or does not belong to this user.",
                ),
            )

        try:
            uploaded_files = require_owned_files(
                conn,
                file_ids=body.uploaded_file_ids,
                owner_user_id=user_id,
                owner_device_id=device_id,
            )
        except UploadValidationError as error:
            raise HTTPException(
                status_code=422,
                detail=error_response(error.code, str(error)),
            )
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=error_response(
                    "file_not_found",
                    "One or more uploaded files were not found for this device.",
                ),
            )
        if not body.message.strip():
            raise HTTPException(
                status_code=422,
                detail=error_response(
                    "blank_message",
                    "Message must contain non-whitespace content.",
                ),
            )
        if (
            len(body.message) > MAX_CHAT_MESSAGE_CHARS
            or len(body.message.encode("utf-8")) > MAX_CHAT_MESSAGE_BYTES
        ):
            raise HTTPException(
                status_code=422,
                detail=error_response(
                    "message_too_large",
                    "Message exceeds the supported request size.",
                ),
            )

        try:
            current_user_content = build_hermes_user_content(
                config,
                message=body.message,
                files=uploaded_files,
            )
        except AttachmentContentError as error:
            raise HTTPException(
                status_code=422,
                detail=error_response(error.code, str(error)),
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=error_response(
                    "file_not_found",
                    "One or more uploaded files are no longer available.",
                ),
            )

        if not registry.reserve(body.session_id):
            raise HTTPException(
                status_code=409,
                detail=error_response(
                    "session_busy",
                    "Session already has an active reply in progress.",
                ),
            )
        session_reserved = True

        try:
            # Close the narrow delete/reserve race: after reservation, confirm
            # the session still exists before the first message write.
            try:
                require_session_for_owner(
                    conn,
                    session_id=body.session_id,
                    user_id=user_id,
                    owner_device_id=device_id,
                )
            except ValueError:
                raise HTTPException(
                    status_code=404,
                    detail=error_response(
                        "session_not_found",
                        "Session does not exist or does not belong to this user.",
                    ),
                )

            current_model = SERVER_HERMES_MODEL_ID

            if body.preferred_model_id:
                print(
                    "[MACSOFT_CHAT] preferred_model_id ignored; "
                    "server Hermes current model owns model selection. "
                    f"preferred_model_id={body.preferred_model_id}"
                )

            user_message = save_message(
                conn,
                session_id=body.session_id,
                user_id=user_id,
                owner_device_id=device_id,
                role="user",
                content=body.message,
                model=None,
            )
            attach_owned_files_to_message(
                conn,
                message_id=str(user_message["message_id"]),
                owner_user_id=user_id,
                owner_device_id=device_id,
                file_ids=body.uploaded_file_ids,
            )

            context_window = list_ai_context_messages_for_session(
                conn,
                session_id=body.session_id,
                user_id=user_id,
                owner_device_id=device_id,
                current_message_id=str(user_message["message_id"]),
            )

            hermes_messages = [
                {
                    "message_id": str(message["message_id"]),
                    "role": str(message["role"]),
                    "content": str(message["content"]),
                }
                for message in context_window.messages
            ]
            if uploaded_files:
                for message in reversed(hermes_messages):
                    if message["role"] == "user":
                        message["content"] = current_user_content
                        break
            else:
                for message in hermes_messages:
                    if message["role"] != "user":
                        continue
                    historical_files = list_owned_files_for_message(
                        conn,
                        message_id=str(message["message_id"]),
                        owner_user_id=user_id,
                        owner_device_id=device_id,
                    )
                    if historical_files:
                        message["content"] = build_hermes_user_content(
                            config,
                            message=str(message["content"]),
                            files=historical_files,
                        )

            selected_client_skills = resolve_selected_client_skills(
                conn,
                owner_user_id=user_id,
                owner_device_id=device_id,
                requested=body.enabled_private_skills,
            )
            client_skill_instruction = build_client_skill_system_instruction(
                selected_client_skills,
            )
            hermes_messages.insert(
                0,
                {
                    "role": "system",
                    "content": build_protected_system_instruction(
                        client_skill_instruction,
                        global_learning_instruction=read_approved_global_memory(config),
                    ),
                },
            )

            assistant_message_id = new_id("msg_assistant")
            activity_enabled = supports_activity_v1(x_macsoft_client_capabilities)
            run_state: dict[str, str | bool | None] = {"run_id": None, "finished": False}

            def on_run_started(run_id: str) -> bool:
                run_state["run_id"] = run_id
                run_conn = connect_db(config)
                try:
                    record_run_started(
                        run_conn,
                        run_id=run_id,
                        device_id=device_id,
                        profile_id=profile_id,
                        session_id=body.session_id,
                    )
                finally:
                    run_conn.close()
                return registry.bind_run(body.session_id, run_id)

            def finish_run(*, completion_status: str, learning_status: str) -> None:
                run_id = run_state["run_id"]
                if not isinstance(run_id, str) or run_state["finished"]:
                    return
                run_conn = connect_db(config)
                try:
                    record_run_finished(
                        run_conn,
                        run_id=run_id,
                        completion_status=completion_status,
                        learning_status=learning_status,
                    )
                    run_state["finished"] = True
                finally:
                    run_conn.close()

            def request_final_reply() -> str:
                raw_assistant_text = request_hermes_reply(
                    base_url=config.hermes.api_base_url,
                    api_key=config.hermes.api_key,
                    profile_id=profile_id,
                    messages=hermes_messages,
                    session_id=body.session_id,
                    timeout_seconds=config.hermes.request_timeout_seconds,
                    on_run_started=on_run_started,
                )
                return enforce_capability_boundary(
                    user_message=body.message,
                    assistant_text=format_assistant_reply(
                        raw_assistant_text,
                        preserve_json=user_requested_json(body.message),
                    ),
                )

            def format_final_reply(raw_assistant_text: str) -> str:
                return enforce_capability_boundary(
                    user_message=body.message,
                    assistant_text=format_assistant_reply(
                        raw_assistant_text,
                        preserve_json=user_requested_json(body.message),
                    ),
                )

            legacy_assistant_text: str | None = None
            if not activity_enabled:
                try:
                    legacy_assistant_text = request_final_reply()
                    finish_run(completion_status="completed", learning_status="eligible")
                except HermesApiError as error:
                    finish_run(
                        completion_status=(
                            "cancelled" if error.kind == "interrupted" else "failed"
                        ),
                        learning_status="skipped",
                    )
                    readable_error = map_user_readable_error(
                        str(error),
                        service=error.service,
                        kind=error.kind,
                        status_code=error.status_code,
                    )
                    print(
                        "[MACSOFT_AI_SERVICE] request failed before legacy stream. "
                        f"error_type={error.__class__.__name__} "
                        f"error_kind={error.kind} status_code={error.status_code}"
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=error_response(
                            "ai_service_authentication_failed"
                            if error.status_code == 401
                            else "hermes_unavailable",
                            readable_error.detail,
                        ),
                    )

            def event_stream() -> Iterator[str]:
                try:
                    yield sse_event(
                        "message_start",
                        {
                            "message_id": assistant_message_id,
                            "session_id": body.session_id,
                            "model": current_model,
                        },
                    )

                    activity_mapper = ActivityMapper(
                        message_id=assistant_message_id,
                        enabled=activity_enabled,
                    )

                    request_ok = True
                    if activity_enabled:
                        activity_event = activity_sse(
                            activity_mapper,
                            activity_id="request_received",
                            kind=ActivityKind.ANALYSIS,
                            status=ActivityStatus.COMPLETED,
                            title="Request received",
                        )
                        if activity_event is not None:
                            yield activity_event

                        if selected_client_skills:
                            activity_event = activity_sse(
                                activity_mapper,
                                activity_id="client_skill_selected",
                                kind=ActivityKind.ANALYSIS,
                                status=ActivityStatus.COMPLETED,
                                title="Client preferences selected",
                                detail=f"Applied {len(selected_client_skills)} enabled Client Skill(s) to this request.",
                            )
                            if activity_event is not None:
                                yield activity_event

                        activity_event = activity_sse(
                            activity_mapper,
                            activity_id="agent_processing",
                            kind=ActivityKind.EXTERNAL_REQUEST,
                            status=ActivityStatus.STARTED,
                            title="MacSoft Agent is processing the request",
                        )
                        if activity_event is not None:
                            yield activity_event

                        try:
                            raw_parts: list[str] = []
                            for internal_event in stream_hermes_reply_events(
                                base_url=config.hermes.api_base_url,
                                api_key=config.hermes.api_key,
                                profile_id=profile_id,
                                messages=hermes_messages,
                                session_id=body.session_id,
                                timeout_seconds=config.hermes.request_timeout_seconds,
                                on_run_started=on_run_started,
                            ):
                                if internal_event.get("type") == "text_delta":
                                    raw_parts.append(str(internal_event.get("text") or ""))
                                    continue
                                if internal_event.get("type") == "interrupted":
                                    raise HermesApiError(
                                        "MacSoft Agent run was interrupted.",
                                        kind="interrupted",
                                    )
                                try:
                                    mapped_activity = activity_mapper.observed_tool_event(
                                        internal_event,
                                    )
                                except Exception as error:
                                    print(
                                        "[MACSOFT_ACTIVITY] Tool event mapping failed; "
                                        "continuing chat stream. "
                                        f"error_type={error.__class__.__name__}"
                                    )
                                    mapped_activity = None
                                if mapped_activity is not None:
                                    yield sse_event("activity", mapped_activity)
                            raw_assistant_text = "".join(raw_parts).strip()
                            ai_response_error = map_ai_service_response_error(
                                raw_assistant_text,
                            )
                            if ai_response_error is not None:
                                # The internal AI Service reports some upstream provider
                                # failures as sanitized assistant content over HTTP 200.
                                # Preserve that safety boundary while marking the request
                                # failed and giving the Client an actionable explanation.
                                request_ok = False
                                readable_error = ai_response_error
                                assistant_text = format_error_markdown(ai_response_error)
                            else:
                                assistant_text = format_final_reply(raw_assistant_text)
                                finish_run(completion_status="completed", learning_status="eligible")
                        except HermesApiError as error:
                            finish_run(
                                completion_status=(
                                    "cancelled"
                                    if error.kind == "interrupted"
                                    else "failed"
                                ),
                                learning_status="skipped",
                            )
                            request_ok = False
                            readable_error = map_user_readable_error(
                                str(error),
                                service=error.service,
                                kind=error.kind,
                                status_code=error.status_code,
                            )
                            assistant_text = format_error_markdown(readable_error)
                            print(
                                "[MACSOFT_AI_SERVICE] request failed; returning a sanitized "
                                f"assistant result. error_type={error.__class__.__name__} "
                                f"error_kind={error.kind} status_code={error.status_code}"
                            )
                    else:
                        if legacy_assistant_text is None:
                            raise RuntimeError("Legacy assistant reply was not prepared.")
                        assistant_text = legacy_assistant_text

                    stream_conn = connect_db(config)

                    try:
                        try:
                            assistant_message = save_message(
                                stream_conn,
                                session_id=body.session_id,
                                user_id=user_id,
                                owner_device_id=device_id,
                                role="assistant",
                                content=assistant_text,
                                model=current_model,
                                message_id=assistant_message_id,
                            )
                        except Exception as error:
                            activity_mapper.close()
                            print(
                                "[MACSOFT_CHAT] Assistant persistence failed. "
                                f"error_type={error.__class__.__name__}"
                            )
                            persistence_error = error_response(
                                "assistant_persistence_failed",
                                "The generated reply could not be saved.",
                            )
                            yield sse_event("error", persistence_error)
                            yield sse_event(
                                "message_done",
                                {
                                    "ok": False,
                                    "message_id": assistant_message_id,
                                    "session_id": body.session_id,
                                    "user_message_id": user_message["message_id"],
                                    "model": current_model,
                                    "error": persistence_error["error"],
                                },
                            )
                            return
                    finally:
                        stream_conn.close()

                    if activity_enabled:
                        if request_ok:
                            activity_event = activity_sse(
                                activity_mapper,
                                activity_id="agent_processing",
                                kind=ActivityKind.EXTERNAL_REQUEST,
                                status=ActivityStatus.COMPLETED,
                                title="MacSoft Agent finished processing",
                            )
                            if activity_event is not None:
                                yield activity_event

                            activity_event = activity_sse(
                                activity_mapper,
                                activity_id="prepare_response",
                                kind=ActivityKind.FINALIZE,
                                status=ActivityStatus.STARTED,
                                title="Preparing the response",
                            )
                            if activity_event is not None:
                                yield activity_event

                            activity_event = activity_sse(
                                activity_mapper,
                                activity_id="prepare_response",
                                kind=ActivityKind.FINALIZE,
                                status=ActivityStatus.COMPLETED,
                                title="Response prepared",
                            )
                            if activity_event is not None:
                                yield activity_event
                        else:
                            activity_event = activity_sse(
                                activity_mapper,
                                activity_id="agent_processing",
                                kind=ActivityKind.WARNING,
                                status=ActivityStatus.FAILED,
                                title="Request failed",
                                detail=readable_error.detail,
                            )
                            if activity_event is not None:
                                yield activity_event

                    yield sse_event(
                        "token_delta",
                        {
                            "text": assistant_text,
                        },
                    )

                    html_document = extract_complete_html_document(assistant_text)
                    if html_document is not None:
                        yield sse_event(
                            "html_document",
                            {
                                "schema_version": 1,
                                "document_id": f"{assistant_message_id}:html",
                                "message_id": assistant_message_id,
                                "session_id": body.session_id,
                                "mime_type": "text/html",
                                "html": html_document,
                            },
                        )

                    if request_ok:
                        activity_event = activity_sse(
                            activity_mapper,
                            activity_id="request",
                            kind=ActivityKind.FINALIZE,
                            status=ActivityStatus.COMPLETED,
                            title="Request completed",
                        )
                        if activity_event is not None:
                            yield activity_event

                    activity_mapper.close()
                    yield sse_event(
                        "message_done",
                        {
                            "ok": request_ok,
                            "message_id": assistant_message["message_id"],
                            "session_id": body.session_id,
                            "user_message_id": user_message["message_id"],
                            "model": current_model,
                        },
                    )
                finally:
                    run_id = run_state["run_id"]
                    if isinstance(run_id, str) and not run_state["finished"]:
                        try:
                            interrupt_hermes_run(
                                base_url=config.hermes.api_base_url,
                                api_key=config.hermes.api_key,
                                profile_id=profile_id,
                                run_id=run_id,
                                timeout_seconds=config.hermes.request_timeout_seconds,
                            )
                        except HermesApiError:
                            # The Run may have reached a terminal state between
                            # disconnect detection and this best-effort stop.
                            pass
                    finish_run(completion_status="cancelled", learning_status="skipped")
                    registry.release(body.session_id)

            response = StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
                background=BackgroundTask(registry.release, body.session_id),
            )
            reservation_owned_by_response = True
            return response
        finally:
            if session_reserved and not reservation_owned_by_response:
                registry.release(body.session_id)
    finally:
        conn.close()
