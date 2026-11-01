# Android network and permission policy

## Network policy

The canonical vault works in airplane mode. Reading, writing, searching,
viewing local documents, recording dose events, scheduling local reminders,
creating local encrypted backups, verifying, and restoring do not require a
HealthVault server.

Cloud destinations are accessed through Android document providers selected by
the user. HealthVault stores a persisted `content://` grant and streams bytes
through `ContentResolver`; it never assumes that a provider exposes a local
path, atomic rename, or immediate network availability.

Android v1 has one production release model and it does **not** request the
`INTERNET` permission. Cloud destinations use their user-selected document
provider. Optional model files are downloaded by the user's browser/provider
and imported through the system picker, then version/checksum validated before
activation. Direct in-app model download is deferred to a separately reviewed
release and cannot appear through an unreviewed product flavor.

CI inspects every merged release manifest and resolved runtime dependency graph.
It fails if `INTERNET`, broad storage, location, contacts, microphone, advertising
identifiers, analytics/crash-upload SDKs, or undeclared exported components
appear. Network tests also run core workflows with all connectivity disabled.

## Permission inventory

| Capability | Permission/access | Policy |
|---|---|---|
| Notifications | `POST_NOTIFICATIONS` on API 33+ | request in context; show degraded state if denied |
| Exact reminders | `SCHEDULE_EXACT_ALARM` special access where required | request only when precise reminders are enabled; check capability every schedule cycle and after restore/permission changes |
| Reboot recovery | `RECEIVE_BOOT_COMPLETED` | reschedule persisted reminders; never unlock records |
| Camera capture | `CAMERA` | request only from explicit capture action; picker remains available |
| Biometric convenience unlock | `USE_BIOMETRIC` | optional; recovery password always works independently |
| Files/cloud destinations | Storage Access Framework URI grants | no broad media/storage permission; user selects each source/destination |
| Internet | none in Android v1 | cloud providers and browser downloads are separate user-selected apps |

The app does not request contacts, location, SMS, call log, nearby devices, or
broad shared-storage access. Microphone/voice capture is deferred until its own
threat model and explicit user workflow exist.

## Exact-alarm degradation

Android v1 uses `SCHEDULE_EXACT_ALARM`, not `USE_EXACT_ALARM`. Precise medicine
and appointment reminders are an optional user-configured feature, and the
user-revocable special-access model is more honest than claiming an always-on
core alarm-clock role for Play policy purposes.

Before each exact schedule operation, and after package replacement, restore,
boot, and return from the special-access settings screen, HealthVault checks
`canScheduleExactAlarms()`. If access is absent it:

1. schedules the best supported inexact local fallback and reconciliation work;
2. labels the reminder-health state **Delayed delivery possible**;
3. shows that delivery may be delayed by Android rather than presenting the
   configured time as guaranteed;
4. offers an explicit route to grant special access; and
5. reschedules all future occurrences when capability becomes available.

Restored installations are assumed to have exact-alarm access denied until the
runtime check proves otherwise. No restore path silently treats historical
permission state as current.

## Component exposure

- Activities, providers, services, and receivers default to `exported=false`.
- Only Android-required intent entry points are exported, with narrow intent
  filters and validation.
- Notification actions use immutable or narrowly mutable explicit
  `PendingIntent`s and idempotent occurrence identifiers.
- File sharing, if added, uses a configured `FileProvider` and explicit
  temporary URI grants, never raw private paths.

## Logging and diagnostics

Release logs contain operational codes, versions, durations, counts when safe,
and exception classes—not patient names, record text, filenames supplied by the
user, OCR/transcript content, passwords, keys, prompts, or attachment bytes.

A diagnostic export is opt-in, locally previewable, synthetic/redacted by
construction, and never sent automatically.
