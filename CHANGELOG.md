# Changelog

## 0.1.0 — 2026-08-10

Initial local-first release.

- Canonical UUID health model for family profiles, providers, visits, prescriptions, medicines/schedules/doses, appointments, documents, notes, observations, voice notes, reminders, tags, extraction proposals, and audit history
- SQLite WAL/foreign-key/integrity/migration safety and FTS5 exact search
- Immutable streamed document storage, byte-signature validation, SHA-256 deduplication, thumbnails, separate OCR evidence/corrections
- Responsive dashboard, profile timelines, medication, appointment calendar, document viewer, search, assistant, backup and settings interfaces
- Local Argon2id lock, server-side sessions, CSRF, throttling, security headers, strict CORS, no telemetry
- Streaming AES-256-GCM `.hvault` backup, generic destinations, verification, test restore, emergency snapshot and full restore
- Versioned portable JSON/CSV/Markdown/original export and version-aware import
- Optional Ollama, Tesseract, HEIC, faster-whisper providers with graceful absence and human-verification boundaries
- ICS export, browser notifications, PWA shell, Windows installation/startup scripts, privacy guard, synthetic fixtures, and automated test suite
