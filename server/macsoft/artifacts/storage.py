from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path


class ArtifactStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishedFile:
    storage_key: str
    path: Path
    size_bytes: int
    sha256: str


class ArtifactStorage:
    """Same-volume staging and immutable final storage."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.staging_root = self.root / "staging"
        self.files_root = self.root / "files"
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self.files_root.mkdir(parents=True, exist_ok=True)

    def staging_dir(self, generation_id: str, attempt_id: str | None = None) -> Path:
        path = self.staging_root / generation_id
        if attempt_id is not None:
            path = path / attempt_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def final_path(self, storage_key: str) -> Path:
        candidate = (self.files_root / storage_key).resolve()
        if self.files_root not in candidate.parents:
            raise ArtifactStorageError("invalid_storage_key")
        return candidate

    def publish(self, source: Path, *, storage_key: str) -> PublishedFile:
        source = source.resolve()
        if self.staging_root not in source.parents or not source.is_file():
            raise ArtifactStorageError("invalid_staging_file")
        target = self.final_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        size = source.stat().st_size
        if target.exists():
            target_digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if target.stat().st_size == size and target_digest == digest:
                source.unlink(missing_ok=True)
                return PublishedFile(storage_key, target, size, digest)
            raise ArtifactStorageError("storage_key_collision")

        last_error: OSError | None = None
        for delay in (0.1, 0.25, 0.5):
            try:
                os.replace(source, target)
                return PublishedFile(storage_key, target, size, digest)
            except OSError as error:
                last_error = error
                time.sleep(delay)
        raise ArtifactStorageError("atomic_publish_failed") from last_error

    def remove_if_unreferenced(self, conn, *, storage_key: str) -> bool:
        referenced = conn.execute(
            """
            SELECT 1 FROM artifact_files
            WHERE storage_key = ? AND status = 'available' AND deleted_at IS NULL
            LIMIT 1
            """,
            (storage_key,),
        ).fetchone()
        if referenced is not None:
            return False
        self.final_path(storage_key).unlink(missing_ok=True)
        return True
