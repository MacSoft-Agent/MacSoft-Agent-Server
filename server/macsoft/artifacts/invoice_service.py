from __future__ import annotations

from macsoft.artifacts.contract import serialize_artifact
from macsoft.artifacts.invoice_chart import (
    build_invoice_count_render_input,
    fetch_latest_sales_invoices,
)
from macsoft.artifacts.repository import create_generation, enqueue_render_job
from macsoft.artifacts.worker import ChartRenderWorker, resolve_artifact_storage
from macsoft.db import connect_db
from macsoft.sessions.message_store import create_pending_assistant_message


def generate_invoice_count_artifact(
    config,
    *,
    request_id: str,
    session_id: str,
    assistant_message_id: str,
    owner_user_id: str,
    owner_device_id: str,
) -> dict:
    # The current Connector completes a 20-row bounded header read reliably
    # within the interactive command timeout. The chart labels this sample as
    # "latest" and never presents it as a complete accounting period.
    rows = fetch_latest_sales_invoices(config, limit=20)
    render_input = build_invoice_count_render_input(rows)
    conn = connect_db(config)
    try:
        create_pending_assistant_message(
            conn,
            session_id=session_id,
            user_id=owner_user_id,
            owner_device_id=owner_device_id,
            message_id=assistant_message_id,
            model="server-autocount-chart",
        )
        generation_id = create_generation(
            conn,
            request_id=request_id,
            session_id=session_id,
            assistant_message_id=assistant_message_id,
            owner_user_id=owner_user_id,
            owner_device_id=owner_device_id,
            source_type="autocount",
            render_input=render_input,
            environment=config.chart_artifacts.environment,
            render_input_ttl_minutes=config.chart_artifacts.render_input_ttl_minutes,
        )
        job_id = enqueue_render_job(
            conn,
            generation_id=generation_id,
            requested_formats=("png", "pdf"),
            max_attempts=config.chart_artifacts.worker_max_attempts,
        )
    finally:
        conn.close()
    worker = ChartRenderWorker(
        config,
        worker_id=f"inline-chart-{request_id}",
        storage=resolve_artifact_storage(config),
    )
    worker.process_one(job_id=job_id)
    conn = connect_db(config)
    try:
        artifact = conn.execute(
            "SELECT artifact_id FROM artifacts WHERE generation_id = ?",
            (generation_id,),
        ).fetchone()
        if artifact is None:
            failure = conn.execute(
                "SELECT error_code FROM artifact_generations WHERE generation_id = ?",
                (generation_id,),
            ).fetchone()
            raise RuntimeError(str(failure["error_code"] if failure else "chart_render_failed"))
        payload = serialize_artifact(conn, str(artifact["artifact_id"]))
        if payload is None:
            raise RuntimeError("chart_artifact_unavailable")
        return payload
    finally:
        conn.close()
