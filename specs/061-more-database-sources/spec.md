# Feature Specification: More database sources — SQLite, MySQL/MariaDB, SQL Server, BigQuery, Google Sheets

**Feature Branch**: `061-more-database-sources`

**Created**: 2026-11-08

**Status**: Draft — clarifications resolved 2026-11-08 (see *Decisions*)

**Input**: Owner, 2026-11-08: "add database connections: 1. SQLite 2. MySQL 3. SQL Server 4. Google
BigQuery 5. Google Sheets". Today Bizview reads PostgreSQL (incl. Supabase), REST and SOAP, read-only,
with credentials that never leave the installation. Small businesses run their ERP on MySQL or SQL
Server, keep operational data in Google Sheets, and consultants land data in BigQuery; each is a
customer Bizview cannot serve today. Five new **source kinds**, each behaving exactly like
PostgreSQL does for the user: connect, test, describe the structure, extract read-only, respect the
security profile, the connection limits (060) and the structure pack (048/052/057).

**Depends on**: 004 (connectors), 048 (BI-ready sources), 052 (structure scan and AI structure),
057 (starter zip carries the source's structure), 060 (connection limits and congestion handling).

## Context — what the code looks like today, and why this spec starts with a registry

The source kind is a string dispatched by `if kind == ...` in at least seven places:
`sources/connectors/__init__.py` (test), `sources/describe.py` (structure), `engine/extract.py`
(`_pg_connect`, psycopg directly, line ~251), `sources/bi_ready.py` (PostgreSQL only), `sources/
samples.py`, `sources/structure_ai.py`, and `cli/bizview_cli/structure.py` (twice). `schemas.KINDS`
holds the per-kind form fields. Adding five kinds by extending each `elif` chain multiplies the
places a kind can be forgotten (the 060 slot logic, the read-only session, the TLS policy, the
netguard address check). So this feature first turns the connector into one **protocol** with one
**registry**, moves PostgreSQL onto it with byte-identical behaviour, and only then adds kinds.
Every kind that lands after this one is a single module plus a registry entry.

SQLAlchemy 2 is already a dependency (constitution 2.5); the SQL kinds ride on it with their own
drivers. The two Google kinds are HTTPS APIs authenticated with a service account.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect an ERP on MySQL or SQL Server (Priority: P1) 🎯

A super user opens *Fuentes → Nueva fuente*, picks **MySQL / MariaDB** or **SQL Server**, fills host,
port, database, read-only user, password and TLS, presses *Probar conexión* and gets the same
verdict card as PostgreSQL (reachable · auth · database · read-only · TLS · time). *Ver estructura*
lists schemas, tables, columns and types. The starter zip (057) carries that structure; the AI
writes the integration; import, run and dashboard work with no other change.

**Independent Test**: a seeded MySQL 8 container and a SQL Server 2022 container in CI; one
integration per kind extracts a `ventas` table and renders the demo's *Ventas por marca*.

**Acceptance Scenarios**:

1. **Given** a MySQL source with a read-only user, **When** tested, **Then** the verdict shows
   `read_only: ok`; **When** an integration tries `INSERT`/`UPDATE`/`DDL`, **Then** the run fails
   before touching the origin with «la fuente es de solo lectura» (statement classification +
   session read-only where the engine supports it).
2. **Given** a SQL Server with `Encrypt=yes;TrustServerCertificate=no` and a private CA, **When** the
   CA PEM is pasted, **Then** the test passes; **When** the profile is `internet` and TLS is off,
   **Then** the save is refused as for PostgreSQL today.
3. **Given** the origin is out of connections (MySQL 1040 *Too many connections*, SQL Server 17809
   / 18456 state 1 with pool exhaustion), **Then** the run is amber «La fuente no admite más
   conexiones ahora» exactly as 060 does for SQLSTATE 53300.

---

### User Story 2 - A SQLite file next to the installation (Priority: P2)

A customer exports its desktop system to a `.sqlite`/`.db` file and drops it in a folder mounted
into the Bizview containers. The super user picks **SQLite**, chooses the file from the allowed
folder (no free path typing), tests, describes and extracts. The file is opened read-only (URI
`mode=ro`, `immutable` when the file is replaced wholesale) and never written.

**Acceptance Scenarios**:

1. **Given** `SOURCES_FILES_DIR=/data/sources` in `bizview.yml`, **Then** the SQLite form lists only
   files under that folder; a path outside it, a symlink escaping it, or the app's own database
   file is refused with a clear message.
2. **Given** the file is replaced by a newer export, **Then** the next run reads the new content;
   **Given** the file is missing at run time, **Then** the run fails with `not_found` and the
   dataset keeps its previous data (060 rule).
3. **Given** `SOURCES_FILES_DIR` is unset, **Then** the SQLite kind is not offered and
   `GET /api/sources/types` omits it (same pattern as `private_only`).

---

### User Story 3 - BigQuery for consultants and larger customers (Priority: P2)

A consultant lands a client's data in BigQuery. They pick **Google BigQuery**, paste a service
account JSON (secret), set project, location and the datasets Bizview may see, and a **maximum
bytes billed per query** so a bad query cannot run up a bill. Test, structure and extraction work
like any SQL source; the structure pack lists datasets as schemas.

**Acceptance Scenarios**:

1. **Given** a service account with `bigquery.dataViewer` + `bigquery.jobUser`, **Then** test shows
   `auth: ok`, `read_only: ok` (the role check is part of the verdict); a service account with
   `dataEditor` or higher shows a warning «la cuenta puede escribir; use una de solo lectura».
2. **Given** `max_bytes_billed = 1 GB`, **When** a query would scan more, **Then** BigQuery refuses
   it and the run reports the estimate from a **dry run** and the limit, not a generic failure.
3. **Given** the time limit of the run, **Then** the job is created with that timeout and
   cancelled if exceeded; costs appear in the run detail (bytes processed, slot ms).

---

### User Story 4 - A Google Sheet as a small source (Priority: P2)

A business keeps prices, budgets or a sales log in a Google Sheet. The super user picks **Google
Sheets**, pastes the spreadsheet URL and the service account JSON, shares the sheet with the service
account's e-mail (the form shows that address to copy), and tests. Each worksheet is a table; the
first row is the header; types are inferred from the first N rows and can be overridden in the
integration. `materialize: daily` is the recommended default.

**Acceptance Scenarios**:

1. **Given** a sheet not shared with the service account, **Then** test says exactly that and shows
   the e-mail to share with.
2. **Given** a worksheet with a header row and 2,000 rows, **Then** `describe` lists its columns
   with inferred types (string, integer, number, date, datetime, bool) and the row count; the
   starter zip carries them.
3. **Given** a cell that does not match the inferred type, **Then** extraction follows the
   integration's declared type (coerce or null, declared per column), never crashes.
4. **Given** Google's read quota is hit, **Then** the run is amber (060 pause semantics) with the
   retry-after; nothing is marked as a defect.

---

### User Story 5 - Nothing changes for PostgreSQL (Priority: P1)

Every existing PostgreSQL, Supabase, REST and SOAP source, integration and scheduled run behaves
exactly as before the refactor: same verdict cards, same structure output, same extraction SQL,
same 060 slots, same errors.

**Independent Test**: the existing test suite passes unchanged; the production demo project
re-imports with a byte-identical structure pack.

---

### Edge Cases

- Mixed case and quoting: MySQL table names are case-sensitive on Linux, SQL Server uses
  `[brackets]`, BigQuery uses backticks and `project.dataset.table`; the engine quotes identifiers
  per kind and the structure pack says which dialect the AI must write.
- Timezones: MySQL `time_zone`, SQL Server has none per session (`datetimeoffset` vs `datetime`),
  BigQuery is UTC, Sheets dates are serials in the sheet's locale; the existing `TimeZone`
  handling of `_pg_connect` becomes a per-kind hook with a documented behaviour.
- Pagination/streaming: large results are fetched in server-side chunks (MySQL `SSCursor`,
  SQL Server `fast_executemany` off / `arraysize`, BigQuery `list_rows` pages, Sheets ranges), never
  whole tables in memory.
- Statement timeout: MySQL `MAX_EXECUTION_TIME`, SQL Server `SET LOCK_TIMEOUT` + query timeout,
  BigQuery job timeout, Sheets request timeout.
- Personal-data columns (projects/personal.py) are excluded by default for every kind.
- Driver absent in the image → the kind is listed as unavailable with the reason, never a 500.

## Requirements *(mandatory)*

### Connector protocol and registry
- **FR-001**: A `Connector` protocol in `sources/connectors/base.py` with: `kind`, `label`,
  `fields` (the `schemas.F` tuple), `capabilities` (sql | tables | files | api), `test()`,
  `describe()`, `connect()`/`extract()` hooks used by `engine/extract.py`, `classify_error()`,
  `is_busy()` (060), `quote_identifier()`, `dialect_notes()` for the structure pack, and
  `availability()` (driver present, config present).
- **FR-002**: A registry (`sources/connectors/registry.py`) is the only place a kind is listed.
  `schemas.KINDS`, `test_source`, `describe`, `extract`, `bi_ready`, `samples`, `structure_ai`, the CLI
  `structure` module and `GET /api/sources/types` all read it. Grep for `kind == "postgresql"`
  after the refactor returns only the PostgreSQL module itself.
- **FR-003**: PostgreSQL, Supabase, REST and SOAP move onto the protocol first, in their own PR,
  with the current test suite green and no behaviour change (US5). New kinds follow in separate PRs.

### New kinds
- **FR-004 SQLite**: driver `sqlite3` (stdlib). Fields: file (picker over `SOURCES_FILES_DIR`),
  timeout, `max_connections` default 1. Opened with `file:...?mode=ro` (and `immutable=1` when the
  file is replaced atomically, per a checkbox). Path canonicalised and checked to stay inside the
  folder; the app's own files are denied. Structure from `sqlite_master` + `PRAGMA table_info`.
- **FR-005 MySQL / MariaDB**: driver `PyMySQL` (pure Python; `mysqlclient` optional). Fields: host,
  port 3306, database, username, password, TLS mode (require / verify-full / prefer / disable with
  `private_only` as PG), CA PEM, timeout, `max_connections`. Session: `SET SESSION TRANSACTION READ
  ONLY`, `SET SESSION MAX_EXECUTION_TIME`, `time_zone`. Address pinned with `resolve_checked`.
  Structure from `information_schema`.
- **FR-006 SQL Server**: driver `pymssql` (no ODBC manager in the image) or `pyodbc` + msodbcsql18 if
  the plan proves pymssql insufficient (document the choice). Fields: host, port 1433, database,
  username, password, auth (sql | windows-not-supported note), encrypt (yes / strict / optional with
  `private_only`), CA PEM, `TrustServerCertificate` never exposed, timeout, `max_connections`. Session:
  `SET TRANSACTION ISOLATION LEVEL READ COMMITTED`, query timeout; read-only enforced by statement
  classification (SQL Server has no session read-only) plus a documented recommendation of a
  `db_datareader`-only login, checked in the test verdict (`IS_MEMBER('db_datawriter')`).
  Structure from `INFORMATION_SCHEMA` + `sys.schemas`.
- **FR-007 BigQuery**: `google-cloud-bigquery` (and `db-dtypes`), no SQLAlchemy dialect needed.
  Fields: project, location, service account JSON (secret, validated as JSON with `client_email`),
  datasets allow-list, `max_bytes_billed` (default 1 GB), timeout, `max_connections` (concurrent
  jobs). Every query is **dry-run first**; the run detail shows bytes and estimated cost. Structure
  from `INFORMATION_SCHEMA.COLUMNS` of the allowed datasets.
- **FR-008 Google Sheets**: Google Sheets API v4 via `google-api-python-client` (or `gspread`),
  service account JSON (secret), spreadsheet URL or id, header row index (default 1), sample rows
  for type inference (default 200), timeout. One worksheet = one table; structure = header +
  inferred types + row count; extraction reads `values.get` in ranges of ≤ 10,000 rows. The form
  shows the service account e-mail to share the sheet with.
- **FR-009**: Each new kind has its own `_classify` with the engine's real messages (auth, not
  found, timeout, tls, unreachable, **busy** for 060) and a test that feeds the raw errors.

### Security and read-only (constitution 3)
- **FR-010**: Every network kind resolves through `netguard.resolve_checked` and obeys
  `sources_allow_private_networks` and the security profile (`internet` forbids unencrypted).
  Google kinds are HTTPS-only by construction.
- **FR-011**: Read-only is enforced in layers: session flag where the engine has one (PG, MySQL,
  SQLite `mode=ro`), statement classification for every kind (reject anything but
  `SELECT`/`WITH`/`SHOW`/`DESCRIBE`/`EXPLAIN`), and a verdict check of the credential's write
  privileges at *Probar conexión*.
- **FR-012**: Secrets (passwords, service account JSON) are stored encrypted like today's
  passwords, write-only in the API, never in the structure pack, never in logs; the structure pack
  carries no host, project id or spreadsheet id beyond a label.

### Engine, limits, structure pack
- **FR-013**: 060 slots apply per source for every kind (`max_connections`), including BigQuery
  concurrent jobs and Sheets concurrent requests.
- **FR-014**: The structure pack (057) and `bizview describe` print the kind, the dialect notes
  (quoting, date functions, `LIMIT` vs `TOP`, backticks), the schemas/datasets/worksheets, and the
  same column shape for every kind, so the AI prompt needs no per-kind branching beyond the notes.
- **FR-015**: `bizview validate` checks an integration's SQL against the source's dialect at least
  for forbidden statements and identifier quoting; the CLI and the server share the check.
- **FR-016**: Materialisation (`materialize: daily`) is recommended in the form help for Sheets and
  BigQuery and defaults on for Sheets.

### Packaging and docs
- **FR-017**: Drivers are added to `pyproject.toml` as optional extras per kind
  (`bizview[mysql]`, `[mssql]`, `[bigquery]`, `[sheets]`); the published image installs all; a
  self-built image without an extra lists the kind as unavailable (edge case).
- **FR-018**: `docs/INSTALL.md` gains one section per kind: minimum privileges, how to create a
  read-only user (MySQL `GRANT SELECT`, SQL Server `db_datareader`, BigQuery roles, Sheets sharing),
  TLS, and `SOURCES_FILES_DIR` for SQLite. i18n ES/EN for forms and help (022).
- **FR-019**: Demo seed: one small SQLite file and one public Google Sheet (owned by Global DV,
  generic data) so the demo can show two kinds beyond PostgreSQL without a server.

## Success Criteria *(mandatory)*

- **SC-001**: After FR-003, the whole existing suite is green and the demo project's structure pack
  is byte-identical to the one produced before the refactor.
- **SC-002**: Five new kinds appear in *Nueva fuente* (SQLite only when configured), each with test,
  structure, starter zip, import, run and dashboard proven in CI against a container or a sandbox
  account.
- **SC-003**: A write attempt is refused for every kind at three layers (statement, session where
  available, credential verdict), with a test per kind.
- **SC-004**: Congestion and quota errors are amber pauses (060) for every kind, with a test that
  feeds the real error text.
- **SC-005**: `grep -rn 'kind == "'` outside the connector modules and the registry returns nothing.
- **SC-006**: A BigQuery query over `max_bytes_billed` never runs; the dry-run estimate is shown.
- **SC-007**: A SQLite path outside `SOURCES_FILES_DIR` is impossible to save (unit test with `..`,
  absolute path, symlink).
- **SC-008**: Docs and forms in ES and EN; no hard-coded strings (lint).

## Questions for `/speckit-clarify`

**Q1 — Oracle as a sixth kind (owner asked).** Add Oracle in this feature?
*Recommended:* put it in a follow-up (`062-oracle-source`) once the registry exists; it is then one
module. Driver `python-oracledb` in **thin mode** is pure Python (no Instant Client, Apache-2.0
licence), supports TLS and wallets, and `SET TRANSACTION READ ONLY` exists; structure from
`ALL_TABLES`/`ALL_TAB_COLUMNS`. The only real costs are testing (the free `gvenzl/oracle-free`
container works in CI) and dialect notes (`FETCH FIRST n ROWS ONLY`, `DUAL`, date literals).

**Q2 — SQL Server driver.** `pymssql` (no ODBC, simpler image) or `pyodbc` + Microsoft ODBC 18
(official, Azure AD auth)?
*Recommended:* `pymssql` first; switch to `pyodbc` only if a customer needs Azure AD or `strict`
encryption that pymssql's FreeTDS lacks. Record the decision in `research.md`.

**Q3 — Google auth.** Service account only, or also OAuth user consent?
*Recommended:* service account only (headless worker, no refresh-token lifecycle). OAuth as a
follow-up if customers can't create service accounts.

**Q4 — Sheets type inference.** Infer and freeze types at import, or re-infer every run?
*Recommended:* infer at describe time, declare in the integration, enforce at run; re-infer only on
re-import (055 revision).

**Q5 — SQLite file picker vs upload.** Pick from a mounted folder or upload through the browser?
*Recommended:* mounted folder (no upload path, no size limits, replaceable by the customer's export
job). Upload as a follow-up with the 049 allowances.

## Assumptions

- The published Docker image can grow by the drivers (PyMySQL, pymssql, google-cloud-bigquery,
  google-api-python-client are all pip-installable without system packages).
- CI can run MySQL and SQL Server containers; BigQuery and Sheets tests use a Global DV sandbox
  project and a service account stored as a CI secret, skipped when absent.
- Existing customers do not need to re-create PostgreSQL sources; the registry refactor is a
  code-only change with no migration.

## Decisions (clarifications resolved without asking)

The owner's brief left five questions open with a recommendation each; the recommendations are taken
as the decision, and the reasoning is in [research.md](./research.md) (R1–R5):

| # | Question | Decision |
|---|---|---|
| Q1 | Oracle as a sixth kind | **Follow-up `062-oracle-source`**, after the registry exists. It is then one module (`python-oracledb` thin mode). Not in this feature. |
| Q2 | SQL Server driver | **`pymssql`** first: no ODBC manager, no system package, works in the published image. `pyodbc` + msodbcsql18 only if a customer needs Azure AD or `strict` encryption. |
| Q3 | Google auth | **Service account only.** Headless worker, no refresh-token lifecycle. A service account JSON is one more secret in the same encrypted store. |
| Q4 | Sheets type inference | **Infer at describe time** (sample N rows), **declare** the types in the integration, **enforce** them at every run; re-infer only when the project is imported again (055). |
| Q5 | SQLite file picker vs upload | **Mounted folder** (`SOURCES_FILES_DIR`), picked from a list, canonicalised and proven to stay inside it. No upload path in this feature. |

Consequences carried into the requirements below: SQLite is offered only when `SOURCES_FILES_DIR` is
set; MySQL/SQL Server/BigQuery/Sheets are offered always but report themselves *unavailable* with the
reason when their driver is not installed (FR-017), never a 500.
