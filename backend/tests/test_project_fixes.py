"""A validator fix is applied without an AI, and only when the file still matches (feature 035)."""
from __future__ import annotations

from textwrap import dedent

import pytest

from tests.conftest import reauth
from tests.test_projects_apply import (  # noqa: F401  (fixtures below)
    apply_ok,
    env,
    origin,
    project_a,
    put,
    replace,
    spec,
)
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture

REPORT = """
    id: ventas-dia
    spec: specs/002-ventas-dia
    title: Ventas del día
    uses:
      lines: ventas-a.sale_lines
      products: ventas-a.products
    date: lines.local_date
    metrics:
      net_sales: {label: Ventas netas, sql: "sum(lines.net_amount)", format: currency}
      orders: {label: Pedidos, sql: "count(distinct lines.document_id)", format: integer}
    views:
      - {type: kpis, metrics: [net_sales, orders]}
"""
BAD_FILTER = """
    layout:
      web:
        components:
          - {id: filtros, type: filters, only: [ghost]}
"""
REPORT_FILE = "reports/ventas-dia/report.yaml"

# The command guard has its own tests: here only the tool's behaviour matters.
pytestmark = pytest.mark.usefixtures("without_command_guard")


@pytest.fixture
def project_without_join(applied, origin, env):        # noqa: F811
    """The session-23 shape: one report reading two sets and joining nobody."""
    c = applied
    slug = project_a(c, origin)
    files = spec("002-ventas-dia", "reporte")
    files[REPORT_FILE] = dedent(REPORT).lstrip()
    put(c, slug, files)
    return c, slug


def _problems(c, slug):
    body = c.post(f"/api/projects/{slug}/validate").json()
    return [*body["validation"]["errors"], *body["validation"]["warnings"]]


def _problem(problems, code):
    return next(p for p in problems if p["code"] == code)


def test_the_join_the_dashboard_missed_is_one_click(project_without_join):
    """SC-003: 1 problem → 0 with one click, then it applies. No provider involved."""
    c, slug = project_without_join
    problem = _problem(_problems(c, slug), "unjoined_sets")
    assert problem["fix_data"] == {"file": REPORT_FILE, "json_path": "/joins", "op": "append",
                                   "value": {"left": "lines.product_code",
                                             "right": "products.product_code", "type": "left"}}
    assert problem["problem_id"].startswith("unjoined_sets:")

    r = reauth(c).post(f"/api/projects/{slug}/fix",
                       json={"fixes": [{**problem["fix_data"],
                                        "problem_id": problem["problem_id"]}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["validation"]["errors"] == []
    assert "+  joins:" in body["results"][0]["diff"] or "+joins:" in body["results"][0]["diff"]
    assert body["results"][0]["revision_id"]
    apply_ok(c, slug)                                   # and the project applies


def test_two_fixes_in_one_file_apply_together(project_without_join):
    """Both corrections of the same YAML land in one write, and one validation closes them."""
    c, slug = project_without_join
    replace(c, slug, REPORT_FILE, dedent(REPORT).lstrip() + dedent(BAD_FILTER).lstrip())
    problems = _problems(c, slug)
    fixes = [p for p in problems if p["code"] in ("unjoined_sets", "layout_filter_missing")]
    assert {p["code"] for p in fixes} == {"unjoined_sets", "layout_filter_missing"}

    body = reauth(c).post(f"/api/projects/{slug}/fix",
                          json={"fixes": [{**p["fix_data"], "problem_id": p["problem_id"]}
                                          for p in fixes]}).json()

    assert body["validation"]["errors"] == []
    assert len(body["results"]) == 1                    # one write per file
    text = c.get(f"/api/projects/{slug}/file",
                 params={"path": REPORT_FILE}).json()["content"]
    assert "joins" in text and "ghost" not in text


def test_a_fix_is_refused_when_the_file_moved_on(project_without_join):
    c, slug = project_without_join
    problem = _problem(_problems(c, slug), "unjoined_sets")
    r = reauth(c).post(f"/api/projects/{slug}/fix",
                       json={"fixes": [{**problem["fix_data"], "base_sha256": "0" * 64}]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "fix_stale"
    assert "joins" not in c.get(f"/api/projects/{slug}/file",
                                params={"path": REPORT_FILE}).json()["content"]


def test_a_fix_never_calls_the_provider(project_without_join, monkeypatch):
    """The whole point of 035: the fix path does not depend on an AI that may be down."""
    c, slug = project_without_join

    def boom(_settings):
        raise AssertionError("the fix path must not reach the provider")

    monkeypatch.setattr("app.ai.get_provider", boom)
    problem = _problem(_problems(c, slug), "unjoined_sets")
    r = reauth(c).post(f"/api/projects/{slug}/fix",
                       json={"fixes": [{**problem["fix_data"],
                                        "problem_id": problem["problem_id"]}]})
    assert r.status_code == 200 and r.json()["validation"]["errors"] == []


def test_the_agent_applies_the_fix_instead_of_rewriting_the_file(
        project_without_join, db, superuser):
    from app.assistant import service as assistant_service
    from app.assistant.tools import run_tool
    from app.config import get_settings
    from app.models import AppUser
    from app.projects import service as projects
    from app.projects.workview import for_session

    c, slug = project_without_join
    problem = _problem(_problems(c, slug), "unjoined_sets")
    project = projects.get(db, slug)
    session = assistant_service.create_session(db, db.get(AppUser, superuser.id),
                                              project_id=project.id)
    db.commit()

    view = for_session(db, session)
    result, summary = run_tool(db, superuser, view, "apply_fix",
                               {"problem_id": problem["problem_id"]}, get_settings())

    assert result["applied"]["file"] == REPORT_FILE
    assert result["validation"]["errors"] == []
    assert "Arreglo aplicado" in summary
