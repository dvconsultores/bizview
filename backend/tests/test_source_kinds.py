"""Feature 061: the connector registry and the five new kinds, without a live origin.

Everything here is a unit test: a temporary SQLite file is a real origin, and MySQL, SQL Server,
BigQuery and Google Sheets are faked at the driver boundary (the SDK object, not our code), so the
rules the spec cares about — read-only, quoting, busy, dry-run ceilings, path escapes — are proven
without a container or a sandbox account.
"""
import json
import sqlite3
from pathlib import Path

import pytest

from app.config import Settings
from app.sources import schemas
from app.sources.connectors import bigquery, mssql, mysql, registry, sheets, sql, sqlite

APP = Settings(database_url_bi="postgresql://x@localhost/x", security_profile="private")


# --- the registry -----------------------------------------------------------------------------

def test_every_kind_is_declared_once_and_has_a_module():
    assert len(set(registry.KINDS)) == len(registry.KINDS)
    for kind in registry.KINDS:
        spec = registry.BY_KIND[kind]
        assert spec.fields(), kind                      # a form to fill
        assert registry.module(kind).kind == kind, kind  # a module that answers for it
        assert kind in schemas.KINDS


def test_registry_and_the_form_list_agree():
    """`schemas.KINDS` is the order the form shows; the registry is what dispatch reads."""
    assert set(schemas.KINDS) == set(registry.KINDS)


def test_capabilities_split_queries_from_requests():
    assert registry.is_sql("postgresql") and registry.is_sql("bigquery")
    assert not registry.is_sql("rest") and not registry.is_sql("sheets")
    assert registry.has_native_copy("postgresql") and not registry.has_native_copy("mysql")
    assert registry.request_rows("rest") is not None
    assert registry.request_rows("sheets") is not None
    assert registry.request_rows("mysql") is None


def test_a_kind_without_a_folder_is_not_offered(monkeypatch):
    monkeypatch.delenv(sqlite.ENV_FOLDER, raising=False)
    app = Settings(database_url_bi="postgresql://x@localhost/x", sources_files_dir=None)
    assert registry.available("sqlite", app) == "sources.unavailable.folder"
    assert "sqlite" not in schemas.types_for(app)


def test_a_kind_without_its_driver_is_listed_with_the_reason(monkeypatch):
    monkeypatch.setattr(registry, "missing_drivers", lambda kind: ("pymssql",) if kind == "mssql"
                        else ())
    payload = schemas.types_for(APP)
    assert payload["mssql"]["available"] is False
    assert payload["mssql"]["reason"]
    result = registry.test_source("mssql", {}, {}, APP)
    assert result.ok is False and result.message


def test_every_sql_kind_states_its_dialect():
    for kind in ("postgresql", "sqlite", "mysql", "mssql", "bigquery"):
        notes = registry.module(kind).dialect_notes()
        assert notes["notes"], kind
        assert notes["kind"] == kind, kind


# --- SQLite: the file is somebody else's data --------------------------------------------------

@pytest.fixture
def folder(tmp_path, monkeypatch):
    (tmp_path / "ventas.sqlite3").exists() or sqlite3.connect(tmp_path / "ventas.sqlite3").close()
    conn = sqlite3.connect(tmp_path / "ventas.sqlite3")
    conn.executescript(
        "create table ventas (id integer primary key, marca text not null, total real);"
        "insert into ventas (marca, total) values ('ACME', 10.5), ('ACME', 4.5);")
    conn.commit()
    conn.close()
    monkeypatch.setenv(sqlite.ENV_FOLDER, str(tmp_path))
    return tmp_path


def sqlite_app(path: Path) -> Settings:
    return Settings(database_url_bi="postgresql://x@localhost/x", sources_files_dir=str(path))


def test_sqlite_lists_only_files_inside_the_folder(folder):
    (folder / "notes.txt").write_text("no soy una base")
    assert [f["name"] for f in sqlite.list_files(sqlite_app(folder))] == ["ventas.sqlite3"]


@pytest.mark.parametrize("bad", ["../fuera.sqlite3", "/etc/passwd", "no-existe.db"])
def test_sqlite_refuses_what_is_not_a_file_in_the_folder(folder, bad):
    with pytest.raises(ValueError):
        sqlite.resolve(bad, sqlite_app(folder))


def test_sqlite_refuses_a_symlink_that_escapes_the_folder(folder, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "robado.sqlite3"
    sqlite3.connect(outside).close()
    (folder / "atajo.db").symlink_to(outside)
    with pytest.raises(ValueError):
        sqlite.resolve("atajo.db", sqlite_app(folder))


def test_sqlite_describes_without_reading_a_row(folder):
    structure = sqlite.describe({"path": "ventas.sqlite3"}, {}, sqlite_app(folder))
    table = structure["tables"][0]
    assert table["name"] == "ventas"
    assert [c["name"] for c in table["columns"]] == ["id", "marca", "total"]
    assert structure["kind"] == "sqlite"


def test_sqlite_reads_and_refuses_a_write(folder):
    settings = {"path": "ventas.sqlite3", "timeout_seconds": 5}
    app = sqlite_app(folder)
    with sqlite.session(settings, {}, app, timezone="UTC", time_limit_s=10) as conn:
        batches = list(sqlite.rows(conn, "select marca, total from ventas order by id", None))
        assert [row for _cols, rows in batches for row in rows] == [("ACME", 10.5), ("ACME", 4.5)]
        with pytest.raises(sql.ReadOnlyRefused):
            list(sqlite.rows(conn, "delete from ventas", None))


def test_sqlite_test_card_reports_the_file(folder):
    result = sqlite.test({"path": "ventas.sqlite3"}, {}, sqlite_app(folder))
    assert result.ok and result.details["tables"] == 1


def test_sqlite_missing_file_is_not_found(folder):
    result = sqlite.test({"path": "otro.db"}, {}, sqlite_app(folder))
    assert result.ok is False and result.code == "not_found"


# --- MySQL / MariaDB and SQL Server ------------------------------------------------------------

def test_quoting_follows_each_dialect():
    assert sql.quote("mysql", "ve`ntas") == "`ve``ntas`"
    assert sql.quote("mssql", "ve]ntas") == "[ve]]ntas]"
    assert sql.quote("postgresql", 've"ntas') == '"ve""ntas"'


def driver_error(code, message):
    """An error shaped the way PyMySQL raises it: the code and the message in `args`."""
    return Exception(code, message)


@pytest.mark.parametrize("error,code", [
    (driver_error(1040, "Too many connections"), "busy"),
    (driver_error(2003, "Can't connect to MySQL server on 'db'"), "unreachable"),
    (driver_error(1045, "Access denied for user 'bi'@'%'"), "auth_failed"),
    (driver_error(1049, "Unknown database 'erp'"), "not_found"),
    (driver_error(1129, "Host is blocked because of many connection errors"), "busy"),
    (RuntimeError("(1203, 'User bi already has more than max_user_connections')"), "busy"),
])
def test_mysql_classifies_the_engine_s_own_messages(error, code):
    assert mysql.classify(error) == code


@pytest.mark.parametrize("error,code", [
    (driver_error(17809, "Could not connect because the maximum number of connections is "
                         "reached"), "busy"),
    (driver_error(18456, "Login failed for user 'bi'"), "auth_failed"),
    (driver_error(4060, 'Cannot open database "erp" requested by the login'), "not_found"),
    (RuntimeError("('08S01', 'Adaptive Server connection timed out')"), "timeout"),
])
def test_mssql_classifies_the_engine_s_own_messages(error, code):
    assert mssql.classify(error) == code


def test_mysql_is_busy_is_the_same_rule_as_060():
    assert mysql.is_busy(driver_error(1040, "Too many connections"))
    assert not mysql.is_busy(driver_error(1045, "Access denied"))


def test_the_read_only_rule_accepts_reads_only():
    for query in ("select 1", "  WITH t AS (select 1) select * from t", "-- c\nSELECT 2",
                  "show tables", "explain select 1", "pragma table_info(x)"):
        assert sql.read_only_query(query) == query
    for query in ("insert into t values (1)", "update t set a = 1", "drop table t",
                  "create table t (a int)", "with x as (select 1) delete from t"):
        with pytest.raises(sql.ReadOnlyRefused):
            sql.read_only_query(query)


# --- BigQuery: the ceiling comes before the query ---------------------------------------------

SERVICE_ACCOUNT = json.dumps({
    "type": "service_account", "project_id": "proyecto", "private_key_id": "k1",
    "private_key": "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----\n",
    "client_email": "bi@proyecto.iam.gserviceaccount.com", "client_id": "1",
    "token_uri": "https://oauth2.googleapis.com/token"})


def test_bigquery_reads_the_datasets_and_the_ceiling():
    settings = {"project": "p", "datasets": "ventas, finanzas ;compras", "max_bytes_billed": 5000}
    assert bigquery.datasets(settings) == ["ventas", "finanzas", "compras"]
    assert bigquery.max_bytes(settings) == 5000
    assert bigquery.service_account_email({"service_account": SERVICE_ACCOUNT}) \
        == "bi@proyecto.iam.gserviceaccount.com"


@pytest.mark.parametrize("blob,key", [
    ("no es json", "sources.bigquery.bad_json"),
    (json.dumps({"client_email": "a@b.c"}), "sources.bigquery.missing_keys"),
])
def test_bigquery_explains_a_bad_service_account(blob, key):
    result = bigquery.test({"project": "p"}, {"service_account": blob}, APP)
    assert result.ok is False and result.code == "auth_failed"


def test_bigquery_refuses_a_query_over_the_ceiling_before_running_it(monkeypatch):
    calls = []

    class Job:
        total_bytes_processed = 2_000_000_000

    class Client:
        def query(self, query, job_config=None):
            calls.append(job_config)
            return Job()

        def close(self):
            pass

    cursor = bigquery._ClientCursor(Client(), {"max_bytes_billed": 1_000_000_000}, 10)
    with pytest.raises(RuntimeError, match="over the"):
        cursor.execute("select * from ventas")
    assert len(calls) == 1 and calls[0].dry_run is True   # the query never ran for real


def test_bigquery_classifies_quota_as_a_pause():
    assert bigquery.is_busy(RuntimeError("403 Quota exceeded for quota metric"))
    assert bigquery.classify(RuntimeError("404 Not found: Dataset p:x")) == "not_found"


# --- Google Sheets: one worksheet is one table ------------------------------------------------

def test_sheets_finds_the_spreadsheet_id_in_a_url():
    url = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit#gid=0"
    assert sheets.spreadsheet_id(url) == "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
    with pytest.raises(ValueError):
        sheets.spreadsheet_id("https://example.com/no-es-una-hoja")


@pytest.mark.parametrize("values,expected", [
    (["1", "2", "3"], "integer"),
    (["1.5", "2"], "number"),
    (["2024-01-02", "2024-02-03"], "date"),
    (["2024-01-02T10:00:00"], "datetime"),
    (["true", "false"], "bool"),
    (["ACME", "1"], "string"),
    (["", ""], "integer"),
])
def test_sheets_infers_the_narrowest_type(values, expected):
    assert sheets._infer(values) == expected


def test_sheets_reads_a_worksheet_through_a_fake_service(monkeypatch):
    class Values:
        def get(self, spreadsheetId, range):
            return self

        def execute(self):
            return {"values": [["marca", "total"], ["ACME", "10,5"], ["Beta", ""]]}

    class Spreadsheets:
        def values(self):
            return Values()

    class Service:
        def spreadsheets(self):
            return Spreadsheets()

    monkeypatch.setattr(sheets, "client", lambda secrets: Service())
    rows = list(sheets.request_rows({"url": "https://docs.google.com/spreadsheets/d/"
                                            "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit"},
                                    {}, APP, {"worksheet": "Ventas"}, {},
                                    ["marca", "total"], time_limit_s=10))
    assert rows == [[{"marca": "ACME", "total": "10,5"}, {"marca": "Beta", "total": None}]]


def test_sheets_explains_a_sheet_nobody_shared(monkeypatch):
    class Boom(Exception):
        pass

    def refuse(secrets):
        raise Boom("403 The caller does not have permission")

    monkeypatch.setattr(sheets, "client", refuse)
    result = sheets.test({"url": "https://docs.google.com/spreadsheets/d/"
                                 "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit"},
                         {"service_account": SERVICE_ACCOUNT}, APP)
    assert result.ok is False and "bi@proyecto.iam.gserviceaccount.com" in result.message


# --- the form: what the super user may save ---------------------------------------------------

def test_sqlite_path_outside_the_folder_cannot_be_saved(folder):
    result = schemas.validate("sqlite", {"path": "../fuera.db"}, {}, {}, sqlite_app(folder))
    assert result.errors["settings.path"].startswith("sources.sqlite.")


def test_a_new_kind_is_accepted_with_its_own_fields():
    result = schemas.validate("mysql", {"host": "127.0.0.1", "port": 3306, "database": "erp",
                                        "username": "bi"},
                              {"password": "secreta"}, {}, APP, check_addresses=False)
    assert result.errors == {}
    assert result.settings["port"] == 3306
    assert result.secrets["password"] == "secreta"


def test_an_unknown_kind_is_refused():
    assert schemas.validate("oracle", {}, {}, {}, APP).errors == {"kind": "invalid"}
