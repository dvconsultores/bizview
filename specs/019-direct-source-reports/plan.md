# Implementation Plan: Direct-source reports (no ETL)

**Branch**: `019-direct-source-reports` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

## Summary

A `report.yaml` may declare a `direct` block instead of `uses`: a source (`bi` = this installation's
BI database, or a PostgreSQL catalogue source enabled for direct reads) and a set of tables with a
column contract. The report engine builds exactly the same aggregate SQL it builds for datasets, but
runs it through a **direct runner** (`backend/app/engine/direct.py`) instead of the BI pool:
read-only session, statement deadline, row cap, per-source concurrency slots, single-flight, result
cache in the existing `report_cache` keyed by a time bucket of `cache_seconds`, and a stale fallback
(≤ 24 h) when the source fails. Validation checks the declared structure against the live source,
refuses every product table of the BI database, and requires the direct-mode lines in the report
spec. The agent and the CLI can author direct reports (authoring pack, golden example, `check_query`
on a report, live preview without a temporary schema). Dataset reports are untouched (SC-005).

## Technical Context

Python 3.12 / FastAPI / SQLAlchemy / Alembic (migration `0015_direct_reports`), psycopg 3
(`psycopg.sql` composition, read-only sessions), jsonschema + sqlglot in `cli/bizview_cli`
(`sqlsafety.check_expression` re-used unchanged), ReportLab PDF (`backend/app/reports/pdf.py`).
React 19 / Tailwind frontend; strings go to `frontend/src/i18n/es.ts` only (022 converts them).
Backend tests on `DATABASE_URL_BI` in `app_test_*` schemas; direct tables for `bi` are seeded in
the test's physical mapping of the logical schema (see §4); no live AI (fake provider). Backend runs
`WEB_CONCURRENCY` (default 2) processes plus the worker, so concurrency and single-flight are
enforced across processes with PostgreSQL advisory locks on the BI database.

**Settings** (`backend/app/config.py`, `.env.example`, `docs/INSTALL.md`):
`DIRECT_REPORTS_BI` (bool, default `true`), `DIRECT_REPORT_CONCURRENCY` (int 1–20, default 2),
`DIRECT_REPORT_WARN_ROWS` (int ≥ 1, default 5 000 000). Internal constants in `engine/direct.py`:
`STALE_MAX = 24 h`, `FAILURE_BACKOFF_S = 30`, `FETCH_CAP = 10 000` rows per statement,
`SOURCE_TTL_S = 10` (source flag/settings cache), `LOG_RETENTION_DAYS = 7`.

**Supporting libraries**: none new.

## Constitution Check

- **II (Backend as ETL, direct reads by exception)** — every exception condition is met:
  - *data already shaped by another process*: FR-003 requires the report spec to state the mode,
    the source, the tables, who maintains them and the expected volume; the validator refuses the
    report without those lines; the agent rule (FR-012) uses direct mode only when the user says the
    data is already prepared.
  - *engine-generated aggregate SQL only over declared tables/columns*: the direct path re-uses
    `from_clause`, `aggregate`, `filter_options` and `expression()` (sqlsafety allow-list, quoted
    identifiers, literals composed by psycopg); aliases resolve only to `direct.tables`; no
    free-form SQL exists in a direct report.
  - *read-only session*: `BEGIN READ ONLY` on the BI connection; `default_transaction_read_only=on`
    via `extract._pg_connect` for catalogue sources (plus `BEGIN READ ONLY` inside).
  - *statement timeout*: `SET LOCAL statement_timeout` = remaining time of the request deadline
    (`timeout_seconds`, 1–60), so the whole build — slot wait included — ends within the timeout
  (SC-004 allows + 1 s for the response).
  - *row cap*: table views limited to `min(view.limit or 100, max_rows)`; every statement fetched
    with `fetchmany(FETCH_CAP + 1)` → error beyond the cap.
  - *result cache*: `report_cache` per report + selection + time bucket; single-flight.
  - *explicitly enabled by the super user*: per-source flag `data_source.direct_reports` (default
    off, PostgreSQL only, step-up, audited); BI database by `DIRECT_REPORTS_BI`.
  - *product tables never readable*: deny-list from `Base.metadata` + `alembic_version` + reserved
    schemas, enforced at validation **and** at context build; BI views depending on a product
    table are refused (dependency walk).
  - *< 200 ms cached, cold within timeout*: cache hit = one `report_cache` lookup (same path as
    datasets); SC-002 test on 1 M rows (opt-in slow marker).
- **III (source of truth external)**: only SELECTs in read-only transactions; no DDL, no temp
  tables, no writes to any source; the BI database is read with the same read-only batch as
  dataset reports. SC-003 test spies every statement sent through the runner.
- **IV (folders)**: engine code in `backend/app/engine/direct.py`; schemas, validator, golden
  example and authoring pack in `cli/`; no customer SQL anywhere (all SQL is generated).
- **V (fixed stack)**: no new component or library.
- **VII (one product)**: golden names generic (`bi_ventas`, `ventas-directo`); no customer data.
- **VIII (AI optional and private)**: no AI in the read path. Agent tools return structure only
  (`describe_source`, `profile_source` counts/min/max as in 017, `check_query` with `LIMIT 0` →
  column names/types); the preview result sent to the agent carries outcome lines only, never
  values (017 SC-002 audit extended). AI narrative on a direct report sends the same aggregates
  the spec lists.
- **IX (spec-driven)**: a direct report is an approved Spec Kit report spec + `report.yaml`;
  "no spec, no run" unchanged; the lock covers the new spec lines; readiness for a direct draft =
  validation + structure matched + checked query + preview succeeded.
- **Security / Constraints**: TLS rules of the `internet` profile apply through `_pg_connect`;
  netguard on catalogue hosts; source credentials never logged (errors pass `_safe_message`);
  direct-read log stores no values; every user-visible text in Spanish now (English via 022).
→ PASS (no amendment needed: constitution 2.0.0 principle II already defines the exception).

## Design

### 1. Schema (`cli/bizview_cli/schemas/report.schema.json`, FR-001/FR-002)
- Top level: `required` loses `uses`; add `"oneOf": [{"required": ["uses"]}, {"required":
  ["direct"]}]` (both present → oneOf fails; the 017 branch picker discriminates by required key).
- New property `direct` (every property with a Spanish `description`, test_schema_descriptions):
  - `source`: string 1–80 (`bi` or a catalogue source name, case-insensitive).
  - `tables`: object, 1–8 properties; key pattern `^[a-z][a-z0-9_]{0,40}$` (alias); value
    `{table, columns, description?}`, `additionalProperties: false`:
    - `table`: pattern `^[a-z_][a-z0-9_]{0,62}\.[a-z_][a-z0-9_]{0,62}$` (`schema.table`).
    - `columns`: `$defs/column` — same contract as integration columns (`type` enum `text,
      integer, bigint, numeric, boolean, date, timestamptz`, `nullable`, `description`), key
      pattern `^[a-z][a-z0-9_]{0,40}$`, minProperties 1.
  - `cache_seconds` integer 60–86400 (default 300), `timeout_seconds` integer 1–60 (default 15),
    `max_rows` integer 1–5000 (default 500); `additionalProperties: false`.
- `PATTERN_EXAMPLES` in `validate.py` gains the table pattern → `public.bi_ventas`.
- CLI version 0.3.0 (`cli/bizview_cli/__init__.py`, `cli/pyproject.toml`).

### 2. Validation (`cli/bizview_cli/validate.py`, FR-002, FR-003, FR-005, FR-006, FR-011)
- New dataclass `DirectContext` (all optional, the backend fills everything; the CLI fills what it
  has): `sources: dict[str, dict] | None` (lower name → `{name, kind, enabled, direct}`),
  `bi_enabled: bool | None`, `product_tables: frozenset[str]` (`schema.table`),
  `structure: Callable[[str, list[str]], dict] | None` (source, `schema.table` list →
  `{"tables": {"schema.table": {"columns": {name: data_type}, "product_dependency": bool}},
  "error": str | None}`), `personal_kind: Callable[[str], str | None] | None`.
  `validate(root, *, known_sources=None, direct: DirectContext | None = None)`.
- `_check_report` branches: `direct` → `_direct_aliases(entry, ctx, issues)` returns
  `alias → columns` from the contract; every following check (joins, date, metrics, dimensions,
  views, filters, pdf, ai_narrative) runs unchanged on those aliases (FR-002).
- Direct-only checks (all with `file`, `path`, `expected`, `fix` as in 017):
  - `materialize` present and ≠ `none` → `direct_materialize` "materialize no aplica a un reporte
    directo; la caché (`cache_seconds`) es el mecanismo de velocidad".
  - Always (offline too): logical schema `pg_catalog`, `information_schema`, `pg_toast*`,
    `app_test_*`, `preview_*` and table `alembic_version` → `direct_product_table` with the
    message **"Tabla del producto: no se puede leer en un reporte directo"**.
  - With `ctx.product_tables` and source `bi` (or a catalogue source that *is* the BI database,
    see §5): table in the deny-list → same issue.
  - With `ctx.sources`/`ctx.bi_enabled`: unknown source; kind ≠ `postgresql` ("las fuentes SOAP,
    REST y Supabase (REST) no admiten reportes directos"); disabled; flag off ("la fuente no
    permite reportes directos"); `bi` with `DIRECT_REPORTS_BI=false`. Each `fix`: "activa
    «Permitir reportes directos» en la fuente o crea una integración (integrations/<id>)".
  - Spec lines (FR-003), checked in the report's `spec.md` when the artifact has `direct`:
    `**Modo**: directo`, `**Fuente**:`, `**Tablas**:`, `**Mantenido por**:`,
    `**Volumen esperado**:` (regex accepts `Mode`/`direct`, `Source`, `Tables`, `Maintained by`,
    `Expected volume` for 022). Each missing line = one `direct_spec_line` issue. A dataset report
    whose spec says `**Modo**: directo` → `direct_mode_mismatch`.
  - Structure (FR-011) when `ctx.structure`: one call per source with all declared tables;
    missing table → `direct_table_missing`; missing column → `direct_column_missing`;
    incompatible type → `direct_column_type` (`expected: {"type": <contract>, "compatible":
    [...]}`, message names the live type); `product_dependency` → `direct_product_table`.
    Compatibility map: `text` ← text, character varying, character, uuid, citext, name;
    `integer` ← integer, smallint; `bigint` ← bigint, integer, smallint; `numeric` ← numeric,
    integer, bigint, smallint, real, double precision; `boolean` ← boolean; `date` ← date;
    `timestamptz` ← timestamp with time zone, timestamp without time zone. The date column
    check stays the existing contract check (`date`/`timestamptz`).
    `error` (unreachable, timeout) → **warning** `direct_structure_unchecked` (apply is not
    blocked by a source that is down; agent readiness treats it as pending, §8).
  - Personal data (Edge) when `ctx.personal_kind`: a dimension or filter expression that uses a
    flagged contract column must name it in the spec line `**Datos personales**:` →
    otherwise `direct_personal_column` error (table and ranking views list dimension values).
- Offline `bizview validate` (no context): schema, semantic, spec lines and the offline deny
  patterns only.

### 3. CLI (`cli/bizview_cli/__main__.py`, `describe.py`, US3 AC4)
- `bizview validate [--describe NAME=FILE]... [--live]`: `--describe` loads the JSON/YAML output
  of `bizview describe NAME --json` and builds `structure` from its `tables`; `--live` fetches
  `/api/sources/<name>/describe` with `BIZVIEW_URL` + `BIZVIEW_TOKEN` for each direct source of the
  workspace (refactor `describe.describe` into `fetch(source) -> dict` + printing).
  Without either, live structure is skipped and the summary line says so.

### 4. Engine direct path (`backend/app/engine/report.py`, `backend/app/engine/direct.py`)
- `report.py`:
  - `Runner` protocol: `session() -> ContextManager[RunnerSession]` with
    `RunnerSession.query(statement, tz) -> list[tuple]`. `BI_RUNNER` wraps today's `_query`
    unchanged (dataset path byte-identical, SC-005).
  - `Context` gains `runner: Runner = BI_RUNNER` and `direct: DirectSpec | None = None`
    (`source`, `label`, `cache_seconds`, `timeout_seconds`, `max_rows`, `tables` logical names).
  - `aggregate()` and `filter_options()` take an optional `session` argument; when absent they use
    `ctx.runner.session()` per call. `run_views()`: dataset → unchanged thread pool; direct →
    one `ctx.runner.session()` (one slot, one connection, one read-only snapshot) and views run
    sequentially through it.
  - `_build_context()` branches on `direct`: aliases → `(physical_schema, table)` after the
    deny-list re-check (`ReportError(409, "direct_product_table", "Tabla del producto: no se
    puede leer en un reporte directo")`), columns from the contract, `integrations=[]`,
    `runner=direct.DirectRunner(...)`, `direct=DirectSpec(...)` with defaults 300/15/500.
  - `view_table` limit = `min(view.limit or 100, ctx.direct.max_rows)` for direct.
  - `definition_json()` adds `"direct": {"source": label, "cache_seconds": n}` **only** for direct
    reports (dataset JSON unchanged).
  - `data_version()` / `data_version_and_cached()` for direct: `v{version}-d{bucket}` with
    `bucket = floor(epoch_seconds / cache_seconds)`, `updated_at = None`; no `integration_run`
    query.
- `direct.py`:
  - **Deny-list**: `product_tables()` = every table of `Base.metadata` + `alembic_version`, in
    logical schema `public`; `refusal(schema, table, *, bi: bool) -> str | None` also refuses
    the reserved schema patterns of §2. `physical_schema(schema)`: production → unchanged;
    tests (`DB_SCHEMA != public`) and source `bi` → `f"{db_schema}__{schema}"` (same rule as
    `datasets.schema_name`, so `ds_x` maps to the test dataset schema and `public` to
    `<test>__public`; nothing ever reaches the real `public`).
  - **Source resolution** `resolve(name) -> DirectSource` (TTL cache 10 s, own short read
    session): `bi` → `DIRECT_REPORTS_BI`; catalogue → kind `postgresql`, `enabled`,
    `direct_reports`. Refusal → `DirectError("not_allowed", "Esta fuente no permite reportes
    directos")` raised **before** any connection. `is_bi_database(settings)` compares host, port
    and database name with `DATABASE_URL_BI` → such a catalogue source gets the `bi` deny-list.
  - **DirectRunner.session()**: deadline = now + `timeout_seconds`; acquire slot (below);
    connect — `bi`: pooled engine connection, autocommit off, `BEGIN READ ONLY`; catalogue:
    `extract._pg_connect(settings, secrets, app, timezone=tz, time_limit_s=timeout,
    connect_timeout_s=remaining)` (TLS profile + netguard) then `BEGIN READ ONLY`. Each
    `query()`: `SET LOCAL statement_timeout = <remaining ms>`, `SET LOCAL TimeZone`, execute,
    `fetchmany(FETCH_CAP + 1)`; remaining ≤ 0 → timeout. Always `ROLLBACK` at the end (nothing to
    commit). For `bi`, first use per process and version runs the view-dependency check (walk
    `pg_depend`/`pg_rewrite` from each declared relation; any product table → refusal).
  - **Errors** (`DirectError(code, message)`): `timeout` ← `QueryCanceled` / deadline ("La
    consulta superó el tiempo límite de N s"); `unreachable` ← `OperationalError`/connect failure
    ("No se pudo conectar con la fuente"); `busy` ("La fuente está ocupada"); `structure_changed`
    ← `UndefinedColumn`/`UndefinedTable` → one structure check names the first missing item ("La
    estructura de la fuente cambió: falta <columna>"); `not_allowed`; `product_table`; `error`
    (other, text through `runner._safe_message`). Never the query text, never values.
  - **Concurrency** (FR-007): per process `BoundedSemaphore(DIRECT_REPORT_CONCURRENCY)` per
    source key (waiters do not hold DB connections), then a cross-process slot: loop over
    `slot in range(N)` with `pg_try_advisory_lock(hashtextextended(lock_key("direct", source,
    slot), 0))` on a pooled BI connection held for the session, polling every 100 ms until the
    deadline → `busy`. Released in `finally`.
  - **Backoff**: after `unreachable`, the source is marked down for 30 s in process; requests in
    that window fail fast (→ stale or error) without connecting (US2 AC4: no tight loop).
  - **Log** (FR-015): logger `app.direct` one line per session (`report, source, duration_ms,
    rows, outcome, stale`) and one `direct_read_log` row written in its own short transaction
    (failures to log are swallowed and logged at warning). Pruned to 7 days by the worker's
    hourly housekeeping (`backend/app/worker.py preview_housekeeping`).

### 5. Cache, single-flight, stale (`direct.cached_data`, FR-008, FR-009)
- `reports._data()` → for `ctx.direct`: `direct.cached_data(db, ctx, sel, filters, key, tz)`:
  1. `version = v{ver}-d{bucket}`; read `report_cache(report, key, version, "data")` → hit.
  2. Miss → in-process single-flight on `(report, key, version)` (dict of `Future`s under a lock;
     followers wait ≤ timeout + 1 s and share the result or the error).
  3. Leader → cross-process lock `pg_try_advisory_lock(lock_key("direct-sf", report, key,
     version))` polled to the deadline; once held, re-read the cache (another process may have
     filled it) → hit.
  4. Build `{selection, filters, freshness: {updated_at: queried_at, data_version: version,
     mode: "direct", source: label, queried_at, stale: false}, views}` and store it; cleanup for
     direct reports deletes this report's `data` rows that are older than 24 h **or** belong to
     another workspace version (rows of earlier buckets of the same version are kept for the
     stale fallback). Dataset cleanup unchanged.
  5. Failure `timeout | unreachable | busy` → newest row with `data_version LIKE 'v{ver}-d%'`
     for the same report/key/kind and `created_at ≥ now − 24 h` → returned with
     `freshness.stale = true`, `freshness.stale_reason = <code>` and the original `queried_at`;
     else `ApiError(503, "source_unavailable" | "source_timeout" | "source_busy", message)`.
     `not_allowed`, `structure_changed`, `product_table` → `ApiError(409, code, message)` (no
     stale: the report itself is wrong).
- ETag `"{version}-{key}"` (stale → the stale row's version + `-stale`).
- `/api/reports/{id}/version` for direct returns `{data_version: v{ver}-d{bucket}, updated_at:
  null}` without touching the source → the 015 "Al llegar datos nuevos" mode (polls every 60 s)
  refreshes exactly once per `cache_seconds` bucket (FR-010).
- Narrative (`kind=narrative`) uses the bucket version; `filter_options` for direct runs live
  through the runner (one session, no cache) with the same error mapping.
- Shared links (`api/shared.py`) and email sends (`mail/sends.py`) already call
  `reports._data` → same cache; `mail/sends.py` maps a 503 without stale to a failed delivery
  with the Spanish message.

### 6. Source flag, step-up, audit (`backend/app/sources/service.py`, `api/sources.py`, FR-006)
- `data_source.direct_reports boolean NOT NULL DEFAULT false` +
  `CHECK (direct_reports = false OR kind = 'postgresql')`.
- `SourceIn`/`SourcePatch` gain `direct_reports: bool | None`; create/update refuse it for other
  kinds (422 "Solo las fuentes PostgreSQL admiten reportes directos"); a kind change away from
  PostgreSQL resets it; every change records audit `source_direct_reports_changed`
  (`{source, value}`). PATCH already requires `recent_reauth` (step-up view, no modal).
- `to_json` adds `direct_reports`. Name `bi` (case-insensitive) is reserved for new or renamed
  sources ("«bi» está reservado para la base de datos BI de la instalación"); a legacy source
  already named `bi` keeps working for integrations; in `direct.source` `bi` always means the BI
  database.
- `GET /api/sources/bi/describe` → `direct.describe_bi()` when `DIRECT_REPORTS_BI` (same shape as
  `describe.postgresql`, logical names, product tables and reserved schemas removed,
  `has_table_privilege` filter), audited `source_described`.

### 7. Backend validation wiring (`direct.validation_context`, FR-011)
- `validation_context(db, app) -> wsv.DirectContext`: sources from `data_source`,
  `bi_enabled`, `product_tables()`, `personal_kind` (from `app.assistant.personal`), and
  `structure(source, tables)`: one targeted query per source (`information_schema.columns` +
  `pg_class` existence + `has_table_privilege`, filtered to the declared `(schema, table)` pairs,
  physical mapping for `bi`) in a read-only session with a 10 s timeout; errors → `{"error":
  text}`.
- Used by `workspace/service.validate_root`, `assistant/tree.validate_draft` and
  `assistant/tree.materialize` (every `wsv.validate` call site).

### 8. Authoring pack, golden example, agent tools, preview (FR-012, FR-013, US3)
- `cli/bizview_cli/golden-direct/`: `bizview.yaml`, `specs/reports/001-ventas-directo/
  {spec,plan,tasks}.md` (with the five direct lines and `**Volumen esperado**: ~1 M filas`),
  `reports/ventas-directo/report.yaml` (`direct: {source: bi, tables: {v: {table:
  public.bi_ventas, columns: fecha date, sucursal text, producto text, monto numeric, unidades
  integer}}, cache_seconds: 300}`, kpis, trend, ranking, table, filters, `pdf.enabled`).
  `authoring.GOLDEN["example-direct"] = "golden-direct"`, `TOPICS` entry, `GOLDEN_SOURCES`
  `bi`. `RULES` adds verbatim: "usa modo directo solo si el usuario indica que los datos ya están
  preparados por otro proceso; si no, crea una integración", plus the spec-lines rule and "un
  reporte usa `uses` o `direct`, nunca ambos". `_report_summary()` adds "exactamente uno de: uses |
  direct" and the `direct` keys/limits (generated from the schema). Preset
  `workspace_template/preset/templates/spec-template.md` gains an optional "Direct mode" block.
- Tools (`backend/app/assistant/tools.py`, `origin.py`):
  - `list_sources` adds `direct: bool` per source and a `bi` entry (`kind: postgresql`, label
    "BI de esta instalación") when `DIRECT_REPORTS_BI`.
  - `describe_source("bi")` → `direct.describe_bi()` (+ personal flags, working-state cache).
  - `profile_source("bi", table)` → same aggregate-only profile on the BI read-only path with the
    deny-list; any profile whose `row_count` > `DIRECT_REPORT_WARN_ROWS` adds `warning`: "más de
    N filas: un reporte directo necesita un índice en la columna de fecha; considera una
    integración".
  - `check_query(source, path="reports/<id>/report.yaml")` for a direct draft: builds the draft
    context, takes the first `kpis` view (or every `sql` metric) for the default period, wraps
    it `SELECT * FROM (<stmt>) AS q LIMIT 0`, runs it through `DirectRunner` (slots + log, no
    cache) and returns column names/types or the redacted error; stored in
    `session.query_checks[path]` with the file sha. `recheck_draft` (apply) also re-checks direct
    report files.
- Preview (`assistant/preview.py`): `run_draft_preview` also renders each draft direct report
  once live (`run_views` through the runner, no cache, no schema) → `session.preview["reports"]
  [rid] = {status, message, duration_ms}`; status `succeeded` only if all integrations and
  direct reports succeed. `_context()`/`report_data()` support direct definitions
  (`engine.preview_context` already goes through `_build_context`); freshness `{mode: "direct",
  source, queried_at, stale: false}` + "Vista previa" (UI and PDF as today).
- Readiness (`assistant/readiness.py`) for a draft direct report: pending when (a) no passing
  `check_query` for the current sha of `report.yaml`, (b) validation carries
  `direct_structure_unchecked` for it, (c) preview not succeeded for the fingerprint, (d) a
  flagged personal contract column is used without the 017 confirmation + spec line. The
  integration-only rules (primary_key, incremental, checks) do not apply.

### 9. UI (`frontend/src`, FR-010, FR-014, US2 AC1)
- `api/types.ts`: `ReportData.freshness` gains optional `mode`, `source`, `queried_at`, `stale`,
  `stale_reason`; `ReportDefinition.direct?`; `DataSource.direct_reports`; workspace
  `report_details`; security `direct_reads`.
- `lib/freshness.ts` `freshnessText(data, def)` used by `ContextBlock.tsx` and `TvLayout` caller in
  `ReportView.tsx`: direct → "Datos en vivo · {fuente} · consultado {hora}"; stale → inline
  `Alert tone="warning"` "Datos de {hora}; la fuente no respondió" (ReportView and
  SharedDashboard). Errors 503/409 shown inline with the server message (no modal).
- `AutoRefreshControl.tsx`: for direct reports the "Al llegar datos nuevos" option shows the hint
  "cada {n} min".
- `pages/admin/SourceForm.tsx`: switch "Permitir reportes directos" (PostgreSQL only, help text
  explaining the exception); saving goes through the existing step-up view. `Sources.tsx`: badge
  "Reportes directos" on the card.
- `pages/admin/Workspace.tsx`: card "Reportes" listing each report with badge Dataset/Directo,
  source, tables and a red "Estructura cambiada" badge when broken.
- `pages/admin/Security.tsx`: section "Lecturas directas (24 h)" per source (total, fallidas).
- All new strings in `i18n/es.ts`; 375 px first; WCAG AA; dark tokens.

### 10. Logging and security overview (FR-015)
- `GET /api/workspace` adds `report_details: [{id, mode: "dataset"|"direct", source, tables,
  status: "ok"|"broken"|"failing"|null, last_read_at}]` (status from the newest
  `direct_read_log` row of the report: `structure_changed`/`product_table` → broken; `timeout`/
  `unreachable`/`busy` → failing).
- `GET /api/security` adds `direct_reads: [{source, total, failed}]` over the last 24 h.

## API changes

| Route | Change |
|---|---|
| `GET /api/reports/{id}` | `direct: {source, cache_seconds}` for direct reports only |
| `GET /api/reports/{id}/data` | direct: freshness `mode, source, queried_at, stale, stale_reason`; 503 `source_unavailable`/`source_timeout`/`source_busy`, 409 `direct_not_allowed`/`direct_structure_changed`/`direct_product_table` |
| `GET /api/reports/{id}/version` | direct: bucket version, no source access |
| `GET /api/reports/{id}/filters/{dim}` | direct: live via runner, same errors |
| `POST /api/reports/{id}/pdf`, `/api/shared/{token}/*` | unchanged contract; direct footer line in PDF |
| `GET/POST/PATCH /api/sources…` | `direct_reports` field (PostgreSQL only; PATCH step-up; audited) |
| `GET /api/sources/bi/describe` | BI database structure without product tables |
| `GET /api/workspace` | `report_details` |
| `GET /api/security` | `direct_reads` |
| Assistant tools | `list_sources.direct`, `describe_source/profile_source("bi")`, `check_query(path=reports/<id>/report.yaml)` |

## Migration `0015_direct_reports` (Claude implements)
- `data_source.direct_reports boolean NOT NULL DEFAULT false` + check
  `ck_data_source_direct_reports_kind`.
- `direct_read_log(id bigint identity PK, occurred_at timestamptz NOT NULL DEFAULT now(),
  report_id text NOT NULL, source text NOT NULL, duration_ms integer NOT NULL, rows integer NOT NULL
  DEFAULT 0, outcome text NOT NULL CHECK IN ('ok','timeout','unreachable','busy',
  'structure_changed','not_allowed','product_table','error'), stale_served boolean NOT NULL
  DEFAULT false)`; indexes `(occurred_at DESC)`, `(report_id, occurred_at DESC)`.
- Audit kinds + `source_direct_reports_changed` (same constraint rewrite pattern as 0013).
- Downgrade drops table, column and check; restores the kind check (refuses if rows of the new
  kind exist). The table is an addition to the brief's column list: FR-015 needs a 24 h count
  shared by every backend process.

## Tests (focused per task; full suites once at the end of the queue)
- CLI: schema oneOf uses/direct (branch errors), materialize, offline deny patterns, spec lines,
  structure check from describe files (missing table/column, type map, date), golden-direct
  validates, summary covers `direct`.
- Backend: US1 independent test (seeded table, KPIs/trend/ranking/table/filters/PDF, no `ds_*`
  created, new row visible after the bucket with a patched clock, cached within); SC-003 deny-list
  over every `Base.metadata` table via `public.<name>` + a BI view over `app_user` refused +
  statement spy (only SELECT inside read-only transactions); flag/step-up/audit/kind reset/reserved
  name; flag off after apply → 409 without connecting; joins over two tables of a test PostgreSQL
  catalogue source; stale fallback + no-cache 503; timeout bound (timeout + 1 s, SC-004); busy with
  concurrency 1; single-flight (10 concurrent → 1 runner session); backoff; structure changed →
  message + workspace `broken`; internet profile refuses non-TLS; SC-005 snapshot of a dataset
  report (data, definition, version, PDF text) taken before the engine change; agent: draft only
  spec + report.yaml (fake provider), structure problems with expected shape, `check_query` on a
  report, preview + PDF, readiness; payload audit (no values) for the new tool paths;
  `/api/security` and `/api/workspace` additions; migration 0015 up/down.
- Frontend unit: freshness texts (live, stale), source toggle visibility, workspace mode badges.
- E2E `frontend/tests/e2e/direct-report.spec.ts`: seeded table → apply a direct-only workspace →
  dashboard + footer + PDF (SC-001).
- Opt-in slow: `backend/tests/test_direct_perf.py` (1 M rows, index on date; p95 cached < 200 ms,
  cold < timeout; marker `slow`).

## Risks
- **BI views/functions**: a view in the BI database may hide a product table; the dependency walk
  catches views/materialized views, not functions called inside a view (e.g. a `SECURITY DEFINER`
  function). Mitigation documented in INSTALL: run the product with a role whose rights on
  product tables are not granted to views owned by other roles; follow-up: optional
  `DATABASE_URL_BI_DIRECT` with a restricted role.
- **Identifier pattern**: column names must match `^[a-z][a-z0-9_]{0,40}$`; sources with
  upper-case or quoted names need a lower-case view on the source side (documented in the
  authoring rules).
- **Connection per cold build** for catalogue sources (no pool): adds connect + TLS latency to
  cold views; acceptable within `timeout_seconds`; pooling is a later optimisation.
- **Advisory locks** hold one BI connection per in-flight direct build; with concurrency 2 per
  source this stays far below `DB_POOL_SIZE + overflow`.
- **Source down at validation**: structure check becomes a warning so unrelated applies are not
  blocked; runtime then reports `structure_changed` if the structure really changed.
- **Spanish-only strings** until 022 converts them (brief order).

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| `direct_read_log` table (not in the brief's migration list) | FR-015 count over 24 h across all backend processes and the worker; workspace "broken" status | in-process counters reset on restart and differ per process; audit_event would flood the audit log |
| Cross-process advisory locks for slots and single-flight | `WEB_CONCURRENCY` processes + worker (email sends) all read the same source | per-process semaphore alone allows N × processes concurrent queries and duplicate queries per selection |
