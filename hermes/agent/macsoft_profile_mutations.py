"""Cross-process safety and audit for MacSoft learned-skill mutations."""

from __future__ import annotations

import contextvars
import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hermes_constants import get_hermes_home, get_writable_skills_dir


_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "macsoft_profile_mutation_depth", default=0
)
_thread_locks_guard = threading.Lock()
_thread_locks: dict[str, threading.RLock] = {}


def _profile() -> tuple[str, Path] | None:
    root_raw = os.environ.get("MACSOFT_PROFILE_ROOT", "").strip()
    if not root_raw:
        return None
    root = Path(root_raw).expanduser().resolve()
    home = get_hermes_home().resolve()
    device_profile = home.parent == root and home.name.startswith("prof_")
    global_staging = (
        home.parent == (root.parent / "global-staging").resolve()
        and home.name.startswith("admin_sess_")
    )
    if not device_profile and not global_staging:
        return None
    return home.name, home


def _hash_tree(root: Path) -> str | None:
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


def _lock_file(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:  # pragma: no cover - Windows product, POSIX development fallback
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_file(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:  # pragma: no cover
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def begin_mutation(*, source: str, skill_id: str | None) -> dict[str, Any] | None:
    resolved = _profile()
    if resolved is None:
        return None
    profile_id, home = resolved
    current_depth = _depth.get()
    token = _depth.set(current_depth + 1)
    if current_depth:
        return {"nested": True, "depth_token": token}

    with _thread_locks_guard:
        thread_lock = _thread_locks.setdefault(profile_id, threading.RLock())
    thread_lock.acquire()
    lock_path = home / "curator" / "mutation.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    if lock_path.stat().st_size == 0:
        handle.write(b"0")
        handle.flush()
    try:
        _lock_file(handle)
        from agent.curator_backup import snapshot_skills

        snapshot = snapshot_skills(reason=f"pre-{source}")
        if snapshot is None:
            raise RuntimeError("required pre-mutation snapshot failed")
        return {
            "nested": False,
            "depth_token": token,
            "profile_id": profile_id,
            "home": home,
            "source": source,
            "skill_id": skill_id,
            "previous_hash": _hash_tree(get_writable_skills_dir()),
            "lock_handle": handle,
            "thread_lock": thread_lock,
            "backup_id": snapshot.name,
        }
    except Exception:
        try:
            _unlock_file(handle)
        except Exception:
            pass
        handle.close()
        thread_lock.release()
        _depth.reset(token)
        raise


def finish_mutation(
    state: dict[str, Any] | None, *, success: bool, detail: str = ""
) -> dict[str, Any] | None:
    if state is None:
        return None
    token = state["depth_token"]
    if state.get("nested"):
        _depth.reset(token)
        return None
    payload = None
    try:
        home = Path(state["home"])
        event_dir = home / "logs" / "skill-change-audit"
        event_dir.mkdir(parents=True, exist_ok=True)
        event_id = f"audit_{uuid.uuid4().hex}"
        payload = {
            "audit_id": event_id,
            "profile_id": state["profile_id"],
            "skill_id": state.get("skill_id"),
            "run_id": _current_run_id(),
            "change_source": state["source"],
            "previous_hash": state.get("previous_hash"),
            "new_hash": _hash_tree(get_writable_skills_dir()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": "succeeded" if success else "failed",
            "detail": str(detail)[:2000],
            "backup_id": state.get("backup_id"),
        }
        temporary = event_dir / f".{event_id}.tmp"
        target = event_dir / f"{event_id}.json"
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, target)
    finally:
        handle = state["lock_handle"]
        try:
            _unlock_file(handle)
        finally:
            handle.close()
            state["thread_lock"].release()
            _depth.reset(token)
    return payload


def _current_run_id() -> Optional[str]:
    try:
        from tools.approval import get_current_session_key

        value = get_current_session_key(default="")
        return value if value.startswith("run_") else None
    except Exception:
        return None
