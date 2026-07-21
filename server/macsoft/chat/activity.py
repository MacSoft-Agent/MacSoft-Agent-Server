from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from macsoft.security import utc_now_iso


ACTIVITY_CAPABILITY = "activity-v1"
ACTIVITY_VERSION = 1
MAX_ACTIVITY_EVENTS = 20
MAX_ACTIVITY_TITLE_LENGTH = 120
MAX_ACTIVITY_DETAIL_LENGTH = 500
MAX_CAPABILITIES_HEADER_LENGTH = 512


class ActivityKind(StrEnum):
    ANALYSIS = "analysis"
    TOOL = "tool"
    VALIDATION = "validation"
    EXTERNAL_REQUEST = "external_request"
    FINALIZE = "finalize"
    WARNING = "warning"
    USER_INPUT = "user_input"


class ActivityStatus(StrEnum):
    STARTED = "started"
    UPDATED = "updated"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_USER = "waiting_user"


class ActivityV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = Field(default=ACTIVITY_VERSION, frozen=True)
    message_id: str
    activity_id: str
    sequence: int = Field(ge=1)
    kind: ActivityKind
    status: ActivityStatus
    title: str = Field(min_length=1, max_length=MAX_ACTIVITY_TITLE_LENGTH)
    detail: str | None = Field(default=None, max_length=MAX_ACTIVITY_DETAIL_LENGTH)
    progress: float | None = Field(default=None, ge=0, le=100)
    timestamp: str


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WINDOWS_PATH = re.compile(r"(?i)\b[a-z]:\\[^\s]+")
_BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_ -]?key|authorization|device[_ -]?token|password|secret)"
    r"\s*[:=]\s*[^\s,;]+"
)
_STACK_TRACE = re.compile(r"(?is)traceback \(most recent call last\):.*")


def supports_activity_v1(value: str | None) -> bool:
    if not value or len(value) > MAX_CAPABILITIES_HEADER_LENGTH:
        return False

    capabilities = {
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    }
    return ACTIVITY_CAPABILITY in capabilities


def sanitize_activity_text(value: Any, *, limit: int) -> str | None:
    if value is None:
        return None

    text = _CONTROL_CHARACTERS.sub("", str(value))
    text = _STACK_TRACE.sub("Technical details were removed.", text)
    text = _BEARER_TOKEN.sub("Bearer [redacted]", text)
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    text = _WINDOWS_PATH.sub("[local path removed]", text)
    text = " ".join(text.split()).strip()

    if not text:
        return None

    return text[:limit]


class ActivityMapper:
    """Owns the bounded, sanitized Client-facing activity sequence.

    The mapper deliberately accepts only already-observed execution states. It
    does not forward internal Agent events or Tool payloads.
    """

    def __init__(self, *, message_id: str, enabled: bool) -> None:
        self.message_id = message_id
        self.enabled = enabled
        self._sequence = 0
        self._closed = False
        self._last_state_by_activity: dict[
            str,
            tuple[str, str, str, str | None, float | None],
        ] = {}

    def close(self) -> None:
        self._closed = True

    def observed_tool_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Map one observed internal Tool event without forwarding its payload."""

        tool = event.get("tool")
        internal_status = event.get("status")
        if not isinstance(tool, str) or internal_status not in {"running", "completed"}:
            return None

        mappings: dict[
            str,
            tuple[str, ActivityKind, str, str],
        ] = {
            "skill_view": (
                "skill_selected",
                ActivityKind.ANALYSIS,
                "Selecting the requested Skill",
                "Skill selection request completed",
            ),
            "autocount_get_connector_status": (
                "autocount_connector_status",
                ActivityKind.EXTERNAL_REQUEST,
                "Checking AutoCount Connector status",
                "AutoCount Connector status request completed",
            ),
            "autocount_search_commands": (
                "autocount_command_catalog",
                ActivityKind.TOOL,
                "Loading the AutoCount command catalog",
                "AutoCount command catalog request completed",
            ),
            "autocount_get_command_schema": (
                "autocount_command_schema",
                ActivityKind.TOOL,
                "Loading the AutoCount command schema",
                "AutoCount command schema request completed",
            ),
            "autocount_validate_command": (
                "autocount_payload_validation",
                ActivityKind.VALIDATION,
                "Validating the AutoCount payload",
                "AutoCount payload validation request completed",
            ),
            "autocount_execute_command": (
                "autocount_command_execution",
                ActivityKind.EXTERNAL_REQUEST,
                "Processing the AutoCount command request",
                "AutoCount command request completed",
            ),
        }
        mapping = mappings.get(tool)
        if mapping is None:
            return None
        activity_id, kind, started_title, completed_title = mapping
        return self.activity(
            activity_id=activity_id,
            kind=kind,
            status=(
                ActivityStatus.STARTED
                if internal_status == "running"
                else ActivityStatus.COMPLETED
            ),
            title=(started_title if internal_status == "running" else completed_title),
        )

    def activity(
        self,
        *,
        activity_id: str,
        kind: ActivityKind,
        status: ActivityStatus,
        title: str,
        detail: str | None = None,
        progress: float | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled or self._closed or self._sequence >= MAX_ACTIVITY_EVENTS:
            return None

        safe_activity_id = re.sub(r"[^a-z0-9_-]+", "_", activity_id.lower()).strip("_")[:64]
        safe_title = sanitize_activity_text(title, limit=MAX_ACTIVITY_TITLE_LENGTH)
        safe_detail = sanitize_activity_text(detail, limit=MAX_ACTIVITY_DETAIL_LENGTH)

        if not safe_activity_id or not safe_title:
            return None

        state = (kind.value, status.value, safe_title, safe_detail, progress)
        if self._last_state_by_activity.get(safe_activity_id) == state:
            return None

        self._sequence += 1
        self._last_state_by_activity[safe_activity_id] = state

        event = ActivityV1(
            message_id=self.message_id,
            activity_id=safe_activity_id,
            sequence=self._sequence,
            kind=kind,
            status=status,
            title=safe_title,
            detail=safe_detail,
            progress=progress,
            timestamp=utc_now_iso(),
        )
        return event.model_dump(mode="json")
