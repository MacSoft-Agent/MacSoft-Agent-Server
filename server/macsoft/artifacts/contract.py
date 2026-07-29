from __future__ import annotations

import json


def serialize_artifact(conn, artifact_id: str) -> dict | None:
    artifact = conn.execute(
        """
        SELECT artifact_id, assistant_message_id, generation_id, kind, status,
               revision, title, summary, metadata_json, expired_at
        FROM artifacts WHERE artifact_id = ? AND deleted_at IS NULL
        """,
        (artifact_id,),
    ).fetchone()
    if artifact is None:
        return None
    files = conn.execute(
        """
        SELECT file_id, format, role, filename, content_type, size_bytes
        FROM artifact_files
        WHERE artifact_id = ? AND revision = ?
          AND status = 'available' AND deleted_at IS NULL
        ORDER BY CASE format WHEN 'png' THEN 0 ELSE 1 END
        """,
        (artifact_id, artifact["revision"]),
    ).fetchall()
    file_values = [dict(row) for row in files]
    expired = artifact["status"] == "expired"
    return {
        "version": 1,
        "event_id": f"artifact:{artifact_id}:{artifact['revision']}",
        "message_id": artifact["assistant_message_id"],
        "generation_id": artifact["generation_id"],
        "artifact": {
            "artifact_id": artifact["artifact_id"],
            "kind": artifact["kind"],
            "status": artifact["status"],
            "revision": artifact["revision"],
            "title": artifact["title"],
            "summary": artifact["summary"],
            "preview": None if expired else next((row for row in file_values if row["role"] == "preview"), None),
            "downloads": [] if expired else file_values,
            "metadata": json.loads(str(artifact["metadata_json"])),
            "expired_at": artifact["expired_at"],
        },
    }
