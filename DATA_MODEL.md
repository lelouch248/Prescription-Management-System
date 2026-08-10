# Canonical data model

All externally meaningful identifiers are RFC 4122 UUID strings. Most health entities include `created_at`, `updated_at`, `archived_at`, and `deleted_at`. A populated `deleted_at` moves a record to recoverable trash; important medical records are not immediately physically removed.

## Core relationships

```text
Profile ─┬─ Visit ─── Prescription ─── PrescribedMedication ─── DoseEvent
         │    │              │                    │
         │    └─ Provider    └─ Document          └─ Reminder
         ├─ Appointment ── Provider
         ├─ Note
         ├─ Observation
         ├─ VoiceNote
         └─ Document
```

Relationships are nullable where old paperwork may be incomplete. Profile ownership is required for health events that need a definite person.

## Entities

- `profiles`: name, DOB, blood group, allergies, chronic conditions, notes, emergency information
- `providers`: doctor, specialty, hospital/clinic, contact/address, notes
- `visits`: person/provider/date, reason, symptoms, impression/diagnosis as written, follow-up, summary, notes
- `prescriptions`: person/visit/provider/document/date, diagnosis text, verification state
- `medications`: reusable generic/brand catalogue, strength, form, manufacturer
- `prescribed_medications`: person/prescription/medicine, dose/frequency/timing/duration/dates/food relation/instructions, PRN, verification and tracking states, JSON schedule
- `appointments`: person/provider/start/location/purpose/preparation/documents/reminder/status/post-visit notes
- `documents`: person/provider/visit/prescription links, immutable original path, MIME, SHA-256, byte size, dates/category, derivative path, original/corrected OCR and confidence
- `notes`: timestamped profile note with optional visit/medicine linkage
- `observations`: configurable measurement kind, value/unit, optional second value
- `reminders`: medication/appointment/follow-up/lab/check-up/renewal/custom, recurrence, due/snooze/status
- `dose_events`: immutable taken/skipped event with scheduled and recorded times
- `voice_notes`: original path/hash, transcript, extracted proposal, transcription and verification states
- `extractions`: source UUID/type, strict proposal JSON, unverified/verified/corrected state
- `tags` / `entity_tags`: flexible cross-entity labels
- `audit_logs`: meaningful operation, old/new canonical JSON, timestamp, session reference
- `backup_destinations` / `backup_runs`: generic filesystem destinations and observable outcomes
- `sessions`: server-side token hash, CSRF token, idle expiry; not exported
- `app_settings`: password hash and locally sealed backup credential; not exported
- `schema_meta`: database compatibility identifier

## Integrity rules

- SQLite foreign keys are enabled on every connection.
- Delete rules use `RESTRICT`, `SET NULL`, or `CASCADE` deliberately; the application normally soft-deletes first.
- Document SHA-256 is unique, so exact duplicates are reported but never auto-deleted.
- Prescription/medication verification states are `unverified`, `verified`, or `corrected`.
- Stopping medication tracking changes `tracking_status`; it does not modify prescriptions or past dose events.
- Schedule/recurrence JSON is version-neutral data, not executable code.

See `src/backend/models.py` for exact SQL types and `DATA_FORMAT.md` for portable serialization.
