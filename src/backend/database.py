from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from .config import DATABASE_SCHEMA_VERSION, settings
from .migrations import apply_migrations
from .models import Base


settings.ensure_layout()
engine = create_engine(
    f"sqlite:///{settings.database_path.as_posix()}",
    connect_args={"check_same_thread": False, "timeout": 30},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def configure_sqlite(dbapi_connection: sqlite3.Connection, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=FULL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


def _snapshot_before_migration(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    target = settings.data_dir / "migration_snapshots" / f"healthvault_pre_migration_{stamp}.db"
    source = sqlite3.connect(path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def initialize_database() -> None:
    is_new = not settings.database_path.exists()
    current = 0
    if not is_new:
        conn = sqlite3.connect(settings.database_path)
        try:
            table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'").fetchone()
            current = int(conn.execute("SELECT value FROM schema_meta WHERE key='database_schema_version'").fetchone()[0]) if table and conn.execute("SELECT value FROM schema_meta WHERE key='database_schema_version'").fetchone() else 0
        finally:
            conn.close()
        if current < DATABASE_SCHEMA_VERSION:
            _snapshot_before_migration(settings.database_path)
    with engine.begin() as conn:
        apply_migrations(conn, current, DATABASE_SCHEMA_VERSION)
        conn.exec_driver_sql("PRAGMA optimize")
    ok, message = integrity_check()
    if not ok:
        raise RuntimeError(f"Database integrity check failed: {message}")


def integrity_check(path: Path | None = None) -> tuple[bool, str]:
    target = path or settings.database_path
    conn = sqlite3.connect(target)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    finally:
        conn.close()
    message = str(row[0] if row else "no result")
    return message.lower() == "ok", message


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def consistent_database_copy(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(settings.database_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


initialize_database()
