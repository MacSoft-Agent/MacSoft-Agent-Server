from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import skipUnless

from macsoft_runtime.control import HostControlServer
from macsoft_runtime.host import (
    CONFIG_BACKEND_PORT,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    HostInstanceLock,
    ChildProcessJob,
    MacSoftAgentHost,
    ServiceSpec,
    build_service_specs,
    prepare_host,
)
from macsoft_runtime.metadata import ProductMetadata
from macsoft_runtime.paths import resolve_packaged_paths


METADATA = ProductMetadata(
    product="MacSoft Agent",
    product_version="0.1.0",
    channel="stable",
    runtime_base_version="test",
    runtime_base_commit="0" * 40,
    runtime_contract_version=1,
    runtime_metadata_schema_version=1,
    build_date="2026-07-14",
    build_id="test",
    data_schema_version=1,
    protected_resource_version=1,
    update_manifest_url=None,
    update_manifest_public_key=None,
)


def free_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


SERVICE_SCRIPT = """\
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
print('api_key=service-secret', flush=True)
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        body=json.dumps({'ok': True, 'server': sys.argv[2]}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
HTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()
"""

RUNTIME_SERVICE_SCRIPT = """\
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
payload=json.loads(sys.argv[2])
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        body=json.dumps(payload).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
HTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()
"""


class HostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.program = self.base / "Program"
        self.data = self.base / "Data"
        self.program.mkdir()
        self.script = self.base / "service.py"
        self.script.write_text(SERVICE_SCRIPT, encoding="utf-8")
        self.runtime_script = self.base / "runtime_service.py"
        self.runtime_script.write_text(RUNTIME_SERVICE_SCRIPT, encoding="utf-8")
        self.paths = resolve_packaged_paths(self.program, self.data)
        self.paths.ai_program_root.mkdir(parents=True)
        (self.paths.ai_program_root / "macsoft-runtime.json").write_text(
            json.dumps(
                {
                    "runtime": "hermes-agent",
                    "runtime_base_version": METADATA.runtime_base_version,
                    "runtime_base_commit": METADATA.runtime_base_commit,
                    "runtime_contract_version": METADATA.runtime_contract_version,
                    "runtime_metadata_schema_version": METADATA.runtime_metadata_schema_version,
                }
            ),
            encoding="utf-8",
        )
        self.paths.logs_root.mkdir(parents=True)
        self.processes: list[subprocess.Popen] = []
        self.hosts: list[MacSoftAgentHost] = []

    def tearDown(self) -> None:
        for host in self.hosts:
            for name in reversed(tuple(host.specs)):
                host.stop(name)
            host.close()
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        self.temp.cleanup()

    def host(self, **kwargs) -> MacSoftAgentHost:
        value = MacSoftAgentHost(self.paths, METADATA, **kwargs)
        self.hosts.append(value)
        return value

    def spec(self, name: str, port: int, identity: str = "MacSoft Test") -> ServiceSpec:
        return ServiceSpec(
            name=name,
            command=(sys.executable, str(self.script), str(port), identity),
            cwd=self.base,
            environment={},
            health_url=f"http://127.0.0.1:{port}/health",
            health_identity={"ok": True, "server": identity},
            port=port,
        )

    def runtime_spec(
        self,
        port: int,
        detected: dict[str, object],
        expected: dict[str, object] | None = None,
    ) -> ServiceSpec:
        return ServiceSpec(
            name="ai_service",
            command=(
                sys.executable,
                str(self.runtime_script),
                str(port),
                json.dumps(
                    {
                        "status": "ok",
                        "platform": "hermes-agent",
                        "macsoft_runtime": detected,
                    }
                ),
            ),
            cwd=self.base,
            environment={},
            health_url=f"http://127.0.0.1:{port}/health",
            health_identity={
                "status": "ok",
                "platform": "hermes-agent",
                "macsoft_runtime": expected or detected,
            },
            port=port,
        )

    def wait_for_http(self, port: int) -> None:
        deadline = time.monotonic() + 5
        url = f"http://127.0.0.1:{port}/health"
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=0.5):
                    return
            except (OSError, urllib.error.URLError):
                time.sleep(0.02)
        self.fail(f"Test service did not bind port {port}.")

    def port_is_open(self, port: int) -> bool:
        with socket.socket() as client:
            client.settimeout(0.2)
            return client.connect_ex(("127.0.0.1", port)) == 0

    def test_server_receives_the_ai_service_internal_key_from_runtime(self) -> None:
        self.paths.runtime_root.mkdir(parents=True)
        self.paths.server_config.parent.mkdir(parents=True, exist_ok=True)
        self.paths.runtime_config.write_text(
            "platforms:\n  api_server:\n    extra:\n      port: 8642\n      key: runtime-owned-key\n",
            encoding="utf-8",
        )
        self.paths.server_config.write_text(
            "server:\n  port: 8787\nhermes:\n  api_key: stale-yaml-key\n",
            encoding="utf-8",
        )

        specs = build_service_specs(self.paths, METADATA)

        self.assertEqual(specs["server"].environment["MACSOFT_HERMES_API_KEY"], "runtime-owned-key")
        self.assertEqual(specs["server"].environment["HERMES_HOME"], str(self.paths.runtime_root))
        self.assertEqual(
            specs["server"].environment["MACSOFT_PROFILE_ROOT"],
            str(self.paths.runtime_root / "profiles"),
        )
        self.assertEqual(
            specs["ai_service"].environment["MACSOFT_PROFILE_ROOT"],
            str(self.paths.runtime_root / "profiles"),
        )
        self.assertEqual(
            specs["ai_service"].health_identity["macsoft_runtime"],
            {
                "runtime": "hermes-agent",
                "runtime_base_version": METADATA.runtime_base_version,
                "runtime_base_commit": METADATA.runtime_base_commit,
                "runtime_contract_version": METADATA.runtime_contract_version,
                "runtime_metadata_schema_version": METADATA.runtime_metadata_schema_version,
            },
        )

    def test_incompatible_runtime_fails_before_start_and_remains_diagnostic(self) -> None:
        (self.paths.ai_program_root / "macsoft-runtime.json").unlink()
        port = free_port()
        host = self.host(specs={"test": self.spec("test", port)}, health_timeout=1)

        with self.assertRaisesRegex(RuntimeError, "compatibility check failed"):
            host.start("test")

        status = host.status()
        self.assertEqual(status["runtime_compatibility"]["status"], "rejected")
        self.assertEqual(
            status["runtime_compatibility"]["error_code"],
            "runtime_declaration_invalid",
        )
        self.assertEqual(status["services"]["test"]["status"], "error")
        self.assertFalse(status["services"]["test"]["owned"])
        self.assertFalse(self.port_is_open(port))

    def test_prepare_host_does_not_initialize_customer_state_when_rejected(self) -> None:
        (self.paths.ai_program_root / "macsoft-runtime.json").unlink()

        host = prepare_host(self.paths, METADATA)
        self.hosts.append(host)

        self.assertEqual(host.runtime_compatibility["status"], "rejected")
        self.assertFalse(self.paths.runtime_config.exists())
        self.assertFalse(self.paths.server_config.exists())
        self.assertFalse(self.paths.server_database.exists())

    def test_live_runtime_mismatch_stops_ai_service_and_blocks_server(self) -> None:
        config_port = free_port()
        ai_port = free_port()
        expected = {
            "runtime": "hermes-agent",
            "runtime_base_version": METADATA.runtime_base_version,
            "runtime_base_commit": METADATA.runtime_base_commit,
            "runtime_contract_version": METADATA.runtime_contract_version,
            "runtime_metadata_schema_version": METADATA.runtime_metadata_schema_version,
        }
        detected = dict(expected)
        detected["runtime_contract_version"] = 2
        ai_spec = self.runtime_spec(ai_port, detected, expected)
        host = self.host(
            specs={
                "config_backend": self.spec("config_backend", config_port),
                "ai_service": ai_spec,
                "server": self.spec("server", free_port()),
            },
            health_timeout=2,
        )

        with self.assertRaisesRegex(RuntimeError, "runtime_contract_version"):
            host.start("ai_service")

        status = host.status()
        self.assertEqual(status["runtime_compatibility"]["phase"], "post_start")
        self.assertEqual(status["runtime_compatibility"]["status"], "rejected")
        self.assertEqual(
            status["runtime_compatibility"]["mismatched_fields"],
            ["runtime_contract_version"],
        )
        self.assertFalse(status["services"]["ai_service"]["owned"])
        self.assertEqual(status["services"]["config_backend"]["status"], "stopped")
        self.assertNotEqual(status["services"]["server"]["status"], "running")

    def test_owned_process_passes_health_and_stops_safely(self) -> None:
        port = free_port()
        host = self.host(specs={"test": self.spec("test", port)}, health_timeout=5)
        started = host.start("test")
        pid = started["pid"]
        self.assertEqual(started["status"], "running")
        self.assertTrue(started["owned"])
        host.stop("test")
        self.assertEqual(host.service_status("test")["status"], "stopped")
        with self.assertRaises(Exception):
            __import__("psutil").Process(pid)

    def test_child_output_is_sanitized_and_uses_bounded_logs(self) -> None:
        port = free_port()
        host = self.host(specs={"test": self.spec("test", port)}, health_timeout=5)
        host.start("test")
        host.stop("test")
        deadline = time.monotonic() + 2
        log_path = self.paths.logs_root / "test.log"
        while time.monotonic() < deadline and not log_path.exists():
            time.sleep(0.02)
        contents = log_path.read_text(encoding="utf-8")
        self.assertIn("api_key=<redacted>", contents)
        self.assertNotIn("service-secret", contents)
        self.assertEqual(LOG_MAX_BYTES, 5 * 1024 * 1024)
        self.assertEqual(LOG_BACKUP_COUNT, 5)

    def test_unrelated_port_owner_is_never_terminated(self) -> None:
        port = free_port()
        unrelated = subprocess.Popen(
            [sys.executable, str(self.script), str(port), "Unrelated Service"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.processes.append(unrelated)
        self.wait_for_http(port)
        host = self.host(specs={"test": self.spec("test", port)}, health_timeout=1)
        with self.assertRaisesRegex(RuntimeError, "unrelated"):
            host.start("test")
        self.assertIsNone(unrelated.poll())

    def test_correct_but_unowned_service_is_not_adopted_or_killed(self) -> None:
        port = free_port()
        external = subprocess.Popen(
            [sys.executable, str(self.script), str(port), "MacSoft Test"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.processes.append(external)
        self.wait_for_http(port)
        host = self.host(specs={"test": self.spec("test", port)}, health_timeout=1)
        with self.assertRaisesRegex(RuntimeError, "not owned"):
            host.start("test")
        self.assertIsNone(external.poll())

    def test_duplicate_host_lock_is_rejected(self) -> None:
        first = HostInstanceLock(self.data / "host.lock")
        second = HostInstanceLock(self.data / "host.lock")
        first.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError, "already running"):
                second.acquire()
        finally:
            first.release()

    def test_duplicate_host_lock_is_rejected_across_processes(self) -> None:
        path = self.data / "host.lock"
        first = HostInstanceLock(path)
        first.acquire()
        try:
            self.assertEqual(path.stat().st_size, 0)
            script = (
                "import sys; "
                "sys.path.insert(0, r'" + str(Path(__file__).parents[1]) + "'); "
                "from pathlib import Path; "
                "from macsoft_runtime.host import HostInstanceLock; "
                "HostInstanceLock(Path(r'" + str(path) + "')).acquire()"
            )
            duplicate = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("already running", (duplicate.stdout + duplicate.stderr).lower())
        finally:
            first.release()

    @skipUnless(sys.platform == "win32", "Windows Job Objects are Windows-only.")
    def test_closing_child_job_terminates_only_assigned_process(self) -> None:
        assigned = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.processes.extend([assigned, unrelated])
        job = ChildProcessJob()
        job.assign(assigned)
        job.close()
        assigned.wait(timeout=5)
        self.assertIsNotNone(assigned.returncode)
        self.assertIsNone(unrelated.poll())

    def test_control_interface_is_loopback_and_requires_token(self) -> None:
        host = self.host(specs={})
        control = HostControlServer(host, free_port())
        control.start()
        try:
            url = f"http://127.0.0.1:{control.port}/v1/status"
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(url, timeout=2)
            self.assertEqual(denied.exception.code, 401)
            request = urllib.request.Request(url, headers={"Authorization": f"Bearer {control.token}"})
            with urllib.request.urlopen(request, timeout=2) as response:
                body = json.loads(response.read())
            self.assertTrue(body["ok"])
            self.assertEqual(body["product"], "MacSoft Agent")
            self.assertEqual(control._server.server_address[0], "127.0.0.1")
        finally:
            control.stop()

    def test_control_interface_remains_available_for_compatibility_failure(self) -> None:
        (self.paths.ai_program_root / "macsoft-runtime.json").unlink()
        host = self.host(specs={"ai_service": self.spec("ai_service", free_port())})
        control = HostControlServer(host, free_port())
        control.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{control.port}/v1/status",
                headers={"Authorization": f"Bearer {control.token}"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                body = json.loads(response.read())
            self.assertTrue(body["ok"])
            self.assertEqual(body["runtime_compatibility"]["status"], "rejected")
            self.assertEqual(body["services"]["ai_service"]["status"], "error")
        finally:
            control.stop()

    def test_control_token_is_injected_into_configuration_backend(self) -> None:
        config_backend = self.spec("config_backend", free_port())
        server = self.spec("server", free_port())
        host = self.host(specs={"config_backend": config_backend, "server": server})

        control = HostControlServer(host, free_port())
        control.start()
        try:
            self.assertEqual(
                config_backend.environment["HERMES_DASHBOARD_SESSION_TOKEN"],
                control.token,
            )
            self.assertEqual(
                server.environment["MACSOFT_HOST_CONTROL_TOKEN"],
                control.token,
            )
            self.assertEqual(CONFIG_BACKEND_PORT, 8643)
        finally:
            control.stop()

    def test_pairing_code_requires_host_token_and_is_not_cached(self) -> None:
        host = self.host(specs={})
        control = HostControlServer(host, free_port())
        control._pairing_code = lambda: "PAIR-123456"
        control.start()
        try:
            url = f"http://127.0.0.1:{control.port}/v1/pairing-code"
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(url, timeout=2)
            self.assertEqual(denied.exception.code, 401)

            request = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {control.token}"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                body = json.loads(response.read())
                cache_control = response.headers.get("Cache-Control")
            self.assertEqual(body, {"ok": True, "pairing_code": "PAIR-123456"})
            self.assertEqual(cache_control, "no-store")
        finally:
            control.stop()


if __name__ == "__main__":
    unittest.main()
