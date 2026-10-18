"""Feature 020 T039: agent draft tools on project files."""
from pathlib import Path

import pytest
from bizview_cli import layout

from app.assistant import readiness, service
from app.assistant.tools import ToolError, run_tool
from app.config import get_settings
from app.models import AppUser
from app.projects import fs, history
from app.projects import service as project_service
from app.projects.workview import for_session
from tests.conftest import sql

SPEC = "# Ventas\n\n**Tipo**: integracion\n**Status**: Draft\n\nVentas diarias.\n"
PLAN = "# Plan\n\nPlan de ventas.\n"
TASKS = "# Tasks\n\n- [ ] T001 Integración\n"
FILES = {
    "specs/001-ventas/spec.md": SPEC,
    "specs/001-ventas/plan.md": PLAN,
    "specs/001-ventas/tasks.md": TASKS,
}


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


@pytest.fixture(autouse=True)
def without_command_guard(monkeypatch):
    """020 write mechanics; the 021 command guard is covered by test_assistant_commands_*."""
    monkeypatch.setattr("app.assistant.commands.guard.check_tool", lambda *a, **k: None)
    monkeypatch.setattr("app.assistant.tools._guard_writes", lambda *a, **k: None)


@pytest.fixture
def chat(db, superuser):
    actor = db.get(AppUser, superuser.id)
    project = project_service.create(db, actor, "Ventas")
    db.commit()
    session = service.create_session(db, actor, project_id=project.id)
    db.commit()
    return project, session


def _run(db, superuser, view, name, args):
    return run_tool(db, db.get(AppUser, superuser.id), view, name, args, get_settings())


def _editor_save(project, superuser, path, old, new):
    fs.apply_ops(
        project.id,
        [{"op": "write", "path": path, "content": new, "base_sha256": history.sha(old),
          "force": False}],
        {"kind": "user", "user_id": superuser.id, "session_id": None, "command": "edit"},
    )


def _second_chat(db, superuser, project):
    session = service.create_session(db, db.get(AppUser, superuser.id), project_id=project.id)
    db.commit()
    return session


def test_agent_writes_record_agent_revisions(db, superuser, chat, projects):
    project, session = chat
    result, _ = _run(db, superuser, for_session(db, session), "propose_draft",
                     {"files": FILES, "summary": "ventas"})
    assert "valid" in result
    assert "specs/001-ventas/spec.md" in result["files"]
    assert (projects / project.slug / "specs/001-ventas/spec.md").read_text() == SPEC
    rows = sql("SELECT path, op, actor_kind, session_id, command FROM project_file_revision "
               "WHERE path LIKE 'specs/%' ORDER BY path")
    assert [tuple(r) for r in rows] == [
        (path, "create", "agent", session.id, "agent") for path in sorted(FILES)]


def test_overwrite_needs_a_read(db, superuser, chat, projects):
    project, session = chat
    spec_path = "specs/001-ventas/spec.md"
    view = for_session(db, session)
    _run(db, superuser, view, "propose_draft", {"files": FILES})
    spec2 = SPEC.replace("Draft", "Approved")
    # Same conversation: the shas it wrote are remembered, so it may overwrite its own file.
    _run(db, superuser, for_session(db, session), "propose_draft", {"files": {spec_path: spec2}})
    _editor_save(project, superuser, spec_path, spec2, spec2 + "Editado.\n")

    view2 = for_session(db, session)
    with pytest.raises(ToolError) as exc:
        _run(db, superuser, view2, "edit_draft",
             {"ops": [{"op": "write", "path": spec_path, "content": "Nuevo."}]})
    assert "cambió" in exc.value.message
    _run(db, superuser, view2, "edit_draft",
         {"ops": [{"op": "replace", "path": spec_path, "old": "Ventas diarias.",
                   "new": "Ventas por día."}]})
    content = (projects / project.slug / spec_path).read_text()
    assert "Ventas por día." in content
    assert "Editado." in content


def test_legacy_path_refused(db, superuser, chat):
    _, session = chat
    with pytest.raises(ToolError) as exc:
        _run(db, superuser, for_session(db, session), "propose_draft", {"files": {
            "specs/integrations/ventas/spec.md": SPEC,
            "integrations/ventas/integration.yaml": "id: ventas\n",
            "reports/r/report.yaml": "id: r\n",
        }})
    assert "specs/integrations/ventas/spec.md" in exc.value.message
    assert layout.ALLOWED_TEXT in exc.value.message
    assert sql("SELECT path FROM project_file_revision "
               "WHERE path LIKE 'specs/integrations/%'") == []


def test_read_after_editor_save(db, superuser, chat, projects):
    project, session = chat
    plan_path = "specs/001-ventas/plan.md"
    new_plan = "# Plan\n\nNuevo plan.\n"
    _run(db, superuser, for_session(db, session), "propose_draft", {"files": FILES})
    _editor_save(project, superuser, plan_path, PLAN, new_plan)

    view = for_session(db, session)
    result, _ = _run(db, superuser, view, "read_draft",
                     {"paths": [plan_path, "specs/009-x/spec.md"]})
    assert result["files"][plan_path] == new_plan
    assert result["missing"] == ["specs/009-x/spec.md"]
    _run(db, superuser, view, "edit_draft",
         {"ops": [{"op": "write", "path": plan_path, "content": "# Plan\n\nOtro.\n"}]})
    assert (projects / project.slug / plan_path).read_text() == "# Plan\n\nOtro.\n"


def test_delete_needs_a_read(db, superuser, chat, projects):
    project, session = chat
    tasks_path = "specs/001-ventas/tasks.md"
    _run(db, superuser, for_session(db, session), "propose_draft", {"files": FILES})

    view2 = for_session(db, _second_chat(db, superuser, project))
    with pytest.raises(ToolError) as exc:
        _run(db, superuser, view2, "edit_draft",
             {"ops": [{"op": "delete", "path": tasks_path}]})
    assert "leerlo" in exc.value.message
    _run(db, superuser, view2, "read_draft", {"paths": [tasks_path]})
    _run(db, superuser, view2, "edit_draft", {"ops": [{"op": "delete", "path": tasks_path}]})
    assert not (projects / project.slug / tasks_path).exists()


def test_readiness_same_from_two_conversations(db, superuser, chat):
    project, session = chat
    _run(db, superuser, for_session(db, session), "propose_draft", {"files": FILES})
    session2 = _second_chat(db, superuser, project)
    assert readiness.compute(for_session(db, session)) == readiness.compute(
        for_session(db, session2))


def test_probe_only_without_specs(db, superuser, chat, projects):
    project, session = chat
    path = "integrations/ventas/integration.yaml"
    on_disk: Path = projects / project.slug / path
    view = for_session(db, session)
    result, _ = _run(db, superuser, view, "propose_draft", {"files": {path: "id: ventas\n"}})
    assert result["probe"] is True
    assert not on_disk.exists()

    _run(db, superuser, view, "propose_draft", {"files": FILES})
    result, _ = _run(db, superuser, view, "propose_draft", {"files": {path: "id: ventas\n"}})
    assert "valid" in result
    assert on_disk.exists()
