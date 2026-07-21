from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger("macsoft.api")


def error_response(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def _standard_error_detail(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("ok") is not False:
        return None
    error = value.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    message = error.get("message")
    details = error.get("details", {})
    if not isinstance(code, str) or not isinstance(message, str):
        return None
    if not isinstance(details, dict):
        details = {}
    return error_response(code, message, details=details)


def _status_code_name(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "permission_denied",
        404: "not_found",
        409: "conflict",
        410: "gone",
        422: "validation_error",
    }.get(status_code, "http_error")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        error: StarletteHTTPException,
    ) -> JSONResponse:
        del request
        standard = _standard_error_detail(error.detail)
        if standard is None:
            try:
                fallback = HTTPStatus(error.status_code).phrase
            except ValueError:
                fallback = "Request failed"
            message = error.detail if isinstance(error.detail, str) else fallback
            standard = error_response(
                _status_code_name(error.status_code),
                message,
            )
        return JSONResponse(
            status_code=error.status_code,
            content=standard,
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        del request
        issues = [
            {
                "location": [str(part) for part in issue.get("loc", ())],
                "message": str(issue.get("msg") or "Invalid value."),
                "type": str(issue.get("type") or "validation_error"),
            }
            for issue in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_response(
                "validation_error",
                "Request validation failed.",
                details={"errors": issues},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        error: Exception,
    ) -> JSONResponse:
        correlation_id = uuid4().hex
        logger.exception(
            "Unhandled API error correlation_id=%s method=%s path=%s error_type=%s",
            correlation_id,
            request.method,
            request.url.path,
            error.__class__.__name__,
        )
        return JSONResponse(
            status_code=500,
            content=error_response(
                "internal_error",
                "MacSoft Server could not complete the request.",
                details={"correlation_id": correlation_id},
            ),
        )
