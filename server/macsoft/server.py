from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from macsoft.config import load_config
from macsoft.chat.active_runs import ActiveChatRunRegistry
from macsoft.admin.auth import AdminAccessRegistry
from macsoft.db import init_db
from macsoft.gateway.errors import register_exception_handlers
from macsoft.gateway.routes_chat import router as chat_router
from macsoft.gateway.routes_audio import router as audio_router
from macsoft.gateway.routes_admin import router as admin_router
from macsoft.gateway.routes_client import router as client_router
from macsoft.gateway.routes_files import router as files_router
from macsoft.gateway.routes_health import router as health_router
from macsoft.gateway.routes_sessions import router as sessions_router
from macsoft.gateway.routes_skills import router as skills_router
from macsoft.product import product_version


CLIENT_CORS_ORIGINS = [
    # Packaged Electron renders from file://, which Chromium serializes as
    # the opaque Origin value "null" for CORS preflight requests.
    "null",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
]


def create_app() -> FastAPI:
    config = load_config()

    init_db(config)

    app = FastAPI(
        title="MacSoft Server",
        version=product_version(),
    )

    app.state.config = config
    app.state.product_version = product_version()
    app.state.active_chat_runs = ActiveChatRunRegistry()
    app.state.admin_access_registry = AdminAccessRegistry()

    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        # The packaged file:// Client does not send an Origin header. These
        # explicit loopback origins support the Client development renderer.
        allow_origins=CLIENT_CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Device-Id",
            "X-Client-Version",
            "X-MacSoft-Client-Capabilities",
            "Accept",
        ],
    )

    app.include_router(health_router)
    app.include_router(client_router)
    app.include_router(sessions_router)
    app.include_router(skills_router)
    app.include_router(files_router)
    app.include_router(chat_router)
    app.include_router(audio_router)
    app.include_router(admin_router)

    return app


app = create_app()


def main() -> None:
    config = load_config()

    print("[MACSOFT_SERVER] starting")
    print(f"[MACSOFT_SERVER] host={config.server.host}")
    print(f"[MACSOFT_SERVER] port={config.server.port}")
    print(f"[MACSOFT_SERVER] hermes_home={config.hermes.home}")
    print(f"[MACSOFT_SERVER] hermes_api={config.hermes.api_base_url}")
    print(f"[MACSOFT_SERVER] runtime_mode={config.runtime.mode}")
    print("[MACSOFT_SERVER] db=ready")
    print("[MACSOFT_SERVER] client_pairing=ready")
    print("[MACSOFT_SERVER] sessions=ready")
    print("[MACSOFT_SERVER] chat_stream=hermes-bridge-ready")

    uvicorn.run(
        "macsoft.server:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
