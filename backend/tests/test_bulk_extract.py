"""Feature 008: PostgreSQL extraction through a COPY pipe. The origin is the BI database itself
(read-only session), as in tests/test_runner.py, whose fixtures and helpers are reused."""
import time
from contextlib import contextmanager
from datetime import timedelta

import psycopg
import pytest
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.engine import extract, runner
from tests.conftest import TEST_SCHEMA, sql
from tests.test_runner import (
    NOW,
    ORIGIN,
    QUERY,
    ds_sql,
    ds_table,
    integration,
    lines,
    run,
)
from tests.test_runner import (
    origin as origin,
)
from tests.test_runner import (
    pg_source as pg_source,
)

SALE_LINES = ds_table("ventas-prueba", "sale_lines")


def origin_conn():
    u = make_url(get_settings().database_url_bi)
    settings = {
        "host": u.host,
        "port": u.port or 5432,
        "database": u.database,
        "username": u.username,
        "sslmode": "prefer",
        "timeout_seconds": 15,
    }
    return settings, {"password": u.password}


def dsn():
    return make_url(get_settings().database_url_bi).set(
        drivername="postgresql").render_as_string(hide_password=False)


def count_lines():
    return ds_sql(f"SELECT count(*) FROM {SALE_LINES}")[0][0]


def test_runs_use_bulk_path(origin):
    r = run()
    assert r.status == "succeeded", r.message
    for ds in ("sale_lines", "products"):
        assert r.rows[ds]["path"] == "copy"
        assert "fallback" not in r.rows[ds]
    assert len(lines()) == 4                    # a first run is a full load, as in test_runner


# Every contract column type (datasets.PG_TYPES) plus the text edge cases of the spec.
EDGE_ROWS = [
    "(1, E'line\\nbreak\\ttab \\\\ back', '', '2026-03-08 01:30-05', '2026-03-08', "
    "1234567890123456789012345678.0123456789, 9223372036854775807, true)",
    "(2, 'quotes '' \" and emoji 😀 ñ á', NULL, '2026-03-08 03:30-04', NULL, "
    "-0.0000000001, -1, false)",
    "(3, NULL, 'x', NULL, '1999-12-31', 0, 0, NULL)",
]


def test_bulk_and_rows_paths_are_identical(pg_source):
    sql("DROP TABLE IF EXISTS edge")
    sql("CREATE TABLE edge (id integer, t text, e text, ts timestamptz, d date, "
        "n numeric(38,10), b bigint, f boolean)")
    sql("INSERT INTO edge VALUES " + ", ".join(EDGE_ROWS))
    try:
        q = f'SELECT id, t, e, ts, d, n, b, f FROM "{TEST_SCHEMA}".edge'
        columns = ["id", "t", "e", "ts", "d", "n", "b", "f"]
        settings, secrets = origin_conn()
        cols = ", ".join(f'"{c}"' for c in columns)
        with psycopg.connect(dsn()) as pg:
            pg.execute(f'CREATE TEMP TABLE bulk_t (LIKE "{TEST_SCHEMA}".edge)')
            pg.execute(f'CREATE TEMP TABLE rows_t (LIKE "{TEST_SCHEMA}".edge)')
            copy_sql = f"COPY bulk_t ({cols}) FROM STDIN (FORMAT text)"
            with pg.cursor() as cur, cur.copy(copy_sql) as d:
                extract.pg_copy(settings, secrets, get_settings(), q, {}, columns=columns,
                                timezone="America/Caracas", time_limit_s=60,
                                deadline=time.monotonic() + 60, write=d.write)
            for got, rows in extract.pg_rows(settings, secrets, get_settings(), q, {},
                                             timezone="America/Caracas", time_limit_s=60):
                runner._copy(pg, "rows_t", columns, runner._text_frame(rows, got))

            # Strict: any difference is a real bug in one of the two paths (SC-003).
            for a, b in (("bulk_t", "rows_t"), ("rows_t", "bulk_t")):
                assert pg.execute(f"SELECT count(*) FROM (SELECT * FROM {a} EXCEPT ALL "
                                  f"SELECT * FROM {b}) x").fetchone()[0] == 0, f"{a} - {b}"
            assert pg.execute("SELECT count(*) FROM bulk_t").fetchone()[0] == len(EDGE_ROWS)
            assert pg.execute("SELECT count(*) FROM rows_t").fetchone()[0] == len(EDGE_ROWS)
            # Text survives byte for byte (newline, tab, backslash, quotes, emoji; '' vs NULL).
            assert pg.execute("SELECT t, e FROM bulk_t ORDER BY id").fetchall() == \
                pg.execute(f'SELECT t, e FROM "{TEST_SCHEMA}".edge ORDER BY id').fetchall()
    finally:
        sql("DROP TABLE IF EXISTS edge")


def test_column_mismatch_refused(origin):
    r = run(files={"queries/products.sql": f"SELECT DISTINCT product AS producto FROM {ORIGIN}"})
    assert r.status == "failed"
    assert "no coinciden con el contrato" in r.message


def test_type_mismatch_fails_cleanly(origin):
    assert run().status == "succeeded"
    before = count_lines()
    bad = QUERY.replace("line AS line_no", "'x' || line AS line_no")
    assert bad != QUERY
    r = run(files={"queries/lines.sql": bad})
    assert r.status == "failed"
    assert "no cumplen el contrato" in r.message
    assert r.rows["sale_lines"]["path"] == "copy"
    assert count_lines() == before


def test_deadline_stops_transfer(pg_source):
    settings, secrets = origin_conn()
    with pytest.raises(extract.ExtractError, match="tiempo máximo"):
        extract.pg_copy(settings, secrets, get_settings(),
                        "SELECT generate_series(1, 100000) AS n", {}, columns=["n"],
                        timezone="UTC", time_limit_s=60, deadline=time.monotonic() - 1,
                        write=lambda b: None)


def test_origin_session_is_read_only(pg_source):
    settings, secrets = origin_conn()
    blocks: list[bytes] = []
    extract.pg_copy(settings, secrets, get_settings(),
                    "SELECT current_setting('transaction_read_only') AS ro", {}, columns=["ro"],
                    timezone="UTC", time_limit_s=60, deadline=time.monotonic() + 60,
                    write=blocks.append)
    assert b"".join(blocks) == b"on\n"


def test_fallback_when_copy_unsupported(origin, monkeypatch):
    def refuse(*args, **kwargs):
        raise extract.BulkUnsupported("FeatureNotSupported")

    monkeypatch.setattr(extract, "pg_copy", refuse)
    r = run()
    assert r.status == "succeeded", r.message
    assert r.rows["sale_lines"]["path"] == "rows"
    assert r.rows["sale_lines"]["fallback"] == "FeatureNotSupported"
    assert len(lines()) == 4


def test_failure_after_data_does_not_fall_back(origin, monkeypatch):
    assert run().status == "succeeded"
    before = count_lines()

    def broken(*args, **kwargs):
        # Declared order: document_id, line_no, line_kind, completed_at, local_date,
        # product_code, net_amount.
        kwargs["write"](b"Z9\t1\tsale\t2026-09-28 10:00:00-04\t2026-09-28\tP1\t1\n")
        raise extract.ExtractError("la extracción falló: conexión perdida")

    monkeypatch.setattr(extract, "pg_copy", broken)
    r = run()
    assert r.status == "failed"
    assert "conexión perdida" in r.message
    assert r.rows["sale_lines"]["path"] == "copy"
    assert "fallback" not in (r.rows or {}).get("sale_lines", {})
    assert count_lines() == before


def test_sqlsafety_still_refuses_writes(origin):
    r = run(files={"queries/products.sql": f"DELETE FROM {ORIGIN}"})
    assert r.status == "failed" and "no permitida" in r.message
    assert sql("SELECT count(*) FROM origin_sales")[0][0] == 4


def all_lines():
    return ds_sql(f"SELECT document_id, line_no, line_kind, completed_at::text, "
                  f"local_date::text, product_code, net_amount::text FROM {SALE_LINES} "
                  f"ORDER BY 1, 2, 3")


def test_query_ending_in_comment_runs_bulk(origin, monkeypatch):
    query = QUERY + "  -- fin de la consulta"
    r = run(files={"queries/lines.sql": query})
    assert r.status == "succeeded", r.message
    assert r.rows["sale_lines"]["path"] == "copy"
    assert "fallback" not in r.rows["sale_lines"]
    snapshot = all_lines()
    assert len(snapshot) == 4

    def refuse(*args, **kwargs):
        raise extract.BulkUnsupported("FeatureNotSupported")

    monkeypatch.setattr(extract, "pg_copy", refuse)
    r = run(files={"queries/lines.sql": query}, kind="full")
    assert r.status == "succeeded", r.message
    assert r.rows["sale_lines"]["path"] == "rows"
    assert r.rows["sale_lines"]["fallback"] == "FeatureNotSupported"
    assert all_lines() == snapshot


def test_session_setting_refused_falls_back(origin, monkeypatch):
    monkeypatch.setattr(extract, "BULK_SESSION",
                        (*extract.BULK_SESSION, "SET bizview_no_such_param = 1"))
    r = run()
    assert r.status == "succeeded", r.message
    assert r.rows["sale_lines"]["path"] == "rows"
    assert r.rows["sale_lines"]["fallback"] == "UndefinedObject"
    assert len(lines()) == 4


def test_session_error_fails_without_fallback(origin, monkeypatch):
    monkeypatch.setattr(extract, "BULK_SESSION", (*extract.BULK_SESSION, "SELECT 1/0"))
    r = run()
    assert r.status == "failed"
    assert r.message.startswith("la extracción falló: ")
    assert "DivisionByZero" not in r.message
    assert r.rows["sale_lines"]["path"] == "copy"
    assert "fallback" not in r.rows["sale_lines"]
    assert ds_sql(f"SELECT to_regclass('{SALE_LINES}')")[0][0] is None


def patch_origin_copy(monkeypatch, copy):
    real_connect = extract._pg_connect

    class CopyCursor(psycopg.Cursor):
        def copy(self, statement, params=None, **kwargs):
            return copy(statement)

    def wrapped(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        conn.cursor_factory = CopyCursor
        return conn

    monkeypatch.setattr(extract, "_pg_connect", wrapped)


def test_copy_refused_at_start_falls_back(origin, monkeypatch):
    @contextmanager
    def refuse(statement):
        raise psycopg.errors.FeatureNotSupported("COPY no soportado")
        yield  # pragma: no cover

    patch_origin_copy(monkeypatch, refuse)
    r = run()
    assert r.status == "succeeded", r.message
    assert r.rows["sale_lines"]["path"] == "rows"
    assert r.rows["sale_lines"]["fallback"] == "FeatureNotSupported"
    assert len(lines()) == 4


def test_connection_lost_after_first_block_fails(origin, monkeypatch):
    assert run().status == "succeeded"
    before = count_lines()

    @contextmanager
    def broken(statement):
        def blocks():
            yield b"Z9\t1\tsale\t2026-09-28 10:00:00-04\t2026-09-28\tP1\t1\n"
            raise psycopg.OperationalError("server closed the connection unexpectedly")
            yield  # pragma: no cover

        yield blocks()

    patch_origin_copy(monkeypatch, broken)
    r = run()
    assert r.status == "failed"
    assert "la extracción falló: server closed the connection" in r.message
    assert r.rows["sale_lines"]["path"] == "copy"
    assert "fallback" not in r.rows["sale_lines"]
    assert count_lines() == before


def test_unsupported_after_first_block_fails(origin, monkeypatch):
    assert run().status == "succeeded"
    before = count_lines()

    @contextmanager
    def broken(statement):
        def blocks():
            yield b"Z9\t1\tsale\t2026-09-28 10:00:00-04\t2026-09-28\tP1\t1\n"
            raise psycopg.errors.FeatureNotSupported("COPY interrumpido")
            yield  # pragma: no cover

        yield blocks()

    patch_origin_copy(monkeypatch, broken)
    r = run()
    assert r.status == "failed"
    assert "la extracción falló" in r.message
    assert r.rows["sale_lines"]["path"] == "copy"
    assert "fallback" not in r.rows["sale_lines"]
    assert count_lines() == before


def test_empty_window_runs_bulk(origin):
    assert run().status == "succeeded"
    before = count_lines()
    definition, files = integration()
    definition["datasets"]["sale_lines"]["checks"] = []
    r = runner.run_integration(definition, files, version_id=None,
                               now=NOW + timedelta(days=30))
    assert r.status == "succeeded", r.message
    assert r.rows["sale_lines"]["extracted"] == 0
    assert r.rows["sale_lines"]["written"] == 0
    assert r.rows["sale_lines"]["path"] == "copy"
    assert "fallback" not in r.rows["sale_lines"]
    assert count_lines() == before
