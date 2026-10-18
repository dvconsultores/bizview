# Research: Faster PostgreSQL extraction

**Feature**: [spec.md](./spec.md) · **Date**: 2026-10-01

## Current path (measured by reading the code, 2026-09-30)

`engine/extract.pg_rows` opens a read-only session (`default_transaction_read_only=on`,
`statement_timeout`, `TimeZone`, `application_name=bizview-engine`), runs the validated query
through a server-side cursor in 20 000-row batches; `engine/runner._extract` converts every value
to text in Python (`extract.text_value`), builds an all-`String` Polars frame, writes it as CSV and
`COPY … FROM STDIN (FORMAT csv)` into a typed temp staging table (PostgreSQL parses the types).
Cost is dominated by Python per-value work (row tuples → Python objects → strings → CSV).
Polars only serialises CSV; ConnectorX is not installed (it cannot open a read-only transaction,
feature 005).

## R1. Mechanism: PostgreSQL → PostgreSQL COPY pipe, text format

- **Decision**: on the origin session run
  `COPY (SELECT <declared columns> FROM (<validated query>) AS q) TO STDOUT (FORMAT text)` and
  forward every block returned by psycopg's `copy.read()` unchanged to
  `COPY <staging> (<declared columns>) FROM STDIN (FORMAT text)` on the installation connection.
- **Rationale**: no row ever becomes Python objects; memory is one libpq buffer; PostgreSQL's text
  format is the native round-trip format (exact for every type with an input/output function:
  numeric, timestamptz, bytea, arrays, json, text with tabs/newlines/backslashes escaped), and the
  destination still parses each value with the declared type (FR-005).
- **Alternatives considered**: `FORMAT binary` — fastest, but requires identical types on both
  sides (origin `int4` into declared `numeric` fails), so declared-type checking breaks; `FORMAT
  csv` — works but needs quoting rules for NULL vs empty string and is no faster; ConnectorX/Arrow
  into Polars — cannot run inside a read-only transaction and still materialises rows in memory.

- **Known, intended difference** (found by the equivalence test, 2026-10-01): contract columns are
  `text`, `integer`, `bigint`, `numeric`, `boolean`, `date`, `timestamptz` (`datasets.PG_TYPES`);
  for all of them both paths load identical values. When a query puts a non-contract origin type
  (array, bytea, jsonb, …) into a declared `text` column, the bulk path stores PostgreSQL's own
  text form (`{1,NULL,3}`, `\x00ff`), while the row path stores a Python/JSON rendering
  (`[1, null, 3]`, `b'\x00\xff'`). The bulk form is the one a SQL author expects from `::text`;
  the row path (now only a fallback) keeps its old behaviour.

## R2. Window parameters without bind variables

- **Decision**: `COPY (query)` does not accept bind parameters, so the query produced by
  `extract.to_psycopg` is rendered once with `psycopg.ClientCursor(conn).mogrify(q, params)`,
  which quotes values with the server's escaping rules. The parameters are engine-generated
  `datetime` values (`window_start`, `window_end`), never user text, and the query was already
  validated by `sqlsafety` (single read-only SELECT).
- **Alternatives**: string formatting (rejected: unsafe pattern even for trusted values); a
  temporary prepared statement + `COPY (EXECUTE …)` (not allowed by PostgreSQL).

## R3. Column check before loading (FR-004)

- **Decision**: in the same read-only transaction, run `SELECT * FROM (<rendered query>) AS q
  LIMIT 0` on a normal cursor to read `cursor.description`; on mismatch raise today's
  `ExtractError` ("las columnas de la consulta no coinciden con el contrato (faltan …, sobran …)")
  before any COPY. The COPY then selects the declared columns by name, so loaded order always
  matches the staging columns.

## R4. Deterministic text output (edge cases, SC-003)

- **Decision**: the bulk session also sets `DateStyle=ISO, MDY`, `IntervalStyle=postgres`,
  `extra_float_digits=3` and `bytea_output=hex` (plus today's `TimeZone`), so the text the origin
  emits is exactly what the destination's input functions read, whatever the origin's defaults.
- The installation's own session already uses ISO defaults; tests compare both paths.

## R5. Time limit and failures (FR-006)

- **Decision**: the origin `statement_timeout` (already set from the run's remaining time) stops
  a long COPY server-side; the pipe loop also checks the run deadline between blocks and raises
  today's "se superó el tiempo máximo de la integración". Destination `DataError` maps to today's
  "los datos no cumplen el contrato: …". Any failure aborts the runner's transaction, so staging
  (temp, ON COMMIT DROP) and the published dataset are untouched.

## R6. Fallback (FR-008)

- **Decision**: fall back to the current row path only when the origin raises one of
  `FeatureNotSupported`, `InsufficientPrivilege`, `SyntaxError` / `UndefinedFunction`
  (protocol-compatible engines without `COPY (query)`) **before the first block is written** to
  staging. Errors after data started flowing, and every other error, fail the run.
  The reason recorded is the SQLSTATE class name (e.g. `FeatureNotSupported`) — never the message
  text (it may echo SQL or values).
- **Rationale**: a fallback after partial writes would require truncating staging and re-reading;
  failing is simpler and those errors are not "unsupported" anyway.

## R7. Counting rows

- **Decision**: after the COPY, `plan.extracted` = `cursor.rowcount` of the destination COPY
  (psycopg 3 reports rows copied). The rows path keeps its current counting.

## R8. Recording the path (FR-009)

- **Decision**: `integration_run.rows[<dataset>]` (existing JSONB) gains `"path": "bulk" | "rows"`
  and, on fallback, `"fallback": "<SQLSTATE class name>"`. No migration. The Integrations admin
  screen shows the path in the run history line.

## R9. Constitution (FR-011)

- **Decision**: amend principle V, Worker bullet, to: "Python 3.11+, APScheduler (single scheduler
  process; no message broker). PostgreSQL sources stream the validated query result with COPY
  (text format) from a read-only session straight into typed staging tables; REST/SOAP records are
  batched with Polars into the same staging COPY. Aggregation stays in PostgreSQL SQL."
  ConnectorX is removed from the text (never installed). MINOR version bump (stack component
  description changed; one component dropped that was never used) → 1.7.0.

## R10. Benchmark (SC-001, SC-002)

- **Decision**: `backend/scripts/bench_extract.py` creates a throwaway schema in the BI database
  with `generate_series` rows covering every edge-case type, runs both paths through the engine's
  functions into temp tables, and prints rows, seconds and peak RSS (`resource.getrusage`). Opt-in
  (`BENCH_ROWS=1000000`), never part of the test suite's default run.

## Supporting libraries

None added (psycopg 3 already provides COPY streaming and `ClientCursor.mogrify`).

## Benchmark (2026-10-01)

Run with `backend/scripts/bench_extract.py` (`BENCH_ROWS=10000`, then `BENCH_ROWS=1000000`)
against the shared BI database (remote host, used as both origin and destination). Each path ran
in its own process; peak MB is the process's `ru_maxrss`. The script had to be launched with
`PYTHONPATH=backend` because it does not find the `app` package on its own. That was an
environment workaround only; no code was changed.

| Path | Rows      | Seconds | Peak MB |
|------|----------:|--------:|--------:|
| bulk |    10,000 |    6.81 |   127.7 |
| rows |    10,000 |   11.58 |   167.8 |
| bulk | 1,000,000 |  711.08 |   137.6 |
| rows | 1,000,000 | 1298.02 |   212.4 |

- Speed-up at 1M (rows seconds / bulk seconds): **1.8×**
- Bulk peak-MB delta, 1M vs 10k: **+9.9 MB**

**SC-001 (speed-up ≥ 5×): NOT MET** (1.8×).
**SC-002 (bulk peak delta < 50 MB): MET** (+9.9 MB; memory stays flat with volume, while the rows
path grew by 44.6 MB).

Note: both paths ran at roughly 1,400 rows/s (bulk) and 770 rows/s (rows), scaling linearly from
10k to 1M rows. Origin and destination are the same remote server, so every row crosses the
network twice. The measurement is therefore probably limited by network throughput, which would
hide the CPU savings of the COPY pipe. SC-001 should be measured again with origin and
destination on the same LAN or host before the result is taken as final.

## Benchmark: transform stage (005 amendment, SC-A01, 2026-10-09)

Run with `backend/scripts/bench_extract.py` (`BENCH_ROWS=1000000`; each mode in its own process;
peak MB = `ru_maxrss`). Machine: AMD Ryzen 5 7430U (12 threads), 15 GB RAM, Linux 6.12; origin
and destination = the shared BI database on a **remote** PostgreSQL 17.6 host (every row crosses
the network twice). `copy+polars` runs `SELECT id, upper(txt) AS txt, amount * 2 AS amount, ts,
d, flag, js FROM input` row-wise with the default `batch_rows` 200 000, exactly as the runner
does (`CopyTextSplitter` → `Sink` → one destination CSV COPY kept open, written by a bounded
background writer that flushes every ≤128 KiB item). The `whole` mode (T035) is recorded in
"Benchmark: whole-mode transform" below.

| Version | Path | Rows | Seconds | Peak MB | Transform ms |
|---------|------|-----:|--------:|--------:|-------------:|
| first (one COPY per 50 000-row slice) | copy | 1,000,000 | 23.27 | 273.6 | — |
| first | rows | 1,000,000 | 88.92 | 272.7 | — |
| first | copy+polars | 1,000,000 | 31.52 | 404.1 | 716 |
| first, rerun | copy / copy+polars | 1,000,000 | 21.86 / 33.83 | 274.1 / 387.9 | 752 |
| open COPY, psycopg queued writer (no flush) | copy / copy+polars | 1,000,000 | 24.98 / 29.23 | 276.4 / 540.1 | 785 |
| **final** (open COPY, bounded + flushed writer) | copy / copy+polars | 1,000,000 | 23.65 / 29.94 | 265.0 / 395.0 | 758 |
| **final**, rerun | copy / copy+polars | 1,000,000 | 24.34 / 31.20 | 268.6 / 385.8 | 733 |

- **SC-A01 time (≤ 30 % over copy): MET** (+26.6 % and +28.2 %; the first version was +35 % to
  +55 % because each output slice opened its own destination COPY and uploaded synchronously
  while the origin stream stalled). The Polars work itself (parse + SQL + dtype check) is
  ~0.75 s per million rows; the rest is network transfer.
- Without a flush, psycopg's queued writer let libpq's output buffer absorb the whole stream on a
  slow link (+140 MB); the final writer flushes each item, which keeps the overlap and bounds the
  buffer.
- **SC-A01 memory (< 300 MB): NOT MET** in this environment: ~390 MB. The plain `copy` path alone
  peaks at ~265–275 MB here (137.6 MB on 2026-10-01 against the same host), leaving ~25 MB for
  the transform. Variants measured (same host, 1M rows, writer without flush, so ~140 MB higher
  than final): slice 10 000 → 526 MB; batch 50 000 → 419 MB; batch 50 000 + slice 10 000 →
  405 MB; `POLARS_MAX_THREADS=2` → 517 MB; `MALLOC_ARENA_MAX=2` → 527 MB — memory follows the
  batch size (raw + typed + output frames). Per plan §8 the spec default (`batch_rows` 200 000)
  stays; an integration that must stay under a memory budget can lower `transform.batch_rows`
  (minimum 10 000). To be measured again on a LAN/host origin.

## Benchmark: whole-mode transform (005 amendment, T035, 2026-10-09)

Run with `BENCH_ROWS=200000 BENCH_MODES=copy,copy+polars,whole uv run python
scripts/bench_extract.py` (throwaway schema `app_test_bench_<hex>`, dropped at the end; same
machine and remote PostgreSQL 17.6 host as above; `TRANSFORM_SPILL_DIR` and `POLARS_TEMP_DIR`
pointed to a scratch folder). `whole` runs the benchmark SQL plus `ORDER BY id`: typed batches
are spilled to Arrow IPC files, the SQL runs with `sink_ipc(..., engine="streaming")` in the
background (polled every 0.25 s for stop requests), and the result is read back in 50 000-row
batches into the destination COPY.

| Path | Rows | Seconds | Peak MB | Transform ms |
|------|-----:|--------:|--------:|-------------:|
| copy | 200,000 | 7.58 | 157.2 | — |
| copy+polars | 200,000 | 7.16 | 340.6 | 169 |
| whole | 200,000 | 7.53 | 406.8 | 432 |

- Time is network-bound at this size (all three within ±6 %); the whole-mode Polars work
  (parse + spill + sorted SQL + read-back) is ~0.43 s for 200 000 rows.
- Peak memory of `whole` is ~65 MB above `copy+polars` (streaming engine buffers and the
  sorted output); the spill folder was empty after the run. A 1 M-row and LAN/host measurement
  remains to be done together with the SC-A01 re-measurement.

## Benchmark: same host (T020, 2026-10-12)

Run with `backend/scripts/bench_extract.py` and `BENCH_DATABASE_URL` set to a PostgreSQL on this
machine (a `postgres:17-alpine` container reached at the docker bridge address, 2 GB
`shared_buffers`, 4 parallel workers per gather, `synchronous_commit=off`), so origin and
destination sit on the same host as the client — the condition SC-001 needs. The loopback
address is never usable: the connector's SSRF guard blocks it by design (an opt-in developer tool
still goes through the production policy), and the benchmark now fails fast instead of waiting
when a child dies before reporting (`measure()`).

```bash
docker run -d --name bizview-bench-pg -e POSTGRES_PASSWORD=bench -e POSTGRES_DB=bench \
  -p 172.17.0.1:55432:5432 postgres:17-alpine -c shared_buffers=2GB -c work_mem=256MB
cd backend && BENCH_DATABASE_URL=postgresql://postgres:bench@172.17.0.1:55432/bench \
  BENCH_ROWS=1000000 uv run python scripts/bench_extract.py
```

Machine: AMD Ryzen 5 7430U (6 cores / 12 threads), 15,390 MB RAM, Linux 6.12 (Debian 13),
PostgreSQL 17.11 (Alpine, container on the same host). `rows/s` comes from the script's table.

| Path | Rows | Seconds | rows/s | Peak MB | Transform ms |
|------|-----:|--------:|-------:|--------:|-------------:|
| copy | 10,000 | 0.03 | 333,333 | 136.2 | — |
| rows | 10,000 | 0.20 | 50,000 | 179.4 | — |
| copy+polars | 10,000 | 0.08 | 125,000 | 184.7 | 16 |
| copy | 1,000,000 | 2.05 | 486,788 | 136.1 | — |
| rows | 1,000,000 | 12.25 | 81,623 | 284.8 | — |
| copy+polars | 1,000,000 | 3.92 | 255,427 | 434.2 | 755 |

- **SC-001 (speed-up ≥ 5×): MET** — 6.0× at 1 M rows (6.1× at 10 k), against 1.8× over the
  remote link. The COPY pipe holds ~487 k rows/s and its peak memory stays flat (136 MB at 10 k
  and at 1 M), while the row fallback manages ~82 k rows/s and grows to 285 MB.
- **SC-001 across sizes**: the advantage is bounded by the row path's per-value Python work, so it
  grows with the number of rows and disappears at very small volumes (10 k rows: two round trips
  dominate).

### SC-A01 at 1 M rows, same host (transform stage)

`copy+polars` over `copy` in the same run, per `transform.batch_rows`. The 2026-10-12 pass reduced
the transform's own cost first (`transform_ms` at 1 M rows: 654 ms → 287 ms with 200 000 rows per
batch — the declared-type check reads the materialised typed frame instead of re-evaluating every
cast; a batch read from COPY text without a backslash skips the unescape pass), which moved the
optimum to smaller batches:

| `batch_rows` | copy s | copy+polars s | Overhead | Peak MB | Δ peak | `transform_ms` |
|-------------:|-------:|--------------:|---------:|--------:|-------:|---------------:|
| 10,000 (3 runs) | 2.14–2.21 | 2.84 | +28.6 / +31.1 / +32.9 % | 201–221 | +66–85 | 818–821 |
| **20,000 (5 runs)** | 2.07–2.21 | 2.71–2.85 | +36.8 / +22.7 / +25.7 / +28.6 / +30.2 % | 202–237 | +66–101 | 493–547 |
| 50,000 (1 run) | 2.13 | 3.09 | +45.1 % | 291 | +155 | 365 |
| 200,000 (1 run) | 2.11 | 3.57 | +68.9 % | 391 | +255 | 287 |
| 200,000, before this pass | 2.05–2.17 | 3.92 | +81 / +91 % | 434 | +298 | 755 |

- **SC-A01 time (≤ 30 % over `copy`): MET at the median** — five runs at `batch_rows` 20 000 give
  a median **+28.6 %** (22.7–36.8 %; four of the five ≤ 30.2 %). The spread comes from the COPY
  baseline (2.07–2.21 s, ±3 %), not from the transform (`copy+polars` 2.71–2.85 s), so the margin
  is thin and the table, not the single percentage, is the evidence. `batch_rows` 10 000 is the
  most stable (2.84 s every run) but sits a little higher (median +31.1 %).
- **SC-A01 memory: MET** — peak 202–237 MB (< 300 MB) and Δ +66–101 MB (≤ 150 MB) at 20 000, against
  434 MB / +298 MB with the old default.
- The default `batch_rows` is now **20 000** (was 200 000) and the authoring guidance for the agent
  and the plan example follow it. What remains of the gap is structural: a row-wise transform must
  read COPY text and write CSV again (≈ 66 ms read + ~300 ms parse/cast + ~460 ms serialise at
  1 M rows), so a much lower overhead needs a different transport (COPY BINARY/Arrow), not a
  smaller batch.
- **Open finding for 005 (SC-A01)**: recorded as a new convergence task in
  `specs/005-vibe-reporting/tasks.md`; the default stays as the spec decides until the owner
  chooses a mitigation (smaller default batch, or a lighter per-batch path).
