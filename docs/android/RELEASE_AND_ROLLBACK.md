# Android release signing, rollback, and recovery

## Release stages

1. Local debug builds using synthetic fixtures
2. Reproducible synthetic-only development build with application ID suffix
   `.debug`
3. Play App Signing enrollment and closed testing under the production
   application ID
4. Closed beta on designated physical phone/tablet devices
5. Production only after the R8 disaster drill and zero unresolved P0/P1

Android is not described as the primary vault during stages 1–4. Primary-vault
readiness requires the completed R8 gate and second-device disaster drill, even
when a closed beta otherwise appears stable. A separately
signed sideload build is never used as the production upgrade lineage; it uses
a distinct application ID and migrates through verified encrypted backup if it
ever contains user-owned data.

The immutable production application ID is
`io.github.lelouch248.healthvault`. Debug and synthetic-only local variants use
suffixes such as `.debug`. The production identity uses Play App Signing from
its first real-data closed test, with a separately controlled upload key.

## Signing-key custody

- Release/upload private keys and passwords never enter Git, CI logs, issue
  bodies, build artifacts, cloud backup destinations, or the HealthVault vault.
- The GitHub repository owner `lelouch248` is the primary signing custodian.
  A trusted recovery custodian, selected by the owner and not the implementation
  agent, must be recorded before any release-signed build exists.
- Keep one encrypted offline primary copy of upload/recovery material and one
  encrypted geographically independent recovery copy, with restore
  instructions and certificate fingerprints.
- CI receives the minimum short-lived/repository-scoped secret material needed
  to sign a release; pull requests from untrusted contexts cannot access it.
- Record Play App Signing enrollment, upload certificate fingerprints,
  custodian roles, non-secret inventory, account-recovery ownership, and the
  latest recovery-copy drill in `SIGNING_REGISTER.md`. Secret locations and
  credentials are never recorded in the repository.
- Verify every published APK/AAB certificate fingerprint and archive the signed
  artifact's SHA-256, source commit, dependency lockfiles, and build metadata.
- Verify recovery copies quarterly and before every production release. The
  recovery custodian confirms readability without transmitting secrets to CI
  or the repository.

No release-signed build may be generated until the register has a named
recovery custodian, expected fingerprints, two verified encrypted copies, and a
successful custody recovery drill. The R8 reviewer checks the non-secret
evidence, not the key material.

Losing update-signing continuity can strand installed vaults on an unpatchable
binary, so signing custody is part of medical-data durability rather than only
a publishing concern.

## Schema and file-layout upgrades

Before every schema, file-layout, crypto-envelope, backup, or restore change:

1. Define forward migration, failure boundaries, and rollback behavior.
2. Create and verify an encrypted pre-migration snapshot.
3. Migrate a disposable candidate or transactional database.
4. Run integrity, relationship, count, search-index, and attachment-hash checks.
5. Promote only after validation succeeds.
6. Retain compatibility readers and a documented recovery route for supported
   older backups.

Downgrading an on-device schema in place is unsupported. Rollback means install
the last trusted compatible binary and restore its verified pre-upgrade backup,
not forcing an older binary to open a newer database.

## Failed application upgrade

- The application detects an incomplete migration marker before normal unlock.
- It does not retry destructively or expose a partially migrated vault.
- It offers local recovery from the verified pre-migration snapshot and retains
  the failed candidate for explicit local diagnosis without uploading contents.
- Recovery is tested with injected interruption after every durable boundary.

## Failed restore or provider operation

- Provider writes are staged and verified by ciphertext hash/read-back when the
  provider permits it.
- A provider failure never deletes the local verified archive.
- Full restore validates a candidate and creates an emergency snapshot before
  replacing current data.
- Failure before promotion leaves current data unchanged; failure after
  promotion invokes the documented emergency-snapshot rollback.

## Release evidence

R8 requires:

- locked dependencies and reproducible build instructions;
- unit, contract, instrumentation, UI, accessibility, migration, backup,
  reminder, and adversarial-file test results;
- backend tests and frontend build for retained desktop compatibility;
- `scripts/privacy_guard.py` passing;
- signed upgrade from the previous beta with record/hash parity;
- synthetic desktop export -> Android import -> Android backup -> verification
  -> second-device full restore;
- independent reviewer verdict with no unresolved P0/P1.
