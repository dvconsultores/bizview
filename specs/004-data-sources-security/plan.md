# Implementation Plan: Data Sources and Internet-Grade Security

**Branch**: `004-data-sources-security` | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-data-sources-security/spec.md`

## Summary

Replace the `DATABASE_URL_ORIGIN` setting with a catalogue of data sources managed by the super
user — PostgreSQL, SOAP (SAP), and REST (SQL Server in a later version) — whose credentials are write-only and
encrypted with AES-256-GCM under a key that exists only in the installation settings. Each source
can be tested through connectors that pin a checked destination address (no SSRF / DNS
rebinding), verify TLS, and parse XML safely. Add a security profile for internet-facing
installations, chosen explicitly with `SECURITY_PROFILE` (`private` allows HTTP, `internet`
requires HTTPS everywhere): TOTP two-step sign-in (mandatory for administrators under `internet`), per-address
sign-in throttling, step-up password confirmation for sensitive actions, an optional admin network
allow-list, trustworthy client addresses, key rotation, and a *Seguridad* overview. See
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12+, TypeScript 5 / Node 24

**Primary Dependencies**: features 002–003 stack + `cryptography` (AES-GCM), `zeep` (SOAP),
`pyotp` (TOTP), `segno` (QR as SVG); `psycopg` and
`httpx` already present

**Storage**: PostgreSQL `DATABASE_URL_BI`, schema `public`; migration `0003_sources_security`
([data-model.md](./data-model.md))

**Testing**: pytest (crypto, AAD binding, rotation; address guard incl. rebinding; connectors against
the development PostgreSQL origin, local stub HTTP/SOAP servers in-process (HTTP and HTTPS);
MFA, throttle, step-up, profile enforcement incl. HTTP-vs-HTTPS rules, secret-leak search);
Playwright (source forms, two-step enrollment and sign-in, re-auth dialog) at 320/375 px

**Target Platform**: installations from feature 003 (amd64/arm64)

**Project Type**: web application

**Performance Goals**: connection test ≤ timeout + 2 s (SC-003); key rotation of 1,000 sources < 1 min

**Constraints**: secrets never leave the backend in clear except to the origin system; no
database containers; interface Spanish, mobile first

**Scale/Scope**: tens of sources per installation; 3 connector kinds (SQL Server later); ~15 endpoints; 5 screens
(sources list, source form, security overview, two-step enrollment, sign-in second step) + dialog

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | Status | Evidence |
|---|---|---|
| I. Mobile-first | PASS | new screens built with the existing kit; e2e at 320/375 px |
| II. API not an origin proxy | PASS | the API touches an origin only for the super user's explicit connection test (R11) |
| III. Origin read-only, isolated | PASS → **clarified** | read-only sessions + permission warnings; origin connections now come from the encrypted catalogue (amendment 1.5.0); origin queries remain in `custom_queries/` |
| IV. Folders | PASS | `backend/app/sources/` (catalogue, crypto, connectors) shared with the future worker (R2) |
| V. Stack | **AMEND → 1.5.0** | adds `cryptography`, `zeep`, `pyotp`, `segno` |
| VII. One product | PASS | sources and security are settings/data per installation; nothing customer-specific in code |
| VIII. AI optional/private | PASS | untouched |
| Constraints (Alembic, JSON API, external DB) | PASS | migration 0003; JSON only (QR as data URI); no DB containers |

Post-design: PASS with amendment 1.5.0, which also adds the constraint "credentials are encrypted
at rest and write-only; internet-facing installations run the `internet` profile".

## Project Structure

### Documentation (this feature)

```text
specs/004-data-sources-security/
├── plan.md  research.md  data-model.md  quickstart.md  tasks.md
├── contracts/api.md  contracts/connectors.md
└── checklists/requirements.md
```

### Source Code

```text
backend/
├── alembic/versions/0003_sources_security.py
├── app/
│   ├── security/
│   │   ├── crypto.py          # AES-256-GCM, key ids, AAD, key check, rotation
│   │   ├── profile.py         # SECURITY_PROFILE resolution + startup enforcement
│   │   ├── netguard.py        # address classification, resolve+check, pinned httpcore backend
│   │   ├── mfa.py             # TOTP, QR (segno), recovery codes
│   │   ├── throttle.py        # per-address sign-in limits
│   │   └── middleware.py      # admin network allow-list
│   ├── sources/
│   │   ├── schemas.py         # per-kind field definitions (drives /types and validation)
│   │   ├── service.py         # CRUD, secret merge, encryption, audit, legacy import
│   │   └── connectors/{base,postgresql,soap,rest}.py   (sqlserver.py in a later version)
│   ├── api/sources.py  api/security.py  (+ auth.py mfa/reauth, me.py mfa, admin.py reset)
│   ├── auth/deps.py           # pending sessions, mfa enforcement, require_recent_reauth
│   └── cli.py                 # + rotate-secret-key, reset-superuser-mfa, legacy import in bootstrap
└── tests/ test_crypto.py test_netguard.py test_sources_api.py test_connectors_*.py test_mfa.py
           test_throttle.py test_reauth.py test_security_profile.py test_secret_leaks.py
frontend/src/
├── pages/admin/Sources.tsx  SourceForm.tsx  Security.tsx
├── pages/TwoFactorSetup.tsx  (sign-in second step inside SignIn.tsx)
├── components/ReauthDialog.tsx  SecretField.tsx
└── api/client.ts            # reauth_required → dialog → retry; mfa_enrollment_required → setup
deploy/install.sh            # + BIZVIEW_SECRET_KEY, --security-profile (asked; private|internet|auto)
deploy/caddy/Caddyfile       # remove trusted_proxies private_ranges; {$TRUSTED_PROXIES}
docs/INSTALL.md SECURITY.md  # key backup/rotation, profiles, 2FA recovery
```

**Structure Decision**: security primitives in `app/security/`, the catalogue and connectors in
`app/sources/` so feature 001's worker reuses them.

## Complexity Tracking

| Item | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Pinned-IP HTTP transport | SC-007 (DNS rebinding) | resolving once then letting the client resolve again leaves a rebinding window |
| Pending MFA sessions | second factor without trusting the client between steps | a signed cookie carrying "password ok" would need a second secret and replay rules |
