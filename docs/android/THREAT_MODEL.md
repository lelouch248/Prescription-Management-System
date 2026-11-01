# Android threat model

Status: proposed for R0 approval. This model is reviewed again when storage,
backup, reminders, AI, and release signing are implemented.

## Protected assets

- canonical family health records and stable relationships;
- original medical documents, images, and voice recordings;
- medicine schedules, dose events, appointments, and reminder state;
- vault master key, password verifiers, recovery credentials, and backup keys;
- backup archives, audit history, and migration/recovery evidence;
- release-signing continuity needed to deliver trustworthy upgrades.

## Trust boundaries

1. Compose UI and authenticated local session
2. Domain policy and repositories
3. Encrypted database and encrypted immutable originals
4. Android Keystore and optional biometric convenience unlock
5. Alarm/notification/boot receivers
6. Untrusted imported files and archives
7. Untrusted `content://` document providers and removable media
8. Optional downloaded model/runtime and AI proposal output
9. Build, CI, signing, and distribution systems

The Android OS and an unlocked device owner are trusted to the degree required
for a local application. Root compromise, a malicious accessibility service,
screen capture by the device owner, and malware running with equivalent device
control are residual platform risks; the app does not claim to defeat them.

## Threats and required controls

| Threat | Required controls | Verification evidence |
|---|---|---|
| Lost or stolen locked device | App-private storage, encrypted DB/files, strong vault password, Keystore convenience key, short idle lock, notification privacy | locked-device tests; no plaintext files |
| Keystore/biometric invalidation | Independent password-wrapped vault master key; biometric is never the sole recovery path | invalidate key and recover with password |
| Offline password guessing | Memory-hard password derivation with versioned parameters, rate limiting, no recovery oracle | known-answer and throttling tests |
| Malicious document/archive | byte-signature MIME checks, size limits, streamed processing, path traversal rejection, parser isolation, immutable originals | adversarial corpus and bounded-memory tests |
| Partial write, crash, or full disk | transactions, fsync/atomic promotion where supported, staged candidates, checksums, emergency snapshot | injected interruption/full-storage tests |
| Cloud provider loss/corruption | encrypted archive, local verified copy, streamed upload, read-back hash, visible partial failure, two destinations | provider failure matrix and restore drill |
| Revoked document URI permission | detect before schedule, preserve local backup, actionable health warning | revoked-grant WorkManager test |
| Notification replay/duplication | stable occurrence IDs, idempotent PendingIntents/domain commands, duplicate suppression | repeated broadcast/tap tests |
| Reboot, timezone, DST, Doze | persisted canonical schedule, boot/time-change reschedule, exact-alarm capability check, visible degradation | device/emulator scenario suite |
| AI hallucination or unsafe action | retrieved evidence only, UUID citations, strict schemas, null unknowns, unverified proposals, no write capability | synthetic grounded evaluation and capability review |
| Model/runtime supply-chain compromise | pinned version, checksum/signature, explicit download, sandboxed provider boundary, no network after install | checksum failure and dependency scan |
| Backup password loss | explicit non-recoverability warning, password-manager/offline-copy guidance, verified test restore | onboarding and disaster drill |
| Signing key loss/compromise | offline encrypted custody, separated CI credentials, documented rotation/recovery, reproducible signed build | custody checklist and upgrade test |
| Accidental logs/screenshots/telemetry | no analytics, redacted operational logs, secure-screen option, synthetic diagnostics, privacy guard | log review and privacy tests |

## Data-loss invariants

- Original uploads are immutable; thumbnails, OCR, and other derivatives are
  separate and replaceable.
- Schema, import, file-layout, backup, and restore changes define rollback first
  and include recovery tests before promotion.
- AI and OCR output cannot write canonical medical data directly.
- Unknown medical values are `null`, never inferred to satisfy a schema.
- A candidate restore never replaces live data before authentication, checksum,
  database/domain validation, and an emergency snapshot.
- A cloud copy is not successful until the completed ciphertext can be read back
  and its hash matches the locally verified archive.

## Residual risks requiring user-visible disclosure

- An unlocked/rooted device or malicious screen/accessibility software may read
  information while the user is viewing it.
- Exact alarms can be denied or delayed by platform/vendor policy; HealthVault
  must show capability health and cannot guarantee delivery against a powered-
  off or severely restricted device.
- Cloud providers can remove, conflict, or delay files. Two independent,
  periodically test-restored destinations remain necessary.
- On-device models may be wrong. They organize evidence and never replace a
  clinician or user verification.
