from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PRODUCT_DIRECTORY_NAME = "MacSoft Agent"


@dataclass(frozen=True)
class ProductPaths:
    mode: str
    program_root: Path
    data_root: Path
    ai_program_root: Path
    server_program_root: Path
    python_executable: Path
    desktop_root: Path
    templates_root: Path
    runtime_root: Path
    server_data_root: Path
    server_config: Path
    server_database: Path
    config_root: Path
    logs_root: Path
    backup_root: Path
    host_state_root: Path

    @property
    def is_packaged(self) -> bool:
        return self.mode == "packaged"

    @property
    def runtime_config(self) -> Path:
        return self.runtime_root / "config.yaml"

    @property
    def soul_file(self) -> Path:
        return self.runtime_root / "SOUL.md"

    @property
    def autocount_plugin_root(self) -> Path:
        return self.runtime_root / "plugins" / "macsoft-autocount"

    @property
    def host_control_file(self) -> Path:
        return self.host_state_root / "host-control.json"


def _resolved(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def resolve_development_paths(project_root: Path | str) -> ProductPaths:
    root = _resolved(project_root)
    if not (root / "product.json").is_file():
        raise FileNotFoundError(f"MacSoft Agent product metadata was not found under {root}.")
    return ProductPaths(
        mode="development",
        program_root=root,
        data_root=root,
        ai_program_root=root / "hermes",
        server_program_root=root / "server",
        python_executable=root / "hermes" / "venv" / "Scripts" / "python.exe",
        desktop_root=root / "hermes" / "apps" / "desktop",
        templates_root=root / "packaging" / "templates",
        runtime_root=root / "runtime",
        server_data_root=root / "server",
        server_config=root / "server" / "macsoft-server.yaml",
        server_database=root / "server" / "data" / "macsoft-server.db",
        config_root=root / "server",
        logs_root=root / "logs",
        backup_root=root / "backup",
        host_state_root=root / "server" / "data" / "host",
    )


def resolve_packaged_paths(
    program_root: Path | str | None = None,
    data_root: Path | str | None = None,
) -> ProductPaths:
    program = _resolved(
        program_root
        or Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / PRODUCT_DIRECTORY_NAME
    )
    data = _resolved(
        data_root
        or Path(os.environ.get("ProgramData", r"C:\ProgramData")) / PRODUCT_DIRECTORY_NAME
    )
    return ProductPaths(
        mode="packaged",
        program_root=program,
        data_root=data,
        ai_program_root=program / "ai-service",
        server_program_root=program / "server",
        python_executable=program / "python" / "python.exe",
        desktop_root=program / "desktop",
        templates_root=program / "templates",
        runtime_root=data / "runtime",
        server_data_root=data / "server",
        server_config=data / "server" / "macsoft-server.yaml",
        server_database=data / "server" / "data" / "macsoft-server.db",
        config_root=data / "config",
        logs_root=data / "logs",
        backup_root=data / "backup",
        host_state_root=data / "config" / "host",
    )
