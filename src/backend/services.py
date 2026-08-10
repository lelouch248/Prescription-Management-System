from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from fastapi import HTTPException
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from .models import (
    Appointment,
    AuditLog,
    Document,
    Medication,
    Note,
    Observation,
    PrescribedMedication,
    Prescription,
    Profile,
    Provider,
    Reminder,
    Visit,
    json_text,
)


Record = TypeVar("Record")


ENTITY_MODELS: dict[str, type[Any]] = {
    "profiles": Profile,
    "providers": Provider,
    "visits": Visit,
    "prescriptions": Prescription,
    "medications": Medication,
    "prescribed_medications": PrescribedMedication,
    "appointments": Appointment,
    "notes": Note,
    "observations": Observation,
    "reminders": Reminder,
    "documents": Document,
}


def record_dict(record: Any, *, parse_json: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in inspect(record).mapper.column_attrs:
        value = getattr(record, column.key)
        if isinstance(value, datetime):
            # SQLite stores normalized UTC datetimes without an offset. Reattach
            # UTC at the API boundary so browsers do not interpret them as local.
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            value = value.isoformat()
        elif isinstance(value, date):
            value = value.isoformat()
        if parse_json and column.key.endswith("_json") and isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        data[column.key.removesuffix("_json") if parse_json else column.key] = value
    return data


def audit(db: Session, entity_type: str, entity_id: str, operation: str, old: dict[str, Any] | None, new: dict[str, Any] | None, session_id: str | None = None) -> None:
    db.add(AuditLog(entity_type=entity_type, entity_id=entity_id, operation=operation, old_json=json_text(old) if old is not None else None, new_json=json_text(new) if new is not None else None, session_id=session_id))


def create_record(db: Session, model: type[Record], values: dict[str, Any], entity_type: str) -> Record:
    values = normalize_input(values)
    record = model(**values)
    db.add(record)
    db.flush()
    new = record_dict(record)
    audit(db, entity_type, str(getattr(record, "id")), "create", None, new)
    reindex_record(db, entity_type, record)
    db.commit()
    db.refresh(record)
    return record


def update_record(db: Session, model: type[Record], record_id: str, values: dict[str, Any], entity_type: str) -> Record:
    record = db.get(model, record_id)
    if not record or getattr(record, "deleted_at", None):
        raise HTTPException(status_code=404, detail=f"{entity_type} record not found")
    old = record_dict(record)
    for key, value in normalize_input(values).items():
        if hasattr(record, key) and key not in {"id", "created_at", "deleted_at"}:
            setattr(record, key, value)
    db.flush()
    new = record_dict(record)
    audit(db, entity_type, record_id, "update", old, new)
    reindex_record(db, entity_type, record)
    db.commit()
    db.refresh(record)
    return record


def soft_delete_record(db: Session, model: type[Record], record_id: str, entity_type: str) -> None:
    record = db.get(model, record_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"{entity_type} record not found")
    if not hasattr(record, "deleted_at"):
        raise HTTPException(status_code=400, detail="Record cannot be moved to trash")
    old = record_dict(record)
    record.deleted_at = datetime.now(timezone.utc)
    audit(db, entity_type, record_id, "trash", old, record_dict(record))
    db.execute(text("DELETE FROM search_index WHERE entity_type=:kind AND entity_id=:id"), {"kind": entity_type, "id": record_id})
    db.commit()


def restore_record(db: Session, model: type[Record], record_id: str, entity_type: str) -> Record:
    record = db.get(model, record_id)
    if not record or not getattr(record, "deleted_at", None):
        raise HTTPException(status_code=404, detail="Trashed record not found")
    old = record_dict(record)
    record.deleted_at = None
    audit(db, entity_type, record_id, "restore", old, record_dict(record))
    reindex_record(db, entity_type, record)
    db.commit()
    return record


def list_records(db: Session, model: type[Record], *, profile_id: str | None = None, include_deleted: bool = False, limit: int = 200) -> list[Record]:
    query = select(model)
    if hasattr(model, "deleted_at") and not include_deleted:
        query = query.where(model.deleted_at.is_(None))
    if profile_id and hasattr(model, "profile_id"):
        query = query.where(model.profile_id == profile_id)
    ordering = None
    for name in ("starts_at", "visit_date", "prescription_date", "occurred_at", "observed_at", "due_at", "created_at", "name"):
        if hasattr(model, name):
            ordering = getattr(model, name)
            break
    if ordering is not None:
        query = query.order_by(ordering.desc())
    return list(db.scalars(query.limit(min(limit, 1000))).all())


def normalize_input(values: dict[str, Any]) -> dict[str, Any]:
    values = dict(values)
    for key in list(values):
        if key in {"schedule", "recurrence"}:
            values[f"{key}_json"] = json_text(values.pop(key))
        if values.get(key) is None and key in {"occurred_at", "observed_at"}:
            values[key] = datetime.now(timezone.utc)
    return values


def reindex_record(db: Session, entity_type: str, record: Any) -> None:
    if entity_type not in ENTITY_MODELS or getattr(record, "deleted_at", None):
        return
    data = record_dict(record)
    profile_id = data.get("profile_id") or (data.get("id") if entity_type == "profiles" else "") or ""
    title_parts = [data.get(k) for k in ("name", "title", "brand_name", "generic_name", "purpose", "reason", "original_filename") if data.get(k)]
    content_parts = [str(v) for k, v in data.items() if v not in (None, "") and k not in {"id", "sha256", "relative_path", "thumbnail_path"}]
    event_date = next((data.get(k) for k in ("visit_date", "prescription_date", "starts_at", "occurred_at", "observed_at", "due_at", "document_date", "created_at") if data.get(k)), "")
    db.execute(text("DELETE FROM search_index WHERE entity_type=:kind AND entity_id=:id"), {"kind": entity_type, "id": data["id"]})
    db.execute(
        text("INSERT INTO search_index(entity_type,entity_id,profile_id,title,content,event_date) VALUES(:kind,:id,:profile,:title,:content,:event_date)"),
        {"kind": entity_type, "id": data["id"], "profile": profile_id, "title": " · ".join(title_parts) or entity_type.replace("_", " ").title(), "content": " ".join(content_parts), "event_date": event_date},
    )


def rebuild_search_index(db: Session) -> int:
    db.execute(text("DELETE FROM search_index"))
    count = 0
    for entity_type, model in ENTITY_MODELS.items():
        for record in list_records(db, model, limit=100000):
            reindex_record(db, entity_type, record)
            count += 1
    db.commit()
    return count


def search_records(db: Session, query: str, *, profile_id: str | None = None, entity_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    tokens = [token.replace('"', "") for token in query.strip().split() if token]
    if not tokens:
        return []
    fts_query = " AND ".join(f'"{token}"*' for token in tokens)
    clauses = ["search_index MATCH :query"]
    params: dict[str, Any] = {"query": fts_query, "limit": min(limit, 100)}
    if profile_id:
        clauses.append("profile_id=:profile_id")
        params["profile_id"] = profile_id
    if entity_type:
        clauses.append("entity_type=:entity_type")
        params["entity_type"] = entity_type
    rows = db.execute(text(f"SELECT entity_type,entity_id,profile_id,title,snippet(search_index,4,'<mark>','</mark>',' … ',24) AS snippet,event_date,bm25(search_index) AS rank FROM search_index WHERE {' AND '.join(clauses)} ORDER BY rank LIMIT :limit"), params).mappings()
    return [dict(row) for row in rows]


def safe_resolve(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if root.resolve() not in candidate.parents and candidate != root.resolve():
        raise ValueError("Path escapes vault data directory")
    return candidate
