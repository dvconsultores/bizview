# Tasks — More database sources (061)

`[X]` means done and verified by the suite named in the task. The order is the order it happened:
the protocol first (so the four existing kinds stop being five `elif`s), then one kind at a time,
then the wiring, the docs and the gates.

## Phase 1 — The protocol and the registry

- [X] T001 `app/sources/connectors/registry.py`: `Capabilities`, `Spec`, `SPECS`, `BY_KIND`,
      `KINDS`, lazy `module()`, `capabilities/is_sql/holds_session/has_native_copy`,
      `missing_drivers`, `available(kind, app)`, `test_source`, `describe`, `request_rows`.
      *Verified by* `tests/test_source_kinds.py::test_every_kind_is_declared_once_and_has_a_module`,
      `::test_capabilities_split_queries_from_requests`.
- [X] T002 Every connector module declares `kind`/`label` and the functions the protocol names;
      `postgresql`, `rest`, `soap` and `supabase` gain a `describe()` shim and `dialect_notes()`
      that delegate to the readers they already had. *Verified by* the module loop in T001's test.
- [X] T003 `connectors/__init__.test_source` delegates to the registry (no `elif` chain).
- [X] T004 `sources/describe.describe` delegates to `registry.describe`, keeping the
      `ExtractError` mapping for an unknown kind and for `httpx` errors.
- [X] T005 `app/engine/runner.py`: `_sql_kind`, `_native_copy`, `_request_rows` replace the three
      `source.kind == "postgresql"` comparisons and the `{"rest": …}` request map; the plain and the
      transformed extraction paths both branch on the registry. *Verified by* `tests/test_runner.py`,
      `tests/test_bulk_extract.py`.
- [X] T006 `app/engine/extract.py`: `sql_rows()` and `sql_all()` stream any SQL kind through its
      connector, refuse a non-read before it reaches the origin, and turn a kind's `is_busy()` into
      the 060 `SourceBusy`. *Verified by* `tests/test_source_busy.py`, T032-T035 below.
- [X] T007 `sources/bi_ready.py`, `sources/structure_scan.py`, `sources/structure_ai.py`,
      `sources/samples.py` and `engine/direct.py` ask the registry (`POSTGRESQL`, `is_sql`,
      `capabilities(kind).tables`) instead of comparing a kind to a string. *Verified by*
      `tests/test_bi_ready_declaration.py`, `tests/test_source_structure_ai.py`,
      `tests/test_direct_sources.py`.
- [X] T008 `cli/bizview_cli/structure.py`: one SQL renderer for every dialect (`SQL_KINDS`) that
      prints the dialect notes; the personal-data heuristic applies to all of them.

## Phase 2 — SQLite

- [X] T009 `connectors/sqlite.py`: `folder`, `available` (unset folder → the kind does not exist),
      `resolve` (inside the folder, real file, extension, 4 GB), `list_files`, `_connect` with
      `mode=ro` + `PRAGMA query_only`, `classify`, `is_busy`, `test`, `describe` from
      `sqlite_master`/`PRAGMA table_info`, `session`, `rows`, `dialect_notes`.
      *Verified by* `tests/test_source_kinds.py::test_sqlite_*` (7 tests, one real file).
- [X] T010 `config.sources_files_dir`; `schemas._check_sqlite_path` refuses an escaping path at save
      time with the reason. *Verified by* `::test_sqlite_path_outside_the_folder_cannot_be_saved`.
- [X] T011 `GET /api/sources/files` (names and sizes, never a path) and the `files` field type in
      the form. *Verified by* `tests/test_sources_api.py` and the form's typecheck.

## Phase 3 — MySQL / MariaDB

- [X] T012 `connectors/mysql.py`: `connect_kwargs` (netguard `resolve_checked`, TLS modes, the
      read-only `init_command`, `program_name`), `_connect` + `MAX_EXECUTION_TIME`, `classify`
      (1040/1203/1129 busy, 1045 auth, 1049 not found, 2002/2003 unreachable), `is_busy`,
      `_can_write` from `SHOW GRANTS`, `test`, `describe` via `structure_sql`, `session`, `rows`.
      *Verified by* `::test_mysql_classifies_the_engine_s_own_messages`, `::test_mysql_is_busy_*`.
- [X] T013 `connectors/sql.py`: the shared DB-API base — `read_only_query` (a read must begin with
      `select|with|show|describe|explain|pragma`, and no writing statement word may follow), `quote`,
      `read_only_prefix`, `session`, `rows` (batched, never the whole result), `row_count`,
      `test_connection`. *Verified by* `::test_the_read_only_rule_accepts_reads_only`,
      `::test_quoting_follows_each_dialect`.
- [X] T014 `connectors/structure_sql.py`: `information_schema` → the PostgreSQL structure shape with
      the kind and its dialect notes. *Verified by* the describe tests of every SQL kind.

## Phase 4 — SQL Server

- [X] T015 `connectors/mssql.py`: `pymssql` (research R2), `encrypt` per the profile, `classify`
      (17809 busy, 18456 auth, 4060 not found), `_write_verdict` (`IS_MEMBER('db_datawriter')`,
      `IS_SRVROLEMEMBER('sysadmin')`, `SYS.DM_EXEC_CONNECTIONS` for the real encryption state),
      `describe` from `INFORMATION_SCHEMA`, `dialect_notes` (`[brackets]`, `TOP`).
      *Verified by* `::test_mssql_classifies_the_engine_s_own_messages`.

## Phase 5 — BigQuery

- [X] T016 `connectors/bigquery.py`: `service_account_info`/`credentials` (the address is readable
      without the SDK), `datasets`, `max_bytes`, `classify`/`is_busy`, `test` (dry run + role list),
      `describe` from `INFORMATION_SCHEMA` of the allowed datasets, a DB-API-shaped cursor whose
      `execute` is **dry run → ceiling check → job with timeout**, `dialect_notes` (backticks).
      *Verified by* `::test_bigquery_refuses_a_query_over_the_ceiling_before_running_it`.

## Phase 6 — Google Sheets

- [X] T017 `connectors/sheets.py`: `spreadsheet_id` from a URL, `_infer` (integer → number → date →
      datetime → bool → string), `test` that names the address to share the sheet with, `describe`
      (worksheet = table, header row, inferred types, row count), `request_rows` (`values.get` in
      chunks, header mapped to the declared columns), `dialect_notes`.
      *Verified by* `::test_sheets_*` (4 tests).

## Phase 7 — Storage, forms and wiring

- [X] T018 `alembic/versions/0056_more_source_kinds.py` widens `ck_data_source_kind` to the nine
      values and refuses to downgrade while a new kind exists; `models.SOURCE_KINDS` mirrors it.
      *Verified by* the suite's migrations run.
- [X] T019 `schemas.py`: the five field tuples, `FIELDS`, `KINDS`, per-kind default ports in
      `_check_destinations`, and `types_for` gaining `available`/`reason` (with SQLite omitted when
      no folder is configured). *Verified by* `::test_a_kind_without_a_folder_is_not_offered`,
      `::test_a_kind_without_its_driver_is_listed_with_the_reason`, `::test_a_new_kind_is_accepted_*`.
- [X] T020 `pyproject.toml` extras (`mysql`, `mssql`, `bigquery`, `sheets`, `sources`), `uv lock`,
      and the image installing `--extra sources`.
- [X] T021 i18n: `sources.kind.*`, `sources.unavailable.*`, `sources.sqlite.*`, `sources.mysql.*`,
      `sources.mssql.*`, `sources.bigquery.*`, `sources.sheets.*`, `sources.test.unavailable`,
      `sources.test.not_read_only`, `run.sql_needs_sql`, `run.check.reconcile_needs_sql`,
      `run.read_only_source` — in ES and EN. *Verified by* `tests/test_i18n_catalogue.py`.
- [X] T022 Frontend: `SourceKind` extended, `FieldDef.type` gains `files`, `SourceFile`,
      `available`/`reason`, the file picker, and a kind this installation cannot use shown disabled
      with its reason. *Verified by* `tsc` and `tests/unit/source-*.test.tsx`.

## Phase 8 — Docs, help and the record

- [X] T023 `docs/INSTALL.md` + `docs/es/INSTALL.md`: one section per kind (read-only user, TLS,
      `SOURCES_FILES_DIR`). *Verified by* `scripts/check_docs_parity.py`.
- [X] T024 Guide topic `otros-tipos-de-fuente` in ES and EN, linked from `fuentes` and
      `estructura-de-una-fuente`. *Verified by* `tests/test_guide.py`, `tests/test_guide_api.py`.
- [X] T025 CHANGELOG under *Unreleased*.
- [X] T026 This feature's `research.md`, `data-model.md`, `contracts/api.md`, `quickstart.md`,
      `tasks.md`, `checklists/requirements.md`.

## Phase 9 — Verification

- [X] T027 `tests/test_source_kinds.py`: 46 tests over the registry, the five kinds, the read-only
      rule, the ceilings and the form.
- [X] T028 `tests/test_connectors.py`, `tests/test_sources_api.py`, `tests/test_source_structure.py`,
      `tests/test_starter_api.py` (14), `tests/test_guide*.py`, the frontend's 782 unit tests and
      `scripts/gates/all.sh`: green (SC-001 for the four existing kinds).
      Five tests in `tests/test_bi_ready_declaration.py`, two in `tests/test_source_structure_ai.py`
      and one in `tests/test_bulk_extract.py` fail **on `HEAD` too** — their fakes for
      `describe()` do not accept the `date_ranges`/`name` arguments the dispatcher already passed
      before this feature (proven by stashing the work and running them). Left untouched: they are
      not this feature's defect.
- [ ] T029 Live verification against a real MySQL 8, SQL Server 2022, a BigQuery sandbox project and
      a shared Google Sheet — the quickstart, not CI. **Not run here**: no container runtime or
      sandbox credentials in this environment.
