# Implementation Plan: Google button branding and role mapping

**Branch**: `054-google-signin-rbac` | **Date**: 2026-11-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/054-google-signin-rbac/spec.md`

## Summary

Two halves, one screen and one card. **Branding**: the sign-in page gets a real *Sign in with Google*
control — the official four-colour G as an inline SVG in both light and dark variants, the catalogue
label, matched with the Telegram button. **Access**: the installation gains a policy for Google
sign-ins — allowed domains editable in Administración → Seguridad (initialised from
`GOOGLE_ALLOWED_DOMAINS`), optional auto-provisioning with a default role and dashboard access, and an
ordered list of rules (first match wins) that can decide the role and access of a Google account,
applied to existing users only when an admin asks for it. The provider switch and the secrets stay
where they are, and superusers stay out of reach.

## Technical Context

**Language/Version**: Python 3.13 (FastAPI + SQLAlchemy 2, Alembic) and TypeScript 5 + React 19 (Vite)

**Primary Dependencies**: existing only — `httpx` (Google exchange), `argon2` via
`app.auth.passwords`, FastAPI deps (`require_superuser`, `recent_reauth`), Tailwind tokens; the SVG is
written by hand, no icon or OAuth library is added

**Storage**: PostgreSQL — two new tables (`google_settings`, `google_rule`), `app_user` gains
`auth_provider` and a nullable `password_hash`; grants reuse `dashboard_access`

**Testing**: `pytest` (backend, temp schema), `npx vitest run` (jsdom), Playwright (the Google flow via
a test hook), `npx tsc -b`, `npm run build`

**Target Platform**: the product's web app and its API; mobile-first

**Performance Goals**: one extra settings read and one rule pass per callback (bounded by 50 rules);
no query per dashboard beyond the materialised grant insert

**Constraints**: secrets untouched and never returned; generic sign-in messages; audit every change;
no schema change that invalidates an installation's audit history

**Scale/Scope**: 1 screen (sign-in), 1 admin card, 2 tables, 1 migration, ~6 audit kinds, 8 endpoints
(2 settings + 6 rules incl. reorder), 1 test hook

## Constitution Check

| Principle | Gate | How this feature satisfies it |
| --- | --- | --- |
| I. Mobile-First | the sign-in screen is designed at 375 px first | 44 px targets, full-width buttons, the card stacks |
| II. Backend as ETL | untouched | no data path change |
| III. Source of Truth Is External | untouched | no source or artifact change |
| IV. Separated Concerns | `app/api` routes, `app/services` policy, `frontend/src` UI | the rule engine lives in a service, not in the route |
| V. Fixed Technology Stack | no auth library, no icon package; the Auth contract | inline SVG, the existing exchange. The Auth bullet bounded Google sign-in as *invite-only* (amendment 2.1.0, feature 027); provisioning and rules expand it, so principle V is **amended** to 3.3.0 by this feature (Sync Impact Report in the constitution) — see T029 |
| VII. One Product, Many Installations | everything is data in the installation | domains, defaults and rules are rows; the env value is only the seed |
| VIII. AI Is Optional and Private | untouched | no AI involved |
| IX. Spec-Driven Reporting | untouched | no report or project change |

No violation, and one amendment: principle V's **Auth** bullet stopped bounding Google sign-in as
invite-only, because the second half of this specification is exactly what that clause forbade. The
amendment keeps every bound that still holds (off by default, per-installation OAuth client, opt-in per
attempt, the `internet` profile's second factor, password sign-in unchanged) and adds the two the
product needed: opt-in automatic sign-up on the allowed domains — never a superuser, no password — and
an ordered rule list that may decide role and access, never for superusers and never for existing
accounts unless the installation asks for it. Nothing to justify in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/054-google-signin-rbac/
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0: what exists, the data model, the callback's order
├── quickstart.md      # Phase 1: gates and manual checks
└── tasks.md           # Phase 2
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0051_google_rbac.py     # app_user columns, the two tables, audit vocabulary
├── app/models.py                            # AppUser.auth_provider/password_hash NULL, GoogleSettings,
│                                            # GoogleRule, AUDIT_KINDS
├── app/services/google_policy.py            # NEW: normalise, read/write settings, evaluate rules,
│                                            # provision, apply to existing, materialise grants
├── app/api/google_admin.py                  # NEW: /api/admin/google (+ /rules, /rules/reorder)
├── app/api/oauth.py                         # domain check → policy; provision; rules; audit details
├── app/api/auth.py                          # password sign-in refuses an account with no hash
├── app/api/testhooks.py                     # google identity override for the e2e flow
├── app/i18n/{es,en}.py                      # messages for the card and the callback
└── tests/
    ├── test_google_rbac.py                  # NEW: settings, rules, provisioning, existing users
    ├── test_google_sign_in.py               # extend: generic message, provisioned flow
    └── test_migrations.py                   # the two tables reach APP_TABLES
frontend/
├── src/components/GoogleSignInButton.tsx    # NEW: the official mark, light and dark
├── src/components/GoogleAdminCard.tsx       # NEW: the Seguridad card
├── src/pages/SignIn.tsx                     # brand button, Telegram matched, generic message
├── src/pages/admin/Security.tsx             # the card
├── src/api/{types,sources}.ts               # the settings and rule types + calls
├── src/i18n/{es,en}.ts                      # labels
└── tests/unit/google-signin-button.test.tsx # NEW: logo, both themes, hidden when off
```

**Structure Decision**: the policy (normalisation, rule evaluation, provisioning) sits in
`app/services/google_policy.py` so the callback, the admin endpoints and the tests share one
implementation; the card is a self-contained component the security page mounts, following
`TelegramAdminCard`.

## Phase 0 — Research (see [research.md](./research.md))

The callback's current order, where `password_hash` is assumed, the audit vocabulary's migration
pattern, how the security page mounts a card, and how the e2e backend provides test hooks.

## Phase 1 — Design

- `GoogleSettings` (singleton `id=1`): `allowed_domains jsonb` (list of normalised domains),
  `auto_provision bool`, `default_role text` in (`user`,`admin`), `default_access jsonb`
  (`{"mode":"none"|"all_public"|"list","codes":[...]}`), `apply_rules_to_existing bool`,
  `updated_at`, `updated_by`.
- `GoogleRule`: `id`, `position int` (0-based, contiguous), `condition text` in
  (`domain`,`email`,`group`), `value jsonb` (list of strings; `domain` carries exactly one),
  `role text` in (`user`,`admin`), `access jsonb`, `enabled bool` default true, `created_at`,
  `updated_at`, `updated_by`; index on `position`.
- API contract:
  - `GET /api/admin/google` → `{settings, dashboards: [{code, name}]}`
  - `PUT /api/admin/google` → the saved settings (step-up, audited)
  - `GET /api/admin/google/rules` → `{items}`
  - `POST /api/admin/google/rules`, `PUT /api/admin/google/rules/{id}`,
    `DELETE /api/admin/google/rules/{id}`, `PUT /api/admin/google/rules/reorder` (`{ids}`)
- Callback order (in `_sign_in`): link by subject → user by email (link) → provision → refuse; then
  rules: new users get the first matching rule over the defaults; existing users get them only with
  `apply_rules_to_existing`, and only when the outcome differs.

## Phases

| Phase | Work |
| --- | --- |
| 1 | Data model + migration + audit vocabulary |
| 2 | `google_policy` service: normalise, settings, rules, evaluate, provision, grants |
| 3 | Admin API + validation + audit |
| 4 | Callback: generic refusals, provisioning, rules; password sign-in without a hash |
| 5 | Frontend: Google button, Telegram matched, generic error, the Seguridad card |
| 6 | i18n, help topic, `.env.example`, CHANGELOG |
| 7 | Tests: backend flows, unit button/card, e2e through the test hook |

## Verification

- `cd backend && uv run pytest tests/test_google_rbac.py tests/test_google_sign_in.py tests/test_auth.py tests/test_migrations.py -q`
- `cd frontend && npx tsc -b && npx vitest run`
- `cd frontend && npm run build`
- The colour gate (`no-raw-colors`) green with the logo's documented exception.
- e2e: `report`-style hook flow for provisioning → role change → next sign-in keeps the admin role.
