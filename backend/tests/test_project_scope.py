"""Feature 037: a project never shows, fixes or previews another project's files.

The incident (production, 2026-10-26): `/proyectos/artemisa` listed a problem of
`projects/coinmarketcap/…`, offered «Aplicar arreglo» for it and answered «El archivo … ya no
existe»; the worker failed four previews with «no ve ningún archivo del proyecto». These tests are
the regression: two projects, one user, and no path of the other project anywhere.
"""
from __future__ import annotations

import json
import secrets
import shutil
from textwrap import dedent

import pytest

from app.assistant import preview, service
from app.config import get_settings
from app.models import AppUser, AssistantPreviewRequest, AssistantSession
from app.projects import fs
from app.projects import service as project_service
from app.projects.workview import for_session
from tests.conftest import reauth, sql, v2_files
from tests.test_assistant_preview import _draft
from tests.test_runner import origin as origin
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import applied as applied
from tests.test_vibe_reporting import workspace as workspace
from tests.workspace_fixture import integration_yaml, queries

REPORT_NO_JOIN = """
    id: resumen-{iid}
    spec: specs/002-resumen-{iid}
    title: Resumen de {iid}
    uses:
      lines: {iid}.sale_lines
      products: {iid}.products
    date: lines.local_date
    metrics:
      net_sales: {{label: Ventas netas, sql: "sum(lines.net_amount)", format: currency}}
    views:
      - {{type: kpis, metrics: [net_sales]}}
"""


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    # Readiness and the query re-check have their own suites: here only the scope matters.
    monkeypatch.setattr("app.projects.readiness.compute",
                        lambda *a, **k: {"ready": True, "pending": []})
    monkeypatch.setattr("app.projects.origin_checks.recheck_draft", lambda *a, **k: [])
    return tmp_path / "projects"


def _create(c, name: str) -> str:
    r = c.post("/api/projects", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["slug"]


def _put(c, slug: str, files: dict[str, str], *, force: bool = False) -> None:
    for path, content in files.items():
        body = {"path": path, "content": content}
        if force:
            body["force"] = True
        r = c.put(f"/api/projects/{slug}/file", json=body)
        assert r.status_code == 200, r.text


def _project_with_integration(c, origin, name: str, iid: str) -> str:
    slug = _create(c, name)
    folder = f"001-{iid}"
    files = {
        f"specs/{folder}/spec.md": f"# {iid}\n\n**Tipo**: integracion\n**Status**: Implemented\n",
        f"specs/{folder}/plan.md": "# Plan\n",
        f"specs/{folder}/tasks.md": "- [X] T001 hecho\n",
    }
    files[f"integrations/{iid}/integration.yaml"] = (
        dedent(integration_yaml()).lstrip()
        .replace("id: ventas-prueba", f"id: {iid}")
        .replace("spec: specs/integrations/001-ventas-prueba", f"spec: specs/{folder}"))
    for name_, content in queries(origin).items():
        files[f"integrations/{iid}/queries/{name_}"] = content
    _put(c, slug, files)
    return slug


def _break_it(c, slug: str, iid: str) -> str:
    """A known problem in this project: two sets and no join (035's unjoined_sets)."""
    folder = f"002-resumen-{iid}"
    files = {
        f"specs/{folder}/spec.md":
            f"# resumen-{iid}\n\n**Tipo**: reporte\n**Status**: Implemented\n",
        f"specs/{folder}/plan.md": "# Plan\n",
        f"specs/{folder}/tasks.md": "- [X] T001 hecho\n",
        f"reports/resumen-{iid}/report.yaml": dedent(
            REPORT_NO_JOIN.format(iid=iid)).lstrip(),
    }
    _put(c, slug, files)
    return f"reports/resumen-{iid}/report.yaml"


def _validate(c, slug: str) -> dict:
    r = c.post(f"/api/projects/{slug}/validate")
    assert r.status_code == 200, r.text
    return r.json()["validation"]


# --- the mapping from a project to disk ---------------------------------------------------------

def test_resolve_project_path_rejects_escapes_and_other_projects(env, db, superuser):
    actor = db.get(AppUser, superuser.id)
    a = project_service.create(db, actor, "Alfa")
    b = project_service.create(db, actor, "Beta")
    db.commit()
    root = fs.project_root(a.slug)
    assert fs.resolve_project_path(a.id, "reports/alfa/report.yaml", db=db) == (
        root / "reports" / "alfa" / "report.yaml")

    for bad, codes in (("../beta/project.yaml", {"path_unsafe"}),
                       ("/etc/passwd", {"path_unsafe"}),
                       (f"projects/{b.slug}/project.yaml", {"path_outside_project"}),
                       ("reports/../../beta/x", {"path_unsafe"})):
        with pytest.raises(fs.ProjectPathError) as err:
            fs.resolve_project_path(a.id, bad, db=db)
        assert err.value.code in codes, (bad, err.value.code)

    # A symlink that leaves the project root is refused even when the name looks allowed.
    outside = env / b.slug
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "roto").symlink_to(outside, target_is_directory=True)
    with pytest.raises(fs.ProjectPathError) as err:
        fs.resolve_project_path(a.id, "reports/roto/report.yaml", db=db)
    assert err.value.code == "path_unsafe"

    with pytest.raises(fs.ProjectPathError) as err:
        fs.resolve_project_path(987654, "project.yaml", db=db)
    assert err.value.code == "project_not_found"


# --- validation publishes its own findings ------------------------------------------------------

def test_a_project_publishes_only_its_own_problems(applied, origin):
    c = applied
    a = _project_with_integration(c, origin, "Proyecto Alfa", "ventas-a")
    b = _project_with_integration(c, origin, "Proyecto Beta", "ventas-b")
    broken = _break_it(c, b, "b")

    beta = _validate(c, b)
    assert any(e["file"] == broken for e in beta["errors"]), beta["errors"]
    assert all(e.get("project") == b for e in [*beta["errors"], *beta["warnings"]])
    assert all(not str(e.get("file") or "").startswith("projects/") for e in beta["errors"])

    alfa = _validate(c, a)
    assert alfa["errors"] == [] and alfa["valid"] is True
    assert all(not str(e.get("file") or "").startswith("projects/")
               for e in [*alfa["errors"], *alfa["warnings"]])
    # Nothing about the other project is published as a fixable entry.
    payload = json.dumps(alfa)
    assert f"projects/{b}/" not in payload and broken not in payload
    assert not any(e.get("project") == b for e in [*alfa["errors"], *alfa["warnings"]])


def test_a_composed_collision_is_counted_never_published(applied, db):
    """Adding an id that already exists in another project is real (apply refuses it), but the
    finding belongs to the other project's file, so this project only counts it."""
    c = applied
    slug = _create(c, "Choque")
    files = {"specs/001-ventas-prueba/spec.md":
             "# ventas-prueba\n\n**Tipo**: integracion\n**Status**: Implemented\n",
             "specs/001-ventas-prueba/plan.md": "# Plan\n",
             "specs/001-ventas-prueba/tasks.md": "- [X] T001 hecho\n",
             "integrations/ventas-prueba/integration.yaml":
                 dedent(integration_yaml()).lstrip().replace(
                     "spec: specs/integrations/001-ventas-prueba", "spec: specs/001-ventas-prueba")}
    _put(c, slug, files)
    validation = _validate(c, slug)
    assert validation["composed_valid"] is False
    assert not any(e["code"] == "duplicate_id" for e in validation["errors"])
    assert validation["other_projects"].get("principal", {}).get("errors", 0) >= 1


# --- fixes ----------------------------------------------------------------------------------------

def test_the_fix_endpoint_refuses_a_foreign_path(applied, origin):
    c = applied
    a = _project_with_integration(c, origin, "Proyecto Alfa", "ventas-a")
    b = _project_with_integration(c, origin, "Proyecto Beta", "ventas-b")
    fix = {"file": f"projects/{b}/reports/ventas-b/report.yaml", "json_path": "/joins",
           "op": "append", "value": {"left": "lines.product_code",
                                     "right": "products.product_code", "type": "left"}}
    r = reauth(c).post(f"/api/projects/{a}/fix", json={"fixes": [fix]})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "path_outside_project"
    assert r.json()["error"]["message"].startswith("projects/")

    r = reauth(c).post(f"/api/projects/{a}/fix",
                       json={"fixes": [{**fix, "file": "/etc/passwd"}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "path_unsafe"

    # A path of this project whose file is gone is still a conflict, not a scope error.
    r = reauth(c).post(f"/api/projects/{a}/fix",
                       json={"fixes": [{**fix, "file": "reports/nada/report.yaml"}]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "fix_not_applicable"

    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'project_fix_applied'") == [(0,)]


# --- preview --------------------------------------------------------------------------------------

def test_the_project_preview_carries_its_project_and_files(applied, origin):
    c = applied
    a = _project_with_integration(c, origin, "Proyecto Alfa", "ventas-a")
    r = c.post(f"/api/projects/{a}/preview")
    assert r.status_code == 200, r.text
    pid = sql("SELECT id FROM project WHERE slug = :s", s=a)[0][0]
    row = sql("SELECT project_id, files FROM assistant_preview_request ORDER BY id DESC LIMIT 1")[0]
    assert row[0] == pid
    assert all(not path.startswith("projects/") for path in row[1])
    assert "integrations/ventas-a/integration.yaml" in row[1]


def test_the_project_preview_uses_the_callers_conversation(db, superuser, admin):
    """R5: the project's newest conversation was taken whoever owned it."""
    actor = db.get(AppUser, superuser.id)
    project = project_service.create(db, actor, "Compartido")
    db.commit()
    mine = service.create_session(db, actor, project_id=project.id)
    other = AssistantSession(title="De otra persona", created_by=admin.id, status="open",
                             project_id=project.id)
    db.add(other)
    db.commit()
    view = for_session(db, mine)
    view.validation = {"valid": True, "errors": [], "warnings": []}
    db.commit()

    from app.api.projects import _conversation

    assert _conversation(db, project, actor).id == mine.id


def test_a_preview_for_another_project_is_not_run(db, superuser):
    """R6: the request names its project; a mismatch is refused and logged, not run blind."""
    actor = db.get(AppUser, superuser.id)
    a = project_service.create(db, actor, "Alfa")
    project_service.create(db, actor, "Beta")
    db.commit()
    files = v2_files(_draft())
    fs.apply_ops(a.id, [{"op": "write", "path": p, "content": t, "base_sha256": None,
                         "force": False} for p, t in files.items()],
                 {"kind": "user", "user_id": superuser.id, "session_id": None, "command": "edit"})
    session = service.create_session(db, actor, project_id=a.id)
    for_project = project_service.create(db, actor, f"Otro {secrets.token_hex(2)}")
    db.commit()
    req = AssistantPreviewRequest(session_id=session.id, project_id=for_project.id,
                                  requested_by=superuser.id, files=files)
    db.add(req)
    db.commit()

    preview.process_request(req.id)

    db.refresh(req)
    assert req.finished_at is not None
    state = sql("SELECT preview FROM project WHERE id = :i", i=a.id)[0][0]
    assert state["status"] == "failed"
    assert for_project.slug in state["message"] and a.slug in state["message"]


def test_an_empty_folder_names_the_project_and_the_path(db, superuser):
    """R6: «no ve ningún archivo» without a name made a wrong scope and a missing volume equal."""
    actor = db.get(AppUser, superuser.id)
    project = project_service.create(db, actor, "Sin carpeta")
    db.commit()
    session = service.create_session(db, actor, project_id=project.id)
    db.commit()
    root = fs.project_root(project.slug)
    shutil.rmtree(root)

    result = preview.run_draft_preview(db, session)

    assert result["status"] == "failed"
    assert project.slug in result["message"] and str(root) in result["message"]
    assert "PROJECTS_DIR" in result["message"]


# --- the incident, end to end ---------------------------------------------------------------------

def test_two_projects_never_share_a_problem(applied, origin):
    """SC-001: what artemisa showed. B's problem never reaches A's pages, and vice versa."""
    c = applied
    a = _project_with_integration(c, origin, "Proyecto Alfa", "ventas-a")
    b = _project_with_integration(c, origin, "Proyecto Beta", "ventas-b")
    broken = _break_it(c, b, "b")

    # B has a known problem; A is clean and must stay clean.
    assert any(e["file"] == broken for e in _validate(c, b)["errors"])
    clean = _validate(c, a)
    assert clean["errors"] == []

    # Everything a page of A receives is free of B's paths.
    for response in (c.get(f"/api/projects/{a}"),
                     c.get(f"/api/projects/{a}/tree"),
                     c.post(f"/api/projects/{a}/validate")):
        assert response.status_code == 200, response.text
        body = json.dumps(response.json())
        assert f"projects/{b}/" not in body
        assert broken not in body

    # A's apply works with B's working folder broken (B's *applied* snapshot is what composes).
    assert reauth(c).post(f"/api/projects/{a}/apply").status_code == 200

    # The reverse: B still owns its problem and A does not acquire it.
    beta = _validate(c, b)
    assert any(e["file"] == broken for e in beta["errors"])
    assert _validate(c, a)["errors"] == []
    assert sql("SELECT count(*) FROM assistant_preview_request WHERE project_id IS NULL") == [(0,)]
