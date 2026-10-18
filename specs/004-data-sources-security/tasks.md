---
description: "Task list for feature 004 — Data Sources and Internet-Grade Security"
---

# Tasks: Data Sources and Internet-Grade Security

**Input**: `/specs/004-data-sources-security/` (plan, spec, research, data-model, contracts, quickstart)

**Tests**: included — security features are verified by tests first (crypto, address guard, MFA,
throttle, step-up, secret-leak search), then connectors and UI.

**Execution mode**: Claude designs and audits; DeepSeek drafts selected non-security UI files;
Claude writes all security-critical code (crypto, netguard, MFA, auth changes) and reviews every
draft before a task is checked.

## Phase 1: Setup

- [X] T001 Add backend dependencies `cryptography>=46`, `zeep>=4.3`, `pyotp>=2.10`, `segno>=1.6` (`backend/pyproject.toml`, `uv.lock`); confirm the backend image still builds for amd64 and arm64
- [X] T002 [P] Settings in `backend/app/config.py`: `bizview_secret_key: SecretStr | None`, `bizview_secret_key_previous`, `security_profile: Literal["auto","internet","private"]="auto"` + resolved property, `admin_allowed_networks: list[IPv4Network|IPv6Network]`, `sources_allow_private_networks=True`, `login_rate_limit=20`, `login_rate_window_minutes=15`; `DATABASE_URL_ORIGIN` read only by the legacy import
- [X] T003 [P] Installer: generate `BIZVIEW_SECRET_KEY` (32 bytes, base64url); new option `--security-profile private|internet|auto` — asked interactively with the suggestion derived from `--site` (domain → `internet`, `:80` → `private`), `auto` with `--yes`; `internet` without a domain → exit 2 ("el perfil internet requiere un dominio con HTTPS"); `private` with a domain keeps HTTPS but allows HTTP sources; writes `SECURITY_PROFILE`; tests in `deploy/tests/test_install.sh`; `.env.example` updated; development `.env` gets a key and `SECURITY_PROFILE=private`

## Phase 2: Foundational (blocks all stories)

- [X] T004 Migration `backend/alembic/versions/0003_sources_security.py` + ORM in `backend/app/models.py` exactly per data-model.md (`data_source` with unique `lower(name)` index and the `(secrets_ct IS NULL) = (secrets_key_id IS NULL)` check; `security_state` singleton `CHECK (id = 1)`; `app_user` TOTP columns; `recovery_code`; `user_session.mfa_pending`, `reauth_at`; `login_throttle`; audit kinds extended); downgrade reverses
- [X] T005 Tests first `backend/tests/test_crypto.py`: round trip; tamper → error; AAD mismatch (other row/purpose) → error; wrong key → error; key id; rotation with previous key re-encrypts all rows in one transaction; rotation of 1,000 sources < 1 min (SC-006); start refuses when data exists and key missing/wrong
- [X] T006 Implement `backend/app/security/crypto.py` (`encrypt(obj, aad)`, `decrypt(blob, key_id, aad)`, `key_id()`, `ensure_key_check(db)`, `verify_key_at_start(db)`, `rotate(db)`) and CLI `rotate-secret-key`; call `verify_key_at_start` in `bootstrap`
- [X] T007 Tests first `backend/tests/test_netguard.py`: classification of loopback, unspecified, link-local, metadata (v4/v6), multicast, private (allowed/blocked by setting), public; names `backend`, `web`, `localhost`; a hostname resolving to several addresses with one blocked → blocked; pinned HTTP backend dials the checked IP and keeps SNI (local HTTPS stub with a test CA); rebinding simulation (resolver returns public then loopback) → blocked at connect
- [X] T008 Implement `backend/app/security/netguard.py` (`check_host(host, port) -> list[IP]`, `BlockedAddress`, `PinnedNetworkBackend` for httpcore, `guarded_client(**httpx_kwargs)`)
- [X] T009 Implement `backend/app/security/profile.py`: resolve profile; `http_allowed` (private) vs HTTPS-only (internet) rule helpers used by source validation and connectors (FR-017 table); startup enforcement for `internet` (secure cookies + domain) with clear error; used by `bootstrap` and the app factory; tests for every row of the FR-017 table
- [X] T010 Caddy: remove `trusted_proxies static private_ranges`; add opt-in `{$TRUSTED_PROXIES}`; test forged `X-Forwarded-For` through Caddy records the real address (compose-level test script `deploy/tests/test_forwarded_for.sh`)

## Phase 3: User Story 1 — Database sources (P1) 🎯 MVP

- [X] T011 [US1] `backend/app/sources/schemas.py`: field definitions per kind from contracts/connectors.md (type, default, required, secret, options per profile), `validate(kind, settings, secrets, profile)` → normalised settings or field errors (`not_allowed_in_profile` for `http://` addresses and plain `sslmode` under `internet`, `blocked_address`, ranges)
- [X] T012 [US1] Tests first `backend/tests/test_sources_api.py`: CRUD as super user; admin/user/anonymous refused; duplicate name (any case) 409; secrets never in any response; PATCH secret semantics (omit keeps, null clears, value replaces); kind immutable; step-up required for create/update/delete/test (403 `reauth_required`); audit events with changed field names and no values; encrypted bytes in DB contain no plaintext
- [X] T013 [US1] `backend/app/sources/service.py` (create with id-then-encrypt in one transaction, update merge, delete, enable/disable, list/get serialisation, last-test persistence) and `backend/app/api/sources.py` per contracts/api.md incl. `GET /api/sources/types`
- [X] T014 [P] [US1] `backend/app/sources/connectors/base.py` (`TestResult`, error codes, timing, message redaction) and `postgresql.py` (hostaddr pinning, sslmode incl. `prefer`/`disable` only under `private`, CA temp file, read-only session, privilege warnings; profile re-checked at test time); tests `test_connectors_postgresql.py` against the development origin (read from the legacy URL or `TEST_POSTGRES_SOURCE_URL`) incl. wrong password → `auth_failed`, closed port → `unreachable`, `verify-full` with wrong CA → `tls_error`
- [X] T015 [US1] Frontend: `pages/admin/Sources.tsx` (cards: kind icon, name, status with icon+text, last test time, enabled switch, imported notice), `pages/admin/SourceForm.tsx` (fields rendered from `/api/sources/types`; `components/SecretField.tsx` shows "Configurada · Reemplazar · Quitar" and never pre-fills; test before save; save; delete with confirmation), route `/admin/fuentes`, super-user nav item "Fuentes"; Spanish strings

## Phase 4: User Story 2 — SOAP and REST sources (P2)

- [X] T016 [P] [US2] `connectors/rest.py` over `guarded_client`: `http://` only under `private` (re-checked at test time); all auth methods incl. OAuth 2.0 client credentials (basic/post client auth), custom headers (secret values), CA, no redirects, 1 MB cap; tests with in-process HTTP and HTTPS stubs (http refused under `internet` with `not_allowed_in_profile`; bearer ok/wrong, basic, api key header/query, oauth token flow + wrong secret, 302 to another host, 404, huge body, timeout)
- [X] T017 [P] [US2] `connectors/soap.py`: zeep with a guarded httpx transport, `http://` WSDL only under `private`, secure XML settings, basic / WS-Security UsernameToken / client certificate (temp PEM 0600, removed after load), CA; tests with a stub WSDL (operations listed; XXE payload refused; DTD refused; auth failure)
- [X] T018 [US2] Source form: SOAP and REST sections (auth-dependent fields, header list editor with per-header secret toggle), test result details (operations list collapsible; status/content type/bytes)

## Phase 5: User Story 3 — Security profile, two-step sign-in, throttling, step-up (P3)

- [X] T019 [P] [US3] Tests first `backend/tests/test_mfa.py`: setup requires step-up; enable with valid code returns 10 codes; login returns `mfa_required` + pending session limited to `/api/auth/mfa` and logout; pending expires after 5 min; code ±1 step ok, reused step refused, wrong ×5 locks; recovery code single use and audited; disable needs code and is refused for admins under `internet`; super user reset of another user (step-up) and CLI `reset-superuser-mfa`; `internet` profile → admin endpoints 403 `mfa_enrollment_required` until enrolled
- [X] T020 [US3] Implement `backend/app/security/mfa.py` (pyotp, segno SVG data URI, recovery codes Argon2id) and endpoints in `api/auth.py` (`/mfa`, `/reauth`), `api/me.py` (`/mfa/*`), `api/admin.py` (`/users/{id}/mfa/reset`); `auth/deps.py`: pending-session handling, `require_admin`/`require_superuser` MFA enforcement, `require_recent_reauth` (also applied to role changes in `PATCH /api/admin/users/{id}`, FR-021); `/api/me` added fields
- [X] T021 [P] [US3] Tests first `backend/tests/test_throttle.py` (20 failures across accounts from one address → 429 with retry-after for the window; other addresses unaffected; one audit event per window; MFA failures count; purge) and implement `backend/app/security/throttle.py` wired into login/mfa/reauth
- [X] T022 [P] [US3] Tests + implementation of the admin network allow-list middleware (`security/middleware.py`): admin/sources/security paths refused outside `ADMIN_ALLOWED_NETWORKS`, others unaffected, audited once per address per hour
- [X] T023 [US3] `GET /api/security` (`api/security.py`) per contract; tests `test_security_profile.py` (auto → internet with domain; startup refusal with insecure cookies under internet; checklist values)
- [X] T024 [US3] Frontend: sign-in second step (code input `inputmode=numeric autocomplete=one-time-code`, "usar código de recuperación" option), `pages/TwoFactorSetup.tsx` (QR, manual key with copy, confirm code, recovery codes with copy/download .txt and "los guardé" confirmation), profile section *Doble factor* (enable/disable/regenerate), forced enrollment route when `mfa_enrollment_required`, `components/ReauthDialog.tsx` + API-client retry on `reauth_required`, `pages/admin/Security.tsx` checklist, user list/detail show MFA status and reset action (super user)

## Phase 6: User Story 4 — Key safety and rotation (P4)

- [X] T025 [US4] Key rotation end to end (CLI + docs); `docs/INSTALL.md` sections: secret key backup, rotation, what is lost without the key; `SECURITY.md` update (profiles, 2FA recovery)

## Phase 7: User Story 5 — Legacy origin import (P5)

- [X] T026 [US5] Legacy import in `bootstrap` per research R10 with tests (import once, encrypted, audited, notice; no duplicate; skipped when sources exist); remove `DATABASE_URL_ORIGIN` from the development `.env` after import verification (asking the user first)

## Phase 8: Polish & Verification

- [X] T027 `backend/tests/test_secret_leaks.py`: run every source/MFA flow with marker secrets, then search API responses, captured logs, audit rows, and a `pg_dump`-equivalent read of all tables for the markers (SC-001)
- [X] T028 Feature 001 is superseded by 005 (vibe reporting): confirm the catalogue and connectors expose what the 005 runner needs (`open()` for extraction, structure for describe) and note it in 005's plan; run `/speckit-analyze` on 004
- [X] T029 Full verification: backend suite, frontend unit/build/compat, Playwright matrix (sources, two-step sign-in, re-auth dialog, security page at 320/375 px), installer tests, ShellCheck, actionlint, local installation from images with `SECURITY_PROFILE=internet` behind a test domain
- [X] T030 Security review of the diff (crypto use, AAD, secret handling, SSRF guard, XML, MFA replay, throttle bypass, header trust, logging) and mark tasks complete

## Dependencies & Execution Order

Phase 1 → Phase 2 (crypto, netguard, profile) → US1 → US2 (reuses US1 service/UI) · US3 can run in
parallel with US1/US2 after Phase 2 (step-up is needed by the sources API, so T020's
`require_recent_reauth` lands before T013 is completed) → US4 → US5 → Polish.

## Parallel Opportunities

T002/T003; T005/T007 (tests first); T016/T017; T019/T021/T022.

## Implementation Strategy

MVP = Phase 2 + US1 (encrypted PostgreSQL sources with testing) with step-up from US3. SQL Server
is deferred to a later version (research R2).
Then SOAP/REST, full internet profile with two-step sign-in, rotation, legacy import, and the
cross-cutting leak and security review.
