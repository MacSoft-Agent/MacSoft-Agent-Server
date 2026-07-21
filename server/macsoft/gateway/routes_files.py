from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import Response

from macsoft.db import connect_db
from macsoft.files.storage import (
    MAX_UPLOAD_BYTES,
    UploadValidationError,
    create_uploaded_file,
    delete_owned_file,
    require_owned_file,
    stored_path,
)
from macsoft.identity.devices import require_device
from macsoft.gateway.errors import error_response


router = APIRouter()


def _require_request_device(conn, authorization: str | None, device_id: str | None):
    try:
        return require_device(conn, authorization=authorization, device_id=device_id)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail=error_response("invalid_device_token", "Device token is invalid or revoked."),
        )


def _record_response(record) -> dict:
    return {
        "ok": True,
        "file_id": record.file_id,
        "fileId": record.file_id,
        "filename": record.original_name,
        "content_type": record.media_type,
        "contentType": record.media_type,
        "size_bytes": record.size_bytes,
        "sizeBytes": record.size_bytes,
        "sha256": record.sha256,
        "created_at": record.created_at,
        "createdAt": record.created_at,
    }


@router.post("/api/files")
async def upload_client_file(
    request: Request,
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    config = request.app.state.config
    conn = connect_db(config)
    try:
        device = _require_request_device(conn, authorization, x_device_id)
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        try:
            record = create_uploaded_file(
                conn,
                config,
                owner_user_id=str(device["user_id"]),
                owner_device_id=str(device["device_id"]),
                filename=file.filename,
                data=data,
            )
        except UploadValidationError as error:
            raise HTTPException(status_code=422, detail=error_response(error.code, str(error)))
        return _record_response(record)
    finally:
        await file.close()
        conn.close()


@router.get("/api/files/{file_id}")
def download_client_file(
    file_id: str,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> Response:
    config = request.app.state.config
    conn = connect_db(config)
    try:
        device = _require_request_device(conn, authorization, x_device_id)
        try:
            record = require_owned_file(
                conn,
                file_id=file_id,
                owner_user_id=str(device["user_id"]),
                owner_device_id=str(device["device_id"]),
            )
        except ValueError:
            raise HTTPException(status_code=404, detail=error_response("file_not_found", "File was not found."))
        path = stored_path(config, record)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=error_response("file_not_found", "File was not found."))
        encoded_name = quote(record.original_name, safe="")
        return Response(
            content=data,
            media_type=record.media_type,
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        conn.close()


@router.delete("/api/files/{file_id}")
def delete_client_file(
    file_id: str,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    config = request.app.state.config
    conn = connect_db(config)
    try:
        device = _require_request_device(conn, authorization, x_device_id)
        try:
            record = delete_owned_file(
                conn,
                config,
                file_id=file_id,
                owner_user_id=str(device["user_id"]),
                owner_device_id=str(device["device_id"]),
            )
        except ValueError:
            raise HTTPException(status_code=404, detail=error_response("file_not_found", "File was not found."))
        return {"ok": True, "deleted": True, "file_id": record.file_id, "fileId": record.file_id}
    finally:
        conn.close()
