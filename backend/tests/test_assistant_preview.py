"""Feature 014/020: preview of the conversation's project into temporary schemas (never
published data). The preview state lives on the project (020)."""
import copy
import secrets
import textwrap
import threading
from datetime import UTC, datetime, timedelta

import pytest
import yaml

from app.assistant import preview, service
from app.assistant.tools import ToolError, run_tool
from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.engine import datasets, runner
from app.models import AppUser, AssistantSession
from app.projects import compose, fs
from app.projects import service as project_service
from app.projects.workview import for_session
from tests.conftest import TEST_SCHEMA, signed_in, sql, v2_files
from tests.test_runner import NOW, ORIGIN
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import apply, lock
from tests.test_vibe_reporting import workspace as workspace  # fixture
from tests.workspace_fixture import REPORT, integration_yaml, queries


@pytest.fixture(autouse=True)
def projects_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))


@pytest.fixture(autouse=True)
def _shift_origin_to_now(request):
    """Shift origin rows to same offsets from the real wall clock when tests depend on origin."""
    if "origin" in request.fixturenames:
        request.getfixturevalue("origin")
        sql(
            "UPDATE origin_sales "
            "SET completed_at = completed_at + (now() - CAST(:n AS timestamptz))",
            n=NOW,
        )


def _report_files(uses_draft_integration: bool) -> dict[str, str]:
    report_yaml = textwrap.dedent(REPORT.format(title="Ventas 2")).lstrip()
    report_yaml = report_yaml.replace("id: ventas\n", "id: ventas2\n")
    report_yaml = report_yaml.replace(
        "spec: specs/reports/001-ventas\n", "spec: specs/reports/002-ventas2\n"
    )
    if uses_draft_integration:
        report_yaml = report_yaml.replace("ventas-prueba.", "ventas-dos.")
    return {
        "reports/ventas2/report.yaml": report_yaml,
        "specs/reports/002-ventas2/spec.md": (
            "# Ventas 2\n\n**Spec type**: report\n\n**Status**: Implemented\n"
        ),
        "specs/reports/002-ventas2/plan.md": "# Plan\n",
        "specs/reports/002-ventas2/tasks.md": "- [X] T001 hecho\n",
    }


def _draft(with_layout: bool = False):
    integ_yaml = textwrap.dedent(integration_yaml()).lstrip()
    integ_yaml = integ_yaml.replace("id: ventas-prueba", "id: ventas-dos")
    integ_yaml = integ_yaml.replace(
        "spec: specs/integrations/001-ventas-prueba",
        "spec: specs/integrations/002-ventas-dos",
    )
    files = {
        "integrations/ventas-dos/integration.yaml": integ_yaml,
        "specs/integrations/002-ventas-dos/spec.md": (
            "# Ventas dos\n\n**Spec type**: integration\n\n**Status**: Implemented\n"
        ),
        "specs/integrations/002-ventas-dos/plan.md": "# Plan\n",
        "specs/integrations/002-ventas-dos/tasks.md": "- [X] T001 hecho\n",
        **_report_files(uses_draft_integration=True),
    }
    for name, text in queries(ORIGIN).items():
        files[f"integrations/ventas-dos/queries/{name}"] = text
    return _with_layout(files) if with_layout else files


# 026: ids que el layout puede enlazar (FR-002) y el layout de las dos mitades (FR-011).
VIEW_IDS = {"kpis": "resumen", "trend": "diaria", "ranking": "por_producto"}
LAYOUT = {
    "web": {
        "gutter": "md",
        "components": [
            {"id": "resumen_ventas", "type": "kpi", "view": "resumen",
             "metric": "net_sales", "delta": "previous_period", "span": 12},
            {"id": "tendencia_ventas", "type": "line", "view": "diaria", "x": "day",
             "series": ["net_sales"], "colors": ["series1"], "span": 8},
            {"id": "productos", "type": "bar", "view": "por_producto", "x": "product",
             "series": ["net_sales"], "orientation": "horizontal", "span": 4},
            {"id": "detalle", "type": "table", "view": "por_producto",
             "columns": ["product", "net_sales"], "page_size": 10, "span": 12},
        ],
    },
    "pdf": {
        "page": {"size": "a4", "orientation": "portrait",
                 "margins": {"top": 12, "right": 10, "bottom": 12, "left": 10}},
        "overflow": "continue",
        "blocks": [
            {"id": "cabecera", "type": "header", "title": True, "period": True},
            {"id": "fila_kpis", "type": "kpi_row", "view": "resumen",
             "items": ["net_sales", "orders"], "delta": True},
            {"id": "grafico", "type": "chart", "view": "diaria", "kind": "line",
             "x": "day", "series": ["net_sales"], "height_mm": 60},
            {"id": "detalle_pdf", "type": "table", "view": "por_producto",
             "columns": ["product", "net_sales"], "totals": True},
            {"id": "pie", "type": "footer", "generated_at": True, "page_numbers": True},
        ],
    },
}


def _with_layout(files: dict[str, str], layout: dict | None = None,
                 rid: str = "ventas2") -> dict[str, str]:
    """El mismo borrador con `id` en las vistas y el `layout` declarado (026 FR-011)."""
    path = f"reports/{rid}/report.yaml"
    doc = yaml.safe_load(files[path])
    for view in doc["views"]:
        view["id"] = VIEW_IDS[view["type"]]
    doc["layout"] = copy.deepcopy(LAYOUT if layout is None else layout)
    return {**files, path: yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)}


def _session(db, superuser, files, valid=True) -> AssistantSession:
    """A conversation on a new project holding `files` (v2), validated or marked invalid."""
    actor = db.get(AppUser, superuser.id)
    project = project_service.create(db, actor, f"Chat {secrets.token_hex(3)}")
    db.commit()
    fs.apply_ops(project.id, [{"op": "write", "path": path, "content": text, "base_sha256": None,
                               "force": False} for path, text in v2_files(files).items()],
                 {"kind": "user", "user_id": superuser.id, "session_id": None, "command": "edit"})
    s = service.create_session(db, actor, project_id=project.id)
    db.commit()
    view = for_session(db, s)
    if valid:
        view.validation = compose.validate_project(db, view.project)
    else:
        view.validation = {"valid": False, "warnings": [],
                           "errors": [{"entry": "x", "code": "y", "message": "z"}]}
    return s


def _preview(s) -> dict:
    return sql("SELECT preview FROM project WHERE id = :i", i=s.project_id)[0][0]


def _run_preview(db, superuser, files):
    s = _session(db, superuser, files)
    r = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/preview")
    assert r.status_code == 200, r.text
    assert r.json()["preview"]["status"] == "pending"
    req_id = sql("SELECT id FROM assistant_preview_request WHERE session_id = :s", s=s.id)[0][0]
    preview.process_request(req_id)
    return s


def _schemas(like: str) -> list[str]:
    """Return only schemas of THIS test run: shared DB may contain other runs' leftovers."""
    return [row[0] for row in sql("SELECT nspname FROM pg_namespace WHERE nspname LIKE :p",
                                  p=like) if row[0].startswith(f"{TEST_SCHEMA}__")]


def test_preview_requires_valid_draft(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    s = _session(db, superuser, _draft(), valid=False)
    r = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/preview")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invalid_draft"


def test_preview_runs_into_temporary_schema_only(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    s = _run_preview(db, superuser, _draft())
    assert for_session(db, s).validation["valid"] is True
    state = _preview(s)
    assert state["status"] == "succeeded", state
    assert state["integrations"]["ventas-dos"]["datasets"]["sale_lines"]["rows"] > 0
    notice = sql("SELECT content FROM assistant_message "
                 "WHERE session_id = :s AND tool_name = 'preview'", s=s.id)
    assert len(notice) == 1 and notice[0][0].startswith("Vista previa lista: sale_lines ")
    names = _schemas("%ventas\\_dos")
    assert any(f"preview_{s.id}__ds_ventas_dos" in n for n in names)
    assert not any(n.endswith("__ds_ventas_dos") and "preview_" not in n for n in names)
    assert "ds_ventas_dos" not in names
    assert sql(
        "SELECT count(*) FROM integration_run WHERE integration_id = 'ventas-dos'"
    )[0][0] == 0


def test_preview_report_data_renders(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    s = _run_preview(db, superuser, _draft())
    client = signed_in("root@example.com")
    r = client.get(f"/api/assistant/sessions/{s.id}/preview/report/ventas2/data"
                   "?period=last_7_days&compare=none")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["views"]
    assert body["views"][0]["type"] == "kpis"
    assert body["freshness"]["data_version"] == "preview"
    r2 = client.get(f"/api/assistant/sessions/{s.id}/preview/report/ventas2")
    assert r2.status_code == 200, r2.text
    assert "title" in r2.json() or "id" in r2.json()


def test_preview_report_before_run_is_409(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    s = _session(db, superuser, _draft())
    r = signed_in("root@example.com").get(
        f"/api/assistant/sessions/{s.id}/preview/report/ventas2/data")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "preview_not_ready"


def test_admin_cannot_read_preview(db, superuser, admin, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    s = _run_preview(db, superuser, _draft())
    r = signed_in("admin@example.com").get(f"/api/assistant/sessions/{s.id}/preview")
    assert r.status_code == 403


def test_drop_preview_removes_schemas(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    s = _run_preview(db, superuser, _draft())
    preview.drop_for_session(s.id)
    assert not any(f"preview_{s.id}__" in n for n in _schemas("%preview%"))


def test_cleanup_stale_drops_old_previews(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    s = _run_preview(db, superuser, _draft())
    old = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    sql(
        "UPDATE project SET preview = "
        "jsonb_set(preview, '{finished_at}', to_jsonb(CAST(:v AS text))) "
        "WHERE id = :i",
        v=old,
        i=s.project_id,
    )
    db.expire_all()
    n = preview.cleanup_stale(db)
    db.commit()
    assert n >= 1
    assert not any(f"preview_{s.id}__" in n for n in _schemas("%preview%"))
    assert _preview(s) == {"status": "expired"}


def test_reports_only_draft_previews_immediately(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    s = _session(db, superuser, _report_files(uses_draft_integration=False))
    r = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/preview")
    assert r.status_code == 200, r.text
    body = r.json()["preview"]
    assert body["status"] == "succeeded"
    assert body["preview_integrations"] == []
    assert sql(
        "SELECT count(*) FROM assistant_preview_request WHERE session_id = :s", s=s.id
    )[0][0] == 0
    assert sql("SELECT content FROM assistant_message "
               "WHERE session_id = :s AND tool_name = 'preview'", s=s.id) == [
        ("Vista previa lista.",)]


def test_draft_items_merges_active_integration():
    base_def = {
        "id": "ventas-prueba",
        "source": "Origen prueba",
        "schedule": "0 * * * *",
        "datasets": {},
    }
    base_files = {
        "queries/lines.sql": "SELECT doc FROM origin",
        "queries/totals.sql": "SELECT count(*) FROM origin",
    }
    base = {"ventas-prueba": {"definition": base_def, "files": base_files}}
    base_def_before = dict(base_def)
    base_files_before = dict(base_files)

    files = {"integrations/ventas-prueba/queries/lines.sql": "SELECT  doc FROM origin"}
    integrations, reports = preview.draft_items(files, base)
    assert reports == {}
    item = integrations["ventas-prueba"]
    assert item["definition"] == base_def_before
    assert item["definition"] is not base_def
    assert item["files"]["queries/lines.sql"] == "SELECT  doc FROM origin"
    assert item["files"]["queries/totals.sql"] == "SELECT count(*) FROM origin"
    assert item["files"] is not base_files
    assert base_def == base_def_before
    assert base_files == base_files_before

    draft_repl = {
        "integrations/ventas-prueba/integration.yaml": (
            "id: ventas-prueba\nsource: Origen prueba\ndatasets: {}\n"
        )
    }
    integrations2, _ = preview.draft_items(draft_repl, base)
    item2 = integrations2["ventas-prueba"]
    assert item2["definition"] == {
        "id": "ventas-prueba",
        "source": "Origen prueba",
        "datasets": {},
    }
    assert "schedule" not in item2["definition"]
    assert item2["definition"] is not base_def
    assert item2["files"] == base_files
    assert item2["files"] is not base_files
    assert base_def == base_def_before
    assert base_files == base_files_before

    files_new = {"integrations/nueva/queries/x.sql": "SELECT 1"}
    integrations3, _ = preview.draft_items(files_new, base)
    assert integrations3["nueva"]["definition"] == {}
    assert integrations3["nueva"]["files"]["queries/x.sql"] == "SELECT 1"


def test_request_preview_refused_while_agent_preview_runs(db, superuser, workspace,
                                                         without_command_guard):
    lock(workspace)
    apply(signed_in("root@example.com"))
    files = _draft()
    s = _session(db, superuser, files)
    with datasets.preview_schemas(datasets.preview_prefix(s.id)):
        schema_name = datasets.schema_name("ventas-dos")
    sql(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')

    key = preview.preview_lock_key(s.id)
    conn = get_engine().connect()
    pg = conn.connection.driver_connection
    pg.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (key,))
    pg.commit()
    try:
        r = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/preview")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "preview_running"
        assert sql(
            "SELECT count(*) FROM assistant_preview_request WHERE session_id = :s",
            s=s.id,
        )[0][0] == 0

        actor = db.get(AppUser, superuser.id)
        with pytest.raises(ToolError, match="en curso"):
            run_tool(db, actor, for_session(db, db.get(AssistantSession, s.id)),
                     "run_preview", {}, get_settings())
        db.commit()

        assert sql(
            "SELECT count(*) FROM information_schema.schemata WHERE schema_name = :n",
            n=schema_name,
        )[0][0] == 1
    finally:
        pg.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,))
        pg.commit()
        conn.close()

    r = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/preview")
    assert r.status_code == 200
    assert r.json()["preview"]["status"] == "pending"
    preview.drop_for_session(s.id)


def test_worker_request_fails_cleanly_when_lock_is_held(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    files = _draft()
    s = _session(db, superuser, files)

    r = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/preview")
    assert r.status_code == 200
    req_id = sql(
        "SELECT id FROM assistant_preview_request WHERE session_id = :s", s=s.id
    )[0][0]

    key = preview.preview_lock_key(s.id)
    conn = get_engine().connect()
    pg = conn.connection.driver_connection
    pg.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (key,))
    pg.commit()
    try:
        preview.process_request(req_id)
        assert _preview(s)["status"] == "failed"
        assert _preview(s)["message"] == (
            "Ya había otra vista previa en curso; vuelve a solicitarla."
        )
        assert sql(
            "SELECT finished_at FROM assistant_preview_request WHERE id = :id",
            id=req_id,
        )[0][0] is not None
    finally:
        pg.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,))
        pg.commit()
        conn.close()

    preview.drop_for_session(s.id)


def test_agent_preview_blocks_request_preview_concurrently(db, superuser, workspace,
                                                           monkeypatch, without_command_guard):
    lock(workspace)
    apply(signed_in("root@example.com"))
    files = _draft()
    s = _session(db, superuser, files)

    entered = threading.Event()
    release = threading.Event()
    errors = []
    results = {}

    def fake_run_preview(definition, files, *, session_id, time_limit_s):
        entered.set()
        assert release.wait(10)
        return {
            "status": "succeeded",
            "message": None,
            "datasets": {"sale_lines": {"rows": 1}, "products": {"rows": 1}},
            "checks": [],
        }

    monkeypatch.setattr(runner, "run_preview", fake_run_preview)

    def run_agent():
        try:
            with get_sessionmaker()() as tdb:
                sess = for_session(tdb, tdb.get(AssistantSession, s.id))
                actor = tdb.get(AppUser, superuser.id)
                results["reply"] = run_tool(tdb, actor, sess, "run_preview", {},
                                            get_settings())
                tdb.commit()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run_agent, daemon=True)
    thread.start()
    try:
        assert entered.wait(10)
        r = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/preview")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "preview_running"
        release.set()
        thread.join(10)
        assert not errors
        assert results["reply"][0]["status"] == "succeeded"
        r = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/preview")
        assert r.status_code == 200
        assert r.json()["preview"]["status"] == "pending"
    finally:
        release.set()
        thread.join(10)
        preview.drop_for_session(s.id)


def test_preview_carries_the_layout_and_its_data(db, superuser, workspace):
    """026 US3: el layout viaja por la definición, los datos y el PDF, en las dos familias de
    rutas de vista previa (projects.py y la conversación)."""
    lock(workspace)
    apply(signed_in("root@example.com"))
    s = _run_preview(db, superuser, _draft(with_layout=True))
    client = signed_in("root@example.com")
    slug = for_session(db, s).project.slug
    web_views = {c["view"] for c in LAYOUT["web"]["components"]}
    pdf_views = {b["view"] for b in LAYOUT["pdf"]["blocks"] if "view" in b}
    for base in (f"/api/assistant/sessions/{s.id}", f"/api/projects/{slug}"):
        definition = client.get(f"{base}/preview/report/ventas2")
        assert definition.status_code == 200, definition.text
        assert definition.json()["layout"] == LAYOUT

        data = client.get(f"{base}/preview/report/ventas2/data"
                          "?period=last_7_days&compare=none")
        assert data.status_code == 200, data.text
        ids = {view.get("id") for view in data.json()["views"]}
        assert web_views <= ids
        assert pdf_views <= ids

        pdf = client.post(f"{base}/preview/report/ventas2/pdf"
                          "?period=last_7_days&compare=none")
        assert pdf.status_code == 200, pdf.text
        assert pdf.headers["content-type"].startswith("application/pdf")
        assert pdf.content.startswith(b"%PDF")


def test_draft_layout_problem_is_reported_with_file_and_path(db, superuser, workspace,
                                                            without_command_guard):
    """026 US3 (FR-014, 015 FR-003): un layout que enlaza una vista inexistente es un problema
    del borrador, con archivo, puntero JSON y el fragmento esperado."""
    lock(workspace)
    apply(signed_in("root@example.com"))
    roto = copy.deepcopy(LAYOUT)
    roto["web"]["components"][1]["view"] = "no_existe"
    actor = db.get(AppUser, superuser.id)
    project = project_service.create(db, actor, f"Chat {secrets.token_hex(3)}")
    db.commit()
    session = for_session(db, service.create_session(db, actor, project_id=project.id))
    db.commit()

    result, _summary = run_tool(db, actor, session, "propose_draft",
                                {"files": v2_files(_with_layout(_draft(), roto))},
                                get_settings())
    db.commit()

    assert result["valid"] is False
    problem = next(e for e in result["errors"] if e["code"] == "layout_view_missing")
    assert problem["file"] == "reports/ventas2/report.yaml"
    assert problem["path"] == "/layout/web/components/1/view"
    assert problem["expected"]["enum"] == ["diaria", "por_producto", "resumen"]
    assert "no_existe" in problem["message"]
    assert result["readiness"]["ready"] is False


def test_an_empty_draft_is_a_failed_preview_not_a_success(db, superuser):
    """The worker without the projects volume saw no files and recorded a "succeeded" preview.

    That is what kept the workspace saying "el borrador cambió desde la última vista previa" with
    Apply disabled, while the project folder was full of files written by the agent (reported
    2026-10-22). An empty draft now fails, with the reason in the payload.
    """
    from app.assistant import preview as assistant_preview
    from app.assistant import readiness

    import shutil

    actor = db.get(AppUser, superuser.id)
    project = project_service.create(db, actor, "Vacío preview")
    db.commit()
    session = service.create_session(db, actor, project_id=project.id)
    db.commit()
    # Exactly what a process without the projects volume sees: the folder is not there.
    shutil.rmtree(fs.project_root(project.slug))

    result = assistant_preview.run_draft_preview(db, session)
    assert result["status"] == "failed"
    assert "PROJECTS_DIR" in result["message"]
    assert result["fingerprint"] == readiness.fingerprint({})
