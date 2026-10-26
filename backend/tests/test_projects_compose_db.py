"""Feature 020 T049: composition with the active version (DB)."""
from textwrap import dedent

import pytest

from app.config import get_settings
from app.models import AppUser
from app.projects import fs
from app.projects import service as project_service
from app.projects.compose import validate_project, version_projects
from app.workspace.service import active
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture
from tests.workspace_fixture import integration_yaml

SPEC = "# Ventas\n\n**Tipo**: integracion\n**Status**: Approved\n"


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))


def _demo(db, superuser, integration_path, integration_text):
    project = project_service.create(db, db.get(AppUser, superuser.id), "Demo")
    db.commit()
    files = {"specs/001-ventas/spec.md": SPEC, "specs/001-ventas/plan.md": "# Plan\n",
             "specs/001-ventas/tasks.md": "- [x] T001 a\n", integration_path: integration_text}
    fs.apply_ops(project.id, [
        {"op": "write", "path": p, "content": c, "base_sha256": None, "force": False}
        for p, c in files.items()
    ], {"kind": "user", "user_id": None, "session_id": None, "command": "edit"})
    return project


def test_legacy_version_is_principal(applied, db):
    trees = version_projects(active(db))
    assert "principal" in trees
    assert "integrations/ventas-prueba/integration.yaml" in trees["principal"]


def test_duplicate_id_is_published_on_the_project_that_owns_the_file(applied, db, superuser):
    """Feature 037: the collision is real (it blocks the composition) but it is *principal's* file
    that the validator flags, so it is reported as another project's problem and never as a fixable
    entry of demo."""
    valid = dedent(integration_yaml()).lstrip().replace(
        "spec: specs/integrations/001-ventas-prueba", "spec: specs/001-ventas")
    project = _demo(db, superuser, "integrations/ventas-prueba/integration.yaml", valid)
    result = validate_project(db, project)
    assert result["other_projects"].get("principal", {}).get("errors", 0) >= 1
    assert not any(e["code"] == "duplicate_id" for e in result["errors"])
    assert result["composed_valid"] is False


def test_problem_mapped_to_file_and_line(db, superuser):
    project = _demo(db, superuser, "integrations/ventas/integration.yaml",
                    "id: ventas\nspec: specs/001-ventas\nsource: Origen prueba\ndatasets: 5\n")
    mine = [e for e in validate_project(db, project)["errors"]
            if e.get("file") == "integrations/ventas/integration.yaml"]
    assert mine
    assert all(e["project"] == "demo" for e in mine)
    assert any(isinstance(e["line"], int) and e["line"] >= 1 for e in mine)
