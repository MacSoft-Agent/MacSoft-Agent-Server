from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .metadata import ProductMetadata
from .paths import ProductPaths


_LEGACY_MACSOFT_SOUL = (
    "Your name is MacSoft Agent.\n"
    "When asked who you are in English, identify yourself only as MacSoft Agent.\n"
    "When asked who you are in Chinese, identify yourself only as MacSoft 助手.\n"
    "Do not mention the underlying framework or upstream product name."
)


@dataclass
class InitializationResult:
    created: list[str] = field(default_factory=list)
    updated_protected: list[str] = field(default_factory=list)
    removed_protected: list[str] = field(default_factory=list)
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


_YAML_KEY_LINE = re.compile(r"^([ \t]*)([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]*(.*?))?(\r?\n)?$")


def _synchronize_yaml_scalar(path: Path, key_path: tuple[str, ...], value: str) -> bool:
    """Update one Host-owned YAML scalar without rewriting customer settings or comments."""
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    parents: list[tuple[int, str]] = []

    for index, line in enumerate(lines):
        match = _YAML_KEY_LINE.match(line)
        if not match:
            continue
        prefix, key, remainder, newline = match.groups()
        indent = len(prefix.expandtabs(8))
        while parents and parents[-1][0] >= indent:
            parents.pop()
        current_path = tuple(item[1] for item in parents) + (key,)
        if current_path == key_path:
            replacement = f"{prefix}{key}: {json.dumps(value)}{newline or ''}"
            if replacement == line:
                return False
            lines[index] = replacement
            _atomic_write(path, "".join(lines).encode("utf-8"))
            return True
        if not (remainder or "").strip() or (remainder or "").lstrip().startswith("#"):
            parents.append((indent, key))

    raise ValueError(f"{path.name} is missing required setting: {'.'.join(key_path)}")


def _migrate_yaml_scalar_if_equal(
    path: Path,
    key_path: tuple[str, ...],
    *,
    old_value: str,
    new_value: str,
) -> bool:
    """Migrate one exact historical scalar while retaining nearby customer text."""
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    parents: list[tuple[int, str]] = []

    for index, line in enumerate(lines):
        match = _YAML_KEY_LINE.match(line)
        if not match:
            continue
        prefix, key, remainder, newline = match.groups()
        indent = len(prefix.expandtabs(8))
        while parents and parents[-1][0] >= indent:
            parents.pop()
        current_path = tuple(item[1] for item in parents) + (key,)
        if current_path == key_path:
            raw_value, marker, comment = (remainder or "").partition("#")
            if raw_value.strip() != old_value:
                return False
            suffix = f" #{comment}" if marker else ""
            lines[index] = f"{prefix}{key}: {new_value}{suffix}{newline or ''}"
            _atomic_write(path, "".join(lines).encode("utf-8"))
            return True
        if not (remainder or "").strip() or (remainder or "").lstrip().startswith("#"):
            parents.append((indent, key))

    raise ValueError(f"{path.name} is missing required setting: {'.'.join(key_path)}")


def _ensure_yaml_list_item(path: Path, key_path: tuple[str, ...], value: str) -> bool:
    """Add one product-required YAML list item while preserving user settings.

    Runtime config is mutable and is intentionally not recopied on upgrades.
    This narrow migration lets a new product-owned capability become available
    without replacing the user's model, provider, or other configuration.
    """
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
    if len(key_path) == 1:
        target_index = None
        target_end = len(lines)
        for index, line in enumerate(lines):
            match = _YAML_KEY_LINE.match(line)
            if not match or len(match.group(1).expandtabs(8)) != 0:
                continue
            if target_index is None:
                if match.group(2) == key_path[0]:
                    target_index = index
                continue
            target_end = index
            break
        if target_index is None:
            if lines and lines[-1].strip():
                lines.append(newline)
            lines.extend((f"{key_path[0]}:{newline}", f"  - {value}{newline}"))
            _atomic_write(path, "".join(lines).encode("utf-8"))
            return True
        if any(re.search(rf"^\s*-\s*{re.escape(value)}\s*(?:#.*)?$", line) for line in lines[target_index + 1:target_end]):
            return False
        lines.insert(target_end, f"  - {value}{newline}")
        _atomic_write(path, "".join(lines).encode("utf-8"))
        return True
    if len(key_path) != 2:
        raise ValueError(f"Unsupported YAML list path: {'.'.join(key_path)}")

    parent_index = None
    parent_end = len(lines)
    for index, line in enumerate(lines):
        match = _YAML_KEY_LINE.match(line)
        if not match:
            continue
        prefix, key, _remainder, _newline = match.groups()
        indent = len(prefix.expandtabs(8))
        if parent_index is None:
            if indent == 0 and key == key_path[0]:
                parent_index = index
            continue
        if indent == 0:
            parent_end = index
            break

    if parent_index is None:
        raise ValueError(f"{path.name} is missing required mapping: {key_path[0]}")

    target_index = None
    for index in range(parent_index + 1, parent_end):
        match = _YAML_KEY_LINE.match(lines[index])
        if not match:
            continue
        prefix, key, _remainder, _newline = match.groups()
        if len(prefix.expandtabs(8)) == 2 and key == key_path[1]:
            target_index = index
            break

    if target_index is None:
        insertion = [
            f"  {key_path[1]}:{newline}",
            f"    - {value}{newline}",
        ]
        lines[parent_end:parent_end] = insertion
        _atomic_write(path, "".join(lines).encode("utf-8"))
        return True

    target_indent = 2
    list_start = target_index + 1
    list_end = list_start
    for index in range(list_start, parent_end):
        line = lines[index]
        match = _YAML_KEY_LINE.match(line)
        if match and len(match.group(1).expandtabs(8)) <= target_indent:
            list_end = index
            break
        list_end = index + 1

    if any(re.search(rf"^\s*-\s*{re.escape(value)}\s*(?:#.*)?$", line) for line in lines[list_start:list_end]):
        return False

    lines.insert(list_end, f"{' ' * (target_indent + 2)}- {value}{newline}")
    _atomic_write(path, "".join(lines).encode("utf-8"))
    return True


def _remove_yaml_list_item(path: Path, key_path: tuple[str, ...], value: str) -> bool:
    """Remove one exact top-level YAML list item while preserving surrounding text."""
    if len(key_path) != 1:
        raise ValueError(f"Unsupported YAML list path: {'.'.join(key_path)}")
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    target_index = None
    target_end = len(lines)
    for index, line in enumerate(lines):
        match = _YAML_KEY_LINE.match(line)
        if not match or len(match.group(1).expandtabs(8)) != 0:
            continue
        if target_index is None:
            if match.group(2) == key_path[0]:
                target_index = index
            continue
        target_end = index
        break
    if target_index is None:
        return False
    item_pattern = re.compile(rf"^\s*-\s*{re.escape(value)}\s*(?:#.*)?(?:\r?\n)?$")
    for index in range(target_index + 1, target_end):
        if item_pattern.match(lines[index]):
            del lines[index]
            _atomic_write(path, "".join(lines).encode("utf-8"))
            return True
    return False


def _load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8-sig") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return value


def _relative_manifest_path(value: object, field_name: str) -> str:
    """Normalize a manifest path while rejecting traversal outside the data root."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Protected resource {field_name} must be non-empty text.")
    normalized = value.replace("\\", "/").strip("/")
    parts = Path(normalized).parts
    if not normalized or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Protected resource {field_name} contains an unsafe path.")
    return "/".join(parts)


def _sync_protected_file(
    *,
    source: Path,
    destination: Path,
    relative_destination: str,
    bundled_version: int,
    state: dict,
    protected_state: dict,
    result: InitializationResult,
) -> None:
    """Synchronize one protected file using the same conflict rules everywhere."""
    source_hash = _sha256(source)
    previous = protected_state.get(relative_destination, {})
    previous_hash = previous.get("hash") if isinstance(previous, dict) else None
    previously_conflicted = (
        previous.get("conflicted") is True if isinstance(previous, dict) else False
    )
    current_hash = _sha256(destination) if destination.exists() else None

    if current_hash is None:
        _atomic_write(destination, source.read_bytes())
        result.created.append(relative_destination)
        current_hash = source_hash
        conflicted = False
    elif current_hash == source_hash:
        result.preserved.append(relative_destination)
        # The administrator may have restored a previously conflicting file to
        # the current bundled content; it is managed again from this point.
        conflicted = False
    elif (
        previous_hash
        and current_hash == previous_hash
        and not previously_conflicted
        and int(state.get("protected_version", 0)) < bundled_version
    ):
        _atomic_write(destination, source.read_bytes())
        result.updated_protected.append(relative_destination)
        current_hash = source_hash
        conflicted = False
    else:
        # A locally changed protected file is customer/administrator state from
        # the initializer's perspective. Keep it intact and report a conflict.
        result.conflicts.append(relative_destination)
        conflicted = True

    protected_state[relative_destination] = {
        "bundled_hash": source_hash,
        "hash": current_hash,
        "conflicted": conflicted,
        "version": bundled_version,
    }


def _sync_protected_directory(
    *,
    source_root: Path,
    destination_root: Path,
    relative_destination_root: str,
    bundled_version: int,
    state: dict,
    protected_state: dict,
    result: InitializationResult,
    include_directories: tuple[str, ...] = (),
) -> None:
    """Synchronize a managed directory without touching unknown runtime files.

    The manifest owns individual files below this directory, not the whole target
    directory. This lets the product remove an unchanged obsolete file while
    preserving files installed or edited outside MacSoft's managed set.
    """
    source_files = {
        path.relative_to(source_root).as_posix(): path
        for path in source_root.rglob("*")
        if path.is_file()
        and (
            not include_directories
            or path.relative_to(source_root).parts[0] in include_directories
        )
    }
    managed_prefix = relative_destination_root.rstrip("/") + "/"

    for relative_path, source in source_files.items():
        relative_destination = f"{managed_prefix}{relative_path}"
        _sync_protected_file(
            source=source,
            destination=destination_root / relative_path,
            relative_destination=relative_destination,
            bundled_version=bundled_version,
            state=state,
            protected_state=protected_state,
            result=result,
        )

    # Reconcile files removed from the source directory. Only remove files that
    # still match the last deployed hash; unknown files and local edits survive.
    for relative_destination in list(protected_state):
        if not relative_destination.startswith(managed_prefix):
            continue
        if relative_destination in {
            f"{managed_prefix}{relative_path}" for relative_path in source_files
        }:
            continue
        previous = protected_state.get(relative_destination, {})
        # ``bundled_hash`` is the last desired product content. ``hash`` may
        # intentionally be the local conflicting content kept in runtime.
        previous_hash = previous.get("bundled_hash") if isinstance(previous, dict) else None
        relative_path = relative_destination[len(managed_prefix) :]
        destination = destination_root / relative_path
        current_hash = _sha256(destination) if destination.exists() else None
        if (
            destination.exists()
            and current_hash == previous_hash
            and int(state.get("protected_version", 0)) < bundled_version
        ):
            destination.unlink()
            result.removed_protected.append(relative_destination)
            protected_state.pop(relative_destination, None)
        elif destination.exists():
            result.conflicts.append(relative_destination)


def _reconcile_removed_protected_resources(
    *,
    paths: ProductPaths,
    active_resources: set[str],
    managed_directory_roots: tuple[str, ...],
    bundled_version: int,
    state: dict,
    protected_state: dict,
    result: InitializationResult,
) -> None:
    """Remove obsolete unchanged managed files while preserving local edits."""
    if int(state.get("protected_version", 0)) >= bundled_version:
        return
    for relative_destination in list(protected_state):
        if relative_destination in active_resources:
            continue
        if any(
            relative_destination.startswith(root.rstrip("/") + "/")
            for root in managed_directory_roots
        ):
            # Managed-directory reconciliation owns these files.
            continue
        previous = protected_state.get(relative_destination, {})
        previous_hash = previous.get("bundled_hash") if isinstance(previous, dict) else None
        destination = paths.data_root / relative_destination
        if not destination.exists():
            protected_state.pop(relative_destination, None)
            continue
        current_hash = _sha256(destination)
        if previous_hash and current_hash == previous_hash:
            destination.unlink()
            result.removed_protected.append(relative_destination)
            protected_state.pop(relative_destination, None)
        elif relative_destination not in result.conflicts:
            result.conflicts.append(relative_destination)


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

    # Identity is mutable customer data, so only migrate the exact historical
    # MacSoft template. Any administrator-authored SOUL.md remains untouched.
    try:
        existing_soul = paths.soul_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        existing_soul = ""
    normalized_soul = existing_soul.replace("\r\n", "\n").replace("\r", "\n").strip()
    if normalized_soul == _LEGACY_MACSOFT_SOUL:
        source_soul = (paths.templates_root / "runtime" / "SOUL.md").read_bytes()
        _atomic_write(paths.soul_file, source_soul)

    # The localhost API credential is generated and owned by the Host. Keep the
    # independently preserved runtime and Server YAML files aligned while
    # leaving every provider credential and customer setting untouched.
    _synchronize_yaml_scalar(
        paths.runtime_config,
        ("platforms", "api_server", "extra", "key"),
        local_api_key,
    )
    _ensure_yaml_list_item(
        paths.runtime_config,
        ("platform_toolsets", "api_server"),
        "hermes-api-server",
    )
    _ensure_yaml_list_item(
        paths.runtime_config,
        ("platform_toolsets", "whatsapp"),
        "hermes-whatsapp",
    )
    _remove_yaml_list_item(
        paths.runtime_config,
        ("plugin_extensible_platform_toolsets",),
        "whatsapp",
    )
    if paths.is_packaged:
        _synchronize_yaml_scalar(
            paths.server_config,
            ("hermes", "api_key"),
            local_api_key,
        )
        _migrate_yaml_scalar_if_equal(
            paths.server_config,
            ("hermes", "request_timeout_seconds"),
            old_value="600",
            new_value="7200",
        )

    if not paths.server_database.exists():
        connection = sqlite3.connect(paths.server_database)
        connection.close()
        result.created.append(str(paths.server_database.relative_to(paths.data_root)))

    resource_manifest = _load_json(paths.templates_root / "protected-resources.json", {})
    bundled_version = int(resource_manifest.get("version", 0))
    protected_state = state.get("protected")
    if not isinstance(protected_state, dict):
        protected_state = {}

    active_resources: set[str] = set()
    for item in resource_manifest.get("resources", []):
        if not isinstance(item, dict):
            continue
        relative_source = _relative_manifest_path(item.get("source"), "source")
        relative_destination = _relative_manifest_path(item.get("destination"), "destination")
        active_resources.add(relative_destination)
        source = paths.templates_root / relative_source
        destination = paths.data_root / relative_destination
        _sync_protected_file(
            source=source,
            destination=destination,
            relative_destination=relative_destination,
            bundled_version=bundled_version,
            state=state,
            protected_state=protected_state,
            result=result,
        )

    managed_directory_roots: list[str] = []
    for item in resource_manifest.get("directories", []):
        if not isinstance(item, dict):
            continue
        relative_source = _relative_manifest_path(item.get("source"), "source")
        relative_destination = _relative_manifest_path(item.get("destination"), "destination")
        managed_directory_roots.append(relative_destination)
        source_root = paths.templates_root / relative_source
        destination_root = paths.data_root / relative_destination
        _sync_protected_directory(
            source_root=source_root,
            destination_root=destination_root,
            relative_destination_root=relative_destination,
            bundled_version=bundled_version,
            state=state,
            protected_state=protected_state,
            result=result,
            include_directories=tuple(
                str(value)
                for value in item.get("include_directories", [])
                if isinstance(value, str) and value
            ),
        )

    _reconcile_removed_protected_resources(
        paths=paths,
        active_resources=active_resources,
        managed_directory_roots=tuple(managed_directory_roots),
        bundled_version=bundled_version,
        state=state,
        protected_state=protected_state,
        result=result,
    )

    next_state = {
        "schema_version": metadata.data_schema_version,
        "protected_version": bundled_version,
        "product_version": metadata.product_version,
        "local_api_key": local_api_key,
        "protected": protected_state,
    }
    _atomic_write(state_path, (json.dumps(next_state, indent=2) + "\n").encode("utf-8"))
    return result
