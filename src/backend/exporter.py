from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import APP_VERSION, DATABASE_SCHEMA_VERSION, EXPORT_SCHEMA_VERSION, settings
from .models import (
    Appointment, AuditLog, Document, DoseEvent, EntityTag, Extraction, Medication, Note, Observation,
    PrescribedMedication, Prescription, Profile, Provider, Reminder, Tag, Visit, VoiceNote,
)
from .services import record_dict


EXPORT_MODELS: list[tuple[str, type[Any]]] = [
    ("profiles", Profile), ("providers", Provider), ("visits", Visit), ("documents", Document),
    ("prescriptions", Prescription), ("medications", Medication), ("prescribed_medications", PrescribedMedication),
    ("appointments", Appointment), ("notes", Note), ("observations", Observation), ("reminders", Reminder),
    ("dose_events", DoseEvent), ("voice_notes", VoiceNote), ("extractions", Extraction), ("tags", Tag),
    ("entity_tags", EntityTag), ("audit_logs", AuditLog),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def create_export(db: Session) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    target = settings.data_dir / "exports" / f"healthvault_export_{stamp}.healthvault-export.zip"
    with tempfile.TemporaryDirectory(prefix="healthvault-export-") as temp_name:
        root = Path(temp_name) / "healthvault-export"
        root.mkdir()
        counts: dict[str, int] = {}
        for name, model in EXPORT_MODELS:
            records = [record_dict(row, parse_json=False) for row in db.scalars(select(model)).all()]
            counts[name] = len(records)
            folder = root / name
            folder.mkdir()
            (folder / f"{name}.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
            if records:
                with (folder / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()), extrasaction="ignore")
                    writer.writeheader(); writer.writerows(records)
                markdown = [f"# {name.replace('_', ' ').title()}", ""]
                for record in records:
                    markdown.extend([f"## {record.get('name') or record.get('title') or record.get('id')}", ""] + [f"- **{key.replace('_', ' ').title()}:** {value}" for key, value in record.items() if value not in (None, "")] + [""])
                (folder / f"{name}.md").write_text("\n".join(markdown), encoding="utf-8")
        for relative in (Path("documents") / "originals", Path("voice") / "originals"):
            source = settings.data_dir / relative
            if source.exists():
                shutil.copytree(source, root / "attachments" / relative, dirs_exist_ok=True)
        (root / "DATA_FORMAT.md").write_text(_data_format_text(), encoding="utf-8")
        manifest = {"format": "healthvault-export", "export_schema_version": EXPORT_SCHEMA_VERSION, "database_schema_version": DATABASE_SCHEMA_VERSION, "application_version": APP_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "counts": counts, "unknown_fields_policy": "preserve-and-report"}
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        files = sorted(path for path in root.rglob("*") if path.is_file())
        (root / "checksums.sha256").write_text("\n".join(f"{_sha256(path)}  {path.relative_to(root).as_posix()}" for path in files) + "\n", encoding="utf-8")
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
    return target


def inspect_or_import(db: Session, archive_path: Path, *, dry_run: bool) -> dict[str, Any]:
    unknown: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    with tempfile.TemporaryDirectory(prefix="healthvault-import-") as temp_name:
        root = Path(temp_name)
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for info in archive.infolist():
                    candidate = PurePosixPath(info.filename)
                    if candidate.is_absolute() or ".." in candidate.parts:
                        raise HTTPException(status_code=400, detail="Import contains an unsafe path")
                archive.extractall(root)
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Import archive is corrupt") from exc
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise HTTPException(status_code=400, detail="Import manifest is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        version = int(manifest.get("export_schema_version", 0))
        if version > EXPORT_SCHEMA_VERSION:
            raise HTTPException(status_code=409, detail=f"Export schema {version} is newer than supported schema {EXPORT_SCHEMA_VERSION}")
        model_by_name = dict(EXPORT_MODELS)
        if not dry_run:
            for name, model in EXPORT_MODELS:
                source = root / name / f"{name}.json"
                if not source.exists():
                    continue
                records = json.loads(source.read_text(encoding="utf-8"))
                allowed = {column.key for column in model.__table__.columns}
                for payload in records:
                    extras = sorted(set(payload) - allowed)
                    if extras:
                        unknown.setdefault(name, []).extend(extras)
                    known = {key: _coerce(model, key, value) for key, value in payload.items() if key in allowed}
                    db.merge(model(**known))
                counts[name] = len(records)
            db.commit()
            attachments = root / "attachments"
            if attachments.exists():
                shutil.copytree(attachments, settings.data_dir, dirs_exist_ok=True)
            if unknown:
                report = settings.data_dir / "logs" / f"import_unknown_fields_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
                report.write_text(json.dumps(unknown, indent=2), encoding="utf-8")
        else:
            for name in model_by_name:
                source = root / name / f"{name}.json"
                if source.exists(): counts[name] = len(json.loads(source.read_text(encoding="utf-8")))
        return {"valid": True, "dry_run": dry_run, "manifest": manifest, "counts": counts, "unknown_fields": {name: sorted(set(fields)) for name, fields in unknown.items()}}


def _coerce(model: type[Any], key: str, value: Any) -> Any:
    if value is None:
        return None
    column = model.__table__.columns[key]
    try:
        kind = column.type.python_type
    except NotImplementedError:
        return value
    if kind is datetime and isinstance(value, str): return datetime.fromisoformat(value)
    if kind is date and isinstance(value, str): return date.fromisoformat(value)
    return value


def _data_format_text() -> str:
    return """# HealthVault Local Export Format v1

This archive is framework-independent. `manifest.json` identifies schema versions and record counts. Each entity folder contains canonical UTF-8 JSON, Excel-friendly CSV, and readable Markdown. Relationships use stable UUID strings. Original document and voice bytes are under `attachments/` and retain the paths referenced by their JSON metadata. `checksums.sha256` authenticates every payload file. Null means unknown; importers must preserve or report unknown fields rather than silently discarding them. Dates are ISO 8601 and timestamps include offsets where known.
"""
