# Implementation Plan: Sales Dashboard for Customers

**Branch**: `001-sales-dashboard` | **Date**: 2026-09-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-sales-dashboard/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A mobile-first sales dashboard for external customer accounts. A Python **integration worker**
(APScheduler, every 30 min + nightly full rebuild) reads the read-only origin database only
through versioned SQL in `custom_queries/` that returns a fixed extract contract, extracting and
validating with **Polars** + ConnectorX (columnar, Rust-backed) for fast loads, and rebuilds
the dashboard's own PostgreSQL models by window replace: an atomic fact table plus daily and
monthly summary tables. A **FastAPI backend** serves pre-aggregated JSON for summary, trend, and
product views (target < 200 ms) and renders PDF exports with ReportLab from the same services.
Sessions are server-side in PostgreSQL behind an HttpOnly cookie; tenant isolation is enforced by
session-scoped repositories plus PostgreSQL Row-Level Security. A **React 19 + Vite + Tailwind**
SPA, served by nginx on the same origin, renders the phone layout first with Recharts. See
[research.md](./research.md) for all decisions.

## Technical Context

**Language/Version**: Python 3.12 (backend, worker); TypeScript 5 on Node 24 (frontend build)

**Primary Dependencies**: FastAPI, Uvicorn, SQLAlchemy 2 (Core + ORM), psycopg 3, Alembic,
Pydantic 2, argon2-cffi, ReportLab, APScheduler 3.x, PyYAML; worker: Polars 1.x, ConnectorX,
PyArrow (fast extraction and transformation, R14); React 19, Vite, Tailwind CSS,
Recharts, Lucide React, react-router 7 (html2canvas stays in the stack, unused by this feature)

**Storage**: PostgreSQL 16 (dashboard-owned; schemas `app`, `mart`, `ops`); origin database
read-only, engine unknown (SQLAlchemy URL + driver extra)

**Testing**: pytest + httpx/TestClient against real PostgreSQL; Vitest + React Testing Library;
Playwright + axe-core at 375 px; Locust; Lighthouse mobile

**Target Platform**: Linux containers via Docker Compose; mobile browsers (iOS Safari 16+,
Android Chrome, last 2 versions), desktop browsers as enhancement

**Project Type**: web application (API + worker + SPA)

**Performance Goals**: API p95 < 200 ms on dashboard endpoints at 200 concurrent users; first
summary view < 2 s on 4G; PDF p95 < 10 s; full rebuild < 5 min for 5 M lines

**Constraints**: origin strictly read-only; worker idempotent and restart-safe; JSON-only API
(PDF download excepted); 375 px usable; WCAG 2.2 AA (screens; PDF per FR-035); data ≤ 60 min
behind origin

**Scale/Scope**: 100 accounts, 1,000 users (200 concurrent), 2,000 products/account, 5 M
historical lines, 20 k new lines/day; 6 customer screens + sign-in/reset; 5 admin endpoints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | Pre-research | Post-design evidence |
|---|---|---|
| I. Mobile-first, Tailwind, readable at 375 px | PASS | Tailwind only; Playwright suite at 375 × 812 with no-horizontal-scroll assertion (quickstart #11) |
| II. API never queries origin; worker builds optimized models; < 200 ms | PASS | Backend has no origin URL; reads `mart` summary tables only (R5, R6); Locust gate (quickstart #12) |
| III. Origin external and read-only; origin SQL isolated | PASS | Read-only user + read-only transaction; SQL only in `custom_queries/` with write-keyword guard ([origin-extract.md](./contracts/origin-extract.md)) |
| IV. `backend/`, `integration/`, `frontend/`, `custom_queries/` | PASS | Structure below; sample origin fixture lives in `integration/` |
| V. Fixed stack (constitution v1.2.0) | PASS | APScheduler (R1), sessions + Argon2id (R2), nginx frontend server (R8), Polars + ConnectorX (R14) are in the constitution; supporting libraries listed with reasons in R10 and Technical Context |
| VI. Summary tables / materialized views | PASS | Summary tables chosen (R5) |
| §3 Origin never written | PASS | Enforced by DB grants and query guard |
| §3 Alembic-only schema changes | PASS | `backend/alembic/` owns all three schemas; worker uses SQL against them, contract-tested |
| §3 Worker idempotent & restart-safe | PASS | Window replace per account in one transaction + advisory lock (R1, R5); quickstart #8 |
| §3 Frontend only calls the API | PASS | nginx proxies `/api` only; no origin credentials in the frontend image |
| §3 All API responses JSON (PDF downloads excepted), no HTML | PASS | Only `POST /api/exports/pdf` returns `application/pdf` (constitution v1.1.0) |
| §3 PDF by backend; html2canvas never the PDF path | PASS | ReportLab vector charts (R9) |
| §4 Quality gates (2 s, 200 ms, 5 min, PDF, findability) | PASS | Mapped to quickstart #1, #6, #12 and structure below (one folder per concern) |

No unjustified violations. Gate passed before and after design.

## Project Structure

### Documentation (this feature)

```text
specs/001-sales-dashboard/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── api.md
│   └── origin-extract.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
docker-compose.yml            # postgres, backend, worker, frontend (+ profiles: dev → origin-sample, mailpit; test → postgres-test)
.env.example                  # all settings, no secrets
db/init/                      # creates roles dash_owner / dash_api / dash_worker on first start

backend/
├── pyproject.toml
├── Dockerfile
├── alembic.ini
├── alembic/versions/         # app, mart, ops schemas + RLS policies
├── app/
│   ├── main.py               # FastAPI app, routers, error handlers, ETag middleware
│   ├── config.py             # settings from env
│   ├── db.py                 # engine, per-request transaction with set_config('app.account_id', …, true)
│   ├── cli.py                # create-admin, seed-demo-accounts
│   ├── auth/                 # passwords.py, sessions.py, lockout.py, tokens.py, routes.py, deps.py
│   ├── domain/               # periods.py (R7), metrics.py (FR-007 math), freshness.py
│   ├── repositories/         # sales.py, products.py, accounts.py, users.py, refresh_runs.py
│   ├── services/             # dashboard.py (summary/trend/products), exports.py, admin.py, mailer.py, audit.py
│   ├── api/                  # me.py, dashboard.py, exports.py, admin.py, health.py
│   └── pdf/                  # report.py, charts.py, fonts/
└── tests/
    ├── unit/                 # periods, metrics, lockout, pdf layout
    └── integration/          # API vs real Postgres, tenant isolation over all routes, PDF = API

integration/
├── pyproject.toml            # extras: mssql, mysql, oracle
├── Dockerfile
├── worker/
│   ├── run.py                # entry: scheduler, or one-shot --full / --incremental
│   ├── scheduler.py          # APScheduler jobs, advisory lock
│   ├── origin.py             # profile loader, write-keyword guard, Polars extraction (ConnectorX / SQLAlchemy fallback)
│   ├── contract.py           # contract schema and version checks
│   ├── transform.py          # Polars: strict casts, row validation, account mapping, local_date per timezone
│   ├── load.py               # COPY Polars frame to staging, window replace into fact
│   ├── aggregate.py          # daily / product daily / product monthly rebuild for dates
│   ├── reconcile.py          # daily_totals comparison
│   ├── alerts.py             # SMTP + webhook
│   ├── housekeeping.py       # audit retention purge, stale running-run cleanup
│   └── check_contract.py     # dry-run validation of a profile
├── sample_origin/            # synthetic origin schema + generate.py (dev/test only)
└── tests/                    # contract, idempotency, restart, reconciliation

custom_queries/
├── README.md                 # = contracts/origin-extract.md
└── sample_postgres/          # manifest.yaml, sale_lines.sql, products.sql, daily_totals.sql

frontend/
├── package.json
├── Dockerfile                # node build → nginx
├── nginx.conf                # SPA fallback, /api proxy, security headers
├── index.html
├── src/
│   ├── main.tsx, App.tsx, router.tsx
│   ├── api/                  # client.ts (fetch + X-Requested-With), useApi.ts, types.ts
│   ├── i18n/                 # es.json (all UI text, Spanish only), useT.ts
│   ├── lib/                  # format.ts (Intl), selection.ts (URL <-> selection)
│   ├── components/           # KpiCard, DeltaBadge, PeriodPicker, CompareToggle, CategoryFilter,
│   │                         # TrendChart, ProductRow, StaleBanner, ExportButton, EmptyState, ErrorRetry
│   └── pages/                # SignIn, ResetPassword, Summary, Trend, Products, ProductDetail
└── tests/
    ├── unit/                 # Vitest
    └── e2e/                  # Playwright 375 px + axe

perf/locustfile.py            # SC-011 load test
```

**Structure Decision**: web application split into the four constitution folders. `backend/` owns
the database schema (Alembic) for all services; `integration/` writes to it with SQL covered by
contract tests; `custom_queries/` is the only place that knows the origin; `frontend/` talks only
to `/api`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. Earlier entries were resolved by /speckit-analyze on 2026-09-28: the PDF response
type by constitution amendment 1.1.0, and the PDF accessibility clause by narrowing FR-035 in the
spec.
