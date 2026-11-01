# HealthVault Android v1 program

Status: **R0 architecture and threat-model review**.

HealthVault Android v1 is a native, standalone, offline-first vault. It is not a
WebView around the desktop application and it does not require the Windows host
to be running. The desktop application remains an independent migration,
export, and recovery tool.

The overriding priority is preserving user-owned medical data. No Android work
may inspect or depend on live `data/`. Tests, screenshots, migration fixtures,
and review evidence use only the repository's explicitly synthetic identities.

## Product boundary

Android v1 includes:

- encrypted local profiles, records, medicines, dose events, appointments,
  notes, measurements, documents, search, audit history, and reminders;
- phone and tablet layouts that remain usable without a network;
- dry-run, non-destructive migration from the versioned desktop portable
  format;
- encrypted, independently verifiable backup to user-selected Android document
  providers such as Google Drive, OneDrive, removable media, or local storage;
- optional, device-qualified, on-device OCR and AI proposals with citations;
- a second-device recovery drill before Android is designated the primary
  vault.

Android v1 explicitly excludes:

- concurrent editing or automatic synchronization between devices;
- a hosted HealthVault server or public Internet access to a vault;
- remote analytics, advertising SDKs, crash uploads, or cloud AI;
- AI authority to create or modify records, medicines, diagnoses, doses, or
  reminders;
- background access to contacts, location, or broad shared storage.

Backups are recovery artifacts, not synchronization. One device is the primary
editable vault until a separately designed encrypted-sync project is completed.

## Platform baseline

- Language/UI: Kotlin and Jetpack Compose
- Supported `minSdk`: Android 10 / API 29; older Android versions are not
  supported by Android v1
- Initial `compileSdk` and `targetSdk`: Android 16 / API 36
- Production application ID: `io.github.lelouch248.healthvault`
- Core operation: no Google Play Services dependency and no network required
- Storage: app-internal encrypted database and encrypted immutable originals
- Background work: AlarmManager for user-intentioned reminders; WorkManager for
  backup and maintenance
- External destinations: Android Storage Access Framework (`content://` URIs),
  never filesystem-path assumptions

The target SDK is reviewed at every release. Google Play requires new apps and
updates submitted after 31 August 2026 to target API 36 or higher:
<https://developer.android.com/google/play/requirements/target-sdk>.

The owner's exact devices remain required release evidence, but they do not
change the v1 OS floor. A device below Android 10 cannot install Android v1. If
testing finds an API 29 platform defect that would weaken recovery,
cryptography, or reminder correctness, changing the floor requires a new ADR
and reviewer approval rather than an implicit scaffold change.

## Architecture decisions

- [ADR 0001: Native standalone Android](ADR-0001-native-standalone.md)
- [ADR 0002: Portable vault and migration boundary](ADR-0002-portable-vault.md)
- [Threat model](THREAT_MODEL.md)
- [Device and API test matrix](DEVICE_MATRIX.md)
- [Network and permission policy](NETWORK_AND_PERMISSIONS.md)
- [Release signing, rollback, and recovery](RELEASE_AND_ROLLBACK.md)
- [Non-secret signing and identity register](SIGNING_REGISTER.md)

## Promotion gates

Every phase is independently reviewed. Findings are graded:

- **P0**: credible data-loss, privacy, or critical security risk;
- **P1**: release-blocking correctness, migration, or recovery defect;
- **P2**: important quality issue that does not invalidate the phase evidence.

Unresolved P0 or P1 findings block promotion. The reviewer reads source code,
tests, CI evidence, and synthetic fixtures only, never live user data, and may
not approve changes it authored.

The authoritative execution board is the
[Android v1 GitHub milestone](https://github.com/lelouch248/Prescription-Management-System/milestone/1).
The standing reviewer records gate evidence in
[Android review issue #15](https://github.com/lelouch248/Prescription-Management-System/issues/15).

## Definition of Android-primary readiness

Android cannot become the primary vault until all of the following are proven:

1. A synthetic desktop export dry-runs and imports with identical entity
   counts, stable relationships, provenance, and original-file SHA-256 hashes.
2. A failed or interrupted import leaves both source and current Android vault
   unchanged.
3. An encrypted Android backup verifies, test-restores, and fully restores on a
   second device or emulator using only the independent recovery password.
4. Reminder tests cover reboot, daylight-saving/timezone changes, Doze,
   permission denial/revocation, repeated delivery, and duplicate suppression.
5. Airplane-mode core workflows, migrations, accessibility, privacy guard, and
   signed upgrade tests pass.
6. The independent R8 review has no unresolved P0 or P1 finding.
