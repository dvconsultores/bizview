"""Assistant direct-report tools via the fake AI provider (feature 019, US1-US3)."""
from __future__ import annotations

import copy
import hashlib
import re

import pytest
import yaml
from sqlalchemy.engine import make_url

from app.ai import fake
from app.assistant import activity, origin, readiness
from app.assistant.tools import ToolError, run_tool
from app.config import get_settings
from app.engine import direct
from app.i18n import t
from app.models import AppUser, AssistantSession
from app.projects import compose
from app.projects.workview import for_session
from tests.conftest import (
    TEST_SCHEMA,
    chat_response,
    project_view,
    signed_in,
    sql,
    v2_files,
    write_project,
)
from tests.test_assistant_api import _chat_reply, _tool_call
from tests.test_assistant_preview import _session as _chat_session

# 019 agent tools through plain-mode calls; the 021 command guard has its own tests.
pytestmark = pytest.mark.usefixtures("without_command_guard")


def _session(db, superuser, files, valid=True):
    """The WorkView of a conversation on a new project holding `files` (v2)."""
    return for_session(db, _chat_session(db, superuser, files, valid=valid))


def _update(session, superuser, path, text):
    """An edit of one project file (020: the draft is the project folder)."""
    write_project(session.project.id, {path: text}, superuser.id)
    session.refresh()


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _direct_engine_cleanup(monkeypatch):
    monkeypatch.setattr(direct, "LOG_ASYNC", False)
    direct.clear_cache()
    yield
    direct.clear_cache()


def _phys() -> str:
    return direct.physical_schema("public")


BI_TABLE = "bi_ventas_agente"
BI_LOGICAL = f"public.{BI_TABLE}"
SECRET_VALUES = {
    "sucursal": "ZETA-SUC-7777",
    "producto": "ZETA-PROD-8888",
    "monto": "97531",
    "unidades": "864213",
    "email": "zeta.persona@ejemplo.test",
}


@pytest.fixture()
def bi_table():
    phys = _phys()
    sql(f'CREATE SCHEMA IF NOT EXISTS "{phys}"')
    sql(f'DROP TABLE IF EXISTS "{phys}".{BI_TABLE} CASCADE')
    sql(
        f"""
        CREATE TABLE "{phys}".{BI_TABLE} (
            fecha date,
            sucursal text,
            producto text,
            monto numeric,
            unidades integer,
            email text
        )
        """
    )
    sql(
        f"""
        INSERT INTO "{phys}".{BI_TABLE}
            (fecha, sucursal, producto, monto, unidades, email)
        VALUES
            (current_date, 'ZETA-SUC-7777', 'ZETA-PROD-8888',
             97531.2468, 864213, 'zeta.persona@ejemplo.test'),
            (current_date, 'Norte', 'A', 10, 1, NULL)
        """
    )
    yield
    sql(f'DROP TABLE IF EXISTS "{phys}".{BI_TABLE} CASCADE')


def _report_overrides() -> dict:
    return {
        "id": "ventas-agente",
        "spec": "specs/reports/001-ventas-agente",
        "title": "Ventas agente",
        "direct": {
            "source": "bi",
            "cache_seconds": 300,
            "tables": {
                "v": {
                    "table": BI_LOGICAL,
                    "columns": {
                        "fecha": {"type": "date"},
                        "sucursal": {"type": "text"},
                        "producto": {"type": "text"},
                        "monto": {"type": "numeric"},
                        "unidades": {"type": "integer"},
                    },
                }
            },
        },
        "date": "v.fecha",
        "metrics": {
            "total": {
                "label": "Total",
                "format": "number",
                "sql": "sum(v.monto)",
            },
            "unidades": {
                "label": "Unidades",
                "format": "integer",
                "sql": "sum(v.unidades)",
            },
        },
        "dimensions": {"producto": {"label": "Producto", "sql": "v.producto"}},
        "periods": {"default": "mtd", "allowed": ["mtd", "last_month"]},
        "compare": {"default": "none", "allowed": ["none", "previous_period"]},
        "views": [
            {"type": "kpis", "metrics": ["total", "unidades"]},
            {"type": "trend", "metric": "total", "grain": "day"},
            {
                "type": "ranking",
                "dimension": "producto",
                "metric": "total",
                "limit": 5,
            },
            {
                "type": "table",
                "dimensions": ["producto"],
                "metrics": ["total"],
            },
        ],
        "filters": ["producto"],
        "pdf": {"enabled": True},
    }


def _files(overrides: dict | None = None, spec_extra: str = "") -> dict[str, str]:
    report = _report_overrides()
    if overrides:
        for key, value in overrides.items():
            if key == "columns":
                report["direct"]["tables"]["v"]["columns"].update(value)
            elif key == "table":
                report["direct"]["tables"]["v"]["table"] = value
            elif key == "source":
                report["direct"]["source"] = value
            else:
                report[key] = value
    report_text = yaml.safe_dump(report, sort_keys=False, allow_unicode=True)
    spec = (
        "# Ventas agente\n\n"
        "**Spec type**: report\n\n"
        "**Status**: Implemented\n\n"
        "**Modo**: directo\n\n"
        "**Fuente**: bi\n\n"
        f"**Tablas**: {BI_LOGICAL}\n\n"
        "**Mantenido por**: proceso nocturno\n\n"
        "**Volumen esperado**: ~10 filas\n" + spec_extra
    )
    return {
        "specs/reports/001-ventas-agente/spec.md": spec,
        "specs/reports/001-ventas-agente/plan.md": "# Plan\n",
        "specs/reports/001-ventas-agente/tasks.md": "- [X] T001 hecho\n",
        "reports/ventas-agente/report.yaml": report_text,
    }


def _actor(db, superuser):
    return db.get(AppUser, superuser.id)


def _tool(db, actor, session, name, args, settings=None):
    return run_tool(db, actor, session, name, args, settings or get_settings())


def test_list_sources_has_bi_entry(db, superuser, bi_table):
    session = _session(db, superuser, _files(), valid=True)
    result, summary = _tool(
        db, _actor(db, superuser), session, "list_sources", {}
    )
    assert set(result) == {"sources"}
    assert result["sources"][0] == {
        "name": "bi",
        "kind": "postgresql",
        "label": "BI de esta instalación",
        "direct": True,
    }
    assert summary == "Consultó la lista de fuentes."


def test_list_sources_without_bi_when_disabled(
    db, superuser, bi_table, monkeypatch
):
    session = _session(db, superuser, _files(), valid=True)
    settings = get_settings()
    monkeypatch.setattr(settings, "direct_reports_bi", False)
    result, _ = _tool(
        db, _actor(db, superuser), session, "list_sources", {}, settings
    )
    assert all(item["name"] != "bi" for item in result["sources"])


def test_describe_source_bi_returns_logical_structure(
    db, superuser, bi_table
):
    session = _session(db, superuser, _files(), valid=True)
    result, summary = _tool(
        db,
        _actor(db, superuser),
        session,
        "describe_source",
        {"name": "bi"},
    )
    tables = result.get("tables") or []
    table_entry = next(
        table for table in tables
        if table.get("schema") == "public" and table.get("name") == BI_TABLE
    )
    assert any("monto numeric" in col for col in table_entry.get("columns", []))
    assert any(item.get("column") == "email" and item.get("kind") == "email"
               for item in table_entry.get("personal", []))
    assert summary == "Consultó la estructura de la base BI («bi»)."
    assert all(
        not (table.get("schema") == "public" and table.get("name") == "app_user")
        for table in tables
    )


def test_describe_bi_with_live_context_disabled(
    db, superuser, monkeypatch
):
    session = _session(db, superuser, _files(), valid=True)
    settings = get_settings()
    monkeypatch.setattr(settings, "direct_reports_bi", False)
    result, _ = _tool(
        db,
        _actor(db, superuser),
        session,
        "describe_source",
        {"name": "bi"},
        settings,
    )
    assert result == {"error": "No existe una fuente con ese nombre."}


def test_profile_source_bi_aggregate_only(db, superuser, bi_table):
    session = _session(db, superuser, _files(), valid=True)
    result, _ = _tool(
        db,
        _actor(db, superuser),
        session,
        "profile_source",
        {"name": "bi", "table": BI_LOGICAL},
    )
    assert result["table"] == BI_LOGICAL
    assert result["row_count"] == 2
    assert result["truncated"] is False
    columns = {col["name"]: col for col in result["columns"]}
    today = sql("SELECT current_date")[0][0].isoformat()  # the date the fixture inserted
    assert columns["fecha"]["min"] == columns["fecha"]["max"] == today
    assert columns["email"]["personal"] == "email"
    assert columns["email"]["null_ratio"] == 0.5
    assert columns["email"]["distinct"] == 1
    assert "warning" not in result


def test_profile_source_bi_deny_list(db, superuser, bi_table):
    session = _session(db, superuser, _files(), valid=True)
    result, _ = _tool(
        db,
        _actor(db, superuser),
        session,
        "profile_source",
        {"name": "bi", "table": "public.app_user"},
    )
    assert result == {"error": direct.PRODUCT_MESSAGE}


def test_profile_source_bi_large_table_warning(
    db, superuser, bi_table, monkeypatch
):
    session = _session(db, superuser, _files(), valid=True)
    settings = get_settings()
    monkeypatch.setattr(settings, "direct_report_warn_rows", 1)
    sql(f'ANALYZE "{_phys()}".{BI_TABLE}')
    result, _ = _tool(
        db,
        _actor(db, superuser),
        session,
        "profile_source",
        {"name": "bi", "table": BI_LOGICAL},
        settings,
    )
    assert result["estimado"] is True
    assert result["row_count"] == 2
    assert all("null_ratio" not in col for col in result["columns"])
    assert result["warning"].startswith("más de 1 filas")


def test_check_query_direct_report_ok(db, superuser, bi_table, monkeypatch):
    files = _files()
    session = _session(db, superuser, files, valid=True)
    seen: list[str] = []
    orig = direct.DirectSession.query

    def spy(self, statement, tz):
        seen.append(statement.as_string(self._pg))
        return orig(self, statement, tz)

    monkeypatch.setattr(direct.DirectSession, "query", spy)
    text = session.files()["reports/ventas-agente/report.yaml"]   # as stored in the project
    result, summary = _tool(
        db,
        _actor(db, superuser),
        session,
        "check_query",
        {"source": "bi", "path": "reports/ventas-agente/report.yaml"},
    )
    assert result["ok"] is True
    assert result["columns"] == [
        {"name": "m_total", "type": "numeric"},
        {"name": "m_unidades", "type": "bigint"},
    ]
    assert result["report"] == "ventas-agente"
    assert result["metrics"] == ["total", "unidades"]
    assert summary.startswith(
        "Comprobó el reporte directo reports/ventas-agente/report.yaml"
    )
    assert any("LIMIT 0" in statement for statement in seen)
    assert not any(
        re.match(r"^\s*(INSERT|UPDATE|DELETE)", statement)
        for statement in seen
    )
    entry = session.query_checks["reports/ventas-agente/report.yaml"]
    assert entry["sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert entry["ok"] is True
    assert sql("SELECT count(*) FROM report_cache")[0][0] == 0


def test_check_query_direct_report_source_mismatch(db, superuser, bi_table):
    files = _files({"source": "otra"})
    session = _session(db, superuser, files, valid=True)
    result, _ = _tool(
        db,
        _actor(db, superuser),
        session,
        "check_query",
        {"source": "bi", "path": "reports/ventas-agente/report.yaml"},
    )
    assert result["ok"] is False
    assert result["error"] == (
        "El reporte usa la fuente «otra»; indica source: otra."
    )
    entry = (session.query_checks or {}).get(
        "reports/ventas-agente/report.yaml"
    ) or {}
    assert "sha256" not in entry
    assert "ok" not in entry


def test_check_query_direct_report_invalid_path(db, superuser):
    session = _session(db, superuser, _files(), valid=True)
    with pytest.raises(ToolError):
        _tool(
            db,
            _actor(db, superuser),
            session,
            "check_query",
            {"source": "bi", "path": "reports/otro/report.yaml"},
        )


def test_check_query_direct_report_non_direct(db, superuser):
    report = _report_overrides()
    report.pop("direct")
    report["uses"] = {"v": "x.y"}
    files = _files()
    files["reports/ventas-agente/report.yaml"] = yaml.safe_dump(
        report, sort_keys=False, allow_unicode=True
    )
    session = _session(db, superuser, files, valid=False)
    with pytest.raises(ToolError):
        _tool(
            db,
            _actor(db, superuser),
            session,
            "check_query",
            {"source": "bi", "path": "reports/ventas-agente/report.yaml"},
        )


def test_check_query_direct_structure_changed_error(db, superuser, bi_table):
    files = _files()
    session = _session(db, superuser, files, valid=True)
    sql(f'ALTER TABLE "{_phys()}".{BI_TABLE} DROP COLUMN monto')
    result, _ = _tool(
        db,
        _actor(db, superuser),
        session,
        "check_query",
        {"source": "bi", "path": "reports/ventas-agente/report.yaml"},
    )
    assert result["ok"] is False
    assert result["error"] == "La estructura de la fuente cambió: falta monto"
    assert TEST_SCHEMA not in result["error"]
    failures = origin.recheck_draft(db, session, get_settings())
    assert any(
        item["path"] == "reports/ventas-agente/report.yaml"
        for item in failures
    )


def _validate(db, superuser, files):
    """020: the project validation (compose) of `files` in a new project."""
    return compose.validate_project(db, project_view(db, superuser.id, v2_files(files)).project)


def test_validate_direct_structure_problems(db, superuser, bi_table):
    valid = _files()
    validation = _validate(db, superuser, valid)
    assert validation["valid"] is True
    assert validation["errors"] == []

    cases = [
        (_files({"columns": {"sucursal": {"type": "integer"}}}),
         "direct_column_type"),
        (_files({"columns": {"color": {"type": "text"}}}),
         "direct_column_missing"),
        (_files({"table": "public.no_existe"}), "direct_table_missing"),
    ]
    for files, code in cases:
        validation = _validate(db, superuser, files)
        assert validation["errors"], code
        assert any(error["code"] == code for error in validation["errors"])
        error = next(error for error in validation["errors"] if error["code"] == code)
        assert error["file"] == "reports/ventas-agente/report.yaml"
        assert error["path"].startswith("/direct/tables/v")
        assert isinstance(error.get("expected"), dict) and error["expected"]
        assert isinstance(error.get("fix"), str) and error["fix"]


def test_run_preview_direct_and_preview_routes(db, superuser, bi_table):
    files = _files()
    session = _session(db, superuser, files, valid=True)
    result, _ = _tool(
        db,
        _actor(db, superuser),
        session,
        "run_preview",
        {},
    )
    assert result["status"] == "succeeded"
    assert session.preview["reports"]["ventas-agente"]["status"] == "succeeded"
    assert any(
        line.startswith("- reporte directo ventas-agente: succeeded; ")
        for line in result["lines"]
    )
    db.commit()

    client = signed_in("root@example.com")
    sid = session.id
    data = client.get(
        f"/api/assistant/sessions/{sid}/preview/report/ventas-agente/data"
    )
    assert data.status_code == 200
    body = data.json()
    assert body["freshness"]["mode"] == "direct"
    assert body["freshness"]["preview"] is True
    assert body["freshness"]["source"] == t("report.bi_source")     # 022: localized label
    assert len(body["views"]) == 4

    page = client.get(f"/api/assistant/sessions/{sid}/preview/report/ventas-agente")
    assert page.status_code == 200
    assert "direct" in page.json()

    pdf = client.post(
        f"/api/assistant/sessions/{sid}/preview/report/ventas-agente/pdf"
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_run_preview_direct_failure_line(db, superuser, bi_table):
    files = _files()
    session = _session(db, superuser, files, valid=True)
    phys = _phys()
    sql(f'DROP TABLE IF EXISTS "{phys}".{BI_TABLE} CASCADE')
    result, _ = _tool(db, _actor(db, superuser), session, "run_preview", {})
    assert result["status"] == "failed"
    assert any(
        line.startswith("- reporte directo ventas-agente: failed; ")
        and "; error: " in line
        for line in result["lines"]
    )


def test_readiness_transitions_for_direct_draft(db, superuser, bi_table):
    files = _files()
    session = _session(db, superuser, files, valid=True)
    state = readiness.compute(session)
    assert state["ready"] is False
    codes = {item["code"] for item in state["pending"]}
    assert "query_check" in codes
    assert "preview" in codes

    _tool(
        db,
        _actor(db, superuser),
        session,
        "check_query",
        {"source": "bi", "path": "reports/ventas-agente/report.yaml"},
    )
    state = readiness.compute(session)
    assert "query_check" not in {item["code"] for item in state["pending"]}

    _tool(db, _actor(db, superuser), session, "run_preview", {})
    state = readiness.compute(session)
    assert state["ready"] is True
    assert state["pending"] == []

    path = "reports/ventas-agente/report.yaml"
    _update(session, superuser, path, session.files()[path] + "# cambio\n")
    state = readiness.compute(session)
    assert any(
        item["code"] == "query_check"
        and item["file"] == "reports/ventas-agente/report.yaml"
        for item in state["pending"]
    )


def test_readiness_direct_structure_warning(db, superuser, bi_table):
    session = _session(db, superuser, _files(), valid=True)
    _tool(
        db,
        _actor(db, superuser),
        session,
        "check_query",
        {"source": "bi", "path": "reports/ventas-agente/report.yaml"},
    )
    _tool(db, _actor(db, superuser), session, "run_preview", {})
    validation = copy.deepcopy(session.validation or {})
    validation["warnings"] = [
        {
            "code": "direct_structure_unchecked",
            "file": "reports/ventas-agente/report.yaml",
            "message": "sin fuente",
        }
    ]
    session.validation = validation
    state = readiness.compute(session)
    assert any(item["code"] == "direct_structure" for item in state["pending"])


def test_readiness_personal_data_needs_confirmation_and_spec_line(
    db, superuser, bi_table
):
    files = _files({"columns": {"email": {"type": "text"}}})
    session = _session(db, superuser, files, valid=True)
    state = readiness.compute(session)
    assert any(
        item["code"] == "personal_data" and "«email»" in item["message"]
        for item in state["pending"]
    )

    session.working_state = {"personal_confirmed": ["email"]}
    state = readiness.compute(session)
    assert any(item["code"] == "personal_data" for item in state["pending"])

    path = "specs/001-ventas-agente/spec.md"
    _update(session, superuser, path, session.files()[path] + "**Datos personales**: email\n")
    state = readiness.compute(session)
    assert not any(item["code"] == "personal_data" for item in state["pending"])


def test_activity_labels_direct():
    assert activity.tool_label(
        "check_query", {"path": "reports/ventas-agente/report.yaml"}
    ) == "Comprobar reporte directo «ventas-agente»"
    assert activity.tool_label("describe_source", {"name": "bi"}) == \
        "Estructura de la base BI"
    assert activity.tool_label(
        "profile_source", {"name": "bi", "table": "public.x"}
    ) == "Perfil de la base BI · public.x"


def _bad_secrets():
    bad = [
        SECRET_VALUES["sucursal"],
        SECRET_VALUES["producto"],
        SECRET_VALUES["email"],
        f"{TEST_SCHEMA}__public",
        "97531",
        "864213",
    ]
    settings = get_settings()
    password = make_url(settings.database_url_bi).password
    if password is not None and len(password) >= 6:
        bad.append(password)
    return bad


def test_direct_agent_flow_and_payload_privacy(db, superuser, bi_table):
    files = v2_files(_files())
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="call-1")],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[_tool_call("describe_source", {"name": "bi"}, call_id="call-2")],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[
                _tool_call(
                    "profile_source",
                    {"name": "bi", "table": BI_LOGICAL},
                    call_id="call-3",
                )
            ],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[
                _tool_call(
                    "propose_draft",
                    {"files": files, "summary": "Reporte directo de ventas"},
                    call_id="call-4",
                )
            ],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[
                _tool_call(
                    "check_query",
                    {
                        "source": "bi",
                        "path": "reports/ventas-agente/report.yaml",
                    },
                    call_id="call-5",
                )
            ],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[_tool_call("run_preview", {}, call_id="call-6")],
            stop_reason="tool_use",
        ),
        _chat_reply(text="Listo"),
    )

    client = signed_in("root@example.com")
    created = chat_response(client)
    assert created.status_code == 200
    sid = created.json()["id"]
    posted = client.post(
        f"/api/assistant/sessions/{sid}/messages",
        json={"text": "Crea el reporte directo de ventas."},
    )
    assert posted.status_code == 202

    db.expire_all()
    session = for_session(db, db.get(AssistantSession, sid))
    assert set(files) <= set(session.files())
    assert not any(path.startswith("integrations/") for path in session.files())
    assert session.validation["valid"] is True
    assert session.preview["status"] == "succeeded"
    assert session.query_checks["reports/ventas-agente/report.yaml"]["ok"] is True

    payloads = fake.SHARED.payloads()
    assert len(payloads) >= 6
    bad = _bad_secrets()
    for payload in payloads:
        for token in bad:
            assert token not in payload
    assert "BI de esta instalación" in payloads[1]

    tool_texts = [
        row[0]
        for row in sql(
            """
            SELECT tool_payload::text
            FROM assistant_message
            WHERE session_id = :s AND tool_payload IS NOT NULL
            """,
            s=sid,
        )
    ]
    for text_value in tool_texts:
        for token in bad:
            assert token not in text_value
    assert len(tool_texts) >= 6
