---
description: "Task list for feature 002 — Platform Foundation"
---

# Tasks: Platform Foundation — Sign-in, User Administration and Dashboard Home

**Input**: Design documents from `/specs/002-auth-admin-home/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: included — the user asked for an audit-and-test pass, and SC-003/SC-005/SC-007 require
automated checks.

**Execution mode** (user request): Claude designs and audits, DeepSeek drafts selected files,
Claude reviews, corrects, and tests everything before a task is checked.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on unfinished tasks)
- **[Story]**: US1 sign-in & home, US2 administer users, US3 own password, US4 dashboard access,
  US5 per-customer deployment

---

## Phase 1: Setup

- [X] T001 Create folders `backend/app/{auth,services,api,reports}`, `backend/alembic/versions`, `backend/tests`, `frontend/src/{api,auth,i18n,lib,components,pages/admin}`, `frontend/tests/{unit,e2e}`, `frontend/scripts`, `deploy/caddy`, `deploy/branding`; root `.gitignore` (`.env`, `.venv/`, `node_modules/`, `dist/`, `__pycache__/`, `.pytest_cache/`, `test-results/`, `playwright-report/`) and `.dockerignore`
- [X] T002 [P] Create `backend/pyproject.toml` (Python ≥3.12; fastapi, uvicorn[standard], sqlalchemy>=2, psycopg[binary]>=3, alembic, pydantic>=2, pydantic-settings, argon2-cffi, email-validator; dev: pytest, httpx, ruff) and `backend/Dockerfile` (python:3.12-slim, non-root user, `entrypoint.sh`: `alembic upgrade head && python -m app.cli bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips='*'`)
- [X] T003 [P] Scaffold `frontend/` (Vite + React 19 + TS): `package.json` (react, react-dom, react-router@7, lucide-react; dev: vite, @vitejs/plugin-react, typescript, tailwindcss@3.4, postcss, autoprefixer, vitest, jsdom, @playwright/test, @axe-core/playwright), `vite.config.ts` (`build.target: ['es2020','safari14','chrome87','firefox78','edge88']`, dev proxy `/api` → `http://localhost:8000`), `tsconfig.json`, `postcss.config.js`, `browserslist` in package.json `"> 0.3%, last 2 versions, iOS >= 14, Safari >= 14, Android >= 8, not dead, not ie 11"`
- [X] T004 [P] Create `.env.example` with every setting of research R12 (placeholders only) and keep `.env` untouched
- [X] T005 [P] Create `deploy/caddy/Caddyfile` per research R2 (`{$SITE_ADDRESS::80}`; `encode zstd gzip`; `handle /api/*` → `reverse_proxy backend:8000`; `handle_path /branding/*` → `root /branding` + `file_server`; `handle` → `root /srv`, `try_files {path} /index.html`, `file_server`; `@assets path /assets/*` → immutable cache; `index.html` → `no-cache`; security headers incl. CSP `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`; `-Server`) and `deploy/caddy/Dockerfile` (stage `node:24-alpine` `npm ci && npm run build` in `frontend/`; stage `caddy:2-alpine` copies `dist/` → `/srv`, Caddyfile → `/etc/caddy/Caddyfile`)
- [X] T006 Create `docker-compose.yml`: `backend` (build `backend/`, `env_file: .env`, healthcheck `GET /api/health`), `caddy` (build context `.`, dockerfile `deploy/caddy/Dockerfile`, ports `${HTTP_PORT:-8080}:80`, `${HTTPS_PORT:-8443}:443`, env `SITE_ADDRESS`, volumes `caddy_data`, `caddy_config`, `./deploy/branding:/branding:ro`, depends_on backend healthy); no database service (databases are always external)

---

## Phase 2: Foundational (blocks all stories)

- [X] T007 Implement `backend/app/config.py` (pydantic-settings reading `.env` from repo root or env: `database_url_bi` normalised to `postgresql+psycopg://`, `super_user_email`, `super_user_password`, `product_name` default "Bizview AI Powered", `organization_name` default "", `logo_url` default None, `public_base_url`, `cookie_secure` default true, `docs_enabled` default false, `log_level`)
- [X] T008 Implement `backend/app/db.py` (engine `pool_pre_ping`, pool_size 5; `get_db` dependency yielding a `Session`, commit on success, rollback on error)
- [X] T009 Implement `backend/app/models.py`: SQLAlchemy 2 ORM in the default schema `public` exactly per data-model.md — `AppUser` (email text unique, CHECK `email = lower(btrim(email))`, CHECK role in (`admin`,`user`), CHECK `NOT is_superuser OR role = 'admin'`, CHECK `is_active OR NOT is_superuser`, partial unique index `uq_app_user_single_superuser ON ((true)) WHERE is_superuser`, `must_change_password` default true, `failed_attempts` default 0, `locked_until`, `last_login_at`, `password_changed_at`, `created_at`, `updated_at`, `created_by` FK), `UserSession` (`id_hash` bytea PK, user_id FK ON DELETE CASCADE, created_at, last_seen_at, user_agent, ip inet), `Dashboard` (code unique `^[a-z][a-z0-9-]{1,39}$`, name, description ≤ 200, icon, sort_order default 100, status CHECK in (`available`,`coming_soon`,`hidden`)), `DashboardAccess` (PK user_id+dashboard_id, granted_by, granted_at), `AuditEvent` (kind CHECK in the 16 kinds of data-model.md, actor_id, target_id, ip inet, detail jsonb default `{}`)
- [X] T010 Initialise Alembic: `backend/alembic.ini`, `backend/alembic/env.py` (URL from config; default schema `public`, version table `public.alembic_version` then commit before `context.configure(version_table_schema="app", include_schemas=True, include_object=` only objects in schema `app`)`)
- [X] T011 Write migration `backend/alembic/versions/0001_app_auth.py` (`app_user`, `user_session`, `audit_event` with every CHECK and index above; downgrade drops them and `DROP SCHEMA app` only if empty besides `alembic_version` — leave schema)
- [X] T012 Write migration `backend/alembic/versions/0002_dashboards.py` (`dashboard`, `dashboard_access`, seed `('ventas','Ventas','Resumen, tendencias y productos de tus ventas.','chart-line',10,'coming_soon')`; downgrade drops both)
- [X] T013 [P] Implement `backend/app/errors.py` (`ApiError(status, code, message, fields=None, extra=None)`, handlers producing `{"error": {...}}`, re-shape FastAPI `RequestValidationError` into `validation_error` with `fields`, 500 → `internal` without details)
- [X] T014 [P] Implement `backend/app/auth/passwords.py` (Argon2id hash/verify/needs_rehash; `validate_new_password(pw, email, current=None)` returning error code `too_short` <10, `too_long` >128, `contains_email` when it equals the email or contains the part before "@" (case-insensitive, local part ≥ 3 chars), `same_as_current`; `DUMMY_HASH` for timing equalisation)
- [X] T015 Implement `backend/app/auth/sessions.py` (create: `secrets.token_urlsafe(32)`, store `sha256`; lookup with idle 7 d / absolute 30 d expiry, delete expired, touch `last_seen_at` if older than 5 min; delete one / delete all for user / delete all except current; cookie set/clear helpers `sid`, HttpOnly, SameSite=Lax, Secure per config, max-age 30 d)
- [X] T016 Implement `backend/app/services/audit.py` (`record(db, kind, actor_id, target_id, ip, detail)`; assert no key containing `password`, `hash`, `token`, `sid` in detail) and `purge_older_than(db, months=12)`
- [X] T017 Implement `backend/app/auth/deps.py`: `client_ip(request)` (first `X-Forwarded-For` entry, else peer), `current_session` (401 `unauthenticated`), `current_user` (also 403 `password_change_required` when `must_change_password`), `current_user_allow_temp`, `require_admin`, `require_superuser`
- [X] T018 Implement `backend/app/main.py`: app factory, CSRF middleware (POST/PUT/PATCH/DELETE under `/api` require `X-Requested-With: fetch` → else 403 `csrf_failed`; `Origin` when present must match `PUBLIC_BASE_URL` scheme+host), routers, error handlers, docs only when `DOCS_ENABLED`, JSON logging, `Cache-Control: no-store` on `/api` responses
- [X] T019 [P] Implement `backend/app/api/health.py` (`GET /api/health`, `SELECT 1` → ok / 503) and `backend/app/api/config.py` (`GET /api/config`)
- [X] T020 Implement `backend/app/cli.py` (`bootstrap` and `reset-superuser-password` per research R4, exit 1 with the setting name on missing/invalid config; purge expired sessions and audit > 12 months)
- [X] T021 Create `backend/tests/conftest.py`: uses `DATABASE_URL_BI` with a temporary schema `app_test_<random>` (`DB_SCHEMA`, guarded by `backend/tests/safety.py`), snapshots schemas `app`/`public` and asserts them unchanged after the run, drops the test schema at the end, runs `alembic upgrade head`, TestClient with `X-Requested-With: fetch` default header, factories `make_user(role, password, **kw)`, `login(client, email, pw)`
- [X] T022 [P] Test migrations in `backend/tests/test_migrations.py`: upgrade → downgrade → upgrade works; only the product tables are created (in `public`) gains objects; `public.bi_ventas` structure and row count unchanged; second `upgrade head` is a no-op (SC-007)
- [X] T023 [P] Frontend foundation: `frontend/tailwind.config.js` (content globs, `brand` = blue scale via CSS variables, font = system stack), `frontend/src/index.css` (tailwind layers, `:root` colour variables, `focus-visible` ring, reduced motion), `frontend/index.html` (lang `es`, viewport `width=device-width, initial-scale=1, viewport-fit=cover`, `theme-color #1e3a8a`, `<noscript>` Spanish message), `frontend/public/favicon.svg`
- [X] T024 [P] Implement `frontend/src/api/client.ts` (`api.get/post/patch/put` with `credentials:'same-origin'`, `X-Requested-With: fetch`, JSON, throws `ApiError{status, code, message, fields, retryAfter}`; network failure → code `network`) and `frontend/src/i18n/es.ts` (all UI strings)
- [X] T025 [P] Implement UI kit in `frontend/src/components/`: `Button` (variants primary/secondary/ghost/danger, `loading` disables + spinner, min-h 44 px), `Input` (label, hint, error with `aria-describedby`/`aria-invalid`), `PasswordField` (show/hide toggle), `Card`, `Badge`, `Alert` (`role="alert"` / `status`, icon + text), `Spinner`, `EmptyState`, `Modal` (focus trap, Esc), `Toast` provider (`aria-live="polite"`)
- [X] T026 Implement `frontend/src/auth/AuthContext.tsx` (`me` loaded from `GET /api/me`, `login`, `logout`, `refresh`; `RequireAuth` redirects to `/ingresar?next=` with same-origin path only; `RequireAdmin`; users with `must_change_password` redirected to `/cambiar-clave`) and `frontend/src/config/BrandingContext.tsx` (loads `/api/config`, sets `document.title`)
- [X] T027 Implement `frontend/src/components/AppShell.tsx` (sticky top bar with logo/product name and avatar menu; bottom nav on < 1024 px with Inicio / Administración (admins) / Perfil; left sidebar on ≥ 1024 px; safe-area insets; skip link) and `frontend/src/App.tsx` routes: `/ingresar`, `/cambiar-clave`, `/`, `/d/:code`, `/perfil`, `/admin/usuarios`, `/admin/usuarios/nuevo`, `/admin/usuarios/:id`, `/admin/auditoria`, `*`

**Checkpoint**: migrations applied on a test database, app boots, shell renders.

---

## Phase 3: User Story 1 — Sign in and reach the home page (P1) 🎯 MVP

**Goal**: super user signs in and sees the dashboard catalogue.
**Independent Test**: quickstart #1–#4.

- [X] T028 [P] [US1] Tests in `backend/tests/test_auth.py`: login ok sets cookie and `last_login_at`; wrong password / unknown email / inactive user → identical 401 body; 5th failure → 423 with `retry_after_seconds` ≈ 900 and correct password refused while locked; success resets count; logout deletes session; idle 7 d and absolute 30 d expiry (manipulate timestamps); missing `X-Requested-With` → 403 `csrf_failed`; email `" Ana@Example.com "` matches `ana@example.com`
- [X] T029 [P] [US1] Tests in `backend/tests/test_bootstrap.py`: creates super user; idempotent; stored password wins after config change; missing/weak password with no super user → exit 1; existing user email promoted; `reset-superuser-password` resets, clears lockout, deletes sessions; audit rows written
- [X] T030 [US1] Implement `backend/app/api/auth.py` (`POST /api/auth/login` with timing-equalised verify, lockout, rehash, session + cookie, audit `login_ok`/`login_failed`/`login_locked`; `POST /api/auth/logout`) and `GET /api/me` in `backend/app/api/me.py`
- [X] T031 [US1] Implement `backend/app/services/dashboards.py` (`visible_for(user)`, `get_for_open(user, code)` → 404 / 403 `forbidden` / 403 `coming_soon`) and `backend/app/api/dashboards.py` (`GET /api/dashboards`, `GET /api/dashboards/{code}`)
- [X] T032 [US1] Implement `frontend/src/pages/SignIn.tsx`: gradient blue hero with logo + product + organisation, card form (email `autocomplete=username`, `inputmode=email`; password `current-password`), generic error, locked message with minutes, busy button, redirect to `next`
- [X] T033 [US1] Implement `frontend/src/pages/Home.tsx` (greeting with first name and date, dashboard cards grid 1 col → 2 → 3, icon, status badge, "Próximamente" disabled card, empty state text from spec US4-1, loading skeleton, retry on error) and `frontend/src/pages/DashboardGate.tsx` (`/d/:code` → calls `GET /api/dashboards/{code}`, shows No autorizado / Próximamente / placeholder "Este tablero se habilitará pronto")
- [X] T034 [US1] Implement `frontend/src/pages/NotFound.tsx` and sign-out in the avatar menu

---

## Phase 4: User Story 2 — Administer users (P2)

**Goal**: super user / admins manage users. **Independent Test**: quickstart #5–#8.

- [X] T035 [P] [US2] Tests in `backend/tests/test_admin_matrix.py`: permission matrix of research R6 for create/edit/role/deactivate/reset over targets {user, admin, super user, self} × actors {user, admin, super}; duplicate email any case → 409; deactivation ends sessions; reset ends sessions + clears lock + sets temp; every `/api/admin/*` route (enumerated from `app.routes`) returns 403 for a regular user (SC-003); each action writes exactly one audit event (SC-009)
- [X] T036 [US2] Implement `backend/app/services/users.py` (`can_manage(actor, target, action)` single source of the R6 matrix; create, update, set_active, reset_password, list with q/role/status/limit/offset)
- [X] T037 [US2] Implement `backend/app/api/admin.py` user routes (`GET/POST /api/admin/users`, `GET/PATCH /api/admin/users/{id}`, `POST /api/admin/users/{id}/password`) per contracts/api.md
- [X] T038 [US2] Implement `frontend/src/pages/admin/Users.tsx` (search with debounce, role/status filter chips, cards on phones and table ≥ 768 px, status badges with text, "Nuevo usuario" FAB on phones)
- [X] T039 [US2] Implement `frontend/src/pages/admin/UserForm.tsx` (create: email, full name, role select (admin option only for super user), temporary password with "Generar" button and copy-to-clipboard, rule hints) and `frontend/src/pages/admin/UserDetail.tsx` (edit name, role (super only), activate/deactivate with confirm modal, reset password modal, info: last sign-in, created)

---

## Phase 5: User Story 3 — Change my own password (P3)

**Independent Test**: quickstart #10.

- [X] T040 [P] [US3] Tests in `backend/tests/test_me.py`: change ok → other sessions deleted, current kept, flag cleared; wrong current → 401 + counts to lockout; each rule → 422 field code; while `must_change_password` every non-allowed route → 403 `password_change_required`
- [X] T041 [US3] Implement `POST /api/me/password` in `backend/app/api/me.py`
- [X] T042 [P] [US3] Implement `frontend/src/lib/password.ts` (mirror of server rules + strength hint) with `frontend/tests/unit/password.test.ts`
- [X] T043 [US3] Implement `frontend/src/pages/ChangePassword.tsx` (forced mode for temporary passwords: no nav except sign out; current, new, confirm; live rule checklist) and `frontend/src/pages/Profile.tsx` (name, email, role, link to change password, sign out)

---

## Phase 6: User Story 4 — Control dashboard access (P4)

**Independent Test**: quickstart #9.

- [X] T044 [P] [US4] Tests in `backend/tests/test_dashboards.py`: user without grants → empty list; grant → visible; `coming_soon` → 403 `coming_soon` on open; revoke → 403 `forbidden`; admin sees all non-hidden; hidden never listed for anyone; unknown code → 404; `PUT` with unknown code → 422; grants to admin target → 422
- [X] T045 [US4] Implement `GET /api/admin/dashboards` and `PUT /api/admin/users/{id}/dashboards` in `backend/app/api/admin.py` (diff-based audit `dashboard_granted`/`dashboard_revoked`)
- [X] T046 [US4] Add dashboard access switches to `frontend/src/pages/admin/UserDetail.tsx` (toggle list with status badges; admins show "Acceso a todos los tableros")

---

## Phase 7: User Story 5 — Deploy for a new customer (P5)

**Independent Test**: quickstart #13–#14.

- [X] T047 [US5] Audit endpoint `GET /api/admin/audit` (super only, keyset paging) in `backend/app/api/admin.py` and `frontend/src/pages/admin/Audit.tsx` (list with kind labels in Spanish, filters by kind)
- [X] T048 [P] [US5] Default branding: `deploy/branding/logo.svg` (neutral blue mark, no customer name); `LOGO_URL` defaults to none so the product name renders as a text logo
- [X] T049 [US5] Write `README.md` (folder map for front/backend/etl/report, run, deploy for a new customer, recovery, production DB role recommendation)

---

## Phase 8: Polish & Verification

- [X] T050 [P] `frontend/scripts/check-compat.mjs` (scan `dist/assets/*.js` for `structuredClone(`, `.at(` on arrays is not detectable → check `Array.prototype.at`, `Object.hasOwn`, `.findLast(`, `.replaceAll(` — fail with file and match) and `npm run check:compat`
- [X] T051 [P] Playwright suite `frontend/tests/e2e/flows.spec.ts` + `playwright.config.ts` (projects chromium, firefox, webkit × viewports 320 and 375; against the compose stack; sign-in, home, profile, admin list; no horizontal scroll assertion; axe 0 serious/critical)
- [X] T052 Run backend suite, frontend unit tests, build, compat check; fix findings
- [X] T053 Apply migrations to the BI database (`DATABASE_URL_BI`) and verify: tables created in `public` of `bizview`, `public.bi_*` row counts unchanged, super user bootstrapped
- [X] T054 Bring up `docker compose` stack, run quickstart scenarios 1–12 end to end, run Playwright; record results
- [X] T055 Security audit pass over diff (auth, CSRF, headers, secrets in logs, permission matrix) and mark tasks complete

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → stories. US1 first (MVP). US2 needs US1's login for tests. US3 and US4
  depend only on Phase 2 + US1 and can run in parallel with US2. US5 is last.
- Within stories: tests → service → routes → UI.

## Parallel Opportunities

- T002/T003/T004/T005 in parallel; T013/T014/T019/T023/T024/T025 in parallel.
- US1: T028 ∥ T029; US3: T040 ∥ T042; frontend pages of different stories in parallel once
  T025–T027 exist.

## Implementation Strategy

MVP = Phases 1–3 (super user signs in, sees catalogue). Then US2 (make the product usable for
others), US3, US4, US5, polish. Each checkpoint runs the backend suite.
