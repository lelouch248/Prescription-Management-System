from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import AppSetting, SessionRecord


SESSION_COOKIE = "hv_session"
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def is_configured(db: Session) -> bool:
    return db.get(AppSetting, "password_hash") is not None


def set_password(db: Session, password: str) -> None:
    value = _hasher.hash(password)
    existing = db.get(AppSetting, "password_hash")
    if existing:
        existing.value = value
    else:
        db.add(AppSetting(key="password_hash", value=value))


def verify_password(db: Session, password: str) -> bool:
    row = db.get(AppSetting, "password_hash")
    if not row:
        return False
    try:
        return _hasher.verify(row.value, password)
    except VerifyMismatchError:
        return False


def enforce_login_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    with _lock:
        recent = _attempts[client_ip]
        while recent and now - recent[0] > 900:
            recent.popleft()
        if len(recent) >= 10:
            raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
        recent.append(now)


def clear_login_attempts(client_ip: str) -> None:
    with _lock:
        _attempts.pop(client_ip, None)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, response: Response, client_ip: str | None) -> dict[str, str]:
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.session_minutes)
    db.add(SessionRecord(token_hash=_token_hash(token), csrf_token=csrf, created_at=now, last_seen_at=now, expires_at=expires, client_ip=client_ip))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_minutes * 60,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )
    return {"csrf_token": csrf}


def delete_session(db: Session, response: Response, token: str | None) -> None:
    if token:
        db.execute(delete(SessionRecord).where(SessionRecord.token_hash == _token_hash(token)))
    response.delete_cookie(SESSION_COOKIE, path="/")


def require_session(
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> SessionRecord:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vault is locked")
    record = db.get(SessionRecord, _token_hash(token))
    now = datetime.now(timezone.utc)
    if not record or _as_utc(record.expires_at) <= now:
        if record:
            db.delete(record)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    record.last_seen_at = now
    record.expires_at = now + timedelta(minutes=settings.session_minutes)
    db.commit()
    request.state.session = record
    return record


def require_csrf(
    request: Request,
    session: SessionRecord = Depends(require_session),
    csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> SessionRecord:
    if request.method not in {"GET", "HEAD", "OPTIONS"} and (not csrf or not secrets.compare_digest(csrf, session.csrf_token)):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    return session


def purge_expired_sessions(db: Session) -> None:
    db.execute(delete(SessionRecord).where(SessionRecord.expires_at < datetime.now(timezone.utc)))


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
