# Android device and API matrix

Status: OS support baseline decided; the owner's exact physical devices remain
required release-evidence rows.

## SDK policy

- `minSdk`: API 29 (Android 10); API 28 and older are unsupported
- `compileSdk`: API 36 (Android 16) for the first implementation baseline
- `targetSdk`: API 36 for the first closed beta
- latest Android preview: compatibility smoke tests only, never the sole release
  environment

The project follows the latest stable Play target requirement at release time.
As of 2026-11-01, API 36 is required for new apps and updates submitted after
2026-08-31: <https://developer.android.com/google/play/requirements/target-sdk>.

## Required automated matrix

| Environment | Form factor | Purpose |
|---|---|---|
| API 29 emulator | compact phone | minimum API, crypto/Keystore, storage, process death |
| API 30 emulator | compact phone | scoped-storage and SAF/document-provider behavior changes |
| API 31 emulator | compact phone | exact-alarm permission and background restrictions |
| API 33 emulator | compact phone | notification runtime permission |
| API 35 emulator | medium/expanded tablet | adaptive UI, multi-window, keyboard, accessibility |
| API 36 emulator | compact phone | target behavior and release regression |
| API 36 emulator | expanded tablet | target behavior, rotation, split-screen, large text |

## Required physical-device classes

| Class | Minimum evidence before release |
|---|---|
| Owner's primary phone | exact model/Android version recorded; full migration, reminder, backup, and restore workflow |
| Owner's tablet, if used | adaptive UI, document capture/import, notification and provider tests |
| Mid-range device with 4–6 GB RAM | core vault and OCR; AI gated by measured capability |
| Device with 8+ GB RAM | optional local-model memory, thermal, cancellation, and background tests |
| Low/free-space scenario | import, backup, restore, and model download fail without changing vault |

No real records are used for device qualification. Tests use only approved
synthetic profiles and documents.

## Layout classes

- Compact: single-pane navigation and touch-first forms
- Medium: list/detail where it reduces navigation without hiding actions
- Expanded: persistent navigation plus list/detail, with no desktop-only hover
  dependency

All classes must pass portrait/landscape, font scaling, screen reader semantics,
44–48 dp touch target, color contrast, keyboard focus, and process recreation
checks.

## Capability gates

Core records, search, reminders, backup, and restore cannot depend on biometric
hardware, a neural accelerator, Google Play Services, or a particular cloud
provider. Biometric unlock, OCR acceleration, and on-device AI are optional
capabilities with clear fallback behavior.

The AI provider is enabled only after measuring available RAM, supported
accelerators/runtime, model size, generation latency, thermal behavior, and
out-of-memory recovery on that exact device class.
