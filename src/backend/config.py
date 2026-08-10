from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_VERSION = "0.1.0"
DATABASE_SCHEMA_VERSION = 1
EXPORT_SCHEMA_VERSION = 1
BACKUP_FORMAT_VERSION = 1


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    host: str
    port: int
    session_minutes: int
    secure_cookies: bool
    ollama_url: str
    ollama_model: str | None

    @classmethod
    def load(cls) -> "Settings":
        raw = Path(os.getenv("HEALTHVAULT_DATA_DIR", "./data")).expanduser()
        data_dir = raw.resolve()
        return cls(
            data_dir=data_dir,
            host=os.getenv("HEALTHVAULT_HOST", "127.0.0.1"),
            port=int(os.getenv("HEALTHVAULT_PORT", "8765")),
            session_minutes=int(os.getenv("HEALTHVAULT_SESSION_MINUTES", "30")),
            secure_cookies=os.getenv("HEALTHVAULT_SECURE_COOKIES", "false").lower() == "true",
            ollama_url=os.getenv("HEALTHVAULT_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=os.getenv("HEALTHVAULT_OLLAMA_MODEL") or None,
        )

    @property
    def database_path(self) -> Path:
        return self.data_dir / "database" / "healthvault.db"

    def ensure_layout(self) -> None:
        for relative in (
            "database",
            "documents/originals",
            "documents/thumbnails",
            "documents/processed",
            "voice/originals",
            "exports",
            "backups",
            "logs",
            "migration_snapshots",
            "restore_staging",
        ):
            (self.data_dir / relative).mkdir(parents=True, exist_ok=True)


settings = Settings.load()
