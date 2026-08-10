from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import struct
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import APP_VERSION, BACKUP_FORMAT_VERSION, DATABASE_SCHEMA_VERSION, settings
from .database import consistent_database_copy, engine, integrity_check
from .models import AppSetting, BackupDestination, BackupRun, Profile, utcnow
from .services import record_dict


MAGIC = b"HVAULT01"
SALT_BYTES = 16
NONCE_BYTES = 12
TAG_BYTES = 16
_unlocked_backup_password: str | None = None


def _derive_key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def configure_backup_secret(db: Session, app_password: str, backup_password: str) -> None:
    from .auth import verify_password
    if not verify_password(db, app_password):
        raise HTTPException(status_code=401, detail="Application password is incorrect")
    salt, nonce = os.urandom(SALT_BYTES), os.urandom(NONCE_BYTES)
    cipher = AESGCM(_derive_key(app_password, salt)).encrypt(nonce, backup_password.encode("utf-8"), b"healthvault-backup-secret-v1")
    for key, value in {
        "backup_secret_salt": salt.hex(),
        "backup_secret_nonce": nonce.hex(),
        "backup_secret_cipher": cipher.hex(),
    }.items():
        row = db.get(AppSetting, key)
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value))
    db.commit()
    unlock_backup_secret(db, app_password)


def unlock_backup_secret(db: Session, app_password: str) -> bool:
    global _unlocked_backup_password
    rows = {key: db.get(AppSetting, key) for key in ("backup_secret_salt", "backup_secret_nonce", "backup_secret_cipher")}
    if not all(rows.values()):
        return False
    try:
        salt = bytes.fromhex(rows["backup_secret_salt"].value)  # type: ignore[union-attr]
        nonce = bytes.fromhex(rows["backup_secret_nonce"].value)  # type: ignore[union-attr]
        cipher = bytes.fromhex(rows["backup_secret_cipher"].value)  # type: ignore[union-attr]
        _unlocked_backup_password = AESGCM(_derive_key(app_password, salt)).decrypt(nonce, cipher, b"healthvault-backup-secret-v1").decode("utf-8")
        return True
    except Exception:
        _unlocked_backup_password = None
        return False


def unlocked_backup_password() -> str | None:
    return _unlocked_backup_password


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_bundle_zip(target: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="healthvault-backup-") as temp_name:
        staging = Path(temp_name)
        payload = staging / "payload"
        payload.mkdir()
        db_target = payload / "database" / "healthvault.db"
        consistent_database_copy(db_target)
        for relative in (Path("documents") / "originals", Path("voice") / "originals"):
            source = settings.data_dir / relative
            if source.exists():
                shutil.copytree(source, payload / relative, dirs_exist_ok=True)
        paths = sorted(path for path in payload.rglob("*") if path.is_file())
        checksums = {path.relative_to(payload).as_posix(): _sha256(path) for path in paths}
        profile_count = 0
        conn = sqlite3.connect(db_target)
        try:
            profile_count = int(conn.execute("SELECT COUNT(*) FROM profiles WHERE deleted_at IS NULL").fetchone()[0])
        finally:
            conn.close()
        manifest = {
            "format": "healthvault-backup",
            "backup_format_version": BACKUP_FORMAT_VERSION,
            "database_schema_version": DATABASE_SCHEMA_VERSION,
            "application_version": APP_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "profile_count": profile_count,
            "file_count": len(paths),
            "encryption": "AES-256-GCM",
            "kdf": "scrypt-n32768-r8-p1",
        }
        (payload / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        checksum_lines = [f"{checksum}  {name}" for name, checksum in checksums.items()]
        (payload / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for path in sorted(payload.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(payload).as_posix())
        return manifest


def _encrypt_file(source: Path, target: Path, password: str) -> None:
    salt, nonce = os.urandom(SALT_BYTES), os.urandom(NONCE_BYTES)
    encryptor = Cipher(algorithms.AES(_derive_key(password, salt)), modes.GCM(nonce)).encryptor()
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".partial")
    try:
        with source.open("rb") as incoming, partial.open("xb") as outgoing:
            outgoing.write(MAGIC)
            outgoing.write(struct.pack("B", BACKUP_FORMAT_VERSION))
            outgoing.write(salt)
            outgoing.write(nonce)
            while chunk := incoming.read(1024 * 1024):
                outgoing.write(encryptor.update(chunk))
            outgoing.write(encryptor.finalize())
            outgoing.write(encryptor.tag)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)


def _decrypt_file(source: Path, target: Path, password: str) -> None:
    size = source.stat().st_size
    minimum = len(MAGIC) + 1 + SALT_BYTES + NONCE_BYTES + TAG_BYTES
    if size < minimum:
        raise HTTPException(status_code=400, detail="Backup is truncated or invalid")
    with source.open("rb") as incoming:
        if incoming.read(len(MAGIC)) != MAGIC:
            raise HTTPException(status_code=400, detail="Not a HealthVault encrypted backup")
        version = struct.unpack("B", incoming.read(1))[0]
        if version > BACKUP_FORMAT_VERSION:
            raise HTTPException(status_code=409, detail=f"Backup format {version} is newer than this application supports")
        salt, nonce = incoming.read(SALT_BYTES), incoming.read(NONCE_BYTES)
        incoming.seek(-TAG_BYTES, os.SEEK_END)
        tag = incoming.read(TAG_BYTES)
        cipher_end = size - TAG_BYTES
        incoming.seek(len(MAGIC) + 1 + SALT_BYTES + NONCE_BYTES)
        decryptor = Cipher(algorithms.AES(_derive_key(password, salt)), modes.GCM(nonce, tag)).decryptor()
        remaining = cipher_end - incoming.tell()
        partial = target.with_suffix(target.suffix + ".partial")
        try:
            with partial.open("xb") as outgoing:
                while remaining:
                    chunk = incoming.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    outgoing.write(decryptor.update(chunk))
                try:
                    outgoing.write(decryptor.finalize())
                except InvalidTag as exc:
                    raise HTTPException(status_code=401, detail="Wrong backup password or damaged backup") from exc
            os.replace(partial, target)
        finally:
            partial.unlink(missing_ok=True)


def _safe_zip_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise HTTPException(status_code=400, detail="Backup contains an unsafe path")
        if member.file_size > 10 * 1024 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Backup member is unexpectedly large")
    return members


def _validate_decrypted_zip(path: Path, *, extract_to: Path | None = None) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            members = _safe_zip_members(archive)
            names = {member.filename for member in members}
            if not {"manifest.json", "checksums.sha256", "database/healthvault.db"}.issubset(names):
                raise HTTPException(status_code=400, detail="Backup is missing required recovery files")
            manifest = json.loads(archive.read("manifest.json"))
            checksums: dict[str, str] = {}
            for line in archive.read("checksums.sha256").decode("utf-8").splitlines():
                checksum, name = line.split("  ", 1)
                checksums[name] = checksum
            for name, expected in checksums.items():
                if name not in names or hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise HTTPException(status_code=400, detail=f"Checksum verification failed for {name}")
            if extract_to:
                archive.extractall(extract_to, members=members)
    except (zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Backup archive is corrupt") from exc
    if extract_to:
        ok, message = integrity_check(extract_to / "database" / "healthvault.db")
        if not ok:
            raise HTTPException(status_code=400, detail=f"Restored database failed integrity check: {message}")
    return manifest


def create_backup(db: Session, password: str | None, kind: str = "manual", *, local_only: bool = False) -> BackupRun:
    password = password or unlocked_backup_password()
    if not password:
        raise HTTPException(status_code=400, detail="Backup password is required; it is never stored inside the archive")
    now = datetime.now(timezone.utc)
    # Microseconds prevent an emergency pre-restore snapshot from overwriting
    # the selected backup when both are created within the same second.
    stamp = now.strftime("%Y-%m-%d_%H%M%S_%f")
    archive_name = f"healthvault_backup_{stamp}_{kind}.hvault"
    run = BackupRun(status="running", kind=kind, archive_name=archive_name)
    db.add(run)
    db.commit()
    db.refresh(run)
    results: list[dict[str, Any]] = []
    try:
        with tempfile.TemporaryDirectory(prefix="healthvault-bundle-") as temp_name:
            plain = Path(temp_name) / "bundle.zip"
            encrypted = Path(temp_name) / archive_name
            _write_bundle_zip(plain)
            _encrypt_file(plain, encrypted, password)
            destinations: list[tuple[str, Path, BackupDestination | None]] = [("Local recovery folder", settings.data_dir / "backups", None)]
            if not local_only:
                destinations.extend((item.name, Path(item.path).expanduser().resolve(), item) for item in db.scalars(select(BackupDestination).where(BackupDestination.enabled.is_(True))).all())
            seen: set[Path] = set()
            for name, destination, row in destinations:
                destination = destination.resolve()
                if destination in seen:
                    continue
                seen.add(destination)
                try:
                    destination.mkdir(parents=True, exist_ok=True)
                    final = destination / archive_name
                    shutil.copy2(encrypted, final)
                    if _sha256(final) != _sha256(encrypted):
                        raise OSError("copy checksum mismatch")
                    results.append({"name": name, "path": str(final), "status": "success"})
                    if row:
                        row.last_success_at = now
                        row.last_error = None
                    _apply_retention(destination)
                except Exception as exc:
                    results.append({"name": name, "path": str(destination), "status": "failed", "error": str(exc)})
                    if row:
                        row.last_error = str(exc)
            successes = [result for result in results if result["status"] == "success"]
            if not successes:
                raise OSError("No backup destination accepted the archive")
            run.status = "success" if len(successes) == len(results) else "partial"
            run.size_bytes = encrypted.stat().st_size
            run.destination_results_json = json.dumps(results)
            run.completed_at = utcnow()
            db.commit()
            return run
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        run.completed_at = utcnow()
        db.commit()
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}") from exc


def _apply_retention(directory: Path) -> None:
    limits = {"daily": 7, "weekly": 8, "monthly": 12, "manual": 20, "emergency": 5}
    for kind, limit in limits.items():
        files = sorted(directory.glob(f"healthvault_backup_*_{kind}.hvault"), key=lambda path: path.stat().st_mtime, reverse=True)
        for old in files[limit:]:
            old.unlink(missing_ok=True)


def verify_backup(path: Path, password: str, *, test_restore: bool = False) -> dict[str, Any]:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")
    with tempfile.TemporaryDirectory(prefix="healthvault-verify-") as temp_name:
        temp = Path(temp_name)
        plain = temp / "bundle.zip"
        _decrypt_file(path, plain, password)
        extraction = temp / "restored" if test_restore else None
        if extraction:
            extraction.mkdir()
        manifest = _validate_decrypted_zip(plain, extract_to=extraction)
        result: dict[str, Any] = {"valid": True, "manifest": manifest, "archive_sha256": _sha256(path)}
        if extraction:
            conn = sqlite3.connect(extraction / "database" / "healthvault.db")
            try:
                result["profile_count"] = int(conn.execute("SELECT COUNT(*) FROM profiles WHERE deleted_at IS NULL").fetchone()[0])
            finally:
                conn.close()
            result["test_restore"] = "passed"
        return result


def restore_backup(db: Session, path: Path, password: str) -> dict[str, Any]:
    emergency = create_backup(db, password, "emergency", local_only=True)
    with tempfile.TemporaryDirectory(prefix="healthvault-restore-") as temp_name:
        temp = Path(temp_name)
        plain, extracted = temp / "bundle.zip", temp / "restored"
        extracted.mkdir()
        _decrypt_file(path, plain, password)
        manifest = _validate_decrypted_zip(plain, extract_to=extracted)
        restored_db = extracted / "database" / "healthvault.db"
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA wal_checkpoint(FULL)")
        source = sqlite3.connect(restored_db)
        destination = sqlite3.connect(settings.database_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        for relative in (Path("documents") / "originals", Path("voice") / "originals"):
            source_dir = extracted / relative
            target_dir = settings.data_dir / relative
            if source_dir.exists():
                shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
        ok, message = integrity_check()
        if not ok:
            raise HTTPException(status_code=500, detail=f"Restore completed but live integrity check failed: {message}")
        return {"restored": True, "manifest": manifest, "emergency_backup": emergency.archive_name}


def backup_health(db: Session) -> dict[str, Any]:
    runs = list(db.scalars(select(BackupRun).order_by(BackupRun.created_at.desc()).limit(50)).all())
    successes = [run for run in runs if run.status in {"success", "partial"}]
    destinations = list(db.scalars(select(BackupDestination)).all())
    last = successes[0] if successes else None
    now = datetime.now(timezone.utc)
    age_days = ((_as_utc(now) - _as_utc(last.completed_at)).total_seconds() / 86400) if last and last.completed_at else None
    score = 100
    warnings: list[str] = []
    if age_days is None:
        score -= 60; warnings.append("No successful backup has been created")
    elif age_days > 7:
        score -= 55; warnings.append("No successful backup in 7 days")
    elif age_days > 1.5:
        score -= 20; warnings.append("Latest backup is older than one day")
    enabled = [item for item in destinations if item.enabled]
    if len(enabled) < 1:
        score -= 25; warnings.append("No external backup destination configured")
    if len(enabled) < 2:
        score -= 15; warnings.append("A second backup destination is strongly recommended")
    verified = next((run for run in successes if run.verified_at), None)
    if not verified:
        score -= 15; warnings.append("No backup verification has been recorded")
    label = "Excellent" if score >= 85 else "Good" if score >= 65 else "Warning" if score >= 40 else "Critical"
    return {"score": max(score, 0), "label": label, "warnings": warnings, "last_successful": record_dict(last) if last else None, "last_verified": record_dict(verified) if verified else None, "destinations": [record_dict(item) for item in destinations], "runs": [record_dict(run) for run in runs]}


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
