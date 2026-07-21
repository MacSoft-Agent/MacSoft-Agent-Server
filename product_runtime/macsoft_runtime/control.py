from __future__ import annotations

import json
import secrets
import threading
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .host import MacSoftAgentHost, sanitize_error


DEFAULT_CONTROL_PORT = 8766


def load_or_create_control_token(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        token = value.get("token")
        if isinstance(token, str) and len(token) >= 32:
            return token
    except (OSError, ValueError, TypeError):
        pass
    token = secrets.token_urlsafe(32)
    path.write_text(json.dumps({"host": "127.0.0.1", "port": DEFAULT_CONTROL_PORT, "token": token}, indent=2) + "\n", encoding="utf-8")
    return token


class HostControlServer:
    def __init__(self, host: MacSoftAgentHost, port: int = DEFAULT_CONTROL_PORT) -> None:
        self.host = host
        self.port = port
        self.token = load_or_create_control_token(host.paths.host_control_file)
        config_backend = host.specs.get("config_backend")
        if config_backend is not None:
            # Reuse the existing authenticated Host-control secret for the
            # localhost-only Hermes configuration backend. Electron main
            # already reads this secret; it is never exposed to the renderer.
            config_backend.environment["HERMES_DASHBOARD_SESSION_TOKEN"] = self.token
        server = host.specs.get("server")
        if server is not None:
            server.environment["MACSOFT_HOST_CONTROL_TOKEN"] = self.token
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "MacSoftHostControl/1"

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _send(self, status: int, body: dict[str, Any]) -> None:
                data = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def _authorized(self) -> bool:
                supplied = self.headers.get("Authorization", "")
                return secrets.compare_digest(supplied, f"Bearer {owner.token}")

            def do_GET(self) -> None:
                if not self._authorized():
                    self._send(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                    return
                if self.path == "/v1/status":
                    self._send(HTTPStatus.OK, {"ok": True, **owner.host.status()})
                elif self.path == "/v1/pairing-code":
                    try:
                        self._send(
                            HTTPStatus.OK,
                            {"ok": True, "pairing_code": owner._pairing_code()},
                        )
                    except RuntimeError as error:
                        self._send(
                            HTTPStatus.CONFLICT,
                            {
                                "ok": False,
                                "error": "pairing_code_unavailable",
                                "message": sanitize_error(error, owner.host.paths),
                            },
                        )
                else:
                    self._send(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

            def do_POST(self) -> None:
                if not self._authorized():
                    self._send(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                    return
                try:
                    if self.path == "/v1/autostart":
                        length = min(int(self.headers.get("Content-Length", "0")), 4096)
                        body = json.loads(self.rfile.read(length) or b"{}")
                        enabled = owner.host.set_auto_start(bool(body.get("enabled")))
                        self._send(HTTPStatus.OK, {"ok": True, "auto_start": enabled})
                        return
                    parts = self.path.strip("/").split("/")
                    if len(parts) == 4 and parts[:2] == ["v1", "services"]:
                        name, action = parts[2], parts[3]
                        if action not in {"start", "stop", "restart"}:
                            raise ValueError("Unsupported service action.")
                        result = getattr(owner.host, action)(name)
                        self._send(HTTPStatus.OK, {"ok": True, "service": result})
                        return
                    self._send(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                except (RuntimeError, ValueError) as error:
                    self._send(
                        HTTPStatus.CONFLICT,
                        {"ok": False, "error": "service_action_failed", "message": sanitize_error(error, owner.host.paths)},
                    )

        self._server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self._thread: threading.Thread | None = None

    def _pairing_code(self) -> str:
        server = self.host.specs.get("server")
        if server is None:
            raise RuntimeError("MacSoft Server is not configured.")
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.port}/api/internal/pairing-code",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise RuntimeError("MacSoft Server could not provide a pairing code.") from error
        pairing_code = body.get("pairing_code") if isinstance(body, dict) else None
        if not isinstance(body, dict) or body.get("ok") is not True:
            raise RuntimeError("MacSoft Server returned an invalid pairing response.")
        if not isinstance(pairing_code, str) or not pairing_code.strip():
            raise RuntimeError("MacSoft Server returned an invalid pairing response.")
        return pairing_code.strip()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever, name="MacSoftHostControl", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)
