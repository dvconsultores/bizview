"""Feature 021 T048 (SC-001): the nine commands in sequence on a new project, fake provider."""
from app.ai import fake
from app.projects import fs
from tests.conftest import sql
from tests.test_assistant_commands_service import _call, _reply, _send, _session
from tests.test_assistant_commands_service import chat as chat  # fixture
from tests.test_assistant_commands_service import fake_provider as fake_provider  # fixture

FOLDER = "specs/001-ventas"
SPEC = ("# Ventas por sucursal\n\n**Tipo**: reporte\n**Status**: Draft\n\n"
        "Ventas por sucursal y mes.\n")
CHECKLIST = "# Calidad\n\n- [ ] CHK001 ¿Métrica definida? [Spec §FR-001]\n"
PLAN = "# Plan\n\nReporte `reports/ventas/` sobre la base BI.\n"
TASKS = "# Tasks\n\n## Phase 1\n\n- [ ] T001 Crear reports/ventas/report.yaml\n"
DATA_CHECKLIST = "# Datos\n\n- [ ] CHK001 ¿Periodo definido? [Gap]\n"
REPORT = "id: ventas\n"


def _files(slug: str) -> dict[str, str]:
    listed, _ = fs.list_files(slug)
    return {p: fs.read_text(slug, p) for p in listed}


def _edit(ops: list[dict], call_id: str = "e1"):
    return _reply("", [_call("edit_draft", {"ops": ops}, call_id)])


def _finish(text: str = "Hecho."):
    return _reply(text, [_call("finish_command", {"summary": text}, "f1")])


def _revisions() -> list[tuple]:
    return [tuple(r) for r in sql("SELECT path, actor_kind, command, command_run_id "
                                  "FROM project_file_revision ORDER BY id")]


def _run_command(c, sid, text, *steps):
    fake.SHARED.queue(*steps)
    r = _send(c, sid, text)
    assert r.status_code == 202, r.text
    run = _session(c, sid)["command_runs"][0]
    assert run["command"] == text.split()[0][1:]
    return run


def test_nine_commands_in_sequence(chat, superuser):
    c, project, sid = chat
    slug = project["slug"]
    constitution_path = ".specify/memory/constitution.md"
    constitution = _files(slug)[constitution_path]

    run = _run_command(
        c, sid, "/speckit-constitution Las ventas se cuentan sin devoluciones",
        _reply("", [_call("read_draft", {"paths": [constitution_path]}, "r1")]),
        _edit([{"op": "write", "path": constitution_path,
                "content": constitution + "\n### VIII. Ventas netas\nSin devoluciones.\n"}]),
        _finish())
    assert run["status"] == "completed"
    assert "VIII. Ventas netas" in _files(slug)[constitution_path]

    run = _run_command(
        c, sid, "/speckit-specify Reporte de ventas por sucursal",
        _edit([{"op": "write", "path": f"{FOLDER}/spec.md", "content": SPEC},
               {"op": "write", "path": f"{FOLDER}/checklists/requirements.md",
                "content": CHECKLIST}]),
        _finish())
    assert (run["status"], run["spec"]) == ("completed", "001-ventas")
    assert _session(c, sid)["current_spec"] == "001-ventas"

    run = _run_command(
        c, sid, "/speckit-clarify",
        _edit([{"op": "replace", "path": f"{FOLDER}/spec.md", "old": "y mes.\n",
                "new": "y mes.\n\n## Clarifications\n\n### Session 2026-10-11\n\n"
                       "- Q: ¿Periodo? → A: mes calendario\n"}]),
        _finish())
    assert "## Clarifications" in _files(slug)[f"{FOLDER}/spec.md"]

    _run_command(c, sid, "/speckit-plan",
                 _edit([{"op": "write", "path": f"{FOLDER}/plan.md", "content": PLAN}]),
                 _finish())
    _run_command(c, sid, "/speckit-tasks",
                 _edit([{"op": "write", "path": f"{FOLDER}/tasks.md", "content": TASKS}]),
                 _finish())

    before = _revisions()
    run = _run_command(c, sid, "/speckit-analyze", _finish("Sin hallazgos críticos."))
    assert run["status"] == "completed" and run["files"] == []
    assert _revisions() == before
    assert "edit_draft" not in {t["name"] for t in fake.SHARED.requests[-1]["tools"]}

    _run_command(c, sid, "/speckit-checklist datos",
                 _edit([{"op": "write", "path": f"{FOLDER}/checklists/datos.md",
                         "content": DATA_CHECKLIST}]),
                 _finish())

    # implement: the unchecked checklists and the Draft status ask first (no provider call).
    requests = len(fake.SHARED.requests)
    _send(c, sid, "/speckit-implement")
    assert _session(c, sid)["active_command"]["pending"]["gate"] == "unchecked_checklists"
    _send(c, sid, "sí")
    assert _session(c, sid)["active_command"]["pending"]["gate"] == "approve_spec"
    assert len(fake.SHARED.requests) == requests
    fake.SHARED.queue(
        _edit([{"op": "write", "path": "reports/ventas/report.yaml", "content": REPORT}]),
        _edit([{"op": "replace", "path": f"{FOLDER}/tasks.md", "old": "- [ ] T001",
                "new": "- [X] T001"}], "e2"),
        _edit([{"op": "replace", "path": f"{FOLDER}/spec.md", "old": "**Status**: Approved",
                "new": "**Status**: Implemented"}], "e3"),
        _finish("Implementado; aplica con el botón Aplicar."),
    )
    _send(c, sid, "sí")
    run = _session(c, sid)["command_runs"][0]
    assert run["status"] == "completed"
    assert {f["path"] for f in run["files"]} == {
        f"{FOLDER}/spec.md", "reports/ventas/report.yaml", f"{FOLDER}/tasks.md"}
    files = _files(slug)
    assert "**Status**: Implemented" in files[f"{FOLDER}/spec.md"]
    assert "- [X] T001" in files[f"{FOLDER}/tasks.md"]

    tasks = files[f"{FOLDER}/tasks.md"]
    appended = tasks + "\n## Phase 2: Convergence\n\n- [ ] T002 Añadir filtro de sucursal\n"
    _run_command(c, sid, "/speckit-converge",
                 _edit([{"op": "write", "path": f"{FOLDER}/tasks.md", "content": appended}]),
                 _finish())
    assert _files(slug)[f"{FOLDER}/tasks.md"] == appended

    runs = _session(c, sid)["command_runs"]
    assert [r["command"] for r in reversed(runs)] == [
        "speckit-constitution", "speckit-specify", "speckit-clarify", "speckit-plan",
        "speckit-tasks", "speckit-analyze", "speckit-checklist", "speckit-implement",
        "speckit-converge"]
    assert all(r["status"] == "completed" for r in runs)
    run_ids = {r["command"]: r["id"] for r in runs}
    agent = [r for r in _revisions() if r[1] == "agent"]
    assert agent and all(cmd == f"/{name}" and run_id == run_ids[name]
                         for _path, _kind, cmd, run_id in agent
                         for name in [cmd[1:]])
    approved = [r for r in _revisions() if r[1] == "user" and r[2] == "/speckit-implement"]
    assert approved == [(f"{FOLDER}/spec.md", "user", "/speckit-implement",
                         run_ids["speckit-implement"])]


def test_converge_cannot_rewrite_tasks(chat, superuser):
    c, project, sid = chat
    from tests.test_assistant_commands_service import _with_spec
    _with_spec(c, project, sid, superuser, {f"{FOLDER}/spec.md": SPEC,
                                            f"{FOLDER}/plan.md": PLAN,
                                            f"{FOLDER}/tasks.md": TASKS})
    fake.SHARED.queue(
        _reply("", [_call("read_draft", {"paths": [f"{FOLDER}/tasks.md"]}, "r1")]),
        _edit([{"op": "write", "path": f"{FOLDER}/tasks.md", "content": "- [ ] T001 otra\n"}]),
        _finish())
    _send(c, sid, "/speckit-converge")
    data = _session(c, sid)
    refused = [m for m in data["messages"] if m.get("tool_name") == "edit_draft"]
    assert refused and f"{FOLDER}/tasks.md" in refused[0]["content"]
    assert _files(project["slug"])[f"{FOLDER}/tasks.md"] == TASKS
