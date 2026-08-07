from __future__ import annotations

import re
import sqlite3
import os
from pathlib import Path
from typing import Any

import yaml

from macsoft.security import new_id, utc_now_iso


PROFILE_SCHEMA_VERSION = 1
_PROFILE_ID_RE = re.compile(r"^prof_[a-f0-9]{32}$")
_PROFILE_CONFIG_SECRET_KEYS = frozenset({
    "api_key",
    "api_key_env",
    "authorization",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
})


def _is_secret_config_key(key: Any) -> bool:
    text = str(key).lower()
    compact = re.sub(r"[^a-z0-9]", "", text)
    if text in _PROFILE_CONFIG_SECRET_KEYS:
        return True
    # Provider/plugin configs are not consistent about snake_case. Reject
    # common camelCase, prefixed and hyphenated secret names as well.
    return any(
        marker in compact
        for marker in (
            "apikey",
            "authorization",
            "credential",
            "password",
            "secret",
            "token",
        )
    )


def configured_profile_root(config: Any) -> Path:
    """Return the Server-owned root shared with the internal Hermes service."""
    # The Host supplies this for the packaged Server and Hermes processes.
    # It must win over a development config value so both processes derive the
    # exact same ProgramData runtime tree.
    configured = os.environ.get("MACSOFT_PROFILE_ROOT", "").strip()
    if not configured:
        hermes = getattr(config, "hermes", None)
        configured = str(getattr(hermes, "profile_root", "")).strip()
    if configured:
        root = Path(configured).expanduser()
        if not root.is_absolute():
            config_path = getattr(config, "config_path", None)
            base = Path(config_path).expanduser().resolve().parent if config_path else Path.cwd()
            root = base / root
        return root.resolve()
    database_path = Path(str(config.database.path)).expanduser().resolve()
    return database_path.parent / "profiles"


def _profile_home(profile_root: Path, profile_id: str) -> Path:
    if not _PROFILE_ID_RE.fullmatch(profile_id):
        raise ValueError("invalid_profile_id")
    profile_root = profile_root.resolve()
    candidate = (profile_root / profile_id).resolve()
    if candidate.parent != profile_root:
        raise ValueError("invalid_profile_path")
    return candidate


def _configured_hermes_home(config: Any) -> Path | None:
    """Resolve the shared Server-owned Hermes runtime home, if configured."""
    # The Host owns the deployed runtime location.  Its environment must win
    # over the development YAML default (typically ../hermes, the source tree)
    # or existing device Profiles would inherit no model configuration.
    configured = os.environ.get("HERMES_HOME", "").strip()
    if not configured:
        hermes = getattr(config, "hermes", None)
        configured = str(getattr(hermes, "home", "")).strip()
    if not configured:
        # The Host always injects the profile root into the Server process.
        # Its parent is the shared Hermes runtime, so this remains a
        # Server-owned derivation rather than a Client-controlled path.  It
        # also keeps existing Profiles able to inherit a later model switch
        # when a service wrapper omitted HERMES_HOME from its environment.
        profile_root = os.environ.get("MACSOFT_PROFILE_ROOT", "").strip()
        if profile_root:
            try:
                root = Path(profile_root).expanduser().resolve()
                if root.name == "profiles":
                    return root.parent
            except OSError:
                pass
    if not configured:
        return None

    home = Path(configured).expanduser()
    if not home.is_absolute():
        config_path = getattr(config, "config_path", None)
        base = Path(config_path).expanduser().resolve().parent if config_path else Path.cwd()
        home = base / home
    return home.resolve()


def _without_embedded_secrets(value: Any) -> Any:
    """Copy behavioral config without copying credentials into device state."""
    if isinstance(value, list):
        return [_without_embedded_secrets(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        str(key): _without_embedded_secrets(item)
        for key, item in value.items()
        if not _is_secret_config_key(key)
    }


def _initial_profile_config(config: Any) -> dict[str, Any]:
    """Build a profile-local Hermes config from the trusted shared runtime.

    Profile homes need the Server's model and behavioral configuration because
    Hermes resolves config through the context-local home. Credentials never
    become Profile files: they remain in the shared runtime secret scope.
    """
    source_home = _configured_hermes_home(config)
    source_path = source_home / "config.yaml" if source_home is not None else None
    source: Any = {}
    if source_path is not None and source_path.is_file():
        try:
            source = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            source = {}
    profile_config = _without_embedded_secrets(source)
    if not isinstance(profile_config, dict):
        profile_config = {}

    memory = profile_config.setdefault("memory", {})
    if isinstance(memory, dict):
        memory.update({
            "memory_enabled": True,
            "user_profile_enabled": True,
            "nudge_interval": 1,
        })
    skills = profile_config.setdefault("skills", {})
    if isinstance(skills, dict):
        skills["creation_nudge_interval"] = 1
        if source_home is not None:
            shared_skills = str((source_home / "skills").resolve())
            global_skills = str((source_home / "global" / "skills" / "learned").resolve())
            configured_dirs = skills.get("external_dirs", [])
            if isinstance(configured_dirs, str):
                configured_dirs = [configured_dirs]
            if not isinstance(configured_dirs, list):
                configured_dirs = []
            skills["external_dirs"] = [
                shared_skills,
                global_skills,
                *(
                    item
                    for item in configured_dirs
                    if str(item) not in {shared_skills, global_skills}
                ),
            ]
    curator = profile_config.setdefault("curator", {})
    if isinstance(curator, dict):
        curator.update({"enabled": True, "consolidate": False})
    return profile_config


def _initialize_profile_home(profile_home: Path, *, config: Any) -> None:
    """Create the smallest safe native Hermes profile shape.

    The profile root is exclusively Server-owned.  Individual profile files are
    intentionally not exposed through any Client request or response.
    """
    for path in (
        profile_home / "memories",
        profile_home / "skills" / "private",
        profile_home / "skills" / "learned",
        profile_home / "sessions",
        profile_home / "logs",
        profile_home / "curator",
        profile_home / "backups",
    ):
        path.mkdir(parents=True, exist_ok=True)

    for path in (profile_home / "memories" / "USER.md", profile_home / "memories" / "MEMORY.md"):
        if not path.exists():
            path.write_text("", encoding="utf-8")

    config_path = profile_home / "config.yaml"
    if not config_path.exists():
        config_path.write_text(
            yaml.safe_dump(_initial_profile_config(config), sort_keys=False),
            encoding="utf-8",
        )
    else:
        # Keep Server-owned behavioral settings current for existing device
        # Profiles.  Credentials deliberately remain in the shared runtime,
        # but model selection must not be frozen at the time a Profile was
        # first paired: a later `hermes model` change applies to every device.
        #
        # Do not copy arbitrary shared config here.  Profile-local learning
        # state stays local; this only synchronizes the non-secret model block
        # and the shared read-only Skill layer that the Server owns.
        try:
            current = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            current = {}
        if isinstance(current, dict):
            changed = False
            shared_model = _initial_profile_config(config).get("model")
            if isinstance(shared_model, dict):
                if current.get("model") != shared_model:
                    current["model"] = shared_model
                    changed = True
            elif "model" in current:
                # The shared configuration is authoritative.  Removing a stale
                # Profile-local model avoids silently using an old provider.
                current.pop("model", None)
                changed = True

            source_home = _configured_hermes_home(config)
            if source_home is not None:
                skills = current.setdefault("skills", {})
                if isinstance(skills, dict):
                    shared_skills = str((source_home / "skills").resolve())
                    global_skills = str((source_home / "global" / "skills" / "learned").resolve())
                    external = skills.get("external_dirs", [])
                    if isinstance(external, str):
                        external = [external]
                    if not isinstance(external, list):
                        external = []
                    merged = [
                        shared_skills,
                        global_skills,
                        *(
                            item
                            for item in external
                            if str(item) not in {shared_skills, global_skills}
                        ),
                    ]
                    if merged != external:
                        skills["external_dirs"] = merged
                        changed = True
            if changed:
                config_path.write_text(
                    yaml.safe_dump(_without_embedded_secrets(current), sort_keys=False),
                    encoding="utf-8",
                )


def _row_to_profile(row: sqlite3.Row) -> dict[str, str | int | None]:
    return {
        "profile_id": str(row["profile_id"]),
        "device_id": str(row["device_id"]),
        "status": str(row["status"]),
        "profile_schema_version": int(row["profile_schema_version"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "last_used_at": row["last_used_at"],
    }


def ensure_device_profile(conn: sqlite3.Connection, *, config: Any, device_id: str) -> dict[str, str | int | None]:
    """Return the active profile for *device_id*, provisioning it once.

    A database write lock makes concurrent first use deterministic.  The
    directory is created only from the server-selected opaque ID, never a
    caller-supplied path.
    """
    profile_root = configured_profile_root(config)
    profile_root.mkdir(parents=True, exist_ok=True)
    now = utc_now_iso()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT * FROM device_profiles WHERE device_id = ?", (device_id,)
        ).fetchone()
        if row is None:
            profile_id = new_id("prof")
            profile_home = _profile_home(profile_root, profile_id)
            _initialize_profile_home(profile_home, config=config)
            conn.execute(
                """
                INSERT INTO device_profiles (
                    profile_id, device_id, status, profile_schema_version,
                    created_at, updated_at, last_used_at
                ) VALUES (?, ?, 'active', ?, ?, ?, ?)
                """,
                (profile_id, device_id, PROFILE_SCHEMA_VERSION, now, now, now),
            )
            row = conn.execute(
                "SELECT * FROM device_profiles WHERE profile_id = ?", (profile_id,)
            ).fetchone()
        else:
            if row["status"] != "active":
                raise ValueError("device_profile_inactive")
            conn.execute(
                "UPDATE device_profiles SET updated_at = ?, last_used_at = ? WHERE profile_id = ?",
                (now, now, row["profile_id"]),
            )
            row = conn.execute(
                "SELECT * FROM device_profiles WHERE profile_id = ?", (row["profile_id"],)
            ).fetchone()
            _initialize_profile_home(
                _profile_home(profile_root, str(row["profile_id"])),
                config=config,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    if row is None:  # pragma: no cover - defensive database invariant
        raise RuntimeError("device_profile_not_created")
    return _row_to_profile(row)


def require_device_profile(conn: sqlite3.Connection, *, config: Any, device_id: str) -> dict[str, str | int | None]:
    """Return an existing active profile and refresh its last-used timestamp."""
    return ensure_device_profile(conn, config=config, device_id=device_id)


def resolve_profile_home(config: Any, *, profile_id: str) -> Path:
    """Resolve a canonical profile home for a registry-owned opaque ID."""
    return _profile_home(configured_profile_root(config), profile_id)
