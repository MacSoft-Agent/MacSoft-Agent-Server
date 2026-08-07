from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HermesApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        service: str = "ai_service",
        kind: str = "unknown",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.service = service
        self.kind = kind
        self.status_code = status_code


def _normalized_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "")).strip()
        raw_content = message.get("content", "")
        if role == "user" and isinstance(raw_content, list):
            if raw_content:
                normalized.append({"role": role, "content": raw_content})
            continue
        content = str(raw_content)
        if role in {"system", "user", "assistant"} and content.strip():
            normalized.append({"role": role, "content": content})
    if not normalized:
        raise HermesApiError(
            "MacSoft Agent request has no valid messages.",
            kind="invalid_request",
        )
    return normalized


def _api_request(
    *,
    base_url: str,
    api_key: str,
    messages: list[dict[str, Any]],
    stream: bool,
) -> Request:
    payload = {
        "model": "hermes-agent",
        "messages": _normalized_messages(messages),
        "stream": stream,
    }
    return Request(
        url=f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        },
        method="POST",
    )


def _raise_transport_error(
    error: Exception,
    *,
    base_url: str,
    timeout_seconds: int,
) -> None:
    if isinstance(error, HTTPError):
        raise HermesApiError(
            f"MacSoft Agent service returned HTTP {error.code}.",
            kind="authentication" if error.code == 401 else "http_error",
            status_code=error.code,
        ) from error
    if isinstance(error, URLError):
        raise HermesApiError(
            "Cannot connect to MacSoft Agent service.",
            kind="unavailable",
        ) from error
    if isinstance(error, TimeoutError):
        raise HermesApiError(
            f"MacSoft Agent service timed out after {timeout_seconds} seconds.",
            kind="timeout",
        ) from error
    raise error


def request_hermes_reply(
    *,
    base_url: str,
    api_key: str,
    messages: list[dict[str, Any]],
    timeout_seconds: int,
) -> str:
    request = _api_request(
        base_url=base_url,
        api_key=api_key,
        messages=messages,
        stream=False,
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as error:
        _raise_transport_error(
            error,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )

    try:
        result = json.loads(raw_body)
    except json.JSONDecodeError as error:
        raise HermesApiError(
            "MacSoft Agent service returned invalid JSON.",
            kind="protocol",
        ) from error

    choices = result.get("choices")

    if not isinstance(choices, list) or not choices:
        raise HermesApiError(
            "MacSoft Agent service response does not contain choices.",
            kind="protocol",
        )

    first_choice = choices[0]

    if not isinstance(first_choice, dict):
        raise HermesApiError(
            "MacSoft Agent service returned an invalid choice.",
            kind="protocol",
        )

    message = first_choice.get("message")

    if not isinstance(message, dict):
        raise HermesApiError(
            "MacSoft Agent service response does not contain an assistant message.",
            kind="protocol",
        )

    assistant_text = str(message.get("content") or "").strip()

    if not assistant_text:
        raise HermesApiError(
            "MacSoft Agent service returned an empty assistant response.",
            kind="protocol",
        )

    return assistant_text


def stream_hermes_reply_events(
    *,
    base_url: str,
    api_key: str,
    messages: list[dict[str, Any]],
    timeout_seconds: int,
) -> Iterator[dict[str, str]]:
    """Yield controlled text and Tool lifecycle events from one Agent run."""

    request = _api_request(
        base_url=base_url,
        api_key=api_key,
        messages=messages,
        stream=True,
    )
    text_seen = False
    event_name = ""
    data_lines: list[str] = []

    def dispatch() -> Iterator[dict[str, str]]:
        nonlocal text_seen, event_name, data_lines
        data_text = "\n".join(data_lines).strip()
        current_event = event_name
        event_name = ""
        data_lines = []
        if not data_text or data_text == "[DONE]":
            return
        try:
            payload = json.loads(data_text)
        except json.JSONDecodeError as error:
            raise HermesApiError(
                "MacSoft Agent service returned malformed SSE data.",
                kind="protocol",
            ) from error
        if not isinstance(payload, dict):
            return
        if current_event == "hermes.tool.progress":
            tool = payload.get("tool")
            status = payload.get("status")
            if isinstance(tool, str) and status in {"running", "completed"}:
                yield {"type": "tool", "tool": tool, "status": status}
            return
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return
        delta = choices[0].get("delta")
        if not isinstance(delta, dict):
            return
        content = delta.get("content")
        if isinstance(content, str) and content:
            text_seen = text_seen or bool(content.strip())
            yield {"type": "text_delta", "text": content}

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line:
                    yield from dispatch()
                elif line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            if event_name or data_lines:
                yield from dispatch()
    except (HTTPError, URLError, TimeoutError) as error:
        _raise_transport_error(
            error,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )

    if not text_seen:
        raise HermesApiError(
            "MacSoft Agent service returned an empty assistant response.",
            kind="protocol",
        )


def _run_headers(
    api_key: str,
    *,
    profile_id: str | None = None,
    admin_scope: str | None = None,
    accept: str = "application/json",
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": accept,
    }
    if profile_id:
        # This is an internal Server-to-Hermes routing value. It is derived
        # exclusively from the authenticated device profile, never a Client
        # parameter or a filesystem path.
        headers["X-MacSoft-Profile-Id"] = profile_id
    if admin_scope:
        if profile_id:
            raise HermesApiError(
                "A Hermes run cannot use both device and Admin scopes.",
                kind="invalid_request",
            )
        headers["X-MacSoft-Admin-Scope"] = admin_scope
    return headers


def _read_json_response(response: Any) -> dict[str, Any]:
    try:
        payload = json.loads(response.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HermesApiError(
            "MacSoft Agent service returned invalid JSON.",
            kind="protocol",
        ) from error
    if not isinstance(payload, dict):
        raise HermesApiError(
            "MacSoft Agent service returned an invalid response.",
            kind="protocol",
        )
    return payload


def request_profile_operation(
    *,
    base_url: str,
    api_key: str,
    profile_id: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Call a Server-only Hermes profile endpoint with trusted routing."""
    if not path.startswith("/v1/macsoft/profile/"):
        raise HermesApiError("Invalid internal profile operation path.", kind="invalid_request")
    body = None
    if method != "GET":
        body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    request = Request(
        url=f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=_run_headers(api_key, profile_id=profile_id),
        method=method,
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return _read_json_response(response)
    except (HTTPError, URLError, TimeoutError) as error:
        _raise_transport_error(error, base_url=base_url, timeout_seconds=timeout_seconds)


def _start_hermes_run(
    *,
    base_url: str,
    api_key: str,
    messages: list[dict[str, Any]],
    session_id: str,
    profile_id: str | None = None,
    admin_scope: str | None = None,
    timeout_seconds: int,
) -> str:
    normalized = _normalized_messages(messages)
    user_index = next(
        (index for index in range(len(normalized) - 1, -1, -1) if normalized[index]["role"] == "user"),
        -1,
    )
    if user_index < 0:
        raise HermesApiError("MacSoft Agent request has no user message.", kind="invalid_request")
    instructions = "\n\n".join(
        str(message["content"]) for message in normalized[:user_index] if message["role"] == "system"
    )
    history = [message for message in normalized[:user_index] if message["role"] != "system"]
    # The Hermes Runs API interprets a top-level list as a list of messages,
    # while OpenAI-style multimodal content is also a list. Wrap the current
    # turn in an explicit user message so image_url parts stay attached to the
    # user input instead of being mistaken for a malformed message list.
    payload = {
        "model": "hermes-agent",
        "input": [{"role": "user", "content": normalized[user_index]["content"]}],
        "conversation_history": history,
        "instructions": instructions,
        "session_id": session_id,
    }
    request = Request(
        url=f"{base_url.rstrip('/')}/v1/runs",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=_run_headers(api_key, profile_id=profile_id, admin_scope=admin_scope),
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            result = _read_json_response(response)
    except (HTTPError, URLError, TimeoutError) as error:
        _raise_transport_error(error, base_url=base_url, timeout_seconds=timeout_seconds)
    run_id = result.get("run_id")
    if not isinstance(run_id, str) or not run_id.startswith("run_"):
        raise HermesApiError("MacSoft Agent service did not return a run ID.", kind="protocol")
    return run_id


def interrupt_hermes_run(
    *,
    base_url: str,
    api_key: str,
    profile_id: str | None = None,
    admin_scope: str | None = None,
    run_id: str,
    timeout_seconds: int,
) -> bool:
    request = Request(
        url=f"{base_url.rstrip('/')}/v1/runs/{run_id}/stop",
        data=b"{}",
        headers=_run_headers(api_key, profile_id=profile_id, admin_scope=admin_scope),
        method="POST",
    )
    try:
        with urlopen(request, timeout=min(timeout_seconds, 10)):
            return True
    except HTTPError as error:
        if error.code == 404:
            return False
        _raise_transport_error(error, base_url=base_url, timeout_seconds=timeout_seconds)
    except (URLError, TimeoutError) as error:
        _raise_transport_error(error, base_url=base_url, timeout_seconds=timeout_seconds)
    return False


def stream_interruptible_hermes_reply_events(
    *,
    base_url: str,
    api_key: str,
    messages: list[dict[str, Any]],
    session_id: str,
    profile_id: str | None = None,
    admin_scope: str | None = None,
    timeout_seconds: int,
    on_run_started: Callable[[str], bool],
) -> Iterator[dict[str, str]]:
    """Start a Hermes Run, expose its run ID, and yield its controlled SSE events."""
    run_id = _start_hermes_run(
        base_url=base_url,
        api_key=api_key,
        messages=messages,
        session_id=session_id,
        profile_id=profile_id,
        admin_scope=admin_scope,
        timeout_seconds=timeout_seconds,
    )
    if on_run_started(run_id):
        interrupt_hermes_run(
            base_url=base_url,
            api_key=api_key,
            profile_id=profile_id,
            admin_scope=admin_scope,
            run_id=run_id,
            timeout_seconds=timeout_seconds,
        )

    request = Request(
        url=f"{base_url.rstrip('/')}/v1/runs/{run_id}/events",
        headers=_run_headers(
            api_key,
            profile_id=profile_id,
            admin_scope=admin_scope,
            accept="text/event-stream",
        ),
        method="GET",
    )
    text_seen = False
    interrupted = False
    data_lines: list[str] = []

    def dispatch() -> Iterator[dict[str, str]]:
        nonlocal text_seen, interrupted, data_lines
        data_text = "\n".join(data_lines).strip()
        data_lines = []
        if not data_text:
            return
        try:
            payload = json.loads(data_text)
        except json.JSONDecodeError as error:
            raise HermesApiError("MacSoft Agent service returned malformed run SSE data.", kind="protocol") from error
        if not isinstance(payload, dict):
            return
        event = payload.get("event")
        if event == "message.delta":
            delta = payload.get("delta")
            if isinstance(delta, str) and delta:
                text_seen = text_seen or bool(delta.strip())
                yield {"type": "text_delta", "text": delta, "run_id": run_id}
        elif event in {"tool.started", "tool.completed"}:
            tool = payload.get("tool") or payload.get("tool_name")
            if isinstance(tool, str):
                yield {"type": "tool", "tool": tool, "status": event.split(".", 1)[1], "run_id": run_id}
        elif event == "run.cancelled":
            interrupted = True
            yield {"type": "interrupted", "run_id": run_id}
        elif event == "run.failed":
            raise HermesApiError(str(payload.get("error") or "MacSoft Agent run failed."), kind="run_failed")

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line:
                    yield from dispatch()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            if data_lines:
                yield from dispatch()
    except (HTTPError, URLError, TimeoutError) as error:
        _raise_transport_error(error, base_url=base_url, timeout_seconds=timeout_seconds)

    if not text_seen and not interrupted:
        raise HermesApiError("MacSoft Agent service returned an empty assistant response.", kind="protocol")
