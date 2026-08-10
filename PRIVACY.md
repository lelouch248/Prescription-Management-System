# Privacy

HealthVault Local has no telemetry, advertising, analytics, crash-reporting cloud, tracking pixel, or required SaaS integration. Core application requests remain on the host or private LAN.

## Stored locally

- Health profiles and structured records
- Original documents and voice notes
- OCR evidence/corrections
- Local AI proposals and transcripts
- Audit records, sessions, backup destinations, and operational status

Passwords are not stored in plaintext. The application password is Argon2id-hashed. An optional automatic-backup credential is encrypted locally with a key derived from the application password; the independent backup password is not stored inside any backup.

## Optional local processors

- Tesseract receives image pixels on the same computer.
- Ollama receives retrieved record text at `127.0.0.1` only.
- faster-whisper receives local audio paths.

No cloud provider implementation is enabled. A future external provider must be opt-in, visibly disclose the exact data leaving the device, and remain behind the same provider boundary.

## GitHub boundary

GitHub contains source, documentation, and clearly fictional fixtures only. `data/`, databases, originals, audio, OCR output, backups, exports, secrets, and credentials are ignored and blocked by a pre-commit privacy guard. Review `git status` and run `python scripts/privacy_guard.py` before every push.

## Deleting records

Application deletion moves records to recoverable trash. Backup archives and exported copies are immutable snapshots and must be expired separately. Original medical evidence is deliberately not physically deleted as part of a routine record-trash action.

## User responsibility

Choose private backup destinations, use full-disk encryption, protect the backup password, avoid public Wi-Fi/LAN mode, and do not upload real records to public bug reports or repositories.
