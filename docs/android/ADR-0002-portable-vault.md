# ADR 0002: Portable vault and migration boundary

- Status: proposed for R0 approval; byte-level contract finalized in Android 01
- Date: 2026-11-01

## Context

The desktop vault stores normalized records in SQLite and immutable originals on
the filesystem. Android will use Room and encrypted app-private storage. Room
must not be expected to ingest a SQLAlchemy-managed database directly, and a
framework database cannot become the long-term interchange format.

## Decision

The versioned canonical JSON representation is authoritative for migration and
cross-platform compatibility. It preserves:

- stable UUIDs and relationships;
- ISO dates/timestamps and explicit timezone information when known;
- JSON `null` for unknown medical data;
- verification status, evidence, audit history, and extraction provenance;
- original attachment bytes, canonical names, media types, sizes, and SHA-256;
- unknown future fields in an import report instead of silently discarding them.

CSV and Markdown remain convenience views. Framework-specific SQLite databases
are operational representations, not interchange contracts.

`.hvault` v1 remains readable for recovery compatibility. Android 01 will add
fixed Python/Kotlin known-answer vectors for its exact layout:

```text
HVAULT01 | format byte | salt | nonce | streaming AES-256-GCM ciphertext | tag
```

The v1 scrypt parameters remain `N=32768`, `r=8`, and `p=1`. Wrong passwords,
truncation, tampering, unsafe archive paths, unsupported future versions, and
checksum mismatches fail before any live replacement.

A proposed `.hvault` v2 places canonical JSON plus immutable originals inside
the authenticated encrypted archive. A v2 writer does not remove the v1 reader.
The format is finalized only after contract vectors and recovery tests exist.

## Migration transaction

1. Select an archive/export through the Storage Access Framework.
2. Stream it into private staging while computing a hash; never mutate source.
3. Authenticate/decrypt and validate archive structure and paths.
4. Perform a dry run: versions, space, counts, UUID graph, unknown fields,
   duplicate policy, and attachment hashes.
5. Present the report and require explicit confirmation.
6. Create and verify an encrypted emergency snapshot of any current vault.
7. Import into a disposable candidate vault and run integrity/domain checks.
8. Atomically promote the candidate or leave the current vault unchanged.
9. Retain a human-readable compatibility report with no medical contents in
   logs beyond the minimum identifiers needed for local remediation.

## Rollback

The source is read-only. Candidate state is disposable until promotion. A
failure before promotion deletes staging plaintext and candidate state. A
failure after promotion restores the verified emergency snapshot. Recovery
tests must inject interruption at every boundary before live migration is
enabled.

## One-primary-device rule

Importing a normal backup does not establish synchronization. Every vault and
backup manifest carries:

- stable `vault_id` UUID;
- monotonic `primary_epoch` integer beginning at 1;
- `primary_instance_id` UUID for the installation allowed to write;
- `primary_state`: `active`, `transfer_prepared`, `retired`, or
  `recovery_fork`;
- backup UUID, parent backup UUID when known, creation time, schema versions,
  and source instance/epoch;
- optional transfer UUID and `handoff` marker.

The state machine is normative:

| State | Canonical writes | Current backup | Meaning and allowed transitions |
|---|---:|---:|---|
| `active` | yes | yes | Sole normal writer at its epoch; may begin a planned transfer and become `transfer_prepared` |
| `transfer_prepared` | no | no | Handoff backup is already verified; may become `retired` after activation receipt, or return to `active` only through the safe cancellation rule below |
| `retired` | no | no | Historical read-only copy; may export evidence but cannot produce a backup presented as current |
| `recovery_fork` | yes, with persistent warning | yes, always marked with fork provenance | Emergency writer at a higher epoch; may become `active` only after explicit old-device retirement confirmation and a verified current backup |

`active` is the only normal write state. `recovery_fork` is deliberately
write-capable because its purpose is to recover from a lost primary, but every
screen and backup carries a degraded/fork warning until the ambiguity is
resolved. `transfer_prepared` and `retired` are read-only apart from diagnostic
export and explicit state-transition operations.

### Planned transfer

1. The active installation at epoch `N` creates and verifies a handoff backup
   with a new transfer UUID and proposed epoch `N+1`.
2. Only after verification succeeds, it records `transfer_prepared` durably and
   blocks canonical writes. A crash before that point leaves it active; a crash
   after it leaves it read-only and the verified handoff remains usable.
3. A new installation dry-runs and restores the handoff, creates a new instance
   UUID, becomes `active` at epoch `N+1`, and emits a small activation receipt
   containing vault/transfer/new-instance/epoch identifiers but no health data.
4. Importing that receipt changes the old installation from
   `transfer_prepared` to `retired`. It remains readable for comparison but
   cannot create a current backup.
5. Cancelling before activation requires explicit confirmation and records a
   cancelled transfer. If activation may have happened, cancellation is not
   offered; the emergency-fork path is used instead.

### Stale and emergency behavior

- A backup with the same `vault_id` and a lower epoch than the target is refused
  as a normal restore. It can be inspected/exported only through an explicit
  conflict workflow.
- A backup from another instance at the same epoch is treated as a fork and is
  never auto-merged.
- If the active device is lost, restoring its latest backup requires an
  explicit emergency takeover. The new device increments the epoch, creates a
  new instance UUID, sets `recovery_fork`, and marks all resulting backups with
  recovery provenance until the user confirms the prior device is wiped,
  permanently inaccessible, or explicitly retired. Confirmation followed by a
  newly verified current backup transitions `recovery_fork` to `active`.
- If an older installation later observes an activation receipt, backup, or
  provider manifest for the same vault at a higher epoch, it immediately blocks
  canonical writes/current backups and enters the retired/conflict workflow. It
  cannot merge its lower-epoch edits automatically.
- The UI displays vault ID suffix, instance, epoch, primary state, and latest
  backup generation in the transfer/recovery screens.

An offline retired or lost copy cannot be cryptographically notified that
another offline device has taken over. HealthVault therefore combines durable
write-blocking during planned transfer, generation/fork detection when artifacts
meet, and a prominent instruction to wipe or permanently retire the old device.
This limitation is disclosed rather than pretending backups provide consensus.
Concurrent edits remain unsupported until an encrypted conflict-aware sync
protocol is separately designed.
