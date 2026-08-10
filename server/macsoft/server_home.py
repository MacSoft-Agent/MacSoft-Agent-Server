from __future__ import annotations

from pathlib import Path
import hashlib
import re
from typing import Any

import yaml

from macsoft.profiles.registry import (
    _configured_hermes_home,
    _without_embedded_secrets,
    configured_profile_root,
)


MAX_SHARED_SERVER_CONTEXT_CHARS = 64_000
_PROFILE_ID_RE = re.compile(r"^prof_[a-f0-9]{32}$")


def runtime_root(config: Any) -> Path:
    root = _configured_hermes_home(config)
    if root is None:
        raise RuntimeError("The Server Hermes runtime home is not configured.")
    return root.resolve()


def server_home(config: Any) -> Path:
    """Return the native Hermes Home used by ordinary Server Desktop chat."""
    return (runtime_root(config) / "admin").resolve()


def ensure_server_home(config: Any) -> Path:
    """Provision one native Server Home without copying provider secrets."""
    home = server_home(config)
    if home.parent != runtime_root(config):
        raise ValueError("invalid_server_hermes_home")

    for directory in (
        home / "memories",
        home / "skills",
        home / "sessions",
        home / "logs",
        home / "curator",
        home / "backups",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    for name in ("USER.md", "MEMORY.md"):
        path = home / "memories" / name
        if not path.exists():
            path.write_text("", encoding="utf-8")

    desired: Any = {}
    source_config = runtime_root(config) / "config.yaml"
    if source_config.is_file():
        try:
            desired = yaml.safe_load(source_config.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            desired = {}
    desired = _without_embedded_secrets(desired)
    if not isinstance(desired, dict):
        desired = {}
    config_path = home / "config.yaml"
    current: Any = {}
    if config_path.is_file():
        try:
            current = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            current = {}
    if not isinstance(current, dict):
        current = {}
    for key in ("model", "memory", "skills", "curator"):
        if key in desired:
            current[key] = desired[key]
    model = current.get("model")
    provider_id = model.get("provider") if isinstance(model, dict) else None
    if isinstance(provider_id, str) and provider_id.strip():
        providers = current.get("providers")
        if not isinstance(providers, dict):
            providers = {}
            current["providers"] = providers
        provider = providers.get(provider_id)
        if not isinstance(provider, dict):
            provider = {}
        desired_providers = desired.get("providers")
        if isinstance(desired_providers, dict):
            desired_provider = desired_providers.get(provider_id)
            if isinstance(desired_provider, dict):
                provider.update(desired_provider)
        timeout_seconds = int(config.hermes.request_timeout_seconds)
        provider["request_timeout_seconds"] = timeout_seconds
        provider["stale_timeout_seconds"] = timeout_seconds
        providers[provider_id] = provider
    config_path.write_text(
        yaml.safe_dump(_without_embedded_secrets(current), sort_keys=False),
        encoding="utf-8",
    )
    return home


def _safe_text(path: Path, limit: int) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit].strip()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return ""


def read_shareable_server_context(config: Any) -> str | None:
    """Snapshot bounded Server Memory and native learned Skills for Clients.

    The returned text is request context only. Client-scoped Hermes runs never
    receive the Server Home path or any mutation authority.
    """
    try:
        home = server_home(config)
    except RuntimeError:
        return None

    sections: list[str] = []
    for label, path in (
        ("Server user context", home / "memories" / "USER.md"),
        ("Server learned memory", home / "memories" / "MEMORY.md"),
    ):
        content = _safe_text(path, MAX_SHARED_SERVER_CONTEXT_CHARS)
        if content:
            sections.append(f"### {label}\n{content}")

    if not sections:
        return None
    return "\n\n".join(sections)[:MAX_SHARED_SERVER_CONTEXT_CHARS]


def read_or_create_server_context_snapshot(
    config: Any, *, profile_id: str, session_id: str
) -> str | None:
    """Return the immutable Server learning snapshot for one Client session."""
    if not _PROFILE_ID_RE.fullmatch(profile_id) or not session_id:
        raise ValueError("invalid_server_context_scope")
    profile_root = configured_profile_root(config)
    profile_home = (profile_root / profile_id).resolve()
    if profile_home.parent != profile_root or not profile_home.is_dir():
        raise ValueError("device_profile_not_found")
    snapshot_root = profile_home / "sessions" / "server-context"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    # Session identifiers are an existing public contract and may use legacy
    # formats. Hash the authenticated value so it can never influence a path.
    snapshot_name = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    snapshot = snapshot_root / f"{snapshot_name}.md"
    existing = _safe_text(snapshot, MAX_SHARED_SERVER_CONTEXT_CHARS)
    if snapshot.exists():
        return existing or None

    content = read_shareable_server_context(config) or ""
    try:
        with snapshot.open("x", encoding="utf-8") as file:
            file.write(content)
        return content or None
    except FileExistsError:
        existing = _safe_text(snapshot, MAX_SHARED_SERVER_CONTEXT_CHARS)
        return existing or None
