from __future__ import annotations

import shutil
from pathlib import Path

from macsoft.artifacts.renderer import ChartRenderError, load_render_input, render_chart_png
from macsoft.artifacts.repository import (
    claim_render_job,
    finalize_render,
    mark_render_failure,
    owns_lease,
)
from macsoft.artifacts.storage import ArtifactStorage
from macsoft.db import connect_db


class ChartRenderWorker:
    """Single-process Foundation worker with fenced SQLite leases."""

    def __init__(self, config, *, worker_id: str, storage: ArtifactStorage):
        self.config = config
        self.worker_id = worker_id
        self.storage = storage

    def process_one(self) -> bool:
        conn = connect_db(self.config)
        try:
            job = claim_render_job(
                conn,
                worker_id=self.worker_id,
                lease_seconds=self.config.chart_artifacts.lease_seconds,
            )
        finally:
            conn.close()
        if job is None:
            return False

        # Each fenced attempt gets its own staging and immutable final key. A
        # Worker that loses its lease can therefore neither overwrite nor
        # collide with the valid Worker's output.
        staging = self.storage.staging_dir(job.generation_id, job.lease_token)
        png_path = staging / "chart.png"
        published = None
        try:
            render_input = load_render_input(job.render_input_json)
            render_chart_png(render_input, png_path)
            conn = connect_db(self.config)
            try:
                if not owns_lease(
                    conn,
                    job_id=job.job_id,
                    worker_id=self.worker_id,
                    lease_token=job.lease_token,
                ):
                    raise ChartRenderError("render_lease_lost")
            finally:
                conn.close()

            storage_key = f"{job.generation_id}/{job.lease_token}/chart.png"
            published = self.storage.publish(png_path, storage_key=storage_key)
            conn = connect_db(self.config)
            try:
                title = str(render_input.get("title") or "Demo Chart")
                summary = str(render_input.get("summary") or "Chart generated from a Foundation test dataset.")
                metadata = dict(render_input.get("metadata") or {})
                metadata.setdefault("source", {"type": "mock"})
                finalize_render(
                    conn,
                    job=job,
                    worker_id=self.worker_id,
                    title=title,
                    summary=summary,
                    metadata=metadata,
                    png_file={
                        "filename": "demo-chart.png",
                        "content_type": "image/png",
                        "size_bytes": published.size_bytes,
                        "sha256": published.sha256,
                        "storage_key": published.storage_key,
                    },
                )
            finally:
                conn.close()
            return True
        except Exception as error:
            conn = connect_db(self.config)
            try:
                mark_render_failure(
                    conn,
                    job_id=job.job_id,
                    worker_id=self.worker_id,
                    lease_token=job.lease_token,
                    code=getattr(error, "args", ["render_failed"])[0] or "render_failed",
                    message=str(error) or "Render failed.",
                )
                if published is not None:
                    self.storage.remove_if_unreferenced(conn, storage_key=published.storage_key)
            finally:
                conn.close()
            return True
        finally:
            shutil.rmtree(staging, ignore_errors=True)


def resolve_artifact_storage(config) -> ArtifactStorage:
    configured = Path(config.chart_artifacts.storage_path)
    if not configured.is_absolute():
        configured = Path(config.config_path).resolve().parent / configured
    return ArtifactStorage(configured)
