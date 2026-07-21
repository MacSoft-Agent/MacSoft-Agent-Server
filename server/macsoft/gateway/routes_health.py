from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    config = request.app.state.config

    return {
        "ok": True,
        "status": "ok",
        "server": "MacSoft Server",
        "version": request.app.state.product_version,
        "host": config.server.host,
        "port": config.server.port,
        "runtime_mode": config.runtime.mode,
        "autocount_enabled": config.autocount.enabled,
        "time": datetime.now(timezone.utc).isoformat(),
    }
