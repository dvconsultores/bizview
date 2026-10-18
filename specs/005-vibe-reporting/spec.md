# Feature Specification: Vibe Reporting — every integration and report is a spec

**Feature Branch**: `005-vibe-reporting`

**Created**: 2026-09-29

**Status**: Implemented (closed 2026-10-12; amendment 2026-10-08: **SC-A01 met at the median** (+28.6 %, 5 same-host runs) after the transform optimizations and the 20 000-row default, **SC-A02 met** at 50 M rows on a local database)

**Input**: User description: "Forget the assistant. The user must work mandatorily with GitHub Spec
Kit: every report, integration and ETL must be handled by a spec. A new report can use an
existing integration from another integration spec, so there can be one spec for an integration
and n specs for reports. Without a spec the AI will not work; it is up to the user to learn vibe
reporting — it can be the slogan: *vibe reporting*. Change the assistant spec for this."

## Clarifications

### Session 2026-09-29

Answered autonomously with the recommended option, at the user's request.

- Q: Where do a customer's integration and report specs live? → A: In a **workspace**: a private
  Git repository per customer (e.g. Customer B's), created from the product's workspace template,
  with Spec Kit initialised. Never in the product repository (constitution VII). The installation
  reads a checkout of that workspace.
- Q: How does the user work? → A: In their editor (VS Code, Claude Code, or any Spec Kit agent)
  inside the workspace: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`. The AI writes only declarative artifacts (queries, mappings, report
  definitions) that belong to a spec. The in-app chat assistant is dropped.
- Q: What does "without a spec the AI will not work" mean in the product? → A: (1) The engine
  refuses to load or run any integration or report whose spec is missing, incomplete, or changed
  since it was validated; (2) the product's AI provider (feature 003) is used only by report
  sections that an approved report spec declares, with the inputs the spec lists; (3) the workspace
  template instructs AI agents to refuse work that is not tied to a spec.
- Q: How do integrations and reports relate? → A: An **integration spec** defines how data comes
  from one data source (feature 004) into named datasets. A **report spec** consumes datasets from
  one or more integration specs and defines metrics, views, access, and exports. One integration →
  n reports; one report → m integrations.
- Q: What replaces feature 001 (sales dashboard)? → A: Its requirements become (a) generic engine
  capabilities (periods, comparisons, trends, product rankings, PDF export, freshness) and (b)
  Customer B's first workspace specs: integration `erp-ventas` and report `ventas`,
  written with vibe reporting itself. Feature 001 is marked superseded.
- Q: How is a workspace deployed to an installation? → A: The installation mounts a checkout of the
  workspace read-only (`/opt/bizview/workspace`). The super user validates and applies it from the
  interface or the command line; the applied version (commit, checksums) is recorded and audited.
  Updating = `git pull` (manually or by the customer's CI) + apply.

## User Scenarios & Testing *(mandatory)*

Actors: the **report author** (a power user, analyst, or implementer who works in the workspace
with an AI agent), the **super user** of the installation (applies workspace versions), and
**report viewers** (read dashboards).

### User Story 1 - Start a customer workspace (Priority: P1)

The report author creates the customer's workspace from the product's template with one command.
It is a Git repository with Spec Kit initialised, the Bizview templates for integration and report
specs, the Vibe Reporting constitution, agent instructions, a validator, and an example. The
author opens it in VS Code and the AI agent already knows the rules.

**Why this priority**: nothing can be built for a customer without a workspace.

**Independent Test**: run the init command in an empty folder; open it with an AI agent; ask for
"a sales report" — the agent starts with `/speckit-specify` for a report spec and asks which
integration it uses, instead of writing SQL directly.

**Acceptance Scenarios**:

1. **Given** an empty folder, **When** the init command runs, **Then** the workspace contains the
   Spec Kit setup, `specs/integrations/`, `specs/reports/`, `integrations/`, `reports/`, the
   Bizview templates, the workspace constitution, agent instructions, and a README explaining
   vibe reporting.
2. **Given** a workspace, **When** an AI agent is asked to create a report without a spec, **Then**
   the agent instructions direct it to create the spec first.
3. **Given** the workspace, **When** it is pushed to a private Git host, **Then** it contains no
   secrets (source credentials stay in the installation's encrypted catalogue).

---

### User Story 2 - Write an integration spec and implement it (Priority: P1)

The report author specifies an integration: which data source (by its catalogue name), which
business data (e.g. completed sales lines, products, returns), the dataset columns and meaning,
schedule, incremental window, and quality checks. The AI plans and implements it as declarative
artifacts: read-only queries (PostgreSQL) or request definitions (REST/SOAP), mappings, and
checks. The validator confirms the artifacts match the spec's dataset contract.

**Why this priority**: reports need data; integrations are the foundation and are reused.

**Independent Test**: write Customer B's `erp-ventas` integration spec; implement;
validate; apply to the local installation; run it; the datasets are filled and the checks pass.

**Acceptance Scenarios**:

1. **Given** an integration spec with plan and all tasks done, **When** the workspace is validated,
   **Then** the integration is accepted and its datasets are listed with columns and types.
2. **Given** an integration artifact that writes (INSERT/UPDATE/…) or references a source that is not
   in the installation's catalogue, **When** validated or applied, **Then** it is refused.
3. **Given** an applied integration, **When** it runs on its schedule, **Then** its datasets are
   replaced for the incremental window in one transaction, runs are recorded (rows, duration,
   checks), and a failed run leaves the previous data intact.
4. **Given** an integration whose query results do not match the dataset contract (missing column,
   wrong type), **When** it runs, **Then** the run fails with a clear message and nothing is loaded.

---

### User Story 3 - Write report specs that reuse integrations (Priority: P1)

The report author specifies a report: which integration datasets it uses (one or several), its
metrics (e.g. net sales, orders, average order value) with exact definitions, dimensions, period
presets and comparisons, views (KPI cards, trend, ranking table), who may see it, PDF export, and
optionally an AI narrative section with the aggregates it may use. The AI implements it as a
declarative report definition. Once applied, the report appears as a dashboard on users' home
pages and renders on phones.

**Why this priority**: reports are what customers pay for; reuse of integrations is the point.

**Independent Test**: write report specs `ventas` and `productos` both using the
`erp-ventas` integration; apply; both appear as dashboards; figures match the
integration's data.

**Acceptance Scenarios**:

1. **Given** a report spec depending on an integration that is not in the workspace or not applied,
   **When** validated, **Then** it is refused with the missing dependency named.
2. **Given** two report specs using the same integration, **When** applied, **Then** both work from
   the same datasets (no duplicate extraction).
3. **Given** an applied report, **When** a viewer granted access opens it on a phone, **Then** KPIs,
   trend, and tables render at 320 px, with period selection and comparisons as the spec defines.
4. **Given** a report spec with an AI narrative section and AI enabled, **When** the report is
   viewed, **Then** a narrative is generated only from the aggregates the spec lists; with AI off,
   the section is hidden and the report still works.
5. **Given** a report, **When** the viewer exports PDF, **Then** the PDF shows the same figures as the
   screen for the same selection.

---

### User Story 4 - Validate and apply a workspace version safely (Priority: P2)

The super user sees the mounted workspace version (commit, date), runs validation, reviews what
will change (integrations and reports added, changed, removed; dataset schema changes), and
applies it. Specs that are missing, not approved, have open tasks, or whose files changed after
validation are refused. Every apply is audited and can be rolled back to the previous version.

**Why this priority**: the gate that makes "no spec, no run" real.

**Independent Test**: change one line of an applied report's definition without updating its spec
lock → apply refuses; revert → apply succeeds; roll back → previous version active.

**Acceptance Scenarios**:

1. **Given** an artifact whose spec folder lacks `spec.md`, `plan.md`, or `tasks.md`, or has open
   tasks, **When** validated, **Then** it is refused naming the spec and reason.
2. **Given** a validated workspace, **When** a file of an integration or report changes without
   re-validation, **Then** apply refuses (checksum mismatch).
3. **Given** an apply, **When** it completes, **Then** the audit log records the actor, commit,
   and the list of changes; the previous version remains available for rollback.
4. **Given** a report removed from the workspace, **When** applied, **Then** its dashboard is hidden
   (not deleted) and its access grants are kept for a possible return.

---

### User Story 5 - Describe a data source for spec writing without exposing data (Priority: P2)

To write an integration spec, the author (via the AI agent) needs the source's structure. A
command, authorised with a personal token of the super user, returns the source's schema — tables,
columns, types, row-count estimates, or for REST/SOAP the operations and response shapes — never
row values or credentials.

**Why this priority**: good specs need accurate structure; data must not leak into AI prompts.

**Independent Test**: run the describe command for Customer B's origin; output lists tables and
columns of the customer's ERP with estimated counts and no row data.

**Acceptance Scenarios**:

1. **Given** a valid token, **When** describe runs for a PostgreSQL source, **Then** it returns
   schemas, tables, columns, types, keys, and estimated counts only.
2. **Given** no token or an expired/revoked token, **When** describe runs, **Then** it is refused.
3. **Given** a describe request, **When** it completes, **Then** it is audited.

---

### Edge Cases

- Two integrations producing the same dataset name → refused (dataset names are namespaced by
  integration id).
- A report metric referencing a column that the integration does not produce → validation error.
- An integration changes a dataset's columns while reports depend on it → validation lists the
  affected reports; apply requires those reports to be updated in the same version.
- Workspace not mounted → the admin page explains how to mount it; the product keeps working with
  the last applied version.
- Integration run exceeds its time limit → stopped, marked failed, previous data kept.
- Source disabled in the catalogue → its integrations are paused and flagged.
- Very large extraction → processed in slices defined by the integration (e.g. month).
- Report viewed while its integration is running → consistent snapshot (previous data until the
  run commits).

## Requirements *(mandatory)*

### Functional Requirements

**Spec discipline ("no spec, no run")**

- **FR-001**: Every integration and every report MUST be backed by a Spec Kit feature folder in the
  workspace (`specs/integrations/<id>/` or `specs/reports/<id>/`) containing `spec.md`, `plan.md`,
  and `tasks.md` with all tasks completed, and a spec status of `Approved` or `Implemented`.
- **FR-002**: The engine MUST refuse to load, run, or display any integration or report whose spec
  folder is missing, incomplete, not approved, or whose spec or artifacts changed after validation
  (checksums in a lock file produced by the validator).
- **FR-003**: The product's AI provider MUST only be invoked by report sections declared in an
  applied report spec, with the aggregate inputs that spec lists; there is no free-form AI entry
  point in the product.
- **FR-004**: The workspace template MUST instruct AI agents (Claude Code, Copilot, Cursor, and
  generic `AGENTS.md`) to refuse integration/report work not tied to a spec, and to follow the
  Spec Kit sequence.

**Workspace**

- **FR-005**: A command MUST create a workspace: Git repository, Spec Kit initialised with the
  Bizview preset (integration and report spec, plan, and task templates), workspace constitution,
  agent instructions, validator configuration, README ("vibe reporting"), and an example
  integration and report.
- **FR-006**: The workspace MUST contain no credentials; integrations reference data sources by
  their catalogue name (feature 004).
- **FR-007**: An installation MUST read the workspace from a read-only mounted folder and record the
  applied version (commit hash if Git, content checksum always, time, actor).

**Integrations**

- **FR-008**: An integration artifact MUST declare: id, spec reference, data source name, datasets
  (name, columns with types and meaning, primary key), extraction per dataset (read-only SQL for
  PostgreSQL; request definition for REST and SOAP including pagination), incremental window and
  slicing, schedule, time limit, and quality checks (row count bounds, not-null keys, optional
  reconciliation query).
- **FR-009**: SQL extraction MUST be validated as a single read-only `SELECT`/`WITH` statement and
  run in a read-only transaction; REST/SOAP extraction MUST use the source's connector and
  security rules (feature 004).
- **FR-010**: Datasets MUST be stored in the product database in a schema per integration
  (`ds_<integration>`), created and altered only by the engine from the integration's contract;
  each run replaces the window atomically and records rows, duration, and check results.
- **FR-011**: Runs MUST be scheduled by the worker, never overlap for the same integration,
  survive restarts, and be triggerable manually by the super user.

**Reports**

- **FR-012**: A report artifact MUST declare: id, spec reference, integrations/datasets used,
  metrics (formula over datasets, format, unit, direction "higher is better"), dimensions, period
  presets and default, comparison options, views (KPI cards, trend chart, ranking table, detail
  table), access (which roles/users see it), PDF export, and optional AI narrative (inputs: named
  metrics/aggregates only).
- **FR-013**: The engine MUST provide period handling (today, yesterday, last 7 days, month to date,
  last month, quarter to date, year to date, last 12 months, custom), comparisons (previous period,
  same period last year) with zero-base handling, and freshness ("updated at") — the generic
  behaviour previously specified in feature 001.
- **FR-014**: Each applied report MUST appear in the dashboard catalogue (feature 002) with its
  name, description, and icon; access follows the report's declared access plus explicit grants.
- **FR-015**: Report views MUST be rendered by the product from the definition (no custom code per
  report), mobile first, accessible (WCAG 2.2 AA), responsive from 320 px.
- **FR-016**: PDF export MUST render the same figures as the screen for the same selection.

**Apply, rollback, describe**

- **FR-017**: Validation MUST check: spec discipline (FR-001), artifact schemas, dependency graph
  (reports → integrations → sources), read-only SQL, dataset contract compatibility, metric
  references, and dataset schema changes affecting reports.
- **FR-018**: Apply MUST show a change summary, require step-up confirmation (feature 004), be atomic,
  audited, and keep the previous applied version for one-click rollback.
- **FR-019**: A describe endpoint/command MUST return a source's structure (never values or
  credentials), authorised by a personal access token that the super user creates, names, scopes to
  `describe`, can revoke, and sees only once; every use is audited.
- **FR-020**: The command-line tool used in the workspace (`bizview validate`, `bizview describe`)
  MUST run without the product's database for `validate` (static checks) and call the
  installation's API for `describe`.

### Key Entities

- **Workspace**: the customer's spec repository; versions identified by commit/checksum.
- **Integration Spec / Integration**: spec folder + artifact defining datasets from one source.
- **Dataset**: a named table produced by an integration, with a column contract.
- **Report Spec / Report**: spec folder + artifact defining metrics and views over datasets.
- **Workspace Version (applied)**: the validated, applied set with lock checksums; one active,
  previous kept for rollback.
- **Integration Run**: one execution with window, rows, duration, checks, outcome.
- **Access Token**: personal, scoped (`describe`), hashed at rest, revocable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of integrations and reports running in an installation have an approved,
  complete spec; any artifact without one is refused (verified by validation tests).
- **SC-002**: A report author creates a new report on an existing integration — spec to visible
  dashboard — in under 1 hour with an AI agent, without writing application code.
- **SC-003**: Adding a second report on an existing integration adds no extraction load (0 extra
  source queries).
- **SC-004**: A report view answers in under 1 second at the 95th percentile for 2 years of daily data.
- **SC-005**: Rollback to the previous workspace version takes under 1 minute and one action.
- **SC-006**: No row values or credentials appear in describe output, AI inputs, or the workspace
  repository (verified by marker tests).

## Assumptions

- Report authors are willing to learn the Spec Kit flow ("vibe reporting"); viewers never see it.
- Workspaces are hosted in the customer's (or implementer's) private Git; the installation needs
  only a read-only checkout.
- Feature 004 (data sources, encryption, security profile) is in place; integrations use its
  catalogue and connectors.
- The worker service (APScheduler, constitution V) runs integrations; it shares the backend's
  source connectors.
- Customer B's first integration (`erp-ventas`) and report (`ventas`) are delivered as
  workspace specs after this feature, replacing feature 001's product-level design.

## Amendment 2026-10-08 (owner): ETL transform stage in Polars (Rust)

Owner, 2026-10-08 (prompt.md): "remember ETL uses Rust (Python lib Polars) (converge spec)".
Constitution 2.0.0 principle V. Extraction (COPY for PostgreSQL, Polars batches for REST/SOAP) and
load (COPY into staging, all-or-nothing publish) are unchanged; this adds the **T** of ETL as an
optional, declarative stage that runs in Polars between them.

- **FR-A01**: A dataset MAY declare `transform: {sql: <SELECT … FROM input …>}`. The SQL MUST be a
  single read-only SELECT over the frame `input` (the extracted columns), checked with sqlglot
  against an allow-list of scalar functions, operators, `CASE`, `COALESCE`, casts, string and date
  functions, and (whole mode only) `GROUP BY`, `DISTINCT`, window functions; it runs in the Polars SQL
  engine (`pl.SQLContext`), never in Python per row. No user code, no UDFs, no file or network
  access.
- **FR-A02**: The transform output columns and types MUST match the dataset `columns` contract
  (checked at validation from the declared input columns and again on each run); a mismatch fails
  the run before any load.
- **FR-A03**: Row-wise transforms (no aggregation, `DISTINCT`, window or `ORDER BY`) MUST run in
  batches of `transform.batch_rows` (default 200,000) streamed between the extraction and the staging
  COPY, so memory stays bounded; other transforms run on the whole window with the Polars streaming
  engine (lazy frame over the staged window, `collect(engine="streaming")`, spilling to the
  container's temp folder), so memory stays bounded without a fixed row cap;
  `TRANSFORM_MAX_ROWS` (default 50,000,000) remains only as a safety stop with a clear error.
- **FR-A04**: For PostgreSQL sources the COPY fast path (008) is kept when there is no transform;
  with a transform the extraction streams COPY output into Polars batches and the result is loaded
  with COPY.
- **FR-A05**: The run history MUST show the path used (`copy`, `copy+polars`, `rows+polars`) and the
  transform duration; the agent's authoring pack and `check_query` cover the transform (output
  columns checked on an empty frame of the declared types).
- **SC-A01**: On the 008 benchmark (1 million rows), a row-wise transform adds at most 30% to the
  extraction-to-load time and at most 150 MB to the peak memory of the same run without a transform
  (clarified 2026-10-09: the COPY path alone already peaks near 270 MB in the worker process).

### Amendment 2026-10-08 (owner, second part): big-data readiness

Owner, 2026-10-08: "ok proceed — we can manage partitions in the long term; big data is another scope
for later if the project succeeds." Found while reviewing: `report.yaml` accepts `materialize: daily`
but the engine never builds it, so every uncached view aggregates raw dataset rows.

- **FR-A06**: `materialize: daily` MUST be implemented: for each report that declares it, the engine
  keeps a rollup table `ds_<integration>.mv_<report>` (day × every declared dimension used by views
  and filters × each SQL metric's additive components: sum, count, min, max; `avg` stored as sum +
  count; `count_distinct` metrics make the report ineligible and fail validation with the reason).
- **FR-A07**: Rollups MUST be refreshed by the worker after each successful run of the integrations
  the report uses, only for the days touched by the run's window (full rebuild after a full run), in
  the same all-or-nothing publish; a failed refresh keeps the previous rollup and marks the run.
- **FR-A08**: When a rollup exists and is fresh for the selection, KPIs, trends (day/week/month),
  rankings, tables and filter options MUST be answered from it; results MUST equal the raw-path
  results (test on every view type and comparison); `table` views listing raw rows keep the raw path.
- **FR-A09**: Validation MUST tell the author when a report over a dataset expected above
  `DIRECT_REPORT_WARN_ROWS` (5 million) rows does not declare `materialize: daily`; the agent proposes
  it by default for such reports.
- **SC-A02**: On a 50-million-row dataset (reference machine), a materialized report answers cold
  views in under 1 s (p95) and the rollup refresh after an hourly incremental run takes under 30 s.
- **Deferred (owner, later scope)**: monthly partitioning of large datasets and columnar engines
  (ClickHouse/DuckDB) for billions of rows — "big data" scope, only if the project succeeds.


### Clarifications 2026-10-09 (plan analysis, adopted by the orchestrator)

These refine FR-A01–FR-A09 (see plan-amendment-2026-10-08.md, "Spec issues"):

- **C1 (FR-A01/A02)**: a dataset with a transform declares the extracted columns in
  `transform.input` (name → type); the query/request must return exactly those; `columns` is the
  transform output.
- **C2 (FR-A06)**: rollup table = `ds_<integration of the report's date dataset>.mv_<report id with
  "-" replaced by "_">`.
- **C3 (FR-A06)**: a report is ineligible for `materialize: daily` when a metric uses `DISTINCT`
  inside an aggregate, percentiles, `stddev`, `variance`, `string_agg`, `bool_or/and`, window
  functions or `current_date`, or a dimension uses an aggregate or `current_date`.
- **C4 (FR-A07)**: the rollup refresh runs inside the publish transaction under a savepoint; if it
  fails the data is still published, the previous rollup is kept but marked stale (reports use raw
  rows until it is rebuilt) and the run records the failure. Refreshed days = the days of every base
  row deleted, updated or inserted by the run; any change in another dataset the report joins →
  full rebuild.
- **C5 (FR-A08)**: the "raw-row table views" clause is void (every `table` view aggregates). A rollup
  is fresh when built from the latest successful run of every integration the report uses, with the
  active report definition.
- **C6 (FR-A08)**: equivalence = equal for sums, counts, minima, maxima, keys and order; averages and
  formulas equal to 12 significant digits.
- **C7 (FR-A09)**: the expected row count comes from the published dataset table (server validation)
  or the origin profile (agent); offline CLI validation cannot warn.
- **C8 (FR-A05)**: run paths are `copy`, `rows`, `copy+polars`, `rows+polars` (`bulk` in older runs is
  shown as `copy`).
- **C9 (FR-A03)**: whole-mode transforms read a lazy frame over the window spilled to Arrow files in
  the temp folder; `TRANSFORM_MAX_ROWS` applies to whole-mode input rows (row-wise memory is bounded
  by the batch).
- **C10 (FR-A01)**: "date functions" means those the engine supports (`extract`, `strftime`,
  `strptime`, casts); casting a time zone-aware timestamp to a date is refused (use `strftime`).
- **C11 (SC-A02)**: the reference machine is described in specs/008-fast-pg-extraction/research.md
  (CPU, RAM, disk, PostgreSQL version, local database) when the benchmark is recorded.
