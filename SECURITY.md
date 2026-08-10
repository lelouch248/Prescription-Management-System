# Security review

## Threat model

HealthVault protects against accidental exposure, opportunistic LAN access, malicious uploads, common web attacks, accidental Git commits, and damaged/modified backups. It does not claim to protect an unlocked Windows session from an administrator, malware, keyloggers, or physical disk extraction without OS disk encryption.

## Implemented controls

- Localhost binding by default; LAN binding is an explicit startup flag.
- First-run setup allowed only from loopback, preventing a LAN peer from claiming an empty vault.
- Argon2id application password hashing with deliberately expensive parameters.
- Opaque 384-bit session tokens; only SHA-256 token hashes are stored server-side.
- Sliding idle expiry (30 minutes default), `HttpOnly`, `SameSite=Strict`, path-scoped cookies; `Secure` cookies configurable for HTTPS.
- Per-session CSRF token required for all authenticated write endpoints.
- Login throttling by client address.
- Narrow CORS origins, Pydantic `extra=forbid` input validation, parameterized SQL/ORM, escaped React rendering.
- CSP, same-origin viewer frames with external frame ancestry blocked, MIME sniffing protection, referrer and browser-permission restrictions, no third-party scripts.
- Streamed upload size limit, byte-signature MIME validation, filename sanitization, UUID filenames, path containment, ZIP traversal checks.
- Original files are served as their validated MIME and never as user-provided HTML.
- SQLite foreign keys, transactions, WAL, FULL synchronous mode, busy timeout, integrity checks, and pre-migration snapshots.
- Encrypted authenticated backups with scrypt and AES-256-GCM; checksums defend the inner payload and destination-copy integrity.
- Audit history for meaningful health-record changes.
- Privacy-oriented `.gitignore` and staged-file guard.

## Local HTTPS for LAN

For a trusted home LAN, use a local reverse proxy such as Caddy with a locally trusted certificate:

```text
healthvault.home {
    tls internal
    reverse_proxy 127.0.0.1:8765
}
```

Bind HealthVault to localhost behind the proxy where possible, set `HEALTHVAULT_SECURE_COOKIES=true`, trust the Caddy local CA on intended devices, and allow only the proxy on Windows Private networks. Certificate distribution is a manual trust decision. Do not expose the proxy through router port forwarding.

## Windows hardening

- Enable BitLocker/device encryption for the live database and originals.
- Use a strong Windows login and automatic screen lock.
- Keep Windows, browsers, Python, Node build tooling, and dependencies updated.
- Use a standard user account for daily operation.
- Limit backup-folder permissions and safely eject offline drives.

## Review findings / residual risk

- Live files are not transparently encrypted by the application. OS disk encryption is the current at-rest control; backup encryption is mandatory.
- Any process running as the same Windows user can read an unlocked vault directory.
- Browser notifications expose their title on the local device. Use discreet reminder titles if lock-screen privacy matters.
- PDF parsing/viewing inherits risk from local browser/Python parsers. Keep dependencies patched and download originals only from trusted medical sources.
- LAN HTTP exposes credentials to a compromised local network; prefer local HTTPS where that threat matters.

Report suspected vulnerabilities privately and never attach real health records to an issue.
