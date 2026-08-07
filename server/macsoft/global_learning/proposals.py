from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from macsoft.global_learning.homes import global_home, global_training_home, runtime_root
from macsoft.security import new_id, utc_now_iso


_approval_lock = threading.RLock()
_MEMORY_FILES = ("memories/USER.md", "memories/MEMORY.md")
_MUTABLE_PREFIXES = ("skills/learned/workflow-improvements/", "curator/")


def _safe_mutable_relative(relative: str) -> bool:
    normalized = Path(relative).as_posix()
    if normalized in _MEMORY_FILES:
        return True
    return any(normalized.startswith(prefix) for prefix in _MUTABLE_PREFIXES)


def _iter_mutable_files(home: Path):
    for relative in _MEMORY_FILES:
        path = home / relative
        if path.is_file() and not path.is_symlink():
            yield relative, path
    for relative_root in ("skills/learned/workflow-improvements", "curator"):
        root = home / relative_root
        if not root.is_dir() or root.is_symlink():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                relative = path.relative_to(home).as_posix()
                if _safe_mutable_relative(relative):
                    yield relative, path


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(home: Path) -> dict[str, str]:
    return {relative: _file_hash(path) for relative, path in _iter_mutable_files(home)}


def _manifest_hash(manifest: dict[str, str]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _changes(before: dict[str, str], after: dict[str, str]) -> list[dict[str, str | None]]:
    result: list[dict[str, str | None]] = []
    for relative in sorted(set(before) | set(after)):
        previous = before.get(relative)
        current = after.get(relative)
        if previous == current:
            continue
        result.append({
            "path": relative,
            "action": "create" if previous is None else "delete" if current is None else "update",
            "previous_hash": previous,
            "new_hash": current,
        })
    return result


def _proposal_kind(changes: list[dict[str, str | None]]) -> str:
    paths = [str(item["path"]) for item in changes]
    memory = any(path.startswith("memories/") for path in paths)
    skills = any(path.startswith("skills/learned/") for path in paths)
    curator = any(path.startswith("curator/") for path in paths)
    if sum((memory, skills, curator)) > 1:
        return "combined_proposal"
    if memory:
        return "memory_proposal"
    if curator:
        return "curator_proposal"
    created = any(item["action"] == "create" for item in changes)
    return "skill_create_proposal" if created else "skill_patch_proposal"


def _snapshot_root(config: Any, proposal_id: str) -> Path:
    if not proposal_id.startswith("global_prop_"):
        raise ValueError("invalid_global_proposal_id")
    root = (runtime_root(config) / "global-proposals").resolve()
    candidate = (root / proposal_id).resolve()
    if candidate.parent != root:
        raise ValueError("invalid_global_proposal_path")
    return candidate


def _copy_mutable_state(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    for relative, path in _iter_mutable_files(source):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def create_proposal_from_staging(
    conn: sqlite3.Connection,
    *,
    config: Any,
    session_id: str,
    run_id: str | None = None,
) -> dict[str, Any] | None:
    canonical = global_home(config)
    staging = global_training_home(config, session_id)
    if not canonical.is_dir() or not staging.is_dir():
        raise ValueError("global_learning_home_not_found")
    before = _manifest(canonical)
    after = _manifest(staging)
    changes = _changes(before, after)
    if not changes:
        return None
    previous_hash = _manifest_hash(before)
    new_hash = _manifest_hash(after)
    training = conn.execute(
        "SELECT workflow_target FROM admin_sessions WHERE session_id=? AND session_type='global_training'",
        (session_id,),
    ).fetchone()
    if training is None:
        raise ValueError("global_training_session_not_found")
    workflow_target = str(training["workflow_target"] or "general")
    skill_targets = {
        Path(str(change["path"])).parts[3]
        for change in changes
        if str(change.get("path") or "").startswith("skills/learned/workflow-improvements/")
        and len(Path(str(change["path"])).parts) >= 4
    }
    has_memory_change = any(str(change.get("path") or "").startswith("memories/") for change in changes)
    if workflow_target == "general" and has_memory_change and skill_targets:
        raise ValueError("global_proposal_multiple_targets")
    if workflow_target != "general" and (has_memory_change or skill_targets - {workflow_target}):
        raise ValueError("global_proposal_target_boundary")
    if len(skill_targets) > 1:
        raise ValueError("global_proposal_multiple_targets")
    existing = conn.execute(
        """
        SELECT * FROM global_learning_proposals
        WHERE training_session_id = ? AND status = 'pending'
        ORDER BY created_at DESC
        """,
        (session_id,),
    ).fetchall()
    for row in existing:
        payload = json.loads(str(row["payload_json"]))
        if payload.get("new_hash") == new_hash:
            return _row(row)

    proposal_id = new_id("global_prop")
    snapshot = _snapshot_root(config, proposal_id)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    _copy_mutable_state(staging, snapshot)
    payload = {
        "schema_version": 1,
        "workflow_target": workflow_target,
        "previous_hash": previous_hash,
        "new_hash": new_hash,
        "changes": changes,
    }
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO global_learning_proposals (
            proposal_id, training_session_id, run_id, kind, payload_json,
            status, created_at, decided_at
        ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL)
        """,
        (
            proposal_id,
            session_id,
            run_id,
            _proposal_kind(changes),
            json.dumps(payload, ensure_ascii=False),
            now,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM global_learning_proposals WHERE proposal_id = ?",
        (proposal_id,),
    ).fetchone()
    return _row(row)


def _row(row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(str(row["payload_json"]))
    return {
        "proposal_id": str(row["proposal_id"]),
        "training_session_id": str(row["training_session_id"]),
        "run_id": row["run_id"],
        "kind": str(row["kind"]),
        "workflow_target": payload.get("workflow_target", "general"),
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
        "decided_at": row["decided_at"],
        "previous_hash": payload.get("previous_hash"),
        "new_hash": payload.get("new_hash"),
        "changes": payload.get("changes", []),
    }


def list_proposals(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM global_learning_proposals ORDER BY created_at DESC"
    ).fetchall()
    return [_row(row) for row in rows]


def _replace_mutable_state(source: Path, target: Path) -> None:
    desired = {relative: path for relative, path in _iter_mutable_files(source)}
    current = {relative: path for relative, path in _iter_mutable_files(target)}
    for relative, path in current.items():
        if relative not in desired:
            path.unlink()
    for relative, path in desired.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
        shutil.copy2(path, temporary)
        os.replace(temporary, destination)


def decide_proposal(
    conn: sqlite3.Connection,
    *,
    config: Any,
    proposal_id: str,
    approve: bool,
) -> dict[str, Any]:
    with _approval_lock:
        row = conn.execute(
            "SELECT * FROM global_learning_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise ValueError("global_proposal_not_found")
        proposal = _row(row)
        if proposal["status"] != "pending":
            raise ValueError("global_proposal_already_decided")
        now = utc_now_iso()
        if not approve:
            conn.execute(
                "UPDATE global_learning_proposals SET status='rejected', decided_at=? WHERE proposal_id=?",
                (now, proposal_id),
            )
            conn.execute(
                """
                INSERT INTO global_learning_audit (
                    audit_id, proposal_id, training_session_id, run_id,
                    change_source, workflow_target, final_target, previous_hash, new_hash, result, detail, created_at
                ) VALUES (?, ?, ?, ?, 'admin_reject', ?, ?, ?, ?, 'rejected', ?, ?)
                """,
                (
                    new_id("global_audit"),
                    proposal_id,
                    proposal["training_session_id"],
                    proposal["run_id"],
                    proposal["workflow_target"],
                    proposal["workflow_target"],
                    proposal["previous_hash"],
                    proposal["new_hash"],
                    "Global learning proposal rejected by Server Admin.",
                    now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM global_learning_proposals WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            return _row(row)

        canonical = global_home(config)
        current_hash = _manifest_hash(_manifest(canonical))
        if current_hash != proposal["previous_hash"]:
            raise ValueError("global_proposal_stale")
        snapshot = _snapshot_root(config, proposal_id)
        if not snapshot.is_dir() or _manifest_hash(_manifest(snapshot)) != proposal["new_hash"]:
            raise ValueError("global_proposal_snapshot_invalid")

        backup = canonical / "backups" / "global-approvals" / proposal_id
        backup.parent.mkdir(parents=True, exist_ok=True)
        _copy_mutable_state(canonical, backup)
        try:
            _replace_mutable_state(snapshot, canonical)
            applied_hash = _manifest_hash(_manifest(canonical))
            if applied_hash != proposal["new_hash"]:
                raise RuntimeError("global_proposal_apply_hash_mismatch")
        except Exception:
            _replace_mutable_state(backup, canonical)
            raise

        conn.execute(
            "UPDATE global_learning_proposals SET status='approved', decided_at=? WHERE proposal_id=?",
            (now, proposal_id),
        )
        conn.execute(
            """
            INSERT INTO global_learning_audit (
                audit_id, proposal_id, training_session_id, run_id,
                change_source, workflow_target, final_target, previous_hash, new_hash, result, detail, created_at
            ) VALUES (?, ?, ?, ?, 'admin_approve', ?, ?, ?, ?, 'succeeded', ?, ?)
            """,
            (
                new_id("global_audit"),
                proposal_id,
                proposal["training_session_id"],
                proposal["run_id"],
                proposal["workflow_target"],
                proposal["workflow_target"],
                proposal["previous_hash"],
                proposal["new_hash"],
                "Native Hermes staging changes promoted to canonical Global Home.",
                now,
            ),
        )
        for change in proposal["changes"]:
            path = str(change.get("path") or "")
            if not path.startswith("skills/learned/") or not path.endswith("/SKILL.md"):
                continue
            skill_id = Path(path).parent.name
            conn.execute(
                """
                INSERT INTO global_skill_versions (
                    version_id, skill_id, proposal_id, previous_hash, new_hash,
                    workflow_target, snapshot_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("global_ver"),
                    skill_id,
                    proposal_id,
                    change.get("previous_hash"),
                    change.get("new_hash") or "deleted",
                    proposal["workflow_target"],
                    str(backup),
                    now,
                ),
            )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM global_learning_proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        return _row(row)


def restore_approved_proposal(
    conn: sqlite3.Connection,
    *,
    config: Any,
    proposal_id: str,
) -> dict[str, Any]:
    """Restore the exact pre-approval Global Home snapshot for one proposal.

    A restore is intentionally linear: it is allowed only while the canonical
    state still equals the version produced by this proposal.  That prevents an
    older restore from silently discarding a newer approved training result.
    """
    with _approval_lock:
        row = conn.execute(
            "SELECT * FROM global_learning_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise ValueError("global_proposal_not_found")
        proposal = _row(row)
        if proposal["status"] != "approved":
            raise ValueError("global_proposal_not_approved")

        canonical = global_home(config)
        if _manifest_hash(_manifest(canonical)) != proposal["new_hash"]:
            raise ValueError("global_proposal_restore_stale")
        backup = canonical / "backups" / "global-approvals" / proposal_id
        if not backup.is_dir() or _manifest_hash(_manifest(backup)) != proposal["previous_hash"]:
            raise ValueError("global_proposal_backup_invalid")

        rollback_id = new_id("global_rollback")
        rollback_snapshot = canonical / "backups" / "global-restores" / rollback_id
        rollback_snapshot.parent.mkdir(parents=True, exist_ok=True)
        _copy_mutable_state(canonical, rollback_snapshot)
        try:
            _replace_mutable_state(backup, canonical)
            if _manifest_hash(_manifest(canonical)) != proposal["previous_hash"]:
                raise RuntimeError("global_proposal_restore_hash_mismatch")
        except Exception:
            _replace_mutable_state(rollback_snapshot, canonical)
            raise

        now = utc_now_iso()
        conn.execute(
            """
            INSERT INTO global_learning_audit (
                audit_id, proposal_id, training_session_id, run_id,
                change_source, workflow_target, final_target, previous_hash, new_hash, result, detail, created_at
            ) VALUES (?, ?, ?, ?, 'admin_restore', ?, ?, ?, ?, 'succeeded', ?, ?)
            """,
            (
                new_id("global_audit"),
                proposal_id,
                proposal["training_session_id"],
                proposal["run_id"],
                proposal["workflow_target"],
                proposal["workflow_target"],
                proposal["new_hash"],
                proposal["previous_hash"],
                "Global Home restored from the pre-approval snapshot.",
                now,
            ),
        )
        conn.commit()
        return proposal
