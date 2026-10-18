"""Feature 020 T077: upgrade of an existing installation (principal, open drafts)."""
import shutil

import pytest
import yaml
from sqlalchemy import select

from app.config import get_settings
from app.models import AssistantSession, Project
from app.projects import importer
from app.projects import service as project_service
from app.workspace.service import active
from tests.conftest import sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


def _backfilled(origin_value: str) -> int:
    """The row migration 0018 inserts on an upgraded installation (no files yet)."""
    return sql("INSERT INTO project (slug, name, origin) VALUES ('principal', 'Principal', "
               ":o) RETURNING id", o=origin_value)[0][0]


def test_ensure_principal_imports_the_applied_workspace(applied, db, projects):
    # The Git apply of the fixture already mirrored `principal`: start from a fresh upgrade.
    sql("DELETE FROM project_file_revision")
    sql("DELETE FROM project")
    shutil.rmtree(projects / "principal", ignore_errors=True)
    _backfilled("git")
    db.expire_all()

    assert importer.ensure_principal(db) is True
    db.commit()
    base = projects / "principal"
    assert (base / "project.yaml").exists()
    assert (base / ".specify/memory/constitution.md").exists()
    spec = (base / "specs/001-ventas-prueba/spec.md").read_text()
    assert "**Tipo**: integracion" in spec
    assert (base / "specs/002-ventas/spec.md").exists()
    assert "spec: specs/001-ventas-prueba" in (
        base / "integrations/ventas-prueba/integration.yaml").read_text()

    version = active(db)   # SC-005: definitions (without spec) and files unchanged
    for group, kind in (("integrations", "integration"), ("reports", "report")):
        for rid, entry in version.artifacts[group].items():
            disk = yaml.safe_load((base / group / rid / f"{kind}.yaml").read_text())
            disk.pop("spec")
            assert disk == {k: v for k, v in entry["definition"].items() if k != "spec"}
            for rel, text in entry["files"].items():
                assert (base / group / rid / rel).read_text() == text

    project = db.scalar(select(Project).where(Project.slug == "principal"))
    assert project.imported_at is not None
    assert project.spec_seq == 2
    assert project_service.status(db, project)[0] == "aplicado"
    assert importer.ensure_principal(db) is False
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'project_imported'")[0][0] == 1


def test_open_drafts_become_projects(db, superuser, projects):
    session = AssistantSession(
        title="Ventas mensuales", created_by=superuser.id, project_id=_backfilled("app"),
        read_only=True, status="open", token_budget=100000,
        draft={"summary": "s", "files": {
            "specs/integrations/003-ventas-m/spec.md":
                "# V\n\n**Spec type**: integration\n\n**Status**: Draft\n",
            "integrations/ventas-m/integration.yaml":
                "id: ventas-m\nspec: specs/integrations/003-ventas-m\n",
            "integrations/ventas-m/queries/a.sql": "SELECT 1\n",
            "bizview.yaml": "name: x\n",
        }})
    db.add(session)
    db.commit()

    assert importer.import_open_drafts(db) == 1
    db.commit()
    db.refresh(session)
    new = db.get(Project, session.project_id)
    assert (new.name, new.slug) == ("Ventas mensuales (borrador)", "ventas-mensuales-borrador")
    assert session.read_only is False
    base = projects / new.slug
    assert "**Tipo**: integracion" in (base / "specs/001-ventas-m/spec.md").read_text()
    assert "spec: specs/001-ventas-m" in (
        base / "integrations/ventas-m/integration.yaml").read_text()
    assert (base / "integrations/ventas-m/queries/a.sql").read_text() == "SELECT 1\n"
    assert not (base / "bizview.yaml").exists()
    assert importer.import_open_drafts(db) == 0
