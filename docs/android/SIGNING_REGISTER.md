# Android signing and identity register

This file records non-secret continuity evidence only. Never add private keys,
passwords, recovery codes, secret locations, or credential screenshots.

## Immutable identity

| Field | Value |
|---|---|
| Production application ID | `io.github.lelouch248.healthvault` |
| Production signing mode | Play App Signing from first real-data closed test |
| Local synthetic variant | production ID with `.debug` suffix; debug key only |
| Other sideload variants | distinct application ID; never production lineage |
| Primary signing custodian | GitHub repository owner `lelouch248` |
| Recovery custodian | **Required before a release-signed build; not yet designated** |

## Public fingerprints and enrollment

| Evidence | Value | Verified date |
|---|---|---|
| Play app-signing certificate SHA-256 | Not generated | — |
| Upload certificate SHA-256 | Not generated | — |
| Play App Signing enrollment/account | Not enrolled | — |
| Account recovery owner confirmed | Pending | — |

## Custody evidence

| Check | Status | Last verified | Next due |
|---|---|---|---|
| Encrypted offline primary copy readable | Pending | — | Before first signed build |
| Independent encrypted recovery copy readable | Pending | — | Before first signed build |
| Upload-key recovery/reset procedure tested | Pending | — | Before first signed build |
| Two-factor/account recovery procedure tested | Pending | — | Before first signed build |
| Quarterly custody drill | Not started | — | After key generation |

## Rules

1. A pending row blocks generation of a release-signed build when its due field
   says "before first signed build".
2. Custody drills verify that authorized humans can recover the upgrade path;
   they do not expose key material to source control, CI output, or the review
   agent.
3. Certificate fingerprints, signed artifact hashes, source commit, dependency
   locks, and reproducible-build metadata are appended for each release.
4. Compromise triggers upload-key reset/revocation procedures and a security
   review. Production app-signing identity is never silently replaced.
