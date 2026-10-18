# Tasks: Sign in with Google

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · **Feature**: `027-google-sign-in`

Every task names the file it touches. `[x]` = done and verified in this session.

## Phase 1: Governance and design

- [x] T001 Amend constitution principle V's **Auth** line (optional federated identity provider, bounded by off-by-default, per-installation client, invite-only, second factor preserved), bump to 2.1.0 and add the Sync Impact Report — `.specify/memory/constitution.md`
- [x] T002 Write the specification (13 FRs, 6 success criteria, the invite-only decision and the edge cases) — `specs/027-google-sign-in/spec.md`
- [x] T003 Write the plan with the six research decisions, including why no JWT library is added — `specs/027-google-sign-in/plan.md`

## Phase 2: Backend

- [x] T004 `GOOGLE_AUTH_ENABLED`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_ALLOWED_DOMAINS`, `GOOGLE_REDIRECT_URI`, plus `google_enabled_effective` (enabled **and** id **and** secret) — `backend/app/config.py`
- [x] T005 `GoogleLink` table: user FK with cascade, **unique** `google_sub`, last known email, timestamps — `backend/app/models.py`
- [x] T006 Migration 0021 creating `google_link`, reversible — `backend/alembic/versions/0021_google_sign_in.py`
- [x] T007 Authorization URL (scope `openid email profile`, `state`, PKCE S256, `prompt=select_account`) and the code exchange against Google's token endpoint with `httpx`; validate `iss`, `aud`, `exp`, `email_verified`; never log the code, tokens or secret — `backend/app/auth/google.py`
- [x] T008 `GET /api/auth/google/start` (302 + `state` cookie, refused when disabled) and `GET /api/auth/google/callback` (state compare in constant time, invite-only linking, `finish_sign_in(method="google")`, redirects `/` or `/ingresar`, failures to `/ingresar?google_error=<code>`) — `backend/app/api/oauth.py`
- [x] T009 `/api/config` exposes `google_auth` (public) — `backend/app/api/config.py`
- [x] T010 Audit kinds `google_sign_in`, `google_sign_in_refused`, `google_linked` — `backend/app/services/audit.py`
- [x] T011 Refusal and error messages in both catalogues, keyed by code (never raw provider text) — `backend/app/i18n/es.py`, `backend/app/i18n/en.py`
- [x] T012 Tests: disabled, enabled start, missing/mismatched/replayed state, success + link reuse, unknown email creates **no** user, inactive, locked, domain mismatch, bad `aud`/`exp`/`email_verified`, `internet` admin still needs MFA, password sign-in survives every failure — `backend/tests/test_google_sign_in.py`

## Phase 3: Frontend

- [x] T013 `google_auth` in the public config type and defaults — `frontend/src/config/BrandingContext.tsx`, `frontend/src/api/types.ts`
- [x] T014 "Continuar con Google" button, shown only when enabled, never inside the second-factor step, never replacing the password form; real `<button>`, 44 px target, 320 px safe — `frontend/src/pages/SignIn.tsx`
- [x] T015 `?google_error=<code>` → localised message for every code, generic fallback for an unknown one — `frontend/src/i18n/es.ts`, `frontend/src/i18n/en.ts`
- [x] T016 Tests: absent when disabled, present and navigates to `/api/auth/google/start` when enabled, each error code, both languages, password form still works — `frontend/tests/unit/google-sign-in.test.tsx`

## Phase 4: Operator documentation

- [x] T017 Settings section, off by default, per-installation client, redirect URI, invite-only and secret note — `.env.example`
- [x] T018 Google Cloud console steps, the two behaviours, and troubleshooting (`redirect_uri_mismatch`, consent screen, lock-out safety) — `docs/INSTALL.md`
- [x] T019 Capability row and configuration row — `README.md`
- [x] T020 `### Added` entry under Unreleased, including the constitution amendment — `CHANGELOG.md`
- [x] T021 Third-party paragraph: what is sent (OAuth parameters and the code, no business data) and that it is off by default — `SECURITY.md`

## Phase 5: Gate

- [x] T022 `ruff` + the backend suites; `tsc` + `vitest`; migration up/down/up
- [ ] T023 Commit, push, and note the change in the release notes

## Dependencies

T004/T005 → T006 → T007/T008 → T012. T013 → T014 → T016. T011 is needed by T008's error codes.
T022/T023 last.

## Out of scope (deliberate)

- Creating or promoting users through Google (invite-only by decision, spec "The decision this spec
  takes").
- Other providers (Microsoft, GitHub) — the seams are the same, but each needs its own spec.
- Vendor-held OAuth client for all installations (constitution VII).
