# ADR 0001: Native standalone Android application

- Status: proposed for R0 approval
- Date: 2026-11-01
- Decision owners: HealthVault project owner and implementation agent

## Context

The responsive React/FastAPI desktop application currently requires a Windows
host process. That makes routine access and native reminders inconvenient on a
phone or tablet. Medical records must remain accessible offline and recoverable
even if the desktop computer is unavailable.

## Decision

Build a native Android application in Kotlin with Jetpack Compose. The Android
application owns its local encrypted vault, immutable encrypted originals,
search index, alarm schedule, backup scheduler, and optional on-device model.

The implementation is divided into replaceable boundaries:

```text
Compose UI
  -> view models / use cases
  -> domain repositories and safety policy
  -> encrypted Room/SQLite + encrypted immutable files
  -> reminder, backup, OCR, and AI provider boundaries
```

Android framework APIs remain at the edge. Canonical record models and domain
rules do not depend on Activity, Compose, Room, cloud providers, or one model
runtime. Persistent data drives the UI; an Activity or process may be destroyed
without losing authoritative state.

The implementation follows Android's separation-of-concerns and persistent
data-layer guidance: <https://developer.android.com/topic/architecture>.

## Alternatives rejected

### WebView or Trusted Web Activity around the existing application

Rejected because it would still depend on a Python server or require moving
security-critical storage, alarms, and filesystem behavior behind a bridge.
Browser lifecycle and notification behavior do not satisfy the reminder and
offline-primary goals.

### Embedded Python/FastAPI on Android

Rejected because packaging, native lifecycle integration, background execution,
binary dependency support, and long-term Play compatibility would be fragile.
It would preserve code at the expense of the durable product boundary.

### Hosted FastAPI service with a thin Android client

Rejected for v1 because it introduces Internet availability, account recovery,
server operations, and a new breach surface. It contradicts standalone
local-first access.

### Cross-platform UI runtime

Deferred. Existing React DOM components are not directly reusable as native
components, while the safety-critical work is in Android storage, alarms,
permissions, backup providers, and process lifecycle. Kotlin/Compose minimizes
bridging at those boundaries.

## Consequences

- Domain behavior is ported and verified rather than mechanically reused.
- The portable data contract, not Python or Room internals, is the compatibility
  boundary.
- The Windows and Android implementations may evolve independently while
  preserving shared fixtures and recovery formats.
- Android-specific testing across OS versions and device vendors is mandatory.
- Multi-device synchronization remains a separate project; Android v1 has one
  primary writer.
