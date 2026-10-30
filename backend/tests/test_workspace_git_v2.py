"""Feature 020 T077: Git workspaces with projects (v2) and the legacy layout."""
import shutil

import pytest

from app.config import get_settings
from tests.conftest import reauth, signed_in, sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import apply, lock
from tests.test_vibe_reporting import workspace as workspace  # fixture


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


def _edit(path, old, new):
    text = path.read_text()
    assert old in text, (path, old)
    path.write_text(text.replace(old, new))


def to_v2(root):
    """The legacy checkout of the fixture as a v2 tree with one project `ventas`."""
    base = root / "projects" / "ventas"
    (base / "specs").mkdir(parents=True)
    shutil.move(root / "integrations", base / "integrations")
    shutil.move(root / "reports", base / "reports")
    shutil.move(root / "specs/integrations/001-ventas-prueba", base / "specs/001-ventas-prueba")
    shutil.move(root / "specs/reports/001-ventas", base / "specs/002-ventas")
    shutil.move(root / "specs/reports/002-ventas-layout", base / "specs/003-ventas-layout")
    shutil.rmtree(root / "specs")
    for folder, kind in (("001-ventas-prueba", "integracion"), ("002-ventas", "reporte"),
                         ("003-ventas-layout", "reporte")):
        spec = base / "specs" / folder / "spec.md"
        spec.write_text(spec.read_text() + f"\n**Tipo**: {kind}\n")
    _edit(base / "integrations/ventas-prueba/integration.yaml",
          "spec: specs/integrations/001-ventas-prueba", "spec: specs/001-ventas-prueba")
    _edit(base / "reports/ventas/report.yaml", "spec: specs/reports/001-ventas",
          "spec: specs/002-ventas")
    _edit(base / "reports/ventas-layout/report.yaml", "spec: specs/reports/002-ventas-layout",
          "spec: specs/003-ventas-layout")
    (base / "project.yaml").write_text(
        'name: "Ventas"\nslug: ventas\ndescription: ""\ncreated: "2026-10-01"\n')
    (root / "bizview.lock").unlink(missing_ok=True)
    lock(root)


def test_v2_git_apply_mirrors_the_project(workspace, superuser, projects):
    to_v2(workspace)
    c = signed_in("root@example.com")
    version = apply(c)
    assert version["projects"]["ventas"]["integrations"] == ["ventas-prueba"]
    assert c.get("/api/projects/ventas").json()["origin"] == "git"
    assert (projects / "ventas/integrations/ventas-prueba/integration.yaml").exists()
    rows = sql("SELECT DISTINCT actor_kind, command FROM project_file_revision")
    assert [tuple(r) for r in rows] == [("git", "git")]
    r = c.put("/api/projects/ventas/file", json={"path": "specs/003-x/spec.md", "content": "x"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "git_project"


def test_git_mirror_keeps_a_spec_number_gap(workspace, superuser, projects):
    """020 T085: a Git project whose specs skip a number (002 deleted) is mirrored as it is."""
    to_v2(workspace)
    base = workspace / "projects" / "ventas"
    shutil.move(base / "specs/002-ventas", base / "specs/004-ventas")
    _edit(base / "reports/ventas/report.yaml", "spec: specs/002-ventas", "spec: specs/004-ventas")
    (workspace / "bizview.lock").unlink(missing_ok=True)
    lock(workspace)
    c = signed_in("root@example.com")
    apply(c)
    assert (projects / "ventas/specs/004-ventas/spec.md").exists()
    assert sorted(s["folder"] for s in c.get("/api/projects/ventas").json()["specs"]) == [
        "001-ventas-prueba", "003-ventas-layout", "004-ventas"]


def test_legacy_git_apply_is_principal(applied, projects):
    detail = applied.get("/api/projects/principal").json()
    assert (detail["origin"], detail["status"]) == ("git", "aplicado")
    assert (projects / "principal/specs/001-ventas-prueba/spec.md").exists()


def test_app_project_with_git_slug_refused_and_convert(workspace, superuser, projects):
    to_v2(workspace)
    c = signed_in("root@example.com")
    apply(c)
    r = reauth(c).post("/api/projects/ventas/convert")
    assert r.status_code == 200, r.text
    assert r.json()["origin"] == "app"
    r = reauth(c).post("/api/workspace/apply")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "git_slug_conflict"
    assert "ventas" in r.json()["error"]["message"]
    assert reauth(c).post("/api/projects/ventas/convert").status_code == 409


def test_git_apply_keeps_app_projects(applied, workspace, projects, monkeypatch):
    monkeypatch.setattr("app.projects.readiness.compute",
                        lambda *a, **k: {"ready": True, "pending": []})
    monkeypatch.setattr("app.projects.origin_checks.recheck_draft", lambda *a, **k: [])
    c = applied
    slug = c.post("/api/projects", json={"name": "Extra"}).json()["slug"]
    report = (workspace / "reports/ventas/report.yaml").read_text().replace(
        "id: ventas\n", "id: ventas-x\n").replace("spec: specs/reports/001-ventas",
                                                  "spec: specs/001-ventas-x")
    for path, content in (
            ("specs/001-ventas-x/spec.md", "# X\n\n**Tipo**: reporte\n**Status**: Implemented\n"),
            ("specs/001-ventas-x/plan.md", "# Plan\n"),
            ("specs/001-ventas-x/tasks.md", "- [X] T001 hecho\n"),
            ("reports/ventas-x/report.yaml", report)):
        r = c.put(f"/api/projects/{slug}/file", json={"path": path, "content": content})
        assert r.status_code == 200, r.text
    assert reauth(c).post(f"/api/projects/{slug}/apply").status_code == 200
    version = apply(c)
    assert "principal" in version["projects"]
    assert version["projects"][slug]["reports"] == ["ventas-x"]
