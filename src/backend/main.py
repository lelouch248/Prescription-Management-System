from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import tempfile
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .ai import answer_from_records, extract_medical_text, ollama_status, transcribe_voice
from .auth import (
    SESSION_COOKIE, clear_login_attempts, create_session, delete_session, enforce_login_rate_limit,
    is_configured, require_csrf, require_session, set_password, verify_password,
)
from .backup import (
    backup_health, configure_backup_secret, create_backup, restore_backup, unlock_backup_secret, unlocked_backup_password,
    verify_backup,
)
from .calendar_utils import events_to_ics
from .config import APP_VERSION, BACKUP_FORMAT_VERSION, DATABASE_SCHEMA_VERSION, EXPORT_SCHEMA_VERSION, settings
from .database import SessionLocal, get_db, integrity_check
from .exporter import create_export, inspect_or_import
from .models import (
    Appointment, AuditLog, BackupDestination, BackupRun, Document, DoseEvent, Extraction, Medication,
    Note, Observation, PrescribedMedication, Prescription, Profile, Provider, Reminder, Visit, VoiceNote,
    new_uuid, utcnow,
)
from .schemas import (
    AIQueryInput, AppointmentInput, BackupCreateInput, BackupDestinationInput, BackupPasswordInput,
    DoseEventInput, ExtractionUpdate, LoginInput, MedicationInput, NoteInput, ObservationInput,
    PrescribedMedicationInput, PrescriptionInput, ProfileInput, ProviderInput, ReminderInput, SetupInput,
    VisitInput,
)
from .services import (
    audit, create_record, list_records, rebuild_search_index, record_dict, restore_record, search_records,
    safe_resolve, soft_delete_record, update_record,
)
from .storage import run_ocr, store_document, store_voice


async def _backup_scheduler() -> None:
    while True:
        await asyncio.sleep(60)
        password = unlocked_backup_password()
        if not password:
            continue
        with SessionLocal() as db:
            last = db.scalar(select(BackupRun).where(BackupRun.status.in_(["success", "partial"])).order_by(BackupRun.completed_at.desc()))
            last_at = _aware(last.completed_at) if last and last.completed_at else None
            if last_at is None or datetime.now(timezone.utc) - last_at > timedelta(hours=24):
                try:
                    now = datetime.now(timezone.utc)
                    kind = "monthly" if now.day == 1 else "weekly" if now.weekday() == 6 else "daily"
                    create_backup(db, password, kind)
                except Exception:
                    pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_backup_scheduler())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="HealthVault Local API",
    description="Local-first, single-user family health record API. Medical AI outputs are proposals and require human verification.",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

allowed_origins = ["http://127.0.0.1:5173", "http://localhost:5173", f"http://127.0.0.1:{settings.port}", f"http://localhost:{settings.port}"]
allowed_origins.extend(origin.strip() for origin in os.getenv("HEALTHVAULT_ALLOWED_ORIGINS", "").split(",") if origin.strip())
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' http://127.0.0.1:8765 ws://127.0.0.1:5173; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") else "no-cache"
    return response


def _ensure_local_setup(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="First-time vault setup is permitted only from this computer")


@app.get("/api/health")
def health() -> dict[str, Any]:
    ok, message = integrity_check()
    return {"status": "ok" if ok else "critical", "database_integrity": message, "version": APP_VERSION}


@app.get("/api/status")
async def status(db: Session = Depends(get_db)) -> dict[str, Any]:
    ai = await ollama_status()
    return {"configured": is_configured(db), "version": APP_VERSION, "database_schema": DATABASE_SCHEMA_VERSION, "export_schema": EXPORT_SCHEMA_VERSION, "backup_format": BACKUP_FORMAT_VERSION, "ai": ai}


@app.post("/api/setup", status_code=201)
def setup(payload: SetupInput, request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure_local_setup(request)
    if is_configured(db):
        raise HTTPException(status_code=409, detail="Vault has already been created")
    set_password(db, payload.password)
    profile = Profile(name=payload.profile_name)
    db.add(profile); db.flush()
    audit(db, "profiles", profile.id, "create", None, record_dict(profile))
    db.commit()
    session = create_session(db, response, request.client.host if request.client else None)
    db.commit()
    return {"configured": True, "profile": record_dict(profile), **session}


@app.post("/api/auth/login")
def login(payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    if not is_configured(db):
        raise HTTPException(status_code=409, detail="Vault setup is not complete")
    client_ip = request.client.host if request.client else "unknown"
    enforce_login_rate_limit(client_ip)
    if not verify_password(db, payload.password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    clear_login_attempts(client_ip)
    unlock_backup_secret(db, payload.password)
    result = create_session(db, response, client_ip); db.commit()
    return {"authenticated": True, **result}


@app.get("/api/auth/me")
def me(session=Depends(require_session)) -> dict[str, Any]:
    return {"authenticated": True, "csrf_token": session.csrf_token, "expires_at": _aware(session.expires_at).isoformat()}


@app.post("/api/auth/logout")
def logout(response: Response, token: str | None = Cookie(default=None, alias=SESSION_COOKIE), db: Session = Depends(get_db), _=Depends(require_csrf)) -> dict[str, bool]:
    delete_session(db, response, token); db.commit()
    return {"authenticated": False}


def _crud_list(db: Session, model: type[Any], profile_id: str | None, include_deleted: bool, limit: int) -> list[dict[str, Any]]:
    return [record_dict(row) for row in list_records(db, model, profile_id=profile_id, include_deleted=include_deleted, limit=limit)]


@app.get("/api/profiles")
def profiles(include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, Profile, None, include_deleted, 500)
@app.post("/api/profiles", status_code=201)
def profile_create(payload: ProfileInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(create_record(db, Profile, payload.model_dump(), "profiles"))
@app.put("/api/profiles/{record_id}")
def profile_update(record_id: str, payload: ProfileInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(update_record(db, Profile, record_id, payload.model_dump(), "profiles"))

@app.get("/api/providers")
def providers(include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, Provider, None, include_deleted, 500)
@app.post("/api/providers", status_code=201)
def provider_create(payload: ProviderInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(create_record(db, Provider, payload.model_dump(), "providers"))
@app.put("/api/providers/{record_id}")
def provider_update(record_id: str, payload: ProviderInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(update_record(db, Provider, record_id, payload.model_dump(), "providers"))

@app.get("/api/visits")
def visits(profile_id: str | None = None, include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, Visit, profile_id, include_deleted, 1000)
@app.post("/api/visits", status_code=201)
def visit_create(payload: VisitInput, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = create_record(db, Visit, payload.model_dump(), "visits")
    if payload.follow_up_date:
        create_record(db, Reminder, {"profile_id": payload.profile_id, "kind": "follow_up", "title": f"Follow-up: {payload.reason or 'medical visit'}", "due_at": payload.follow_up_date, "recurrence": {}, "status": "pending", "notes": f"Created from visit {item.id}"}, "reminders")
    return record_dict(item)
@app.put("/api/visits/{record_id}")
def visit_update(record_id: str, payload: VisitInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(update_record(db, Visit, record_id, payload.model_dump(), "visits"))

@app.get("/api/prescriptions")
def prescriptions(profile_id: str | None = None, include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, Prescription, profile_id, include_deleted, 1000)
@app.post("/api/prescriptions", status_code=201)
def prescription_create(payload: PrescriptionInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(create_record(db, Prescription, payload.model_dump(), "prescriptions"))
@app.put("/api/prescriptions/{record_id}")
def prescription_update(record_id: str, payload: PrescriptionInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(update_record(db, Prescription, record_id, payload.model_dump(), "prescriptions"))

@app.get("/api/medications")
def medications(include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, Medication, None, include_deleted, 1000)
@app.post("/api/medications", status_code=201)
def medication_create(payload: MedicationInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(create_record(db, Medication, payload.model_dump(), "medications"))
@app.put("/api/medications/{record_id}")
def medication_update(record_id: str, payload: MedicationInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(update_record(db, Medication, record_id, payload.model_dump(), "medications"))

@app.get("/api/prescribed-medications")
def prescribed_medications(profile_id: str | None = None, include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, PrescribedMedication, profile_id, include_deleted, 1000)
@app.post("/api/prescribed-medications", status_code=201)
def prescribed_medication_create(payload: PrescribedMedicationInput, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = create_record(db, PrescribedMedication, payload.model_dump(), "prescribed_medications")
    # Only an explicitly verified schedule may become an actionable reminder.
    if payload.verification_status == "verified" and payload.tracking_status == "active":
        medication = db.get(Medication, payload.medication_id)
        title = f"Take {medication.brand_name or medication.generic_name or 'medicine'}" if medication else "Take medicine"
        local_tz = datetime.now().astimezone().tzinfo or timezone.utc
        start = payload.start_date or datetime.now(local_tz).date()
        for raw_time in payload.schedule.get("times", []):
            try:
                clock = datetime.strptime(str(raw_time), "%H:%M").time()
            except ValueError:
                continue
            due_at = datetime.combine(start, clock, tzinfo=local_tz).astimezone(timezone.utc)
            create_record(db, Reminder, {"profile_id": payload.profile_id, "prescribed_medication_id": item.id, "kind": "medication", "title": title, "due_at": due_at, "recurrence": {"pattern": "daily", "time": str(raw_time), "until": payload.end_date.isoformat() if payload.end_date else None}, "status": "pending", "notes": payload.instructions}, "reminders")
    return record_dict(item)
@app.put("/api/prescribed-medications/{record_id}")
def prescribed_medication_update(record_id: str, payload: PrescribedMedicationInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(update_record(db, PrescribedMedication, record_id, payload.model_dump(), "prescribed_medications"))

@app.get("/api/appointments")
def appointments(profile_id: str | None = None, include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, Appointment, profile_id, include_deleted, 1000)
@app.post("/api/appointments", status_code=201)
def appointment_create(payload: AppointmentInput, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = create_record(db, Appointment, payload.model_dump(), "appointments")
    if payload.status == "scheduled":
        create_record(db, Reminder, {"profile_id": payload.profile_id, "appointment_id": item.id, "kind": "appointment", "title": payload.purpose or "Medical appointment", "due_at": payload.starts_at - timedelta(minutes=payload.reminder_minutes), "recurrence": {}, "status": "pending", "notes": payload.preparation_notes}, "reminders")
    return record_dict(item)
@app.put("/api/appointments/{record_id}")
def appointment_update(record_id: str, payload: AppointmentInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(update_record(db, Appointment, record_id, payload.model_dump(), "appointments"))

@app.post("/api/appointments/{record_id}/create-visit", status_code=201)
def visit_from_appointment(record_id: str, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = db.get(Appointment, record_id)
    if not item: raise HTTPException(status_code=404, detail="Appointment not found")
    existing = db.scalar(select(Visit).where(Visit.appointment_id == record_id))
    if existing: return record_dict(existing)
    visit = create_record(db, Visit, {"profile_id": item.profile_id, "provider_id": item.provider_id, "visit_date": item.starts_at, "reason": item.purpose, "appointment_id": item.id}, "visits")
    return record_dict(visit)

@app.get("/api/notes")
def notes(profile_id: str | None = None, include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, Note, profile_id, include_deleted, 1000)
@app.post("/api/notes", status_code=201)
def note_create(payload: NoteInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(create_record(db, Note, payload.model_dump(), "notes"))
@app.put("/api/notes/{record_id}")
def note_update(record_id: str, payload: NoteInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(update_record(db, Note, record_id, payload.model_dump(), "notes"))

@app.get("/api/observations")
def observations(profile_id: str | None = None, include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, Observation, profile_id, include_deleted, 1000)
@app.post("/api/observations", status_code=201)
def observation_create(payload: ObservationInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(create_record(db, Observation, payload.model_dump(), "observations"))

@app.get("/api/reminders")
def reminders(profile_id: str | None = None, include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, Reminder, profile_id, include_deleted, 1000)
@app.post("/api/reminders", status_code=201)
def reminder_create(payload: ReminderInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(create_record(db, Reminder, payload.model_dump(), "reminders"))
@app.put("/api/reminders/{record_id}")
def reminder_update(record_id: str, payload: ReminderInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(update_record(db, Reminder, record_id, payload.model_dump(), "reminders"))

@app.post("/api/reminders/{record_id}/complete")
def reminder_complete(record_id: str, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = db.get(Reminder, record_id)
    if not item or item.deleted_at:
        raise HTTPException(status_code=404, detail="Reminder not found")
    old = record_dict(item)
    item.status = "completed"
    audit(db, "reminders", item.id, "complete", old, record_dict(item))
    recurrence = json.loads(item.recurrence_json or "{}")
    next_item = None
    if recurrence.get("pattern") == "daily":
        next_due = _aware(item.due_at) + timedelta(days=1)
        while next_due <= datetime.now(timezone.utc):
            next_due += timedelta(days=1)
        until = date.fromisoformat(recurrence["until"]) if recurrence.get("until") else None
        if until is None or next_due.date() <= until:
            next_item = Reminder(profile_id=item.profile_id, prescribed_medication_id=item.prescribed_medication_id, appointment_id=item.appointment_id, kind=item.kind, title=item.title, due_at=next_due, recurrence_json=item.recurrence_json, status="pending", notes=item.notes)
            db.add(next_item); db.flush(); audit(db, "reminders", next_item.id, "create", None, record_dict(next_item))
    db.commit()
    return {"completed": record_dict(item), "next": record_dict(next_item) if next_item else None}

@app.post("/api/reminders/{record_id}/snooze")
def reminder_snooze(record_id: str, minutes: int = Query(default=10, ge=1, le=1440), db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = db.get(Reminder, record_id)
    if not item or item.deleted_at:
        raise HTTPException(status_code=404, detail="Reminder not found")
    old = record_dict(item); item.status = "snoozed"; item.snoozed_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    audit(db, "reminders", item.id, "snooze", old, record_dict(item)); db.commit(); return record_dict(item)

@app.post("/api/doses", status_code=201)
def dose_event(payload: DoseEventInput, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = DoseEvent(**payload.model_dump()); db.add(item); db.flush(); audit(db, "dose_events", item.id, "create", None, record_dict(item)); db.commit(); return record_dict(item)

TRASH_MODELS = {"profiles": Profile, "providers": Provider, "visits": Visit, "prescriptions": Prescription, "medications": Medication, "prescribed-medications": PrescribedMedication, "appointments": Appointment, "notes": Note, "observations": Observation, "reminders": Reminder, "documents": Document}


@app.delete("/api/{entity_type}/{record_id}", status_code=204)
def trash(entity_type: str, record_id: str, db: Session = Depends(get_db), _=Depends(require_csrf)):
    model = TRASH_MODELS.get(entity_type)
    if not model: raise HTTPException(status_code=404, detail="Unknown record type")
    soft_delete_record(db, model, record_id, entity_type.replace("-", "_")); return Response(status_code=204)


@app.post("/api/{entity_type}/{record_id}/restore")
def untrash(entity_type: str, record_id: str, db: Session = Depends(get_db), _=Depends(require_csrf)):
    model = TRASH_MODELS.get(entity_type)
    if not model: raise HTTPException(status_code=404, detail="Unknown record type")
    return record_dict(restore_record(db, model, record_id, entity_type.replace("-", "_")))


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), _=Depends(require_session)) -> dict[str, Any]:
    now, tomorrow = datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=1)
    upcoming_appointments = list(db.scalars(select(Appointment).where(Appointment.deleted_at.is_(None), Appointment.starts_at >= now, Appointment.status == "scheduled").order_by(Appointment.starts_at).limit(8)).all())
    due = list(db.scalars(select(Reminder).where(Reminder.deleted_at.is_(None), Reminder.status.in_(["pending", "snoozed"]), or_(Reminder.snoozed_until.is_(None), Reminder.snoozed_until <= tomorrow)).order_by(Reminder.due_at).limit(12)).all())
    recent: list[dict[str, Any]] = []
    for kind, model in (("Prescription", Prescription), ("Visit", Visit), ("Document", Document), ("Note", Note)):
        for item in list_records(db, model, limit=4):
            payload = record_dict(item); payload["kind"] = kind; recent.append(payload)
    recent.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    follow_ups = list(db.scalars(select(Visit).where(Visit.deleted_at.is_(None), Visit.follow_up_date.is_not(None), Visit.follow_up_date <= tomorrow).order_by(Visit.follow_up_date).limit(8)).all())
    return {"profiles": _crud_list(db, Profile, None, False, 100), "appointments": [record_dict(item) for item in upcoming_appointments], "reminders": [record_dict(item) for item in due], "follow_ups": [record_dict(item) for item in follow_ups], "recent": recent[:10], "backup": backup_health(db)}


@app.get("/api/timeline/{profile_id}")
def timeline(profile_id: str, db: Session = Depends(get_db), _=Depends(require_session)) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    specs = [("visit", Visit, "visit_date"), ("prescription", Prescription, "prescription_date"), ("appointment", Appointment, "starts_at"), ("note", Note, "occurred_at"), ("measurement", Observation, "observed_at"), ("document", Document, "document_date"), ("reminder", Reminder, "due_at")]
    for kind, model, date_key in specs:
        for row in list_records(db, model, profile_id=profile_id, limit=1000):
            payload = record_dict(row); payload["kind"] = kind; payload["event_date"] = payload.get(date_key) or payload.get("created_at"); items.append(payload)
    return sorted(items, key=lambda item: item.get("event_date") or "", reverse=True)


@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=500), profile_id: str | None = None, entity_type: str | None = None, db: Session = Depends(get_db), _=Depends(require_session)): return search_records(db, q, profile_id=profile_id, entity_type=entity_type)
@app.post("/api/search/rebuild")
def search_rebuild(db: Session = Depends(get_db), _=Depends(require_csrf)): return {"indexed": rebuild_search_index(db)}


@app.get("/api/documents")
def documents(profile_id: str | None = None, include_deleted: bool = False, db: Session = Depends(get_db), _=Depends(require_session)): return _crud_list(db, Document, profile_id, include_deleted, 1000)


@app.post("/api/documents", status_code=201)
async def document_upload(file: UploadFile = File(...), profile_id: str | None = Form(None), category: str = Form("other"), document_date: str | None = Form(None), title: str | None = Form(None), visit_id: str | None = Form(None), provider_id: str | None = Form(None), db: Session = Depends(get_db), _=Depends(require_csrf)):
    parsed_date = date.fromisoformat(document_date) if document_date else None
    try:
        item, duplicate = await store_document(db, file, profile_id=profile_id, category=category, document_date=parsed_date, title=title, visit_id=visit_id, provider_id=provider_id)
        return {"document": record_dict(item), "duplicate": duplicate}
    except IntegrityError:
        db.rollback(); existing = db.scalar(select(Document).where(Document.sha256 == item.sha256)); return {"document": record_dict(existing), "duplicate": True}


@app.get("/api/documents/{record_id}/content")
def document_content(record_id: str, download: bool = False, db: Session = Depends(get_db), _=Depends(require_session)):
    item = db.get(Document, record_id)
    if not item or item.deleted_at: raise HTTPException(status_code=404, detail="Document not found")
    path = safe_resolve(settings.data_dir, item.relative_path)
    if not path.is_file(): raise HTTPException(status_code=410, detail="Original file is missing; restore it from backup")
    return FileResponse(path, media_type=item.mime_type, filename=item.original_filename if download else None, content_disposition_type="attachment" if download else "inline")


@app.get("/api/documents/{record_id}/thumbnail")
def document_thumbnail(record_id: str, db: Session = Depends(get_db), _=Depends(require_session)):
    item = db.get(Document, record_id)
    if not item or not item.thumbnail_path: raise HTTPException(status_code=404, detail="Thumbnail unavailable")
    return FileResponse(safe_resolve(settings.data_dir, item.thumbnail_path), media_type="image/jpeg")


@app.post("/api/documents/{record_id}/ocr")
def document_ocr(record_id: str, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = db.get(Document, record_id)
    if not item or item.deleted_at: raise HTTPException(status_code=404, detail="Document not found")
    return record_dict(run_ocr(db, item))


@app.post("/api/documents/{record_id}/extract", status_code=201)
async def document_extract(record_id: str, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = db.get(Document, record_id)
    if not item: raise HTTPException(status_code=404, detail="Document not found")
    source = item.corrected_ocr_text or item.original_ocr_text
    if not source: raise HTTPException(status_code=409, detail="Run OCR or enter corrected text before extraction")
    proposal = await extract_medical_text(source)
    extraction = Extraction(source_type="document", source_id=item.id, schema_name="medical_record_proposal_v1", proposed_json=proposal.model_dump_json(), status="unverified")
    db.add(extraction); db.commit(); db.refresh(extraction)
    return record_dict(extraction)


@app.put("/api/extractions/{record_id}")
def extraction_review(record_id: str, payload: ExtractionUpdate, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = db.get(Extraction, record_id)
    if not item: raise HTTPException(status_code=404, detail="Extraction not found")
    old = record_dict(item); item.proposed_json = payload.proposal.model_dump_json(); item.status = payload.status; item.verified_at = utcnow() if payload.status != "unverified" else None
    audit(db, "extractions", item.id, "review", old, record_dict(item)); db.commit(); return record_dict(item)


@app.post("/api/voice-notes", status_code=201)
async def voice_upload(file: UploadFile = File(...), profile_id: str = Form(...), occurred_at: str | None = Form(None), db: Session = Depends(get_db), _=Depends(require_csrf)):
    voice_id = new_uuid(); relative, sha256, _size = await store_voice(file, voice_id)
    item = VoiceNote(id=voice_id, profile_id=profile_id, occurred_at=datetime.fromisoformat(occurred_at) if occurred_at else utcnow(), relative_path=relative, mime_type=file.content_type or "application/octet-stream", sha256=sha256)
    db.add(item); audit(db, "voice_notes", item.id, "create", None, record_dict(item)); db.commit(); return record_dict(item)


@app.post("/api/voice-notes/{record_id}/transcribe")
async def voice_transcribe(record_id: str, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = db.get(VoiceNote, record_id)
    if not item: raise HTTPException(status_code=404, detail="Voice note not found")
    try:
        item.transcript = await transcribe_voice(str(safe_resolve(settings.data_dir, item.relative_path))); item.transcription_status = "complete"
    except HTTPException:
        item.transcription_status = "unavailable"; db.commit(); raise
    db.commit(); return record_dict(item)


@app.get("/api/ai/status")
async def ai_status(_=Depends(require_session)): return await ollama_status()
@app.post("/api/ai/test")
async def ai_test(_=Depends(require_csrf)):
    status = await ollama_status(); return {**status, "test": "passed" if status["available"] else "unavailable"}
@app.post("/api/ai/query")
async def ai_query(payload: AIQueryInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return await answer_from_records(db, payload.question, payload.profile_id)


@app.get("/api/appointments.ics")
def calendar_export(profile_id: str | None = None, db: Session = Depends(get_db), _=Depends(require_session)):
    query = select(Appointment).where(Appointment.deleted_at.is_(None), Appointment.status == "scheduled")
    if profile_id: query = query.where(Appointment.profile_id == profile_id)
    appointments = db.scalars(query.order_by(Appointment.starts_at)).all()
    content = events_to_ics({"id": item.id, "starts_at": item.starts_at, "title": item.purpose or "Medical appointment", "description": item.preparation_notes, "location": item.location} for item in appointments)
    return PlainTextResponse(content, media_type="text/calendar", headers={"Content-Disposition": "attachment; filename=healthvault_appointments.ics"})


@app.get("/api/profiles/{profile_id}/doctor-summary")
def doctor_summary(profile_id: str, db: Session = Depends(get_db), _=Depends(require_session)):
    profile = db.get(Profile, profile_id)
    if not profile: raise HTTPException(status_code=404, detail="Profile not found")
    active = list(db.scalars(select(PrescribedMedication).where(PrescribedMedication.profile_id == profile_id, PrescribedMedication.tracking_status == "active", PrescribedMedication.deleted_at.is_(None))).all())
    visits = list(db.scalars(select(Visit).where(Visit.profile_id == profile_id, Visit.deleted_at.is_(None)).order_by(Visit.visit_date.desc()).limit(8)).all())
    notes = list(db.scalars(select(Note).where(Note.profile_id == profile_id, Note.deleted_at.is_(None)).order_by(Note.occurred_at.desc()).limit(8)).all())
    lines = [f"# Doctor Visit Summary — {profile.name}", "", "> Generated from personal records. Verify medical information before relying on it.", "", "## Important information", f"- Allergies: {profile.allergies or 'Not recorded'}", f"- Chronic conditions: {profile.chronic_conditions or 'Not recorded'}", "", "## Current tracked medicines"]
    for item in active: lines.append(f"- Medication UUID `{item.medication_id}` — {item.dosage or 'dose not recorded'}, {item.frequency or 'frequency not recorded'} ({item.verification_status})")
    lines.extend(["", "## Recent visits"])
    for item in visits: lines.append(f"- {item.visit_date.date().isoformat()}: {item.reason or 'Reason not recorded'} — {item.diagnosis_text or item.clinical_impression or 'Impression not recorded'}")
    lines.extend(["", "## Recent notes"])
    for item in notes: lines.append(f"- {item.occurred_at.date().isoformat()}: {item.content}")
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/markdown", headers={"Content-Disposition": f"attachment; filename=doctor_summary_{profile.id}.md"})


@app.get("/api/backups")
def backups(db: Session = Depends(get_db), _=Depends(require_session)): return backup_health(db)
@app.post("/api/backups/destinations", status_code=201)
def backup_destination_create(payload: BackupDestinationInput, db: Session = Depends(get_db), _=Depends(require_csrf)):
    path = str(Path(payload.path).expanduser().resolve()); item = BackupDestination(**payload.model_dump(exclude={"path"}), path=path); db.add(item); db.commit(); return record_dict(item)
@app.delete("/api/backups/destinations/{record_id}", status_code=204)
def backup_destination_delete(record_id: str, db: Session = Depends(get_db), _=Depends(require_csrf)):
    item = db.get(BackupDestination, record_id)
    if not item: raise HTTPException(status_code=404, detail="Destination not found")
    db.delete(item); db.commit(); return Response(status_code=204)
@app.post("/api/backups/credential")
def backup_credential(app_password: str = Form(...), backup_password: str = Form(..., min_length=12), db: Session = Depends(get_db), _=Depends(require_csrf)):
    configure_backup_secret(db, app_password, backup_password); return {"configured": True, "message": "The backup password is encrypted locally with your application password. Keep an offline copy; it cannot be recovered."}
@app.post("/api/backups/create")
def backup_create(payload: BackupCreateInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return record_dict(create_backup(db, payload.password, payload.kind))
@app.post("/api/backups/verify")
def backup_verify(payload: BackupPasswordInput, db: Session = Depends(get_db), _=Depends(require_csrf)):
    result = verify_backup(Path(payload.path).expanduser().resolve(), payload.password)
    run = db.scalar(select(BackupRun).where(BackupRun.archive_name == Path(payload.path).name).order_by(BackupRun.created_at.desc()))
    if run: run.verified_at = utcnow(); db.commit()
    return result
@app.post("/api/backups/test-restore")
def backup_test_restore(payload: BackupPasswordInput, _=Depends(require_csrf)): return verify_backup(Path(payload.path).expanduser().resolve(), payload.password, test_restore=True)
@app.post("/api/backups/restore")
def backup_restore(payload: BackupPasswordInput, db: Session = Depends(get_db), _=Depends(require_csrf)): return restore_backup(db, Path(payload.path).expanduser().resolve(), payload.password)


@app.post("/api/exports")
def export_create(db: Session = Depends(get_db), _=Depends(require_csrf)):
    path = create_export(db); return {"filename": path.name, "download_url": f"/api/exports/{path.name}"}
@app.get("/api/exports/{filename}")
def export_download(filename: str, _=Depends(require_session)):
    if Path(filename).name != filename: raise HTTPException(status_code=400, detail="Invalid export filename")
    path = settings.data_dir / "exports" / filename
    if not path.is_file(): raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(path, filename=filename, media_type="application/zip")
@app.post("/api/imports")
async def import_data(file: UploadFile = File(...), dry_run: bool = Form(True), db: Session = Depends(get_db), _=Depends(require_csrf)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as handle:
        temp = Path(handle.name)
        while chunk := await file.read(1024 * 1024): handle.write(chunk)
    try: return inspect_or_import(db, temp, dry_run=dry_run)
    finally: temp.unlink(missing_ok=True)


@app.get("/api/audit")
def audit_log(entity_type: str | None = None, entity_id: str | None = None, limit: int = 200, db: Session = Depends(get_db), _=Depends(require_session)):
    query = select(AuditLog)
    if entity_type: query = query.where(AuditLog.entity_type == entity_type)
    if entity_id: query = query.where(AuditLog.entity_id == entity_id)
    return [record_dict(row) for row in db.scalars(query.order_by(AuditLog.occurred_at.desc()).limit(min(limit, 1000))).all()]


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "dist"
if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists(): app.mount("/assets", StaticFiles(directory=assets), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend(full_path: str):
    if full_path.startswith("api/"): raise HTTPException(status_code=404, detail="API route not found")
    index = FRONTEND_DIST / "index.html"
    if index.exists(): return HTMLResponse(index.read_text(encoding="utf-8"))
    return JSONResponse(status_code=503, content={"detail": "Frontend is not built. Run npm run build."})


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
