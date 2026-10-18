"""Feature 020 T045: spec numbering, kind and stage."""
import pytest

from app.config import get_settings
from app.models import Project
from app.projects import fs, history
from app.projects.specs import list_specs, parse_spec, stage
from tests.conftest import sql


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


@pytest.fixture
def project(db):
    proj = Project(slug="demo", name="Demo")
    db.add(proj)
    db.commit()
    return proj


def actor(command="edit"):
    return {"kind": "user", "user_id": None, "session_id": None, "command": command}


def w(path, content, base=None):
    return {"op": "write", "path": path, "content": content, "base_sha256": base, "force": False}


def write(project, *ops, command="edit"):
    return fs.apply_ops(project.id, list(ops), actor(command))


def test_numbering_never_reused(project):
    write(project, w("specs/001-a/spec.md", "# A\n"))
    with pytest.raises(fs.ProjectPathError) as exc:
        write(project, w("specs/003-c/spec.md", "# C\n"))
    assert exc.value.code == "spec_number"
    write(project, {"op": "rmdir", "path": "specs/001-a"})
    with pytest.raises(fs.ProjectPathError) as exc:
        write(project, w("specs/001-a/spec.md", "# A\n"))
    assert exc.value.code == "spec_number"
    write(project, w("specs/002-b/spec.md", "# B\n"))
    assert sql("SELECT spec_seq FROM project WHERE id = :i", i=project.id)[0][0] == 2


@pytest.mark.parametrize(("line", "expected"), [
    ("**Tipo**: integracion", "integracion"),
    ("**Type**: report", "reporte"),
    ("**Tipo**: Distribución", "distribucion"),
    ("**Type**: source", "fuente"),
    ("**Spec type**: integration", "integracion"),
    ("Sin tipo", None),
])
def test_kind_aliases(line, expected):
    assert parse_spec(f"# T\n\n{line}\n")["kind"] == expected


def _stage(files, applied=None, sources=None, clarify_revision=False, folder="001-ventas"):
    return stage(folder, files, applied=applied, sources=sources or {},
                 clarify_revision=clarify_revision)


def test_stages_in_order():
    spec = "specs/001-ventas/spec.md"
    base = "# Ventas\n\n**Tipo**: integracion\n"
    files = {spec: base}
    assert _stage(files)["stage"] == "especificada"
    files[spec] = base + "\n## Clarifications\n\n- Q: … → A: …\n"
    assert _stage(files)["stage"] == "especificada"
    files[spec] = (base + "\n## Clarifications\n\n### Session 2026-10-01\n\n"
                   "- Q: ¿Qué moneda? → A: USD\n\n## Otra\n")
    assert _stage(files)["stage"] == "aclarada"
    files[spec] = base
    assert _stage(files, clarify_revision=True)["stage"] == "aclarada"
    files["specs/001-ventas/plan.md"] = "# Plan\n"
    assert _stage(files)["stage"] == "planificada"
    files["specs/001-ventas/tasks.md"] = "- [ ] T001 x\n"
    assert _stage(files)["stage"] == "tareas"
    files[spec] = base + "**Status**: Approved\n"
    files["specs/001-ventas/tasks.md"] = "- [x] T001 x\n"
    assert _stage(files)["stage"] == "tareas"

    files["integrations/ventas/integration.yaml"] = (
        "id: ventas\nspec: specs/001-ventas\nsource: origen\n")
    result = _stage(files)
    assert result["stage"] == "implementada"
    assert result["linked"] == {"integracion": ["integrations/ventas/integration.yaml"]}
    applied = {p: history.sha(t) for p, t in files.items()}
    assert _stage(files, applied=applied)["stage"] == "aplicada"
    files["specs/001-ventas/plan.md"] = "# Plan v2\n"
    assert _stage(files, applied=applied)["stage"] == "implementada"


def test_fuente_stage():
    files = {
        "specs/002-origen/spec.md": ("# Origen\n\n**Tipo**: fuente\n**Status**: Approved\n"
                                     "**Fuente**: Origen ERP\n**Tipo de fuente**: supabase\n"),
        "specs/002-origen/plan.md": "# Plan\n",
        "specs/002-origen/tasks.md": "- [x] T001 x\n",
    }
    result = _stage(files, folder="002-origen")
    assert result["stage"] == "tareas"
    assert result["source_missing"] == {"source": "Origen ERP",
                                        "link": "/admin/fuentes/nueva?kind=supabase"}
    assert _stage(files, sources={"origen erp": False}, folder="002-origen")["stage"] == "tareas"
    result = _stage(files, sources={"origen erp": True}, folder="002-origen")
    assert result["stage"] == "implementada"
    assert "source_missing" not in result


def test_converged_badge_and_list(project, db):
    tasks = "specs/001-a/tasks.md"
    first, second = "- [x] T001 a\n", "- [x] T001 a\n- [ ] T002 b\n"
    write(project, w("specs/001-a/spec.md", "# A\n\n**Tipo**: reporte\n"),
          w("specs/001-a/plan.md", "# Plan\n"), w(tasks, first))
    write(project, w(tasks, second, history.sha(first)), command="/speckit-converge")
    item = list_specs(db, project)[0]
    assert (item["folder"], item["number"], item["kind"], item["stage"], item["converged"]) == (
        "001-a", 1, "reporte", "tareas", True)
    write(project, w(tasks, "- [x] T001 a\n- [x] T002 b\n", history.sha(second)))
    assert list_specs(db, project)[0]["converged"] is False
