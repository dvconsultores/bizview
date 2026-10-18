# Implementation Plan: Faster PostgreSQL extraction

**Branch**: `008-fast-pg-extraction` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-fast-pg-extraction/spec.md`

## Summary

For PostgreSQL sources, replace "server-side cursor → Python values → text → Polars CSV → COPY"
with a COPY pipe: the origin's read-only session runs
`COPY (SELECT <declared columns> FROM (<validated query>) q) TO STDOUT (FORMAT text)` and every
block is forwarded unchanged into `COPY <typed staging> FROM STDIN (FORMAT text)`. Window
parameters are rendered client-side with psycopg's quoting; the declared columns are checked with
a `LIMIT 0` probe first; deterministic output settings make both paths byte-identical; the run's
time limit still applies; "COPY not supported/permitted" falls back to today's path and is
recorded in the run history. Constitution V is amended to describe what the engine really does
(research R1–R10).

## Technical Context

**Language/Version**: Python 3.12+ (backend/worker)

**Primary Dependencies**: existing — psycopg 3 (COPY streaming, `ClientCursor`), sqlglot
(validated query), Polars (REST/SOAP batches only); no new library

**Storage**: unchanged schema; `integration_run.rows` JSON gains `path`/`fallback`

**Testing**: pytest on `DATABASE_URL_BI` (`app_test_*`) using the existing `pg_source` fixture
(origin = BI database, read-only session): new `tests/test_bulk_extract.py` (edge-case
equivalence, column mismatch, type mismatch, deadline, fallback via monkeypatched origin error,
connection loss, REST unchanged); existing `tests/test_runner.py` unchanged and green.
Opt-in benchmark script.

**Target Platform**: the `worker` service of every installation

**Project Type**: web application + worker (backend change only)

**Performance Goals**: ≥ 5× faster full rebuild at 1 M rows; flat memory (SC-001/002)

**Constraints**: read-only origin, single validated query, statement timeout, declared types
checked by the installation database, no credentials/values in logs or run records

**Scale/Scope**: 2 engine functions, runner integration, run-history display, constitution text

## Constitution Check

| Rule | Status | Evidence |
|---|---|---|
| II. Backend as ETL | PASS | still worker → staging → datasets; aggregation in SQL |
| III. Origin read-only, isolated | PASS | same read-only session and validated query; COPY TO is a read |
| IV. Folders | PASS | `backend/app/engine/` only |
| V. Fixed stack | **AMEND** | text says "Polars with ConnectorX for extraction"; code uses psycopg COPY (and Polars only for REST/SOAP). Amendment 1.7.0 (R9) |
| VI. Data tuning | PASS | unchanged |
| IX. Spec-driven reporting | PASS | workspace artifacts unchanged |
| Constraints (no secrets in logs, Alembic, worker idempotent/restart-safe) | PASS | no schema change; failures abort the run transaction as today |

Post-design re-check: PASS once amendment 1.7.0 is applied (task T001).

## Project Structure

### Documentation (this feature)

```text
specs/008-fast-pg-extraction/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/engine.md
└── tasks.md
```

### Source Code (repository root)

```text
.specify/memory/constitution.md            principle V amendment (1.7.0) + Sync Impact Report
backend/app/engine/extract.py              BulkUnsupported, pg_copy (R1–R6)
backend/app/engine/runner.py               bulk path for `query` datasets, fallback, path record
frontend/src/pages/admin/Integrations.tsx  show path (and fallback) in the run history line
frontend/src/api/types.ts                  run rows type gains path/fallback
backend/scripts/bench_extract.py           opt-in benchmark (R10)
backend/tests/test_bulk_extract.py         equivalence and failure tests
```

**Structure Decision**: the engine keeps its two modules: `extract.py` talks to origins,
`runner.py` owns the installation transaction and staging.

## Complexity Tracking

| Item | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Keeping the rows path as fallback | some PostgreSQL-compatible sources refuse `COPY (query)` | removing it would break those integrations |
