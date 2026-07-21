from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .metadata import ProductMetadata
from .paths import ProductPaths


@dataclass
class InitializationResult:
    created: list[str] = field(default_factory=list)
    updated_protected: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _copy_template_once(source: Path, destination: Path, replacements: dict[str, str]) -> bool:
    if destination.exists():
        return False
    raw = source.read_text(encoding="utf-8")
    for old, new in replacements.items():
        raw = raw.replace(old, new)
    _atomic_write(destination, raw.encode("utf-8"))
    return True


def _load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8-sig") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return value


def initialize_product_data(paths: ProductPaths, metadata: ProductMetadata) -> InitializationResult:
    """Create packaged writable state without importing developer or customer data.

    Mutable templates are create-once. Protected program resources are upgraded only
    when their on-disk hash still matches the hash recorded by the previous product
    initialization; locally changed files are retained and reported as conflicts.
    """
    result = InitializationResult()
    for directory in (
        paths.data_root,
        paths.runtime_root,
        paths.server_data_root,
        paths.server_database.parent,
        paths.config_root,
        paths.logs_root,
        paths.backup_root,
        paths.host_state_root,
    ):
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            result.created.append(str(directory.relative_to(paths.data_root)))

    state_path = paths.config_root / "initialization.json"
    state = _load_json(state_path, {"schema_version": 0, "protected": {}})
    local_api_key = state.get("local_api_key")
    if not isinstance(local_api_key, str) or len(local_api_key) < 32:
        local_api_key = secrets.token_urlsafe(32)
    replacements = {"${MACSOFT_LOCAL_API_KEY}": local_api_key}

    mutable_templates = (
        (paths.templates_root / "runtime" / "config.yaml", paths.runtime_config),
        (paths.templates_root / "runtime" / "SOUL.md", paths.soul_file),
        (
            paths.templates_root / "runtime" / "plugins" / "macsoft-autocount" / "config.json",
            paths.autocount_plugin_root / "config.json",
        ),
        (paths.templates_root / "server" / "macsoft-server.yaml", paths.server_config),
    )
    for source, destination in mutable_templates:
        if _copy_template_once(source, destination, replacements):
            result.created.append(str(destination.relative_to(paths.data_root)))
        else:
            result.preserved.append(str(destination.relative_to(paths.data_root)))

    if not paths.server_database.exists():
        connection = sqlite3.connect(paths.server_database)
        connection.close()
        result.created.append(str(paths.server_database.relative_to(paths.data_root)))

    resource_manifest = _load_json(paths.templates_root / "protected-resources.json", {})
    bundled_version = int(resource_manifest.get("version", 0))
    protected_state = state.get("protected")
    if not isinstance(protected_state, dict):
        protected_state = {}

    for item in resource_manifest.get("resources", []):
        if not isinstance(item, dict):
            continue
        relative_source = str(item["source"])
        relative_destination = str(item["destination"])
        source = paths.templates_root / relative_source
        destination = paths.data_root / relative_destination
        source_hash = _sha256(source)
        previous = protected_state.get(relative_destination, {})
        previous_hash = previous.get("hash") if isinstance(previous, dict) else None
        current_hash = _sha256(destination) if destination.exists() else None

        if current_hash is None:
            _atomic_write(destination, source.read_bytes())
            result.created.append(relative_destination)
            current_hash = source_hash
        elif current_hash == source_hash:
            result.preserved.append(relative_destination)
        elif previous_hash and current_hash == previous_hash and int(state.get("protected_version", 0)) < bundled_version:
            _atomic_write(destination, source.read_bytes())
            result.updated_protected.append(relative_destination)
            current_hash = source_hash
        else:
            result.conflicts.append(relative_destination)

        protected_state[relative_destination] = {
            "bundled_hash": source_hash,
            "hash": current_hash,
            "version": bundled_version,
        }

    next_state = {
        "schema_version": metadata.data_schema_version,
        "protected_version": bundled_version,
        "product_version": metadata.product_version,
        "local_api_key": local_api_key,
        "protected": protected_state,
    }
    _atomic_write(state_path, (json.dumps(next_state, indent=2) + "\n").encode("utf-8"))
    return result
