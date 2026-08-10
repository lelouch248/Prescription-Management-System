from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


FORBIDDEN_PATH_PARTS = {"data", "backups", "exports", "uploads", "documents", "voice", "logs", "secrets"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".hvault", ".heic", ".m4a", ".wav", ".webm"}
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
]
ALLOWLIST = {Path(".env.example"), Path("fixtures/synthetic/records.json")}


def staged_files() -> list[Path]:
    result = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], capture_output=True, text=True, check=True)
    return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    violations: list[str] = []
    for path in staged_files():
        normalized = Path(*path.parts)
        if normalized not in ALLOWLIST and (set(part.lower() for part in path.parts) & FORBIDDEN_PATH_PARTS or path.suffix.lower() in FORBIDDEN_SUFFIXES):
            violations.append(f"private-data path or extension: {path}")
            continue
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if normalized not in ALLOWLIST:
            for pattern in SECRET_PATTERNS:
                if pattern.search(content):
                    violations.append(f"possible secret: {path}")
                    break
    if violations:
        print("HealthVault privacy guard blocked the commit:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1
    print("HealthVault privacy guard: staged files look safe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
