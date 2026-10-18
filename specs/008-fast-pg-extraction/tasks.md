---
description: "Task list for feature 008 — Faster PostgreSQL extraction"
---

# Tasks: Faster PostgreSQL extraction

**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/engine.md](./contracts/engine.md),
[quickstart.md](./quickstart.md)

**Tests**: included (SC-003 byte-identical equivalence and SC-004 safety cases must be proven).
Per the current working agreement, code is written for all queued features first and the full
suites run once at the end (T011).

**Roles**: DeepSeek writes the code from briefs; Claude audits, fixes, converges.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Amend constitution principle V (Worker: COPY pipe for PostgreSQL, Polars only for REST/SOAP, ConnectorX removed) to 1.7.0 in .specify/memory/constitution.md per research R9

---

## Phase 2: Foundational

- [X] T002 In backend/app/engine/extract.py add `class BulkUnsupported(Exception)` with `reason: str` (SQLSTATE class name) and the constant `BULK_UNSUPPORTED = (psycopg.errors.FeatureNotSupported, psycopg.errors.InsufficientPrivilege, psycopg.errors.SyntaxError, psycopg.errors.UndefinedFunction)` per contracts/engine.md

---

## Phase 3: User Story 1 — Large PostgreSQL integrations finish much faster (P1) 🎯 MVP

- [X] T003 [US1] Implement `pg_copy(settings, secrets, app, query, params, *, columns, timezone, time_limit_s, deadline, write)` in backend/app/engine/extract.py exactly per contracts/engine.md steps 1–5: `_pg_connect` + session `SET DateStyle = 'ISO, MDY'`, `IntervalStyle = 'postgres'`, `extra_float_digits = 3`, `bytea_output = 'hex'`; render `to_psycopg(query)` with `psycopg.ClientCursor(conn).mogrify(q, params)`; `LIMIT 0` probe for column names (today's mismatch message); `COPY (SELECT <psycopg.sql.Identifier columns> FROM (<rendered>) AS q) TO STDOUT (FORMAT text)` via `cursor.copy(...)`, iterating `copy` blocks into `write`; deadline check between blocks
- [X] T004 [US1] In backend/app/engine/runner.py `_extract`, for `query` datasets: open `pg.cursor().copy(COPY <staging> (<columns>) FROM STDIN (FORMAT text))`, call `extract.pg_copy(..., write=copy.write)`, set `plan.extracted` from the copy cursor's `rowcount`, `plan.path = "bulk"`; map `psycopg.errors.DataError` to today's `ExtractError("los datos no cumplen el contrato: …")`; add `path: str = "rows"` and `fallback: str | None = None` to `Plan`
- [X] T005 [US1] In backend/app/engine/runner.py `_finish`, write `path` (and `fallback` when set) into each `run.rows[<dataset>]` per data-model.md

---

## Phase 4: User Story 2 — Same safety guarantees (P1)

- [X] T006 [US2] Tests in backend/tests/test_bulk_extract.py (reuse the `pg_source` fixture pattern of tests/test_runner.py): edge-case fixture table (text with `\n`, `\t`, `\\`, quotes, emoji; empty string vs NULL; timestamptz across a DST change; numeric(38,10); bigint; bytea; int[]; jsonb; date) loaded through bulk and rows paths into two temp tables → `EXCEPT` both ways empty (SC-003); column mismatch → today's message and zero rows; type mismatch (text into a declared integer) → "los datos no cumplen el contrato"; deadline already passed → "se superó el tiempo máximo"; a write inside the query refused by `sqlsafety`; the origin session is read-only (`SHOW transaction_read_only` = on inside pg_copy's connection)

---

## Phase 5: User Story 3 — Sources without bulk export keep working (P2)

- [X] T007 [US3] In backend/app/engine/runner.py: on `extract.BulkUnsupported(reason)` (raised before any block) run the existing rows path for that dataset, set `plan.path = "rows"`, `plan.fallback = reason`; any other error fails the run (no fallback)
- [X] T008 [US3] Tests in backend/tests/test_bulk_extract.py: monkeypatch the origin COPY to raise `psycopg.errors.FeatureNotSupported` before the first block → run succeeds with `rows[ds].path == "rows"` and `fallback == "FeatureNotSupported"`; raise `psycopg.OperationalError` after one block was written → run fails, no fallback, dataset unchanged; a REST integration records `path == "rows"` without fallback

---

## Phase 6: Polish

- [X] T009 [P] frontend/src/api/types.ts run rows type gains `path?: "bulk" | "rows"` and `fallback?: string`; frontend/src/pages/admin/Integrations.tsx shows " · rápida" for bulk and " · por filas (<reason>)" on fallback in the run-history line
- [X] T010 [P] backend/scripts/bench_extract.py (opt-in, `BENCH_ROWS`, default 100000): throwaway schema `bench_<hex>` in DATABASE_URL_BI with generate_series rows of mixed types, runs both paths through the engine functions into temp tables, prints rows/seconds/peak RSS for each and the speed-up, drops the schema in `finally`; CHANGELOG.md Unreleased entry
- [X] T012 [P] Update backend/tests/test_runner.py to expect "path": "bulk" in run.rows
- [X] T011 Full suites at the end of the coding round (sequential, detached): backend `uv run pytest`, then frontend `npm test && npm run build && npm run check:compat && npm run e2e`; then `/speckit-converge` — *Baseline 2026-10-08: backend (all pass after 2 test fixes and 3 network-timeout reruns), CLI, frontend unit 425, build, compat, Playwright 300 passed / 36 skipped*

---

## Dependencies

T001 → T002 → T003 → T004 → T005; T007 after T004; tests T006/T008 after their code;
T009/T010 independent; T011 last (after all queued features are coded).

---

## Phase 7: Convergence (workflow wf_aa9720db-186, 2026-10-01)

- [X] T013 In backend/app/engine/extract.py pg_copy, close the wrapped query on a new line in both the LIMIT 0 probe and the COPY (`({}\n) AS q`) so a query ending in a `-- comment` works; test in backend/tests/test_bulk_extract.py that such a query runs on the bulk path and matches the rows path, per FR-007 / FR-003 (contradicts)
- [X] T014 Run backend/scripts/bench_extract.py at BENCH_ROWS=10000 and 1000000 (after the e2e run, not concurrently), record seconds and peak MB of both paths in research.md, confirm ≥5× and bulk peak-RSS delta < 50 MB, per SC-001 / SC-002 / FR-002 (partial) — measured 2026-10-01 on the remote BI database (origin = destination over the internet): 1.8× at 1M rows (SC-001 not met in this environment, network-bound; re-measure on a LAN origin), bulk peak +9.9 MB (SC-002 met)
- [X] T015 In pg_copy wrap the BULK_SESSION SETs: FeatureNotSupported / UndefinedObject / InvalidParameterValue / CantChangeRuntimeParam → BulkUnsupported(class name); other psycopg errors → ExtractError; test with a forced SET failure → run succeeds on rows with that fallback, per FR-008 / US3 AS1 (partial)
- [X] T016 In backend/app/engine/runner.py set `plan.path = "bulk"` before calling `_copy_bulk` (reset to "rows" in the BulkUnsupported branch); assert `path == "bulk"` in the type-mismatch and failure-after-data tests, per FR-009 (contradicts)
- [X] T017 Tests that exercise pg_copy's own error classification by patching the origin COPY (not pg_copy itself): FeatureNotSupported at COPY start → rows fallback recorded; OperationalError after one block → run fails, no fallback, dataset unchanged; a bulk run whose window matches nothing → extracted 0, path bulk, dataset unchanged; REST run test asserts `path == "rows"` without fallback, per FR-008 / FR-010 / SC-005 / edge cases (partial)
- [X] T018 Align spec.md FR-007 / SC-003 / edge cases with research R1 (identity guaranteed for contract types; non-contract origin types in text columns use PostgreSQL's text form), contracts/engine.md (pg_copy returns blocks; lazy destination COPY), and T009 wording ("rápida" / "por filas (motivo)"), per FR-007 / contracts (contradicts)
- [X] T019 Full suites again after T013–T017 (sequential, detached), then re-run convergence, per T011 (partial) — *Baseline 2026-10-08: backend (all pass after 2 test fixes and 3 network-timeout reruns), CLI, frontend unit 425, build, compat, Playwright 300 passed / 36 skipped*

---

## Phase 8: Convergence

- [X] T020 Let backend/scripts/bench_extract.py take `BENCH_DATABASE_URL` (origin and destination; default `DATABASE_URL_BI`, never printed), then re-run it at BENCH_ROWS=10000 and 1000000 with origin and destination on the same host or LAN and record seconds, rows/s and peak MB of both paths in research.md — the 2026-10-01 measurement (1.8×) ran both paths at ~1,400 and ~770 rows/s over the internet link, which hides the COPY pipe's CPU savings, so SC-001 (≥ 5×) is unverified, per SC-001 / US1/AC2 (partial) — *2026-10-12: `BENCH_DATABASE_URL` (both sides, never printed; the run prints host/port/database
only) added, plus `BENCH_BATCH_ROWS` for the transform variants; run against a local PostgreSQL
(`postgres:17-alpine`, same host as the client) at 10 000 and 1 000 000 rows: **SC-001 met**
(6.0x at 1 M, 6.1x at 10 k), rows at 81 623 rows/s vs copy at 486 788 rows/s, peak 284.8 MB vs
136.1 MB. Numbers, batch variants and the SC-A01 finding in research.md; SC-A01's time target stays
open as T042 in feature 005. The benchmark also fails fast now when a path dies before reporting.*
