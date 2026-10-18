"""Direct-report engine (feature 019): deny-list, runner, concurrency, log."""
import logging
import math
import os
import re
import threading
import time
import types
from datetime import date

import bizview_cli.validate as wsv
import psycopg
import pytest
import yaml
from psycopg import sql as pgsql
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db import get_engine, get_read_sessionmaker, get_sessionmaker, lock_key
from app.engine import direct, extract, report
from app.errors import ApiError
from app.models import Base
from tests.conftest import signed_in, sql
from tests.test_reports_params import _pdf_lines
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import apply, lock
from tests.workspace_fixture import write


def test_every_base_table_refused_for_bi():
    for table in Base.metadata.tables.values():
        assert direct.refusal("public", table.name, bi=True) == direct.PRODUCT_MESSAGE
        assert direct.refusal("Public", table.name.upper(), bi=True) == direct.PRODUCT_MESSAGE


def test_alembic_version_refused_always():
    assert direct.refusal("public", "alembic_version", bi=True) == direct.PRODUCT_MESSAGE
    assert direct.refusal("public", "alembic_version", bi=False) == direct.PRODUCT_MESSAGE


@pytest.mark.parametrize("schema,table", [
    ("pg_catalog", "pg_class"),
    ("information_schema", "tables"),
    ("pg_toast_x", "something"),
    ("app_test_abc", "any_table"),
    ("preview_1", "any_table"),
])
def test_reserved_schemas_refused_even_for_non_bi(schema, table):
    assert direct.refusal(schema, table, bi=False) == direct.PRODUCT_MESSAGE


def test_dataset_tables_allowed_for_bi():
    assert direct.refusal("ds_ventas", "lines", bi=True) is None
    assert direct.refusal("public", "origin_sales", bi=True) is None


def test_non_product_schema_product_table_allowed_for_bi():
    assert direct.refusal("sales", "app_user", bi=True) is None


def test_product_table_allowed_for_non_bi():
    assert direct.refusal("public", "app_user", bi=False) is None


def test_physical_logical_round_trip_under_test_schema():
    settings = get_settings()
    assert settings.db_schema.startswith("app_test_")
    assert direct.physical_schema("public") == f"{settings.db_schema}__public"
    assert direct.logical_schema(direct.physical_schema("public")) == "public"
    assert direct.logical_schema(direct.physical_schema("ds_ventas")) == "ds_ventas"
    assert direct.logical_schema(settings.db_schema) == "public"
    assert direct.logical_schema("unrelated_schema") == "unrelated_schema"


def _bi_source(**overrides):
    url = make_url(get_settings().database_url_bi)
    data = {"host": url.host, "port": url.port or 5432, "database": url.database,
            "username": url.username}
    data.update(overrides)
    return data


def test_is_bi_database_true():
    url = make_url(get_settings().database_url_bi)
    assert direct.is_bi_database(_bi_source()) is True
    assert direct.is_bi_database(_bi_source(port=str(url.port or 5432))) is True
    assert direct.is_bi_database(_bi_source(host=url.host.upper())) is True
    assert direct.is_bi_database({"host": url.host, "database": url.database}) is \
        ((url.port or 5432) == 5432)


def test_is_bi_database_false():
    url = make_url(get_settings().database_url_bi)
    assert direct.is_bi_database(_bi_source(database="other_db")) is False
    assert direct.is_bi_database(_bi_source(port=int(url.port or 5432) + 1)) is False
    assert direct.is_bi_database(_bi_source(host=None)) is False
    assert direct.is_bi_database(_bi_source(host="")) is False
    assert direct.is_bi_database(_bi_source(port="abc")) is False


@pytest.fixture(autouse=True)
def _clear_direct_cache(monkeypatch):
    monkeypatch.setattr(direct, "LOG_ASYNC", False)
    direct.clear_cache()
    yield
    direct.clear_cache()


def test_direct_error_default_messages():
    assert direct.DirectError("timeout").message == "La consulta superó el tiempo límite"
    assert direct.DirectError("unreachable").message == "No se pudo conectar con la fuente"
    assert direct.DirectError("busy").message == "La fuente está ocupada"
    assert direct.DirectError("not_allowed").message == "Esta fuente no permite reportes directos"
    assert direct.DirectError("product_table").message == direct.PRODUCT_MESSAGE
    assert direct.DirectError("structure_changed").message == "La estructura de la fuente cambió"
    assert direct.DirectError("error").message == "No se pudo leer la fuente"


def test_direct_error_special_constructors():
    assert direct.DirectError.timeout(15).message == "La consulta superó el tiempo límite de 15 s"
    assert direct.DirectError.structure_changed("importe").message.endswith("falta importe")


def test_direct_error_unknown_code():
    with pytest.raises(ValueError):
        direct.DirectError("unknown")


def test_resolve_bi():
    src = direct.resolve("bi")
    assert src.key == "bi" and src.label == "BI" and src.bi and src.builtin
    src2 = direct.resolve(" BI ")
    assert src2.key == "bi"


def test_resolve_bi_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "direct_reports_bi", False)
    with pytest.raises(direct.DirectError) as e:
        direct.resolve("bi")
    assert e.value.code == "not_allowed"


def test_resolve_catalogue_off_by_default(pg_source):
    with pytest.raises(direct.DirectError) as e:
        direct.resolve("origen prueba")
    assert e.value.code == "not_allowed"


def test_resolve_catalogue_enabled(pg_source):
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    src = direct.resolve("origen PRUEBA")
    assert src.label == "Origen prueba"
    assert src.key == "origen prueba"
    assert src.builtin is False
    assert src.bi is True
    assert isinstance(src.secrets, dict) and "password" in src.secrets


def test_resolve_catalogue_cached_until_expired(monkeypatch, pg_source):
    sql("UPDATE data_source SET direct_reports = true")
    monkeypatch.setattr(direct, "RESOLVE_TTL_SECONDS", 0.0)
    direct.clear_cache()
    direct.resolve("origen prueba")
    sql("UPDATE data_source SET enabled = false")
    with pytest.raises(direct.DirectError) as e:
        direct.resolve("origen prueba")
    assert e.value.code == "not_allowed"


def test_resolve_catalogue_cache_refusal_and_clear(pg_source):
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    first = direct.resolve("origen prueba")
    sql("UPDATE data_source SET enabled = false")
    second = direct.resolve("origen prueba")
    assert second == first
    direct.clear_cache()
    with pytest.raises(direct.DirectError) as e:
        direct.resolve("origen prueba")
    assert e.value.code == "not_allowed"


def test_resolve_unknown_name():
    with pytest.raises(direct.DirectError) as e:
        direct.resolve("source-that-does-not-exist")
    assert e.value.code == "not_allowed"


def test_resolve_non_postgresql_kind(monkeypatch):
    fake = types.SimpleNamespace(kind="rest", enabled=True, direct_reports=True, name="X",
                                 id=1, settings={})
    monkeypatch.setattr(direct.sources_service, "by_name", lambda db, name: fake)
    with pytest.raises(direct.DirectError) as e:
        direct.resolve("x")
    assert e.value.code == "not_allowed"


def test_resolve_refused_does_not_connect_or_decrypt(monkeypatch, pg_source):
    import app.engine.extract as extract
    monkeypatch.setattr(extract, "_pg_connect",
                        lambda *a, **k: pytest.fail("unexpected source connection"))
    monkeypatch.setattr(direct.sources_service, "secrets_of",
                        lambda *a, **k: pytest.fail("unexpected secret decryption"))
    with pytest.raises(direct.DirectError) as e:
        direct.resolve("origen prueba")  # direct_reports is off by default
    assert e.value.code == "not_allowed"


def test_lookup_failure_is_error_code_and_not_cached(monkeypatch):
    def failing(db, name):
        raise RuntimeError("boom secret")
    monkeypatch.setattr(direct.sources_service, "by_name", failing)
    with pytest.raises(direct.DirectError) as e:
        direct.resolve("anything")
    assert e.value.code == "error"
    assert "boom" not in e.value.message
    monkeypatch.setattr(direct.sources_service, "by_name", lambda db, name: None)
    with pytest.raises(direct.DirectError) as e2:
        direct.resolve("anything")
    assert e2.value.code == "not_allowed"


def test_direct_source_repr_hides_secrets(pg_source):
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    src = direct.resolve("origen prueba")
    assert "password" not in repr(src)


def _std_query(phys_schema):
    return pgsql.SQL("SELECT SUM(amount) FROM {}.sales").format(pgsql.Identifier(phys_schema))


@pytest.fixture
def seeded():
    phys = direct.physical_schema("ds_direct19")
    sql(f'DROP SCHEMA IF EXISTS "{phys}" CASCADE')
    sql(f'CREATE SCHEMA "{phys}"')
    sql(f'''CREATE TABLE "{phys}".sales (day date, amount numeric, product text)''')
    sql(f'''INSERT INTO "{phys}".sales VALUES
            ('2025-01-01', 10.5, 'A'), ('2025-01-02', 20.0, 'B'), ('2025-01-03', 5.25, 'A')''')
    yield phys
    sql(f'DROP SCHEMA "{phys}" CASCADE')


def _bi_runner(phys_schema, **overrides):
    kwargs = {
        "report_id": "r1",
        "timeout_seconds": 5,
        "tables": {"s": ("ds_direct19", "sales")},
        "columns": {"s": {"day": {"type": "date"}, "amount": {"type": "numeric"},
                          "product": {"type": "text"}}},
    }
    kwargs.update(overrides)
    return direct.DirectRunner("bi", **kwargs)


def test_direct_query_returns_rows(seeded):
    runner = _bi_runner(seeded)
    with runner.session() as s:
        rows = s.query(_std_query(seeded), "UTC")
    assert len(rows) == 1
    assert float(rows[0][0]) == 35.75


def test_two_queries_same_session_consistent(seeded):
    with _bi_runner(seeded).session() as s:
        first = s.query(_std_query(seeded), "UTC")
        second = s.query(_std_query(seeded), "UTC")
    assert first == second


def test_read_only_reject_delete(seeded):
    with _bi_runner(seeded).session() as s:
        with pytest.raises(direct.DirectError):
            s.query(pgsql.SQL("DELETE FROM {}.sales").format(pgsql.Identifier(seeded)), "UTC")
    rows = sql(f'''SELECT COUNT(*) FROM "{seeded}".sales''')
    assert rows[0][0] == 3


def test_read_only_reject_multi_statement(seeded):
    with _bi_runner(seeded).session() as s:
        with pytest.raises(direct.DirectError):
            s.query(pgsql.SQL("SELECT 1; DELETE FROM {}.sales").format(pgsql.Identifier(seeded)),
                    "UTC")
    rows = sql(f'''SELECT COUNT(*) FROM "{seeded}".sales''')
    assert rows[0][0] == 3


def test_timeout_during_query(seeded):
    with _bi_runner(seeded, timeout_seconds=60).session() as s:
        s.query(pgsql.SQL("SELECT 1"), "UTC")
    with _bi_runner(seeded, timeout_seconds=60).session() as s:
        s.query(pgsql.SQL("SELECT 1"), "UTC")

    start = time.monotonic()
    with _bi_runner(seeded, timeout_seconds=60).session() as s:
        s.query(pgsql.SQL("SELECT 1"), "UTC")
    warm = time.monotonic() - start

    timeout_seconds = max(2, math.ceil(warm) + 2)
    runner2 = _bi_runner(seeded, timeout_seconds=timeout_seconds)
    start = time.monotonic()
    deadline = start + timeout_seconds
    with pytest.raises(direct.DirectError) as e:
        with runner2.session() as s:
            s.query(pgsql.SQL("SELECT pg_sleep(600)"), "UTC")
    assert e.value.code == "timeout"
    assert time.monotonic() - deadline < 1 + warm


def test_timeout_deadline_passed(seeded):
    runner = _bi_runner(seeded, timeout_seconds=1)
    with runner.session() as s:
        time.sleep(1.05)
        with pytest.raises(direct.DirectError) as e:
            s.query(_std_query(seeded), "UTC")
    assert e.value.code == "timeout"


def test_fetch_cap_error(seeded):
    with _bi_runner(seeded).session() as s:
        with pytest.raises(direct.DirectError) as e:
            s.query(pgsql.SQL("SELECT generate_series(1, 10001)"), "UTC")
    assert e.value.code == "error"


def test_fetch_cap_ok(seeded):
    with _bi_runner(seeded).session() as s:
        rows = s.query(pgsql.SQL("SELECT generate_series(1, 10000)"), "UTC")
    assert len(rows) == 10_000


def test_structure_changed_missing_column(seeded):
    cols = {"s": {"day": {"type": "date"}, "amount": {"type": "numeric"},
                  "product": {"type": "text"}, "missing_col": {"type": "text"}}}
    runner = _bi_runner(seeded, columns=cols)
    with runner.session() as s:
        with pytest.raises(direct.DirectError) as e:
            s.query(pgsql.SQL("SELECT missing_col FROM {}.sales").format(
                pgsql.Identifier(seeded)), "UTC")
    assert e.value.code == "structure_changed"
    assert "falta missing_col" in e.value.message


def test_structure_changed_missing_table(seeded):
    sql(f'DROP TABLE "{seeded}".sales')
    runner = _bi_runner(seeded)
    with runner.session() as s:
        with pytest.raises(direct.DirectError) as e:
            s.query(pgsql.SQL("SELECT 1 FROM {}.sales").format(pgsql.Identifier(seeded)), "UTC")
    assert e.value.code == "structure_changed"
    assert "ds_direct19.sales" in e.value.message


def _make_product_views(seeded):
    test_schema = get_settings().db_schema
    sql(f'CREATE VIEW "{seeded}".v_users AS SELECT id FROM "{test_schema}".app_user')
    sql(f'''CREATE VIEW "{seeded}".v_nested AS SELECT id FROM "{seeded}".v_users''')


def test_product_view_dependency(seeded):
    _make_product_views(seeded)
    runner = _bi_runner(seeded, tables={"v": ("ds_direct19", "v_nested")},
                        columns={"v": {"id": {"type": "integer"}}})
    with pytest.raises(direct.DirectError) as e:
        with runner.session():
            pass
    assert e.value.code == "product_table"
    runner2 = _bi_runner(seeded, tables={"v": ("ds_direct19", "v_users")},
                         columns={"v": {"id": {"type": "integer"}}})
    with pytest.raises(direct.DirectError) as e2:
        with runner2.session():
            pass
    assert e2.value.code == "product_table"


def test_view_over_dataset_is_allowed(seeded):
    sql(f'''CREATE VIEW "{seeded}".v_sales AS SELECT * FROM "{seeded}".sales''')
    runner = _bi_runner(seeded, tables={"v": ("ds_direct19", "v_sales")},
                        columns={"v": {"day": {"type": "date"}, "amount": {"type": "numeric"},
                                       "product": {"type": "text"}}})
    with runner.session() as s:
        rows = s.query(pgsql.SQL("SELECT COUNT(*) FROM {}.v_sales").format(
            pgsql.Identifier(seeded)), "UTC")
    assert rows[0][0] == 3


def test_product_table_refused_before_connection(monkeypatch):
    monkeypatch.setattr(direct, "get_engine",
                        lambda *a, **k: pytest.fail("unexpected BI connection"))
    runner = direct.DirectRunner("bi", report_id="r1", timeout_seconds=5,
                                 tables={"u": ("public", "app_user")})
    with pytest.raises(direct.DirectError) as e:
        with runner.session():
            pass
    assert e.value.code == "product_table"


_spy_records: list[tuple[int, str]] = []
_spy_enabled = False


def _spy(conn, text):
    if _spy_enabled:
        _spy_records.append((id(conn), text))


def _patch_cursor(monkeypatch):
    orig_execute = psycopg.Cursor.execute
    orig_server_execute = psycopg.ServerCursor.execute

    def _patched(self, query, *args, **kwargs):
        if isinstance(query, pgsql.Composed):
            text = query.as_string(self.connection)
        else:
            text = str(query)
        _spy(self.connection, text)
        return orig_execute(self, query, *args, **kwargs)

    def _patched_server(self, query, *args, **kwargs):
        if isinstance(query, pgsql.Composed):
            text = query.as_string(self.connection)
        else:
            text = str(query)
        _spy(self.connection, text)
        return orig_server_execute(self, query, *args, **kwargs)

    monkeypatch.setattr(psycopg.Cursor, "execute", _patched)
    monkeypatch.setattr(psycopg.ServerCursor, "execute", _patched_server)


def test_statement_spy(seeded, monkeypatch):
    global _spy_enabled
    _spy_records.clear()
    _patch_cursor(monkeypatch)
    _spy_enabled = True
    try:
        with _bi_runner(seeded).session() as s:
            s.query(_std_query(seeded), "UTC")
            s.query(_std_query(seeded), "UTC")
    finally:
        _spy_enabled = False
    by_conn: dict[int, list[str]] = {}
    for cid, text in _spy_records:
        by_conn.setdefault(cid, []).append(text)
    assert by_conn
    selected = None
    for statements in by_conn.values():
        try:
            idx = statements.index("BEGIN READ ONLY")
        except ValueError:
            continue
        try:
            rollback_idx = statements.index("ROLLBACK", idx)
        except ValueError:
            continue
        selected = statements[idx:rollback_idx + 1]
        break
    assert selected is not None
    allowed_prefixes = ("SET LOCAL statement_timeout",
                        "SET LOCAL TimeZone",
                        "SELECT",
                        "WITH RECURSIVE")
    for stmt in selected:
        assert stmt == "BEGIN READ ONLY" \
               or stmt == "ROLLBACK" \
               or stmt.startswith(allowed_prefixes) \
               or re.fullmatch(
                   r'DECLARE "bizview_direct_\d+" NO SCROLL CURSOR FOR SELECT .*',
                   stmt, re.S) \
               or re.fullmatch(r'FETCH FORWARD 10001 FROM "bizview_direct_\d+"', stmt) \
               or re.fullmatch(r'CLOSE "bizview_direct_\d+"', stmt)
    assert selected[-1] == "ROLLBACK"
    assert "COMMIT" not in selected
    assert not any(s.startswith(("INSERT ", "UPDATE ", "DELETE ")) for s in selected)
    assert sum(1 for s in selected
               if re.fullmatch(
                   r'DECLARE "bizview_direct_\d+" NO SCROLL CURSOR FOR SELECT .*',
                   s, re.S)) == 2


def test_catalogue_bi_source_query(pg_source, seeded):
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    runner = direct.DirectRunner("origen prueba", report_id="r1", timeout_seconds=5,
                                 tables={"s": ("ds_direct19", "sales")},
                                 columns={"s": {"day": {"type": "date"},
                                                "amount": {"type": "numeric"},
                                                "product": {"type": "text"}}})
    with runner.session() as s:
        rows = s.query(_std_query(seeded), "UTC")
    assert len(rows) == 1


def test_catalogue_product_view_refused(pg_source, seeded):
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    _make_product_views(seeded)
    runner = direct.DirectRunner("origen prueba", report_id="r1", timeout_seconds=5,
                                 tables={"v": ("ds_direct19", "v_users")},
                                 columns={"v": {"id": {"type": "integer"}}})
    with pytest.raises(direct.DirectError) as e:
        with runner.session():
            pass
    assert e.value.code == "product_table"


def test_catalogue_unreachable(monkeypatch, pg_source):
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    monkeypatch.setattr(extract, "_pg_connect",
                        lambda *a, **k: (_ for _ in ()).throw(psycopg.OperationalError("x")))
    runner = direct.DirectRunner("origen prueba", report_id="r1", timeout_seconds=5,
                                 tables={"x": ("some", "table")})
    with pytest.raises(direct.DirectError) as e:
        with runner.session():
            pass
    assert e.value.code == "unreachable"


def test_body_error_propagates_and_pool_stays_clean(seeded):
    with pytest.raises(ValueError):
        with _bi_runner(seeded).session():
            raise ValueError("body")
    with _bi_runner(seeded).session() as s:
        rows = s.query(_std_query(seeded), "UTC")
    assert len(rows) == 1


def test_structure_bi(seeded):
    _make_product_views(seeded)
    result = direct.structure("bi", ["ds_direct19.sales", "ds_direct19.nope",
                                     "ds_direct19.v_users", "public.app_user"])
    tables = result.get("tables", {})
    assert "error" not in result
    assert "ds_direct19.sales" in tables
    assert tables["ds_direct19.sales"]["columns"] == {
        "day": "date", "amount": "numeric", "product": "text"}
    assert tables["ds_direct19.sales"]["product_dependency"] is False
    assert "ds_direct19.nope" not in tables
    assert "public.app_user" not in tables
    assert tables["ds_direct19.v_users"]["product_dependency"] is True


def test_structure_not_allowed(monkeypatch):
    monkeypatch.setattr(get_settings(), "direct_reports_bi", False)
    result = direct.structure("bi", ["public.something"])
    assert result == {"error": "Esta fuente no permite reportes directos"}


def _quote_role(role: str) -> str:
    return '"' + role.replace('"', '""') + '"'


def _test_role() -> str:
    role = os.environ.get("DIRECT_BI_TEST_ROLE", "")
    if not role:
        pytest.skip("DIRECT_BI_TEST_ROLE not set")
    rows = sql("SELECT 1 FROM pg_roles WHERE rolname = :r", r=role)
    if not rows:
        pytest.skip(f"role {role} does not exist")
    rows = sql("SELECT pg_has_role(current_user, :r, 'MEMBER') AS ok", r=role)
    if not rows or not rows[0][0]:
        pytest.skip(f"current user is not a member of {role}")
    return role


def test_role_statement_spy(seeded, monkeypatch):
    global _spy_enabled
    role = make_url(get_settings().database_url_bi).username
    monkeypatch.setattr(get_settings(), "direct_bi_role", role)
    _spy_records.clear()
    _patch_cursor(monkeypatch)
    _spy_enabled = True
    try:
        with _bi_runner(seeded).session() as s:
            rows = s.query(_std_query(seeded), "UTC")
    finally:
        _spy_enabled = False
    assert float(rows[0][0]) == 35.75
    selected = None
    by_conn: dict[int, list[str]] = {}
    for cid, text in _spy_records:
        by_conn.setdefault(cid, []).append(text)
    for statements in by_conn.values():
        try:
            idx = statements.index("BEGIN READ ONLY")
        except ValueError:
            continue
        selected = statements[idx:]
        break
    assert selected is not None
    assert selected[1] == f"SET LOCAL ROLE {_quote_role(role)}"


def test_role_quoting_error(seeded, monkeypatch):
    global _spy_enabled
    role = 'no_such_role_"019'
    monkeypatch.setattr(get_settings(), "direct_bi_role", role)
    _spy_records.clear()
    _patch_cursor(monkeypatch)
    _spy_enabled = True
    try:
        runner = _bi_runner(seeded)
        with pytest.raises(direct.DirectError) as e:
            with runner.session():
                pass
    finally:
        _spy_enabled = False
    assert e.value.code == "error"
    expected = 'SET LOCAL ROLE "no_such_role_""019"'
    assert any(text == expected for _, text in _spy_records), _spy_records


def test_catalogue_no_role(pg_source, seeded, monkeypatch):
    global _spy_enabled
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    monkeypatch.setattr(get_settings(), "direct_bi_role",
                        make_url(get_settings().database_url_bi).username)
    _spy_records.clear()
    _patch_cursor(monkeypatch)
    _spy_enabled = True
    try:
        runner = direct.DirectRunner("origen prueba", report_id="r1", timeout_seconds=5,
                                     tables={"s": ("ds_direct19", "sales")})
        with runner.session() as s:
            s.query(_std_query(seeded), "UTC")
    finally:
        _spy_enabled = False
    assert not any("SET LOCAL ROLE" in text for _, text in _spy_records)


def test_role_permission_denied(seeded, monkeypatch):
    role = _test_role()
    qrole = _quote_role(role)
    test_schema = get_settings().db_schema
    phys = seeded
    sql(f"""CREATE OR REPLACE FUNCTION "{phys}".f_users() RETURNS bigint
            LANGUAGE sql SECURITY INVOKER AS
            $$ SELECT count(*) FROM "{test_schema}".app_user $$""")
    sql(f"""CREATE VIEW "{phys}".v_fn AS SELECT "{phys}".f_users() AS n""")
    sql(f'GRANT USAGE ON SCHEMA "{phys}" TO {qrole}')
    sql(f'GRANT SELECT ON "{phys}".v_fn TO {qrole}')
    sql(f'GRANT EXECUTE ON FUNCTION "{phys}".f_users() TO {qrole}')
    monkeypatch.setattr(get_settings(), "direct_bi_role", role)
    runner = _bi_runner(seeded, tables={"v": ("ds_direct19", "v_fn")},
                        columns={"v": {"n": {"type": "bigint"}}})
    with pytest.raises(direct.DirectError) as e:
        with runner.session() as s:
            s.query(pgsql.SQL("SELECT n FROM {}.v_fn").format(pgsql.Identifier(phys)), "UTC")
    assert e.value.code == "error"
    assert "permission denied" in e.value.message.lower() \
           or "insufficientprivilege" in e.value.message.lower()
    monkeypatch.setattr(get_settings(), "direct_bi_role", None)
    runner2 = _bi_runner(seeded, tables={"v": ("ds_direct19", "v_fn")},
                         columns={"v": {"n": {"type": "bigint"}}})
    with runner2.session() as s:
        rows = s.query(pgsql.SQL("SELECT n FROM {}.v_fn").format(pgsql.Identifier(phys)), "UTC")
    assert len(rows) == 1


def test_concurrency_semaphore_busy(seeded, monkeypatch):
    monkeypatch.setattr(get_settings(), "direct_report_concurrency", 1)
    _clear_direct_read_log()
    outcome = []

    def worker():
        try:
            with _bi_runner(seeded, timeout_seconds=1).session():
                pass
        except Exception as e:
            outcome.append(e)
        else:
            outcome.append(None)

    with _bi_runner(seeded).session():
        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=15)
    assert not t.is_alive(), "worker session should have returned"
    assert len(outcome) == 1
    assert isinstance(outcome[0], direct.DirectError)
    assert outcome[0].code == "busy"
    rows = sql("SELECT duration_ms FROM direct_read_log WHERE outcome = 'busy'")
    assert len(rows) == 1
    assert rows[0][0] < 2000
    with _bi_runner(seeded).session() as s:
        rows = s.query(_std_query(seeded), "UTC")
    assert float(rows[0][0]) == 35.75


def test_cross_process_advisory_lock_busy(seeded, monkeypatch):
    monkeypatch.setattr(get_settings(), "direct_report_concurrency", 1)
    key = lock_key("direct", "bi", "0")
    conn = get_engine().connect()
    pg = conn.connection.driver_connection
    pg.autocommit = True
    try:
        got = pg.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
            (key,),
        ).fetchone()[0]
        assert got is True
        start = time.monotonic()
        with pytest.raises(direct.DirectError) as e:
            with _bi_runner(seeded, timeout_seconds=1).session():
                pass
        assert e.value.code == "busy"
        assert time.monotonic() - start < 3
    finally:
        pg.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,))
        pg.autocommit = False
        conn.close()
    with _bi_runner(seeded).session() as s:
        rows = s.query(_std_query(seeded), "UTC")
    assert float(rows[0][0]) == 35.75


def _raw_try_lock(slot):
    conn = get_engine().connect()
    pg = conn.connection.driver_connection
    pg.autocommit = True
    try:
        got = pg.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
            (lock_key("direct", "bi", str(slot)),),
        ).fetchone()[0]
        return got, pg, conn
    except Exception:
        pg.autocommit = False
        conn.close()
        raise


def _raw_unlock(pg, slot):
    pg.execute(
        "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
        (lock_key("direct", "bi", str(slot)),),
    )


def test_locks_released_after_errors(seeded, monkeypatch):
    monkeypatch.setattr(get_settings(), "direct_report_concurrency", 1)
    with pytest.raises(ValueError):
        with _bi_runner(seeded).session():
            raise ValueError("body error")
    with pytest.raises(direct.DirectError) as e:
        with _bi_runner(seeded).session() as s:
            s.query(pgsql.SQL("SELECT 1/0"), "UTC")
    assert e.value.code == "error"

    got0, pg0, conn0 = _raw_try_lock(0)
    got1, pg1, conn1 = _raw_try_lock(1)
    assert got0 is True and got1 is True
    _raw_unlock(pg0, 0)
    _raw_unlock(pg1, 1)
    pg0.autocommit = False
    pg1.autocommit = False
    conn0.close()
    conn1.close()

    with _bi_runner(seeded).session() as s:
        rows = s.query(_std_query(seeded), "UTC")
    assert float(rows[0][0]) == 35.75


def test_backoff_marks_source_down(monkeypatch, pg_source):
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    calls = 0

    def _fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(extract, "_pg_connect", _fail)
    runner = direct.DirectRunner("origen prueba", report_id="r1", timeout_seconds=5,
                                 tables={"x": ("some", "table")})
    with pytest.raises(direct.DirectError) as e:
        with runner.session():
            pass
    assert e.value.code == "unreachable"
    assert calls == 1
    with pytest.raises(direct.DirectError) as e2:
        with runner.session():
            pass
    assert e2.value.code == "unreachable"
    assert calls == 1  # marked down, no new call

    direct.clear_cache()
    monkeypatch.setattr(direct, "DOWN_SECONDS", 0.0)
    with pytest.raises(direct.DirectError):
        with runner.session():
            pass
    assert calls == 2
    with pytest.raises(direct.DirectError):
        with runner.session():
            pass
    assert calls == 3


def test_bi_lock_connection_failure_not_marked_down(monkeypatch):
    monkeypatch.setattr(direct, "get_engine",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no db")))
    runner = _bi_runner("unused")
    with pytest.raises(direct.DirectError) as e:
        with runner.session():
            pass
    assert e.value.code == "error"
    assert direct._is_down("bi") is False


def _clear_direct_read_log():
    sql("DELETE FROM direct_read_log")


def test_log_ok_session(seeded, caplog):
    _clear_direct_read_log()
    with caplog.at_level(logging.INFO, logger="app.direct"):
        with _bi_runner(seeded).session() as s:
            s.query(_std_query(seeded), "UTC")
            s.query(_std_query(seeded), "UTC")
    rows = sql("SELECT report_id, source, rows, outcome, stale_served, duration_ms "
               "FROM direct_read_log ORDER BY id")
    assert len(rows) == 1
    r = rows[0]
    assert r[0] == "r1"
    assert r[1] == "bi"
    assert r[2] == 2
    assert r[3] == "ok"
    assert r[4] is False
    assert r[5] >= 0
    records = [rec.message for rec in caplog.records if rec.name == "app.direct"]
    assert len(records) == 1
    assert "outcome=ok" in records[0]
    assert "SELECT" not in records[0]


def test_log_timeout_outcome(seeded):
    _clear_direct_read_log()
    runner = _bi_runner(seeded, timeout_seconds=1)
    with pytest.raises(direct.DirectError):
        with runner.session() as s:
            s.query(pgsql.SQL("SELECT pg_sleep(3)"), "UTC")
    rows = sql("SELECT outcome, rows FROM direct_read_log ORDER BY id")
    assert len(rows) == 1
    assert rows[0][0] == "timeout"
    assert rows[0][1] == 0


def test_log_not_allowed_outcome(seeded, monkeypatch):
    _clear_direct_read_log()
    monkeypatch.setattr(get_settings(), "direct_reports_bi", False)
    with pytest.raises(direct.DirectError):
        with _bi_runner(seeded).session():
            pass
    rows = sql("SELECT report_id, source, outcome, rows FROM direct_read_log ORDER BY id")
    assert len(rows) == 1
    assert rows[0][0] == "r1"
    assert rows[0][1] == "bi"
    assert rows[0][2] == "not_allowed"
    assert rows[0][3] == 0


def test_log_product_table_outcome(seeded):
    _clear_direct_read_log()
    runner = direct.DirectRunner("bi", report_id="r1", timeout_seconds=5,
                                 tables={"u": ("public", "app_user")})
    with pytest.raises(direct.DirectError):
        with runner.session():
            pass
    rows = sql("SELECT outcome FROM direct_read_log ORDER BY id")
    assert len(rows) == 1
    assert rows[0][0] == "product_table"


def test_log_body_error_outcome(seeded):
    _clear_direct_read_log()
    with pytest.raises(ValueError):
        with _bi_runner(seeded).session():
            raise ValueError("boom")
    rows = sql("SELECT outcome FROM direct_read_log ORDER BY id")
    assert len(rows) == 1
    assert rows[0][0] == "error"


def test_log_write_failure_swallowed(seeded, monkeypatch, caplog):
    _clear_direct_read_log()
    monkeypatch.setattr(direct, "get_sessionmaker",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no db")))
    with caplog.at_level(logging.WARNING, logger="app.direct"):
        with _bi_runner(seeded).session() as s:
            rows = s.query(_std_query(seeded), "UTC")
    assert float(rows[0][0]) == 35.75
    assert any("read log not written" in rec.message for rec in caplog.records)


def test_prune_log():
    _clear_direct_read_log()
    sql("INSERT INTO direct_read_log (report_id, source, duration_ms, rows, outcome, "
        "occurred_at) VALUES ('r1', 'bi', 1, 0, 'ok', now() - interval '8 days')")
    sql("INSERT INTO direct_read_log (report_id, source, duration_ms, rows, outcome, "
        "occurred_at) VALUES ('r1', 'bi', 1, 0, 'ok', now() - interval '1 day')")
    with get_sessionmaker().begin() as db:
        n = direct.prune_log(db)
    assert n == 1
    remaining = sql("SELECT count(*) FROM direct_read_log")
    assert remaining[0][0] == 1


def test_worker_preview_housekeeping_calls_prune(monkeypatch):
    from app import worker as worker_module
    from app.worker import Worker
    _clear_direct_read_log()
    calls = []

    def fake_prune(db):
        calls.append(1)
        return 1

    monkeypatch.setattr(worker_module.assistant_preview, "cleanup_stale", lambda db: None)
    monkeypatch.setattr(worker_module.direct, "prune_log", fake_prune)
    w = Worker()
    try:
        w.preview_housekeeping()
        assert calls == [1]
        w.preview_housekeeping()
        assert calls == [1]
    finally:
        w.pool.shutdown(wait=False)


def test_worker_preview_housekeeping_swallows_prune_error(monkeypatch):
    from app import worker as worker_module
    from app.worker import Worker

    def failing_prune(db):
        raise RuntimeError("prune boom")

    monkeypatch.setattr(worker_module.assistant_preview, "cleanup_stale", lambda db: None)
    monkeypatch.setattr(worker_module.direct, "prune_log", failing_prune)
    w = Worker()
    try:
        w.preview_housekeeping()
    finally:
        w.pool.shutdown(wait=False)


def test_structure_reltuples_and_date_index(seeded):
    sql(f'INSERT INTO "{seeded}".sales '
        f"(day, amount, product) SELECT '2025-01-04'::date + i, i, 'X' "
        f"FROM generate_series(1, 7) AS i")
    sql(f'ANALYZE "{seeded}".sales')
    result = direct.structure("bi", ["ds_direct19.sales"])
    info = result["tables"]["ds_direct19.sales"]
    assert info["reltuples"] == 10
    assert info["date_indexed"] is False
    assert info["date_index_columns"] == []

    sql(f'CREATE INDEX ON "{seeded}".sales (day)')
    result = direct.structure("bi", ["ds_direct19.sales"])
    info = result["tables"]["ds_direct19.sales"]
    assert info["date_indexed"] is True
    assert info["date_index_columns"] == ["day"]


def test_structure_text_index_not_counted(seeded):
    sql(f'CREATE INDEX ON "{seeded}".sales (product)')
    result = direct.structure("bi", ["ds_direct19.sales"])
    info = result["tables"]["ds_direct19.sales"]
    assert info["date_indexed"] is False
    assert info["date_index_columns"] == []


def test_structure_partition_key_counts(seeded):
    sql(f'CREATE TABLE "{seeded}".psales (day date, amount numeric) '
        f'PARTITION BY RANGE (day)')
    sql(f'CREATE TABLE "{seeded}".psales_2025 PARTITION OF "{seeded}".psales '
        f"FOR VALUES FROM ('2025-01-01') TO ('2026-01-01')")
    result = direct.structure("bi", ["ds_direct19.psales"])
    info = result["tables"]["ds_direct19.psales"]
    assert info["date_indexed"] is True
    assert info["date_index_columns"] == ["day"]


def test_direct_context_accepts_warn_rows():
    from bizview_cli.validate import DirectContext
    ctx = DirectContext(warn_rows=5)
    assert ctx.warn_rows == 5


def test_fingerprint_bypass_denylist(pg_source, seeded, monkeypatch):
    monkeypatch.setattr(direct, "is_bi_database", lambda s: False)
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    src = direct.resolve("origen prueba")
    assert src.bi is False
    runner = direct.DirectRunner("origen prueba", report_id="r1", timeout_seconds=5,
                                 tables={"u": ("public", "app_user")})
    with pytest.raises(direct.DirectError) as e:
        with runner.session():
            pass
    assert e.value.code == "product_table"

    result = direct.structure("origen prueba", ["public.app_user"])
    assert "error" not in result
    assert "public.app_user" not in result.get("tables", {})

    monkeypatch.setattr(direct, "_bi_fingerprint", lambda: ("other", "x", "1"))
    direct.clear_cache()
    result2 = direct.structure("origen prueba", ["public.app_user"])
    assert "error" not in result2
    assert "public.app_user" in result2.get("tables", {})


def test_fingerprint_normal_catalogue_path(pg_source, seeded, monkeypatch):
    monkeypatch.setattr(direct, "is_bi_database", lambda s: False)
    monkeypatch.setattr(direct, "_bi_fingerprint",
                        lambda: ("other", "x", "1"))
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    runner = direct.DirectRunner("origen prueba", report_id="r1", timeout_seconds=5,
                                 tables={"s": ("ds_direct19", "sales")},
                                 columns={"s": {"day": {"type": "date"},
                                                "amount": {"type": "numeric"},
                                                "product": {"type": "text"}}})
    with runner.session() as s:
        rows = s.query(_std_query(seeded), "UTC")
    assert float(rows[0][0]) == 35.75


def test_fingerprint_bi_failure_fails_closed(pg_source, seeded, monkeypatch):
    monkeypatch.setattr(direct, "is_bi_database", lambda s: False)
    monkeypatch.setattr(direct, "_bi_fingerprint",
                        lambda: (_ for _ in ()).throw(direct.DirectError("error", "x")))
    sql("UPDATE data_source SET direct_reports = true")
    direct.clear_cache()
    runner = direct.DirectRunner("origen prueba", report_id="r1", timeout_seconds=5,
                                 tables={"s": ("ds_direct19", "sales")})
    with pytest.raises(direct.DirectError) as e:
        with runner.session():
            pass
    assert e.value.code == "error"


def test_log_row_written_async(seeded, monkeypatch):
    sql("DELETE FROM direct_read_log")
    monkeypatch.setattr(direct, "LOG_ASYNC", True)
    with _bi_runner(seeded).session() as s:
        s.query(pgsql.SQL("SELECT 1"), "UTC")
    assert direct.flush_log()
    rows = sql("SELECT report_id, outcome FROM direct_read_log")
    assert rows == [("r1", "ok")]


# --- US1 (T024): a direct report over `public.bi_ventas` of the BI database ----------------------

US1_REPORT = {
    "id": "bi-ventas",
    "spec": "specs/reports/001-bi-ventas",
    "title": "Ventas BI",
    "direct": {
        "source": "bi",
        "cache_seconds": 300,
        "tables": {
            "s": {
                "table": "public.bi_ventas",
                "columns": {"day": {"type": "date"}, "amount": {"type": "numeric"},
                            "product": {"type": "text"}},
            },
        },
    },
    "date": "s.day",
    "metrics": {"total": {"label": "Total", "format": "number", "sql": "sum(s.amount)"}},
    "dimensions": {"product": {"label": "Producto", "sql": "s.product"}},
    "periods": {"default": "mtd", "allowed": ["mtd", "custom"]},
    "compare": {"default": "none", "allowed": ["none", "previous_period"]},
    "views": [{"type": "kpis", "metrics": ["total"]},
              {"type": "trend", "metric": "total", "grain": "day"},
              {"type": "ranking", "dimension": "product", "metric": "total", "limit": 5},
              {"type": "table", "dimensions": ["product"], "metrics": ["total"]}],
    "filters": ["product"],
    "pdf": {"enabled": True},
}
BUCKET_A = 1_000_000 * 300 + 1
BUCKET_B = BUCKET_A + 300


def _write_workspace(root, report_dict, tables_line):
    rid = report_dict["id"]
    spec_folder = report_dict["spec"]
    write(root, "bizview.yaml", "name: cliente\ncurrency: USD\n")
    write(root, f"{spec_folder}/spec.md",
          f"# Ventas\n\n**Spec type**: report\n\n**Status**: Implemented\n\n"
          f"**Modo**: directo\n\n**Fuente**: bi\n\n**Tablas**: {tables_line}\n\n"
          f"**Mantenido por**: proceso ERP\n\n**Volumen esperado**: 3 filas\n")
    write(root, f"{spec_folder}/plan.md", "# Plan\n")
    write(root, f"{spec_folder}/tasks.md", "- [X] T001 hecho\n")
    write(root, f"reports/{rid}/report.yaml",
          yaml.safe_dump(report_dict, sort_keys=False, allow_unicode=True))


@pytest.fixture
def bi_ventas(tmp_path, monkeypatch):
    settings = get_settings()
    phys = direct.physical_schema("public")
    sql(f'CREATE SCHEMA IF NOT EXISTS "{phys}"')
    sql(f'DROP TABLE IF EXISTS "{phys}".bi_ventas CASCADE')
    sql(f'CREATE TABLE "{phys}".bi_ventas (day date, amount numeric, product text)')
    sql(f'INSERT INTO "{phys}".bi_ventas VALUES '
        f"('2026-09-01', 10.5, 'A'), ('2026-09-02', 20.0, 'B'), ('2026-09-03', 5.25, 'A')")
    root = tmp_path / "ws"
    root.mkdir()
    _write_workspace(root, US1_REPORT, "public.bi_ventas")
    monkeypatch.setattr(settings, "workspace_path", str(root))
    yield root
    sql(f'DROP TABLE IF EXISTS "{phys}".bi_ventas CASCADE')


def test_us1_direct_report_end_to_end(bi_ventas, superuser, monkeypatch):
    settings = get_settings()
    phys = direct.physical_schema("public")
    direct._inflight.clear()
    ds_before = sql("SELECT count(*) FROM information_schema.schemata "
                    "WHERE schema_name LIKE :p",
                    p=f"{settings.db_schema}\\_\\_ds\\_%")[0][0]

    lock(bi_ventas)
    c = signed_in("root@example.com")
    apply(c)

    definition = c.get("/api/reports/bi-ventas").json()
    # 022: the API sends the raw source id; clients show "bi" in their language.
    assert definition["direct"] == {"source": "bi", "cache_seconds": 300}

    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)
    bucket = BUCKET_A // 300

    query = "?period=custom&from=2026-09-01&to=2026-09-30&compare=none"
    data = c.get(f"/api/reports/bi-ventas/data{query}").json()
    assert data["freshness"]["mode"] == "direct"
    assert data["freshness"]["source"] == "bi"            # localized by the client (022)
    assert data["freshness"]["stale"] is False
    assert data["freshness"]["data_version"].endswith(f"-d{bucket}")
    assert data["views"][0]["items"][0]["value"] == 35.75
    points = data["views"][1]["points"]
    assert points[:3] == [
        {"bucket": "2026-09-01", "value": 10.5},
        {"bucket": "2026-09-02", "value": 20.0},
        {"bucket": "2026-09-03", "value": 5.25},
    ]
    assert len(points) == 30
    assert all(p["value"] is None for p in points[3:])
    assert [(i["key"], i["value"]) for i in data["views"][2]["items"]] == [
        ("B", 20.0), ("A", 15.75)]
    assert len(data["views"][3]["rows"]) == 2

    filtered = c.get(f"/api/reports/bi-ventas/data{query}&filter.product=A").json()
    assert filtered["views"][0]["items"][0]["value"] == 15.75

    filter_items = c.get(f"/api/reports/bi-ventas/filters/product{query}").json()
    assert filter_items == {"items": ["A", "B"], "truncated": False}

    pdf = c.post(f"/api/reports/bi-ventas/pdf{query}")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert any(line.startswith("Datos en vivo · BI de esta instalación · consultado ")
               for line in _pdf_lines(pdf.content))

    version = c.get("/api/reports/bi-ventas/version").json()
    assert version["updated_at"] is None
    assert version["data_version"].endswith(f"-d{bucket}")

    sql(f'INSERT INTO "{phys}".bi_ventas VALUES (\'2026-09-04\', 100, \'C\')')
    same_bucket = c.get(f"/api/reports/bi-ventas/data{query}").json()
    assert same_bucket["views"][0]["items"][0]["value"] == 35.75

    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)
    next_bucket = c.get(f"/api/reports/bi-ventas/data{query}").json()
    assert next_bucket["views"][0]["items"][0]["value"] == 135.75

    ds_after = sql("SELECT count(*) FROM information_schema.schemata "
                   "WHERE schema_name LIKE :p",
                   p=f"{settings.db_schema}\\_\\_ds\\_%")[0][0]
    assert ds_before == ds_after
    assert sql("SELECT count(*) FROM integration_run")[0][0] == 0


def test_us1_under_role_with_public_table_grant(bi_ventas, superuser, monkeypatch):
    # T048: the documented grants (USAGE on public + SELECT on the allowed table only)
    role = _test_role()
    qrole = _quote_role(role)
    phys = direct.physical_schema("public")
    test_schema = get_settings().db_schema

    sql(f'GRANT USAGE ON SCHEMA "{phys}" TO {qrole}')
    sql(f'GRANT SELECT ON "{phys}".bi_ventas TO {qrole}')
    sql(f'CREATE TABLE "{phys}".bi_otra (x int)')

    try:
        monkeypatch.setattr(get_settings(), "direct_bi_role", role)
        direct._inflight.clear()
        lock(bi_ventas)
        c = signed_in("root@example.com")
        apply(c)
        monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)
        query = "?period=custom&from=2026-09-01&to=2026-09-30&compare=none"
        data = c.get(f"/api/reports/bi-ventas/data{query}").json()
        assert data["freshness"]["mode"] == "direct"
        assert data["views"][0]["items"][0]["value"] == 35.75

        runner = direct.DirectRunner(
            "bi",
            report_id="r1",
            timeout_seconds=5,
            tables={"s": ("public", "bi_ventas")},
            columns={
                "s": {
                    "day": {"type": "date"},
                    "amount": {"type": "numeric"},
                    "product": {"type": "text"},
                }
            },
        )

        with pytest.raises(direct.DirectError) as e:
            with runner.session() as s:
                s.query(
                    pgsql.SQL("SELECT count(*) FROM {}.app_user").format(
                        pgsql.Identifier(test_schema)
                    ),
                    "UTC",
                )
        msg = e.value.message.lower()
        assert "permission denied" in msg or "insufficientprivilege" in msg

        with pytest.raises(direct.DirectError) as e:
            with runner.session() as s:
                s.query(
                    pgsql.SQL("SELECT count(*) FROM {}.bi_otra").format(
                        pgsql.Identifier(phys)
                    ),
                    "UTC",
                )
        msg = e.value.message.lower()
        assert "permission denied" in msg or "insufficientprivilege" in msg
    finally:
        sql(f'DROP TABLE IF EXISTS "{phys}".bi_otra')
        sql(f'REVOKE ALL ON SCHEMA "{phys}" FROM {qrole}')


def test_us1_statement_spy_through_api(bi_ventas, superuser, monkeypatch):
    direct._inflight.clear()
    lock(bi_ventas)
    c = signed_in("root@example.com")
    apply(c)
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)
    _patch_cursor(monkeypatch)

    global _spy_enabled
    _spy_records.clear()
    _spy_enabled = True
    try:
        r = c.get("/api/reports/bi-ventas/data"
                  "?period=custom&from=2026-09-01&to=2026-09-30&compare=none")
        assert r.status_code == 200
    finally:
        _spy_enabled = False

    by_conn: dict[int, list[str]] = {}
    for conn_id, statement in _spy_records:
        by_conn.setdefault(conn_id, []).append(statement)

    segments: list[list[str]] = []
    for stmts in by_conn.values():
        current: list[str] = []
        for stmt in stmts:
            if stmt == "BEGIN READ ONLY":
                if current:
                    raise AssertionError("unterminated read-only segment")
                current = [stmt]
            elif current:
                current.append(stmt)
                if stmt == "ROLLBACK":
                    segments.append(current)
                    current = []
        assert not current, "read-only segment without ROLLBACK"

    assert segments, "no standalone read-only segment"
    declare_re = re.compile(
        r'DECLARE "bizview_direct_\d+" NO SCROLL CURSOR FOR SELECT .*', re.S)
    fetch_re = re.compile(r'FETCH FORWARD 10001 FROM "bizview_direct_\d+"')
    close_re = re.compile(r'CLOSE "bizview_direct_\d+"')
    for segment in segments:
        assert segment[0] == "BEGIN READ ONLY"
        assert segment[-1] == "ROLLBACK"
        assert any(declare_re.fullmatch(stmt) for stmt in segment)
        for stmt in segment:
            assert (
                stmt in ("BEGIN READ ONLY", "ROLLBACK")
                or stmt.startswith(("SET LOCAL statement_timeout", "SET LOCAL TimeZone",
                                    "SELECT", "WITH RECURSIVE"))
                or declare_re.fullmatch(stmt)
                or fetch_re.fullmatch(stmt)
                or close_re.fullmatch(stmt)
            ), f"unexpected statement: {stmt}"
            assert not stmt.startswith(("COMMIT", "INSERT", "UPDATE", "DELETE"))


def test_us1_single_flight_runner_sessions(bi_ventas, monkeypatch):
    direct._inflight.clear()
    direct.clear_cache()
    ctx = report._build_context("bi-ventas", US1_REPORT,
                                report.PreviewVersion(id=901, artifacts={}), {}, None)
    sel, filters = report.selection(ctx, {"period": "custom", "from": "2026-09-01",
                                          "to": "2026-09-30", "compare": "none"},
                                    date(2026, 9, 30))
    key = report.selection_hash(sel, filters)

    calls = {"n": 0}
    orig = direct.DirectRunner.session

    def counting(self):
        calls["n"] += 1
        return orig(self)

    monkeypatch.setattr(direct.DirectRunner, "session", counting)
    real = report.run_views

    def slow(*args, **kwargs):
        time.sleep(0.5)
        return real(*args, **kwargs)

    monkeypatch.setattr(report, "run_views", slow)

    barrier = threading.Barrier(10)
    results = []
    errors = []
    lock_append = threading.Lock()

    def worker():
        try:
            barrier.wait()
            session = get_read_sessionmaker()()
            try:
                payload = direct.cached_data(session, ctx, sel, filters, key, "UTC")
                with lock_append:
                    results.append(payload)
            finally:
                session.close()
        except Exception as exc:  # pragma: no cover - diagnostic
            with lock_append:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert calls["n"] == 1
    assert len(results) == 10
    first = results[0]
    for r in results[1:]:
        assert r == first


def test_every_product_table_refused_at_validation(tmp_path):
    tables = list(Base.metadata.tables.values())
    root = tmp_path / "ws"
    root.mkdir()
    expected_pairs = set()
    for chunk_start in range(0, len(tables), 8):
        chunk = tables[chunk_start:chunk_start + 8]
        chunk_index = chunk_start // 8
        rid = f"evil-{chunk_index}"
        spec_folder = f"specs/reports/00{chunk_index + 1}-evil-{chunk_index}"
        direct_tables = {}
        for i, table in enumerate(chunk):
            alias = f"t{i}"
            direct_tables[alias] = {
                "table": f"public.{table.name}",
                "columns": {"id": {"type": "integer"}, "day": {"type": "date"}},
            }
            expected_pairs.add((f"reports/{rid}", f"/direct/tables/{alias}/table"))
        rep = {
            "id": rid, "spec": spec_folder, "title": "Evil",
            "direct": {"source": "bi", "cache_seconds": 60, "tables": direct_tables},
            "date": "t0.day",
            "metrics": {"total": {"label": "Total", "sql": "count(*)"}},
            "views": [{"type": "kpis", "metrics": ["total"]}],
        }
        _write_workspace(root, rep, "varias")
    db = get_sessionmaker()()
    try:
        result = wsv.validate(root, direct=direct.validation_context(db))
        pairs = {(issue.entry, issue.path) for issue in result.issues
                 if issue.code == "direct_product_table"}
        assert pairs == expected_pairs
    finally:
        db.close()


def test_every_product_table_refused_at_context_build():
    tables = list(Base.metadata.tables.values())
    for table in tables:
        rep = {
            "id": "evil", "spec": "specs/reports/001-evil", "title": "Evil",
            "direct": {
                "source": "bi", "cache_seconds": 60,
                "tables": {"t": {"table": f"public.{table.name}",
                                 "columns": {"id": {"type": "integer"},
                                             "day": {"type": "date"}}}},
            },
            "date": "t.day",
            "metrics": {"total": {"label": "Total", "sql": "count(*)"}},
            "views": [{"type": "kpis", "metrics": ["total"]}],
        }
        with pytest.raises(ApiError) as excinfo:
            report._build_context("evil", rep,
                                  report.PreviewVersion(id=902, artifacts={}), {}, None)
        assert excinfo.value.status == 409
        assert excinfo.value.code == "direct_product_table"


def test_bi_view_over_app_user_refused(tmp_path):
    settings = get_settings()
    phys = direct.physical_schema("public")
    sql(f'CREATE SCHEMA IF NOT EXISTS "{phys}"')
    sql(f'CREATE OR REPLACE VIEW "{phys}".v_app_user AS '
        f'SELECT id FROM "{settings.db_schema}".app_user')
    try:
        rep = {
            "id": "view-evil", "spec": "specs/reports/001-view-evil", "title": "View Evil",
            "direct": {
                "source": "bi", "cache_seconds": 60,
                "tables": {"v": {"table": "public.v_app_user",
                                 "columns": {"id": {"type": "integer"},
                                             "day": {"type": "date"}}}},
            },
            "date": "v.day",
            "metrics": {"total": {"label": "Total", "sql": "count(*)"}},
            "views": [{"type": "kpis", "metrics": ["total"]}],
        }
        root = tmp_path / "ws"
        root.mkdir()
        _write_workspace(root, rep, "public.v_app_user")

        db = get_sessionmaker()()
        try:
            result = wsv.validate(root, direct=direct.validation_context(db))
            assert any(issue.code == "direct_product_table" for issue in result.issues)
        finally:
            db.close()

        with pytest.raises(direct.DirectError) as excinfo:
            with direct.DirectRunner("bi", report_id="r1", timeout_seconds=5,
                                     tables={"v": ("public", "v_app_user")},
                                     columns={"v": {"id": {"type": "integer"}}}).session():
                pass
        assert excinfo.value.code == "product_table"
    finally:
        sql(f'DROP VIEW IF EXISTS "{phys}".v_app_user')
