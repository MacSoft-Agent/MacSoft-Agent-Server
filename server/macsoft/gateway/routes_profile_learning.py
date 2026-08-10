from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Body, Header, HTTPException, Request

from macsoft.chat.hermes_client import HermesApiError
from macsoft.db import connect_db
from macsoft.gateway.errors import (
    device_credentials_rejected_error,
    error_response as _error_response,
)
from macsoft.identity.devices import require_device
from macsoft.profiles.registry import require_device_profile, resolve_profile_home
from macsoft.profiles.mutations import (
    audited_profile_mutation,
    backup_rollback_path,
    call_profile_operation,
    proposal_payload,
    skill_operation_path,
)
from macsoft.security import utc_now_iso

router = APIRouter()


def error_response(code: str, message: str) -> dict:
    if code == "invalid_device_token":
        return device_credentials_rejected_error()
    return _error_response(code, message)


def _scope(request: Request, authorization: str | None, device_id: str | None):
    config = request.app.state.config
    conn = connect_db(config)
    try:
        try:
            device = require_device(conn, authorization=authorization, device_id=device_id)
        except ValueError as error:
            raise HTTPException(
                401,
                detail=error_response("invalid_device_token", "Device token is invalid or revoked."),
            ) from error
        profile = require_device_profile(conn, config=config, device_id=str(device["device_id"]))
        home = resolve_profile_home(config, profile_id=str(profile["profile_id"]))
        return conn, device, profile, home
    except Exception:
        conn.close()
        raise


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return None


def _skill_metadata(skill_md: Path, usage: dict[str, Any]) -> dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    frontmatter: dict[str, Any] = {}
    if text.startswith("---\n"):
        marker = text.find("\n---", 4)
        if marker >= 0:
            try:
                parsed = yaml.safe_load(text[4:marker]) or {}
                if isinstance(parsed, dict):
                    frontmatter = parsed
            except yaml.YAMLError:
                pass
    name = str(frontmatter.get("name") or skill_md.parent.name)
    record = usage.get(name, {}) if isinstance(usage.get(name), dict) else {}
    agent_created = (
        record.get("created_by") == "agent"
        or record.get("agent_created") is True
    )
    return {
        "id": name,
        "name": name,
        "description": str(frontmatter.get("description") or ""),
        "state": str(record.get("state") or "active"),
        "origin": "agent" if agent_created else "manual",
        "enabled": True,
        "pinned": bool(record.get("pinned", False)),
        "use_count": int(record.get("use_count") or 0),
        "last_used_at": record.get("last_used_at"),
        "updated_at": _mtime(skill_md),
        "version": record.get("version"),
    }


def _upstream_error(error: HermesApiError) -> HTTPException:
    status = 503 if error.kind in {"unavailable", "timeout"} else 502
    return HTTPException(
        status,
        detail=error_response(
            "profile_learning_unavailable",
            "Hermes profile learning service is temporarily unavailable.",
        ),
    )


def _proposal_response(row: Any) -> dict[str, Any]:
    payload = proposal_payload(row)
    return {
        "id": row["proposal_id"],
        "action": row["kind"],
        "skill_id": row["target_id"],
        "skill_name": payload.get("skill_name"),
        "rationale": payload.get("rationale"),
        "status": row["status"],
    }


def _curator_status(conn: Any, profile_id: str, home: Path) -> dict[str, Any]:
    state = _json_object(home / "skills" / "learned" / ".curator_state")
    usage = _json_object(home / "skills" / "learned" / ".usage.json")
    states = [
        record.get("state", "active")
        for record in usage.values()
        if isinstance(record, dict)
        and (record.get("created_by") == "agent" or record.get("agent_created") is True)
    ]
    rows = conn.execute(
        "SELECT * FROM curator_proposals WHERE profile_id=? ORDER BY created_at DESC LIMIT 100",
        (profile_id,),
    ).fetchall()
    return {
        "enabled": True,
        "last_run_at": state.get("last_run_at"),
        "next_eligible_at": state.get("next_eligible_at"),
        "active_skills": states.count("active"),
        "stale_skills": states.count("stale"),
        "archived_skills": states.count("archived"),
        "proposals": [_proposal_response(row) for row in rows],
    }


def _reconcile_native_learning_events(conn: Any, profile_id: str, home: Path) -> None:
    event_dir = home / "logs" / "learning-events"
    changed = False
    event_paths = sorted(event_dir.glob("run_*.json")) if event_dir.is_dir() else []
    for path in event_paths:
        payload = _json_object(path)
        run_id = str(payload.get("run_id") or "")
        if run_id != path.stem:
            continue
        owned = conn.execute(
            "SELECT session_id FROM agent_runs WHERE run_id=? AND profile_id=?",
            (run_id, profile_id),
        ).fetchone()
        if owned is None:
            continue
        timestamp = payload.get("created_at")
        try:
            created_at = datetime.fromtimestamp(float(timestamp), timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            created_at = _mtime(path) or utc_now_iso()
        review_status = (
            "completed" if payload.get("status") == "completed" else "failed"
        )
        conn.execute(
            "UPDATE agent_runs SET learning_status=? WHERE run_id=? AND profile_id=?",
            (review_status, run_id, profile_id),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO learning_events (
                event_id, run_id, profile_id, event_type, status, detail, created_at
            ) VALUES (?, ?, ?, 'background_review', ?, ?, ?)
            """,
            (
                f"learn_bg_{run_id[4:]}",
                run_id,
                profile_id,
                review_status,
                str(payload.get("detail") or "Hermes background review completed.")[:2000],
                created_at,
            ),
        )
        changed = True
    if changed:
        conn.commit()

    profile_row = conn.execute(
        "SELECT device_id FROM device_profiles WHERE profile_id=?", (profile_id,)
    ).fetchone()
    if profile_row is None:
        return
    audit_dir = home / "logs" / "skill-change-audit"
    if not audit_dir.is_dir():
        return
    imported = False
    for path in sorted(audit_dir.glob("audit_*.json")):
        payload = _json_object(path)
        audit_id = str(payload.get("audit_id") or "")
        if audit_id != path.stem or payload.get("profile_id") != profile_id:
            continue
        run_id = payload.get("run_id")
        if run_id and conn.execute(
            "SELECT 1 FROM agent_runs WHERE run_id=? AND profile_id=?",
            (run_id, profile_id),
        ).fetchone() is None:
            run_id = None
        conn.execute(
            """
            INSERT OR IGNORE INTO skill_change_audit (
                audit_id, profile_id, device_id, skill_id, run_id, proposal_id,
                change_source, previous_hash, new_hash, created_at, result, detail
            ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                profile_id,
                str(profile_row["device_id"]),
                payload.get("skill_id"),
                run_id,
                str(payload.get("change_source") or "native_hermes"),
                payload.get("previous_hash"),
                payload.get("new_hash"),
                str(payload.get("timestamp") or _mtime(path) or utc_now_iso()),
                str(payload.get("result") or "unknown"),
                str(payload.get("detail") or "")[:2000],
            ),
        )
        if run_id:
            conn.execute(
                """
                INSERT OR IGNORE INTO learning_events (
                    event_id, run_id, profile_id, skill_id, event_type, status,
                    detail, created_at
                ) VALUES (?, ?, ?, ?, 'skill_updated', ?, ?, ?)
                """,
                (
                    f"learn_{audit_id}",
                    run_id,
                    profile_id,
                    payload.get("skill_id"),
                    str(payload.get("result") or "unknown"),
                    str(payload.get("detail") or payload.get("change_source") or "Progress Skill changed")[:2000],
                    str(payload.get("timestamp") or _mtime(path) or utc_now_iso()),
                ),
            )
        imported = True
    if imported:
        conn.commit()


@router.get("/api/profile/memory")
def profile_memory(request: Request, authorization: str | None = Header(None, alias="Authorization"), x_device_id: str | None = Header(None, alias="X-Device-Id")) -> dict:
    conn, _, profile, home = _scope(request, authorization, x_device_id)
    try:
        paths = [home / "memories" / "USER.md", home / "memories" / "MEMORY.md"]
        timestamps = [timestamp for path in paths if path.is_file() if (timestamp := _mtime(path))]
        updated = max(timestamps, default=None)
        try:
            graph = call_profile_operation(
                request.app.state.config,
                profile_id=str(profile["profile_id"]),
                path="/v1/macsoft/profile/learning-graph",
            )
        except HermesApiError as error:
            raise _upstream_error(error) from error
        cards = graph.get("memory", []) if isinstance(graph, dict) else []
        titles = [
            str(card.get("title") or "").strip()
            for card in cards
            if isinstance(card, dict) and str(card.get("title") or "").strip()
        ]
        return {
            "summary": "\n".join(f"• {title}" for title in titles)[:4000],
            "updated_at": updated,
            "source_count": len(titles),
        }
    finally:
        conn.close()


@router.get("/api/profile/skills")
def profile_skills(request: Request, authorization: str | None = Header(None, alias="Authorization"), x_device_id: str | None = Header(None, alias="X-Device-Id")) -> dict:
    conn, device, _, home = _scope(request, authorization, x_device_id)
    try:
        usage = _json_object(home / "skills" / "learned" / ".usage.json")
        learned = home / "skills" / "learned"
        skills = [_skill_metadata(path, usage) for path in sorted(learned.rglob("SKILL.md"))] if learned.is_dir() else []
        private_rows = conn.execute("SELECT skill_id, name, description, enabled, updated_at FROM client_skills WHERE owner_device_id=? ORDER BY updated_at DESC", (device["device_id"],)).fetchall()
        private_skills = [
            {
                "id": str(row["skill_id"]),
                "name": str(row["name"]),
                "description": str(row["description"] or ""),
                "enabled": bool(row["enabled"]),
                "updated_at": row["updated_at"],
                "origin": "private",
                "state": "active",
            }
            for row in private_rows
        ]
        return {"skills": skills, "private_skills": private_skills}
    finally:
        conn.close()


@router.get("/api/profile/learning")
def profile_learning(request: Request, authorization: str | None = Header(None, alias="Authorization"), x_device_id: str | None = Header(None, alias="X-Device-Id")) -> dict:
    conn, _, profile, home = _scope(request, authorization, x_device_id)
    try:
        _reconcile_native_learning_events(conn, str(profile["profile_id"]), home)
        rows = conn.execute(
            """
            SELECT le.event_id AS id, le.event_type AS kind,
                   le.event_type AS title, le.detail, le.created_at,
                   ar.session_id, le.skill_id
            FROM learning_events AS le
            JOIN agent_runs AS ar ON ar.run_id = le.run_id
            WHERE le.profile_id=?
            ORDER BY le.created_at DESC LIMIT 100
            """,
            (profile["profile_id"],),
        ).fetchall()
        journey = None
        journey_status = "unavailable"
        try:
            journey = call_profile_operation(
                request.app.state.config,
                profile_id=str(profile["profile_id"]),
                path="/v1/macsoft/profile/learning-graph",
            )
            journey_status = "ready"
        except HermesApiError:
            # The audit event list remains useful while :8642 is restarting;
            # never manufacture a graph from parallel Server-side state.
            pass
        return {
            "events": [dict(row) for row in rows],
            "journey": journey,
            "journey_status": journey_status,
        }
    finally:
        conn.close()


@router.get("/api/profile/curator")
def profile_curator(request: Request, authorization: str | None = Header(None, alias="Authorization"), x_device_id: str | None = Header(None, alias="X-Device-Id")) -> dict:
    conn, _, profile, home = _scope(request, authorization, x_device_id)
    try:
        return _curator_status(conn, str(profile["profile_id"]), home)
    finally:
        conn.close()


@router.post("/api/profile/curator/dry-run")
def profile_curator_dry_run(request: Request, authorization: str | None = Header(None, alias="Authorization"), x_device_id: str | None = Header(None, alias="X-Device-Id")) -> dict:
    conn, device, profile, home = _scope(request, authorization, x_device_id)
    profile_id = str(profile["profile_id"])
    try:
        result = call_profile_operation(
            request.app.state.config,
            profile_id=profile_id,
            path="/v1/macsoft/profile/curator/dry-run",
            method="POST",
        )
        transitions = result.get("result", {}).get("auto_transitions", {})
        checked = int(transitions.get("checked") or 0) if isinstance(transitions, dict) else 0
        if checked:
            proposal_id = f"proposal_{uuid.uuid4().hex}"
            now = utc_now_iso()
            conn.execute(
                """
                INSERT INTO curator_proposals (
                    proposal_id, profile_id, device_id, kind, target_id,
                    payload_json, status, created_at, decided_at
                ) VALUES (?, ?, ?, 'curator_run', NULL, ?, 'pending', ?, NULL)
                """,
                (
                    proposal_id,
                    profile_id,
                    str(device["device_id"]),
                    json.dumps(
                        {
                            "rationale": f"Official Hermes Curator reviewed {checked} learned skills in dry-run mode.",
                            "preview": result.get("result", {}),
                        },
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )
            conn.commit()
        return _curator_status(conn, profile_id, home)
    except HermesApiError as error:
        raise _upstream_error(error) from error
    finally:
        conn.close()


@router.post("/api/profile/curator/proposals/{proposal_id}/{decision}")
def decide_curator_proposal(proposal_id: str, decision: str, request: Request, authorization: str | None = Header(None, alias="Authorization"), x_device_id: str | None = Header(None, alias="X-Device-Id")) -> dict:
    if decision not in {"approve", "reject"}:
        raise HTTPException(404, detail=error_response("not_found", "Proposal operation not found."))
    conn, device, profile, home = _scope(request, authorization, x_device_id)
    profile_id = str(profile["profile_id"])
    try:
        row = conn.execute(
            "SELECT * FROM curator_proposals WHERE proposal_id=? AND profile_id=?",
            (proposal_id, profile_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, detail=error_response("proposal_not_found", "Curator proposal not found."))
        if row["status"] != "pending":
            raise HTTPException(409, detail=error_response("proposal_already_decided", "Curator proposal was already decided."))
        now = utc_now_iso()
        if decision == "reject":
            cursor = conn.execute(
                """
                UPDATE curator_proposals SET status='rejected', decided_at=?
                WHERE proposal_id=? AND profile_id=? AND status='pending'
                """,
                (now, proposal_id, profile_id),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise HTTPException(409, detail=error_response("proposal_already_decided", "Curator proposal was already decided."))
            conn.commit()
        else:
            if row["kind"] != "curator_run":
                raise HTTPException(409, detail=error_response("unsupported_proposal", "Curator proposal cannot be applied."))
            # Claim before invoking Hermes. Without this compare-and-swap, two
            # simultaneous approve requests could both mutate the same Profile.
            cursor = conn.execute(
                """
                UPDATE curator_proposals SET status='applying', decided_at=?
                WHERE proposal_id=? AND profile_id=? AND status='pending'
                """,
                (now, proposal_id, profile_id),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise HTTPException(409, detail=error_response("proposal_already_decided", "Curator proposal was already decided."))
            conn.commit()
            try:
                audited_profile_mutation(
                    conn,
                    request.app.state.config,
                    profile_id=profile_id,
                    device_id=str(device["device_id"]),
                    profile_home=home,
                    change_source="curator_approved_run",
                    operation_path="/v1/macsoft/profile/curator/run",
                    proposal_id=proposal_id,
                )
            except Exception:
                # Never make a possibly-applied operation retryable: a lost
                # upstream response is ambiguous. Backup/rollback remains the
                # explicit recovery path.
                conn.execute(
                    "UPDATE curator_proposals SET status='failed' WHERE proposal_id=? AND status='applying'",
                    (proposal_id,),
                )
                conn.commit()
                raise
            conn.execute(
                "UPDATE curator_proposals SET status='applied' WHERE proposal_id=? AND status='applying'",
                (proposal_id,),
            )
            conn.commit()
        updated = conn.execute("SELECT * FROM curator_proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
        return _proposal_response(updated)
    except HermesApiError as error:
        raise _upstream_error(error) from error
    finally:
        conn.close()


@router.post("/api/profile/skills/{skill_id}/pin")
def profile_skill_pin(skill_id: str, request: Request, body: dict[str, Any] = Body(default_factory=dict), authorization: str | None = Header(None, alias="Authorization"), x_device_id: str | None = Header(None, alias="X-Device-Id")) -> dict:
    pinned = body.get("pinned", True)
    if not isinstance(pinned, bool):
        raise HTTPException(422, detail=error_response("invalid_pinned", "pinned must be boolean."))
    conn, device, profile, home = _scope(request, authorization, x_device_id)
    try:
        audited_profile_mutation(
            conn,
            request.app.state.config,
            profile_id=str(profile["profile_id"]),
            device_id=str(device["device_id"]),
            profile_home=home,
            change_source="skill_pin",
            operation_path=skill_operation_path(skill_id, "pin"),
            operation_payload={"pinned": pinned},
            skill_id=skill_id,
        )
        usage = _json_object(home / "skills" / "learned" / ".usage.json")
        path = home / "skills" / "learned" / skill_id / "SKILL.md"
        if not path.is_file():
            raise HTTPException(404, detail=error_response("skill_not_found", "Progress skill not found."))
        return _skill_metadata(path, usage)
    except HermesApiError as error:
        if error.status_code == 403:
            raise HTTPException(
                403,
                detail=error_response(
                    "skill_not_agent_created",
                    "Only Hermes-created Progress Skills can be curated.",
                ),
            ) from error
        raise _upstream_error(error) from error
    finally:
        conn.close()


@router.post("/api/profile/skills/{skill_id}/restore")
def profile_skill_restore(skill_id: str, request: Request, authorization: str | None = Header(None, alias="Authorization"), x_device_id: str | None = Header(None, alias="X-Device-Id")) -> dict:
    conn, device, profile, home = _scope(request, authorization, x_device_id)
    try:
        audited_profile_mutation(
            conn,
            request.app.state.config,
            profile_id=str(profile["profile_id"]),
            device_id=str(device["device_id"]),
            profile_home=home,
            change_source="skill_restore",
            operation_path=skill_operation_path(skill_id, "restore"),
            skill_id=skill_id,
        )
        usage = _json_object(home / "skills" / "learned" / ".usage.json")
        path = home / "skills" / "learned" / skill_id / "SKILL.md"
        if not path.is_file():
            raise HTTPException(502, detail=error_response("restore_failed", "Hermes did not restore the Progress skill."))
        return _skill_metadata(path, usage)
    except HermesApiError as error:
        if error.status_code == 403:
            raise HTTPException(
                403,
                detail=error_response(
                    "skill_not_agent_created",
                    "Only Hermes-created Progress Skills can be curated.",
                ),
            ) from error
        raise _upstream_error(error) from error
    finally:
        conn.close()


@router.get("/api/profile/curator/backups")
def profile_curator_backups(request: Request, authorization: str | None = Header(None, alias="Authorization"), x_device_id: str | None = Header(None, alias="X-Device-Id")) -> dict:
    conn, _, profile, _ = _scope(request, authorization, x_device_id)
    try:
        result = call_profile_operation(
            request.app.state.config,
            profile_id=str(profile["profile_id"]),
            path="/v1/macsoft/profile/curator/backups",
        )
        backups = result.get("backups", [])
        return {
            "backups": [
                {
                    "id": item.get("id"),
                    "created_at": item.get("created_at"),
                    "reason": item.get("reason"),
                    "skill_count": item.get("skill_count"),
                    "restorable": True,
                }
                for item in backups
                if isinstance(item, dict) and item.get("id")
            ]
        }
    except HermesApiError as error:
        raise _upstream_error(error) from error
    finally:
        conn.close()


@router.post("/api/profile/curator/backups/{backup_id}/rollback")
def profile_curator_rollback(backup_id: str, request: Request, body: dict[str, Any] = Body(default_factory=dict), authorization: str | None = Header(None, alias="Authorization"), x_device_id: str | None = Header(None, alias="X-Device-Id")) -> dict:
    if body.get("confirm") is not True:
        raise HTTPException(422, detail=error_response("confirmation_required", "Explicit rollback confirmation is required."))
    conn, device, profile, home = _scope(request, authorization, x_device_id)
    try:
        response, audit = audited_profile_mutation(
            conn,
            request.app.state.config,
            profile_id=str(profile["profile_id"]),
            device_id=str(device["device_id"]),
            profile_home=home,
            change_source="rollback",
            operation_path=backup_rollback_path(backup_id),
            pre_snapshot=False,
        )
        return {"ok": bool(response.get("ok")), "audit_event": audit}
    except HermesApiError as error:
        raise _upstream_error(error) from error
    finally:
        conn.close()
