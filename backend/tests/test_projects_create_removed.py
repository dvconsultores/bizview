"""Feature 049 US4: a project enters Bizview only through import.

Owner decision: projects are authored outside Bizview with whatever tool the author prefers and
arrive as a zip. The creation route stays declared — so an old client reads why — and creates
nothing. The importer keeps its own path to the service, which is where a project is made.
"""
import io
import zipfile

import pytest

from app.config import get_settings
from tests.conftest import reauth, signed_in, sql


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


@pytest.fixture
def client(superuser):
    return signed_in("root@example.com")


def test_the_creation_route_refuses_and_says_why(client, projects):
    r = reauth(client).post("/api/projects", json={"name": "Manual"})
    assert r.status_code == 410
    error = r.json()["error"]
    assert error["code"] == "project_creation_removed"
    assert "Importar" in error["message"] or "import project" in error["message"]
    assert sql("SELECT count(*) FROM project")[0][0] == 0
    assert not projects.exists() or not any(projects.iterdir())


def test_the_slug_suggester_is_gone_with_the_form_it_fed(client):
    assert client.get("/api/projects/slug", params={"name": "Ventas"}).status_code == 404


def test_an_import_still_creates_a_project(client, projects):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("project.yaml", "name: Importado\nslug: importado\n")
        zf.writestr("specs/001-x/spec.md", "---\n**Tipo**: reporte\n**Status**: Approved\n")
    r = reauth(client).post("/api/projects/import", content=buffer.getvalue(),
                            headers={"Content-Type": "application/zip"})
    assert r.status_code == 200, r.text
    assert r.json()["project"]["slug"] == "importado"
    assert sql("SELECT count(*) FROM project")[0][0] == 1
    assert (projects / "importado" / "project.yaml").exists()


def test_export_validation_history_and_apply_keep_working(client, projects):
    """FR-009: removing creation must not disturb anything a stored project can do."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("project.yaml", "name: Vivo\nslug: vivo\n")
        zf.writestr("reports/ventas/report.yaml",
                    "id: ventas\nname: Ventas\ntitle: Ventas\nmetrics:\n  total: {sql: count(1)}\n")
    assert reauth(client).post("/api/projects/import", content=buffer.getvalue(),
                               headers={"Content-Type": "application/zip"}).status_code == 200
    assert client.get("/api/projects/vivo/tree").status_code == 200
    assert client.get("/api/projects/vivo/export.zip").content[:2] == b"PK"
    assert client.post("/api/projects/vivo/validate").status_code == 200
    assert client.get("/api/projects/vivo/history").status_code == 200
    assert client.get("/api/projects/vivo/changes").status_code == 200


def test_an_import_is_audited_as_a_creation_and_as_an_import(client, projects):
    """The service still records the project it creates; the import adds its own event on top.
    Removing the route did not remove the audit trail of a project coming into being."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("project.yaml", "name: Uno\nslug: uno\n")
    reauth(client).post("/api/projects/import", content=buffer.getvalue(),
                        headers={"Content-Type": "application/zip"})
    kinds = [k for (k,) in sql("SELECT kind FROM audit_event ORDER BY id")]
    assert "project_created" in kinds
    assert "project_imported" in kinds
    # ...and a refused manual creation creates nothing and audits nothing (the step-up is done
    # first, because confirming the password is itself an audit event).
    c = reauth(client)
    before = sql("SELECT count(*) FROM audit_event")[0][0]
    assert c.post("/api/projects", json={"name": "Manual"}).status_code == 410
    assert sql("SELECT count(*) FROM audit_event")[0][0] == before
    assert sql("SELECT count(*) FROM project")[0][0] == 1
