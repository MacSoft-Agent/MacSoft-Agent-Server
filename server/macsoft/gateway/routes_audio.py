from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from macsoft.db import connect_db
from macsoft.gateway.errors import (
    device_credentials_rejected_error,
    error_response as _error_response,
)
from macsoft.identity.devices import require_device


router = APIRouter(prefix="/api/client/audio", tags=["client-audio"])

MAX_TRANSCRIPTION_DATA_URL_CHARS = 35_000_000
DEFAULT_CONFIG_API_URL = "http://127.0.0.1:8643"
TRANSCRIPTION_TIMEOUT_SECONDS = 120.0


def error_response(code: str, message: str) -> dict:
    if code == "invalid_device_token":
        return device_credentials_rejected_error()
    return _error_response(code, message)


class AudioTranscriptionRequest(BaseModel):
    data_url: str = Field(min_length=1, max_length=MAX_TRANSCRIPTION_DATA_URL_CHARS)
    mime_type: str | None = Field(default=None, max_length=128)
    language: str | None = Field(default=None, pattern="^(en|zh|ja)$")


def _require_request_device(request: Request, authorization: str | None, device_id: str | None) -> None:
    conn = connect_db(request.app.state.config)
    try:
        try:
            require_device(conn, authorization=authorization, device_id=device_id)
        except ValueError:
            raise HTTPException(
                status_code=401,
                detail=error_response("invalid_device_token", "Device token is invalid or revoked."),
            )
    finally:
        conn.close()


@router.post("/transcribe")
def transcribe_client_audio(
    request: Request,
    body: AudioTranscriptionRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> Response:
    _require_request_device(request, authorization, x_device_id)

    session_token = os.environ.get("MACSOFT_HOST_CONTROL_TOKEN", "").strip()
    if not session_token:
        raise HTTPException(
            status_code=503,
            detail=error_response("transcription_unavailable", "Voice transcription service is unavailable."),
        )

    base_url = os.environ.get("MACSOFT_HERMES_CONFIG_API_URL", DEFAULT_CONFIG_API_URL).rstrip("/")
    try:
        upstream = httpx.post(
            f"{base_url}/api/audio/transcribe",
            headers={
                "Content-Type": "application/json",
                "X-Hermes-Session-Token": session_token,
            },
            json=body.model_dump(),
            timeout=TRANSCRIPTION_TIMEOUT_SECONDS,
        )
    except (httpx.TimeoutException, httpx.NetworkError):
        raise HTTPException(
            status_code=503,
            detail=error_response("transcription_unavailable", "Voice transcription service is unavailable."),
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json").split(";", 1)[0],
        headers={"Cache-Control": "no-store"},
    )
