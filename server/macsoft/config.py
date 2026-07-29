from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ServerSettings:
    host: str
    port: int


@dataclass(frozen=True)
class DatabaseSettings:
    path: str


@dataclass(frozen=True)
class HermesSettings:
    home: str
    api_base_url: str
    api_key: str
    request_timeout_seconds: int


@dataclass(frozen=True)
class ModelSettings:
    default_model: str
    fallback_model: str


@dataclass(frozen=True)
class RuntimeSettings:
    mode: str


@dataclass(frozen=True)
class AutoCountSettings:
    enabled: bool
    catalog_path: str


@dataclass(frozen=True)
class ChartArtifactSettings:
    enabled: bool
    environment: str
    storage_path: str
    worker_max_attempts: int
    lease_seconds: int
    render_input_ttl_minutes: int
    retention_days: int


@dataclass(frozen=True)
class AppConfig:
    config_path: str
    server: ServerSettings
    database: DatabaseSettings
    hermes: HermesSettings
    models: ModelSettings
    runtime: RuntimeSettings
    autocount: AutoCountSettings
    chart_artifacts: ChartArtifactSettings


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8-sig") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ValueError("Config file must contain a YAML object.")

    return data


def load_config(config_path: str | None = None) -> AppConfig:
    root_dir = Path(__file__).resolve().parents[1]
    configured_path = config_path or os.environ.get("MACSOFT_SERVER_CONFIG")
    path = Path(configured_path).expanduser() if configured_path else root_dir / "macsoft-server.yaml"
    path = path.resolve()
    data = _read_yaml(path)

    server_data = data.get("server", {})
    database_data = data.get("database", {})
    hermes_data = data.get("hermes", {})
    models_data = data.get("models", {})
    runtime_data = data.get("runtime", {})
    autocount_data = data.get("autocount", {})
    chart_data = data.get("chart_artifacts", {})
    chart_environment = str(chart_data.get("environment", "production")).strip().lower()
    if chart_environment not in {"production", "development", "test"}:
        raise ValueError("chart_artifacts.environment must be production, development, or test")

    return AppConfig(
        config_path=str(path),
        server=ServerSettings(
            host=str(server_data.get("host", "127.0.0.1")),
            port=int(server_data.get("port", 8787)),
        ),
        database=DatabaseSettings(
            path=str(database_data.get("path", "./data/macsoft-server.db")),
        ),
        hermes=HermesSettings(
            home=str(hermes_data.get("home", "../hermes")),
            api_base_url=str(
                hermes_data.get(
                    "api_base_url",
                    "http://127.0.0.1:8642",
                )
            ).rstrip("/"),
            api_key=str(
                os.environ.get("MACSOFT_HERMES_API_KEY")
                or hermes_data.get("api_key", "macsoft-local-dev")
            ),
            request_timeout_seconds=int(
                hermes_data.get(
                    "request_timeout_seconds",
                    180,
                )
            ),
        ),
        models=ModelSettings(
            default_model=str(models_data.get("default_model", "server-default")),
            fallback_model=str(models_data.get("fallback_model", "server-fallback")),
        ),
        runtime=RuntimeSettings(
            mode=str(runtime_data.get("mode", "minimal")),
        ),
        autocount=AutoCountSettings(
            enabled=bool(autocount_data.get("enabled", False)),
            catalog_path=str(
                autocount_data.get(
                    "catalog_path",
                    "./docs/autocount-api-catalog.json",
                )
            ),
        ),
        chart_artifacts=ChartArtifactSettings(
            enabled=bool(chart_data.get("enabled", False)),
            environment=chart_environment,
            storage_path=str(chart_data.get("storage_path", "./data/chart-artifacts")),
            worker_max_attempts=max(1, min(int(chart_data.get("worker_max_attempts", 3)), 10)),
            lease_seconds=max(10, min(int(chart_data.get("lease_seconds", 30)), 300)),
            render_input_ttl_minutes=max(
                1,
                min(int(chart_data.get("render_input_ttl_minutes", 60)), 24 * 60),
            ),
            retention_days=max(1, min(int(chart_data.get("retention_days", 30)), 3650)),
        ),
    )
