"""Feature 005 / US2: integration runs. The "origin" is a PostgreSQL source pointing at the BI
database itself (read-only session) reading a fixture table in the test schema; REST runs use a
stub server. Datasets land in `<test schema>__ds_<id>`, dropped with the test schema."""
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db import get_engine, get_sessionmaker, lock_key
from app.engine import datasets, extract, runner
from app.models import AppUser
from app.security.netguard import Policy
from app.sources import service as sources
from app.sources.connectors import postgresql, rest
from tests.conftest import TEST_SCHEMA, sql
from tests.test_netguard import fake_dns
from tests.tls_helpers import StubServer

NOW = datetime(2026, 9, 29, 15, 0, tzinfo=UTC)          # 11:00 in Caracas (UTC-4)
TZ = "America/Caracas"
ORIGIN = f'"{TEST_SCHEMA}".origin_sales'


def ds_sql(query: str):
    with get_engine().begin() as c:
        r = c.execute(text(query))
        return r.all() if r.returns_rows else None


def ds_table(integration_id: str, table: str) -> str:
    return f'"{datasets.schema_name(integration_id)}"."{table}"'


@pytest.fixture
def pg_source(superuser):
    url = make_url(get_settings().database_url_bi)
    with get_sessionmaker().begin() as db:
        actor = db.get(AppUser, superuser.id)
        sources.create(db, actor, {
            "name": "Origen prueba", "kind": "postgresql",
            "settings": {"host": url.host, "port": url.port or 5432, "database": url.database,
                         "username": url.username, "sslmode": "prefer", "timeout_seconds": 15},
            "secrets": {"password": url.password}}, get_settings(), None)
    return "Origen prueba"


@pytest.fixture
def origin(pg_source):
    sql("DROP TABLE IF EXISTS origin_sales")
    sql("CREATE TABLE origin_sales (doc text, line int, kind text, completed_at timestamptz, "
        "amount numeric, product text)")
    rows = [("A1", 1, "sale", NOW - timedelta(days=1), "10.50", "P1"),
            ("A1", 2, "sale", NOW - timedelta(days=1), "4.25", "P2"),
            ("A2", 1, "return", NOW - timedelta(days=2), "3", "P1"),
            ("OLD", 1, "sale", NOW - timedelta(days=40), "100", "P1")]
    for r in rows:
        sql("INSERT INTO origin_sales VALUES (:d, :l, :k, :t, CAST(:a AS numeric), :p)",
            d=r[0], l=r[1], k=r[2], t=r[3], a=r[4], p=r[5])
    yield
    with get_engine().begin() as c:
        datasets.drop_integration(c.connection.driver_connection, "ventas-prueba")
        datasets.drop_integration(c.connection.driver_connection, "rest-prueba")
    sql("DROP TABLE IF EXISTS origin_sales")


QUERY = (f"SELECT doc AS document_id, line AS line_no, kind AS line_kind, completed_at, "
         f"(completed_at AT TIME ZONE 'America/Caracas')::date AS local_date, "
         f"product AS product_code, amount AS net_amount FROM {ORIGIN} "
         f"WHERE completed_at >= :window_start AND completed_at < :window_end")
TOTALS = (f"SELECT (completed_at AT TIME ZONE 'America/Caracas')::date AS local_date, "
          f"sum(amount) AS net_amount FROM {ORIGIN} "
          f"WHERE completed_at >= :window_start AND completed_at < :window_end GROUP BY 1")
PRODUCTS = f"SELECT DISTINCT product AS product_code FROM {ORIGIN}"


def integration(**over) -> tuple[dict, dict]:
    lines = {
        "primary_key": ["document_id", "line_no", "line_kind"],
        "date_column": "local_date",
        "columns": {
            "document_id": {"type": "text", "nullable": False},
            "line_no": {"type": "integer", "nullable": False},
            "line_kind": {"type": "text", "nullable": False, "enum": ["sale", "return"]},
            "completed_at": {"type": "timestamptz", "nullable": False},
            "local_date": {"type": "date", "nullable": False},
            "product_code": {"type": "text", "nullable": False},
            "net_amount": {"type": "numeric", "nullable": False, "min": 0},
        },
        "extract": {"query": "queries/lines.sql", "params": ["window_start", "window_end"]},
        "incremental": {"window_days": 7},
        "checks": [{"type": "row_count", "min": 1},
                   {"type": "reconcile", "query": "queries/totals.sql",
                    "compare": ["local_date", "net_amount"], "tolerance": 0.01}],
    }
    products = {"primary_key": ["product_code"],
                "columns": {"product_code": {"type": "text", "nullable": False}},
                "extract": {"query": "queries/products.sql"}, "incremental": {"mode": "full"}}
    definition = {"id": "ventas-prueba", "spec": "specs/integrations/001-ventas-prueba",
                  "source": "Origen prueba", "schedule": "*/30 * * * *", "timezone": TZ,
                  "time_limit_minutes": 5,
                  "datasets": {"sale_lines": lines, "products": products}}
    files = {"queries/lines.sql": QUERY, "queries/totals.sql": TOTALS,
             "queries/products.sql": PRODUCTS}
    definition.update(over.pop("definition", {}))
    files.update(over.pop("files", {}))
    return definition, files


def run(kind="incremental", now=NOW, **over):
    definition, files = integration(**over)
    return runner.run_integration(definition, files, version_id=None, kind=kind, now=now)


def lines():
    return ds_sql(f"SELECT document_id, line_no, line_kind, net_amount::text, local_date::text "
                  f"FROM {ds_table('ventas-prueba', 'sale_lines')} ORDER BY 1, 2, 3")


# --- SQL parameters ------------------------------------------------------------------------------

def test_placeholders_bound_not_spliced():
    q = extract.to_psycopg("select a::date, '%x', ':window_start' from t "
                           "where c >= :window_start and c < :window_end -- :window_end")
    assert q == ("select a::date, '%%x', ':window_start' from t "
                 "where c >= %(window_start)s and c < %(window_end)s -- :window_end")


def test_unsafe_query_refused_by_runner(origin):
    r = run(files={"queries/products.sql": f"DELETE FROM {ORIGIN}"})
    assert r.status == "failed" and "no permitida" in r.message
    assert sql("SELECT count(*) FROM origin_sales")[0][0] == 4


def test_window_is_local_midnight():
    from zoneinfo import ZoneInfo
    start, end = runner.window({"incremental": {"window_days": 7}}, full=False, now=NOW,
                               tz=ZoneInfo(TZ))
    assert start.isoformat() == "2026-09-22T00:00:00-04:00" and end == NOW


# --- PostgreSQL runs -----------------------------------------------------------------------------

def test_first_run_creates_tables_and_loads_everything(origin):
    r = run()
    assert r.status == "succeeded", r.message
    assert r.rows["sale_lines"] == {
        "extracted": 4,
        "written": 4,
        "full": True,
        "path": "copy",
    }
    assert r.rows["products"]["written"] == 2
    assert all(c["ok"] for c in r.checks)
    assert lines() == [
        ("A1", 1, "sale", "10.50", "2026-09-28"),
        ("A1", 2, "sale", "4.25", "2026-09-28"),
        ("A2", 1, "return", "3", "2026-09-27"),
        ("OLD", 1, "sale", "100", "2026-08-20"),
    ]
    run_ids = ds_sql(
        f"SELECT DISTINCT _run_id FROM {ds_table('ventas-prueba', 'sale_lines')}"
    )
    assert run_ids == [(r.id,)]


def test_incremental_rerun_is_idempotent_and_replaces_only_the_window(origin):
    assert run().status == "succeeded"
    sql("UPDATE origin_sales SET amount = 11 WHERE doc = 'A1' AND line = 1")
    sql("DELETE FROM origin_sales WHERE doc = 'A2'")
    sql("UPDATE origin_sales SET amount = 1 WHERE doc = 'OLD'")        # outside the window
    r = run()
    assert r.status == "succeeded", r.message
    assert r.rows["sale_lines"] == {
        "extracted": 2,
        "written": 2,
        "full": False,
        "path": "copy",
    }
    assert lines() == [
        ("A1", 1, "sale", "11", "2026-09-28"),
        ("A1", 2, "sale", "4.25", "2026-09-28"),
        ("OLD", 1, "sale", "100", "2026-08-20"),
    ]
    assert run().status == "succeeded" and len(lines()) == 3


def test_full_run_rereads_everything(origin):
    run()
    sql("UPDATE origin_sales SET amount = 1 WHERE doc = 'OLD'")
    assert run(kind="full").status == "succeeded"
    assert ("OLD", 1, "sale", "1", "2026-08-20") in lines()


def test_contract_mismatch_fails_and_keeps_previous_data(origin):
    run()
    before = lines()
    bad = QUERY.replace("amount AS net_amount", "amount AS net_amount, 1 AS extra")
    r = run(files={"queries/lines.sql": bad})
    assert r.status == "failed" and "no coinciden con el contrato" in r.message
    assert "extra" in r.message
    assert lines() == before


def test_type_mismatch_fails(origin):
    r = run(files={"queries/lines.sql": QUERY.replace("line AS line_no", "doc AS line_no")})
    assert r.status == "failed" and "contrato" in r.message


def test_contract_checks_block_the_load(origin):
    run()
    before = lines()
    sql("INSERT INTO origin_sales VALUES ('B1', 1, 'gift', :t, -5, 'P1')",
        t=NOW - timedelta(hours=1))
    r = run()
    assert r.status == "failed"
    failed = {c["detail"] for c in r.checks if not c["ok"]}
    assert any("gift" not in d and "fuera de" in d for d in failed)
    assert any("net_amount" in d and "<" in d for d in failed)
    assert lines() == before


def test_reconcile_detects_differences(origin):
    # The extraction drops returns but the origin totals include them.
    r = run(files={"queries/lines.sql": QUERY + " AND kind = 'sale'"})
    assert r.status == "failed"
    rec = next(c for c in r.checks if c["type"] == "reconcile")
    assert not rec["ok"] and "2026-09-27" in rec["detail"]


def test_disabled_source_is_skipped(origin):
    sql("UPDATE data_source SET enabled = false")
    r = run()
    assert r.status == "skipped" and "deshabilitada" in r.message


def test_unknown_source_fails(origin):
    r = run(definition={"source": "No existe"})
    assert r.status == "failed" and "no existe" in r.message


def test_overlapping_run_is_skipped(origin):
    with get_engine().connect() as c:
        pg = c.connection.driver_connection
        pg.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))",
                   (lock_key("integration", "ventas-prueba"),))
        try:
            r = run()
        finally:
            pg.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                       (lock_key("integration", "ventas-prueba"),))
            pg.commit()
    assert r.status == "skipped"


def test_stale_running_rows_are_closed(origin):
    sql("INSERT INTO integration_run (integration_id, kind, status) "
        "VALUES ('ventas-prueba', 'incremental', 'running')")
    assert run().status == "succeeded"
    assert sql("SELECT status, message FROM integration_run ORDER BY id")[0] == (
        "failed", "ejecución interrumpida")


def test_contract_evolution_adds_and_rebuilds(origin):
    run()
    definition, files = integration()
    definition["datasets"]["products"]["columns"]["label"] = {"type": "text"}
    files["queries/products.sql"] = PRODUCTS.replace("product_code", "product_code, "
                                                     "'x' || product AS label")
    r = runner.run_integration(definition, files, version_id=None, now=NOW)
    assert r.status == "succeeded", r.message
    assert ds_sql(f"SELECT label FROM {ds_table('ventas-prueba', 'products')} ORDER BY 1") == [
        ("xP1",), ("xP2",)]
    definition["datasets"]["products"]["columns"]["label"] = {"type": "integer"}
    files["queries/products.sql"] = PRODUCTS.replace("product_code", "product_code, 1 AS label")
    r = runner.run_integration(definition, files, version_id=None, now=NOW)
    assert r.status == "succeeded", r.message
    assert r.rows["products"]["full"] is True
    col = ds_sql("SELECT data_type FROM information_schema.columns WHERE table_schema = "
                 f"'{datasets.schema_name('ventas-prueba')}' AND table_name = 'products' "
                 "AND column_name = 'label'")
    assert col == [("integer",)]


def test_messages_never_contain_the_password(origin):
    password = make_url(get_settings().database_url_bi).password
    sql("UPDATE data_source SET settings = jsonb_set(settings, '{database}', '\"no_such_db\"')")
    r = run()
    assert r.status == "failed"
    assert password not in (r.message or "")


# --- REST ----------------------------------------------------------------------------------------

@pytest.fixture
def rest_origin(monkeypatch, superuser, origin):
    pages = {1: [{"id": 1, "total": "5.5", "when": "2026-09-28", "tags": ["a"]},
                 {"id": 2, "total": 7, "when": "2026-09-28", "tags": []}],
             2: [{"id": 3, "total": 1.25, "when": "2026-09-27", "tags": None}]}

    def handler(h):
        from urllib.parse import parse_qs, urlsplit
        q = parse_qs(urlsplit(h.path).query)
        page = int(q.get("page", ["1"])[0])
        body = json.dumps({"data": {"items": pages.get(page, [])}}).encode()
        h.send_response(200 if h.headers.get("Authorization") == "Bearer tok" else 401)
        h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)

    server = StubServer(handler)
    loop = Policy(allow_loopback_for_tests=True)
    for mod in (extract, rest, postgresql):
        monkeypatch.setattr(mod, "policy_from_settings", lambda s: loop)
    with get_sessionmaker().begin() as db:   # stub.test is unresolvable here: accepted
        sources.create(db, db.get(AppUser, superuser.id), {
            "name": "API prueba", "kind": "rest",
            "settings": {"base_url": f"http://stub.test:{server.port}/v1", "auth": "bearer",
                         "headers": [], "timeout_seconds": 5},
            "secrets": {"token": "tok"}}, get_settings(), None)
    fake_dns(monkeypatch, {"stub.test": ["127.0.0.1"]})
    yield server
    server.close()


def test_rest_paginated_run(rest_origin):
    definition = {"id": "rest-prueba", "spec": "specs/integrations/002-rest-prueba",
                  "source": "API prueba", "schedule": "0 * * * *", "timezone": TZ,
                  "datasets": {"orders": {
                      "primary_key": ["id"], "date_column": "day",
                      "columns": {"id": {"type": "bigint", "nullable": False},
                                  "total": {"type": "numeric"}, "day": {"type": "date"},
                                  "tags": {"type": "text"}},
                      "extract": {"request": "requests/orders.yaml"},
                      "incremental": {"window_days": 3}}}}
    request = {"method": "GET", "path": "/orders",
               "params": {"from": "{window_start_date}", "to": "{window_end_date}"},
               "pagination": {"type": "page", "param": "page", "size_param": "per_page",
                              "size": 2},
               "records": "$.data.items",
               "fields": {"id": "id", "total": "total", "day": "when", "tags": "tags"}}
    import yaml
    r = runner.run_integration(definition, {"requests/orders.yaml": yaml.safe_dump(request)},
                               version_id=None, now=NOW)
    assert r.status == "succeeded", r.message
    assert r.rows["orders"]["written"] == 3
    assert r.rows["orders"]["path"] == "rows"
    assert "fallback" not in r.rows["orders"]
    got = ds_sql(f"SELECT id, total::text, day::text, tags FROM "
                 f"{ds_table('rest-prueba', 'orders')} ORDER BY id")
    assert got == [(1, "5.5", "2026-09-28", '["a"]'), (2, "7", "2026-09-28", "[]"),
                   (3, "1.25", "2026-09-27", None)]
    first = rest_origin.requests[0]["path"]
    assert "from=1900-01-01" in first and "to=2026-09-29" in first and "per_page=2" in first
    assert [q["path"].split("page=")[-1][:1] for q in rest_origin.requests] == ["1", "2"]


def test_timezone_cannot_smuggle_session_settings(origin):
    r = run(definition={"timezone": "UTC -c default_transaction_read_only=off"})
    assert r.status == "failed" and "zona horaria" in r.message
    with pytest.raises(extract.ExtractError):
        extract.check_timezone("America/Caracas -c x=y")
    assert extract.check_timezone("America/Argentina/Buenos_Aires")


def test_rest_credentials_never_leave_the_source_host(rest_origin):
    import yaml
    definition = {"id": "rest-prueba", "spec": "specs/integrations/002-rest-prueba",
                  "source": "API prueba", "schedule": "0 * * * *", "timezone": TZ,
                  "datasets": {"orders": {
                      "primary_key": ["id"], "columns": {"id": {"type": "bigint"}},
                      "extract": {"request": "requests/orders.yaml"},
                      "incremental": {"mode": "full"}}}}
    def with_path(path):
        request = {"path": path, "records": "$.data.items", "fields": {"id": "id"}}
        return runner.run_integration(definition,
                                      {"requests/orders.yaml": yaml.safe_dump(request)},
                                      version_id=None, now=NOW)

    r = with_path("https://evil.example/steal")
    assert r.status == "failed" and "otro servidor" in r.message
    assert rest_origin.requests == []
    # A network-path reference is treated as a path on the source's own host.
    with_path("//evil.example/steal")
    assert [q["path"].split("?")[0] for q in rest_origin.requests] == ["/v1/evil.example/steal"]


def test_run_message_stored_with_key():
    r = run(definition={"source": "Fuente inexistente"})
    assert r.status == "failed"
    assert r.message == "la fuente 'Fuente inexistente' no existe"
    assert r.message_key == "run.source_missing"
    assert r.message_params == {"source": "Fuente inexistente"}


def test_runs_render_in_viewer_language(superuser):
    from app.models import IntegrationRun
    from tests.conftest import signed_in

    with get_sessionmaker().begin() as db:
        db.add_all([
            IntegrationRun(
                integration_id="i18n-runs",
                version_id=None,
                kind="incremental",
                status="failed",
                message="la fuente 'X' no existe",
                message_key="run.source_missing",
                message_params={"source": "X"},
                checks=[{"dataset": "d", "type": "row_count", "ok": True, "detail": "3 filas",
                         "key": "run.check.rows", "params": {"n": 3}}],
                requested_by=superuser.id,
                finished_at=datetime.now(UTC),
            ),
            IntegrationRun(
                integration_id="i18n-runs",
                version_id=None,
                kind="incremental",
                status="failed",
                message="texto antiguo",
                message_key=None,
                message_params=None,
                checks=[{"dataset": "d", "type": "row_count", "ok": True, "detail": "2 filas"}],
                requested_by=superuser.id,
                finished_at=datetime.now(UTC),
            ),
        ])

    c = signed_in("root@example.com")
    items = c.get("/api/integrations/i18n-runs/runs",
                  headers={"Accept-Language": "en"}).json()["items"]

    assert items[0]["message"] == "texto antiguo"
    assert items[0]["checks"][0]["detail"] == "2 filas"
    assert items[1]["message"] == "source 'X' does not exist"
    assert items[1]["checks"][0]["detail"] == "3 rows"
