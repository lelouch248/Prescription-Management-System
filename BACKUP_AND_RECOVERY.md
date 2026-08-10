# Backup and recovery

Backup is distinct from data export. A backup restores a complete working vault. An export is a framework-independent handoff to future software.

## `.hvault` format v1

The encrypted file layout is:

```text
HVAULT01 magic | format byte | 16-byte salt | 12-byte nonce | AES-GCM ciphertext | 16-byte tag
```

The encryption key is derived from the user-controlled password with scrypt (`N=32768`, `r=8`, `p=1`) and used with streaming AES-256-GCM. The password is never written into the archive. Inside the encrypted ZIP:

```text
manifest.json
checksums.sha256
database/healthvault.db
documents/originals/...
voice/originals/...
```

The database is copied through SQLite's online backup API, not by copying a live WAL file. Each destination copy is re-hashed after writing.

## Recommended destinations

Configure at least two paths with independent failure modes:

1. Primary: a normal local or synced folder on another physical disk/service.
2. Secondary: an unplugged external disk or NAS share.
3. Optional archive: a monthly offline drive.

HealthVault treats each as an ordinary filesystem path, so OneDrive, Google Drive, Dropbox, NAS, USB, and second-drive folders work without vendor APIs. Confirm the sync client has finished before treating a cloud-synced folder as off-device protection.

## Automatic and retained backups

The local scheduler checks once per minute and creates an archive when the latest successful backup is older than 24 hours, if the application is running, a backup credential has been configured, and login has unlocked that credential. Sunday runs are weekly; first-of-month runs are monthly; other runs are daily. The credential is locally encrypted with the application password; keep the independent backup password offline. Per destination, retention keeps 7 daily, 8 weekly, 12 monthly, 20 manual, and 5 emergency archives. Use periodic offline copies for longer histories.

## Verify backup

Verification checks:

1. HealthVault header and supported format
2. AES-GCM authentication (wrong password or changed ciphertext fails)
3. ZIP structure and path safety
4. Required database, manifest, and checksum file
5. SHA-256 of each protected payload

The dashboard records successful verification time.

## Test restore

Test restore decrypts to a temporary directory, repeats all verification, opens the copied database, runs `PRAGMA integrity_check`, counts profiles, checks referenced payload presence through checksums, reports success, and deletes the temporary copy. Current data is untouched.

## Full restore

1. Verify and test-restore the chosen archive first.
2. Call the guided restore action with the archive path and backup password.
3. HealthVault creates an **emergency encrypted backup** of the current vault in `data/backups/`.
4. The candidate decrypts and validates in staging.
5. SQLite's backup API replaces the live database consistently.
6. Original documents and voice notes are restored by UUID/hash path.
7. A final live integrity check must pass.
8. Restart HealthVault and confirm counts/search.

If restoration is interrupted, the emergency archive is the rollback point. Never remove it until the restored vault has passed a second test backup.

## Acceptance failure scenarios

- Database deleted: install/start, select `.hvault`, verify/test, restore; database is recreated.
- Documents deleted: restoring the same archive repopulates original paths and hashes.
- Application reinstalled/new laptop: code installation is independent; one `.hvault` reconstructs vault data.
- Corrupt archive: AES-GCM, ZIP, required-file, checksum, or SQLite integrity validation rejects it before replacement.
- Wrong password: AES-GCM authentication rejects it; no data is changed.
- Backup schema older/newer: older supported formats migrate after safe restore; newer unsupported formats are refused with a version warning.
- App updated: pre-migration database snapshot is created before ordered schema migrations.

## Password loss

There is intentionally no recovery backdoor. Record the backup password in a reputable password manager and one sealed offline location. Test that copy before relying on it.
