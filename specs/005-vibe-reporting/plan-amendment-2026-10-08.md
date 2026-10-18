# Implementation Plan: Vibe Reporting — Amendment 2026-10-08 (Polars transform, big-data readiness)

**Branch**: `005-vibe-reporting` | **Date**: 2026-10-09 | **Spec**: [spec.md](./spec.md) (sections
"Amendment 2026-10-08" and "Amendment 2026-10-08 (owner, second part)") | **Tasks**: T029–T041

## Summary

Two additions to the integration engine and the report engine; extraction, staging, checks and the
all-or-nothing publish of feature 005/008 stay as they are.

1. **Transform stage (FR-A01–FR-A05, SC-A01)**: a dataset may declare
   `transform: {sql, input, batch_rows}`. The SQL is one read-only `SELECT … FROM input`, checked by
   sqlglot against a node and function **allow-list**, regenerated (what is checked is what runs) and
   executed by `pl.SQLContext`. Row-wise transforms run per batch between the extraction and the
   staging COPY (`copy+polars` for PostgreSQL, `rows+polars` for REST/SOAP and the row fallback).
   Whole-mode transforms (aggregation, `DISTINCT`, windows, `ORDER BY`) spill the typed window to
   Arrow IPC files, run on a lazy scan with the streaming engine into an IPC result (cancellable
   background query), then load the result in batches. Output columns/types are checked against the
   dataset `columns` at validation (empty typed frame) and again before every run's extraction.
2. **Daily rollups (FR-A06–FR-A09, SC-A02)**: `materialize: daily` on a `uses` report builds
   `ds_<base integration>.mv_<report>` = day × every dimension used by views/filters × the additive
   components of each SQL metric. Rollups are refreshed inside the run's publish transaction (under
   a savepoint) for the touched days only, rebuilt in full after full runs or changes of joined
   datasets, and built by a worker job after apply. The report engine answers KPIs, trends,
   rankings, tables and filter options from a **fresh** rollup by substituting four SQL fragments
   (FROM, date, dimension, metric) in the same query skeleton, so both paths are equal by
   construction and by a test matrix; otherwise it uses the raw path.

Migration **`0016_run_transform`** is needed (rollup state table + run column); the transform itself
needs no new columns.

## Technical Context

Python 3.12 / FastAPI / SQLAlchemy / Alembic, psycopg 3 (COPY streaming), **Polars 1.44.2** (backend
`uv.lock`; `pl.SQLContext`, `LazyFrame.sink_ipc(lazy=True)`, `collect(background=True)` →
`InProcessQuery.cancel()`, `collect_batches(engine="streaming")`, `scan_ipc`), sqlglot 30.x (postgres
dialect), jsonschema. Worker = `python -m app.worker` (same image as the backend; previews of feature
014/017 run the same `_extract` in the backend process). Tests on `DATABASE_URL_BI` (`app_test_*`
schemas); benchmarks are opt-in scripts. Behaviour of Polars 1.44 SQL used below was verified on the
installed version (2026-10-09): supported/unsupported functions, regeneration round-trip, decimal and
time-zone semantics (see §1, §2 and Risks).

**Supporting libraries**: none new in the backend. `bizview-cli` gains an **optional extra**
`transform = ["polars>=1.44,<2"]` so `bizview validate` can infer transform output columns locally;
without it the CLI reports a warning and server validation (always has Polars; it is the apply
gate) performs the check.

**Config** (`backend/app/config.py`, documented in the env example and `docs/INSTALL.md`):
`TRANSFORM_MAX_ROWS` (50 000 000, ≥ 1), `TRANSFORM_SPILL_DIR` (default
`<tempfile.gettempdir()>/bizview-transform`), `ROLLUP_TIMEOUT_SECONDS` (1800, 10–86400, worker
builds); `DIRECT_REPORT_WARN_ROWS` (existing, 5 000 000) is reused by FR-A09. `docker-compose.yml`
sets `POLARS_TEMP_DIR=/tmp/bizview-polars` for `worker` and `backend` (Polars' own spill folder).

## Constitution Check (2.0.0)

- **II (Backend as ETL, direct reads by exception)**: rollups are pre-computed models in the BI
  database; direct reports are untouched (`materialize` on a direct report stays a validation error,
  `direct_materialize`). PASS.
- **V (Fixed stack)**: Polars is already the worker's transform engine (2.0.0 amendment); no new
  component. Note: principle V says "aggregation stays in PostgreSQL SQL" while FR-A01 allows
  `GROUP BY` in whole-mode transforms. We read V as *report* aggregation (serving, rollups — both
  stay in PostgreSQL) and the transform `GROUP BY` as ETL shaping that the owner approved in FR-A01;
  propose a PATCH wording (Spec issue S10). PASS with note.
- **VI (Data tuning over raw storage)**: FR-A06 implements the preferred mechanism (daily summary
  tables) that was accepted-and-reserved since T018. PASS.
- **VIII (AI optional and private)**: no AI call is added. The agent's `check_query` returns only
  transform output **names and types** inferred on an empty frame (no values); FR-A09 hints use row
  estimates already exposed by `profile_source`. PASS.
- **IX (Spec-driven)**: the transform is declarative SQL inside `integration.yaml` (hashed in the
  lock), allow-listed, no UDFs, no files, no network; rollups derive only from the approved report
  definition and are rebuilt when it changes (definition hash). PASS.
- **Constraints**: product schema via Alembic (`0016_run_transform`); `ds_*` objects (rollups, the
  extra date index) created only by the engine; worker idempotent (window delete/insert, rebuild by
  swap) and restart-safe (everything in one transaction; stale spill folders swept at start). PASS.

## Design

### 1. Transform schema and SQL allow-list (FR-A01, FR-A03)

**Schema** (`cli/bizview_cli/schemas/integration.schema.json`, dataset property, additive, CLI minor):

```yaml
transform:
  input:                       # required: the extraction contract (query/request output)
    <column>: {type: text|integer|bigint|numeric|boolean|date|timestamptz, nullable?: bool}
  sql: "SELECT … FROM input"   # required, 1–20 000 chars
  batch_rows: 20000            # optional, 10 000–1 000 000, row-wise mode only
```

`input` is required because FR-A02 checks "from the declared input columns" and today nothing
declares them (Spec issue S1). With a transform: the extraction query (`columns_mismatch`), the
request `fields` and the COPY column list use `transform.input`; `columns` describes the transform
output = the dataset table; checks (contract, `primary_key`, `row_count`, `not_null`, `reconcile`)
run on the staged output as today; `row_count` counts output rows (`rows_in` is recorded apart).

**`sqlsafety.check_transform(sql, input_types) -> TransformCheck(problems, mode, sql)`**
(`cli/bizview_cli/sqlsafety.py`), parsed with `read="postgres"`:

- exactly one statement, an `exp.Select` (optionally with non-recursive `WITH` CTEs whose bodies
  are `exp.Select`);
- every `exp.Table` has an `exp.Identifier` as `this` (no table functions such as `read_csv` —
  Polars would read the file even during schema inference), no `db`/`catalog`, and its name is
  `input` or a CTE defined earlier; table aliases allowed;
- **allowed node classes** (anything else → `unsafe_sql "construcción no permitida: <key>"`):
  `Select, From, Where, With, CTE, Table, TableAlias, Identifier, Column, Star, Alias, Literal,
  Boolean, Null, Paren, Neg, Not, And, Or, Add, Sub, Mul, Div, Mod, DPipe, EQ, NEQ, GT, GTE, LT,
  LTE, Is, In (literal lists only), Between, Like, ILike, Case, If, Cast, TryCast, DataType,
  DataTypeParam, Interval, Var` + the function classes below; whole mode adds `Group, Having,
  Distinct, Order, Ordered, Window, Qualify`;
- **refused explicitly** (clear message): `Join`, set operations (`Union/Except/Intersect`),
  `Subquery`/scalar sub-selects, `Limit/Offset/Fetch`, `Into`, `Placeholder`/parameters, `Lateral`,
  `Values`, schema-qualified names, `Filter` (aggregate FILTER), `Anonymous` functions not listed;
- **allowed functions** (sqlglot `_function_name`, each verified to run on Polars 1.44 after
  regeneration):
  - math: `abs, ceil, floor, round, sign, sqrt, power, ln, exp, greatest, least` (`mod()` parses
    to `%`);
  - conditional: `coalesce` (incl. `ifnull`), `nullif`, `if`, `case`;
  - text: `lower, upper, trim` (incl. `ltrim/rtrim`), `length` (incl. `char_length`), `concat,
    concat_ws, left, right, substring` (incl. `substr`), `replace, split_part, str_position`
    (`strpos`), `starts_with, ends_with, initcap, reverse, regexp_like, pad` (`lpad/rpad`);
  - date/time: `extract` (incl. `date_part`), `strftime`, `strptime`; casts `cast` (incl. `::`),
    `try_cast`;
  - whole mode only — aggregates `sum, count` (incl. `count(DISTINCT …)`), `avg, min, max`;
    window functions `row_number, rank, dense_rank, lag, lead, first_value, last_value` and the
    aggregates with `OVER`.
  - Not offered (unsupported by Polars 1.44 or order/time dependent): `date_trunc, current_date,
    now, random, md5, to_date, timestamp(), median/percentile_*, string_agg, array_agg, first,
    last`. The authoring guide shows the replacements (`strftime(d, '%Y-%m-01')`, `extract`).
- **Mode detection**: `whole` when the tree contains any `Group, Having, Distinct, Window, Qualify,
  Order` or an `AggFunc` outside a `Window`; else `rows` (`WHERE` keeps row-wise mode). Recorded
  as `transform_mode`.
- **Regeneration**: `TransformCheck.sql` = `tree.sql(dialect=PolarsSQL, identify=True)` where
  `PolarsSQL` is a 10-line sqlglot dialect subclassing Postgres that renders `TryCast` as
  `TRY_CAST(x AS t)` (plain Postgres output silently turns it into a strict `CAST`). Only this text
  is ever given to Polars (validation and runtime), so parser differences cannot smuggle constructs.

### 2. Output-column validation and type mapping (FR-A02, FR-A05)

Shared module **`cli/bizview_cli/transform.py`** (imports Polars lazily; used by `validate.py`, the
backend engine and the assistant):

- `input_schema(input_cols, tz) -> dict[str, pl.DataType]`, `infer(check, input_cols, tz) ->
  dict[str, pl.DataType]`: `pl.SQLContext(input=pl.DataFrame(schema=…).lazy())
  .execute(check.sql).collect_schema()`; Polars errors → issue `transform_invalid` with the first
  line (no values exist on an empty frame).
- `compare(inferred, columns) -> list[problem]`: names must equal the `columns` keys exactly
  (missing / extra listed); each dtype must be accepted for the contract type:

| Contract type | Input frame dtype (transform reads) | Output dtypes accepted |
|---|---|---|
| text | `String` | `String` |
| integer | `Int32` | `Int8/16/32`, `UInt8/16` |
| bigint | `Int64` | all `Int*`, `UInt8/16/32` |
| numeric | `Decimal(38, 9)` | `Decimal(*)`, all `Int*`/`UInt8/16/32`; `Float32/64` → **warning** `transform_float` ("usa CAST(x AS DECIMAL(38, 9))") |
| boolean | `Boolean` | `Boolean` |
| date | `Date` | `Date` |
| timestamptz | `Datetime("us", <integration tz>)` | `Datetime` tz-aware (any zone) or naive (= wall time in the integration zone, as PostgreSQL parses it in the run session) |

- **Time-zone rule**: Polars `CAST(<tz-aware> AS DATE)` returns the **UTC** date while `EXTRACT`
  and `strftime` use the local zone (verified). For every `Cast`/`::` to `DATE`, validation probes
  the operand dtype on the empty frame (same scope, projections replaced by the operand); a
  tz-aware `Datetime` operand → error `transform_tz_date`, fix
  `CAST(strftime(<expr>, '%Y-%m-%d') AS DATE)`.
- `validate.py` (`_check_integration`): `check_transform` problems; then, when Polars is importable,
  infer + compare (issues with `file`, `path=/datasets/<ds>/transform/sql`, `expected` = contract
  types, `fix`); when not importable, one warning `transform_unchecked` ("instala
  bizview-cli[transform]"). Also: request `fields` and the incremental `:window_*` rules unchanged;
  with a transform, `date_column`/`primary_key` must be output columns (already enforced through
  `columns`).
- Runtime re-check: the engine runs the same infer + compare **before extraction starts**; a
  mismatch fails the run with no load (stronger than "before any load").
- Assistant (`backend/app/assistant/origin.py`, `_dataset_for` / `run_check`): when the checked
  query/request feeds a dataset with a transform, `missing/extra` compare with `transform.input`,
  and the result adds `transform: {mode, columns: [{name, type}], problems}` from §2 (types only).

### 3. Runtime (FR-A03, FR-A04, FR-A05)

New **`backend/app/engine/transform.py`**:

- `compile(ds, tz) -> Compiled | None` (check + expected dtypes + infer/compare; raises
  `ExtractError` with a safe message).
- `parse_text(frame_str, compiled) -> pl.DataFrame`: all-`String` frame → typed input. Text: PG
  `COPY … (FORMAT text)` escapes un-done vectorised (`\\`→`\x00` sentinel, then `\t \n \r \b \f \v`,
  then sentinel→`\`; PostgreSQL text never contains NUL); integer/bigint strict cast; numeric
  `cast(Decimal(38, 9))`; boolean `t/f/true/false/1/0`; date `%Y-%m-%d`; timestamptz first of
  `%Y-%m-%d %H:%M:%S%.f%#z`, `%Y-%m-%dT%H:%M:%S%.f%#z`, naive (localized to the integration zone),
  then `convert_time_zone(tz)`. Any value that was non-null and became null → `ExtractError`
  ("la columna X no cumple el tipo declarado en transform.input").
- `CopyTextSplitter(on_batch, columns, batch_rows)`: receives arbitrary COPY blocks, cuts at the
  `batch_rows`-th `\n` (text format escapes embedded newlines, so every `\n` ends a row), parses with
  `pl.read_csv(separator="\t", quote_char=None, has_header=False, null_values=["\\N"],
  infer_schema=False)` and calls `on_batch`.
- `Sink(compiled, write, check, deadline, spill_dir, max_rows)`:
  - **rows mode**: `add(frame)` → `parse_text` → `SQLContext(input=batch.lazy()).execute(sql)
    .collect()` → dtype check against the compiled output schema → `write(out)` in 50 000-row
    slices → `check()`; buffers are released before the next batch (memory = one raw batch + one
    typed batch + one output slice).
  - **whole mode**: `add(frame)` → `parse_text` → `write_ipc(<spill>/<run>-<ds>/in-%05d.arrow)`;
    `rows_in += n`; `rows_in > TRANSFORM_MAX_ROWS` → `ExtractError("la transformación superó
    TRANSFORM_MAX_ROWS (…) filas; usa un transform por filas o reduce la ventana")`. `finish()`:
    `SQLContext(input=pl.scan_ipc(<in-*.arrow>)).execute(sql).sink_ipc(<out.arrow>, lazy=True,
    engine="streaming")` → `.collect(background=True)`; poll `fetch()` every 0.25 s calling
    `check()` and the deadline; on stop/time-out `cancel()` then raise. Then
    `pl.scan_ipc(out).collect_batches(chunk_size=batch_rows, engine="streaming")` → dtype check →
    `write` → `check()` between batches. The streaming engine spills blocking operators under
    `POLARS_TEMP_DIR`. `finally`: `shutil.rmtree` of the run folder.
  - `transform_ms` = wall time inside parse + SQL + serialisation (excludes origin wait and COPY-in).

**Wiring in `backend/app/engine/runner.py`** (`_extract`, used by `run_integration` and
`run_preview`):

| Source / path | No transform (unchanged) | With transform |
|---|---|---|
| PostgreSQL, COPY accepted | `copy` (was `bulk`): origin COPY → staging COPY | `copy+polars`: `extract.pg_copy(columns=input, write=splitter.write, check=stop)` → `Sink` → `_copy(pg, staging, columns, frame)` (CSV, `NULL '\N'`) |
| PostgreSQL, COPY refused (`BulkUnsupported`) | `rows` | `rows+polars`: `extract.pg_rows` → `_text_frame(rows, got)` → `Sink.add` |
| REST / SOAP / Supabase | `rows` | `rows+polars`: `fn(…, columns=input)` → `_text_frame` → `Sink.add` |

- `compiled = transform.compile(ds, tz)` runs first (before `extract.*`), so contract mismatches
  never touch the origin.
- Stop requests (013): `check` (the `StopFlag`) is called per COPY block (existing), after every
  batch, during the whole-mode background poll, and between output batches; the watchdog still
  cancels origin/destination statements. Errors after a stop are recorded as `stopped` (existing
  logic).
- `Plan` gains `transform_mode: str | None`, `rows_in: int`, `transform_ms: int`, plus rollup fields
  (§4). `Plan.path` values: `copy`, `rows`, `copy+polars`, `rows+polars`; legacy `bulk` in old run
  rows is read as `copy` by the API/UI.
- **Run history** (no new column): `_finish` writes per dataset in `integration_run.rows`:
  `{extracted, written, full, path, fallback?, transform_mode?, rows_in?, transform_ms?}`.
  `frontend/src/pages/admin/Integrations.tsx` shows `COPY`, `COPY + Polars`, `filas`,
  `filas + Polars`, the transform time and mode (`frontend/src/api/types.ts`, i18n catalogues `es`
  and, when feature 022 has landed, `en`).

### 4. Daily rollups (FR-A06, FR-A07)

**Shared decomposition** — new **`cli/bizview_cli/materialize.py`** (pure sqlglot; used by
`validate.py` and `backend/app/engine/rollup.py`):

- `decompose(metric_sql) -> Decomposition(components, template) | problems`. Each aggregate node
  of the metric expression becomes a component; the expression outside aggregates (scalar math,
  `coalesce`, `round`, `CASE` over aggregates, literals) is kept as a template.

| Aggregate in the metric | Component column(s) built from raw rows | Recomposed over the rollup |
|---|---|---|
| `sum(e)` | `sum(e)` | `sum(c)::<type of c>` |
| `count(*)`, `count(e)` | `count(…)` | `coalesce(sum(c), 0)::bigint` |
| `min(e)` / `max(e)` | `min(e)` / `max(e)` | `min(c)` / `max(c)` |
| `avg(e)` | `sum(e)`, `count(e)` | `sum(s)::numeric / nullif(sum(n), 0)` |
| aggregate with `FILTER (WHERE …)` | the filtered aggregate as is | as its kind |

  `e` is any row-level expression (the argument stays whole inside the component), so
  `sum(case when l.tipo = 'devolucion' then -l.monto else l.monto end)` is one `sum` component:
  the rollup groups are a partition of the raw rows and every filter/dimension used later is a
  grouping column, so sums of partial sums equal the raw sum. The cast to the component's column
  type (read from the built table and stored in `report_rollup.columns`) keeps PostgreSQL result
  types (e.g. `sum(integer)` is `bigint`, so `sum(a)/count(*)` stays an integer division as on the
  raw path). Components are deduplicated by canonical SQL; column name `c_<sha1(canonical)[:12]>`.
  Formulas are unchanged (evaluated in Python over metric values).
- **Ineligible** (validation error `materialize_ineligible`, `path=/metrics/<id>/sql` or
  `/dimensions/<id>/sql`, reason + fix): any aggregate with `DISTINCT` (incl. `count(distinct …)`;
  fix: "si la columna es la clave primaria del conjunto base y las uniones no repiten filas, usa
  count(*); si no, quita materialize"), `percentile_cont/disc, stddev, variance, group_concat
  (string_agg), logical_or/and`, window functions, nested aggregates, a column outside any aggregate,
  `current_date` anywhere in metrics or dimensions, and aggregate functions inside a dimension used
  by views/filters (Spec issue S3).

**Table and DDL** (`backend/app/engine/rollup.py`):

- Name `ds_<base integration>.mv_<report id with '-' → '_'>` where the base integration owns the
  dataset of the report's `date` alias (report ids have no `_`, so the mapping is injective; ≤ 53
  chars) (Spec issue S2).
- Columns: `day date NOT NULL` (= the report's `date_expression`, `(col)::date` for timestamptz
  computed with `SET LOCAL TimeZone = <installation zone>` — the zone the report API uses),
  `k_<dimension id>` for every dimension used by any view (`ranking.dimension`,
  `table.dimensions`) or `filters` (native type of the expression), and the component columns.
- Build: `CREATE TABLE <schema>.mv_<r>__new AS SELECT <day>, <dims>, <components> FROM
  <report.from_clause> GROUP BY 1..n`; `CREATE INDEX … (day)`; `DROP TABLE IF EXISTS mv_<r>`;
  `ALTER TABLE … RENAME TO mv_<r>`. The build also creates, if missing, an index on the base
  dataset's report date column (`ix_<dataset>_<col>`) so windowed refreshes do not scan the table.
- Windowed refresh: `DELETE FROM mv WHERE day = ANY(%(days)s)`; `INSERT INTO mv SELECT … FROM
  <from_clause> WHERE <date_expr> = ANY(%(days)s) [AND <col> >= %(lo)s AND <col> < %(hi)s] GROUP
  BY …` (the range guard keeps a timestamptz date sargable).

**State** — migration **`backend/alembic/versions/0016_run_transform.py`** (revises
`0015_direct_reports`; name kept because 020/022 already chain on it):

- table `report_rollup`: `report_id text PK`, `schema_name text NOT NULL`, `table_name text NOT
  NULL`, `definition_hash text NOT NULL` (sha256 of the canonical rollup definition: uses, joins,
  date, metric SQL, used dimensions, dataset column contracts), `status text NOT NULL CHECK (status
  IN ('ready','stale','failed'))`, `source_runs jsonb NOT NULL DEFAULT '{}'` (integration id → id of
  the last run whose data the rollup includes), `columns jsonb NOT NULL DEFAULT '{}'` (component →
  PostgreSQL type), `rows bigint NULL`, `built_at timestamptz NULL`, `refreshed_at timestamptz
  NULL`, `refresh_ms integer NULL`, `error text NULL`, `updated_at timestamptz NOT NULL DEFAULT
  now()`;
- `integration_run.rollups jsonb NOT NULL DEFAULT '{}'::jsonb` (report id → `{mode:
  window|full, days, rows, ms, ok, error?}`);
- `backend/app/models.py`: `ReportRollup`, `IntegrationRun.rollups`; downgrade drops both; up/down
  test in `backend/tests/test_migrations.py`.

**Refresh after a run** (`runner._run`, after the `_load` loop, before `pg.commit()`):
`rollup.after_load(pg, run, iid, plans, version_id, app, deadline, stop)`:

1. Reports = active-version (`version_id`) reports with `materialize: daily` whose `uses` include
   `iid`, sorted by id. None → no-op.
2. Touched days are captured in `_load` **before** its delete (hook `rollup.capture`), only for
   base datasets of those reports: report-date values (`(col AT TIME ZONE <installation zone>)::date`
   for timestamptz) of target rows in the delete condition ∪ target rows whose primary key is in
   staging (old dates of upserted rows) ∪ staged rows (new dates). For non-base datasets used by
   those reports: an `md5` fingerprint of the used columns before/after the load when the table has
   ≤ 1 000 000 rows (`pg_class.reltuples`), else "changed".
3. Per report: `pg_advisory_xact_lock(lock_key('rollup', report_id))` (serialises refreshes of a
   report used by two integrations), `SAVEPOINT`, `SET LOCAL statement_timeout` = remaining run
   time, `SET LOCAL TimeZone` = installation zone. **Window mode** only when: row exists,
   `status = ready`, hash matches, `source_runs[iid]` = the previous succeeded run of `iid` (no gap),
   the base dataset belongs to `iid` and was loaded incrementally, and no non-base dataset of the
   report changed. Otherwise **full** (full run, rebuilt dataset, stale/missing rollup, joined
   dataset changed, definition changed).
4. Success → `report_rollup` upsert `status=ready, source_runs[iid]=run.id` (full rebuild: other
   integrations' entries = their latest succeeded run), `refreshed_at`, `rows`, `refresh_ms`;
   `run.rollups[report] = {ok: true, …}`.
5. Failure → `ROLLBACK TO SAVEPOINT` (previous rollup rows kept), upsert `status=stale,
   error=<safe message>`, `run.rollups[report] = {ok: false, error}`; the data still publishes and
   the run ends `succeeded` with message "datos publicados; resumen diario no actualizado: <ids>"
   (FR-A07 "marks the run"; Spec issue S4). A stale rollup is never read (§5) and the next run of
   any of its integrations rebuilds it in full. A stop request during refresh stops the whole run
   (nothing published), as for any other stop.

**Build after apply** (`backend/app/worker.py`): when `reload()` sees a new active version (apply
or rollback), and then every loop while some rollup is pending (at most once per 60 s), the pool
runs `rollup.ensure_version(version_id)`: for each `materialize: daily` report with no row, a hash
mismatch, a missing table (`to_regclass`), or `status != ready` → try the integration advisory locks
(`runner._lock_key`) of all its integrations (session-level, all or none; busy → retry later, so a
build never overlaps a run), then build in one transaction with `statement_timeout =
ROLLUP_TIMEOUT_SECONDS` and `source_runs` = latest succeeded run per integration. Rollups of reports
that are no longer materialized in the active version are dropped and their rows deleted. Failures
set `status = failed` with the error (shown on Administración → Workspace next to the report).

### 5. Report engine routing and equivalence (FR-A08)

- `backend/app/engine/report.py`: a `Source` with four fragments — `from_()`, `date()`,
  `dimension(id)`, `metric(id)`. `RawSource` = today's `from_clause`, `date_expression`,
  `expression(dimension.sql)`, `expression(metric.sql)`. `RollupSource` = `<schema>.mv_<r> AS r`,
  `r.day`, `r.k_<id>`, the recomposed metric SQL (built once per definition hash and cached like
  `cached_context`). `aggregate`, `_where`, `_bucket_expr`, the four views and `filter_options`
  take the source instead of building fragments themselves; the query skeleton (`BETWEEN` on the
  date, `(dim)::text IN (…)`, `GROUP BY` ordinals, `ORDER BY m DESC NULLS LAST, 1`, `LIMIT`,
  `::text = ANY(keys)`, `date_trunc(grain, date)::date`) is shared, so the only difference between
  paths is those fragments.
- Routing per view: `kpis` (current and comparison) → rollup; `trend` (day/week/month, auto
  resolved) → rollup; `ranking` (ranked rows, comparison keys, total) → rollup; `table` → rollup
  (every `table` view of the current schema aggregates by dimensions; no raw-row table exists, Spec
  issue S5); `filter_options` → `SELECT DISTINCT (r.k_<dim>)::text … WHERE r.day BETWEEN …`;
  narrative and PDF reuse `aggregate`/`run_views` and follow. Direct reports and assistant previews
  (`preview_context`) never route to rollups.
- **Freshness** (global, the rollup covers all days): `status = ready` ∧ `definition_hash` = hash of
  the active definition ∧ `source_runs` = `{iid: max(id) of succeeded runs}` for every used
  integration. Resolved in the same round trip as the cache lookup (`data_version_and_cached` joins
  `report_rollup` and a per-integration `jsonb_object_agg` of max run ids); `api/reports.py`
  `filter_options` does the same lookup. The route is attached to a per-request copy of the cached
  `Context` (`dataclasses.replace`), never to the shared one. Cache keys do not change (results are
  equal).
- **Fallback**: not fresh → raw path. `UndefinedTable/UndefinedColumn` on a rollup query → mark the
  row `stale` (own short transaction), log, rerun that view on the raw path.
- **Equivalence**: grouping by day × all used dimensions is a partition of the raw rows; every
  WHERE term is a predicate on grouping columns; recomposition is exact for `sum/count/min/max`
  (with the type casts above) and identical PostgreSQL `numeric_div` for `avg`. Tests assert exact
  equality of `sum/count/min/max` values and keys/order of rankings and tables; `avg` and formulas
  compare as floats with `rel_tol=1e-12` (both paths go through `_number()`; Spec issue S6).

### 6. Authoring pack, golden example, agent rules (FR-A05, FR-A09)

- `cli/bizview_cli/authoring.py`: topic `transform` (schema fragment, allow-list from
  `sqlsafety`, mode rules, type table, time-zone rule, replacements for missing functions, Decimal
  notes) and topic `example-large` → new golden workspace `cli/bizview_cli/golden-large/` (source
  `origen_ventas`): integration `pedidos` with a row-wise transform (`upper(trim(moneda))`,
  `coalesce(impuesto, 0)`, `monto_neto + coalesce(impuesto, 0) AS monto_total`, `CAST(strftime(
  creado_en, '%Y-%m-%d') AS DATE) AS fecha`) and report `pedidos-dia` with `materialize: daily`
  (metrics only `sum/count/avg`; its spec states the expected volume). The main `golden` stays
  without `materialize` (its `count(distinct …)` metric is the documented example of an ineligible
  metric). `summary()` mentions `transform` and `materialize`.
- Rules (`RULES`): "propón `materialize: daily` en reportes sobre conjuntos de más de 5 millones de
  filas (estimación de `profile_source` o del conjunto publicado)"; "usa `transform` solo cuando la
  consulta de origen no puede dar la forma (fuentes REST/SOAP, limpieza)"; fixes the existing rule
  that said "integración con `materialize: daily`" (materialize is a report key).
- **FR-A09 validation**: `validate.DirectContext` (the existing live context) gains
  `dataset_rows: Callable[[str, str], int | None]`; `backend/app/engine/direct.py` provides it from
  `pg_class.reltuples` of `ds_<iid>.<dataset>`. `_check_report` adds warning
  `materialize_recommended` when a `uses` report without `materialize: daily` has a dataset above
  `warn_rows`. Offline CLI has no estimate and stays silent (Spec issue S7). The assistant already
  hints from `profile_source` (`origin.py`).

### 7. Tests and benchmarks

- **CLI** (`cli/tests/test_transform.py`, `cli/tests/test_materialize.py`): every allowed function
  passes and runs on Polars after regeneration; refusals (table functions, `read_csv`, joins, set
  ops, sub-queries, `LIMIT`, parameters, qualified names, unknown/`Anonymous` functions); mode
  detection per construct; `TRY_CAST` survives regeneration; output mismatch (missing, extra, type),
  float→numeric warning, tz date error, warning without Polars; schema bounds of `batch_rows`;
  decomposition table above incl. CASE-wrapped sums and outer expressions; every ineligible reason;
  `golden-large` validates; `materialize_recommended` with a fake `dataset_rows`.
- **Backend** (`backend/tests/test_transform.py`): `parse_text` (escapes, `\N`, quotes, tz offsets
  `-04`/`+05:30`, fractional seconds, decimals, booleans); splitter across block boundaries;
  `copy+polars`, `rows+polars` (COPY refused, REST stub) produce the same table as the SQL-only
  equivalent; batch vs whole equal results for a row-wise SQL forced to whole (`ORDER BY`);
  `TRANSFORM_MAX_ROWS` error; stop between batches and during the whole-mode poll (status
  `stopped`, nothing loaded, spill folder removed); contract mismatch fails before extraction;
  run `rows` JSON fields; preview runs the transform. Existing `"bulk"` assertions become `"copy"`.
- **Backend** (`backend/tests/test_rollup.py`): fixture integration (lines + products join, NULL
  dimension values, timestamptz date crossing midnight in the installation zone, integer and
  numeric columns) and a report using every view type; for each view × period preset × comparison ×
  filter combination × trend grain: rollup result == raw result. Windowed refresh changes only
  touched days (incl. a PK row moving from an old day); unchanged joined dataset → window mode,
  changed → full; full run → full; failed refresh (forced error) keeps previous rows, marks `stale`,
  run `succeeded` with message, reads fall back to raw; next run rebuilds; `ensure_version` builds
  missing, rebuilds on hash change, drops removed; lock serialisation of two integrations; missing
  table → stale + raw fallback; direct reports/previews never route. `backend/tests/
  test_migrations.py`: 0016 up/down.
- **Frontend unit**: path labels incl. legacy `bulk`, transform time, rollup outcome line.
- **Benchmarks (opt-in, not in CI)**: `backend/scripts/bench_extract.py` adds modes `copy+polars`
  (row-wise `SELECT id, upper(txt) AS txt, amount * 2 AS amount, ts, d, flag, js FROM input`) and
  `whole` (same SQL + `ORDER BY id`), each in its own process; SC-A01 = (copy+polars seconds / copy
  seconds − 1) ≤ 30 % and peak MB < 300 at 1 M rows; results appended to
  `specs/008-fast-pg-extraction/research.md` with the machine description (also on a LAN/host
  origin, since the 2026-10-01 numbers were network-bound). New `backend/scripts/bench_rollup.py`
  (`BENCH_ROWS`, default 5 M, 50 M for SC-A02): throwaway schema in the BI database, dataset via
  `datasets.ensure_table`, synthetic 3 years × 500 dimension combinations, report with all view
  types; measures full build, windowed refresh after a 7-day incremental change (< 30 s) and 20
  cold view runs per type on rollup vs raw (p95 < 1 s); results and the reference machine recorded
  in `specs/005-vibe-reporting/research.md` (new section R11).

### 8. Risks

- **Polars SQL drift**: function support and semantics change between versions → backend pinned by
  `uv.lock`, CLI extra `<2`; the allow-list test runs every function on the installed Polars, so an
  upgrade that breaks one fails CI.
- **Decimal semantics**: input numeric is `Decimal(38, 9)` (values with more than 9 decimals are
  truncated; ≥ 29 integer digits overflow); Polars `ROUND` on decimals differs from PostgreSQL at
  exact halves (`2.205 → 2.20`) → the guide says to round in report metrics (PostgreSQL), not in the
  transform.
- **Memory (SC-A01 < 300 MB)**: baseline process is ~137 MB; one 200 000-row batch of the benchmark
  shape is ~30 MB of text → raw + typed + output ≈ 100–130 MB. Mitigations: output serialised in
  50 000-row slices, buffers released per batch; if the benchmark exceeds 300 MB, the default stays
  (spec) and the slice size is reduced.
- **Whole-mode resources**: input window spilled to disk (≈ Arrow size of the window) plus Polars'
  own spill; disk must hold it (documented in INSTALL). Some operators may fall back to in-memory in
  the streaming engine → `TRANSFORM_MAX_ROWS` is the safety stop. Stop latency during the background
  query is ≤ 0.25 s (cancel), but Polars may finish its current morsel.
- **Rollup cardinality**: high-cardinality dimensions (customer name) make rollups approach raw size
  → validation warning `materialize_large` when a used dimension is a raw text column of a dataset
  above `warn_rows` (live only); the benchmark documents the reference shape.
- **Full rebuild cost**: a changed joined dataset forces a full rebuild inside the run (minutes at
  50 M rows) → bounded by the run time limit; a time-out marks the rollup stale (raw path) and the
  worker job rebuilds it outside the run. Builds hold the integration locks, so a scheduled run that
  fires meanwhile is recorded `skipped`.
- **Freshness gap**: between a run's commit and `_finish`, and after a crash that leaves a published
  run marked `failed`, `source_runs` ≠ latest succeeded run → raw path (correct, slower) until the
  next run.
- **CSV `\N` edge case** (existing in `_copy`): a text value equal to `\N` loads as NULL; unchanged.

**Amendment 2026-10-12 (benchmark, T041b/T042)**: the same-host benchmark changed both knobs it
left open. `parse_text` no longer re-evaluates every cast for its declared-type check (the check
reads the materialised typed frame: `transform_ms` for 1 M rows went 654 ms → 287 ms at 200 000
rows per batch) and a batch read from COPY text without a backslash skips the unescape pass
(`CopyTextSplitter` decides per batch). With those two changes the default `batch_rows` moved from
200 000 to **20 000**; five same-host 1 M-row runs then give a median +28.6 % extraction time over the
COPY path (22.7–36.8 %) with ~210 MB peak, and SC-A01 holds at the median. The margin is thin —
the COPY baseline itself varies ±3 % run to run — so the numbers, not the single percentage, are
the evidence, and they are in `specs/008-fast-pg-extraction/research.md` (same-host section) under
T042.


## Spec issues (do not edit spec.md; proposed minimal fixes)

- **S1 (FR-A01/FR-A02, ambiguous)**: "declared input columns" are not declared anywhere. Fix: "the
  dataset declares the extracted columns in `transform.input` (name → type); the query/request must
  return them; `columns` is the transform output".
- **S2 (FR-A06, ambiguous)**: `ds_<integration>` is undefined for reports over two integrations and
  report ids contain `-`. Fix: "`ds_<integration of the report's date dataset>.mv_<report id with -
  replaced by _>`".
- **S3 (FR-A06, incomplete)**: there is no `count_distinct` metric kind; other non-additive
  aggregates exist in the allow-list. Fix: "metrics whose SQL uses `DISTINCT` inside an aggregate,
  percentiles, `stddev`, `variance`, `string_agg`, `bool_or/and`, window functions or `current_date`
  (and dimensions with aggregates or `current_date`) make the report ineligible".
- **S4 (FR-A07, contradictory)**: "in the same all-or-nothing publish" vs "a failed refresh keeps the
  previous rollup and marks the run". Fix: "the refresh runs inside the publish transaction under a
  savepoint; if it fails, the data is still published, the previous rollup is kept but marked stale
  (reports use raw rows until it is rebuilt) and the run records the failure". Also "days touched by
  the run's window" is not enough with primary-key upserts and joined datasets. Fix: "the days of
  every base row deleted, updated or inserted; any change in another dataset the report joins →
  full rebuild".
- **S5 (FR-A08, vacuous)**: "`table` views listing raw rows keep the raw path" — no such view exists
  (all `table` views aggregate). Fix: delete the clause or say "a future raw-row view keeps the raw
  path". "Fresh for the selection" → "fresh (built from the latest successful run of every used
  integration with the active definition)".
- **S6 (FR-A08, precision)**: "results MUST equal" → "equal for sums, counts, minima, maxima, keys
  and order; averages and formulas equal to 12 significant digits".
- **S7 (FR-A09, undefined)**: "dataset expected above 5 million rows" has no source. Fix: "estimated
  from the published dataset table (server validation) or the origin profile (agent); offline CLI
  validation cannot warn".
- **S8 (FR-A05, incomplete)**: path list omits `rows` (no transform on REST/SOAP or COPY fallback)
  and the former `bulk`. Fix: "`copy`, `rows`, `copy+polars`, `rows+polars` (`bulk` in older runs
  = `copy`)".
- **S9 (FR-A03, infeasible as worded)**: a Polars lazy frame cannot scan the PostgreSQL staging
  table. Fix: "a lazy frame over the window spilled to Arrow files in the temp folder"; and state
  that `TRANSFORM_MAX_ROWS` applies to whole-mode input rows (row-wise memory is bounded by the
  batch).
- **S10 (constitution V wording)**: "aggregation stays in PostgreSQL SQL" vs whole-mode `GROUP BY`
  in Polars. PATCH: "report aggregation and rollups stay in PostgreSQL SQL".
- **S11 (FR-A01, feasibility note)**: "date functions" — Polars 1.44 has no `date_trunc`/
  `current_date`, and `CAST(timestamptz AS DATE)` is UTC. Fix: "date functions supported by the
  engine (`extract`, `strftime`, `strptime`, casts); casting a time zone-aware timestamp to a date
  is refused (use `strftime`)".
- **S12 (SC-A02, undefined)**: "reference machine" → describe it in research R11 (CPU, RAM, disk,
  PostgreSQL version, local database).
