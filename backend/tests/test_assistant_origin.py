"""Feature 017 (US2): origin tools of the assistant — personal-data flags, profile_source and
check_query return structure and aggregates only, never row values."""
import hashlib
import json
import re
import threading
from types import SimpleNamespace

import httpx
import psycopg
import pytest
import yaml
from sqlalchemy import func, select, text

from app.assistant import origin as origin_tools
from app.assistant import tools
from app.assistant.tools import run_tool
from app.config import get_settings
from app.db import get_engine
from app.engine import extract
from app.models import AppUser, AuditEvent
from app.projects.workview import for_session
from app.sources.service import by_name
from tests.conftest import (
    TEST_SCHEMA,
    project_view,
    signed_in,
    sql,
    v2_files,
    write_project,
)
from tests.test_assistant_preview import _draft, _session
from tests.test_runner import ORIGIN
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_runner import rest_origin as rest_origin  # fixture
from tests.test_vibe_reporting import apply, lock
from tests.test_vibe_reporting import workspace as workspace  # fixture
from tests.workspace_fixture import queries

# 017 origin tools through plain-mode calls; the 021 command guard has its own tests.
pytestmark = pytest.mark.usefixtures("without_command_guard")


def _make_session(db, superuser):
    """The WorkView of a conversation on a new project (020)."""
    return project_view(db, superuser.id)


def _set_files(session, files, superuser):
    """020: the draft is the project folder (legacy spec folders become v2)."""
    write_project(session.project.id, v2_files(files), superuser.id)
    session.refresh()


def _run(db, superuser, session, name, args):
    return run_tool(db, db.get(AppUser, superuser.id), session, name, args, get_settings())


def _audit_count(db):
    return db.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.kind == "source_described")
    )


@pytest.mark.parametrize(
    ("name", "data_type", "expected"),
    [
        ("email", "text", "email"),
        ("customerEmail", None, "email"),
        ("correo_cliente", "text", "email"),
        ("telefono", "text", "phone"),
        ("celular", None, "phone"),
        ("cédula", None, "document_id"),
        ("rif", None, "document_id"),
        ("chat_id", "bigint", "chat_id"),
        ("telegram_user", None, "chat_id"),
        ("iban", None, "payment"),
        ("numero_tarjeta", None, "payment"),
        ("name", None, "name"),
        ("nombre_cliente", None, "name"),
        ("firstName", None, "name"),
        ("apellido", None, "name"),
        ("payload", "jsonb", "payload"),
        ("raw_data", "json", "payload"),
        ("data", "text", None),
        ("product_name", "text", None),
        ("nombre_producto", "text", None),
        ("cliente_id", "text", None),
        ("doc", "text", None),
        ("amount", "numeric", None),
        ("fecha_nacimiento", "date", "birth_date"),
        ("birthDate", None, "birth_date"),
        ("dob", None, "birth_date"),
        ("fechanacimiento", None, "birth_date"),
        ("cumpleaños", None, "birth_date"),
        ("born", "date", "birth_date"),
        ("fecha_creacion", "date", None),
    ],
)
def test_personal_kind_heuristics(name, data_type, expected):
    assert origin_tools.personal_kind(name, data_type) == expected


def test_describe_flags_personal_columns_and_caches(db, superuser, pg_source, monkeypatch):
    session = _make_session(db, superuser)
    calls = []

    def fake(source_kind, settings, secrets, app, path):
        calls.append(path)
        return {
            "kind": "postgresql",
            "truncated": False,
            "tables": [{
                "schema": "ventas",
                "name": "clientes",
                "kind": "table",
                "estimated_rows": 3,
                "primary_key": ["id"],
                "columns": [
                    {"name": "id", "type": "integer", "nullable": False},
                    {"name": "email", "type": "text", "nullable": True},
                    {"name": "nombre_cliente", "type": "text", "nullable": True},
                    {"name": "data", "type": "jsonb", "nullable": True},
                    {"name": "product_name", "type": "text", "nullable": True},
                ],
            }],
        }

    monkeypatch.setattr(tools, "describe", fake)
    result, summary = _run(db, superuser, session, "describe_source", {"name": "Origen prueba"})
    table = result["tables"][0]
    assert table["personal"] == [
        {"column": "email", "kind": "email"},
        {"column": "nombre_cliente", "kind": "name"},
        {"column": "data", "kind": "payload"},
    ]
    personal = session.working_state["personal"]["origen prueba"]
    assert personal == {"email": "email", "nombre_cliente": "name", "data": "payload"}
    assert "personales" in session.working_state["inspected"]["origen prueba"]["ventas.clientes"]
    assert _audit_count(db) == 1

    result, summary = _run(db, superuser, session, "describe_source", {"name": "Origen prueba"})
    assert result["cached"] is True
    assert summary.startswith("Usó la estructura ya consultada")
    assert len(calls) == 1
    assert _audit_count(db) == 1

    result, _ = _run(db, superuser, session, "describe_source",
                     {"name": "Origen prueba", "refresh": True})
    assert "cached" not in result
    assert len(calls) == 2
    assert _audit_count(db) == 2

    result, _ = _run(db, superuser, session, "describe_source",
                     {"name": "Origen prueba", "path": "x"})
    assert "cached" not in result
    assert len(calls) == 3

    with pytest.raises(tools.ToolError):
        _run(db, superuser, session, "describe_source",
             {"name": "Origen prueba", "refresh": "si"})


def test_profile_source_returns_only_aggregates(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    sql("INSERT INTO origin_sales VALUES ('ZETA-UNICO-4242', 9, 'sale', "
        "'2011-11-11 11:11:11+00', CAST('987654.321' AS numeric), 'ZETA-PROD-4242')")
    result, _ = _run(db, superuser, session, "profile_source",
                     {"name": "Origen prueba", "table": f"{TEST_SCHEMA}.origin_sales"})
    assert result["row_count"] == 5
    assert [c["name"] for c in result["columns"]] == [
        "doc", "line", "kind", "completed_at", "amount", "product"
    ]
    by_name = {c["name"]: c for c in result["columns"]}
    assert by_name["doc"]["distinct"] == 4
    assert by_name["doc"]["null_ratio"] == 0.0
    assert by_name["completed_at"]["min"].startswith("2011-11-11")
    assert "max" in by_name["completed_at"]
    for col in ("amount", "doc", "product"):
        assert "min" not in by_name[col]
        assert "max" not in by_name[col]
    dumped = json.dumps(result, ensure_ascii=False)
    for forbidden in ["ZETA", "987654", "10.5", "4.25", "P1", "P2"]:
        assert forbidden not in dumped
    audit = db.scalar(
        select(AuditEvent).where(AuditEvent.detail["tool"].astext == "profile_source")
    )
    assert audit is not None
    key = f"{TEST_SCHEMA}.origin_sales"
    assert "perfil: 5 filas" in session.working_state["inspected"]["origen prueba"][key]


def test_profile_source_json_columns_and_personal_values(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    sql("""
        CREATE TABLE origin_people (
            id int, email text, payload jsonb, born date,
            fecha_nacimiento date, creado date
        )
    """)
    try:
        sql("""
            INSERT INTO origin_people VALUES
            (1, 'ana.secreta@example.com', '{"k": "VALOR-OCULTO"}', '1990-05-05',
             '1970-03-03', '2020-01-01')
        """)
        sql("""
            INSERT INTO origin_people VALUES
            (2, NULL, NULL, '1985-01-02', '1971-04-04', '2020-02-02')
        """)
        result, _ = _run(db, superuser, session, "profile_source",
                         {"name": "Origen prueba", "table": f"{TEST_SCHEMA}.origin_people"})
        by_name = {c["name"]: c for c in result["columns"]}
        assert by_name["email"]["null_ratio"] == 0.5
        assert by_name["email"]["distinct"] == 1
        assert by_name["email"]["personal"] == "email"
        assert by_name["payload"]["distinct"] is None
        assert by_name["payload"]["personal"] == "payload"
        assert by_name["born"]["personal"] == "birth_date"
        assert "min" not in by_name["born"]
        assert "max" not in by_name["born"]
        assert by_name["born"]["null_ratio"] == 0.0
        assert by_name["born"]["distinct"] == 2
        assert by_name["fecha_nacimiento"]["personal"] == "birth_date"
        assert "min" not in by_name["fecha_nacimiento"]
        assert "max" not in by_name["fecha_nacimiento"]
        assert by_name["fecha_nacimiento"]["null_ratio"] == 0.0
        assert by_name["fecha_nacimiento"]["distinct"] == 2
        assert by_name["creado"]["min"] == "2020-01-01"
        assert by_name["creado"]["max"] == "2020-02-02"
        assert "personal" not in by_name["creado"]
        dumped = json.dumps(result, ensure_ascii=False)
        assert "ana.secreta" not in dumped
        assert "VALOR-OCULTO" not in dumped
        assert "1985-01-02" not in dumped
        assert "1990-05-05" not in dumped
        assert "1970-03-03" not in dumped
        assert "1971-04-04" not in dumped
        stored = (session.working_state or {}).get("personal", {}).get("origen prueba", {})
        assert stored.get("email") == "email"
        assert stored.get("born") == "birth_date"
        assert stored.get("fecha_nacimiento") == "birth_date"
        assert stored.get("payload") == "payload"
    finally:
        sql("DROP TABLE IF EXISTS origin_people")


def test_profile_source_unknown_or_injected_table(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    result, _ = _run(db, superuser, session, "profile_source",
                     {"name": "Origen prueba", "table": f"{TEST_SCHEMA}.no_existe"})
    assert result["error"].startswith("La tabla no existe")
    result, _ = _run(db, superuser, session, "profile_source",
                     {"name": "Origen prueba",
                      "table": f"{TEST_SCHEMA}.origin_sales; DROP TABLE origin_sales"})
    assert "error" in result
    assert sql("SELECT count(*) FROM origin_sales")[0][0] == 4
    result, _ = _run(db, superuser, session, "profile_source",
                     {"name": "No existe", "table": "x"})
    assert result == {"error": "No existe una fuente con ese nombre."}
    with pytest.raises(tools.ToolError):
        _run(db, superuser, session, "profile_source", {"name": "Origen prueba"})


def test_profile_source_timeout(db, superuser, origin, pg_source, monkeypatch):
    session = _make_session(db, superuser)
    monkeypatch.setattr(get_settings(), "ai_tool_timeout_seconds", 1.0)
    locked, release = threading.Event(), threading.Event()

    def locker():
        with get_engine().connect() as lc:
            lc.execute(text(f'LOCK TABLE "{TEST_SCHEMA}".origin_sales IN ACCESS EXCLUSIVE MODE'))
            locked.set()
            release.wait(30)
            lc.rollback()

    thread = threading.Thread(target=locker, daemon=True)
    thread.start()
    try:
        assert locked.wait(10)
        result, _ = _run(db, superuser, session, "profile_source",
                         {"name": "Origen prueba", "table": f"{TEST_SCHEMA}.origin_sales"})
        assert result == {"error": "tiempo agotado; reduce la consulta"}
    finally:
        release.set()
        thread.join(10)


def test_profile_source_rest_row_count_only(db, superuser, rest_origin):
    session = _make_session(db, superuser)
    result, _ = _run(db, superuser, session, "profile_source",
                     {"name": "API prueba", "table": "orders"})
    assert result["row_count"] is None
    assert "note" in result
    dumped = json.dumps(result, ensure_ascii=False)
    assert "5.5" not in dumped
    assert "2026-09-28" not in dumped
    request = rest_origin.requests[0]
    assert request["path"].startswith("/v1/orders")
    prefer = next(v for k, v in request["headers"].items() if k.lower() == "prefer")
    assert "count=exact" in prefer


def test_check_query_draft_file_columns(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    files = _draft()
    _set_files(session, files, superuser)
    db.flush()
    path = "integrations/ventas-dos/queries/lines.sql"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "path": path})
    assert result["ok"] is True
    assert result["dataset"] == "sale_lines"
    assert [c["name"] for c in result["columns"]] == [
        "document_id", "line_no", "line_kind", "completed_at", "local_date",
        "product_code", "net_amount"
    ]
    types = {c["name"]: c["type"] for c in result["columns"]}
    assert types["line_no"] == "integer"
    assert types["local_date"] == "date"
    assert types["completed_at"] == "timestamp with time zone"
    assert result["missing"] == []
    assert result["extra"] == []
    assert session.query_checks[path]["sha256"] == hashlib.sha256(
        files[path].encode()
    ).hexdigest()
    assert session.query_checks[path]["ok"] is True
    assert session.stats["query_checks"] == 1
    assert result["readiness"]["ready"] is False
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba",
                      "path": "integrations/ventas-dos/queries/totals.sql"})
    assert result["ok"] is True
    assert result["dataset"] is None


def test_check_query_reports_contract_mismatch(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    files = _draft()
    path = "integrations/ventas-dos/queries/lines.sql"
    files[path] = files[path].replace(", amount AS net_amount", "")
    _set_files(session, files, superuser)
    db.flush()
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "path": path})
    assert result["ok"] is False
    assert result["missing"] == ["net_amount"]
    assert session.query_checks[path]["ok"] is False


def test_check_query_rejects_unsafe_sql(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    unsafe_queries = (
        f"DELETE FROM {ORIGIN}",
        "SELECT pg_sleep(5)",
        f"SELECT 1; DROP TABLE {ORIGIN}",
    )
    for unsafe in unsafe_queries:
        result, _ = _run(db, superuser, session, "check_query",
                         {"source": "Origen prueba", "sql": unsafe})
        assert result["ok"] is False
        assert result["error"].startswith("consulta no permitida")
        assert sql("SELECT count(*) FROM origin_sales")[0][0] == 4
        assert not session.query_checks


def test_check_query_redacts_database_errors(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "sql": "SELECT 'ZETA-SECRETO'::int AS x"})
    assert result["ok"] is False
    assert "ZETA-SECRETO" not in result["error"]
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba",
                      "sql": f"SELECT no_existe_col FROM {ORIGIN}"})
    assert result["ok"] is False
    assert "no_existe_col" not in result["error"]
    assert "«…»" in result["error"]


def test_check_query_request_shape_only(db, superuser, rest_origin):
    session = _make_session(db, superuser)
    request_yaml = yaml.safe_dump({
        "method": "GET",
        "path": "/orders",
        "params": {"from": "{window_start_date}"},
        "pagination": {"type": "page", "param": "page", "size_param": "per_page", "size": 2},
        "records": "$.data.items",
        "fields": {"id": "id", "total": "total", "day": "when", "tags": "tags",
                   "ghost": "nope"},
    })
    integration_yaml = yaml.safe_dump({
        "id": "rest-dos",
        "spec": "specs/integrations/003-rest-dos",
        "source": "API prueba",
        "schedule": "0 * * * *",
        "datasets": {
            "orders": {
                "primary_key": ["id"],
                "columns": {"id": {"type": "bigint"}, "total": {"type": "numeric"},
                            "day": {"type": "date"}, "tags": {"type": "text"}},
                "extract": {"request": "requests/orders.yaml"},
                "incremental": {"window_days": 3},
                "checks": [{"type": "row_count", "min": 0}],
            }
        },
    })
    files = {
        "integrations/rest-dos/integration.yaml": integration_yaml,
        "integrations/rest-dos/requests/orders.yaml": request_yaml,
    }
    _set_files(session, files, superuser)
    db.flush()
    path = "integrations/rest-dos/requests/orders.yaml"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "API prueba", "path": path})
    assert result["ok"] is False
    assert result["records"] == 1
    by_column = {f["column"]: f for f in result["fields"]}
    assert by_column["id"]["json_type"] == "integer"
    assert by_column["total"]["json_type"] == "string"
    assert by_column["day"]["json_type"] == "string"
    assert by_column["tags"]["json_type"] == "array"
    assert by_column["ghost"]["found"] is False
    assert result["missing"] == ["ghost"]
    assert result["missing_columns"] == []
    dumped = json.dumps(result, ensure_ascii=False)
    assert "5.5" not in dumped
    assert "2026-09-28" not in dumped
    assert len(rest_origin.requests) == 1
    request = rest_origin.requests[0]
    assert "per_page=1" in request["path"]
    assert "page=1" in request["path"]

    request_yaml = yaml.safe_dump({
        "method": "GET",
        "path": "/orders",
        "params": {"from": "{window_start_date}"},
        "pagination": {"type": "page", "param": "page", "size_param": "per_page", "size": 2},
        "records": "$.data.items",
        "fields": {"id": "id", "total": "total", "day": "when", "tags": "tags"},
    })
    files[path] = request_yaml
    _set_files(session, files, superuser)
    db.flush()
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "API prueba", "path": path})
    assert result["ok"] is True


def test_check_query_argument_errors(db, superuser, pg_source):
    session = _make_session(db, superuser)
    with pytest.raises(tools.ToolError):
        _run(db, superuser, session, "check_query",
             {"source": "Origen prueba", "path": "p", "sql": "s"})
    with pytest.raises(tools.ToolError):
        _run(db, superuser, session, "check_query", {"source": "Origen prueba"})
    with pytest.raises(tools.ToolError, match=re.escape("integrations/<id>/queries/*.sql")):
        _run(db, superuser, session, "check_query",
             {"source": "Origen prueba", "path": "integrations/x/queries/a.sql"})
    _set_files(session, _draft(), superuser)
    db.flush()
    with pytest.raises(tools.ToolError):
        _run(db, superuser, session, "check_query",
             {"source": "Origen prueba", "path": "reports/ventas2/report.yaml"})
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "No existe",
                      "path": "integrations/ventas-dos/queries/lines.sql"})
    assert result == {"error": "No existe una fuente con ese nombre."}


def test_recheck_draft(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    files = _draft()
    _set_files(session, files, superuser)
    db.flush()
    assert origin_tools.recheck_draft(db, session, get_settings()) == []
    assert len(session.query_checks) == 3

    broken = dict(files)
    path = "integrations/ventas-dos/queries/lines.sql"
    broken[path] = broken[path].replace(", amount AS net_amount", "")
    session2 = _make_session(db, superuser)
    _set_files(session2, broken, superuser)
    db.flush()
    failures = origin_tools.recheck_draft(db, session2, get_settings())
    assert len(failures) == 1
    assert failures[0]["path"] == path
    assert "net_amount" in failures[0]["error"]


def test_check_query_modulo_and_like_without_window(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba",
                      "sql": f"SELECT line % 2 AS paridad FROM {ORIGIN}"})
    assert result["ok"] is True
    assert [c["name"] for c in result["columns"]] == ["paridad"]
    assert result["missing"] == []
    assert result["extra"] == []

    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba",
                      "sql": f"SELECT count(*) AS n FROM {ORIGIN} WHERE kind LIKE 'sa%'"})
    assert result["ok"] is True
    assert result["extra"] == []


def test_check_query_flags_personal_columns_read_by_the_query(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    sql("CREATE TABLE origin_contacts (id int, correo text)")
    try:
        sql("INSERT INTO origin_contacts VALUES (1, 'ana.secreta@example.com')")
        result, _ = _run(db, superuser, session, "check_query",
                         {"source": "Origen prueba",
                          "sql": (f'SELECT correo AS contacto FROM "{TEST_SCHEMA}"'
                                  '.origin_contacts')})
        assert result["ok"] is True
        assert result["personal"] == [{"column": "correo", "kind": "email"}]
        stored = (session.working_state or {}).get("personal", {}).get("origen prueba", {})
        assert stored.get("correo") == "email"
        assert "ana.secreta" not in json.dumps(result, ensure_ascii=False)
    finally:
        sql("DROP TABLE IF EXISTS origin_contacts")


def test_check_query_post_request_is_skipped(db, superuser, rest_origin):
    session = _make_session(db, superuser)
    request_yaml = yaml.safe_dump({
        "method": "POST",
        "path": "/orders",
        "params": {"from": "{window_start_date}"},
        "pagination": {"type": "page", "param": "page", "size_param": "per_page", "size": 2},
        "records": "$.data.items",
        "fields": {"id": "id", "total": "total", "day": "when", "tags": "tags"},
        "payload": {"x": 1},
    })
    integration_yaml = yaml.safe_dump({
        "id": "rest-tres",
        "spec": "specs/integrations/004-rest-tres",
        "source": "API prueba",
        "schedule": "0 * * * *",
        "datasets": {
            "orders": {
                "primary_key": ["id"],
                "columns": {"id": {"type": "bigint"}, "total": {"type": "numeric"},
                            "day": {"type": "date"}, "tags": {"type": "text"}},
                "extract": {"request": "requests/orders.yaml"},
                "incremental": {"window_days": 3},
                "checks": [{"type": "row_count", "min": 0}],
            }
        },
    })
    files = {
        "integrations/rest-tres/integration.yaml": integration_yaml,
        "integrations/rest-tres/requests/orders.yaml": request_yaml,
    }
    _set_files(session, files, superuser)
    db.flush()
    path = "integrations/rest-tres/requests/orders.yaml"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "API prueba", "path": path})
    assert result["ok"] is True
    assert "skipped" in result
    assert "note" in result
    assert rest_origin.requests == []
    stored = (session.query_checks or {}).get(path)
    assert stored is not None
    assert stored["ok"] is True
    assert stored.get("skipped") == result["skipped"]
    assert origin_tools.recheck_draft(db, session, get_settings()) == []


def test_check_request_soap_is_skipped():
    result = origin_tools._run_check_request(
        SimpleNamespace(kind="soap", settings={}), {}, get_settings(), "operation: X\n", None
    )
    assert result["ok"] is True
    assert "SOAP" in result["skipped"]
    assert result["error"] is None


def test_describe_rest_shape_flags_personal(db, superuser, pg_source, monkeypatch):
    session = _make_session(db, superuser)

    def fake(source_kind, settings, secrets, app, path):
        return {
            "kind": "rest",
            "path": "/clientes",
            "shape": [{
                "id": "integer",
                "contacto": {"email": "string", "telefono": "string"},
                "total": "number",
            }],
        }

    monkeypatch.setattr(tools, "describe", fake)
    result, _ = _run(db, superuser, session, "describe_source",
                     {"name": "Origen prueba", "path": "clientes"})
    assert result["personal"] == [
        {"column": "contacto.email", "kind": "email"},
        {"column": "contacto.telefono", "kind": "phone"},
    ]
    stored = (session.working_state or {}).get("personal", {}).get("origen prueba", {})
    assert stored.get("email") == "email"
    assert stored.get("telefono") == "phone"


def test_check_query_reconcile_query_has_no_contract(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    _set_files(session, _draft(), superuser)
    db.flush()
    path = "integrations/ventas-dos/queries/totals.sql"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "path": path})
    assert result["ok"] is True
    assert result["dataset"] is None
    assert result["missing"] == []
    assert result["extra"] == []


def _rest_draft() -> dict[str, str]:
    request_yaml = yaml.safe_dump({
        "method": "GET",
        "path": "/orders",
        "params": {"from": "{window_start_date}"},
        "pagination": {"type": "page", "param": "page", "size_param": "per_page",
                       "size": 2},
        "records": "$.data.items",
        "fields": {"id": "id", "total": "total", "day": "when", "tags": "tags"},
    })
    integration_yaml = yaml.safe_dump({
        "id": "rest-dos",
        "spec": "specs/integrations/003-rest-dos",
        "source": "API prueba",
        "schedule": "0 * * * *",
        "datasets": {"orders": {
            "primary_key": ["id"],
            "columns": {"id": {"type": "bigint"}, "total": {"type": "numeric"},
                        "day": {"type": "date"}, "tags": {"type": "text"}},
            "extract": {"request": "requests/orders.yaml"},
            "incremental": {"window_days": 3},
            "checks": [{"type": "row_count", "min": 0}],
        }},
    })
    return {
        "integrations/rest-dos/integration.yaml": integration_yaml,
        "integrations/rest-dos/requests/orders.yaml": request_yaml,
    }


def _timeout_client(exc_type, recorded: dict):
    def fake_guarded_client(policy=None, timeout=None, verify=True, **kwargs):
        recorded["timeout"] = timeout

        def handler(request):
            raise exc_type("timed out", request=request)

        return httpx.Client(transport=httpx.MockTransport(handler))

    return fake_guarded_client


def test_check_query_postgres_statement_timeout(db, superuser, origin, pg_source,
                                                monkeypatch):
    session = _make_session(db, superuser)
    monkeypatch.setattr(get_settings(), "ai_tool_timeout_seconds", 1.0)
    locked, release = threading.Event(), threading.Event()

    def locker():
        with get_engine().connect() as lc:
            lc.execute(text(
                f'LOCK TABLE "{TEST_SCHEMA}".origin_sales IN ACCESS EXCLUSIVE MODE'))
            locked.set()
            release.wait(30)
            lc.rollback()

    thread = threading.Thread(target=locker, daemon=True)
    thread.start()
    try:
        assert locked.wait(10)
        result, _ = _run(db, superuser, session, "check_query",
                         {"source": "Origen prueba",
                          "sql": f"SELECT doc FROM {ORIGIN}"})
        assert result["ok"] is False
        assert result["error"] == origin_tools.TIMEOUT_TEXT
    finally:
        release.set()
        thread.join(10)


def test_check_query_postgres_connect_timeout_bounded(db, superuser, origin, pg_source,
                                                      monkeypatch):
    session = _make_session(db, superuser)
    monkeypatch.setattr(get_settings(), "ai_tool_timeout_seconds", 3.0)
    recorded = {}
    real_connect = psycopg.connect

    def fake_connect(*args, **kwargs):
        if kwargs.get("application_name") == "bizview-engine":
            recorded.update(kwargs)
            raise psycopg.errors.ConnectionTimeout("connection timeout expired")
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba",
                      "sql": f"SELECT doc FROM {ORIGIN}"})
    assert result["ok"] is False
    assert result["error"] == origin_tools.TIMEOUT_TEXT
    assert recorded["connect_timeout"] == 3


def test_check_query_rest_timeout(db, superuser, rest_origin, monkeypatch):
    session = _make_session(db, superuser)
    monkeypatch.setattr(get_settings(), "ai_tool_timeout_seconds", 4.0)
    files = _rest_draft()
    _set_files(session, files, superuser)
    db.flush()
    recorded = {}
    monkeypatch.setattr(extract, "guarded_client",
                        _timeout_client(httpx.ReadTimeout, recorded))
    path = "integrations/rest-dos/requests/orders.yaml"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "API prueba", "path": path})
    assert result["ok"] is False
    assert result["error"] == origin_tools.TIMEOUT_TEXT
    assert recorded["timeout"] <= 4.0
    result, _ = _run(db, superuser, session, "profile_source",
                     {"name": "API prueba", "table": "orders"})
    assert result == {"error": origin_tools.TIMEOUT_TEXT}


def test_check_request_supabase_timeout(monkeypatch):
    source = SimpleNamespace(kind="supabase",
                             settings={"url": "https://zeta.supabase.co",
                                       "timeout_seconds": 5})
    secrets = {"service_key": "k"}
    recorded = {}
    monkeypatch.setattr(extract, "guarded_client",
                        _timeout_client(httpx.ConnectTimeout, recorded))
    monkeypatch.setattr(get_settings(), "ai_tool_timeout_seconds", 4.0)
    text = yaml.safe_dump({"method": "GET", "path": "x",
                           "records": "$", "fields": {"id": "id"}})
    result = origin_tools._run_check_request(source, secrets, get_settings(), text, None)
    assert result["ok"] is False
    assert result["error"] == origin_tools.TIMEOUT_TEXT
    assert recorded["timeout"] <= 4.0


def test_query_only_draft_resolves_active_integration(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    session = _make_session(db, superuser)
    lines = queries(ORIGIN)["lines.sql"]
    full_path = "integrations/ventas-prueba/queries/lines.sql"
    _set_files(session, {full_path: lines}, superuser)
    db.flush()
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "path": full_path})
    assert result["ok"] is True
    assert result["dataset"] == "sale_lines"
    assert result["missing"] == []
    failures = origin_tools.recheck_draft(db, session, get_settings())
    assert failures == []

    session2 = _make_session(db, superuser)
    broken = lines.replace(", amount AS net_amount", "")
    _set_files(session2, {full_path: broken}, superuser)
    db.flush()
    result2, _ = _run(db, superuser, session2, "check_query",
                      {"source": "Origen prueba", "path": full_path})
    assert result2["ok"] is False
    assert "net_amount" in result2["missing"]
    failures2 = origin_tools.recheck_draft(db, session2, get_settings())
    assert len(failures2) == 1
    assert "net_amount" in failures2[0]["error"]


def _internet(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "security_profile", "internet")


def _plain_pg(db) -> None:
    source = by_name(db, "Origen prueba")
    source.settings = {**source.settings, "sslmode": "disable"}
    db.commit()


def test_internet_profile_refuses_plain_pg_profile_and_check(
    db, superuser, origin, pg_source, monkeypatch
):
    _plain_pg(db)
    _internet(monkeypatch)
    session = _make_session(db, superuser)

    table = f"{TEST_SCHEMA}.origin_sales"
    result, summary = _run(db, superuser, session, "profile_source",
                           {"name": "Origen prueba", "table": table})
    assert result == {"error": "la fuente requiere TLS en el perfil de seguridad actual"}
    assert summary.startswith("No se pudo perfilar")
    assert not session.working_state or "inspected" not in session.working_state

    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "sql": f"SELECT doc FROM {ORIGIN}"})
    assert result["ok"] is False
    assert result["error"] == "la fuente requiere TLS en el perfil de seguridad actual"

    _set_files(session, _draft(), superuser)
    db.flush()
    path = "integrations/ventas-dos/queries/lines.sql"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "path": path})
    assert result["ok"] is False
    assert result["error"] == "la fuente requiere TLS en el perfil de seguridad actual"
    assert session.query_checks[path]["ok"] is False
    assert (session.query_checks[path]["error"]
            == "la fuente requiere TLS en el perfil de seguridad actual")


def test_internet_profile_refuses_http_rest(db, superuser, rest_origin, monkeypatch):
    _internet(monkeypatch)
    session = _make_session(db, superuser)
    _set_files(session, _rest_draft(), superuser)
    db.flush()

    path = "integrations/rest-dos/requests/orders.yaml"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "API prueba", "path": path})
    assert result["ok"] is False
    assert result["error"] == "la fuente requiere HTTPS en el perfil de seguridad actual"

    result, _ = _run(db, superuser, session, "profile_source",
                     {"name": "API prueba", "table": "orders"})
    assert result == {"error": "la fuente requiere HTTPS en el perfil de seguridad actual"}
    assert rest_origin.requests == []


def test_internet_profile_refuses_plain_pg_preview(db, superuser, workspace, monkeypatch):
    lock(workspace)
    apply(signed_in("root@example.com"))
    session = for_session(db, _session(db, superuser, _draft()))
    assert session.validation["valid"] is True

    _plain_pg(db)
    _internet(monkeypatch)

    result, summary = _run(db, superuser, session, "run_preview", {})
    assert result["status"] == "failed"
    assert summary == "Ejecutó una vista previa (con errores)."
    assert any(
        "la fuente requiere TLS en el perfil de seguridad actual" in line
        for line in result["lines"]
    )
    assert session.preview["integrations"]["ventas-dos"]["status"] == "failed"


def test_check_request_retries_without_window_when_empty(monkeypatch):
    calls = []
    responses = [
        ([], {}),
        ([{"id": 41, "total": 99.5, "fecha": "2026-01-02"}], {}),
    ]

    def fake_supabase(settings, secrets, app, request, params, *, extra_params, time_limit_s):
        calls.append((request, params, extra_params))
        return responses.pop(0)

    monkeypatch.setattr(extract, "supabase_once", fake_supabase)
    source = SimpleNamespace(
        kind="supabase",
        settings={"url": "https://zeta.supabase.co", "timeout_seconds": 5},
    )
    request_yaml = """
method: GET
path: ventas
params:
  select: id,total,fecha
  order: fecha.desc
  fecha: gte.{window_start}
  and: (fecha.gte.{window_start},fecha.lt.{window_end})
records: $
fields:
  id: id
  total: total
  fecha: fecha
"""
    result = origin_tools._run_check_request(
        source, {"service_key": "k"}, get_settings(), request_yaml, ["id", "total", "fecha"]
    )
    assert len(calls) == 2
    first_call = calls[0]
    second_call = calls[1]
    assert second_call[1] is first_call[1]
    assert second_call[2] == first_call[2]
    assert second_call[0]["params"] == {"select": "id,total,fecha", "order": "fecha.desc"}
    assert result["ok"] is True
    assert result["records"] == 1
    assert result["sin_ventana"] is True
    assert result["note"] == (
        "No hubo filas en la ventana; se comprobó la forma con la fila más reciente sin "
        "filtro de fechas."
    )
    assert [f["json_type"] for f in result["fields"]] == ["integer", "number", "string"]
    dumped = json.dumps(result)
    assert "99.5" not in dumped
    assert "2026-01-02" not in dumped
    assert "41" not in dumped


def test_check_request_no_window_does_not_retry(monkeypatch):
    calls = []

    def fake_supabase(settings, secrets, app, request, params, *, extra_params, time_limit_s):
        calls.append((request, params, extra_params))
        return ([], {})

    monkeypatch.setattr(extract, "supabase_once", fake_supabase)
    source = SimpleNamespace(
        kind="supabase",
        settings={"url": "https://zeta.supabase.co", "timeout_seconds": 5},
    )
    request_yaml = """
method: GET
path: ventas
params:
  select: id,total,fecha
records: $
fields:
  id: id
"""
    result = origin_tools._run_check_request(
        source, {"service_key": "k"}, get_settings(), request_yaml, ["id"]
    )
    assert len(calls) == 1
    assert "sin_ventana" not in result
    assert result["records"] == 0
    assert result["note"] == (
        "sin registros en los últimos 7 días; no se comprobaron los campos"
    )


def test_check_request_retry_also_empty(monkeypatch):
    def fake_supabase(settings, secrets, app, request, params, *, extra_params, time_limit_s):
        return ([], {})

    monkeypatch.setattr(extract, "supabase_once", fake_supabase)
    source = SimpleNamespace(
        kind="supabase",
        settings={"url": "https://zeta.supabase.co", "timeout_seconds": 5},
    )
    request_yaml = """
method: GET
path: ventas
params:
  select: id,total,fecha
  fecha: gte.{window_start}
records: $
fields:
  id: id
"""
    result = origin_tools._run_check_request(
        source, {"service_key": "k"}, get_settings(), request_yaml, ["id"]
    )
    assert result["records"] == 0
    assert result["sin_ventana"] is True
    assert result["note"] == (
        "sin registros en los últimos 7 días ni sin filtro de fechas; no se comprobaron "
        "los campos"
    )
    assert result["ok"] is True
    assert result["fields"] == [{"column": "id", "found": None, "json_type": None}]


def test_check_request_retry_error_keeps_empty_result(monkeypatch):
    responses = [([], {})]

    def fake_supabase(settings, secrets, app, request, params, *, extra_params, time_limit_s):
        if not responses:
            raise extract.ExtractError("x")
        return responses.pop(0)

    monkeypatch.setattr(extract, "supabase_once", fake_supabase)
    source = SimpleNamespace(
        kind="supabase",
        settings={"url": "https://zeta.supabase.co", "timeout_seconds": 5},
    )
    request_yaml = """
method: GET
path: ventas
params:
  select: id,total,fecha
  fecha: gte.{window_start}
records: $
fields:
  id: id
"""
    result = origin_tools._run_check_request(
        source, {"service_key": "k"}, get_settings(), request_yaml, ["id"]
    )
    assert result["records"] == 0
    assert "sin_ventana" not in result
    assert result["note"] == (
        "sin registros en los últimos 7 días; no se comprobaron los campos"
    )
    assert result["fields"] == [{"column": "id", "found": None, "json_type": None}]
    assert result["missing"] == []
    assert result["ok"] is True


def test_implement_prompt_warns_against_probe_files():
    """021: the workflow rules moved from the base prefix to the /speckit-implement prompt."""
    from app.assistant.commands.registry import prompt_body

    text = " ".join(prompt_body("speckit-implement", "es").split())
    assert "comprueba la forma aunque la ventana esté vacía); nunca agregues archivos de prueba" \
        in text


def _with_transform(files, sql_text, extra_input=None):
    doc = yaml.safe_load(files["integrations/ventas-dos/integration.yaml"])
    columns = doc["datasets"]["sale_lines"]["columns"]
    input_cols = {c: {"type": d["type"]} for c, d in columns.items()}
    if extra_input:
        input_cols.update(extra_input)
    doc["datasets"]["sale_lines"]["transform"] = {
        "input": input_cols,
        "sql": sql_text,
    }
    files["integrations/ventas-dos/integration.yaml"] = yaml.safe_dump(
        doc, sort_keys=False, allow_unicode=True
    )
    return files


def test_check_query_returns_transform_output_columns(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    files = _with_transform(
        _draft(),
        "SELECT document_id, line_no, line_kind, completed_at, local_date, "
        "upper(product_code) AS product_code, net_amount FROM input",
    )
    _set_files(session, files, superuser)
    db.flush()
    path = "integrations/ventas-dos/queries/lines.sql"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "path": path})
    assert result["ok"] is True
    assert result["missing"] == []
    assert result["extra"] == []
    transform_result = result["transform"]
    assert transform_result["mode"] == "rows"
    assert [c["name"] for c in transform_result["columns"]] == [
        "document_id", "line_no", "line_kind", "completed_at", "local_date",
        "product_code", "net_amount"
    ]
    types = {c["name"]: c["type"] for c in transform_result["columns"]}
    assert types["product_code"] == "String"
    assert types["line_no"] == "Int32"
    assert transform_result["problems"] == []


def test_check_query_compares_with_transform_input(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    files = _with_transform(
        _draft(),
        "SELECT document_id, line_no, line_kind, completed_at, local_date, "
        "upper(product_code) AS product_code, net_amount FROM input",
        extra_input={"discount": {"type": "numeric"}},
    )
    _set_files(session, files, superuser)
    db.flush()
    path = "integrations/ventas-dos/queries/lines.sql"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "path": path})
    assert result["ok"] is False
    assert result["missing"] == ["discount"]


def test_check_query_reports_transform_mismatch(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    files = _with_transform(
        _draft(),
        "SELECT document_id, line_no, line_kind, completed_at, local_date, "
        "upper(product_code) AS product_code FROM input",
    )
    _set_files(session, files, superuser)
    db.flush()
    path = "integrations/ventas-dos/queries/lines.sql"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "path": path})
    assert result["ok"] is False
    problems = result["transform"]["problems"]
    assert any(
        p["code"] == "transform_mismatch"
        and p["level"] == "error"
        and "net_amount" in p["message"]
        for p in problems
    )
    assert result["transform"]["mode"] == "rows"


def test_check_query_transform_whole_mode_and_tz_date(db, superuser, origin, pg_source):
    session = _make_session(db, superuser)
    files = _with_transform(
        _draft(),
        "SELECT document_id, line_no, line_kind, completed_at, "
        "CAST(completed_at AS DATE) AS local_date, product_code, net_amount "
        "FROM input ORDER BY document_id",
    )
    _set_files(session, files, superuser)
    db.flush()
    path = "integrations/ventas-dos/queries/lines.sql"
    result, _ = _run(db, superuser, session, "check_query",
                     {"source": "Origen prueba", "path": path})
    assert result["transform"]["mode"] == "whole"
    assert any(
        p["code"] == "transform_tz_date"
        for p in result["transform"]["problems"]
    )
