from __future__ import annotations

import hashlib
import io
import mimetypes
import os
import re
import shutil
from datetime import date
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Document, new_uuid
from .services import audit, reindex_record


MAX_UPLOAD_BYTES = 250 * 1024 * 1024
ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png", "image/heic", "image/heif"}
EXTENSION_FOR_MIME = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/heic": ".heic", "image/heif": ".heif"}


def _safe_filename(name: str | None) -> str:
    base = Path(name or "document").name
    clean = re.sub(r"[^\w.() -]+", "_", base, flags=re.UNICODE).strip(". ")
    return clean[:240] or "document"


def _detect_mime(path: Path, declared: str | None) -> str:
    with path.open("rb") as handle:
        header = handle.read(32)
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    try:
        with Image.open(path) as image:
            image.verify()
            fmt = (image.format or "").upper()
        return {"JPEG": "image/jpeg", "PNG": "image/png", "HEIF": "image/heif", "HEIC": "image/heic"}.get(fmt, "")
    except (UnidentifiedImageError, OSError):
        return ""


async def store_document(
    db: Session,
    upload: UploadFile,
    *,
    profile_id: str | None,
    category: str,
    document_date: date | None,
    title: str | None,
    visit_id: str | None = None,
    provider_id: str | None = None,
) -> tuple[Document, bool]:
    temp_id = new_uuid()
    temp = settings.data_dir / "documents" / "processed" / f"upload-{temp_id}.tmp"
    digest = hashlib.sha256()
    size = 0
    try:
        with temp.open("xb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File exceeds the 250 MB local upload limit")
                digest.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        mime = _detect_mime(temp, upload.content_type)
        if mime not in ALLOWED_MIME:
            raise HTTPException(status_code=415, detail="Only genuine PDF, JPEG, PNG, HEIC, and HEIF files are accepted")
        sha256 = digest.hexdigest()
        duplicate = db.scalar(select(Document).where(Document.sha256 == sha256))
        if duplicate:
            return duplicate, True
        extension = EXTENSION_FOR_MIME[mime]
        stored_filename = f"{temp_id}{extension}"
        subdir = sha256[:2]
        relative_path = Path("documents") / "originals" / subdir / stored_filename
        destination = settings.data_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp, destination)
        thumbnail = _make_thumbnail(destination, temp_id, mime)
        document = Document(
            id=temp_id,
            profile_id=profile_id,
            provider_id=provider_id,
            visit_id=visit_id,
            original_filename=_safe_filename(upload.filename),
            stored_filename=stored_filename,
            relative_path=relative_path.as_posix(),
            thumbnail_path=thumbnail,
            mime_type=mime,
            sha256=sha256,
            size_bytes=size,
            category=category,
            document_date=document_date,
            title=title or _safe_filename(upload.filename),
        )
        db.add(document)
        db.flush()
        audit(db, "documents", document.id, "create", None, {"id": document.id, "original_filename": document.original_filename, "sha256": sha256, "size_bytes": size, "mime_type": mime})
        reindex_record(db, "documents", document)
        db.commit()
        db.refresh(document)
        return document, False
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)


def _make_thumbnail(path: Path, document_id: str, mime: str) -> str | None:
    if not mime.startswith("image/"):
        return None
    relative = Path("documents") / "thumbnails" / f"{document_id}.jpg"
    target = settings.data_dir / relative
    try:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((640, 640))
            image.save(target, format="JPEG", quality=84, optimize=True)
        return relative.as_posix()
    except (OSError, UnidentifiedImageError):
        return None


def run_ocr(db: Session, document: Document) -> Document:
    path = (settings.data_dir / document.relative_path).resolve()
    if document.mime_type == "application/pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise HTTPException(status_code=503, detail="PDF text extraction is unavailable. Install the OCR optional dependencies.") from exc
        text = "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
        confidence = 1.0 if text else 0.0
    else:
        try:
            import pytesseract
        except ImportError as exc:
            raise HTTPException(status_code=503, detail="Local OCR is not installed. Run the optional OCR installation step.") from exc
        try:
            with Image.open(path) as image:
                data = pytesseract.image_to_data(ImageOps.exif_transpose(image), output_type=pytesseract.Output.DICT)
            words = [word for word in data["text"] if word.strip()]
            confidence_values = [float(value) for value in data["conf"] if float(value) >= 0]
            text = " ".join(words)
            confidence = sum(confidence_values) / (len(confidence_values) * 100) if confidence_values else 0.0
        except Exception as exc:
            document.ocr_status = "failed"
            db.commit()
            raise HTTPException(status_code=503, detail=f"Local OCR engine could not process this file: {exc}") from exc
    document.original_ocr_text = text
    document.ocr_confidence = confidence
    document.ocr_status = "complete" if text else "needs_review"
    audit(db, "documents", document.id, "ocr", None, {"ocr_status": document.ocr_status, "ocr_confidence": confidence})
    reindex_record(db, "documents", document)
    db.commit()
    db.refresh(document)
    return document


async def store_voice(upload: UploadFile, voice_id: str) -> tuple[str, str, int]:
    safe_name = _safe_filename(upload.filename)
    extension = Path(safe_name).suffix.lower()[:12] or ".webm"
    relative = Path("voice") / "originals" / f"{voice_id}{extension}"
    target = settings.data_dir / relative
    digest = hashlib.sha256()
    size = 0
    with target.open("xb") as handle:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Voice note exceeds the 250 MB limit")
            digest.update(chunk)
            handle.write(chunk)
    return relative.as_posix(), digest.hexdigest(), size
