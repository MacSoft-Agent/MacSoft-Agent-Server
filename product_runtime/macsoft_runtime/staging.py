from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from .compatibility import (
    RUNTIME_DECLARATION_FILENAME,
    expected_runtime_metadata,
    load_runtime_metadata,
)
from .metadata import load_product_metadata


AI_EXCLUDED_DIRECTORIES = {
    ".git",
    ".github",
    ".plans",
    "__pycache__",
    "apps",
    "docs",
    "node_modules",
    "tests",
    "venv",
    "web",
    "website",
}
AI_EXCLUDED_FILES = {
    ".env",
    ".envrc",
    "AGENTS.md",
    "package-lock.json",
    "package.json",
}
FORBIDDEN_NAMES = {
    ".git",
    "auth.json",
    "macsoft-server.db",
    "state.db",
    "client_skills",
}


def _ignore_ai(directory: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in AI_EXCLUDED_DIRECTORIES or name in AI_EXCLUDED_FILES:
            ignored.add(name)
        elif name.endswith((".pyc", ".log", ".backup", ".bak")):
            ignored.add(name)
    return ignored


def _ignore_python(directory: str, names: list[str]) -> set[str]:
    current = Path(directory)
    ignored = {"__pycache__", "Doc", "include", "Scripts", "Tools"}.intersection(names)
    if current.name.lower() == "lib":
        ignored.add("site-packages")
        ignored.add("test")
    return ignored


def _ignore_generated(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name == "__pycache__" or name.endswith((".pyc", ".log", ".backup"))}


def _ignore_site_packages(directory: str, names: list[str]) -> set[str]:
    ignored = _ignore_generated(directory, names)
    for name in names:
        lowered = name.lower()
        if (
            lowered.startswith("__editable__.")
            or lowered.startswith("__editable___")
            or lowered.endswith(".egg-link")
            or lowered == "direct_url.json"
        ):
            ignored.add(name)
    return ignored


def _copy_runtime(source_root: Path, destination: Path) -> dict[str, str]:
    venv_python = source_root / "hermes" / "venv" / "Scripts" / "python.exe"
    if not venv_python.is_file():
        raise FileNotFoundError("The audited Hermes Python environment is missing.")
    probe = __import__("subprocess").run(
        [
            str(venv_python),
            "-c",
            "import json,platform,sys; print(json.dumps({'base':sys.base_prefix,'prefix':sys.prefix,'version':platform.python_version(),'architecture':platform.machine()}))",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    info = json.loads(probe.stdout)
    base = Path(info["base"])
    prefix = Path(info["prefix"])
    if base.resolve() == prefix.resolve():
        raise RuntimeError("Expected an isolated development environment, not the base Python installation.")
    shutil.copytree(base, destination, ignore=_ignore_python)
    site_packages = prefix / "Lib" / "site-packages"
    shutil.copytree(
        site_packages,
        destination / "Lib" / "site-packages",
        dirs_exist_ok=True,
        ignore=_ignore_site_packages,
    )
    pth = "\n".join(
        [
            "python312.zip",
            ".",
            "Lib",
            "DLLs",
            "Lib\\site-packages",
            "..",
            "..\\ai-service",
            "..\\server",
            "import site",
            "",
        ]
    )
    (destination / "python312._pth").write_text(pth, encoding="utf-8")
    return {
        "python_version": str(info["version"]),
        "architecture": str(info["architecture"]),
        "dependency_strategy": "audited-venv-site-packages-sanitized-and-merged-into-isolated-runtime",
    }


def _hash_manifest(root: Path) -> list[dict[str, object]]:
    result = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        result.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    return result


def _contains_development_path(text: str, development_root: Path) -> bool:
    normalized_text = text.replace("\\", "/").lower()
    normalized_root = str(development_root).replace("\\", "/").rstrip("/").lower()
    return bool(normalized_root and normalized_root in normalized_text)


def audit_staging(root: Path, development_root: Path) -> list[str]:
    issues: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        relative_parts = tuple(part.lower() for part in path.relative_to(root).parts)
        if any(part.lower() == ".git" for part in path.parts):
            issues.append(f"Git metadata included: {relative}")
        if path.is_file() and path.name.lower() in FORBIDDEN_NAMES:
            issues.append(f"Forbidden state file included: {relative}")
        if path.is_file() and path.name.lower() == "creds.json":
            issues.append(f"WhatsApp credential included: {relative}")
        if path.is_file() and path.name.lower() == ".env":
            issues.append(f"Runtime environment file included: {relative}")
        if path.is_file() and "pairing" in relative_parts[:-1]:
            issues.append(f"Pairing state included: {relative}")
        if path.is_file() and path.suffix.lower() == ".log":
            issues.append(f"Runtime log included: {relative}")
        if path.is_file() and path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            issues.append(f"Runtime database included: {relative}")
        if (
            path.is_file()
            and any(
                relative_parts[index:index + 3] == ("platforms", "whatsapp", "session")
                for index in range(max(0, len(relative_parts) - 2))
            )
        ):
            issues.append(f"WhatsApp session state included: {relative}")
        lowered_name = path.name.lower()
        if path.is_file() and (
            lowered_name.startswith("__editable__.")
            or lowered_name.startswith("__editable___")
            or lowered_name.endswith(".egg-link")
        ):
            issues.append(f"Editable Python install metadata included: {relative}")
    sensitive_files = [
        root / "templates" / "runtime" / "config.yaml",
        root / "templates" / "runtime" / "plugins" / "macsoft-autocount" / "config.json",
        root / "templates" / "server" / "macsoft-server.yaml",
    ]
    for path in sensitive_files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if _contains_development_path(text, development_root):
            issues.append(f"Development path included: {path.relative_to(root).as_posix()}")
    python_metadata = root / "python" / "Lib" / "site-packages"
    if python_metadata.is_dir():
        candidates = [
            path
            for path in python_metadata.rglob("*")
            if path.is_file()
            and (
                path.name.lower() == "direct_url.json"
                or path.name.lower().endswith(".pth")
                or path.name.lower().endswith(".egg-link")
                or path.name.lower().startswith("__editable___")
            )
        ]
        for path in candidates:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if _contains_development_path(text, development_root):
                issues.append(f"Development Python path included: {path.relative_to(root).as_posix()}")
    return issues


def build_staging(source_root: Path, desktop_directory: Path, output: Path) -> dict[str, object]:
    source_root = source_root.resolve()
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Staging output must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    metadata = load_product_metadata(source_root)
    runtime_metadata = load_runtime_metadata(
        source_root / "hermes" / RUNTIME_DECLARATION_FILENAME
    )
    if runtime_metadata != expected_runtime_metadata(metadata):
        raise ValueError(
            "Hermes runtime declaration does not match authoritative product.json."
        )
    desktop_package = json.loads((source_root / "hermes" / "apps" / "desktop" / "package.json").read_text("utf-8"))
    if desktop_package.get("version") != metadata.product_version:
        raise ValueError("Desktop version does not match authoritative product.json.")

    shutil.copy2(source_root / "product.json", output / "product.json")
    shutil.copytree(source_root / "product_runtime" / "macsoft_runtime", output / "macsoft_runtime", ignore=_ignore_generated)
    shutil.copytree(source_root / "packaging" / "templates", output / "templates", ignore=_ignore_generated)
    shutil.copytree(source_root / "server" / "macsoft", output / "server" / "macsoft", ignore=_ignore_generated)
    shutil.copytree(source_root / "hermes", output / "ai-service", ignore=_ignore_ai)
    shutil.copytree(desktop_directory.resolve(), output / "desktop")
    python_audit = _copy_runtime(source_root, output / "python")

    issues = audit_staging(output, source_root)
    if issues:
        raise RuntimeError("Staging audit failed:\n" + "\n".join(issues))
    manifest = {
        "product": metadata.product,
        "product_version": metadata.product_version,
        "build_id": metadata.build_id,
        "layout_version": 1,
        "python_strategy": "bundled-isolated-runtime",
        "python_audit": python_audit,
        "files": _hash_manifest(output),
    }
    (output / "staging-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"output": str(output), "files": len(manifest["files"]), "build_id": metadata.build_id}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build-macsoft-staging")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--desktop-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build_staging(args.source_root, args.desktop_dir, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
