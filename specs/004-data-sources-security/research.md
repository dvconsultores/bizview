# Research: Data Sources and Internet-Grade Security

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-29

Decisions taken autonomously with the recommended option, at the user's request.

## R1. Encryption of credentials at rest

- **Decision**: application-level **AES-256-GCM** (`cryptography`'s `AESGCM`), key in the setting
  `BIZVIEW_SECRET_KEY` (32 random bytes, base64url), never stored in the database.
  - All secrets of one source are one JSON document encrypted as a whole: stored as
    `nonce (12 random bytes) || ciphertext+tag` in `data_source.secrets_ct`, with the key id
    (`secrets_key_id` = first 8 hex chars of SHA-256 of the key).
  - **Associated data** binds the ciphertext to its row and purpose:
    `bizview:v1:data_source:<id>:secrets` (TOTP secrets: `bizview:v1:app_user:<id>:totp`), so a
    ciphertext copied to another row or column fails to decrypt (FR-013).
  - **Key check**: `security_state.key_check` holds an encrypted known value; at start, if any
    encrypted data exists, the key must decrypt it or the backend refuses to start (FR-014) with
    "BIZVIEW_SECRET_KEY no coincide con la clave usada para cifrar".
  - **Rotation** (`python -m app.cli rotate-secret-key`): new key in `BIZVIEW_SECRET_KEY`, old one in
    `BIZVIEW_SECRET_KEY_PREVIOUS`; one transaction decrypts with whichever key id matches and
    re-encrypts everything with the new key, updates the key check and `key_rotated_at`, audits
    `secret_key_rotated` (FR-015). Afterwards the previous key setting is removed.
  - The installer generates the key; `docs/INSTALL.md` states it must be backed up separately from
    database backups.
- **Rationale**: authenticated encryption detects tampering; AAD prevents ciphertext swapping; a
  key outside the database means a stolen dump is useless (SC-001, US4).
- **Alternatives**: `pgcrypto` (rejected: the key travels to and is visible in the database;
  installs an extension); Fernet (rejected: AES-128-CBC+HMAC, no associated data); external KMS /
  HashiCorp Vault (rejected for this version: extra infrastructure for on-premises customers; the
  key-provider interface allows adding one later).

## R2. Connectors

One interface in `backend/app/sources/`: `test(source) -> TestResult` now; `open(source)` for the
extraction worker later. Every connector resolves and checks the destination address first (R3).

| Type | Library | Security settings | Test |
|---|---|---|---|
| PostgreSQL | `psycopg` 3 (already a dependency) | `sslmode` `require` / `verify-full` (+ CA); `hostaddr` = checked IP, `host` = name for certificate checks; `options=-c default_transaction_read_only=on`; `connect_timeout` | `select version()`; warn if `rolsuper`, CREATE on the database, or INSERT/UPDATE/DELETE on any table |
| SOAP | `zeep` with a custom transport over `httpx` (R3 guard) | `Settings(forbid_dtd, forbid_entities, forbid_external, xml_huge_tree=False)`; auth `basic`, `wsse_username_token` (`zeep.wsse.UsernameToken`), `client_certificate` (PEM kept in a 0600 temp file only while the SSL context loads) | load WSDL, list services/ports/operations (max 200) |
| REST | `httpx` (R3 guard) | TLS verification on; optional CA; auth `none`/`bearer`/`basic`/`api_key_header`/`api_key_query`/`oauth2_client_credentials` (token cached in memory until expiry); custom headers | `GET base + test_path`; 2xx ok, 401/403 `auth_failed`, 404 `not_found`; body read up to 1 MB |

- **Redirects**: never followed automatically; a redirect is reported as `invalid_response` with the
  target host, so credentials can never be forwarded (FR-010).
- **Read-only** (FR-007): PostgreSQL session default read-only; the account must still be
  read-only, which the test checks (FR-006).
- **Timeout**: per source, default 15 s, max 60 s, applied to connect and to the whole test.
- **SQL Server (deferred to a later version, user decision 2026-09-29)**: when added, use
  Microsoft's `mssql-python` (driver bundled, Linux amd64/arm64 wheels) with `Encrypt=Mandatory`,
  `TrustServerCertificate=No`, `ApplicationIntent=ReadOnly`, pinned `tcp:<ip>,<port>` +
  `HostNameInCertificate`; fallback `pyodbc` + ODBC Driver 18. The catalogue's `kind` check and the
  field-definition registry are designed so a new kind is one connector + one schema entry.
- **Where the code lives**: `backend/app/sources/` (models, crypto, connectors). The feature 001
  worker imports the same package (the repository installs `backend` as a local dependency of
  `integration`), so there is one implementation of connections and secrets.

## R3. Destination address guard (SSRF / DNS rebinding)

- **Decision**: before any connection, resolve the host (`getaddrinfo`) and check **every** resolved
  address:
  - always refused: loopback (`127.0.0.0/8`, `::1`), unspecified, link-local (`169.254.0.0/16`,
    `fe80::/10`), cloud metadata (`169.254.169.254`, `fd00:ec2::254`, `100.100.100.200`),
    multicast, reserved, and the backend container's own addresses and compose service names
    (`backend`, `web`, `localhost`);
  - private networks (`10/8`, `172.16/12`, `192.168/16`, `100.64/10`, `fc00::/7`): allowed unless
    `SOURCES_ALLOW_PRIVATE_NETWORKS=false`.
  Then connect **to the checked IP** (pinning), keeping the name for TLS/SNI: PostgreSQL via
  `hostaddr`; HTTP via a custom
  `httpcore` network backend that resolves, checks, and dials the checked address while httpx
  keeps the original host for SNI and certificate verification. This closes the DNS-rebinding
  window (SC-007).
- **Rationale**: an internet-facing product whose administrator account is compromised must not
  become a proxy into the server itself or the cloud provider's metadata service.

## R4. Security profile

- **Decision**: explicit installation option `SECURITY_PROFILE` = `private` | `internet` | `auto`
  (`auto` resolves to `internet` when `SITE_ADDRESS` is a domain, else `private`). The installer
  asks for it interactively (default suggested from the address) or takes `--security-profile`.
  It is not editable from the interface: changing it means editing `.env` and restarting.
  - **HTTP vs HTTPS** (user decision): `private` allows plain HTTP for the product address and for
    SOAP/REST/OAuth addresses, and plain PostgreSQL (`sslmode` `prefer`/`disable`); `internet`
    requires HTTPS for all of them and `sslmode` `require`/`verify-full`. Validation rejects
    disallowed values with `not_allowed_in_profile`; the connection test re-checks them, so sources
    saved under `private` stop working (with that reason) if the installation moves to
    `internet`.
  - `internet` enforces at start: `COOKIE_SECURE=true` and a domain `SITE_ADDRESS` (else the backend
    refuses to start with the reason); at run time: two-step sign-in for admin and super user;
    sources must use verified TLS and HTTPS addresses.
  - Both profiles: per-address sign-in throttling, step-up re-authentication, optional admin
    allow-list, write-only secrets, audit.
  - Session lifetimes stay 7 d idle / 30 d absolute (feature 002); a user can end all sessions by
    changing the password.
- **Rationale**: one switch the implementer understands; safe default derived from how the
  installation is published.

## R5. Two-step sign-in (TOTP)

- **Decision**: `pyotp` (RFC 6238, SHA-1, 6 digits, 30 s — universal authenticator compatibility),
  160-bit random secret encrypted with the master key (R1, AAD per user); `valid_window=1`;
  `totp_last_step` stored so a code is never accepted twice. Enrollment returns the `otpauth://`
  URI, the base32 secret for manual entry, and a QR code rendered **server-side as SVG with
  `segno`** (no third-party service, CSP-compatible `data:` image). Confirmation with a valid code
  enables it and returns 10 recovery codes (`XXXXX-XXXXX`, base32, 50 bits each) shown once,
  stored Argon2id-hashed, single use.
  - **Sign-in flow**: correct password + two-step enabled → response `{"mfa_required": true}` and a
    *pending* session (`user_session.mfa_pending = true`, expires after 5 minutes) that only
    allows `POST /api/auth/mfa` and logout; a valid code or recovery code upgrades it. Wrong codes
    count toward the account lockout and the address throttle.
  - **Enforcement** (`internet`): `require_admin` / `require_superuser` return
    `403 mfa_enrollment_required` until enrolled; the interface routes to enrollment.
  - **Reset**: super user resets another user's (step-up required, audited); CLI
    `reset-superuser-mfa` for the super user.
- **Alternatives**: WebAuthn/passkeys (better phishing resistance; planned later — heavier UX and
  per-device enrolment); SMS/email codes (rejected: weaker, needs a messaging provider).

## R6. Sign-in throttling per address

- **Decision**: table `login_throttle (ip, window_start, failures)` with fixed 15-minute windows;
  checked before verifying a password; failures (password or code) increment it; at 20 the address
  gets `429 rate_limited` with `retry_after_seconds` until the window ends, and one
  `login_rate_limited` audit event per window. Stored in PostgreSQL so it works across Uvicorn
  workers without Redis. Old rows purged by `bootstrap` and hourly by the request path (cheap
  `DELETE … WHERE window_start < now() - interval '1 day'` at most once per hour per worker).
  Configurable: `LOGIN_RATE_LIMIT=20`, `LOGIN_RATE_WINDOW_MINUTES=15`.

## R7. Step-up re-authentication

- **Decision**: `user_session.reauth_at`; `POST /api/auth/reauth {password}` sets it (wrong
  passwords count toward lockout); dependency `require_recent_reauth(minutes=5)` returns `403
  reauth_required`. The frontend API client catches it, opens a password dialog, calls reauth, and
  retries the original request once.

## R8. Client address and proxies

- **Decision**: the backend is reachable only through Caddy (compose network, no published port), so
  Uvicorn keeps `--forwarded-allow-ips='*'` and trusts `X-Forwarded-For` from Caddy. Caddy must
  not pass through client-supplied forwarding headers: the `trusted_proxies static
  private_ranges` global option is **removed** (it let any LAN client spoof its address) and
  replaced by an opt-in `TRUSTED_PROXIES` setting for installations behind another load balancer.
  A test sends a forged `X-Forwarded-For` through Caddy and checks the audit address (FR-023).

## R9. Admin network allow-list

- **Decision**: `ADMIN_ALLOWED_NETWORKS` — comma-separated CIDRs; when set, a middleware refuses
  `/api/admin/*`, `/api/sources*`, and `/api/security*` from other addresses with `403
  address_not_allowed` (audited, at most once per address per hour). Sign-in and dashboards are not
  affected.

## R10. Legacy `DATABASE_URL_ORIGIN`

- **Decision**: `bootstrap` parses the URL if present; when no source exists it creates PostgreSQL
  source "Origen (importado)" (host, port, database, user; password encrypted; `sslmode` from the
  URL or `prefer`→`require`), audits `source_imported`, logs a warning to delete the variable, and
  sets a flag the *Fuentes de datos* page shows. When sources already exist it only logs the
  warning. The settings class ignores the variable otherwise.

## R11. Constitution impact

- Principle II ("the API must not query the origin on every request") is respected: the only
  origin access from the API is the super user's explicit connection test.
- Principle III gains: origin connections are defined in the encrypted source catalogue (no origin
  URL in settings); origin queries stay isolated in `custom_queries/`.
- Stack additions (amendment 1.5.0): `cryptography`, `zeep`, `pyotp`, `segno`.
