# Architecture

## Decision summary

HealthVault Local is a local modular monolith. This keeps the operational surface small without coupling durable data to one UI framework.

```text
Responsive React/TypeScript PWA shell
                ↓ REST/OpenAPI
FastAPI boundary: auth, validation, safety policy
                ↓
Domain services: records, search, files, reminders, backup, export, AI proposals
                ↓
SQLAlchemy repositories + immutable filesystem originals
                ↓
SQLite (WAL, foreign keys, integrity checks) + ordinary files
```

Python/FastAPI was selected for mature local file/OCR/AI tooling and readable long-term maintenance. React/Vite provides a responsive offline-capable UI with a small production bundle. SQLAlchemy separates domain code from SQLite details. Production serves the compiled frontend from FastAPI, so there is only one local process.

## Durability boundary

The framework-independent vault consists of:

- `data/database/healthvault.db`: operational normalized records
- `data/documents/originals/`: immutable uploaded bytes, sharded by hash prefix
- `data/voice/originals/`: original voice notes
- stable UUIDs in every portable relationship
- versioned `.hvault` backups and `.healthvault-export.zip` exports

React state, generated thumbnails, OCR tools, Ollama models, and Python packages are replaceable. Originals and canonical records are not.

## Modules

- `models.py`: normalized canonical record schema and constraints
- `migrations.py` / `database.py`: ordered schema upgrades, pre-migration snapshots, WAL/foreign keys, integrity checks
- `services.py`: CRUD, audit history, soft deletion, FTS indexing, path containment
- `storage.py`: streamed uploads, true MIME checks, hashing, deduplication, immutable originals, derivatives, OCR
- `backup.py`: consistent database copies, archive manifests/checksums, streaming AES-GCM, destination copies, verification, test restore, live restore
- `exporter.py`: independent JSON/CSV/Markdown/original export and version-aware import
- `auth.py`: Argon2id password verification, server-side session records, CSRF tokens, login throttling
- `ai.py`: optional Ollama/Whisper providers, deterministic retrieval, strict Pydantic proposals, no record-write capability
- `main.py`: OpenAPI routes, security middleware, scheduler, production SPA serving
- `src/frontend`: accessible responsive interface; authoritative data always comes from the API

## Search

SQLite FTS5 is the core search engine. A replaceable `search_index` contains denormalized text and stable entity/profile UUIDs. Results cite entity UUIDs. Embeddings can be added later behind a provider interface, but neither normal search nor assistant retrieval depends on a vector database.

## AI and extraction trust boundary

```text
Original evidence → OCR/raw transcript → local model proposal → Pydantic validation
        → visible UNVERIFIED review → explicit user confirmation → domain write
```

The model has no database credentials and no write tool. Null represents unknown. The safety prompt prohibits diagnosis, dose changes, or interpreting illegible handwriting. Evidence-free questions return an explicit no-records answer.

## Reminders

Reminder state and dose events are deterministic database records. The UI polls due reminders and may use the browser notification API. A local scheduler creates a daily encrypted backup while running and unlocked. Standard ICS export is the durable phone/off-host fallback.

## Major risks and controls

| Risk | Control |
|---|---|
| Disk/laptop loss | Encrypted multi-destination backup, visible safety score, checksums, test restore |
| App/framework abandonment | Versioned JSON/CSV/Markdown export, originals, UUIDs, schema docs |
| Database corruption | WAL, FULL synchronous writes, foreign keys, transactions, pre-migration snapshots, integrity checks |
| Incorrect handwritten extraction | Confidence/evidence fields, unverified status, manual confirmation, unchanged original |
| Backup password loss | Explicit onboarding warning and offline-copy guidance; password never placed in archive |
| LAN exposure | localhost default, password required, strict cookies/CORS/CSP, no automatic public binding |
| Host powered off | Documented notification limit and ICS phone-calendar fallback |

## Versioning

- Application: `0.1.0`
- Database schema: `1`
- Export schema: `1`
- Backup format: `1`

Each evolves independently. Future upgrades must preserve old export/backup readers or provide an explicit compatibility migration.
