from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from macsoft.chat.hermes_client import request_profile_operation
from macsoft.config import AppConfig
from macsoft.security import utc_now_iso


_LOCKS_GUARD = threading.Lock()
_PROFILE_LOCKS: dict[str, threading.RLock] = {}


def profile_write_lock(profile_id: str) -> threading.RLock:
    with _LOCKS_GUARD:
        return _PROFILE_LOCKS.setdefault(profile_id, threading.RLock())


def _tree_hash(root: Path) -> str | None:
    if not root.exists():
        return None
    digest = hashlib.sha256()
    found = False
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".curator_backups" in path.parts:
            continue
        found = True
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest() if found else None


def _audit(
    conn: sqlite3.Connection,
    *,
    profile_id: str,
    device_id: str,
    skill_id: str | None,
    proposal_id: str | None,
    change_source: str,
    previous_hash: str | None,
    new_hash: str | None,
    result: str,
    detail: str,
) -> dict[str, Any]:
    audit_id = f"audit_{uuid.uuid4().hex}"
    created_at = utc_now_iso()
    conn.execute(
        """
        INSERT INTO skill_change_audit (
            audit_id, profile_id, device_id, skill_id, run_id, proposal_id,
            change_source, previous_hash, new_hash, created_at, result, detail
        ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id,
            profile_id,
            device_id,
            skill_id,
            proposal_id,
            change_source,
            previous_hash,
            new_hash,
            created_at,
            result,
            detail,
        ),
    )
    return {
        "id": audit_id,
        "kind": change_source,
        "created_at": created_at,
        "detail": detail,
        "previous_hash": previous_hash,
        "new_hash": new_hash,
        "result": result,
    }


def call_profile_operation(
    config: AppConfig,
    *,
    profile_id: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return request_profile_operation(
        base_url=config.hermes.api_base_url,
        api_key=config.hermes.api_key,
        profile_id=profile_id,
        path=path,
        method=method,
        payload=payload,
        timeout_seconds=config.hermes.request_timeout_seconds,
    )


def audited_profile_mutation(
    conn: sqlite3.Connection,
    config: AppConfig,
    *,
    profile_id: str,
    device_id: str,
    profile_home: Path,
    change_source: str,
    operation_path: str,
    operation_payload: dict[str, Any] | None = None,
    skill_id: str | None = None,
    proposal_id: str | None = None,
    pre_snapshot: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Serialize and audit a native Hermes learned-skill mutation."""
    learned = profile_home / "skills" / "learned"
    with profile_write_lock(profile_id):
        previous_hash = _tree_hash(learned)
        if pre_snapshot:
            call_profile_operation(
                config,
                profile_id=profile_id,
                path="/v1/macsoft/profile/curator/backups",
                method="POST",
                payload={"reason": change_source},
            )
        try:
            response = call_profile_operation(
                config,
                profile_id=profile_id,
                path=operation_path,
                method="POST",
                payload=operation_payload,
            )
            native_audit = response.get("_macsoft_audit")
            if not isinstance(native_audit, dict):
                native_audit = {}
            exact_previous_hash = native_audit.get("previous_hash", previous_hash)
            new_hash = native_audit.get("new_hash", _tree_hash(learned))
            audit = _audit(
                conn,
                profile_id=profile_id,
                device_id=device_id,
                skill_id=skill_id,
                proposal_id=proposal_id,
                change_source=change_source,
                previous_hash=exact_previous_hash,
                new_hash=new_hash,
                result="succeeded",
                detail=f"Native Hermes {change_source} completed.",
            )
            conn.commit()
            return response, audit
        except Exception as error:
            audit = _audit(
                conn,
                profile_id=profile_id,
                device_id=device_id,
                skill_id=skill_id,
                proposal_id=proposal_id,
                change_source=change_source,
                previous_hash=previous_hash,
                new_hash=_tree_hash(learned),
                result="failed",
                detail=f"Native Hermes {change_source} failed: {type(error).__name__}.",
            )
            conn.commit()
            raise


def skill_operation_path(skill_id: str, operation: str) -> str:
    return f"/v1/macsoft/profile/skills/{quote(skill_id, safe='')}/{operation}"


def backup_rollback_path(backup_id: str) -> str:
    return (
        "/v1/macsoft/profile/curator/backups/"
        f"{quote(backup_id, safe='')}/rollback"
    )


def proposal_payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(str(row["payload_json"]))
    except (json.JSONDecodeError, TypeError):
        payload = {}
    return payload if isinstance(payload, dict) else {}
