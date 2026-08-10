# Development

## Repository layout

```text
src/backend/       FastAPI, domain services, models, migrations
src/frontend/      React/TypeScript responsive application
tests/backend/     API/domain/recovery tests with synthetic records
fixtures/synthetic/ Clearly fictional fixtures
migrations/        Migration policy
scripts/           Privacy and repository safety tools
public/            PWA metadata/service worker
data/              Live vault (ignored; created at runtime)
dist/              Production frontend build (ignored)
```

## Setup

```powershell
.\install.ps1
```

For development, run the API and Vite dev server in separate terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --app-dir src --reload --port 8765
npm run dev
```

Vite proxies `/api` to the local backend. Production `npm run build` emits `dist/`, which FastAPI serves directly.

## Architecture rules

- Never place framework-specific identifiers in portable relationships.
- Original uploads are immutable. Create derivatives under separate paths.
- Use deterministic code for storage, search, reminders, backup, import/export, and scheduling.
- AI may return validated proposals but must never call record-write services.
- Every write requiring provenance must append an audit entry in the same transaction.
- Add indexes from actual query patterns and verify with `EXPLAIN QUERY PLAN`; run `PRAGMA optimize` after schema changes.
- Add an ordered migration and compatibility test; never edit a released migration.
- Keep database, backup, export, and application versions independent.

## Adding an entity

1. Define the SQLAlchemy model and UUID relationships.
2. Add a strict Pydantic input schema (`extra=forbid`).
3. Add migration/indexes and portable export ordering.
4. Add CRUD/audit/soft-delete/search behavior as appropriate.
5. Add synthetic tests and UI.
6. Verify backup/restore and unknown-field import behavior.
7. Update `DATA_MODEL.md` and `DATA_FORMAT.md`.

## Release checklist

Run tests/build/lint, inspect `git diff`, stage only code/synthetic fixtures, run the privacy guard, create a fresh test backup and test restore, update versions/changelog, commit, then tag `vX.Y.Z`. Never push a tag containing a live `data/` path.
