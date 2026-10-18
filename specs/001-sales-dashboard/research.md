# Research: Sales Dashboard for Customers

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-28

Decisions taken autonomously with BI-practice defaults, at the user's request. Each entry:
Decision / Rationale / Alternatives considered.

## R1. Worker scheduler (constitution TODO(WORKER_SCHEDULER))

- **Decision**: APScheduler 3.x `BlockingScheduler` in a single `worker` container, with two jobs:
  an *incremental refresh* every 30 minutes and a *full rebuild* nightly at 03:00 (server time).
  A PostgreSQL advisory lock (`pg_try_advisory_lock`) guarantees only one run at a time; a run
  that finds the lock taken exits as `skipped`. Jobs use `coalesce=True`, `max_instances=1`,
  `misfire_grace_time=600`.
- **Rationale**: the workload is one periodic pipeline with no fan-out, so a message broker adds
  a container and failure modes without benefit. The advisory lock gives restart safety even if
  two worker containers start by mistake. 30-minute cadence keeps data ≤ 60 minutes old (SC-004)
  even when a run takes 5 minutes; the stale threshold (2× interval) is 60 minutes (FR-026).
- **Alternatives**: Celery + beat + Redis (rejected: extra broker service, only one task type);
  system cron in the container (rejected: no misfire handling, harder to test); `pg_cron`
  (rejected: runs inside the database, cannot reach the origin cleanly).

## R2. Authentication and session model (constitution TODO(AUTH))

- **Decision**: email + password sign-in handled by the backend. Passwords hashed with
  **Argon2id** (`argon2-cffi`). **Server-side sessions** stored in PostgreSQL; the browser holds
  an opaque random session id in an `HttpOnly; Secure; SameSite=Lax` cookie. Idle timeout 7 days,
  absolute lifetime 30 days (FR-032). Lockout: 5 consecutive failures → 15-minute block
  (FR-033). Password recovery: single-use token (hashed at rest, 30-minute expiry) sent by email
  (FR-005). State-changing requests require the `X-Requested-With: fetch` header and a matching
  `Origin`, which with `SameSite=Lax` blocks CSRF. Roles: `customer` and `admin`.
- **Rationale**: the SPA and API are served from the same origin (see R8), so cookies are the
  simplest secure transport. Server-side sessions allow immediate revocation on sign-out and user
  deactivation (US5 scenario 3), which stateless JWTs cannot do without a denylist. No external
  identity provider is needed for external small-business customers.
- **Alternatives**: JWT access + refresh tokens (rejected: revocation complexity, token storage
  in JS); OAuth2/OIDC with an external IdP (rejected: customers have no shared IdP; adds a
  dependency); magic-link only (rejected: depends on email for every sign-in on phones).

## R3. Tenant isolation (FR-002, SC-007)

- **Decision**: two layers.
  1. Every repository function takes a mandatory `account_id` argument, always taken from the
     session, never from request parameters. No endpoint accepts an account id from a customer.
  2. **PostgreSQL Row-Level Security** on all `mart` tables for the `dash_api` role: policies
     compare `account_id` with `current_setting('app.account_id', true)`, set at the start of
     each request transaction with `SELECT set_config('app.account_id', :id, true)` (the
     transaction-local form of `SET LOCAL`; plain `SET` cannot take bound parameters). The
     worker uses a separate `dash_worker` role with a permissive policy.
- **Rationale**: SC-007 requires zero cross-account leaks; RLS makes a forgotten filter fail
  closed (no rows) instead of leaking. The setting is transaction-scoped, so pooled connections
  cannot carry one customer's setting into another request.
- **Alternatives**: schema-per-customer (rejected: 100 schemas × migrations, harder aggregates for
  operators); application filter only (rejected: a single missed `WHERE` leaks data).

## R4. Origin integration contract (origin engine and schema unknown)

- **Decision**: the worker never embeds origin SQL. It loads named, versioned queries from
  `custom_queries/<profile>/` where `<profile>` is set by `ORIGIN_QUERY_PROFILE`. Each query must
  return an exact column set defined in [contracts/origin-extract.md](./contracts/origin-extract.md)
  and accept named parameters `:window_start` / `:window_end`. The worker validates column names
  and types of every result and fails the run (no partial load) on mismatch. Extraction runs
  through **Polars** (see R14): `ORIGIN_ENGINE=connectorx` (default) reads with ConnectorX from a
  URI such as `postgresql://`, `mysql://`, `mssql://`, or `oracle://`;
  `ORIGIN_ENGINE=sqlalchemy` is the fallback for engines ConnectorX does not support, using a
  SQLAlchemy URL and batched reads. The origin user MUST be read-only at the database level
  (ConnectorX cannot open a read-only transaction), and the worker refuses query files that
  contain write keywords.
- A **`sample_postgres` profile** plus a synthetic sample origin database (compose profile `dev`)
  ship with the project so the whole pipeline runs and is tested before the real origin is known.
- **Rationale**: isolating origin knowledge in SQL files that return a canonical shape is the
  constitution's Principle III and lets a DBA adapt the project to the real origin by writing
  three queries, without touching Python.
- **Alternatives**: ORM models of the origin (rejected: couples code to an unknown schema);
  change-data-capture/replication (rejected: needs write-level access or extra infrastructure on
  a system we do not own).

## R5. Load and transformation strategy

- **Decision**: extract (Polars) → transform (Polars) → staging → fact → aggregates (SQL), in
  one transaction per account:
  1. Write the account's validated Polars frame into `mart.stg_sale_line` (unlogged table) with
     `COPY … FROM STDIN (FORMAT csv)` on the account's transaction.
  2. Delete `mart.fact_sale_line` rows of that account whose `local_date` falls in the window,
     insert the staged rows (**window replace** → idempotent; cancelled or deleted origin rows
     disappear naturally).
  3. Recompute `agg_sales_daily`, `agg_category_daily`, `agg_product_daily`, and affected months of
     `agg_product_monthly` for the window's dates only (`INSERT … ON CONFLICT DO UPDATE` after
     deleting window rows).
  4. Upsert `dim_product` from the products query.
  - Incremental window: the last 7 local days through now (FR-025). Nightly full rebuild: all
    history, same code path, extracted in calendar-month slices so memory stays bounded.
  - Aggregates are **summary tables**, not materialized views.
- **Rationale**: window replace is idempotent and restart-safe (constitution §3): a crash rolls
  back that account's transaction and the next run redoes it. Summary tables can be refreshed
  for a date range; materialized views can only be refreshed whole.
- **Alternatives**: row-level upsert by change timestamp (rejected: needs reliable `updated_at`
  and delete tracking in the origin); materialized views (rejected: full refresh each time).

## R6. Aggregation grain and query performance (<200 ms)

- **Decision**:
  - `agg_sales_daily` (account × local day): net sales, gross sales, discounts, returns value,
    orders, units sold, units returned. All measures are additive because each sale document
    completes on exactly one day, so orders over any range = sum of daily orders; average order
    value is computed at query time.
  - `agg_category_daily` (account × category × day), same measures, so category-filtered
    summaries and trends keep correct orders and average order value (distinct orders cannot
    be summed from product rows).
  - `agg_product_daily` (account × product × day) and `agg_product_monthly` (account × product ×
    month). Product queries read whole months from the monthly table and the partial edge months
    from the daily table.
  - Weeks and months for trends are rolled up from `agg_sales_daily` at query time (≤ 1,100 rows
    per account).
  - Responses carry `ETag` = data version (last successful refresh id) + query hash, with
    `Cache-Control: private, no-cache`, so repeat views revalidate in one round trip.
- **Rationale**: at the clarified scale (100 accounts, ~20 M sparse product-day rows at most) all
  dashboard queries read ≤ 25 k rows via primary-key range scans, well inside 200 ms.
- **Alternatives**: weekly/monthly sales tables (rejected: cheap rollup already); an in-memory
  cache like Redis (rejected: another service, ETag covers repeat views).

## R7. Period and comparison rules (single source of truth)

- **Decision**: the backend resolves every period and comparison; the frontend only sends a
  preset or a custom range. Rules (account timezone, ISO weeks starting Monday):

  | Preset | Range | Previous-period comparison |
  |---|---|---|
  | `today` | today (partial) | yesterday, whole day (today is flagged partial; aggregates are daily, so no same-hour cut-off) |
  | `yesterday` | yesterday | the day before |
  | `last_7_days` | 7 complete days ending yesterday | the 7 days before |
  | `mtd` | 1st of month → today | same day numbers of previous month, clipped to its last day |
  | `last_month` | previous calendar month | the month before it (whole month) |
  | `qtd` | 1st day of quarter → today | same elapsed days of previous quarter |
  | `ytd` | 1 Jan → today | same dates of previous year |
  | `last_12_months` | 12 complete months ending last month | the 12 months before |
  | `custom` | from → to (max 3 years, clipped to history) | same length immediately before |

  Year-over-year comparison: same dates one year earlier (29 Feb → 28 Feb).
  Percentage change with a zero base returns `null` and a `"new"` flag (spec edge case).
- **Rationale**: one implementation guarantees screen and PDF agree (FR-021) and makes the most
  error-prone logic unit-testable.
- **Alternatives**: date logic in the browser (rejected: two implementations, device timezone
  bugs).

## R8. Serving topology

- **Decision**: the `frontend` container is a multi-stage build: Node builds the Vite bundle, and
  **nginx** serves it and reverse-proxies `/api/*` to `backend:8000`. One public origin, so
  cookies need no CORS. TLS terminates at the hosting load balancer (or a Caddy/Traefik sidecar
  in production compose override). `backend`: Uvicorn with 4 workers.
- **Rationale**: same-origin simplifies auth (R2) and matches the constitution's four services.
- **Alternatives**: FastAPI serving static files (rejected: mixes concerns and breaks the
  "frontend container" in the constitution); separate API domain (rejected: CORS + third-party
  cookie issues on mobile Safari).

## R9. PDF generation and accessibility

- **Decision**: `POST /api/exports/pdf` renders synchronously with ReportLab Platypus using the
  same service functions as the JSON endpoints. The trend chart is drawn with
  `reportlab.graphics` (vector), not a browser screenshot. Page content fits the common safe area
  of A4 and US Letter (190 × 259 mm). Fonts: bundled Noto Sans (full Latin coverage for Spanish).
  Metadata sets title, author, subject, and language.
- **PDF accessibility (FR-035)**: open-source ReportLab does not produce *tagged* PDF (PDF/UA).
  Resolved by /speckit-analyze: FR-035 now requires, for the PDF, real selectable text, logical
  reading order, AA contrast, the trend as a data table, and title/language metadata; PDF/UA is
  out of scope for this release (possible later post-processing step).
- **html2canvas**: not needed by any requirement in this feature; kept in the stack for future
  client-side chart snapshots and never used for the PDF (constitution §3).
- **Alternatives**: headless-browser PDF (rejected: violates constitution, heavy); WeasyPrint
  (rejected: not the constitution's PDF library).

## R10. Frontend supporting libraries (not stack changes)

- **Decision**: TypeScript; `react-router` 7 for the five screens and URL-encoded filters
  (period, compare, category stay in the URL → FR-013 and deep links); formatting via the
  browser `Intl` API with one configurable Spanish locale (`UI_LOCALE`, default `es`) for
  numbers, currency, dates, and compact "1,2 M"; all interface text in one Spanish dictionary
  (`es.json`) with a small lookup hook, so strings are not hard-coded and a later language is
  cheap to add. No language selection (Spanish only, FR-030). No data-fetching or
  state library: a small `useApi` hook with abort + retry.
- **Rationale**: the constitution fixes frameworks; these are minimal supporting libraries or
  none. Keeping period state in the URL makes back/refresh behave and survives session expiry
  redirect (spec edge case).
- **Alternatives**: TanStack Query, i18next, date-fns (rejected for now: not needed at this size).

## R11. Observability and alerting (FR-027, FR-034)

- **Decision**: JSON structured logs to stdout from all services. `ops.refresh_run` records every
  run; `GET /api/health` returns status and the last successful refresh. The worker sends an
  alert (SMTP email to `ALERT_EMAILS`, and optional `ALERT_WEBHOOK_URL`) when two consecutive runs
  fail or the origin is unreachable, and a recovery notice on the next success.
- **Rationale**: meets operational readiness with the email transport already required for
  password recovery.
- **Alternatives**: Prometheus/Grafana stack (rejected for v1: extra services; health endpoint
  can be scraped later).

## R12. Reconciliation (SC-003)

- **Decision**: after each run, the worker executes the contract query `daily_totals` (origin
  totals per customer per completion **hour** in the window, converted by the worker to each
  account's local day, so accounts in any whole-hour timezone are reconciled) and compares net sales, orders, and units
  with `agg_sales_daily`. Differences are stored on the run (`reconciliation_status`,
  `reconciliation_diffs`) and trigger an alert; the data is still published.
- **Rationale**: accuracy is the first trust factor of a BI product; automated reconciliation
  turns SC-003 into a continuous check instead of a one-off test.

## R13. Testing stack

- **Decision**: backend and worker: `pytest`, FastAPI `TestClient`/`httpx`, a real PostgreSQL
  from the compose `test` profile. Frontend: Vitest + React Testing Library; Playwright e2e at
  375 × 812 with `@axe-core/playwright` (FR-035, SC-009, SC-012) and a no-horizontal-scroll
  assertion. Performance: Locust (200 users, SC-011) and Lighthouse mobile profile (SC-001).
- **Rationale**: tests run against the same database engine as production; isolation tests
  iterate every registered route (SC-007).

## R14. Extraction and transformation engine: Polars

- **Decision**: the worker uses **Polars** (1.x) for extraction and transformation.
  - **Extract**: `pl.read_database_uri(query, uri, engine="connectorx")`. ConnectorX is written
    in Rust, reads straight into Arrow memory, and avoids building a Python object per row. The
    fallback engine uses `pl.read_database(query, connection, iter_batches=True,
    batch_size=100_000)` over SQLAlchemy.
  - **Parameters**: ConnectorX takes no bound parameters, so the worker replaces `:window_start`
    and `:window_end` with timestamp literals (`'YYYY-MM-DD HH:MM:SS'`). The values are always
    `datetime` objects the worker computes itself, never user input. Query files wrap them in the
    engine's cast (see [contracts/origin-extract.md](./contracts/origin-extract.md)).
  - **Transform** (`integration/worker/transform.py`): enforce the contract schema with strict
    casts; `is_duplicated()` on the line key (run fails); vectorised row checks for currency,
    negative values, and `net = gross − discount` (rows rejected and counted); join to linked
    accounts, dropping unlinked customers; compute `local_date` per account timezone with
    `dt.replace_time_zone(origin_tz).dt.convert_time_zone(account_tz).dt.date()`, processing one
    timezone group at a time; convert reconciliation hours to local dates the same way.
  - **Load**: `write_csv` into an in-memory buffer, then psycopg `COPY` on the account's
    transaction. Polars' `write_database` is not used because it opens its own connection, which
    would break the one-transaction-per-account guarantee (R5).
  - **Aggregates** stay as set-based SQL inside PostgreSQL (R5, R6), so they are rebuilt from
    `fact_sale_line` in the same transaction and never leave the database.
  - **Memory**: a full rebuild is processed month by month (~620 k lines per month at the
    clarified volume), so the worker stays well under 1 GB.
- **Rationale**: at 5 M historical lines, row-by-row extraction through a Python DB driver
  dominates the 5-minute budget (SC-005). A columnar read plus vectorised validation cuts
  extraction and validation to seconds, and the checks are much simpler to express as expressions
  over whole columns.
- **Alternatives**: pandas (rejected: slower and heavier in memory for the same work); plain
  SQLAlchemy row streaming (kept only as the fallback engine); doing the transformation in
  origin SQL (rejected: puts business rules in the system we do not own and duplicates them per
  dialect); aggregating in Polars (rejected: would move fact rows out of and back into
  PostgreSQL and lose the single transaction).

