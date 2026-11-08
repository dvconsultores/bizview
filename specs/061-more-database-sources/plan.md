# Implementation Plan: More database sources

**Branch**: `061-more-database-sources` | **Date**: 2026-11-08 | **Spec**: [spec.md](./spec.md)

## Summary

Turn the origin connector into **one protocol with one registry**, move the four kinds that exist
today onto it with no behaviour change, and then add five kinds — SQLite, MySQL/MariaDB, SQL Server,
BigQuery and Google Sheets — each of which connects, tests, describes, extracts read-only and reports
congestion exactly as PostgreSQL does (004/048/052/057/060).

The refactor comes first because the kind is a string dispatched by `if kind == …` in nine places:
`sources/connectors/__init__.py`, `sources/describe.py`, `sources/schemas.py` (twice),
`sources/bi_ready.py`, `sources/samples.py`, `sources/structure_ai.py`, `sources/structure_scan.py`
(twice), `engine/runner.py`, `engine/direct.py`, plus the CLI's `structure.py`. Every new kind added
to each chain is a place the next one can be forgotten — the 060 slot logic, the read-only session,
the TLS policy and the netguard check all live in those branches.

## Technical Context

**Language/Version**: Python 3.13 (backend `backend/.venv`), TypeScript/React (the form renders the
field list the API serves, so a new kind needs no page).

**Primary Dependencies**: psycopg 3 (PostgreSQL), httpx (REST/SOAP/Supabase, unchanged);
new optional extras — `PyMySQL` (MySQL), `pymssql` (SQL Server), `google-cloud-bigquery` and
`google-api-python-client` + `google-auth` (the two Google kinds), `sqlite3` (stdlib, SQLite).

**Storage**: `data_source.settings`/`secrets` as today; no migration — a kind is a value of an
existing CHECK, widened by one revision per batch of kinds (`0056_more_source_kinds`).

**Testing**: `pytest` for classification, quoting, fields, availability, path safety, structure
mapping against fakes and a real SQLite file; the existing PostgreSQL suites must stay byte-identical
(SC-001). Live MySQL/SQL Server/BigQuery/Sheets verification is a quickstart with containers and a
sandbox account — CI cannot host those in this environment.

**Constraints**: constitution II and III (read-only origin, credentials encrypted, never written),
FR-11 of the brief (read-only enforced in layers), no new system packages in the image, every label
in ES and EN.

## Constitution Check

| Principle | How it is satisfied |
|---|---|
| II. Backend as ETL | Unchanged: the new kinds feed the same runner and the same staging tables. The 060 ceiling is applied by the registry too (`max_connections` for every kind). |
| III. Source of truth external | Read-only in layers: session flag where the engine has one (PostgreSQL, MySQL, SQLite `mode=ro`), statement classification for every kind, and the credential verdict at *Probar conexión*. Nothing is ever written, created or migrated. |
| IV. Folder separation | New modules live beside the existing ones in `backend/app/sources/connectors/`; the CLI keeps its own structure module and reads the same registry through a thin adapter. |
| V. Fixed stack | The only additions are drivers behind optional extras; `psycopg`, `sqlglot` and the netguard are reused. |
| IX / 004 security | `resolve_checked`, the profile's TLS rule and the encrypted secret store are called from the protocol, not duplicated per kind. |
| Constraints | No migration for data; one CHECK widening for the kind values. Credentials stay write-only; the structure pack carries no host, project or spreadsheet id. |

**Gate: PASS.**

## Project Structure

```text
backend/app/sources/
├── connectors/
│   ├── base.py            # + Connector protocol, Capabilities, availability, classify hooks
│   ├── registry.py        # NEW: the only place a kind is listed
│   ├── postgresql.py      # migrated onto the protocol (no behaviour change)
│   ├── supabase.py        # migrated (HTTP kind)
│   ├── rest.py            # migrated (HTTP kind)
│   ├── soap.py            # migrated (HTTP kind)
│   ├── sql.py             # NEW: DB-API base — SQLite, MySQL and SQL Server ride on it
│   ├── sqlite.py          # NEW
│   ├── mysql.py           # NEW
│   ├── mssql.py           # NEW
│   ├── bigquery.py        # NEW
│   └── sheets.py          # NEW
├── schemas.py             # KINDS built from the registry; SQLITE_FILES field type
├── describe.py            # dispatch through the registry
├── bi_ready.py            # "is a SQL origin" from the registry, not `kind == "postgresql"`
└── structure_scan.py      # idem
backend/app/engine/
├── extract.py             # SQL kinds stream through one DB-API reader; PostgreSQL keeps COPY
└── runner.py              # "does this kind hold a session?" from the registry
backend/tests/test_sources_registry.py, test_sqlite_source.py, test_mysql_source.py,
              test_mssql_source.py, test_bigquery_source.py, test_sheets_source.py,
              test_source_kinds_fields.py
docs/INSTALL.md + docs/es/INSTALL.md   # one section per kind
```

## Phase 0 — research

See [research.md](./research.md): R1 Oracle out of scope, R2 pymssql, R3 service account, R4 infer at
describe, R5 mounted folder, R6 the protocol's shape, R7 how extraction rides the existing runner
paths, R8 availability instead of a 500.

## Phase 1 — design

- [data-model.md](./data-model.md): the kind values, the field lists per kind, the secret shapes, the
  migration.
- [contracts/api.md](./contracts/api.md): `GET /api/sources/types`, `POST /api/sources/{id}/test`,
  `GET /api/sources/{id}/structure` and the availability field.
- [quickstart.md](./quickstart.md): what a reviewer runs, including what cannot be run here.

## Post-design Constitution Check

Unchanged: PASS. Two notes a reviewer will ask for:

- The SQLite file is inside the installation's own volume, but it is still an origin: it is opened
  read-only, never migrated, and a path outside `SOURCES_FILES_DIR` (or a symlink escaping it, or the
  product's own database file) cannot be saved.
- BigQuery bills by bytes scanned: a query is **dry-run first** and refused before it runs when the
  estimate exceeds the source's `max_bytes_billed`, so a mistake costs nothing.
