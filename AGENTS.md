# HealthVault repository instructions

The overriding priority is preserving user-owned medical data. Code may change; live health records must remain private, durable, portable, and recoverable.

- Never read, copy, stage, commit, log, screenshot, or use real content from `data/` unless the user explicitly asks for a specific local diagnostic action.
- Never commit databases, documents, images, audio, OCR output, exports, `.hvault` archives, credentials, or names/details from live data.
- Tests and screenshots use only `Alex Example`, `Sam Example`, `Dr Fiction`, and explicitly synthetic medical details.
- Before schema/file/backup/restore changes, identify rollback behavior and add recovery tests.
- Original uploads are immutable; derivatives are separate.
- AI outputs are proposals only. They cannot directly create or change medical records, medicines, doses, diagnoses, or reminders.
- Unknown medical data is `null`, never guessed.
- Use stable UUIDs for portable relationships and preserve unknown import fields in a report.
- Run backend tests, frontend build, and `scripts/privacy_guard.py` before release.
