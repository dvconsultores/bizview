# Feature Specification: BI-ready sources — dashboards straight from a curated database

**Feature Branch**: `main` (this repository works on `main` only; no feature branches)

**Created**: 2026-11-01

**Status**: Draft

**Input**: Owner, 2026-10-31: "A database connection can already be BI-ready, so no new `ds_`
schema or integration is needed: read directly from the DB and put it in the dashboard."
Brief: `pendind_specs/048-bi-ready-sources-spec.md`.

**Builds on**: 004 (sources, encrypted credentials, SSRF rules), 019 (direct mode in
`report.yaml`), 043 (external authoring, structure packs), 005/026/030 (report engine, layouts,
palette), 031 (import), 045 (the authoring agent is gone; there is no in-app author).

## What already exists (verified in the code, 2026-11-01)

The brief's premise — that direct reports "bypass every protection the ETL path gives (timeouts,
limits, caching, schema allow-lists)" — is **not what the code does today**. Before planning
anything on top of it, this is what 019 actually shipped:

| Concern | Today | Where |
|---|---|---|
| Declaring a source readable | per-source `direct_reports` flag, PostgreSQL only (`check (direct_reports = false or kind = 'postgresql')`) | `app/models.py`, audited as `source_direct_reports_changed` |
| Read-only guarantee | `READ ONLY`-style session, `SET LOCAL statement_timeout`, read-only role required under `SECURITY_PROFILE=internet` | `app/engine/direct.py`, `app/security/profile.py` |
| Schema allow-list | deny-list of reserved/`app_test_*`/`preview_*`/product tables, plus the BI database's own product tables | `app/engine/direct.py`, `bizview_cli/validate.py` (`DIRECT_RESERVED_*`) |
| Concurrency | `DIRECT_REPORT_CONCURRENCY` (default 2) per source | `app/config.py` |
| Result cache | per-report `cache_seconds` (default 300 s) bucketed in the cache key | `app/engine/report.py` |
| Traceability | one row per direct read (`direct_read_log`) | `app/models.py` |
| Row volume warning | `DIRECT_REPORT_WARN_ROWS` (default 5 000 000) on the date column | `app/config.py` |

So this feature does **not** add the protections — they exist. What it adds is the thing the brief
is really after: **the scope and the limits become the source's own declared contract** (which
schemas, which objects, what timeout, what cache TTL, what row cap, which timezone), verified at save
time and visible in the product, instead of installation-wide environment constants that every
source inherits and nobody can see.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declare a source as BI-ready (Priority: P1)

In Fuentes de datos, the super user opens a PostgreSQL source and turns on **"Lista para BI"**:
picks the schemas (and optionally the tables or views) reports may read, confirms the credential is
read-only, and sets the query timeout, the cache lifetime and the row cap. From then on the
structure pack says the source is BI-ready and lists only the allowed objects.

**Why this priority**: without the declaration there is nothing to read from; it is the whole
front door of the feature.

**Independent Test**: turn it on for a source with one allowed schema and one excluded, produce the
structure pack, and check that the pack lists exactly the allowed objects and that the source page
shows the limits that were set.

**Acceptance Scenarios**:

1. **Given** a PostgreSQL source, **When** "Lista para BI" is turned on, **Then** Bizview proves the
   credential can `SELECT 1` and cannot write (a refused `CREATE TEMP TABLE` or `INSERT` is the
   proof), stores the scope and the limits on the source, and records the change in the audit trail.
2. **Given** a source of any other kind (REST, SOAP, Supabase), **Then** the option is not offered,
   and an API call that tries to set it is refused naming why.
3. **Given** a BI-ready source, **When** the structure pack is produced, **Then** `structure.md`
   says reports may read it directly and lists only the allowed schemas and objects, with columns,
   types and which are keys, flagging columns that look like personal data.
4. **Given** a source with "Lista para BI" off, **Then** a report that reads it directly is refused
   at validation with the setting named.

---

### User Story 2 - A report reads the BI-ready source directly (Priority: P1)

The author writes a report with `direct:` — no integration, no `ds_` schema — and everything else
(metrics, dimensions, filters, periods, comparison, views, layout, PDF, share links, TV mode) behaves
as it does for an integration-backed report.

**Why this priority**: this is the value; without it the declaration is inert.

**Independent Test**: build a direct report against a seeded view and render the same dashboard,
PDF and share link an equivalent integration-backed report renders.

**Acceptance Scenarios**:

1. **Given** a BI-ready source and

   ```yaml
   direct:
     source: Almacén ventas
     tables:
       v: reporting.v_ventas_dia
       p: reporting.dim_producto
   joins:
     - {left: v.producto_id, right: p.id}
   date: v.fecha
   ```

   **When** validated, **Then** every object is inside the source's scope, every referenced column
   exists in the source's structure, the join is on existing columns, and a personal-data column is
   refused unless the report records the decision.
2. **Given** the dashboard open, **When** data is requested, **Then** the query runs through the
   source's read-only connection with its timeout, its row cap (a truncated result says so) and its
   cache, and share links and TV mode read the same cache.
3. **Given** a source that is slow or unreachable, **Then** a dashboard with a cached result shows it
   with a "data from N minutes ago" notice, and a dashboard without one shows a typed error per
   tile — never a blank page.
4. **Given** `materialize: daily` on a direct report, **Then** the worker stores the report's figures
   nightly and the dashboard reads that snapshot with a "yesterday's data" notice; with
   `materialize: none` (default) the dashboard reads live.

---

### User Story 3 - The person responsible can see it working (Priority: P2)

The source page shows, for the last 24 hours, how many direct queries ran, how slow they were, how
many failed and how often the cache answered; a change in the source's structure or in the
credential's read-only status raises a notification.

**Why this priority**: a declared contract nobody can watch is a contract that silently breaks.

**Independent Test**: run a few direct queries (one fast, one refused, one cached) and read the
numbers on the source page; then drop a view and check the notification.

**Acceptance Scenarios**:

1. **Given** direct queries ran in the last day, **Then** the source page shows their count, a
   typical and a slow-case duration, the error count and the cache hit rate.
2. **Given** an object in the scope disappeared or changed its columns, **Then** validating a report
   that uses it names the object, and the admin is notified.
3. **Given** the credential stopped being read-only, **Then** the daily check records it and the
   admin is notified.

---

### Edge Cases

- A report mixes `direct:` and `uses:`: refused — one or the other.
- Two reports read the same BI-ready source with different aliases: allowed.
- A view in the scope is dropped while a dashboard is open: typed error per tile plus the
  notification; the cache keeps answering until its TTL, then the error.
- A declared object resolves outside the scope (a view that reads a forbidden schema): refused at
  validation, and the engine still refuses at execution — the checker is not the only guard.
- Time zones: the date column is read in the source's declared timezone; periods behave as they do
  for `ds_*` tables.
- Personal data: columns whose name looks personal are excluded unless the report and its spec record
  the decision.
- Importing a project whose report reads a source that is not BI-ready on the target installation:
  the import says so and names the setting.
- Existing 019 direct reports, including `source: bi`, keep rendering without edits.

## Requirements *(mandatory)*

### The declaration

- **FR-001**: A PostgreSQL source carries a BI-ready declaration: whether it is one, the schemas it
  exposes, optionally the objects inside them, the query timeout, the cache lifetime, the row cap,
  the concurrency and the timezone in which its dates are read. Only the super user changes it, and
  every change is audited.
- **FR-002**: Turning it on proves the credential reads and cannot write; a credential that can write
  is refused with the reason. The proof is repeated daily and a change is reported.
- **FR-003**: The declaration is the whole truth for the scope: an object outside it is refused at
  validation *and* at execution, whichever door the request came through.

### The report

- **FR-004**: A report declares `direct: {source, tables}` — alias to `schema.object` — and may add
  joins and a date column. It cannot also declare `uses`. The objects' columns come from the source's
  structure, so the author writes no column list.
- **FR-005**: The declarations that exist today keep working: 019's form (alias to an object with a
  declared column contract) and `source: bi` resolve as they do now, and a report written either way
  renders the same.
- **FR-006**: Validation refuses, naming file and path: an object outside the scope, a column that
  does not exist, a join on columns that are not there, a personal-data column without the recorded
  decision, and anything that is not a single read-only query.

### Running it

- **FR-007**: A direct query runs read-only, under the source's timeout and row cap, at most the
  source's concurrency at a time, and its result is cached for the source's lifetime keyed by the
  report and its parameters. A truncated result says it was truncated.
- **FR-008**: When the source is slow, unreachable or changed, the dashboard shows the cached result
  with its age, or a typed error per tile; it never renders blank, and a failure never reaches
  another dashboard.
- **FR-009**: `materialize: daily` stores the report's figures nightly and the dashboard reads the
  snapshot with its date; `none` (the default) reads live.

### Seeing and documenting it

- **FR-010**: The source page shows, for the last 24 hours: how many direct queries ran, how long
  they took, how many failed and how often the cache answered.
- **FR-011**: The structure pack and `PROMPT.md` explain how to write a direct report, when an
  integration is the better answer (transactional systems, cross-source joins, heavy history), and
  what the limits are.
- **FR-012**: The admin is notified when an object in the scope disappears or changes, or when the
  credential stops being read-only.

### Principles

- **FR-013**: The constitution's principle II ("never query the origin on every request") is amended:
  a source the super user declares BI-ready is an optimized model **by declaration**, carrying the
  read-only proof, the scope, the limits and the cache this feature defines. Transactional origins
  stay behind integrations, unchanged.

## Key Entities

- **BI-ready declaration**: on a data source; what it exposes, the limits it imposes, the timezone,
  and the last time its credential was proven read-only.
- **Direct report**: a report whose data comes from declared objects of one source rather than from
  an applied integration.
- **Direct read**: one executed direct query, recorded with its report, its source, its duration,
  its outcome and whether the cache answered.
- **Snapshot**: the figures a `materialize: daily` report stored on a given day.

## Success Criteria *(mandatory)*

- **SC-001**: A direct report over a seeded reporting view renders the same dashboard, PDF and share
  link as the equivalent integration-backed report (fixture parity).
- **SC-002**: Every adversarial query tried — a write, a DDL statement, a product table, an object
  outside the scope, a second statement — is refused before it reaches the database: 100 % of them.
- **SC-003**: With a source that takes 60 s to answer, a dashboard shows the cached result or the
  typed error within the source's timeout, and no request hangs.
- **SC-004**: 50 viewers of one direct dashboard produce at most one query per cache lifetime for
  each distinct set of parameters.
- **SC-005**: From the authoring pack alone, an author produces a direct report that validates within
  two rounds.
- **SC-006**: Every 019 direct report on this installation keeps rendering after the upgrade, and
  `source: bi` keeps working.
- **SC-007**: The super user can answer "what may be read from this source, and with what limits"
  from the source page alone, without reading a manual or an environment file.

## Assumptions

- **BI-ready sources are PostgreSQL** (warehouses, reporting schemas, replicas with views). Other
  engines later, behind the same declaration.
- **The read-only credential is the customer's**; Bizview proves it and refuses a writable one, and
  does not create roles.
- **Cross-source joins are out of scope**: a BI-ready source joined with an integration's dataset
  stays an integration's job.
- **The declaration replaces environment constants, it does not add a second set.** `DIRECT_REPORTS_BI`,
  `DIRECT_BI_ROLE`, `DIRECT_REPORT_CONCURRENCY` and `DIRECT_REPORT_WARN_ROWS` become defaults a
  source can override; the internet-profile rule that demands a read-only role stays.
- **Both `direct.tables` shapes are accepted**: alias to `schema.object` (columns read from the
  source) and 019's alias to a declared column contract. The second is what makes `source: bi` and
  every existing report keep working; the first is what makes a BI-ready source writable by hand or
  by an AI without copying a column list.
- **`materialize: daily` is in scope** because the brief asks for it and the worker already exists;
  it stores figures, never rows.
- **A personal-data column is recognised by name heuristics** (as 015 did), and a report may read one
  only when it records the decision in `allow_personal`.
- **The constitution is amended to 3.2.0 (MINOR)**, not "2.1.0" as the brief says: 046 already moved
  it to 3.1.0 and a version never travels backwards.
