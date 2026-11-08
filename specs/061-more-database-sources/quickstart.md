# Quickstart — More database sources (061)

What a reviewer runs, in order, and what cannot be run in this environment. Everything in the first
part needs no container and no cloud account: the five kinds are exercised at their driver boundary.

## 1. The suite

```bash
cd backend
.venv/bin/python -m pytest tests/test_source_kinds.py -q          # 46 tests, ~3 min with the schema
.venv/bin/python -m ruff check app tests/test_source_kinds.py
```

The tests that prove the spec's own criteria:

| Criterion | Test |
|---|---|
| SC-003, a write is refused | `test_the_read_only_rule_accepts_reads_only`, `test_sqlite_reads_and_refuses_a_write` |
| SC-004, congestion is an amber pause | `test_mysql_classifies_the_engine_s_own_messages`, `test_mssql_classifies_*`, `test_bigquery_classifies_quota_as_a_pause` |
| SC-005, no `kind == "…"` left | `grep -rn 'kind == "' backend/app --include=*.py` → only connector modules |
| SC-006, over the ceiling never runs | `test_bigquery_refuses_a_query_over_the_ceiling_before_running_it` |
| SC-007, a path outside the folder is impossible | `test_sqlite_refuses_what_is_not_a_file_in_the_folder`, `test_sqlite_refuses_a_symlink_that_escapes_the_folder` |
| SC-008, both languages | `tests/test_i18n_catalogue.py` (every key in ES and EN) |
| SC-001, nothing changed for PostgreSQL | `tests/test_connectors.py`, `tests/test_source_structure.py`, `tests/test_bulk_extract.py`, `tests/test_runner.py` |

## 2. SQLite end to end, with a real file

```bash
mkdir -p /tmp/bizview-sources
sqlite3 /tmp/bizview-sources/erp.db <<'SQL'
create table ventas (id integer primary key, marca text, total real);
insert into ventas (marca, total) values ('ACME', 10.5), ('ACME', 4.5);
SQL
SOURCES_FILES_DIR=/tmp/bizview-sources make dev        # or run the backend however you usually do
```

Then, in the app: **Administración → Fuentes de datos → Nueva fuente → SQLite (archivo)**, pick
`erp.db`, **Probar conexión** (green, one table), **Guardar**, **Estructura** (two columns and a
row count), **Descargar paquete inicial** with this source selected → the zip carries
`sources/<name>/structure.md`. Hand the folder to any AI, import what it returns.

## 3. MySQL and SQL Server, with containers

```bash
docker run --rm -d --name mysql-061 -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=erp mysql:8
docker exec -i mysql-061 mysql -uroot -proot -e "
  CREATE TABLE erp.ventas (id int primary key, marca varchar(40), total decimal(12,2));
  INSERT INTO erp.ventas VALUES (1,'ACME',10.50),(2,'ACME',4.50);
  CREATE USER 'bizview'@'%' IDENTIFIED BY 'secreta';
  GRANT SELECT ON erp.* TO 'bizview'@'%';"

docker run --rm -d --name mssql-061 -p 1433:1433 \
  -e ACCEPT_EULA=Y -e MSSQL_SA_PASSWORD='Str0ng!Passw0rd' mcr.microsoft.com/mssql/server:2022-latest
docker exec -i mssql-061 /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Str0ng!Passw0rd' -C <<'SQL'
create database erp;
use erp; create table ventas (id int primary key, marca nvarchar(40), total decimal(12,2));
insert into ventas values (1,'ACME',10.50),(2,'ACME',4.50);
create login bizview with password = 'Str0ng!Passw0rd2';
create user bizview for login bizview; alter role db_datareader add member bizview;
SQL
```

Register each one with **Nueva fuente** and check, in order: the verdict card is green with
`read_only: ok`; **Ver estructura** lists `ventas` with three columns; a query with an `insert`
fails **before reaching the origin** («la fuente es de solo lectura»); and stopping the container and
running the test again gives `unreachable`, not a 500.

## 4. BigQuery and Sheets (sandbox account)

1. Create a service account with **BigQuery Data Viewer** + **BigQuery Job User**; download its JSON.
2. **Nueva fuente → Google BigQuery**: project, location, the datasets allowed, the byte ceiling
   (drop it to `10 MB`), paste the JSON, **Probar conexión**. Then run a query that scans more than
   the ceiling from an integration: it must be refused with the estimate, not executed.
3. **Nueva fuente → Google Sheets**: paste a sheet's link, the same JSON, and share the sheet with
   the `client_email` the form shows. **Probar conexión** must name that address while the sheet is
   not shared. After sharing: **Ver estructura** lists each worksheet with its header and inferred
   types.

## What cannot be run here

- No container runtime, no Google sandbox account and no network egress to BigQuery in this
  environment, so T029 of [tasks.md](./tasks.md) stays unchecked: the drivers are verified through
  fakes at the SDK boundary and through a real SQLite file, which is where this kind's logic lives.
- `make check`'s full backend suite takes hours against the remote BI database; the suites listed in
  §1 are the ones this feature can change, and they are green.

## Known failures that are not this feature's

Five tests of `tests/test_bi_ready_declaration.py`, two of `tests/test_source_structure_ai.py` and
one of `tests/test_bulk_extract.py` fail with this working tree stashed, i.e. on `HEAD`: their
fakes replace `describe()` with a lambda that does not accept `date_ranges`/`name`, which the
dispatcher already passed before this feature (`TypeError: … unexpected keyword argument`). They are
listed here so a reviewer does not attribute them to 061.
