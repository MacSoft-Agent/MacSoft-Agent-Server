from __future__ import annotations

import json
import logging
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable

import psutil
import yaml

from .initializer import initialize_product_data
from .compatibility import (
    RuntimeCompatibilityError,
    assess_live_compatibility,
    assess_pre_start_compatibility,
    compatibility_error_message,
    expected_runtime_metadata,
)
from .metadata import ProductMetadata
from .paths import ProductPaths


HEALTH_TIMEOUT_SECONDS = 60.0
MAX_RESTARTS = 3
RESTART_WINDOW_SECONDS = 300.0
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 5
CONFIG_BACKEND_PORT = 8643


def sanitize_error(value: object, paths: ProductPaths | None = None) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"(?i)(authorization|api[_ -]?key|token|password)\s*[:=]\s*\S+", r"\1=<redacted>", text)
    if paths:
        for root in (paths.program_root, paths.data_root):
            text = text.replace(str(root), "<product-path>")
    return text[:500]


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    command: tuple[str, ...]
    cwd: Path
    environment: dict[str, str]
    health_url: str
    health_identity: dict[str, Any]
    port: int


@dataclass
class ServiceState:
    status: str = "stopped"
    pid: int | None = None
    started_at: float | None = None
    last_error: str | None = None
    desired_running: bool = False
    process: subprocess.Popen | None = field(default=None, repr=False)
    process_create_time: float | None = field(default=None, repr=False)


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        value = yaml.safe_load(file) or {}
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a YAML object.")
    return value


def _read_service_config(path: Path, *, allow_missing: bool) -> dict[str, Any]:
    if allow_missing and not path.is_file():
        return {}
    return _read_yaml(path)


def build_service_specs(
    paths: ProductPaths,
    metadata: ProductMetadata,
    *,
    allow_missing_config: bool = False,
) -> dict[str, ServiceSpec]:
    runtime = _read_service_config(
        paths.runtime_config,
        allow_missing=allow_missing_config,
    )
    server = _read_service_config(
        paths.server_config,
        allow_missing=allow_missing_config,
    )
    api = runtime.get("platforms", {}).get("api_server", {}).get("extra", {})
    ai_port = int(api.get("port", 8642))
    ai_api_key = str(api.get("key", "")).strip()
    server_port = int(server.get("server", {}).get("port", 8787))
    cert_file = paths.program_root / "python" / "Lib" / "site-packages" / "certifi" / "cacert.pem"
    shared_environment = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "MACSOFT_PRODUCT_METADATA": str(paths.program_root / "product.json"),
    }
    if cert_file.is_file():
        shared_environment.update({"SSL_CERT_FILE": str(cert_file), "REQUESTS_CA_BUNDLE": str(cert_file)})

    return {
        "config_backend": ServiceSpec(
            name="config_backend",
            command=(
                str(paths.python_executable),
                "-m",
                "hermes_cli.main",
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(CONFIG_BACKEND_PORT),
            ),
            cwd=paths.ai_program_root,
            environment={
                **shared_environment,
                "HERMES_CONFIG_ONLY": "1",
                "HERMES_HOME": str(paths.runtime_root),
                "PYTHONPATH": str(paths.ai_program_root),
            },
            health_url=f"http://127.0.0.1:{CONFIG_BACKEND_PORT}/api/status",
            health_identity={"runtime_mode": "config-only"},
            port=CONFIG_BACKEND_PORT,
        ),
        "ai_service": ServiceSpec(
            name="ai_service",
            command=(str(paths.python_executable), "-m", "hermes_cli.main", "gateway", "run"),
            cwd=paths.ai_program_root,
            environment={
                **shared_environment,
                "HERMES_HOME": str(paths.runtime_root),
                "PYTHONPATH": str(paths.ai_program_root),
            },
            health_url=f"http://127.0.0.1:{ai_port}/health",
            health_identity={
                "status": "ok",
                "platform": "hermes-agent",
                "macsoft_runtime": expected_runtime_metadata(metadata),
            },
            port=ai_port,
        ),
        "server": ServiceSpec(
            name="server",
            command=(str(paths.python_executable), "-m", "macsoft.server"),
            cwd=paths.server_program_root,
            environment={
                **shared_environment,
                "MACSOFT_SERVER_CONFIG": str(paths.server_config),
                "MACSOFT_HERMES_API_KEY": ai_api_key,
                "PYTHONPATH": str(paths.server_program_root),
            },
            health_url=f"http://127.0.0.1:{server_port}/health",
            health_identity={"ok": True, "server": "MacSoft Server"},
            port=server_port,
        ),
    }


class HostInstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._file = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            file.close()
            raise RuntimeError("MacSoft Agent Host is already running.") from error
        self._file = file

    def release(self) -> None:
        if not self._file:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None


class ChildProcessJob:
    """Keep Host-owned Windows children bounded to the Host lifetime."""

    def __init__(self) -> None:
        self._handle = None
        if os.name != "nt":
            return
        import win32job

        handle = win32job.CreateJobObject(None, "")
        information = win32job.QueryInformationJobObject(
            handle,
            win32job.JobObjectExtendedLimitInformation,
        )
        information["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(
            handle,
            win32job.JobObjectExtendedLimitInformation,
            information,
        )
        self._handle = handle

    def assign(self, process: subprocess.Popen) -> None:
        if self._handle is None:
            return
        import win32job

        win32job.AssignProcessToJobObject(self._handle, process._handle)

    def close(self) -> None:
        if self._handle is None:
            return
        import win32api

        win32api.CloseHandle(self._handle)
        self._handle = None


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.35)
        return client.connect_ex(("127.0.0.1", port)) == 0


def _read_health(spec: ServiceSpec, timeout: float = 1.5) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(spec.health_url, timeout=timeout) as response:
            if response.status != 200:
                return None
            body = json.loads(response.read().decode("utf-8"))
        return body if isinstance(body, dict) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def _health_matches(spec: ServiceSpec, timeout: float = 1.5) -> bool:
    body = _read_health(spec, timeout)
    return body is not None and all(body.get(key) == value for key, value in spec.health_identity.items())


class MacSoftAgentHost:
    def __init__(
        self,
        paths: ProductPaths,
        metadata: ProductMetadata,
        *,
        specs: dict[str, ServiceSpec] | None = None,
        runtime_compatibility: dict[str, Any] | None = None,
        health_timeout: float = HEALTH_TIMEOUT_SECONDS,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    ) -> None:
        self.paths = paths
        self.metadata = metadata
        self.runtime_compatibility = (
            runtime_compatibility
            if runtime_compatibility is not None
            else assess_pre_start_compatibility(paths, metadata)
        )
        self.specs = (
            specs
            if specs is not None
            else build_service_specs(
                paths,
                metadata,
                allow_missing_config=self.runtime_compatibility["status"] != "accepted",
            )
        )
        self.health_timeout = health_timeout
        self._popen = popen
        self.states = {name: ServiceState() for name in self.specs}
        self._lock = threading.RLock()
        self._instance_lock = HostInstanceLock(paths.host_state_root / "host.lock")
        self._child_job = ChildProcessJob()
        self._restart_times = {name: deque() for name in self.specs}
        self._stop_event = threading.Event()
        self._monitor: threading.Thread | None = None
        self._log_threads: list[threading.Thread] = []
        self._logger = self._create_logger()
        if self.runtime_compatibility["status"] != "accepted":
            self._mark_compatibility_rejected(self.runtime_compatibility)

    def _mark_compatibility_rejected(self, result: dict[str, Any]) -> None:
        message = compatibility_error_message(result)
        for state in self.states.values():
            if state.status != "running":
                state.status = "error"
                state.last_error = message
                state.desired_running = False

    def _create_logger(self) -> logging.Logger:
        self.paths.logs_root.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(f"macsoft-host-{id(self)}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = RotatingFileHandler(
            self.paths.logs_root / "host.log",
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        return logger

    def acquire(self) -> None:
        self._instance_lock.acquire()

    def release(self) -> None:
        self._instance_lock.release()

    def close(self) -> None:
        self.release()
        for thread in self._log_threads:
            thread.join(timeout=5)
        self._child_job.close()
        for handler in list(self._logger.handlers):
            handler.close()
            self._logger.removeHandler(handler)

    def start_all(self) -> None:
        started: list[str] = []
        try:
            for name in ("config_backend", "ai_service", "server"):
                self.start(name)
                started.append(name)
        except Exception:
            for name in reversed(started):
                self.stop(name)
            raise
        try:
            self._ensure_monitor()
        except Exception:
            for name in reversed(started):
                self.stop(name)
            raise

    def start(self, name: str) -> dict[str, Any]:
        with self._lock:
            if name not in self.specs:
                raise ValueError("Unknown service.")
            if self.runtime_compatibility["status"] != "accepted":
                self._mark_compatibility_rejected(self.runtime_compatibility)
                raise RuntimeCompatibilityError(
                    compatibility_error_message(self.runtime_compatibility)
                )
            if name == "ai_service" and self.states.get("config_backend", ServiceState()).status != "running":
                self.start("config_backend")
            if name == "server" and self.states.get("ai_service", ServiceState()).status != "running":
                self.start("ai_service")
            spec = self.specs[name]
            state = self.states[name]
            if state.process and state.process.poll() is None and _health_matches(spec):
                state.status = "running"
                state.desired_running = True
                return self.service_status(name)
            if _port_is_open(spec.port):
                if _health_matches(spec):
                    reason = f"{name} is responding but is not owned by this Host."
                else:
                    reason = f"Port {spec.port} is occupied by an unrelated process."
                state.status = "error"
                state.last_error = reason
                raise RuntimeError(reason)

            state.status = "starting"
            state.last_error = None
            state.desired_running = True
            environment = os.environ.copy()
            environment.update(spec.environment)
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            try:
                process = self._popen(
                    spec.command,
                    cwd=spec.cwd,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception:
                state.status = "error"
                raise
            try:
                self._child_job.assign(process)
            except Exception as error:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                state.status = "error"
                state.last_error = "Host could not contain its child process."
                raise RuntimeError(state.last_error) from error
            state.process = process
            state.pid = process.pid
            state.process_create_time = psutil.Process(process.pid).create_time()
            state.started_at = time.time()
            if process.stdout is not None:
                thread = threading.Thread(
                    target=self._pump_service_log,
                    args=(name, process.stdout),
                    name=f"MacSoftLog-{name}",
                    daemon=True,
                )
                self._log_threads.append(thread)
                thread.start()

        deadline = time.monotonic() + self.health_timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            health_body = _read_health(spec)
            if health_body is not None and name == "ai_service":
                live_result = assess_live_compatibility(
                    expected_runtime_metadata(self.metadata),
                    health_body,
                )
                if live_result["status"] != "accepted":
                    with self._lock:
                        self.runtime_compatibility = live_result
                        self._mark_compatibility_rejected(live_result)
                    self._stop_owned_process(state)
                    with self._lock:
                        state.process = None
                        state.pid = None
                        state.process_create_time = None
                    if name == "ai_service" and "config_backend" in self.states:
                        self.stop("config_backend")
                    raise RuntimeCompatibilityError(
                        compatibility_error_message(live_result)
                    )
                with self._lock:
                    self.runtime_compatibility = live_result
            if health_body is not None and all(
                health_body.get(key) == value for key, value in spec.health_identity.items()
            ):
                with self._lock:
                    state.status = "running"
                self._logger.info("service_started name=%s pid=%s", name, process.pid)
                return self.service_status(name)
            time.sleep(0.2)

        error = f"{name} did not pass its identity health check."
        with self._lock:
            state.status = "error"
            state.last_error = error
        self._stop_owned_process(state)
        raise RuntimeError(error)

    def _pump_service_log(self, name: str, stream: Any) -> None:
        handler = RotatingFileHandler(
            self.paths.logs_root / f"{name}.log",
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger = logging.getLogger(f"macsoft-child-{id(self)}-{name}-{time.monotonic_ns()}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.addHandler(handler)
        try:
            for line in stream:
                clean = sanitize_error(line.strip(), self.paths)
                if clean:
                    logger.info("%s", clean)
        finally:
            stream.close()
            handler.close()
            logger.removeHandler(handler)

    def _stop_owned_process(self, state: ServiceState) -> None:
        process = state.process
        if not process or state.pid is None:
            return
        try:
            owner = psutil.Process(state.pid)
            if state.process_create_time is None or abs(owner.create_time() - state.process_create_time) > 0.01:
                return
            children = owner.children(recursive=True)
            for child in reversed(children):
                child.terminate()
            owner.terminate()
            _, alive = psutil.wait_procs([*children, owner], timeout=8)
            for item in alive:
                item.kill()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        except psutil.NoSuchProcess:
            pass

    def stop(self, name: str) -> dict[str, Any]:
        with self._lock:
            if name not in self.specs:
                raise ValueError("Unknown service.")
            state = self.states[name]
            state.desired_running = False
            self._stop_owned_process(state)
            state.process = None
            state.pid = None
            state.process_create_time = None
            state.status = "stopped"
            self._logger.info("service_stopped name=%s", name)
            return self.service_status(name)

    def restart(self, name: str) -> dict[str, Any]:
        self.stop(name)
        return self.start(name)

    def stop_all(self) -> None:
        self._stop_event.set()
        for name in ("server", "ai_service", "config_backend"):
            if name in self.specs:
                self.stop(name)

    def service_status(self, name: str) -> dict[str, Any]:
        state = self.states[name]
        if state.process and state.process.poll() is not None and state.status in {"running", "starting"}:
            state.status = "error"
            state.last_error = "Service process exited unexpectedly."
        return {
            "name": name,
            "status": state.status,
            "pid": state.pid,
            "started_at": state.started_at,
            "last_error": sanitize_error(state.last_error, self.paths) if state.last_error else None,
            "owned": bool(state.process and state.pid),
        }

    def status(self) -> dict[str, Any]:
        return {
            "product": "MacSoft Agent",
            "version": self.metadata.product_version,
            "runtime_compatibility": self.runtime_compatibility,
            "services": {name: self.service_status(name) for name in self.specs},
            "auto_start": self._read_auto_start(),
        }

    def set_auto_start(self, enabled: bool) -> bool:
        path = self.paths.host_state_root / "preferences.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"auto_start": bool(enabled)}, indent=2) + "\n", encoding="utf-8")
        if os.name == "nt":
            try:
                import win32service

                manager = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
                try:
                    service = win32service.OpenService(
                        manager,
                        "MacSoftAgentHost",
                        win32service.SERVICE_CHANGE_CONFIG,
                    )
                    try:
                        win32service.ChangeServiceConfig(
                            service,
                            win32service.SERVICE_NO_CHANGE,
                            win32service.SERVICE_AUTO_START if enabled else win32service.SERVICE_DEMAND_START,
                            win32service.SERVICE_NO_CHANGE,
                            None,
                            None,
                            0,
                            None,
                            None,
                            None,
                            None,
                        )
                    finally:
                        win32service.CloseServiceHandle(service)
                finally:
                    win32service.CloseServiceHandle(manager)
            except Exception:
                # Staging runs before the final installer registers the service.
                # The preference is retained and applied by service registration.
                pass
        return bool(enabled)

    def _read_auto_start(self) -> bool:
        try:
            value = json.loads((self.paths.host_state_root / "preferences.json").read_text("utf-8"))
            return value.get("auto_start") is not False
        except (OSError, ValueError, TypeError):
            return True

    def _ensure_monitor(self) -> None:
        if self._monitor and self._monitor.is_alive():
            return
        self._stop_event.clear()
        self._monitor = threading.Thread(target=self._monitor_loop, name="MacSoftHostMonitor", daemon=True)
        self._monitor.start()

    def _monitor_loop(self) -> None:
        while not self._stop_event.wait(2.0):
            for name, state in self.states.items():
                if not state.desired_running or not state.process or state.process.poll() is None:
                    continue
                now = time.monotonic()
                history = self._restart_times[name]
                while history and now - history[0] > RESTART_WINDOW_SECONDS:
                    history.popleft()
                if len(history) >= MAX_RESTARTS:
                    state.status = "error"
                    state.last_error = "Restart limit reached. Review the service log."
                    state.desired_running = False
                    continue
                history.append(now)
                try:
                    self.start(name)
                except Exception as error:
                    state.last_error = sanitize_error(error, self.paths)


def prepare_host(paths: ProductPaths, metadata: ProductMetadata) -> MacSoftAgentHost:
    runtime_compatibility = assess_pre_start_compatibility(paths, metadata)
    if runtime_compatibility["status"] == "accepted":
        initialize_product_data(paths, metadata)
    return MacSoftAgentHost(
        paths,
        metadata,
        runtime_compatibility=runtime_compatibility,
    )
