"""Feature 005 end to end: workspace → validate → apply → worker run → report data, PDF;
rollback; access; "no spec, no run"."""
import re
from pathlib import Path

import pytest
from bizview_cli import validate as wsv

from app.config import get_settings
from app.worker import Worker
from tests.conftest import client, reauth, signed_in, sql
from tests.test_runner import ORIGIN, PRODUCTS
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.workspace_fixture import REPORT, build, write

SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period"


@pytest.fixture
def workspace(tmp_path, monkeypatch, origin):
    root = build(tmp_path / "cliente-bizview", ORIGIN)
    monkeypatch.setattr(get_settings(), "workspace_path", str(root))
    return root


def lock(root: Path) -> None:
    """What `bizview validate --write-lock` does in the author's workspace."""
    result = wsv.validate(root)
    assert result.ok, [str(i) for i in result.issues]
    wsv.write_lock(root, result.lock)


def apply(c) -> dict:
    r = reauth(c).post("/api/workspace/apply")
    assert r.status_code == 200, r.text
    return r.json()["version"]


def run_worker_requests():
    w = Worker()
    w.take_requests()
    w.pool.shutdown(wait=True)


@pytest.fixture
def applied(workspace, superuser):
    lock(workspace)
    c = signed_in("root@example.com")
    apply(c)
    r = reauth(c).post("/api/integrations/ventas-prueba/run", json={"kind": "full"})
    assert r.status_code == 202, r.text
    run_worker_requests()
    runs = c.get("/api/integrations/ventas-prueba/runs").json()["items"]
    assert runs[0]["status"] == "succeeded", runs[0]
    return c


# --- validate / apply ----------------------------------------------------------------------------

def test_validate_requires_lock_and_detects_changes(workspace, superuser):
    c = signed_in("root@example.com")
    r = c.post("/api/workspace/validate").json()
    assert not r["ok"] and {e["code"] for e in r["errors"]} == {"lock_missing"}
    lock(workspace)
    r = c.post("/api/workspace/validate").json()
    assert r["ok"], r["errors"]
    assert r["changes"]["added"] == ["integrations/ventas-prueba", "reports/ventas",
                                   "reports/ventas-layout"]
    (workspace / "integrations/ventas-prueba/queries/products.sql").write_text(
        PRODUCTS + " WHERE true\n")
    r = c.post("/api/workspace/validate").json()
    assert [e["code"] for e in r["errors"]] == ["lock_mismatch"]
    r = reauth(c).post("/api/workspace/apply")
    assert r.status_code == 409 and r.json()["error"]["code"] == "lock_mismatch"


def test_no_spec_no_run(workspace, superuser):
    (workspace / "specs/reports/001-ventas/tasks.md").write_text("- [ ] T001 pendiente\n")
    c = signed_in("root@example.com")
    r = c.post("/api/workspace/validate").json()
    assert "open_tasks" in {e["code"] for e in r["errors"]}
    r = reauth(c).post("/api/workspace/apply")
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_workspace"
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == 0


def test_unknown_source_is_refused(workspace, superuser):
    sql("DELETE FROM data_source")
    lock(workspace)
    r = signed_in("root@example.com").post("/api/workspace/validate").json()
    assert "unknown_source" in {e["code"] for e in r["errors"]}


def test_apply_needs_step_up_and_superuser(workspace, superuser, admin):
    lock(workspace)
    r = signed_in("root@example.com").post("/api/workspace/apply")
    assert r.status_code == 403 and r.json()["error"]["code"] == "reauth_required"
    assert signed_in("admin@example.com").get("/api/workspace").status_code == 403
    assert client().get("/api/workspace").status_code == 401


def test_apply_creates_dashboard_and_audits(workspace, superuser):
    lock(workspace)
    c = signed_in("root@example.com")
    version = apply(c)
    assert version["reports"] == ["ventas", "ventas-layout"] and version["integrations"] == [
        "ventas-prueba"]
    items = c.get("/api/dashboards").json()["items"]
    ventas = next(d for d in items if d["code"] == "ventas")
    assert ventas["status"] == "available" and ventas["path"] == "/r/ventas"
    assert sql("SELECT count(*) FROM dashboard WHERE code = 'ventas'")[0][0] == 1
    kinds = [k for (k,) in sql("SELECT kind FROM audit_event ORDER BY id")]
    assert "workspace_applied" in kinds
    ws = c.get("/api/workspace").json()
    assert ws["active"]["id"] == version["id"] and ws["mounted"]["checksum"]


def test_rollback_and_removed_report_hidden_with_grants(workspace, superuser, user):
    lock(workspace)
    c = signed_in("root@example.com")
    first = apply(c)
    dash_id = sql("SELECT id FROM dashboard WHERE code = 'ventas'")[0][0]
    sql("INSERT INTO dashboard_access (user_id, dashboard_id, granted_by) "
        "VALUES (:u, :d, :g)", u=user.id, d=dash_id, g=superuser.id)
    write(workspace, "reports/ventas/report.yaml", REPORT.format(title="Ventas 2"))
    lock(workspace)
    apply(c)
    assert c.get("/api/reports/ventas").json()["title"] == "Ventas 2"
    r = reauth(c).post("/api/workspace/rollback")
    assert r.status_code == 200 and r.json()["version"]["id"] == first["id"]
    assert c.get("/api/reports/ventas").json()["title"] == "Ventas"
    assert reauth(c).post("/api/workspace/rollback").status_code == 404
    # A version without the report hides its dashboard; the grant stays.
    import shutil
    shutil.rmtree(workspace / "reports")
    lock(workspace)
    apply(c)
    assert sql("SELECT status FROM dashboard WHERE code = 'ventas'")[0][0] == "hidden"
    assert sql("SELECT count(*) FROM dashboard_access WHERE dashboard_id = :d", d=dash_id)[0][0]
    assert c.get("/api/reports/ventas").status_code == 404


# --- runs and reports ----------------------------------------------------------------------------

def test_integrations_list(applied):
    items = applied.get("/api/integrations").json()["items"]
    assert items[0]["id"] == "ventas-prueba" and not items[0]["paused"]
    assert items[0]["last_run"]["kind"] == "manual_full" and items[0]["next_run"]


def test_report_figures_match_the_origin(applied):
    d = applied.get("/api/reports/ventas").json()
    assert d["metrics"]["net_sales"]["format"] == "currency" and d["currency"] == "USD"
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}")
    assert r.status_code == 200, r.text
    body = r.json()
    kpis = {k["metric"]: k for k in body["views"][0]["items"]}
    # Origin, 27-28 Sep (Caracas): sales 10.50 + 4.25, return 3 → 11.75; one order.
    direct = sql(f"SELECT sum(CASE WHEN kind = 'sale' THEN amount ELSE -amount END) "
                 f"FROM {ORIGIN} WHERE (completed_at AT TIME ZONE 'America/Caracas')::date "
                 f"BETWEEN '2026-09-27' AND '2026-09-28'")[0][0]
    assert kpis["net_sales"]["value"] == float(direct) == 11.75
    assert kpis["orders"]["value"] == 1 and kpis["avg_ticket"]["value"] == 11.75
    assert kpis["net_sales"]["change"] == {"pct": None, "new": True}
    trend = body["views"][1]
    assert [(p["bucket"], p["value"]) for p in trend["points"]] == [
        ("2026-09-27", -3.0), ("2026-09-28", 14.75)]
    ranking = body["views"][2]["items"]
    assert [(i["key"], i["value"]) for i in ranking] == [("P1", 7.5), ("P2", 4.25)]
    etag = r.headers["etag"]
    again = applied.get(f"/api/reports/ventas/data?{SELECTION}", headers={"If-None-Match": etag})
    assert again.status_code == 304


def test_filters_and_selection_rules(applied):
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}&filter.product=P1").json()
    assert r["views"][0]["items"][0]["value"] == 7.5
    assert applied.get("/api/reports/ventas/filters/product?" + SELECTION).json()["items"] == [
        "P1", "P2"]
    assert applied.get("/api/reports/ventas/data?period=ytd").status_code == 422
    assert applied.get("/api/reports/ventas/data?period=custom&from=x&to=y").status_code == 422
    # A filter value is a literal, never SQL.
    evil = applied.get(f"/api/reports/ventas/data?{SELECTION}&filter.product=P1'%20OR%201=1--")
    assert evil.status_code == 200 and evil.json()["views"][0]["items"][0]["value"] is None


def test_report_access_follows_grants(applied, user):
    u = signed_in("user@example.com")
    assert u.get("/api/reports/ventas").status_code == 403
    dash_id = sql("SELECT id FROM dashboard WHERE code = 'ventas'")[0][0]
    sql("INSERT INTO dashboard_access (user_id, dashboard_id, granted_by) "
        "VALUES (:u, :d, :u)", u=user.id, d=dash_id)
    assert u.get(f"/api/reports/ventas/data?{SELECTION}").status_code == 200
    assert u.post("/api/workspace/validate").status_code == 403
    assert u.post("/api/integrations/ventas-prueba/run", json={}).status_code == 403


def test_pdf_has_the_same_figures(applied):
    data = applied.get(f"/api/reports/ventas/data?{SELECTION}").json()
    r = applied.post(f"/api/reports/ventas/pdf?{SELECTION}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    from app.reports.pdf import fmt
    net = data["views"][0]["items"][0]["value"]
    assert fmt(net, "currency") == "11,75 USD"
    text = r.content.decode("latin-1")
    for expected in ("11,75 USD", "Ventas netas", "Pedidos", "P1", "7,50 USD"):
        assert f"({expected})" in text, expected


def test_only_the_ai_service_and_the_connection_test_call_the_provider():
    """045: with the authoring agent gone, the provider has exactly two callers left — the
    connection test the administrator runs, and the read-only help assistant."""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    callers = set()
    for f in app_dir.rglob("*.py"):
        text = f.read_text()
        if re.search(r"\bget_provider\(", text) and not f.match("app/ai/__init__.py"):
            callers.add(f.relative_to(app_dir).as_posix())
    # 045 removed engine/narrative.py with its generator. assistant/service.py is the next to go;
    # the assertion tightens to {"ai/service.py"} the moment it does.
    assert callers == {"ai/service.py", "assistant/service.py"}


def test_non_superuser_cannot_see_runs(applied, admin):
    a = signed_in("admin@example.com")
    assert a.get("/api/integrations").status_code == 403
    assert a.get("/api/integrations/ventas-prueba/runs").status_code == 403


def test_run_request_for_unknown_integration(applied):
    assert reauth(applied).post("/api/integrations/nope/run", json={}).status_code == 404


def test_validation_problems_follow_the_account_language(workspace, superuser):
    """Feature 022 T039: CLI validation messages follow the account language."""
    (workspace / "specs/reports/001-ventas/tasks.md").write_text("- [ ] T001 pendiente\n")

    sql("UPDATE app_user SET locale = 'en' WHERE email = 'root@example.com'")
    c = signed_in("root@example.com")
    r = c.post("/api/workspace/validate").json()
    error = next(e for e in r["errors"] if e["code"] == "open_tasks")
    assert error["message"] == "there are 1 incomplete tasks"

    sql("UPDATE app_user SET locale = 'es' WHERE email = 'root@example.com'")
    c = signed_in("root@example.com")
    r = c.post("/api/workspace/validate").json()
    error = next(e for e in r["errors"] if e["code"] == "open_tasks")
    assert error["message"] == "hay 1 tareas sin completar"


def test_english_report_texts_pass_through(workspace, superuser):
    """Feature 022 T040: optional *_en texts reach the catalogue and the report definition."""
    import yaml
    path = workspace / "reports/ventas/report.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["title_en"] = "Sales"
    doc["description_en"] = "Sales summary"
    doc["metrics"]["net_sales"]["label_en"] = "Net sales"
    doc["dimensions"]["product"]["label_en"] = "Product"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    lock(workspace)
    c = signed_in("root@example.com")
    apply(c)
    item = next(d for d in c.get("/api/dashboards").json()["items"] if d["code"] == "ventas")
    assert item["name"] == doc["title"]
    assert item["name_en"] == "Sales"
    assert item["description_en"] == "Sales summary"
    definition = c.get("/api/reports/ventas").json()
    assert definition["title_en"] == "Sales"
    assert definition["metrics"]["net_sales"]["label_en"] == "Net sales"
    assert "label_en" not in definition["metrics"]["orders"]
    assert definition["dimensions"]["product"]["label_en"] == "Product"
