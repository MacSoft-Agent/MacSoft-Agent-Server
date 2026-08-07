from __future__ import annotations

from pathlib import Path
import json
import os
import re
import shutil
import uuid
from typing import Any

import yaml

from macsoft.profiles.registry import (
    _configured_hermes_home,
    _initial_profile_config,
    _without_embedded_secrets,
)


GLOBAL_HOME_SCHEMA_VERSION = 1
MAX_GLOBAL_MEMORY_CHARS = 32_000
_ADMIN_SESSION_ID_RE = re.compile(r"^admin_sess_[a-f0-9]{32}$")
GLOBAL_WORKFLOW_TARGETS = (
    "autocount-operations", "macsoft-chart-dashboard",
    "macsoft-chart-visualization", "data-storytelling", "web-design-engineer",
)
_GLOBAL_USER_PROFILE = """# MacSoft Agent Global Service Profile

This Hermes Home belongs to MacSoft Server, not to an individual user.

- Improve only reusable service behavior that can safely help every paired Client.
- Preserve security boundaries, company/workflow rules and AutoCount permissions.
- Treat personal preferences, identities, credentials, customer details, local paths
  and temporary task context as non-global information.
- Prefer event analysis, reliable procedures, validation and failure prevention.
"""


def runtime_root(config: Any) -> Path:
    root = _configured_hermes_home(config)
    if root is None:
        raise RuntimeError("The Server Hermes runtime home is not configured.")
    return root.resolve()


def admin_home(config: Any) -> Path:
    return (runtime_root(config) / "admin").resolve()


def global_home(config: Any) -> Path:
    return (runtime_root(config) / "global").resolve()


def global_staging_root(config: Any) -> Path:
    return (runtime_root(config) / "global-staging").resolve()


def global_training_home(config: Any, session_id: str) -> Path:
    if not _ADMIN_SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("invalid_global_training_session")
    root = global_staging_root(config)
    candidate = (root / session_id).resolve()
    if candidate.parent != root:
        raise ValueError("invalid_global_training_home")
    return candidate


def _scoped_config(config: Any) -> dict[str, Any]:
    scoped = _initial_profile_config(config)
    scoped["macsoft_scope_schema_version"] = GLOBAL_HOME_SCHEMA_VERSION
    return _without_embedded_secrets(scoped)


def _provision(home: Path, *, config: Any) -> Path:
    root = runtime_root(config)
    staging_root = global_staging_root(config)
    if home.parent != root and home.parent != staging_root:
        raise ValueError("invalid_server_hermes_home")

    for directory in (
        home / "memories",
        home / "skills" / "learned",
        home / "sessions",
        home / "logs",
        home / "curator",
        home / "backups",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    if home == global_home(config) or home.parent == global_staging_root(config):
        overlay_root = home / "skills" / "learned" / "workflow-improvements"
        overlay_root.mkdir(parents=True, exist_ok=True)
        for target in GLOBAL_WORKFLOW_TARGETS:
            (overlay_root / target).mkdir(parents=True, exist_ok=True)

    for memory_file in (home / "memories" / "USER.md", home / "memories" / "MEMORY.md"):
        if not memory_file.exists():
            memory_file.write_text("", encoding="utf-8")
    if home == global_home(config):
        global_user = home / "memories" / "USER.md"
        if not global_user.read_text(encoding="utf-8").strip():
            global_user.write_text(_GLOBAL_USER_PROFILE, encoding="utf-8")
        index_path = home / "workflow-index.json"
        if not index_path.exists():
            index_path.write_text(
                json.dumps(
                    {"schema_version": 1, "workflows": [
                        {"workflow_id": target, "overlay": f"skills/learned/workflow-improvements/{target}"}
                        for target in GLOBAL_WORKFLOW_TARGETS
                    ]},
                    indent=2,
                ),
                encoding="utf-8",
            )

    config_path = home / "config.yaml"
    desired = _scoped_config(config)
    current: Any = {}
    if config_path.is_file():
        try:
            current = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            current = {}
    if not isinstance(current, dict):
        current = {}

    # Keep native state and local behavioral settings, but synchronize the
    # Server-owned model and protected read-only Skill source. Credentials are
    # removed before every write.
    for key in ("model", "memory", "skills", "curator", "macsoft_scope_schema_version"):
        if key in desired:
            current[key] = desired[key]
    config_path.write_text(
        yaml.safe_dump(_without_embedded_secrets(current), sort_keys=False),
        encoding="utf-8",
    )
    return home


def ensure_server_hermes_homes(config: Any) -> dict[str, Path]:
    """Provision native Admin and Global homes without copying secrets."""
    return {
        "admin": _provision(admin_home(config), config=config),
        "global": _provision(global_home(config), config=config),
    }


def ensure_global_training_home(config: Any, session_id: str) -> Path:
    """Clone canonical native learning state into one proposal workspace."""
    canonical = _provision(global_home(config), config=config)
    staging_root = global_staging_root(config)
    staging_root.mkdir(parents=True, exist_ok=True)
    target = global_training_home(config, session_id)
    if target.is_dir():
        return _provision(target, config=config)

    temporary = staging_root / f".{session_id}.{uuid.uuid4().hex}.tmp"
    temporary.mkdir(parents=False, exist_ok=False)
    try:
        for name in ("memories", "skills", "curator"):
            source = canonical / name
            if source.is_dir():
                shutil.copytree(source, temporary / name)
        for name in ("sessions", "logs", "backups"):
            (temporary / name).mkdir(parents=True, exist_ok=True)
        config_path = canonical / "config.yaml"
        if config_path.is_file():
            shutil.copy2(config_path, temporary / "config.yaml")
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return _provision(target, config=config)


def set_global_training_target(config: Any, session_id: str, workflow_target: str) -> Path:
    """Persist the immutable Server-validated training target in staging config."""
    home = ensure_global_training_home(config, session_id)
    config_path = home / "config.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise RuntimeError("invalid_global_training_config")
    payload["macsoft_global_workflow_target"] = workflow_target
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return home


def read_approved_global_memory(config: Any) -> str | None:
    """Return canonical approved global context without exposing its path."""
    try:
        home = global_home(config)
    except RuntimeError:
        # Global context is an optional additive layer for legacy/direct route
        # callers. The real Server provisions its home during create_app().
        return None
    sections: list[str] = []
    for label, relative in (
        ("Server-wide operating context", "memories/USER.md"),
        ("Approved reusable knowledge", "memories/MEMORY.md"),
    ):
        path = home / relative
        try:
            content = path.read_text(encoding="utf-8").strip()
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            continue
        if content:
            sections.append(f"### {label}\n{content}")
    if not sections:
        return None
    return "\n\n".join(sections)[:MAX_GLOBAL_MEMORY_CHARS]
