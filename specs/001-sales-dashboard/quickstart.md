# Quickstart & Validation: Sales Dashboard for Customers

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Runs the whole system against the bundled synthetic origin, then walks through the checks that
prove each user story. Commands assume the repository root.

## Prerequisites

- Docker with Compose v2.
- Node.js 24 and Python 3.12 only for running tests outside containers.
- A copy of `.env.example` as `.env` (never committed). Defaults point at the sample origin:
  `ORIGIN_QUERY_PROFILE=sample_postgres`, `ORIGIN_ENGINE=connectorx`,
  `ORIGIN_DATABASE_URL=postgresql://origin_ro:…@origin-sample:5432/origin`.

## 1. Start the stack with the sample origin

```bash
cp .env.example .env
docker compose --profile dev up -d --build          # postgres, backend, worker, frontend, origin-sample
docker compose exec backend alembic upgrade head
docker compose exec origin-sample python /seed/generate.py --customers 3 --months 27   # synthetic history
docker compose exec backend python -m app.cli create-admin --email admin@example.test
docker compose exec backend python -m app.cli seed-demo-accounts   # links the 3 sample customers, 1 user each
docker compose exec worker python -m worker.run --full              # first full load
```

Expected: the worker prints a `succeeded` run with `reconciliation_status=ok`; the full load
takes < 5 minutes at the default seed size (SC-005).

## 2. Validation scenarios

| # | Story / requirement | How | Expected |
|---|---|---|---|
| 1 | US1, FR-007/008 | Open `http://localhost:8080` in a 375 × 812 device emulator, sign in as `demo1@example.test` | Summary for month-to-date with 4 figures and previous-period changes; "last updated" visible |
| 2 | US1, FR-009/010 | Switch presets and "vs last year" | Figures and comparison dates change; values match `pytest backend/tests/integration/test_summary_known_values.py` fixtures |
| 3 | US1 sc.4, SC-007 | `pytest backend/tests/integration/test_tenant_isolation.py` | Every route returns only the signed-in account's data; 0 failures |
| 4 | US2 | Trend for "Last 12 months" | Monthly grain, 12 points + comparison, current bucket not partial |
| 5 | US3 | Products view, rank by units, search, category filter | Ranking, shares, and totals follow [contracts/api.md](./contracts/api.md) rules |
| 6 | US4, FR-021 | Export PDF from the summary | PDF opens, figures equal the screen; `pytest backend/tests/integration/test_pdf_matches_api.py` passes |
| 7 | US5 | `POST /api/admin/accounts/{id}/users`, set password from the emailed link (Mailpit at `http://localhost:8025`), then deactivate | New user signs in; after deactivation the session is gone and sign-in fails |
| 8 | FR-024/025, constitution §3 | Run `python -m worker.run` twice; kill it mid-run once (`docker compose kill worker`) and restart | Row counts identical after each run; no duplicates; interrupted run marked `failed`, next run `succeeded` |
| 9 | FR-026/034 | Stop `origin-sample`, wait for 2 runs (or run twice manually) | Runs `failed`, alert email in Mailpit, dashboard shows stale notice after 60 min (use `STALE_AFTER_MINUTES=1` to test quickly) |
| 10 | SC-003 | Edit an order in the sample origin inside the 7-day window, run worker | Dashboard reflects the change; reconciliation `ok` |
| 11 | FR-028, FR-035, SC-009, SC-012 | `cd frontend && npx playwright test` | 375 px layout, no horizontal scroll, axe finds no serious/critical issues |
| 12 | SC-001/002/011 | `locust -f perf/locustfile.py --users 200` and Lighthouse mobile on the summary | API p95 < 200 ms; first view < 2 s on the 4G profile |

## 3. Test suites

```bash
docker compose --profile test up -d postgres-test
cd backend && pytest                 # unit + integration (periods, metrics, auth, isolation, PDF)
cd integration && pytest             # contract validation, idempotency, restart, reconciliation
cd frontend && npm test && npx playwright test
```

## 4. Connecting the real origin

1. Get a **read-only** database user for the origin.
2. Copy `custom_queries/sample_postgres/` to `custom_queries/<origin_name>/` and rewrite the three
   queries to the shapes in [contracts/origin-extract.md](./contracts/origin-extract.md).
3. Set `ORIGIN_QUERY_PROFILE`, `ORIGIN_ENGINE` (`connectorx`, or `sqlalchemy` if ConnectorX
   does not support the engine), and `ORIGIN_DATABASE_URL` in `.env`; for the fallback, install the driver extra
   (`pip install ".[mssql]"` etc. in the worker image).
4. `docker compose exec worker python -m worker.check_contract` — runs each query for a 1-day
   window and validates the columns without writing anything.
5. Run a full load and confirm `reconciliation_status=ok`.
