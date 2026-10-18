---
description: "Task list for feature 005 — Vibe Reporting"
---

# Tasks: Vibe Reporting

**Input**: `/specs/005-vibe-reporting/` (plan, spec, research, data-model, contracts, quickstart)

**Prerequisite**: feature 004 complete (catalogue, connectors, crypto, step-up).

**Tests**: included; validator and SQL-safety tests first.

## Phase 1: Setup

- [X] T001 Create `cli/` package `bizview-cli` (pyproject: `pyyaml`, `jsonschema`, `sqlglot`, `httpx`; entry point `bizview`), add it as a path dependency of `backend`; add `polars`, `apscheduler<4`, `reportlab` to backend; `recharts` to frontend — *done: no `recharts`; the trend chart is an inline SVG component (smaller bundle, Safari 14-safe)*
- [X] T002 [P] JSON Schemas `cli/bizview_cli/schemas/{integration,report,request,lock,workspace}.json` exactly per contracts/artifacts.md
- [X] T003 [P] Constitution amendment 1.6.0 (principle IX Spec-Driven Reporting; folders `cli/`, `workspace-template/`; engine-owned dataset schemas); mark feature 001 superseded (header note + README of `specs/001-*`)

## Phase 2: Foundational

- [X] T004 Tests first `cli/tests/test_sqlsafety.py`: allowed single `SELECT`/`WITH`; refused DDL/DML, multiple statements, `COPY`, `SELECT … INTO`, `FOR UPDATE`, `pg_read_file`/`pg_ls_dir`/`lo_*`/`dblink*`/`set_config`/`pg_terminate_backend`, comments hiding statements, unknown dataset aliases in report metrics
- [X] T005 Implement `cli/bizview_cli/sqlsafety.py` (sqlglot, postgres dialect) 
- [X] T006 Tests first `cli/tests/test_validate.py` on fixture workspaces: spec discipline (missing files, status not approved, open tasks, wrong folder), schema errors, duplicate ids, dependency graph, metric references, lock write/verify, breaking dataset change detection
- [X] T007 Implement `cli/bizview_cli/{validate,lock}.py` and CLI `bizview validate [--write-lock]`
- [X] T008 Migration `0004_vibe_reporting` + models per data-model.md (`workspace_version` with one-active partial unique index, `integration_run`, `integration_run_request`, `report_cache`, `api_token`, `dashboard.report_id/managed_by`, audit kinds)

## Phase 3: US1 — Workspace (P1)

- [X] T009 [US1] `workspace-template/preset/` (Spec Kit preset `bizview`: spec/plan/tasks templates with `Spec type`, integration and report sections; scripts placing features under `specs/integrations|reports/`) — *done in `cli/bizview_cli/workspace_template/preset/` (package data; constitution 1.6.1)*
- [X] T010 [US1] `workspace-template/extension/` (commands `bizview-validate`, `bizview-describe`; mandatory `after_implement` hook running `bizview validate --write-lock`) — *done in `cli/bizview_cli/workspace_template/extension/`*
- [X] T011 [US1] `workspace-template/files/`: workspace constitution (Vibe Reporting principles), `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, `README.md` ("vibe reporting" guide in Spanish and English), `bizview.yaml`, `.gitignore` — *done in `cli/bizview_cli/workspace_template/files/`*
- [X] T012 [US1] `bizview init` (git init, `specify init --here --ai <agent>`, `specify preset add`, `specify extension add`, copy files) + test on a temp folder (layout, `specify preset resolve spec-template` → bizview)

## Phase 4: US2 — Integrations (P1)

- [X] T013 [US2] `backend/app/engine/datasets.py`: contract → DDL in `ds_<id>` (create, add column, rebuild on incompatible change), staging, window replace in one transaction
- [X] T014 [US2] `backend/app/engine/runner.py`: PostgreSQL extraction via 004 connector (read-only transaction, parameters `window_start/window_end` bound safely), REST/SOAP request definitions with pagination, Polars typing/checks, reconciliation, run records, advisory lock, time limit — *done: full rebuilds stream the origin in 20 000-row batches inside one transaction; `slice` is accepted and reserved*
- [X] T015 [US2] Worker entry point `python -m app.worker` (APScheduler from the active version; incremental/full crons; run-request queue; stale run cleanup); compose + installer add `worker` service and mount `./workspace:ro`
- [X] T016 [US2] Tests: runner against the Customer B origin (read-only, small window) and stub REST/SOAP; contract mismatch fails without loading; idempotent re-run; failure keeps previous data

## Phase 5: US3 — Reports (P1)

- [X] T017 [US3] `backend/app/engine/periods.py` (presets, comparisons, zero base, ISO weeks, grain) with the unit tests of feature 001 research R7
- [X] T018 [US3] `backend/app/engine/report.py`: query builder over declared datasets/joins, metrics and formulas, dimensions, filters, views, daily materialisation, cache/ETag; `api/reports.py` — *done: `materialize: daily` is accepted and reserved (not needed at Customer B's volume: year-to-date queries run in 130–230 ms)*
- [X] T019 [US3] PDF (`engine/pdf.py`, ReportLab) with parity test against the JSON views — *done in `backend/app/reports/pdf.py` (constitution: PDF code in `app/reports/`)*
- [X] T020 [US3] AI narrative (`engine/narrative.py`): only declared aggregates; captured-prompt test; hidden when AI off; test that no other code path calls the AI provider (except the 003 connection test)
- [X] T021 [US3] Frontend generic renderer `/r/:id` (`ReportView`, `KpiGrid`, `TrendChart`, `RankingTable`, `PeriodPicker`, `Narrative`, PDF button), dashboards catalogue linking; Playwright 320/375 px

## Phase 6: US4 — Apply and rollback (P2)

- [X] T022 [US4] `backend/app/workspace/{loader,validate,apply}.py` (server validation = CLI validation + live checks), `api/workspace.py` (validate, apply with step-up, rollback), dashboards sync (create/update/hide) — *done in `backend/app/workspace/service.py` and `api/workspace.py` (integrations API included)*
- [X] T023 [US4] Admin pages `Workspace` (mounted version, validate, diff, apply, rollback) and `Integrations` (status, runs, run now)
- [X] T024 [US4] Tests: lock mismatch, atomic apply, rollback < 1 min, audit entries, removed report hidden with grants kept

## Phase 7: US5 — Describe and tokens (P2)

- [X] T025 [US5] `api_token` endpoints + admin page `Tokens`; `GET /api/sources/{name}/describe` (PostgreSQL/REST/SOAP structure only); `bizview describe`; tests (no values, revoked token 401, audit)

## Phase 8: Customer B workspace (dogfooding) & Polish

- [X] T026 Create Customer B's workspace with `bizview init` outside the product repository; write, with vibe reporting, integration spec `erp-ventas` (from feature 001's origin contract and `bizview describe`) and report specs `ventas` and `productos`; implement, validate, apply locally; compare figures against direct read-only queries on the customer's ERP — *done: `../cliente-b-bizview` (separate repo); the first full load failed reconciliation on some historical ERP days and the spec was clarified; the latest month equals the direct ERP query to the cent*
- [X] T027 Docs: README slogan "Vibe reporting", `docs/VIBE-REPORTING.md` (author guide), `docs/INSTALL.md` (workspace mount, worker), CONTRIBUTING (preset/extension development)
- [X] T028 Full verification (backend, CLI, frontend, Playwright, installer, ShellCheck, actionlint) and security review (SQL safety, lock integrity, token scope, AI inputs, dataset schema ownership) — *done: backend 288 passed / 1 skipped, CLI 39, frontend unit 13, Playwright 48 (3 engines × 320/375 px), installer 47, ShellCheck, actionlint. Review fixed: time zone injection into origin session options, REST credentials to another host, YAML parsed and hashed from the same bytes, AI prompt carries filter labels only*

## Dependencies

004 → Phase 1–2 → US1 ∥ (US2 → US3) → US4 → US5 → Phase 8.

## Phase 9: Converge 2026-10-08 — Polars transform stage (amendment FR-A01–FR-A05)

Design: [plan-amendment-2026-10-08.md](./plan-amendment-2026-10-08.md) §1–§3, §6, §7.

- [X] T029 [A] Schema: add optional `transform: {input, sql, batch_rows}` to datasets in `cli/bizview_cli/schemas/integration.schema.json` (`input` = extraction contract, required with `sql`; `sql` 1–20 000 chars; `batch_rows` 10 000–1 000 000, default 200 000); `cli/bizview_cli/sqlsafety.py` gains `check_transform(sql, input_types) -> TransformCheck(problems, mode, sql)`: single SELECT (+ non-recursive CTEs) over `input`, node and function allow-list of plan §1, refusals (table functions, joins, set ops, sub-queries, LIMIT, parameters, qualified names), whole-mode detection, regeneration with the `PolarsSQL` dialect (keeps `TRY_CAST`) per FR-A01, FR-A03
- [X] T030 [A] Validation: new shared `cli/bizview_cli/transform.py` (lazy Polars import: input dtypes, `infer` on an empty typed frame, `compare` with the type table of plan §2, tz-aware `CAST … AS DATE` probe); `cli/bizview_cli/validate.py` uses it in `_check_integration` (issues with file/path/expected/fix, `transform_float` warning, `transform_unchecked` warning without Polars; query/request columns checked against `transform.input`); `cli/pyproject.toml` optional extra `transform = ["polars>=1.44,<2"]` per FR-A02
- [X] T031a [A] Engine: `backend/app/engine/transform.py` — `compile`, `parse_text` (PG text-format unescape, typed casts, tz), `CopyTextSplitter`, `Sink` rows mode (per-batch SQLContext, dtype check, 50 000-row output slices); `backend/app/config.py` `TRANSFORM_MAX_ROWS`, `TRANSFORM_SPILL_DIR` per FR-A03
- [X] T031b [A] Wiring in `backend/app/engine/runner.py` `_extract` (also used by `run_preview`): `compile` before extraction (mismatch → failed, nothing extracted or loaded); `copy+polars` via `extract.pg_copy(columns=input, write=splitter.write)`, `rows+polars` for the COPY fallback and REST/SOAP/Supabase (`columns=input`); staging via `_copy`; `Plan.path` values `copy|rows|copy+polars|rows+polars` (was `bulk`); stop requests (013) honoured per block and between batches per FR-A03, FR-A04
- [X] T032 [A] Run history: `_finish` writes per dataset in `integration_run.rows` `path`, `transform_mode`, `rows_in`, `transform_ms` (no new column); `frontend/src/api/types.ts` + `frontend/src/pages/admin/Integrations.tsx` show COPY / COPY + Polars / filas / filas + Polars (legacy `bulk` = COPY), mode and time; texts in `frontend/src/i18n/es.ts` (+ `en.ts` when 022 has landed) per FR-A05
- [X] T033 [A] Agent: `cli/bizview_cli/authoring.py` topic `transform` + topic `example-large` → new golden workspace `cli/bizview_cli/golden-large/` (integration `pedidos` with a row-wise transform); `backend/app/assistant/origin.py` `check_query` compares the query/request with `transform.input` and returns the transform output columns/types (`transform: {mode, columns, problems}`) per FR-A05
- [X] T034 [A] Tests: `cli/tests/test_transform.py` (allow-list runs on Polars after regeneration, refusals, mode detection, mismatch, float warning, tz date error, no-Polars warning); `backend/tests/test_transform.py` (parse/splitter, copy+polars and rows+polars equal SQL-only results, batch vs whole equal, cap error, stop between batches, no load on mismatch, preview); update `"bulk"` → `"copy"` in `backend/tests/test_bulk_extract.py`, `backend/tests/test_runner.py`; `backend/scripts/bench_extract.py` modes `copy+polars` and `whole`; SC-A01 recorded in `specs/008-fast-pg-extraction/research.md` (whole-mode tests — batch vs whole, cap error, stop during the poll — and the bench `whole` mode belong to T035; until then whole-mode transforms fail the run before extraction with a clear message)

## Phase 10: Converge 2026-10-08 — big-data readiness (FR-A03 streaming, FR-A06–FR-A09)

Design: [plan-amendment-2026-10-08.md](./plan-amendment-2026-10-08.md) §3–§8.

- [X] T035 [A] Engine: whole mode in `backend/app/engine/transform.py` `Sink` — typed batches spilled to Arrow IPC under `TRANSFORM_SPILL_DIR/<run>-<dataset>/`, `TRANSFORM_MAX_ROWS` (50 000 000) on input rows, `scan_ipc` → SQL → `sink_ipc(lazy=True, engine="streaming")` → `collect(background=True)` polled with stop/deadline (`cancel()`), result loaded with `collect_batches`; folder removed in `finally`; stale folders swept at worker start (`backend/app/worker.py`); `POLARS_TEMP_DIR` for `worker`/`backend` in `docker-compose.yml` and the env example — per FR-A03
- [X] T036 [A] Validation: new shared `cli/bizview_cli/materialize.py` (`decompose`: sum/count/min/max/avg components, FILTER, CASE inside aggregates, outer template; ineligibility reasons of plan §4); `cli/bizview_cli/validate.py` issues `materialize_ineligible` with reason and fix — per FR-A06
- [X] T037a [A] Migration `backend/alembic/versions/0016_run_transform.py` (revises `0015_direct_reports`): table `report_rollup` (`report_id` PK, `schema_name`, `table_name`, `definition_hash`, `status` ready|stale|failed, `source_runs` jsonb, `columns` jsonb, `rows`, `built_at`, `refreshed_at`, `refresh_ms`, `error`, `updated_at`) and `integration_run.rollups jsonb NOT NULL DEFAULT '{}'`; `backend/app/models.py` `ReportRollup`, `IntegrationRun.rollups`; up/down test in `backend/tests/test_migrations.py` — per FR-A06, FR-A07
- [X] T037b [A] Engine: `backend/app/engine/rollup.py` — definition + hash, table `ds_<base integration>.mv_<report, - → _>` (day + `k_<dimension>` + `c_<hash>` components, index on day, date index on the base dataset), full build by `__new` + swap, windowed refresh (delete/insert touched days with sargable range), recomposed metric SQL with type casts — per FR-A06, FR-A07
- [X] T038 [A] Runner + worker: `backend/app/engine/runner.py` `_load` captures touched days / joined-dataset fingerprints (`rollup.capture`) and `_run` calls `rollup.after_load` before commit (xact lock per report, savepoint, window vs full rules, failure → previous rollup kept, `stale`, run `succeeded` with message, `run.rollups`); `backend/app/worker.py` submits `rollup.ensure_version` after a new active version (apply/rollback) and while rollups are pending (integration locks, `ROLLUP_TIMEOUT_SECONDS`, drop removed rollups) — per FR-A07
- [X] T039 [A] Report engine: `backend/app/engine/report.py` `RawSource`/`RollupSource` fragments shared by `aggregate`, `_where`, `_bucket_expr`, the four views and `filter_options`; freshness (status, hash, `source_runs` = latest succeeded runs) resolved in `data_version_and_cached`; per-request context copy; stale-on-missing-table fallback; `backend/app/api/reports.py` filter options use it; direct reports and previews never routed — per FR-A08
- [X] T040 [A] Authoring: `cli/bizview_cli/authoring.py` rules (propose `materialize: daily` above 5 M rows; fix the "integración con materialize" wording) + `golden-large` report `pedidos-dia` with `materialize: daily`; FR-A09 warning `materialize_recommended` (and `materialize_large` for high-cardinality text dimensions) in `cli/bizview_cli/validate.py` via `DirectContext.dataset_rows`, provided by `backend/app/engine/direct.py` from `pg_class.reltuples` — per FR-A09
- [X] T041 [A] Tests: `backend/tests/test_rollup.py` (rollup == raw for every view type, period, comparison, filter and grain; touched-day refresh incl. PK row moving days; joined dataset unchanged/changed; full run; failed refresh keeps previous + raw fallback; `ensure_version`; lock serialisation; missing table fallback; direct/preview never routed); `cli/tests/test_materialize.py` (decomposition, ineligibility, `golden-large`, FR-A09 warnings); frontend unit (path labels, rollup outcome); SC-A02 benchmark `backend/scripts/bench_rollup.py` (opt-in, records R11 with the reference machine in `specs/005-vibe-reporting/research.md`) — per FR-A06–FR-A09, SC-A02 — *2026-10-10: tests done (backend test_rollup 13, CLI test_materialize, frontend integration-runs); benchmark split to T041b*
- [X] T041b [A] Opt-in benchmark `backend/scripts/bench_rollup.py` (BENCH_ROWS, own `app_test_bench_*` schema dropped in finally, dataset via `datasets.ensure_table` with the dict column contract, `rollup.definition(...)` → `build_full` + 7-day `refresh_days`, prints seconds; record R11 + reference machine in research) — split from T041 after two failed DeepSeek attempts — per SC-A02 — *2026-10-12: `backend/scripts/bench_rollup.py` written and run (1 M rows, 500 dimension
combinations, throwaway `app_test_bench_*` schema dropped and verified); R11 in research.md
holds the machine and the numbers, the 50 M SC-A02 run stays on the reference machine*

## Convergence 2026-10-12

- [X] T042 [A] SC-A01's time target (a row-wise transform adds at most 30 % to the
  extraction-to-load time at 1 M rows) is **not met on a same-host origin**: measured **+81–91 %**
  with the default `transform.batch_rows` (200 000) and **+44.2 %** at best with 50 000 (AMD Ryzen 5
  7430U, local PostgreSQL 17.11, dataset on the same host; the earlier +19.1 % came from a
  network-bound remote run that hid the Polars work — ~1.9 s added to a 2.05 s COPY). Memory:
  peak 434 MB / Δ+298 MB with the default, 298 MB / Δ+162 MB at 50 000 and 242 MB / Δ+106 MB at
  20 000, so the spec's peak < 300 MB and Δ ≤ 150 MB hold from 50 000 down. Choose and implement a
  mitigation (lower the default `batch_rows` and/or cut the per-batch work in
  `app/engine/transform.py`, where the typed frame plus CSV serialisation are ~1 s of the 1.9 s
  added) or have the owner amend SC-A01 to the measured overhead; re-run
  `BENCH_ROWS=1000000 BENCH_MODES=copy,copy+polars uv run python scripts/bench_extract.py` with
  `BENCH_DATABASE_URL` on a same-host database and update the table in
  `specs/008-fast-pg-extraction/research.md` — per SC-A01, plan §8, T041/T041b

  *Closed 2026-10-12*: both mitigations were implemented in `app/engine/transform.py` (the
  declared-type check reads the materialised typed frame — `transform_ms` 654 → 287 ms at 200 000
  rows per batch — and `CopyTextSplitter` marks a batch as unescaped when it contains no backslash)
  and the default `batch_rows` came down from 200 000 to **20 000**; five same-host 1 M-row runs
  then give a median **+28.6 %** (22.7–36.8 %, four of five ≤ 30.2 %) with ~210 MB peak, so SC-A01
  holds at the median and its memory target comfortably (±3 % run-to-run spread of the COPY
  baseline is what keeps the margin thin — the table in the 008 research is the evidence).
  A much lower overhead would need another transport (COPY BINARY/Arrow) instead of CSV twice.

