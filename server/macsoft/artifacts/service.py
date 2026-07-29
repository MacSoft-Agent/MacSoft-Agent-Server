from __future__ import annotations

from typing import Any

from macsoft.artifacts.repository import create_generation, enqueue_render_job
from macsoft.security import new_id
from macsoft.sessions.message_store import create_pending_assistant_message


def create_foundation_mock_job(
    conn,
    config,
    *,
    request_id: str,
    session_id: str,
    owner_user_id: str,
    owner_device_id: str,
    render_input: dict[str, Any],
    requested_formats: tuple[str, ...] = ("png",),
) -> dict[str, str]:
    """Internal test harness entry point; never registered as a production route."""

    if config.chart_artifacts.environment not in {"test", "development"}:
        raise ValueError("foundation_test_harness_disabled")
    assistant_message_id = new_id("msg_assistant")
    create_pending_assistant_message(
        conn,
        session_id=session_id,
        user_id=owner_user_id,
        owner_device_id=owner_device_id,
        message_id=assistant_message_id,
        model="server-foundation-mock",
    )
    generation_id = create_generation(
        conn,
        request_id=request_id,
        session_id=session_id,
        assistant_message_id=assistant_message_id,
        owner_user_id=owner_user_id,
        owner_device_id=owner_device_id,
        source_type="mock",
        render_input=render_input,
        environment=config.chart_artifacts.environment,
        render_input_ttl_minutes=config.chart_artifacts.render_input_ttl_minutes,
    )
    job_id = enqueue_render_job(
        conn,
        generation_id=generation_id,
        requested_formats=requested_formats,
        max_attempts=config.chart_artifacts.worker_max_attempts,
    )
    return {
        "assistant_message_id": assistant_message_id,
        "generation_id": generation_id,
        "job_id": job_id,
    }
