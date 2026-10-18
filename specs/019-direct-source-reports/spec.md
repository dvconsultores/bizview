# Feature Specification: Direct-source reports (no ETL)

**Feature Branch**: `019-direct-source-reports`

**Created**: 2026-10-08

**Status**: Implemented (closed 2026-10-12, backend + CLI + frontend + e2e suites green)

**Input**: Owner, 2026-10-08 (prompt.md): "Suppose I want to create a report connected direct to the
source, no ETL, just indicating the source and tables, because the data was already set in another
process or exists in a well-tested BI table."

**Builds on**: 005-vibe-reporting (report engine, `report.yaml`), 004-data-sources-security (source
catalogue, read-only connectors), 017-agentic-vibe-chat (`describe_source`, `check_query`).
**Constitution**: 2.0.0 principle II (direct reads by exception).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Report over an existing BI table, no integration (Priority: P1) 🎯

The BI database already holds `public.bi_ventas`, maintained and tested by another process. The super
user writes a report spec that names the source "BI de esta instalación" and the table; after apply
the dashboard shows the table's figures live, with no integration, no worker run and no copy of the
data.

**Why this priority**: it is the owner's exact case and the shortest path from an existing table to a
dashboard.

**Independent Test**: on a test schema with a seeded table, apply a workspace containing only a direct
report (no integration); the dashboard renders KPIs, trend, ranking and table; inserting a row in the
table is visible after the cache period without any worker run; no `ds_*` schema is created.

**Acceptance Scenarios**:

1. **Given** a report spec declaring direct mode with source `bi` and table `public.bi_ventas` with
   its columns, **When** the workspace is validated and applied, **Then** the report is accepted
   without any integration and appears in the dashboards catalogue like any other report.
2. **Given** the applied direct report, **When** a user opens it, **Then** KPIs, comparison, trend,
   rankings, tables, filters, periods and PDF work exactly as for dataset reports, and the footer
   says "Datos en vivo · <fuente> · consultado <hora>" instead of the last integration run.
3. **Given** the table changes, **When** the cache period of the report has passed, **Then** the next
   view shows the new figures; within the period, views are served from cache.
4. **Given** a direct report that names a product table (users, sessions, audit, credentials,
   assistant, sharing, alembic) of the BI database, **When** validated, **Then** validation fails
   with "Tabla del producto: no se puede leer en un reporte directo".

---

### User Story 2 - Report directly over a PostgreSQL source (Priority: P1)

The customer's ERP has a reporting schema (views already aggregated by its own team). The super user
enables "Permitir reportes directos" on that PostgreSQL source and writes a direct report over two of
its views joined by a key.

**Independent Test**: with a test PostgreSQL source enabled for direct reads, a direct report over two
joined tables renders; with the flag off, apply fails and an already applied report shows "Esta
fuente no permite reportes directos" without querying it.

**Acceptance Scenarios**:

1. **Given** a PostgreSQL source in the catalogue, **When** the super user turns on "Permitir reportes
   directos" (default off), **Then** the change requires step-up confirmation, is audited, and the
   source card shows the flag.
2. **Given** a direct report over a source whose flag is off, a disabled source, or a source of kind
   SOAP, REST or Supabase (REST), **When** validated, **Then** it fails with the reason and the
   suggestion to create an integration instead.
3. **Given** a direct report with `joins` between declared tables, **When** rendered, **Then** the
   engine builds the same join and aggregate SQL it builds for datasets, over the source tables.
4. **Given** the source is unreachable or the query exceeds the timeout, **When** the dashboard is
   opened, **Then** it shows the last cached result marked "Datos de <hora>; la fuente no respondió"
   if one exists, otherwise a clear error; the source is never retried in a tight loop.

---

### User Story 3 - The agent and the CLI can author direct reports (Priority: P2)

From the chat or from VS Code, a report spec can choose "directo" instead of an integration. The agent
inspects the table with `describe_source`, fills the column contract, checks it, and the preview
renders the report from the live source.

**Acceptance Scenarios**:

1. **Given** a request "reporte directo sobre bi_ventas, sin ETL", **When** the agent drafts it,
   **Then** the draft contains only the report spec and `report.yaml` with direct mode, no integration.
2. **Given** a direct report draft, **When** validated, **Then** declared tables and columns are
   compared with the live structure (names and compatible types) and every mismatch is one problem
   with the expected shape (017 FR-003).
3. **Given** a valid direct draft, **When** the preview runs, **Then** the report renders from the live
   source marked "Vista previa" (no temporary schema is needed) and the PDF preview downloads.
4. **Given** `bizview validate` in a customer workspace, **When** it meets a direct report, **Then** it
   validates the schema offline and checks live structure only when a source description is available
   (`bizview describe` output or the access token of 005).

### Edge Cases

- A direct report and dataset report share a dashboard filter: each report keeps its own data path; no
  cross-mode joins (a report is either direct or dataset-based, never both).
- `materialize: daily` on a direct report: rejected (nothing to materialize; the cache is the speed
  mechanism).
- Columns flagged as personal data by `describe_source`: excluded unless confirmed, as for
  integrations (017 FR-007); a direct table view never lists rows of a flagged column.
- Very large table without an index on the date column: the timeout protects the source; the report
  spec must state the expected volume, and the agent warns when `profile_source` shows more than
  `DIRECT_REPORT_WARN_ROWS` (default 5 million) rows.
- The source structure changes after apply (column dropped): the report shows "La estructura de la
  fuente cambió: falta <columna>" and the workspace page lists the report as broken; nothing crashes.
- The same table is read by many users at once: one in-flight query per report and selection; other
  requests wait for it (single-flight) and share the result.
- Shared links (018) and email subscriptions render direct reports through the same cache.
- Security profile `internet`: the same TLS rules as integrations apply to direct reads.
- A catalogue source named `bi`: the name is reserved for the BI database in `direct.source`; new or
  renamed sources cannot use it.

## Requirements *(mandatory)*

### Functional Requirements

#### Declaration
- **FR-001**: `report.yaml` MUST accept a `direct` block as an alternative to `uses`: `source`
  (catalogue source name, or `bi` for the installation's BI database), `tables` (alias → `table`
  as `schema.table` plus a column contract with name and type, the same column types as datasets),
  optional `cache_seconds` (60–86400, default 300), optional `timeout_seconds` (1–60, default 15),
  optional `max_rows` for table views (1–5000, default 500). Exactly one of `uses` or `direct`.
- **FR-002**: Everything else in `report.yaml` (date, joins, metrics, dimensions, periods, compare,
  views, filters, access, pdf, ai_narrative) MUST work unchanged with aliases from `direct.tables`;
  `materialize` other than `none` MUST be rejected.
- **FR-003**: The report spec of a direct report MUST state the mode (`**Modo**: directo`), the source,
  the tables, who maintains them (the process that already shapes the data) and the expected volume,
  one line each (`**Modo**: directo`, `**Fuente**:`, `**Tablas**:`, `**Mantenido por**:`,
  `**Volumen esperado**:`); validation fails for each missing line.

#### Safety
- **FR-004a** (big tables, 2026-10-08): validation MUST read each direct table's estimated row count
  (`pg_class.reltuples`, no scan); above `DIRECT_REPORT_WARN_ROWS` (default 5 million) direct mode
  MUST be refused unless the date column is the leading column of an index or the table is
  partitioned by it; the refusal says "Tabla grande sin índice por fecha: crea una integración con
  materialize: daily o indexa <columna>", and the agent proposes the integration path instead.
- **FR-004**: Direct reads MUST run only SQL generated by the engine from the declared tables and
  columns (the same expression checker as dataset reports), in a read-only session (`BEGIN READ
  ONLY`, `statement_timeout` = `timeout_seconds`), through the existing read-only connectors and
  network guard.
- **FR-005**: The source `bi` MUST resolve to the BI database with a read-only session and MUST
  refuse every table owned by the product (all tables of the product's Alembic metadata,
  `alembic_version`, `app_test_*` schemas). `ds_*` dataset tables MAY be read. Defence in depth: when
  `DIRECT_BI_ROLE` is set (required on the `internet` security profile), every `bi` session MUST run
  `SET LOCAL ROLE` to that database role, which the installer creates with SELECT only on the
  allowed schemas/tables and no privilege on product tables, so views or functions cannot reach
  product data even if the deny-list is bypassed.
- **FR-006**: Catalogue sources MUST have a flag "Permitir reportes directos" (default off), only for
  kind PostgreSQL; changing it requires step-up and is audited. The built-in `bi` source is enabled
  by the installation setting `DIRECT_REPORTS_BI` (default on).
- **FR-007**: At most `DIRECT_REPORT_CONCURRENCY` (default 2) direct queries MUST run at once per
  source; further requests wait up to the timeout, then fail with "La fuente está ocupada".

#### Freshness and cache
- **FR-008**: Results MUST be cached per report, selection (period, comparison, filters) and time
  bucket of `cache_seconds`, in the existing report cache; concurrent identical requests share one
  query (single-flight).
- **FR-009**: When a direct read fails and a cached result for the same selection exists (any age up
  to 24 h), the API MUST return it with `stale: true` and the time it was computed; the dashboard
  marks it.
- **FR-010**: The report footer, PDF and shared view MUST show "Datos en vivo · <fuente> · consultado
  <hora>" for direct reports; auto-refresh "Al llegar datos nuevos" (015) MUST behave as "cada
  `cache_seconds`" for direct reports.

#### Authoring
- **FR-011**: Validation MUST check, when a source description is available (backend always; CLI with
  `describe` data), that each declared table exists, each declared column exists with a compatible
  type, and that the date column is `date` or `timestamptz`/`timestamp`.
- **FR-012**: The agent's authoring pack (017 FR-001) MUST include the `direct` schema, a golden
  direct-report example, and the rule "usa modo directo solo si el usuario indica que los datos ya
  están preparados por otro proceso; si no, crea una integración"; `check_query` MUST accept a direct
  report to test its generated KPI query with `LIMIT 0`.
- **FR-013**: The 014/017 preview MUST render a direct draft report from the live source (marked
  "Vista previa", with PDF) without a temporary schema; readiness for a direct-only draft = validation
  passed + structure matched + preview succeeded.

#### Operations
- **FR-014**: Administración → Espacio de trabajo and the workspace API MUST show per report its mode
  (Dataset / Directo), source and tables; the integrations page is unaffected.
- **FR-015**: Each direct query MUST be logged with report, source, duration, rows and outcome (no
  values); the security overview counts direct reads per source over the last 24 h.

### Key Entities

- **Direct report**: a report whose data comes from `direct.source` + `direct.tables` instead of
  datasets; same views and outputs.
- **Direct table**: alias, `schema.table`, column contract.
- **Direct source permission**: per catalogue source flag + `DIRECT_REPORTS_BI` for the BI database.
- **Direct result cache entry**: report, selection hash, time bucket, payload, computed at, stale flag.
- **Direct read log entry**: report, source, time, duration, rows, outcome (no values); kept 7 days;
  feeds the 24 h count of FR-015 and the broken/failing status of FR-014.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From an existing table, a super user goes from "nueva spec" to a working dashboard
  without creating any integration, in one apply (e2e).
- **SC-002**: Cached views of a direct report answer in under 200 ms (p95) and cold views within
  `timeout_seconds`, on the reference test table of 1 million rows with an index on the date column.
- **SC-003**: 0 statements other than read-only SELECTs reach a source through direct reports (test
  with a source role that logs statements); 0 product tables readable through `bi` (test over every
  table of the Alembic metadata).
- **SC-004**: With the source down, a dashboard that was viewed before still shows figures (stale)
  in 100% of runs, and shows a clear error otherwise; no request hangs longer than the timeout + 1 s.
- **SC-005**: Existing dataset reports produce byte-identical API responses before and after this
  feature (regression suite).

## Assumptions

- Only PostgreSQL-family sources support direct mode in this version (catalogue kind PostgreSQL and
  the BI database). Supabase connected through its PostgreSQL connection string (kind PostgreSQL)
  works; Supabase through REST does not (no server-side aggregation).
- The tables are already "tested" by their owner process; BizView does not run integration checks on
  them. `row_count`-style checks remain an integration feature.
- The existing `report_cache` table can hold direct results keyed by time bucket; no new cache
  component.
- Reports keep one data path each; mixing datasets and direct tables in one report is out of scope.
