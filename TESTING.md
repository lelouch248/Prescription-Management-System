# Testing

All automated tests use fictional names and medical details. No test may read the default live `data/` directory.

## Commands

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest --cov=backend --cov-report=term-missing
npm test
npm run lint
npm run build
```

## Current automated coverage

- First-run lock, password login, rate/CSRF session boundaries
- Profile/provider/visit/note CRUD, full-text search, audit log, trash restore
- Medication validation, prescribed schedule, dose event history
- Dashboard and combined profile timeline
- Real MIME validation, immutable original bytes, thumbnail generation, SHA-256 duplicate detection
- Encrypted backup signature, wrong-password rejection, inner checksums, SQLite integrity, profile opening during test restore
- Corrupt backup detection
- Portable JSON/CSV/Markdown export with manifest/schema/original attachments
- ICS calendar export
- Local AI unavailable behavior and evidence-free safe answer
- Extraction failure cannot create a prescription
- Security headers and OpenAPI version
- Production TypeScript/Vite build

## Critical disaster matrix

Before a release, run or confirm:

| Scenario | Expected result |
|---|---|
| Delete database in a disposable vault | Restore recreates profiles and records |
| Delete original documents in a disposable vault | Restore repopulates hash paths and checksums |
| Fresh install/new data directory | One `.hvault` reconstructs the vault |
| Flip one ciphertext byte | Verification fails before extraction |
| Wrong password | Authentication tag failure; current data unchanged |
| Restore older schema | Supported migration applies after emergency snapshot |
| App upgrade | Pre-migration snapshot exists and integrity check passes |

Never run destructive restore testing against a real vault. Set `HEALTHVAULT_DATA_DIR` to a disposable path and verify its resolved absolute location first.

## Responsive/accessibility checks

Verify 390×844 mobile, 768×1024 tablet, and 1440×900 desktop widths; keyboard navigation; visible focus; dialog Escape; form labels; 44 px primary touch targets; system/light/dark themes; reduced-motion behavior; and print layout for doctor summaries.
