# Feature Specification: Faster PostgreSQL extraction

**Feature Branch**: `008-fast-pg-extraction`

**Created**: 2026-10-01

**Status**: Implemented (closed 2026-10-12) — **SC-001 met** on a same-host origin: 6.0x at 1 M rows (T020; SC-002 met, T042 in 005 covers the SC-A01 transform overhead)

**Input**: User description: "Faster PostgreSQL extraction: when an integration reads from a
PostgreSQL source, stream the origin's bulk export (the query's result as a bulk copy) straight
into the staging table instead of fetching rows into the application and converting each value;
keep the read-only guarantees, the spec-declared columns, the time limits and the checks; fall
back automatically to the current path when the source does not allow bulk export; REST and SOAP
sources keep their current path. Update the constitution, which still says extraction uses
Polars with ConnectorX."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Large PostgreSQL integrations finish much faster (Priority: P1)

An implementer runs (or the schedule runs) an integration whose source is a PostgreSQL
database. The data moves from the source into the installation's dataset in bulk, without the
product handling each value one by one, so a large full rebuild that used to take many minutes
finishes in a fraction of the time and the dashboards show fresh figures sooner. The results —
rows loaded, checks, run history — are exactly the same as before.

**Why this priority**: extraction time bounds how fresh the dashboards are and how large a
customer's history can be; it is the reason for the feature.

**Independent Test**: run the same integration (same source, same window) once with the bulk
path and once with the current path; compare duration, memory and the resulting dataset
(identical rows, identical check results).

**Acceptance Scenarios**:

1. **Given** an integration reading a PostgreSQL source, **When** it runs, **Then** the dataset
   contains exactly the rows and values the current path produces, and the run history records
   the same counts and check results.
2. **Given** a full rebuild of 1 million rows, **When** it runs, **Then** it completes at least
   5 times faster than the current path on the same source and server, and the product's memory
   use does not grow with the number of rows.
3. **Given** an incremental run, **When** it runs, **Then** only the rows of the run window are
   read, exactly as today.

---

### User Story 2 - Same safety guarantees (Priority: P1)

The super user and the source's owner keep every protection of today: the source is only read,
never written; only the spec's single validated query runs; the run stops at its time limit; the
values must match the declared column types, and a mismatch fails the run with a clear message
without touching the published dataset.

**Why this priority**: the source belongs to another system (constitution III); a faster path
that weakened these guarantees would be unacceptable.

**Independent Test**: attempt the known unsafe or broken cases — a query that writes, a run that
exceeds its time limit, a value that does not fit its declared type, a query whose columns differ
from the declared ones — and confirm each is refused or fails cleanly as today.

**Acceptance Scenarios**:

1. **Given** the bulk path, **When** an integration runs, **Then** the source session is read-only
   and only the validated query runs (any write is rejected by the source).
2. **Given** a query whose columns differ from the declared columns, **When** the run starts,
   **Then** it fails with the same message as today, before loading any row.
3. **Given** a value that does not match its declared type, **When** it is loaded, **Then** the run
   fails with a message naming the problem, and the published dataset is unchanged.
4. **Given** a run that exceeds its time limit, **When** the limit is reached, **Then** the run is
   stopped and recorded as failed, as today.

---

### User Story 3 - Sources without bulk export keep working (Priority: P2)

Some PostgreSQL-compatible sources (managed services, read replicas or other engines speaking
the PostgreSQL protocol) do not allow bulk export. For them the integration falls back
automatically to the current path, records which path was used, and still succeeds.

**Why this priority**: no existing integration may break; it only matters for some sources.

**Independent Test**: run an integration against a source that refuses bulk export and confirm
it completes with the current path and the run history says so.

**Acceptance Scenarios**:

1. **Given** a source that refuses bulk export, **When** the integration runs, **Then** it
   completes through the current path and the run history shows the path used and why.
2. **Given** a failure that is not about bulk export being unsupported (wrong data, time limit,
   connection lost), **When** it happens, **Then** the run fails as today and does not silently
   retry through the other path.

---

### Edge Cases

- Text containing line breaks, tabs, backslashes, quotes, non-Latin characters or emoji arrives
  unchanged.
- Empty strings and missing values stay distinct.
- Dates and timestamps keep their exact value regardless of the source's display settings and
  time zone; the installation time zone rules of today still apply.
- Very large numbers and decimals keep full precision.
- Origin values of types that are not contract column types (arrays, binary, JSON) placed in a
  declared text column are stored in the source database's own text form (as a SQL author gets
  with a text cast); the previous row path rendered them differently, and only it keeps that form.
- A query that returns no rows completes successfully with zero rows loaded.
- The source closes the connection mid-transfer: the run fails, nothing is published, and the
  staging data is discarded as today.
- REST and SOAP sources are not affected in any way.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Integrations with a PostgreSQL source MUST move the query result into the staging
  area in bulk, without the product converting individual values.
- **FR-002**: The product's memory use during extraction MUST stay bounded regardless of the
  number of rows transferred.
- **FR-003**: The source session MUST remain read-only, with the same statement time limit, time
  zone and application name as today; only the spec's validated single query may run, and the
  window parameters MUST be applied safely (never by unchecked text substitution).
- **FR-004**: The query's columns MUST be checked against the declared columns before any row is
  loaded, with today's message on mismatch; loaded columns MUST follow the declared order.
- **FR-005**: Values MUST be checked against the declared types during the load; a mismatch MUST
  fail the run with a message naming the problem and leave the published dataset unchanged.
- **FR-006**: The run's time limit MUST still stop the run, including during a long transfer.
- **FR-007**: For every contract column type, results MUST be identical to the current path: same
  rows, same values (including the edge cases above), same counts in the run history, same checks.
- **FR-008**: When the source refuses bulk export because it is not supported or not permitted,
  the run MUST fall back to the current path automatically; any other error MUST fail the run
  without fallback.
- **FR-009**: The run history MUST record which extraction path was used and, on fallback, the
  reason — never credentials or row values.
- **FR-010**: REST and SOAP sources MUST keep their current behaviour.
- **FR-011**: The project constitution MUST describe the extraction approach the product actually
  uses (it currently names a tool combination the code does not use).

### Key Entities

- **Integration run**: gains the extraction path used (`bulk` or `rows`) and, on fallback, the
  reason; everything else unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A full rebuild of 1 million rows from a PostgreSQL source completes at least 5× faster
  than the current path on the same hardware and data.
- **SC-002**: Peak memory of the extraction process varies by less than 50 MB between a 10 thousand
  and a 1 million row run.
- **SC-003**: For a reference dataset covering every contract column type and the text edge cases
  above, the bulk and current paths produce identical dataset contents in 100% of runs.
- **SC-004**: 100% of the existing unsafe/broken-case tests (writes, time limit, type mismatch,
  column mismatch) still fail or are refused as before.
- **SC-005**: Integrations against sources that refuse bulk export succeed in 100% of runs through
  the fallback, with the path recorded.

## Assumptions

- The installation and the source are both PostgreSQL (or protocol-compatible); the bulk path is
  attempted for every PostgreSQL source, with fallback for the ones that refuse it.
- Reconciliation queries (small, checked result sets) keep their current path.
- The customer-facing workspace artifacts (integration and report specs) do not change; no spec
  needs to be rewritten.
- The current path is kept as the fallback, not removed.
- Benchmarks are run on a test source populated by a script; customer data is not used.
