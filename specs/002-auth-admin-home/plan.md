# Implementation Plan: Platform Foundation — Sign-in, User Administration and Dashboard Home

**Branch**: `002-auth-admin-home` | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-auth-admin-home/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

The first deliverable code of the product: a secured, branded, mobile-first shell that every
dashboard plugs into. A **FastAPI** backend owns its tables in schema `public` of the BI database (`DATABASE_URL_BI`)
(`DATABASE_URL_BI`) through **Alembic** migrations that never touch the existing `public.bi_*`
tables. It provides email/password sign-in with **Argon2id** hashes and **server-side sessions**
(HttpOnly cookie), lockout, a super user bootstrapped from `SUPER_USER_EMAIL` /
`SUPER_USER_PASSWORD`, user administration with a two-level permission model, a dashboard
catalogue with per-user grants, and an audit log. A **React 19 + Vite + Tailwind 3.4** SPA in a
blue design system renders sign-in, home (dashboard cards), profile/password, and administration,
phone layout first, targeting iOS 14+ and the last two versions of every major browser. **Caddy**
is the single edge: it serves the SPA, proxies `/api`, and provides automatic HTTPS. See
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5 on Node 24 (frontend build)

**Primary Dependencies**: FastAPI, Uvicorn, SQLAlchemy 2, psycopg 3, Alembic, Pydantic 2,
pydantic-settings, argon2-cffi; React 19, Vite, react-router 7, lucide-react, Tailwind CSS 3.4 +
PostCSS + Autoprefixer; Caddy 2

**Storage**: PostgreSQL 15 — `DATABASE_URL_BI` (database `bizview`), standard schema `public` (5 tables);
tables untouched

**Testing**: pytest + TestClient on `DATABASE_URL_BI` in a temporary `app_test_*` schema; Vitest; Playwright
(Chromium, Firefox, WebKit) + axe-core at 320/375 px; bundle compatibility check

**Target Platform**: Linux containers (Docker Compose: `caddy`, `backend`); browsers per FR-027

**Project Type**: web application (API + SPA behind an edge proxy)

**Performance Goals**: sign-in < 1 s server time (Argon2 dominated); other API calls p95 < 200 ms;
home visible < 2 s after sign-in on 4G (JS+CSS < 150 kB gzip)

**Constraints**: autogenerate limited to the product's own tables; JSON-only API; WCAG 2.2 AA; 320 px without
horizontal scroll; no customer-specific values in code

**Scale/Scope**: up to 1,000 users per deployment; 7 screens (sign-in, change password, home,
dashboard gate, profile, users list, user detail/new) + audit list; 15 endpoints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | Pre-research | Post-design evidence |
|---|---|---|
| I. Mobile-first, Tailwind, 375 px | PASS | Tailwind only; phone layout first, bottom nav on phones, Playwright at 320/375 px (quickstart #12) |
| II. API never queries origin; worker builds models | PASS (n/a) | This feature has no origin access; no sales data |
| III. Origin external and read-only | PASS (n/a) | No origin connection configured in backend |
| IV. Folders `backend/`, `integration/`, `frontend/`, `custom_queries/` | PASS | Uses `backend/`, `frontend/`; adds `deploy/` for infrastructure (research R1); reports stay in `backend/app/reports/` |
| V. Fixed stack | **AMEND** → PASS | nginx replaced by Caddy as the edge (user request) — constitution amended to **1.3.0** before implementation (below). Tailwind version is a supporting detail (3.4 for browser support, R8). No database container: the BI database (and the test database) are always external |
| VI. Summary tables | PASS (n/a) | |
| §Constraints: Alembic-only schema changes | PASS | `backend/alembic/` owns the product tables in `public`; version table `public.alembic_version` |
| §Constraints: JSON-only API | PASS | All `/api` responses JSON; SPA served by Caddy |
| §Constraints: frontend calls only the API | PASS | Caddy proxies `/api/*` only |
| §Quality gates: 2 s on 4G, 200 ms API | PASS | Budgets in Technical Context; no data endpoints yet |

Gate passes after amendment 1.3.0 (V: nginx → Caddy; container list: `caddy`, `backend`,
`worker`, PostgreSQL provided by the deployment). No other violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-auth-admin-home/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/api.md     # Phase 1
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
docker-compose.yml             # caddy, backend (database is always external)
.env.example                   # every setting, no secrets
.gitignore, .dockerignore
README.md                      # folder map (front/back/etl/report → folders), run, deploy

deploy/
├── caddy/
│   ├── Caddyfile              # SPA + /api proxy + headers + auto TLS via {$SITE_ADDRESS}
│   └── Dockerfile             # node build of frontend/ → caddy:2-alpine
└── branding/                  # default logo; mounted at /branding (override per customer)

backend/
├── pyproject.toml, Dockerfile, entrypoint.sh, alembic.ini
├── alembic/
│   ├── env.py                 # DATABASE_URL_BI; default schema public; only the models' tables
│   └── versions/0001_app_auth.py, 0002_dashboards.py
├── app/
│   ├── main.py                # app factory, routers, error handlers, CSRF middleware
│   ├── config.py              # pydantic-settings
│   ├── db.py                  # engine, session-per-request dependency
│   ├── errors.py              # ApiError + envelope
│   ├── models.py              # SQLAlchemy ORM (default schema public)
│   ├── cli.py                 # bootstrap, reset-superuser-password
│   ├── auth/                  # passwords.py, sessions.py, deps.py
│   ├── services/              # users.py (permission rules R6), dashboards.py, audit.py
│   ├── api/                   # health.py, config.py, auth.py, me.py, dashboards.py, admin.py
│   └── reports/               # reserved for feature 001 PDF reports (ReportLab)
└── tests/                     # conftest + safety (app_test_* schema guard), test_migrations, test_auth,
                               # test_me, test_admin_matrix, test_dashboards, test_bootstrap

frontend/
├── package.json, vite.config.ts, tailwind.config.js, postcss.config.js, tsconfig.json
├── index.html                 # viewport, theme-color, noscript
├── public/favicon.svg
├── scripts/check-compat.mjs   # fails on APIs missing in Safari 14
├── src/
│   ├── main.tsx, App.tsx, index.css
│   ├── api/client.ts          # fetch wrapper, error envelope, X-Requested-With
│   ├── auth/AuthContext.tsx   # me, login, logout, guards
│   ├── i18n/es.ts
│   ├── lib/password.ts, format.ts, icons.ts
│   ├── components/            # AppShell, TopBar, BottomNav, SideNav, Button, Input,
│   │                          # PasswordField, Card, Badge, Alert, Spinner, EmptyState, Modal, Toast
│   └── pages/                 # SignIn, ChangePassword, Home, DashboardGate, Profile,
│                              # admin/Users, admin/UserForm, admin/UserDetail, admin/Audit, NotFound
└── tests/                     # unit (vitest), e2e (playwright)

integration/, custom_queries/  # created by feature 001 (ETL); reserved
```

**Structure Decision**: constitution folders plus `deploy/` (research R1). The user's "report"
maps to `backend/app/reports/` and "etl" to `integration/` + `custom_queries/`; both are filled by
feature 001.

## Relationship to feature 001

Feature 001's plan (tasks T010–T025, T045, T048–T049) planned sign-in, sessions, lockout, and an
admin role. This feature delivers them first, with these differences that 001 must adopt when it
is implemented (to be reconciled by `/speckit-analyze` on 001):

- Roles are `admin` / `user` (+ super user) instead of `admin` / `customer`; 001 adds
  `customer_account` and a nullable `account_id` on `app_user`, required for users who read
  sales.
- Emails are normalised `text`, not `citext` (no extensions in the shared BI database).
- The edge is Caddy (constitution 1.3.0), not nginx.
- The database is the BI database from `DATABASE_URL_BI`, not a compose-managed PostgreSQL.

## Complexity Tracking

No unjustified violations. The only deviation (Caddy instead of nginx) is resolved by constitution
amendment 1.3.0 instead of being tracked here.
