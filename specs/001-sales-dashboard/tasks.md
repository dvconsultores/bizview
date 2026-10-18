---

description: "Task list for Sales Dashboard for Customers"
---

# Tasks: Sales Dashboard for Customers

**Input**: Design documents from `/specs/001-sales-dashboard/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md,
contracts/origin-extract.md, quickstart.md

**Tests**: Included — the plan requires tenant isolation, idempotency, restart safety,
reconciliation, 375 px/axe, and performance checks. Within each story, write tests first and
confirm they fail before implementing.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
demonstrated on its own. Stories are tested with seeded `mart` rows, so they do not depend on
the real origin.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5 from spec.md
- Paths follow plan.md: `backend/`, `integration/`, `custom_queries/`, `frontend/`, `perf/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository skeleton, containers, and tooling

- [ ] T001 Create the folder layout from plan.md (`backend/app/{auth,domain,repositories,services,api,pdf}`, `backend/tests/{unit,integration}`, `integration/worker`, `integration/sample_origin`, `integration/tests`, `custom_queries/sample_postgres`, `frontend/src/{api,i18n,lib,components,pages}`, `frontend/tests/{unit,e2e}`, `db/init`, `perf/`) with a root `.gitignore` excluding `.env`, `.venv/`, `node_modules/`, `dist/`, `.specify/integrations/.cache/`
- [ ] T002 [P] Create `backend/pyproject.toml` (Python ≥3.12; fastapi, uvicorn[standard], sqlalchemy>=2, psycopg[binary]>=3, alembic, pydantic>=2, pydantic-settings, argon2-cffi, reportlab; dev: pytest, httpx, pypdf, ruff, mypy) and `backend/Dockerfile` (python:3.12-slim, non-root user, `uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000`)
- [ ] T003 [P] Create `integration/pyproject.toml` (polars>=1, connectorx, pyarrow, sqlalchemy>=2, psycopg[binary]>=3, apscheduler>=3,<4, pyyaml; extras for the SQLAlchemy fallback engine `mssql`=pyodbc, `mysql`=pymysql, `oracle`=oracledb; dev: pytest, ruff) and `integration/Dockerfile` (entry `python -m worker.run`)
- [ ] T004 [P] Scaffold `frontend/` with Vite + React 19 + TypeScript: `package.json` (react, react-dom, react-router@7, recharts, lucide-react, html2canvas; dev: tailwindcss, @tailwindcss/vite, vitest, @testing-library/react, jsdom, @playwright/test, @axe-core/playwright, eslint, typescript), `vite.config.ts` (proxy `/api` → `http://localhost:8000` in dev), `index.html` with `<meta name="viewport" content="width=device-width, initial-scale=1">`
- [ ] T005 [P] Create `frontend/Dockerfile` (stage 1 `node:24` builds `dist/`; stage 2 `nginx:alpine`) and `frontend/nginx.conf` (SPA fallback to `index.html`, `location /api/ { proxy_pass http://backend:8000; }`, headers: `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`)
- [ ] T006 Create `db/init/01-roles.sql` creating roles `dash_owner`, `dash_api`, `dash_worker` (passwords from env via `psql` variables) and database `dashboard` owned by `dash_owner`
- [ ] T007 Create `docker-compose.yml` with services `postgres` (postgres:16, volume, `db/init` mounted), `backend`, `worker`, `frontend` (port 8080); profile `dev`: `origin-sample` (postgres:16 with `integration/sample_origin` mounted at `/seed`) and `mailpit` (ports 1025/8025); profile `test`: `postgres-test` (tmpfs)
- [ ] T008 [P] Create `.env.example` listing every setting with safe placeholders: `DASH_OWNER_URL`, `DASH_API_URL`, `DASH_WORKER_URL`, `ORIGIN_ENGINE=connectorx`, `ORIGIN_DATABASE_URL` (ConnectorX URI, e.g. `postgresql://origin_ro:…@origin-sample:5432/origin`), `ORIGIN_QUERY_PROFILE=sample_postgres`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `ALERT_EMAILS`, `ALERT_WEBHOOK_URL`, `PUBLIC_BASE_URL`, `REFRESH_INTERVAL_MINUTES=30`, `STALE_AFTER_MINUTES=60`, `FULL_REBUILD_CRON=0 3 * * *`, `COOKIE_SECURE=true`
- [ ] T009 [P] Configure linters: `backend/ruff.toml`, `integration/ruff.toml`, `frontend/eslint.config.js`, plus Tailwind entry `frontend/src/index.css` (`@import "tailwindcss";`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, security, data pipeline, and app shell that every story needs

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Backend core

- [ ] T010 Implement settings in `backend/app/config.py` (pydantic-settings, reads T008 variables; `STALE_AFTER_MINUTES` default 60)
- [ ] T011 Implement `backend/app/db.py`: SQLAlchemy engine for `DASH_API_URL`; FastAPI dependency `get_tx(account_id|None)` that opens a transaction and, when `account_id` is given, runs `SELECT set_config('app.account_id', :id, true)` (transaction-local; plain `SET` cannot take bound parameters); commits/rolls back per request
- [ ] T012 Initialize Alembic in `backend/alembic/` (`alembic.ini` uses `DASH_OWNER_URL`) and write migration `0001_schemas_app.py`: schemas `app`, `mart`, `ops`; extension `citext`; tables `app.customer_account` (name text 1–120 chars, `origin_customer_id text unique not null`, timezone text not null, `currency char(3)`, `is_active default true`, timestamps), `app.app_user` (`email citext unique`, full_name, role in (`customer`,`admin`), account_id FK, password_hash null, is_active, `failed_attempts int default 0`, `locked_until timestamptz`, timestamps, `last_login_at`; CHECK `(role = 'customer') = (account_id IS NOT NULL)`), `app.user_session` (`id_hash bytea PK`, user_id FK on delete cascade, created_at, last_seen_at, user_agent), `app.password_token` (token_hash bytea, purpose in (`set`,`reset`), expires_at, used_at), `app.audit_event` (occurred_at, user_id null, account_id null, kind in (`login_ok`,`login_failed`,`login_locked`,`logout`,`pdf_export`,`password_reset`,`admin_change`), detail jsonb, ip inet)
- [ ] T013 Write migration `backend/alembic/versions/0002_mart_ops.py`: `mart.dim_product` (PK account_id, product_code), `mart.stg_sale_line` (UNLOGGED, extract columns + run_id), `mart.fact_sale_line` (PK `(account_id, document_id, line_no, line_kind)`, index `(account_id, local_date)`, `line_kind in ('sale','return')`, quantity/amounts `numeric(18,4)` ≥ 0), `mart.agg_sales_daily` (PK `(account_id, local_date)`; gross_sales, discounts, returns_value, net_sales, orders int, units_sold, units_returned), `mart.agg_category_daily` (PK `(account_id, category_key, local_date)`, `category_key` = category_code or `''` for uncategorised, same measures), `mart.agg_product_daily` (PK `(account_id, local_date, product_code)`), `mart.agg_product_monthly` (PK `(account_id, month, product_code)`), `ops.refresh_run` (fields per data-model.md; status in (`running`,`succeeded`,`failed`,`skipped`); reconciliation_status in (`ok`,`mismatch`,`not_run`))
- [ ] T014 Write migration `backend/alembic/versions/0003_grants_rls.py`: grants per data-model.md role table; `ENABLE` + `FORCE ROW LEVEL SECURITY` on `mart.dim_product`, `fact_sale_line`, `agg_sales_daily`, `agg_category_daily`, `agg_product_daily`, `agg_product_monthly`; policy for `dash_api` `USING (account_id = current_setting('app.account_id', true)::bigint)`; policy for `dash_worker` `USING (true) WITH CHECK (true)`; revoke all on `mart.stg_sale_line` from `dash_api`; grant `dash_api` INSERT on `ops.rebuild_request` (table created in T085's migration 0004)
- [ ] T015 [P] Implement error model and handlers in `backend/app/main.py` + `backend/app/errors.py`: `{"error": {"code", "message", "fields"}}` with codes `unauthenticated`, `forbidden`, `locked`, `validation_error`, `not_found`, `rate_limited`, `internal`; JSON structured logging to stdout
- [ ] T016 [P] Implement `backend/app/auth/passwords.py` (Argon2id hash/verify with `argon2-cffi`, rehash-if-needed; min length 10)
- [ ] T017 Implement `backend/app/auth/sessions.py`: create session (32 random bytes, store SHA-256 in `id_hash`), cookie `sid` `HttpOnly; Secure (per COOKIE_SECURE); SameSite=Lax; Path=/`, validate with idle expiry `last_seen_at + 7 days` and absolute `created_at + 30 days`, update `last_seen_at` at most every 5 minutes, delete on logout and delete all for a user
- [ ] T018 Implement `backend/app/auth/deps.py`: `current_user`, `require_customer` (returns user + account, 401/403; refuses inactive user or inactive account), `require_admin`; CSRF guard for POST/PATCH/DELETE requiring `X-Requested-With: fetch` and same-site `Origin`
- [ ] T019 Implement `backend/app/auth/lockout.py` and `backend/app/auth/routes.py`: `POST /api/auth/login` (generic 401; after 5 consecutive failures set `locked_until = now + 15 min` and return `423 locked` with `retry_after_seconds`; audit `login_ok`/`login_failed`/`login_locked`), `POST /api/auth/logout` (204, audit `logout`)
- [ ] T020 [P] Implement `backend/app/services/audit.py` (write `app.audit_event`, never storing passwords or tokens) and `backend/app/services/mailer.py` (SMTP via env; no-op + log in tests)
- [ ] T021 Implement `backend/app/api/me.py`: `GET /api/me` per contracts/api.md
- [ ] T022 Implement `backend/app/cli.py`: `create-admin --email` (password prompt), `seed-demo-accounts` (links sample origin customers `C001`–`C003` to accounts with timezone `America/Caracas`, currency `USD`, one user each `demoN@example.test`)
- [ ] T023 [P] Implement `backend/app/api/health.py`: `GET /api/health` → status `ok`/`degraded` (stale), `503` when the database is unreachable, last refresh `finished_at`/`status`/`stale`; no customer data
- [ ] T024 Create test fixtures in `backend/tests/conftest.py`: migrated `postgres-test` database, TestClient, factories for accounts/users/sessions, and `seed_mart(account, rows)` helper inserting `agg_sales_daily`, `agg_product_daily`, `agg_product_monthly`, `dim_product`, and a succeeded `ops.refresh_run`
- [ ] T025 [P] Test auth in `backend/tests/integration/test_auth.py`: login ok/fail, lockout on 5th failure for 15 min, idle (7 days) and absolute (30 days) expiry with frozen time, logout invalidates, inactive user and inactive account refused, CSRF header required

### Domain logic shared by all dashboard views

- [ ] T026 [P] Write unit tests first in `backend/tests/unit/test_periods.py` covering every row of research.md R7: all presets in timezone `America/Caracas`, MTD on the 31st vs a 30-day month and vs February (clipped), leap day YoY (29 Feb → 28 Feb), QTD elapsed days, `last_7_days` ends yesterday, `last_12_months` = 12 complete months, custom span > 3 years → `validation_error`, `from > to` → `validation_error`, clipping to available history sets `clipped: true`, ISO weeks start Monday
- [ ] T027 Implement `backend/app/domain/periods.py`: `resolve_selection(preset, from, to, compare, today_local)` → period, comparison, partial flag, clipped flag; `auto_grain(days)` (day ≤ 31, week ≤ 91, month otherwise); bucket generation for day/week/month
- [ ] T028 [P] Write unit tests first in `backend/tests/unit/test_metrics.py`: net sales, AOV with zero orders → null, `delta_pct` with zero base → null, share of total, decimal rounding to 2 places as strings
- [ ] T029 Implement `backend/app/domain/metrics.py` (FR-007 math on Decimal) and `backend/app/domain/freshness.py` (last succeeded run, `stale` when older than `STALE_AFTER_MINUTES`, data_version = run id)
- [ ] T030 Implement ETag middleware in `backend/app/main.py`: ETag = hash(data_version, path, sorted query) for `GET /api/dashboard/*`, `Cache-Control: private, no-cache`, `304` on `If-None-Match`

### Data pipeline (integration worker)

- [ ] T031 [P] Create the synthetic origin in `integration/sample_origin/schema.sql` (customers, products with categories, invoices with status/completed_at, invoice_lines with gross/discount, returns, return_lines) and `integration/sample_origin/generate.py` (`--customers N --months M`, deterministic seed, includes cancelled invoices, returns, uncategorised products, and sales at 23:30 local time)
- [ ] T032 [P] Write `custom_queries/sample_postgres/manifest.yaml` (`contract_version: 1`, `dialect: postgresql`, `origin_timezone: UTC`) and the three queries `sale_lines.sql`, `products.sql`, `daily_totals.sql` exactly matching contracts/origin-extract.md columns, excluding cancelled invoices; `daily_totals.sql` computed from invoice headers, not lines, grouped by `completed_hour` (hour truncation in UTC)
- [ ] T033 [P] Copy contracts/origin-extract.md into `custom_queries/README.md`
- [ ] T034 Write tests first in `integration/tests/test_contract.py`: missing/extra column → run `failed`; wrong `contract_version` → `failed`; duplicate `(document_id, line_no, line_kind)` → `failed`; currency mismatch, negative amounts, `net_amount` ≠ `gross − discount` (> 0.01) → row rejected and counted; a query containing `UPDATE` is refused before execution; `:window_start`/`:window_end` are replaced only with `'YYYY-MM-DD HH:MM:SS'` literals built from `datetime` values (any other type raises); a result whose Polars schema cannot be cast strictly to the contract types fails the run
- [ ] T035 Implement `integration/worker/origin.py` (profile loader reading `manifest.yaml` and the three SQL files; write-keyword guard for `INSERT|UPDATE|DELETE|MERGE|ALTER|DROP|CREATE|TRUNCATE|GRANT`; parameter substitution with timestamp literals; extraction returning a Polars DataFrame via `pl.read_database_uri(query, ORIGIN_DATABASE_URL, engine="connectorx")`, or `pl.read_database(..., iter_batches=True, batch_size=100_000)` over SQLAlchemy when `ORIGIN_ENGINE=sqlalchemy`) and `integration/worker/contract.py` (column names, strict casts to contract types, `contract_version` check)
- [ ] T036 Write tests first in `integration/tests/test_idempotency.py`: two consecutive incremental runs produce identical `fact_sale_line` and aggregate rows; a cancelled origin invoice inside the window disappears; a sale at 23:30 local counts on that local day; returns reduce net sales and units on the return's day
- [ ] T037 Implement `integration/worker/transform.py` with Polars (duplicate key check via `is_duplicated()` → run fails; vectorised row rejection for currency ≠ account currency, negative quantity/amounts, `|net − (gross − discount)| > 0.01`, with counts and a logged sample; join to linked accounts, dropping unlinked customers; `local_date` = `completed_at` `.dt.replace_time_zone(origin_timezone).dt.convert_time_zone(account_tz).dt.date()`, one timezone group at a time) and `integration/worker/load.py`: per account, one transaction: delete the account's staging rows, `write_csv` the account's frame to an in-memory buffer and `COPY mart.stg_sale_line FROM STDIN (FORMAT csv, HEADER true)` with psycopg on that transaction (not `write_database`), delete `fact_sale_line` rows in the window, insert staged rows; upsert `dim_product` from `products.sql`
- [ ] T038 Implement `integration/worker/aggregate.py`: for the window's dates delete and rebuild `agg_sales_daily` (definitions in data-model.md), `agg_category_daily` (orders = distinct sale documents with a line in the category), `agg_product_daily`, and every month touched in `agg_product_monthly`, inside the same account transaction as T037
- [ ] T039 Write tests first in `integration/tests/test_restart.py`: kill the worker between two accounts → committed accounts intact, the run marked `failed` by the next run, next run `succeeded` and totals equal to a clean run; a second concurrent run exits `skipped` (advisory lock)
- [ ] T040 Implement `integration/worker/scheduler.py` and `integration/worker/run.py` (full rebuild extracted and loaded in calendar-month slices): `pg_try_advisory_lock`; run lifecycle in `ops.refresh_run` (`running` → `succeeded`/`failed`/`skipped`, counts, error text without credentials); mark stale `running` rows as `failed`; APScheduler `BlockingScheduler` with incremental job every `REFRESH_INTERVAL_MINUTES` (window = now − 7 local days → now) and full job on `FULL_REBUILD_CRON`, `coalesce=True`, `max_instances=1`, `misfire_grace_time=600`; CLI flags `--full`, `--incremental`
- [ ] T041 Write tests first in `integration/tests/test_reconcile.py` and implement `integration/worker/reconcile.py`: convert `daily_totals.sql` hourly rows to each account's local date, compare with `agg_sales_daily` per account/day for net sales, orders, units; store `reconciliation_status` and up to 100 `reconciliation_diffs`; `not_run` only for accounts whose offset from `origin_timezone` is not a whole number of hours; test with `America/Caracas` accounts against the UTC sample origin
- [ ] T042 Implement `integration/worker/alerts.py` (SMTP to `ALERT_EMAILS` + optional `ALERT_WEBHOOK_URL` JSON POST) triggered on 2 consecutive failed runs, origin unreachable, or reconciliation `mismatch`; recovery notice on next success; with tests in `integration/tests/test_alerts.py`
- [ ] T043 [P] Implement `integration/worker/housekeeping.py` (delete `app.audit_event` older than 12 months in the nightly job) and `integration/worker/check_contract.py` (runs each query for a 1-day window, validates, writes nothing)
- [ ] T044 Write `backend/tests/integration/test_worker_sql_vs_schema.py`: runs the worker load against a database migrated by Alembic head to prove the worker's SQL matches the schema (constitution §3)

### Frontend shell

- [ ] T045 [P] Implement `frontend/src/api/client.ts` (fetch with `credentials: 'same-origin'`, `X-Requested-With: fetch` on mutations, error parsing to the contract's error model, 401 → redirect to sign-in keeping the current URL) and `frontend/src/api/useApi.ts` (AbortController, retry, keeps last data on failure)
- [ ] T046 [P] Implement Spanish text lookup in `frontend/src/i18n/{es.json,useT.ts}` (all UI strings in `es.json`, no language selection) and formatting in `frontend/src/lib/format.ts` (`Intl.NumberFormat`/`DateTimeFormat` with the locale from `VITE_UI_LOCALE`, default `es`: currency, compact notation for charts, percentages, dates)
- [ ] T047 [P] Implement `frontend/src/lib/selection.ts`: read/write `preset`, `from`, `to`, `compare`, `category` in the URL query string so the selection persists across views (FR-013)
- [ ] T048 Implement `frontend/src/router.tsx` and `frontend/src/App.tsx`: routes `/signin`, `/reset`, `/` (Summary), `/trend`, `/products`, `/products/:code`; mobile layout with bottom tab bar (tap targets ≥ 44 × 44 px), header with account name
- [ ] T049 Implement `frontend/src/pages/SignIn.tsx`: email/password form, generic error, locked message with minutes remaining, redirect back to the original URL

**Checkpoint**: Schema, auth, pipeline, and shell ready — stories can start in parallel

---

## Phase 3: User Story 1 - See my sales summary on my phone (Priority: P1) 🎯 MVP

**Goal**: Signed-in customer sees net sales, orders, units, and AOV for the chosen period with
comparisons and last-updated time, only for their own account.

**Independent Test**: seed one account with known daily rows, sign in at 375 px, verify the four
figures and comparisons for month-to-date match hand-calculated values.

### Tests for User Story 1 ⚠️

- [ ] T050 [P] [US1] Contract test in `backend/tests/integration/test_summary_contract.py`: `GET /api/dashboard/summary` response shape (selection, freshness, measures with decimal strings, `delta_pct` null on zero base, `avg_order_value` null on zero orders) for every preset and both `compare` values
- [ ] T051 [P] [US1] Known-values test in `backend/tests/integration/test_summary_known_values.py`: fixed seed → exact expected figures for `mtd`, `last_month`, `ytd` with `previous` and `yoy`; with a `category` filter, an order containing two products of that category counts once
- [ ] T052 [P] [US1] Tenant isolation test in `backend/tests/integration/test_tenant_isolation.py`: iterate every route in `app.routes` under `/api/dashboard` and `/api/exports`, call as user of account A with account B data seeded, assert no B values appear; also run a raw `SELECT` on each `mart` table as `dash_api` without `app.account_id` set and assert 0 rows (RLS fails closed)
- [ ] T053 [P] [US1] Frontend unit tests in `frontend/tests/unit/Summary.test.tsx`: KPI cards render values, arrow + sign for changes (not colour alone), "new" / "—" for null `delta_pct`, stale banner when `freshness.stale`

### Implementation for User Story 1

- [ ] T054 [US1] Implement `backend/app/repositories/sales.py`: `daily_totals(tx, account_id, from, to, category=None)` summing `agg_sales_daily`, or `agg_category_daily` when `category` is set (never summing product rows for orders); `account_id` is a required positional argument
- [ ] T055 [US1] Implement `summary()` in `backend/app/services/dashboard.py` using periods (T027), metrics (T029), freshness, and the repository
- [ ] T056 [US1] Implement `GET /api/dashboard/summary` in `backend/app/api/dashboard.py` with selection parameter validation per contracts/api.md (preset enum, `from`/`to` required iff `custom`, span ≤ 3 years, `compare` in `previous`,`yoy`)
- [ ] T057 [P] [US1] Implement components `frontend/src/components/{KpiCard,DeltaBadge,StaleBanner,EmptyState,ErrorRetry}.tsx` (DeltaBadge shows arrow icon + signed percentage + accessible label)
- [ ] T058 [P] [US1] Implement `frontend/src/components/PeriodPicker.tsx` (bottom sheet with the 8 presets + custom date range, `to ≥ from`) and `frontend/src/components/CompareToggle.tsx` (`previous` / `yoy`)
- [ ] T059 [US1] Implement `frontend/src/pages/Summary.tsx`: 2 × 2 KPI grid at 375 px, period and comparison labels with resolved dates, "last updated" time, stale banner, empty state "no sales in this period", skeleton loading, retry on error
- [ ] T060 [US1] Playwright test `frontend/tests/e2e/summary.spec.ts` at 375 × 812: sign in as `demo1`, summary visible, change preset and comparison, no horizontal scroll (`document.documentElement.scrollWidth <= 375`), axe has no serious/critical violations

**Checkpoint**: MVP — a customer can sign in and read their headline sales on a phone

---

## Phase 4: User Story 2 - See how my sales move over time (Priority: P2)

**Goal**: Trend chart of net sales / orders / units with comparison overlay and auto grain.

**Independent Test**: seed known daily rows; "Last 12 months" by month returns 12 points equal to
hand-calculated monthly totals; chart readable at 375 px.

### Tests for User Story 2 ⚠️

- [ ] T061 [P] [US2] Contract + known-values test in `backend/tests/integration/test_trend.py`: auto grain (31 days → day, 32 → week, 92 → month), manual grain override, `measure` enum, comparison aligned by bucket position, last bucket `partial: true` when the period includes today, week buckets start Monday
- [ ] T062 [P] [US2] Frontend unit test `frontend/tests/unit/TrendChart.test.tsx`: renders both series, partial bucket styled distinctly, tap shows exact values, accessible data table fallback

### Implementation for User Story 2

- [ ] T063 [US2] Add `bucket_totals(tx, account_id, from, to, grain, category=None)` to `backend/app/repositories/sales.py` (roll up `agg_sales_daily`, or `agg_category_daily` when `category` is set, to day/week/month)
- [ ] T064 [US2] Implement `trend()` in `backend/app/services/dashboard.py` and `GET /api/dashboard/trend` in `backend/app/api/dashboard.py` (params `measure` = `net_sales`|`orders`|`units_sold`, `grain` = `auto`|`day`|`week`|`month`)
- [ ] T065 [US2] Implement `frontend/src/components/TrendChart.tsx` with Recharts (ResponsiveContainer, current vs comparison lines, compact axis labels, tooltip on tap, partial bucket dashed, visually hidden data table for screen readers)
- [ ] T066 [US2] Implement `frontend/src/pages/Trend.tsx` with measure selector and grain selector, sharing the URL selection (T047)
- [ ] T067 [US2] Playwright test `frontend/tests/e2e/trend.spec.ts` at 375 px: switch measure and grain, tap a point, no horizontal scroll, axe clean

**Checkpoint**: US1 and US2 work independently

---

## Phase 5: User Story 3 - See which products drive my sales (Priority: P3)

**Goal**: Ranked products with share and change, search, category filter, product detail.

**Independent Test**: seed product rows; verify top 10 order, shares, totals with category filter,
search across unloaded products, and one product's trend.

### Tests for User Story 3 ⚠️

- [ ] T068 [P] [US3] Contract + known-values test in `backend/tests/integration/test_products.py`: ranking by `net_sales` and `units`, `limit` 1–50 and `offset`, `share_pct` over category-filtered totals, `q` filters list but not totals, accent-insensitive search, monthly + edge-day combination equals pure daily sum, `404` for another account's product code, categories list includes null entry only when uncategorised products exist
- [ ] T069 [P] [US3] Frontend unit test `frontend/tests/unit/Products.test.tsx`: list rows, load more, search debounce, category filter chip

### Implementation for User Story 3

- [ ] T070 [US3] Implement `backend/app/repositories/products.py`: `product_totals(tx, account_id, from, to, category, q, rank_by, limit, offset)` reading whole months from `agg_product_monthly` and edge days from `agg_product_daily`, joined with `dim_product`; `categories(tx, account_id)`; `product(tx, account_id, code)`
- [ ] T071 [US3] Implement `products()`, `product_detail()` in `backend/app/services/dashboard.py` and endpoints `GET /api/dashboard/products`, `GET /api/dashboard/products/{product_code}`, `GET /api/dashboard/categories` in `backend/app/api/dashboard.py`
- [ ] T072 [US3] Implement `frontend/src/components/{ProductRow,CategoryFilter}.tsx` and `frontend/src/pages/Products.tsx` (rank toggle, search input, category chips, 10 rows + "load more")
- [ ] T073 [US3] Implement `frontend/src/pages/ProductDetail.tsx` (product KPIs + TrendChart reuse)
- [ ] T074 [US3] Playwright test `frontend/tests/e2e/products.spec.ts` at 375 px: rank, search, filter, open detail, no horizontal scroll, axe clean

**Checkpoint**: US1–US3 work independently

---

## Phase 6: User Story 4 - Export a PDF summary (Priority: P4)

**Goal**: Backend-generated PDF with the same figures as the screen.

**Independent Test**: export a known period; every figure equals the API response; legible on A4
and Letter.

### Tests for User Story 4 ⚠️

- [ ] T075 [P] [US4] Test `backend/tests/integration/test_pdf_matches_api.py`: extract text from the PDF (`pypdf` dev dependency) and assert customer name, period, comparison basis, last-updated time, the four measures, and top 10 products equal the JSON endpoints for the same selection; empty period produces the "no sales in this period" text; audit `pdf_export` written
- [ ] T076 [P] [US4] Unit test `backend/tests/unit/test_pdf_layout.py`: content fits 190 × 259 mm on both A4 and Letter, document language and title metadata set, text is selectable (not images)

### Implementation for User Story 4

- [ ] T077 [US4] Add Noto Sans fonts to `backend/app/pdf/fonts/` and implement `backend/app/pdf/charts.py` (ReportLab `reportlab.graphics` line chart: current vs comparison, compact labels, AA-contrast colours)
- [ ] T078 [US4] Implement `backend/app/pdf/report.py` (Platypus: header with customer name, period, comparison, generation time, last-updated; KPI table; trend chart + data table; top-10 products table; Spanish labels) using `summary()`, `trend()`, `products()` from `backend/app/services/dashboard.py`
- [ ] T079 [US4] Implement `POST /api/exports/pdf` in `backend/app/api/exports.py` and `backend/app/services/exports.py` (selection body, `application/pdf`, `Content-Disposition` filename with period dates, audit event)
- [ ] T080 [US4] Implement `frontend/src/components/ExportButton.tsx` (POST, progress indicator, non-blocking, download via Blob URL, error retry) and add it to Summary, Trend, and Products pages

**Checkpoint**: US1–US4 work independently

---

## Phase 7: User Story 5 - Provision customer access (Priority: P5)

**Goal**: Administrators create accounts linked to origin customers and manage their users.

**Independent Test**: create an account and a user through the API, set the password from the
email link, sign in and see only that account; deactivate and verify sign-in fails.

### Tests for User Story 5 ⚠️

- [ ] T081 [P] [US5] Test `backend/tests/integration/test_admin.py`: customers get 403 on all `/api/admin/*`; create account (`origin_customer_id` unique → `409`, IANA timezone and ISO 4217 currency validated); add user sends a `set` token (7-day expiry) email; deactivation deletes all sessions; `unlock` clears `locked_until`; timezone change schedules a full rebuild; every change audited as `admin_change`
- [ ] T082 [P] [US5] Test `backend/tests/integration/test_password_tokens.py`: request always `202`; reset token single-use, expires after 30 minutes, stored hashed; weak password (< 10 chars) → `validation_error`

### Implementation for User Story 5

- [ ] T083 [US5] Implement `backend/app/auth/tokens.py` and routes `POST /api/auth/password/request`, `POST /api/auth/password/confirm` in `backend/app/auth/routes.py` (emails link `${PUBLIC_BASE_URL}/reset?token=…`, audit `password_reset`)
- [ ] T084 [US5] Implement `backend/app/repositories/{accounts,users,refresh_runs}.py` and `backend/app/services/admin.py`
- [ ] T085 [US5] Implement admin endpoints in `backend/app/api/admin.py` per contracts/api.md (`GET/POST /api/admin/accounts`, `PATCH /api/admin/accounts/{id}`, `GET/POST /api/admin/accounts/{id}/users`, `PATCH /api/admin/users/{id}`, `GET /api/admin/refresh-runs`); a timezone change inserts a row into `ops.rebuild_request` (table created in migration `backend/alembic/versions/0004_rebuild_request.py`, fields per data-model.md)
- [ ] T086 [US5] Make the worker honour `ops.rebuild_request` in `integration/worker/scheduler.py` (checked at the start of each incremental run; runs a full rebuild for those accounts, then marks them done)
- [ ] T087 [US5] Implement `frontend/src/pages/ResetPassword.tsx` (sets or resets the password from the emailed token; used for both invite and reset)

**Checkpoint**: All five stories functional

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates from the constitution and success criteria

- [ ] T088 [P] Spanish copy review (FR-030): every UI string comes from `frontend/src/i18n/es.json`, and PDF labels in `backend/app/pdf/report.py` plus email templates in `backend/app/services/mailer.py` are in Spanish; add an ESLint rule in `frontend/eslint.config.js` that forbids hard-coded JSX text
- [ ] T089 [P] Session-expiry flow: 401 on any call returns to `/signin?next=<url>` and back after sign-in, in `frontend/src/api/client.ts` + `frontend/src/pages/SignIn.tsx`; Playwright test `frontend/tests/e2e/session.spec.ts`
- [ ] T090 [P] Accessibility pass across pages: text scaling to 200 % without loss, focus order, screen-reader labels for KPI values and charts; Playwright `frontend/tests/e2e/a11y.spec.ts` running axe on every route (SC-012)
- [ ] T091 [P] Load test `perf/locustfile.py`: 200 users across summary/trend/products with realistic preset mix on seed data sized to the clarified scale (100 accounts, 5 M lines); pass criterion p95 < 200 ms (SC-002, SC-011)
- [ ] T092 [P] Lighthouse mobile run script `perf/lighthouse.sh` against the summary page with 4G throttling; pass criterion LCP < 2 s (SC-001)
- [ ] T093 Full-rebuild timing test `integration/tests/test_full_rebuild_timing.py` (marked `slow`): 5 M generated lines complete in < 5 minutes (SC-005) with worker peak memory < 1 GB
- [ ] T094 [P] Write `README.md` at the repository root: architecture diagram (origin → worker → mart → API → SPA), where to find the origin query, transformation, and API route for each metric (constitution §4 findability), and links to quickstart.md
- [ ] T095 Run every scenario in `specs/001-sales-dashboard/quickstart.md` and record results in `specs/001-sales-dashboard/checklists/quickstart-run.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all stories
- **US1–US5 (Phases 3–7)**: each depends only on Foundational
- **Polish (Phase 8)**: after the stories it touches

### User Story Dependencies

- **US1 (P1)**: Foundational only
- **US2 (P2)**: Foundational only (reuses `periods.py`; independent endpoint and page)
- **US3 (P3)**: Foundational only; `ProductDetail` reuses `TrendChart` (T065) — if US2 is not done, T073 includes a minimal chart
- **US4 (P4)**: needs the services of US1–US3 (`summary`, `trend`, `products`) to render the PDF
- **US5 (P5)**: Foundational only (demo accounts come from T022 until then)

### Within Each Story

Tests first (must fail) → repositories → services → endpoints → components → pages → e2e.

### Key task dependencies

- T011 → T012–T014 → T024 → all backend integration tests
- T027 → T055, T064, T071
- T035 → T037 → T038 → T040 → T041/T042
- T045–T048 → every page task

## Parallel Examples

### Phase 2

```text
T015 errors/logging   | T016 passwords   | T020 audit+mailer | T023 health
T026 period tests     | T028 metric tests
T031 sample origin    | T032 sample queries | T033 README
T045 api client       | T046 Spanish text+format | T047 selection
```

### User Story 1

```text
T050 contract test | T051 known values | T052 isolation | T053 frontend unit
T057 KPI components | T058 period picker   (while T054–T056 build the endpoint)
```

### User Story 3

```text
T068 backend tests | T069 frontend tests
T070 repository → T071 endpoints ; in parallel T072 components/page against a mocked API
```

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 → Phase 2 (pipeline running on the sample origin).
2. Phase 3 (US1). **Stop and validate** with quickstart scenarios 1–3 and 8–10.
3. Demo to one pilot customer with their origin profile connected.

### Incremental Delivery

US1 (headline figures) → US2 (trends) → US3 (products) → US4 (PDF) → US5 (self-service admin;
until then accounts are created with the CLI). Each increment ships behind the same deployment.

### Delegation notes (Claude + DeepSeek)

Security-sensitive tasks stay with Claude: T011, T014, T016–T019, T052, T083, T085 (sessions,
RLS, auth, tokens, admin). Candidates for delegation: UI components, repository queries with
known-value tests, PDF layout, sample origin generator.
