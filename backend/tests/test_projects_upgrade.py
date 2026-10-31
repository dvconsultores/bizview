"""Feature 020 T077: upgrade of an existing installation (the `principal` project)."""
import shutil

import pytest
import yaml
from sqlalchemy import select

from app.config import get_settings
from app.models import Project
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

