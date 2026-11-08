# Research — More database sources (061)

The decisions the spec asked for in `/speckit-clarify` (recorded in [spec.md](./spec.md), section
*Decisions*) plus the ones the implementation needed. Every one of them is a choice that is
expensive to reverse, so each says what it costs and what would make us change it.

## R1 — Oracle is a follow-up, not a sixth kind here

The owner asked for Oracle in the same breath. It is **out of scope for 061** and becomes
`062-oracle-source` once this registry exists, at which point it is one module plus one `Spec` row:
`python-oracledb` in thin mode is pure Python (no Instant Client), Apache-2.0, speaks TLS and
wallets, has `SET TRANSACTION READ ONLY`, and its catalogue is `ALL_TABLES`/`ALL_TAB_COLUMNS`. The
real cost is testing (the free `gvenzl/oracle-free` image) and dialect notes (`FETCH FIRST n ROWS
ONLY`, `DUAL`), not design. Doing it now would make this PR twice as large for one more `elif`
that no longer exists.

## R2 — SQL Server through `pymssql`, not `pyodbc`

`pymssql` speaks TDS from Cython wheels, so the published image needs **no ODBC manager and no
Microsoft package** — one less system dependency in a container that must stay rebuildable on
`python:3.12-slim`. What it does not give us: Azure AD authentication, and FreeTDS's `strict`
encryption flavour. Neither is needed by the customers this feature serves (a SQL login with
`db_datareader`), and the plan records the switch to `pyodbc` + `msodbcsql18` as the answer the day
a customer needs Azure AD or `TrustServerCertificate=no` with forced encryption. `encrypt` is
therefore exposed as `yes | optional` and `TrustServerCertificate` is not exposed at all.

## R3 — Google authentication: service account only

A headless worker cannot complete a user consent flow, and a refresh token is another secret with
a lifecycle (expiry, revocation, re-consent e-mails) that an installation would have to babysit.
Both Google kinds take a service-account JSON, stored encrypted like a password and write-only
through the API. Sheets needs one extra human step — sharing the sheet with the account's
`client_email` — so the form shows that address and the failure message repeats it: "share it with
this address" is the fix, and it must be in the error, not in the docs.

## R4 — Sheets types are inferred at describe time and enforced at run time

Re-inferring every run would let a stray cell silently change a column's type between two runs of
the same integration — a report that works on Monday and breaks on Tuesday. So: infer from the
first `sample_rows` (default 200) when the structure is read, write the types into the structure
pack, the AI declares them in the integration, and the run enforces them (the staging table parses
the text it is given). A cell that does not match becomes a null or a contract error — auditable —
never a silent type change. Re-inference happens on re-import (055 revisions), which is where a
schema change belongs.

## R5 — SQLite is a file in a mounted folder, never an upload

An upload would need a size allowance (049), a place to keep the file, a way to replace it and a way
to delete it, and it would put customer data inside the product's own volume in a shape nobody can
see. A mounted folder (`SOURCES_FILES_DIR`) keeps the export job on the customer's side, makes the
file replaceable by `rsync`, and lets the product stay ignorant of its size. The picker only offers
what is inside that folder, and `sqlite.resolve()` re-checks the path when the source is saved: `..`,
an absolute path elsewhere, a symlink resolving out of the folder and the product's own database
file are all refused (SC-007). Upload can later ride 049's allowances without changing this module.

## R6 — The protocol is a `Spec` row plus a module, not an ABC

The nine dispatch points need three different things from a kind: its form fields (the API), its
behaviour (test/describe/extract), and facts about it (`is_sql`, `holds_session`, `has_native_copy`).
An abstract base class would force the four existing connectors to inherit, which changes their
module-level imports and their tests for no benefit. So:

- `registry.Spec` declares `kind`, `module`, `capabilities`, `fields` and `drivers` — the one list.
- connector modules stay plain modules with `kind`, `label` and the functions the protocol names
  (`test`, `describe`, `session`, `rows`, `dialect_notes`, `available`, `is_busy`,
  `request_rows` where it applies).
- a driver is imported **inside** the function that needs it, so a missing extra never breaks the
  import of the app, and `registry.available()` can say why a kind is not offered.

`fields` is a closure that imports `app.sources.schemas` lazily: `schemas.KINDS` is built from the
registry and the registry names the fields, which is a cycle if both are module-level.

## R7 — Non-PostgreSQL SQL rides the runner's existing row path

PostgreSQL keeps `COPY (query) TO STDOUT` (feature 008) and its warm origin session (060). Every
other SQL kind streams DB-API batches through `connectors/sql.rows()` into `_text_frame()` and the
staging table's `COPY FROM STDIN`, which the runner already has for the PostgreSQL fallback. That
means: one new function in `extract.py` (`sql_rows`, plus `sql_all` for the reconcile check), one new
branch in `runner._extract`, and **no** new staging, contract or transform code. The transform
(`transform:` block) path takes the same rows, so a MySQL integration may transform exactly like a
PostgreSQL one.

## R8 — Congestion is per kind, and it is 060's rule

060 decided that a full origin is an amber pause, keyed on SQLSTATE 53300. Each new kind brings its
own words for the same situation — MySQL 1040/1203/1129, SQL Server 17809, Google's quota errors,
SQLite's `database is locked` — so every connector implements `is_busy()` (usually `classify() ==
"busy"`) and `extract.sql_rows()` turns that into `SourceBusy`, which the runner already maps to
`skipped_busy`. No new state, no new UI. `2002`/`2003` ("cannot connect") stay **unreachable**: a
server that is down is not a busy one.

## R9 — Two Google kinds, two shapes

BigQuery is SQL (`sql=True`, `session=False`, no native COPY): it answers a query, so it rides the
SQL row path with a DB-API-shaped adapter over `QueryJob`. Google Sheets is not: one worksheet is one
table, the call is `values.get` in ranges of ≤10 000 rows, and its integration carries a `request`
(`worksheet`, optional `header_row`) exactly like REST. That is why `registry.request_rows(kind)`
replaces the `{"rest": …}` dictionary the runner used to keep, and why Sheets has
`tables=True, api=True`.

## R10 — `SOURCES_FILES_DIR` unset means the kind does not exist

The spec asks for SQLite to be absent, not broken, on an installation with no folder (the same shape
as `private_only` removing an option). `registry.available()` returns an i18n key, and
`schemas.types_for()` **omits** a kind whose reason is `sources.unavailable.folder` while it keeps a
kind whose reason is a missing driver (that one is an installation defect worth showing, with the
reason, instead of a 500).

## R11 — `CONTENIDO.md`/`CONTENTS.md` stays 057's business

The starter zip, its contents and the two explanatory documents were built by 057; this feature only
adds one thing to the pack: `sources/<name>/structure.{md,json}` when the super user picks a source
in the download dialog — which 048/052 already generate for PostgreSQL. Nothing in the pack changes
shape, so the committed template is regenerated only if a kind's dialect notes change it.
