from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response

from macsoft.artifacts.repository import get_visible_artifact, get_visible_artifact_file
from macsoft.artifacts.worker import resolve_artifact_storage
from macsoft.db import connect_db
from macsoft.gateway.errors import error_response
from macsoft.identity.devices import require_device


router = APIRouter()


def _device(conn, authorization: str | None, device_id: str | None):
    try:
        return require_device(conn, authorization=authorization, device_id=device_id)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail=error_response("invalid_device_token", "Device token is invalid or revoked."),
        )


def _expired() -> HTTPException:
    return HTTPException(
        status_code=410,
        detail=error_response("artifact_expired", "This chart artifact has expired."),
    )


@router.get("/api/artifacts/{artifact_id}/preview")
def preview_artifact(
    artifact_id: str,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> Response:
    conn = connect_db(request.app.state.config)
    try:
        device = _device(conn, authorization, x_device_id)
        artifact = get_visible_artifact(
            conn,
            artifact_id=artifact_id,
            owner_user_id=str(device["user_id"]),
            owner_device_id=str(device["device_id"]),
        )
        if artifact is None:
            raise HTTPException(status_code=404, detail=error_response("artifact_not_found", "Artifact not found."))
        if artifact["status"] == "expired":
            raise _expired()
        row = conn.execute(
            """
            SELECT * FROM artifact_files
            WHERE artifact_id = ? AND revision = ? AND format = 'png'
              AND status = 'available' AND deleted_at IS NULL
            """,
            (artifact_id, artifact["revision"]),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=error_response("artifact_preview_missing", "Preview is unavailable."))
        path = resolve_artifact_storage(request.app.state.config).final_path(str(row["storage_key"]))
        if not path.is_file():
            raise HTTPException(status_code=404, detail=error_response("artifact_preview_missing", "Preview is unavailable."))
        return Response(
            content=path.read_bytes(),
            media_type="image/png",
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": "inline",
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        conn.close()


@router.get("/api/artifacts/{artifact_id}/files/{file_id}")
def download_artifact_file(
    artifact_id: str,
    file_id: str,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> Response:
    conn = connect_db(request.app.state.config)
    try:
        device = _device(conn, authorization, x_device_id)
        row = get_visible_artifact_file(
            conn,
            artifact_id=artifact_id,
            file_id=file_id,
            owner_user_id=str(device["user_id"]),
            owner_device_id=str(device["device_id"]),
        )
        if row is None:
            raise HTTPException(status_code=404, detail=error_response("artifact_file_not_found", "Artifact file not found."))
        if row["artifact_status"] == "expired":
            raise _expired()
        path = resolve_artifact_storage(request.app.state.config).final_path(str(row["storage_key"]))
        if not path.is_file():
            raise HTTPException(status_code=404, detail=error_response("artifact_file_missing", "Artifact file is unavailable."))
        encoded = quote(str(row["filename"]), safe="")
        return Response(
            content=path.read_bytes(),
            media_type=str(row["content_type"]),
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        conn.close()
