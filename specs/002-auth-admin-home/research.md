# Research: Platform Foundation — Sign-in, User Administration and Dashboard Home

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-29

Decisions taken autonomously with the recommended best practice, at the user's request. Each
entry: Decision / Rationale / Alternatives considered. Where feature 001 already decided a topic
(research R2, R8, R10, R13 there), this feature reuses the decision and delivers it first.

## R1. Folder layout (user asked: front, backend, report, etl)

- **Decision**: keep the constitution's folders and add one for deployment:

  | User's name | Folder | Why this name |
  |---|---|---|
  | front | `frontend/` | constitution IV; same name as feature 001 |
  | backend | `backend/` | constitution IV |
  | etl | `integration/` + `custom_queries/` | the ETL worker and the origin SQL it runs; kept apart so a DBA edits SQL without Python (constitution III, IV) |
  | report | `backend/app/reports/` | PDF reports are rendered by the backend from the same services as the JSON API (constitution: "PDF by the backend with ReportLab"); a top-level folder would split them from the code they depend on |
  | — | `deploy/` | Caddy edge (Caddyfile, image build), compose overrides, branding assets — infrastructure is not application code |

  Feature 002 creates `backend/`, `frontend/`, `deploy/`; `integration/` and `custom_queries/`
  are created by feature 001 and are only reserved here.
- **Rationale**: one folder per deployable or per owner. Reports are a feature of the backend
  service, not a separate runtime; the ETL is a separate runtime (its own container and
  schedule). The constitution's findability gate ("origin query, transformation, API route in
  under one minute each") holds.
- **Alternatives**: renaming `integration/` to `etl/` (rejected: constitution MAJOR amendment and
  churn across all of feature 001's plan for a naming preference; the README maps the names);
  top-level `report/` (rejected, see above); monorepo `apps/` + `packages/` (rejected: two
  languages, no shared packages yet — overhead without benefit).

## R2. Edge server: Caddy replaces nginx (constitution amendment 1.3.0)

- **Decision**: one `caddy` service (image `caddy:2-alpine`) is the only public entry point:
  - serves the built SPA from `/srv` with `try_files {path} /index.html` (client-side routes);
  - `reverse_proxy /api/* backend:8000`, forwarding the real client IP;
  - automatic HTTPS (Let's Encrypt/ZeroSSL, auto-renew) when `SITE_ADDRESS` is a domain; plain
    HTTP on `:80` when it is `:80` (local / behind another TLS terminator);
  - `encode zstd gzip`; `Cache-Control: public, max-age=31536000, immutable` for hashed
    `/assets/*`, `no-cache` for `index.html`;
  - security headers: CSP `default-src 'self'; img-src 'self' data:; style-src 'self'
    'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`, HSTS (only
    when TLS), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
    `Permissions-Policy` denying camera/mic/geolocation; `-Server` header removed;
  - serves `/branding/*` from a mounted folder (per-customer logo, R9).
  The image is built by `deploy/caddy/Dockerfile`: stage 1 `node:24-alpine` builds `frontend/`,
  stage 2 copies `dist/` and the `Caddyfile` into `caddy:2-alpine`. Certificates persist in the
  `caddy_data` volume.
- **Rationale**: the user asked for Caddy. It removes a second proxy (nginx + separate TLS
  terminator in 001's R8) because it does automatic TLS itself, and its config is a dozen lines.
  Same-origin serving is kept, so the cookie session needs no CORS.
- **Alternatives**: Caddy in front of an nginx frontend container (rejected: two proxies for
  static files); Traefik (rejected: label-driven config is heavier for one site); FastAPI serving
  static files (rejected: constitution concern split).

## R3. Authentication and sessions (reuses 001 R2)

- **Decision**: email + password; **Argon2id** hashes (`argon2-cffi` defaults, RFC 9106
  low-memory profile; rehash when parameters change); **server-side sessions** in
  `app.user_session`, the browser holds a random 32-byte id (base64url) in cookie `sid`
  (`HttpOnly; SameSite=Lax; Path=/; Secure` when `COOKIE_SECURE=true`); only the SHA-256 of the id
  is stored. Idle 7 days / absolute 30 days; `last_seen_at` written at most every 5 minutes.
  Lockout: 5 consecutive failures → `locked_until = now + 15 min`, reset on success. Unknown
  emails still run one Argon2 verify against a fixed dummy hash so response time does not reveal
  whether an email exists.
- **CSRF**: `SameSite=Lax` + every `POST/PUT/PATCH/DELETE` requires header
  `X-Requested-With: fetch` (a cross-site form cannot set it; a cross-site `fetch` with it
  triggers a CORS preflight that the API never approves) + `Origin`, when present, must equal
  `PUBLIC_BASE_URL`.
- **Temporary passwords**: `must_change_password = true` after creation or admin reset; while
  set, every API route except `GET /api/me`, `POST /api/me/password`, `POST /api/auth/logout`,
  `GET /api/config` answers `403 password_change_required` (enforced on the server, not only by
  the UI — FR-014).
- **Rationale**: immediate revocation (deactivation, password reset) needs server-side sessions;
  same-origin behind Caddy makes cookies the simplest safe transport.
- **Alternatives**: JWT (rejected: revocation needs a denylist, token in JS storage); OAuth/OIDC
  (rejected: out of scope, no IdP).

## R4. Super-user bootstrap and recovery (FR-007 – FR-009)

- **Decision**: a CLI in the backend image, run by the container entrypoint before Uvicorn:
  `alembic upgrade head` → `python -m app.cli bootstrap` → `exec uvicorn …`.
  `bootstrap` reads `SUPER_USER_EMAIL` / `SUPER_USER_PASSWORD`:
  - missing or invalid (FR-015 rules) and no super user exists → exit code 1 with the setting
    name (container fails to start);
  - no super user and no user with that email → create it (`role=admin`, `is_superuser=true`,
    `must_change_password=false`), audit `superuser_created`;
  - no super user but the email belongs to a user → promote it and set the configured password,
    audit `superuser_promoted`;
  - super user exists → do nothing (the stored password wins; a different configured email is
    logged as a warning).
  Recovery: `docker compose exec backend python -m app.cli reset-superuser-password` sets the
  configured password on the existing super user, clears lockout, deletes its sessions, audits
  `superuser_recovered`. A partial unique index `ON app.app_user ((true)) WHERE is_superuser`
  guarantees exactly one super user.
  `bootstrap` also deletes audit events older than 12 months (FR-023) until feature 001's worker
  housekeeping job takes it over.
- **Rationale**: an explicit command is predictable; a "reset on every start" env flag would
  silently overwrite a password changed in the interface. Running it before Uvicorn avoids races
  between Uvicorn workers.
- **Alternatives**: bootstrap inside FastAPI `lifespan` (rejected: runs once per worker, races);
  env flag `SUPER_USER_RESET=true` (rejected: easy to leave on).

## R5. Database: `DATABASE_URL_BI`, standard schema `public`, Alembic

- **Decision** (user decision 2026-09-29, replacing the earlier dedicated `app` schema): connect
  with `DATABASE_URL_BI` (normalised to the `postgresql+psycopg://` driver URL in config). The
  product's tables live in the database's standard schema **`public`**; no schema is hard-coded
  in models or migrations, and Alembic's version table is the default `public.alembic_version`.
  `DATABASE_URL_BI` points at a database dedicated to the product (`bizview`), so `public` holds
  only the product's tables. `include_object` limits autogenerate to the tables defined in
  `app/models.py`, so any other table present in a deployment's database is never altered or
  dropped. No extensions are installed: emails are stored normalised (`lower(btrim())`, enforced
  by a CHECK) with a plain unique constraint instead of `citext`.
- **History**: first deployed on 2026-09-29 to database `bi` in schema `app`; the user then
  pointed `DATABASE_URL_BI` at the new database `bizview` and asked for the standard `public`
  schema, so the `app` schema in `bizview` was dropped and the migrations re-applied in `public`.
- **Rationale**: standard layout for a product that owns its database; simplest to operate and
  to connect BI tools to. SC-007 (idempotent setup) still holds.
- **Dedicated DB role**: recommended for production — a role that owns the product's tables
  instead of the `postgres` superuser in `DATABASE_URL_BI`. Not enforced by this feature because
  the operator controls the database.
- **Alternatives**: dedicated schema `app` (used first; replaced at the user's request);
  `citext` (rejected: installs an extension).

## R6. Authorisation model (FR-009, FR-012, FR-013, FR-019)

- **Decision**: roles `admin` and `user`, plus the `is_superuser` flag (always `admin`). Rules,
  enforced in one service module (`services/users.py`) and tested as a matrix:

  | Action on target → | regular user | administrator | super user | self |
  |---|---|---|---|---|
  | create / edit name / reset password / (de)activate | admin, super | super | — (own password only via profile) | own name/password via profile only |
  | change role | admin → no; super → yes | super | — | — |
  | grant dashboards | admin, super | not needed (sees all) | not needed | — |

  Admin routes return `403 forbidden` for regular users, and `404 not_found` for unknown ids.
- **Rationale**: a clear two-level hierarchy with an untouchable super user; nobody can lock
  themselves out.

## R7. Dashboard catalogue

- **Decision**: table `app.dashboard` seeded by migrations (the catalogue ships with releases,
  FR-018); first row `ventas` / "Ventas" / icon `chart-line` / status `coming_soon` / route
  `/d/ventas`. Grants in `app.dashboard_access (user_id, dashboard_id)`. Access rule:
  `status <> 'hidden'` and (user is admin or a grant exists); opening needs
  `status = 'available'`. The frontend route `/d/:code` asks `GET /api/dashboards/{code}` first
  and renders "No autorizado" / "Próximamente" from its answer; each future dashboard API also
  calls the same `require_dashboard(code)` dependency, so typed URLs are refused server-side.
- **Rationale**: data-driven catalogue means the home page never changes when a dashboard is
  added; feature 001 flips `ventas` to `available` in its own migration.

## R8. Frontend stack and browser support (FR-025 – FR-029)

- **Decision**: React 19, Vite, TypeScript, react-router 7 (declarative `BrowserRouter` mode),
  lucide-react, **Tailwind CSS 3.4** with PostCSS + Autoprefixer, `browserslist`
  `> 0.3%, last 2 versions, iOS >= 14, Safari >= 14, Android >= 8, not dead, not ie 11`, Vite
  `build.target = ['es2020', 'safari14', 'chrome87', 'firefox78', 'edge88']`. System font stack
  (no web-font download). No state or data library: a small `api` client + `useAuth` context.
  All texts in `src/i18n/es.ts`.
- **Why Tailwind 3.4, not 4**: Tailwind 4 relies on `@property`, `color-mix()` and cascade
  layers and officially needs Safari 16.4+ / Chrome 111+; FR-027 requires iOS 14. 3.4 compiles to
  plain CSS those browsers support. (The constitution names Tailwind without a version.)
- **Verification of "all browsers"**: after build, a check fails if the bundle uses APIs missing
  in Safari 14 (`structuredClone`, `Array.prototype.at`, `Object.hasOwn`, `findLast`) without a
  polyfill; Playwright runs the flows in Chromium, Firefox, and WebKit at 320 px and 375 px.
- **Alternatives**: `@vitejs/plugin-legacy` (rejected: needs inline scripts → weaker CSP, and
  ES2020 already covers the target list); Tailwind 4 (rejected, above).

## R9. Visual design and branding (FR-026, FR-030)

- **Decision**: a blue design system via CSS variables consumed by Tailwind theme tokens:
  `brand-50…950` (Tailwind blue scale, primary `#2563eb` / hover `#1d4ed8`, deep `#172554` for
  the sign-in hero and the app bar), neutrals from `slate`, success/danger from `emerald`/`rose`
  always paired with an icon and text. Sign-in: full-height gradient hero (`#1e3a8a → #2563eb`)
  with the logo and product name, form card below on phones / side by side on ≥ 1024 px. App
  shell: sticky top bar with product name and avatar menu; bottom navigation on phones (Inicio,
  Administración for admins, Perfil), left sidebar on ≥ 1024 px. Cards with 16 px radius, 44 px
  minimum targets, visible `focus-visible` rings, `prefers-reduced-motion` respected.
  Branding comes from `GET /api/config` (`PRODUCT_NAME`, `ORGANIZATION_NAME`, `LOGO_URL` pointing
  to `/branding/<file>` served by Caddy from `deploy/branding/` or a mounted folder); the HTML
  `<title>` is updated at runtime. Colour tokens as variables make a future per-customer primary
  colour a config change.

## R10. API conventions (reuses 001 error model)

- **Decision**: JSON only under `/api`; errors `{"error": {"code", "message", "fields"}}` with
  codes `unauthenticated` (401), `invalid_credentials` (401), `locked` (423 +
  `retry_after_seconds`), `password_change_required` (403), `forbidden` (403), `not_found` (404),
  `conflict` (409), `validation_error` (422), `csrf_failed` (403), `internal` (500). Pydantic v2
  models; FastAPI's own 422 is re-shaped into the same envelope. Messages in Spanish. OpenAPI docs
  disabled in production (`DOCS_ENABLED=false`).
- Client IP for audit comes from `X-Forwarded-For` set by Caddy; Uvicorn runs with
  `--proxy-headers --forwarded-allow-ips=*` since the port is only reachable on the compose
  network.

## R11. Testing

- **Decision**: backend `pytest` + FastAPI `TestClient` on **`DATABASE_URL_BI`**, the
  same database the migrations target (user decision 2026-09-29), but inside a temporary schema
  `app_test_<random>` selected with `DB_SCHEMA` and redirected by SQLAlchemy's
  `schema_translate_map`; it is created, migrated, and dropped by each run. The suite snapshots
  schema `public` before the run and asserts it is unchanged after it. No
  database container and no separate test database;
  the suite runs Alembic up/down/up to prove repeatable migrations, and a test creates fake
  `public.bi_*` tables first and asserts they are untouched (SC-007). Authorisation matrix test
  iterates every `/api/admin/*` route as a regular user (SC-003). Frontend: Vitest for the
  password-rule helper and API client; Playwright (Chromium, Firefox, WebKit) at 320 and 375 px
  with `@axe-core/playwright` for sign-in, home, profile, and admin (SC-005, SC-006).
- **Rationale**: same engine version as production; the shared BI database is never a test
  target.

## R12. Runtime configuration

- **Decision**: one `.env` per deployment (`.env.example` committed, `.env` git-ignored):
  `DATABASE_URL_BI`, `SUPER_USER_EMAIL`, `SUPER_USER_PASSWORD`, `PRODUCT_NAME`,
  `ORGANIZATION_NAME`, `LOGO_URL`, `SITE_ADDRESS` (`:80` or a domain), `PUBLIC_BASE_URL`,
  `COOKIE_SECURE`, `HTTP_PORT`/`HTTPS_PORT`, `DOCS_ENABLED`, `LOG_LEVEL`. Feature 001's settings
  (origin, worker) are added by 001. Backend image runs as a non-root user; Uvicorn 2 workers.
- **Rationale**: SC-008 — a new customer is a new `.env` and branding folder, no code change.
