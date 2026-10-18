# Research: Vibe Reporting

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-29

Decisions taken autonomously with the recommended option, at the user's request.

## R1. Spec discipline through Spec Kit itself

- **Decision**: build on GitHub Spec Kit 1.x (the version this project uses, 1.0.13) instead of a
  home-made workflow:
  - a **Spec Kit preset `bizview`** (installed with `specify preset add`) overriding
    `spec-template`, `plan-template`, and `tasks-template` with Vibe Reporting variants. The spec
    template starts with a mandatory `**Spec type**: integration | report` line and has the
    sections for both types (dataset contract, schedule, checks / metrics, views, access, AI
    narrative); the plan template maps the spec to artifact files; the tasks template ends with
    "run `bizview validate`";
  - a **Spec Kit extension `bizview`** providing commands `/bizview-validate` and
    `/bizview-describe`, and a **mandatory `after_implement` hook** running `bizview validate`, so
    the agent cannot finish `/speckit-implement` with an invalid workspace;
  - a **workspace constitution** (Vibe Reporting principles) and agent instruction files
    (`CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`) stating: no integration or report
    work without a spec; artifacts only in their spec's folders; SQL read-only; no credentials;
    no row data in prompts.
- **Rationale**: the user asked for GitHub Spec Kit specifically; presets/extensions are its
  supported customisation points, so workspaces stay upgradable with `specify` itself.
- **Alternatives**: a custom CLI generating specs (rejected: reinvents Spec Kit, loses agent
  integrations); free-form prompts (rejected: the user requires spec discipline).

## R2. Workspace layout (customer repository)

```text
<customer>-bizview/                  private Git repository per customer
├── .specify/                        Spec Kit + preset bizview + extension bizview
├── .claude/ , AGENTS.md, CLAUDE.md  agent integration + rules
├── bizview.yaml                     workspace manifest: name, product version range
├── specs/
│   ├── integrations/<id>/           spec.md plan.md tasks.md (Spec Kit feature folders)
│   └── reports/<id>/
├── integrations/<id>/
│   ├── integration.yaml             artifact (contracts/artifacts.md)
│   └── queries/*.sql | requests/*.yaml
├── reports/<id>/report.yaml
└── bizview.lock                     written by `bizview validate`: checksums per spec + artifacts
```

- Spec Kit numbers features under `specs/`; the Bizview preset's scripts create them under
  `specs/integrations/` or `specs/reports/` according to the spec type, and the id is the folder's
  short name (e.g. `001-erp-ventas` → id `erp-ventas`).
- **Spec status**: the spec's `**Status**:` line must be `Approved` or `Implemented`; `tasks.md`
  must have no unchecked `- [ ]` tasks; validation writes the lock.

## R3. Artifacts are declarative (no customer code)

- **Decision**: integrations and reports are YAML + SQL validated against JSON Schemas shipped
  with the product (`contracts/artifacts.md`). No Python/JS per customer. SQL is parsed with
  `sqlglot` to enforce a single read-only `SELECT`/`WITH`, no DDL/DML, no `COPY`, no functions with
  side effects (`pg_*` admin functions, `dblink`, `lo_*`), and — for report metrics — references
  only to the report's declared datasets.
- **Rationale**: constitution VII (one product) — customer logic is data the engine interprets;
  the AI can write it safely; reviews are easy.

## R4. Dataset storage and runs

- **Decision**: each integration gets schema `ds_<integration_id_with_underscores>` in the product
  database. The engine creates/alters tables from the dataset contract (`CREATE TABLE`,
  `ALTER TABLE ADD COLUMN`; incompatible changes rebuild the table on the next full run). Runs:
  extract with the 004 connector (PostgreSQL: read-only transaction, `COPY` of results into a
  staging table; REST/SOAP: paginated requests → rows), apply contract casts and checks, then in
  one transaction delete the window and insert staging rows. Runs are recorded in
  `integration_run`; one advisory lock per integration prevents overlap. Extraction uses Polars
  for type coercion and checks (constitution V).
- **Constitution impact**: Alembic owns the product schema; integration schemas are owned by the
  engine from validated contracts (amendment 1.6.0).
- **Worker**: the `worker` service (APScheduler, constitution V) loads the applied workspace
  version, schedules each integration's cron, and runs manual triggers queued in
  `integration_run_request`.

## R5. Report engine

- **Decision**: metrics are SQL aggregate expressions over one dataset or a declared join of
  datasets (e.g. `sum(net_amount)`, `count(distinct document_id)`), with a date column per dataset
  for periods. The engine builds parameterised queries: period and comparison ranges (the rules of
  feature 001 research R7, now generic), grain (day/week/month), dimension filters; results cached
  per (report, selection, data version) with ETag. Views: `kpis`, `trend`, `ranking`, `table` —
  rendered by one generic frontend renderer; PDF with ReportLab using the same queries
  (constitution: PDF by backend).
- **Performance**: for SC-004 the engine creates daily aggregate tables per report metric set when
  the report declares `materialize: daily` (recommended for >1 M rows).

## R6. AI only through report specs

- **Decision**: a report section `ai_narrative` lists `inputs` (metric ids and period); the engine
  computes those aggregates and sends only them, with the report's instructions, through the
  feature 003 provider; output cached per data version. No other product code path calls the AI
  provider (enforced by a test that greps call sites). The feature 003 super-user connection test
  remains (it sends a fixed prompt, no data).

## R7. Apply, lock, rollback

- **Decision**: `bizview validate` (static, no DB) writes `bizview.lock` with SHA-256 of every spec
  file and artifact. The installation's *Espacio de trabajo* page (super user): shows the mounted
  commit/checksum, runs the same validator plus live checks (sources exist in the catalogue,
  dataset compatibility), shows a diff against the active version, and applies with step-up. The
  applied version is copied into the database (`workspace_version` with the artifacts' JSON and
  lock), so the product runs from the database copy, not the mounted files; rollback re-activates
  the previous row. Mounted files changed after apply do nothing until the next apply.

## R8. Describe and tokens

- **Decision**: personal access tokens (`api_token`: name, scopes `["describe"]`, SHA-256 hash of a
  32-byte random token shown once, expiry default 90 days, last used, revoked). `GET
  /api/sources/{name}/describe` with `Authorization: Bearer` returns structure only: PostgreSQL via
  `information_schema` + `pg_class.reltuples`; REST via a configured sample path returning JSON
  *shape* (keys and types inferred, values dropped); SOAP via WSDL operations and message schemas.
  CLI `bizview describe <source>` reads `BIZVIEW_URL` and `BIZVIEW_TOKEN` from the environment.
  Tokens do not grant any other endpoint.

## R9. Tooling distribution

- **Decision**: a small Python package `bizview-cli` in the product repository (`cli/`), installable
  with `uv tool install` from the release, providing `bizview init`, `bizview validate`,
  `bizview describe`. It embeds the artifact JSON Schemas and the SQL rules shared with the backend
  (same module, published as package data) so local and server validation agree. The preset and
  extension live in `cli/bizview_cli/workspace_template/` (package data) and are installed by
  `bizview init`.

## R10. Feature 001 disposition

- **Decision**: feature 001 is marked **Superseded by 005**. Its generic requirements (periods,
  comparisons, zero-base, freshness, product rankings, PDF parity, 375 px) become FR-013 – FR-016
  engine capabilities; its Customer B-specific parts (origin extract contract, metrics
  definitions) become the first workspace specs `erp-ventas` (integration) and
  `ventas` (report) in Customer B's workspace, written with vibe reporting after this feature.

## R11. Benchmark: daily rollups (SC-A02, T041b, 2026-10-12)

`backend/scripts/bench_rollup.py` (opt-in, not part of CI) builds a synthetic dataset of
`BENCH_ROWS` rows over 3 years × `BENCH_DIMS` product combinations in its own throwaway schema
`app_test_bench_<hex>__ds_bench` (`datasets.ensure_table` with the dict column contract, day and
product decorrelated so the rollup covers the whole cross product), then measures
`rollup.build_full`, `rollup.refresh_days` for the days an hourly incremental run would touch, and
`BENCH_RUNS` cold runs of every view type on the rollup route (`engine.Route`, what
`engine.routed` builds from a ready `report_rollup` row) and on the raw path, reported as p95.
The schema is dropped at the end (verified: no `app_test_bench_*` schema left).

Two runs, recorded below: **50 M rows on a local reference database (the SC-A02 run)** and
1 M rows against the installation's remote BI database. Run with
`BENCH_ROWS=50000000 BENCH_DIMS=500 BENCH_RUNS=20 uv run python scripts/bench_rollup.py` (and
`DATABASE_URL_BI` pointed at the local database).

| Reference machine | |
|---|---|
| CPU | AMD Ryzen 5 7430U with Radeon Graphics (6 cores / 12 threads) |
| RAM | 15,390 MB |
| Disk (free) | 72.3 GB |
| Client | Linux 6.12 (Debian 13), Python 3.13.5 |
| Database (SC-A02 run) | **local** `postgres:17-alpine` 17.11 container reached at the docker bridge address, 2 GB `shared_buffers`, 256 MB `work_mem`, 4 parallel workers per gather, `synchronous_commit=off` |
| Database (second run) | the installation's BI database on a **remote** host (≈ 25 mbps link, ~200 ms per round trip): those numbers include the network |

### SC-A02: 50 M rows, local database (2026-10-12)

| Measurement | Target | Result |
|---|---|---|
| Dataset | — | 50,000,000 base rows over 3 years × 500 products (~2.5 GB + index) |
| Full build (`build_full`) | — | 14.74 s (547,500 rollup rows) |
| 7-day refresh after an incremental change (3,500 touched rows) | < 30 s | **2.25 s ✅** |
| Cold views p95, rollup route (kpis / trend / ranking / table) | < 1 s | **0.017 / 0.033 / 0.027 / 0.013 s ✅** |
| Cold views p95, raw path (same selection, last 30 days ≈ 1.37 M rows) | — | 0.551 / 1.045 / 0.936 / 0.529 s |

- **SC-A02 MET** on a local reference database: every cold view is served in ≤ 33 ms from the
  rollup against 0.53–1.05 s on the raw path, i.e. **16–40× faster**, and the refresh that an
  hourly incremental run triggers costs 2.25 s, far below the 30 s budget.
- The raw path already fails the SC-A02 p95 target (> 1 s for `trend`) at this size, which is
  exactly what routing materialized reports to their rollup is for.

### 1 M rows, remote database (2026-10-12)

| Measurement | Target | Result (1 M rows, 547,500 rollup rows) |
|---|---|---|
| Full build (`build_full`) | — | 6.06 s |
| 7-day refresh after an incremental change (3,500 touched rows) | < 30 s | 0.74 s ✅ |
| Cold views p95, rollup route (kpis / trend / ranking / table) | < 1 s | 0.352 / 0.381 / 0.528 / 0.236 s ✅ |
| Cold views p95, raw path (same selection, last 30 days) | — | 0.441 / 0.421 / 0.578 / 0.278 s |

- Both SC-A02 thresholds hold at 1 M rows, where the raw path is still cheap: a 30-day window
  touches ~30/1095 of the base table, and every cold view pays the same ~0.2 s of round trips to
  the remote database, which hides the rollup's advantage. The gap grows with the window and the
  table size (see `specs/008-fast-pg-extraction/research.md` for the same effect in extraction).
- 50 M rows need ~2.5 GB for the base table plus ~1 GB of index in the throwaway schema, and
  ~1 GB of disk-backed temp space for the build; the schema is dropped at the end (verified).
  The reproduction command is in `specs/008-fast-pg-extraction/research.md` (same host section).
- **SC-A01 (transform stage)**: the same-host extraction benchmark also re-measured the row-wise
  transform; after the 2026-10-12 optimizations in `app/engine/transform.py` and with the default
  `batch_rows` at 20 000 it holds at +28.6 % median over the COPY path (five 1 M-row runs) with
  ~210 MB peak. The table, the spread and the structural floor are in
  `specs/008-fast-pg-extraction/research.md` (same host section).
- **Follow-up studied and rejected (2026-10-12)**: a typed/binary transport was specified, planned
  and researched to remove the remaining overhead, and the research found it **more expensive** than
  the text path it would replace. Measured, 1 M rows: reading the whole COPY text blob with Polars is
  **0.038 s** and the casts plus declared-type checks are **0.053 s** (flat data) to 0.355 s (varied
  data), while a PostgreSQL-binary `numeric` (variable-length base-10000) needs a Python decoder at
  **0.394 s per 1 M values** — and numerics are the backbone of BI datasets. Arrow cannot help
  either: the origin is an external PostgreSQL that emits COPY text or COPY binary only, so Arrow
  could only be produced *inside* the worker, where the values already exist. The plan's three
  "free" micro-optimizations were then measured and are worth **~0 %**, which says the design is at
  its floor and that what remains is the price of "declarative transform in Polars between extraction
  and load". The owner closed the follow-up spec as **not needed**; reaching ≤ 15 % would need a
  compiled codec (a new stack component, principle V amendment) or moving the transform into
  PostgreSQL (reversing the ratified "transform in Polars" decision). **Revisit trigger**: a real
  integration with a transform crossing ~5 M rows, or a customer hitting a time or memory limit.
