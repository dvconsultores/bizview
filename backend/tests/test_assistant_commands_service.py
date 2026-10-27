"""Feature 021 T031-T035: commands in `start()`/`_turn()`, runs, guard, API and history."""
import pytest

from app.ai import ChatReply, ChatUsage, ToolCall, fake
from app.config import get_settings
from app.projects import fs
from tests.conftest import signed_in, sql

SPEC = "# Ventas\n\n**Tipo**: reporte\n**Status**: Draft\n\nVentas por sucursal.\n"


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    fake.SHARED.reset()
    yield
    fake.SHARED.reset()
    get_settings.cache_clear()


def _reply(text="", calls=()):
    return ChatReply(text=text, tool_calls=tuple(calls), usage=ChatUsage(input=10, output=5),
                     model="fake")


def _call(name, args, call_id="call-1"):
    return ToolCall(id=call_id, name=name, args=args)


@pytest.fixture
def chat(superuser):
    c = signed_in("root@example.com")
    project = c.post("/api/projects", json={"name": "Ventas"}).json()
    sid = c.post("/api/assistant/sessions", json={"project": project["slug"]}).json()["id"]
    return c, project, sid


def _send(c, sid, text):
    return c.post(f"/api/assistant/sessions/{sid}/messages", json={"text": text})


def _session(c, sid):
    return c.get(f"/api/assistant/sessions/{sid}").json()


def _write(project_id, files, user_id):
    fs.apply_ops(project_id, [{"op": "write", "path": p, "content": t, "base_sha256": None,
                               "force": False} for p, t in files.items()],
                 {"kind": "user", "user_id": user_id, "session_id": None, "command": "edit"})


def _with_spec(c, project, sid, superuser, files):
    _write(project["id"], files, superuser.id)
    r = c.patch(f"/api/assistant/sessions/{sid}", json={"current_spec": "001-ventas"})
    assert r.status_code == 200, r.text


def test_command_list(chat):
    c, _, _ = chat
    items = c.get("/api/assistant/commands").json()["items"]
    # 039: `/speckit-all` heads the menu; the authoring commands keep their 021 order.
    assert [i["name"] for i in items][:3] == ["speckit-all", "speckit-constitution",
                                              "speckit-specify"]
    assert "speckit-verify" in {i["name"] for i in items}
    assert all(i["description"] for i in items)
    assert next(i for i in items if i["name"] == "speckit-plan")["needs_spec"] is True


def test_help_and_parse_errors_cost_no_provider_call(chat):
    c, _, sid = chat
    r = _send(c, sid, "/ayuda")
    assert r.status_code == 202, r.text
    assert "/speckit-specify" in r.json()["messages"][-1]["content"]
    assert _send(c, sid, "/speckit-nada").json()["error"]["code"] == "unknown_command"
    assert _send(c, sid, "/speckit-specify").json()["error"]["code"] == "command_needs_args"
    r = _send(c, sid, "/speckit-plan")
    assert r.status_code == 409 and r.json()["error"]["code"] == "needs_spec"
    assert r.json()["error"]["specs"] == []
    assert fake.SHARED.requests == []
    runs = _session(c, sid)["command_runs"]       # 023: /ayuda is recorded, nothing else
    assert [(r["command"], r["status"], r["files"]) for r in runs] == [("ayuda", "completed", [])]


def test_missing_prerequisite_suggests_the_command(chat, superuser):
    c, project, sid = chat
    _with_spec(c, project, sid, superuser, {"specs/001-ventas/spec.md": SPEC})
    r = _send(c, sid, "/speckit-tasks")
    assert r.status_code == 202, r.text
    last = r.json()["messages"][-1]
    assert "plan.md" in last["content"] and "/speckit-plan" in last["content"]
    assert last["suggestions"] == [{"command": "speckit-plan", "arguments": "",
                                    "spec": "001-ventas"}]
    assert fake.SHARED.requests == []
    assert _session(c, sid)["active_command"] is None


def test_specify_writes_through_its_run(chat, superuser, monkeypatch):
    c, project, sid = chat
    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": "specs/001-ventas/spec.md", "content": SPEC}]})]),
        _reply("Spec creada.", [_call("finish_command", {"summary": "spec 001"}, "call-2")]),
    )
    r = _send(c, sid, "/speckit-specify Reporte de ventas por sucursal")
    assert r.status_code == 202, r.text
    first = fake.SHARED.requests[0]
    assert "\n\n## /speckit-specify\n" in first["system"]
    assert "## Comando" in first["context"] and "specs/001-<nombre-corto>/" in first["context"]
    assert {t["name"] for t in first["tools"]} >= {"edit_draft", "propose_draft",
                                                  "finish_command"}
    assert "suggest_command" not in {t["name"] for t in first["tools"]}
    assert len(fake.SHARED.requests) == 2

    data = _session(c, sid)
    assert data["current_spec"] == "001-ventas"
    assert data["active_command"] is None
    run = data["command_runs"][0]
    assert (run["command"], run["spec"], run["status"]) == ("speckit-specify", "001-ventas",
                                                           "completed")
    assert [f["path"] for f in run["files"]] == ["specs/001-ventas/spec.md"]
    assert run["tokens"] == 30
    rows = sql("SELECT actor_kind, command, command_run_id FROM project_file_revision "
               "WHERE path = 'specs/001-ventas/spec.md'")
    assert [tuple(r) for r in rows] == [("agent", "/speckit-specify", run["id"])]
    history = c.get(f"/api/projects/{project['slug']}/history").json()["items"]
    assert history[0]["command_run_id"] == run["id"]


def test_plain_message_cannot_write_and_may_suggest(chat):
    c, _, sid = chat
    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": "specs/001-ventas/spec.md", "content": SPEC}]}),
            _call("suggest_command", {"command": "speckit-specify", "arguments": "Ventas",
                                     "spec": ""},
                  "call-2")]),
        _reply("Usa el comando sugerido."),
    )
    r = _send(c, sid, "Crea la spec de ventas")
    assert r.status_code == 202, r.text
    assert "edit_draft" not in {t["name"] for t in fake.SHARED.requests[0]["tools"]}
    data = _session(c, sid)
    tool = next(m for m in data["messages"] if m.get("tool_name") == "edit_draft")
    assert "/speckit-" in tool["content"]
    assert data["messages"][-1]["suggestions"] == [{"command": "speckit-specify",
                                                    "arguments": "Ventas"}]
    assert sql("SELECT count(*) FROM project_file_revision WHERE path LIKE 'specs/%'")[0][0] == 0
    assert data["command_runs"] == []


def test_path_outside_the_command_is_refused(chat, superuser):
    c, project, sid = chat
    _with_spec(c, project, sid, superuser, {"specs/001-ventas/spec.md": SPEC})
    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": "specs/001-ventas/tasks.md", "content": "- [ ] T001 x\n"}]})]),
        _reply("No pude.", [_call("finish_command", {"summary": "nada"}, "call-2")]),
    )
    assert _send(c, sid, "/speckit-plan").status_code == 202
    data = _session(c, sid)
    tool = next(m for m in data["messages"] if m.get("tool_name") == "edit_draft")
    assert "specs/001-ventas/plan.md" in tool["content"]
    assert not (fs.project_root(project["slug"]) / "specs/001-ventas/tasks.md").exists()


def test_interactive_command_waits_and_terminar(chat, superuser):
    c, project, sid = chat
    _with_spec(c, project, sid, superuser, {"specs/001-ventas/spec.md": SPEC})
    fake.SHARED.queue(_reply("¿Qué periodo usamos? A) mes B) semana"))
    assert _send(c, sid, "/speckit-clarify").status_code == 202
    data = _session(c, sid)
    assert data["active_command"]["status"] == "waiting"
    r = _send(c, sid, "/speckit-plan")
    assert r.status_code == 409 and r.json()["error"]["code"] == "command_active"

    fake.SHARED.queue(_reply("Anotado; siguiente pregunta."))
    assert _send(c, sid, "B").status_code == 202
    assert "## /speckit-clarify" in fake.SHARED.requests[-1]["system"]
    assert _session(c, sid)["active_command"]["status"] == "waiting"

    r = c.post(f"/api/assistant/sessions/{sid}/command/finish")
    assert r.status_code == 200, r.text
    assert r.json()["active_command"] is None
    assert r.json()["command_runs"][0]["status"] == "completed"
    r = c.post(f"/api/assistant/sessions/{sid}/command/finish")
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_active_command"


def test_implement_gate_approves_the_spec(chat, superuser):
    c, project, sid = chat
    _with_spec(c, project, sid, superuser, {
        "specs/001-ventas/spec.md": SPEC, "specs/001-ventas/plan.md": "# Plan\n",
        "specs/001-ventas/tasks.md": "- [ ] T001 Reporte\n"})
    r = _send(c, sid, "/speckit-implement")
    assert r.status_code == 202, r.text
    assert "Draft" in r.json()["messages"][-1]["content"]
    assert fake.SHARED.requests == []
    assert _session(c, sid)["active_command"]["pending"]["gate"] == "approve_spec"

    fake.SHARED.queue(_reply("Listo.", [_call("finish_command", {"summary": "ok"})]))
    assert _send(c, sid, "sí").status_code == 202
    spec = (fs.project_root(project["slug"]) / "specs/001-ventas/spec.md").read_text()
    assert "**Status**: Approved" in spec
    rows = sql("SELECT actor_kind, actor_id, command FROM project_file_revision "
               "WHERE path = 'specs/001-ventas/spec.md' ORDER BY id DESC LIMIT 1")
    assert tuple(rows[0]) == ("user", superuser.id, "/speckit-implement")
    assert len(fake.SHARED.requests) == 1
    assert _session(c, sid)["command_runs"][0]["status"] == "completed"


def test_gate_no_cancels(chat, superuser):
    c, project, sid = chat
    _with_spec(c, project, sid, superuser, {
        "specs/001-ventas/spec.md": SPEC.replace("Ventas por", "[NEEDS CLARIFICATION: x] Ventas"),
        "specs/001-ventas/plan.md": "# Plan\n"})
    _send(c, sid, "/speckit-tasks")
    assert _session(c, sid)["active_command"]["pending"]["gate"] == "open_clarifications"
    r = _send(c, sid, "no")
    assert r.json()["messages"][-1]["content"] == "Comando cancelado."
    data = _session(c, sid)
    assert data["active_command"] is None
    assert data["command_runs"][0]["status"] == "interrupted"
    assert fake.SHARED.requests == []


def test_stop_interrupts_the_running_command(chat, db):
    from app.assistant import service
    from app.assistant.commands import registry, runs
    from app.models import AssistantSession

    _, project, sid = chat
    session = db.get(AssistantSession, sid)
    run = runs.create(db, session_id=sid, project_id=project["id"],
                      definition=registry.REGISTRY["speckit-plan"], arguments="",
                      locale="es", spec="001-ventas")
    sql(f"UPDATE assistant_session SET busy_since = now() WHERE id = {sid}")
    db.commit()
    db.refresh(session)
    service.stop(db, session, get_settings())
    db.commit()
    db.refresh(run)
    assert run.status == "interrupted" and run.ended_at is not None


def test_interrupted_implement_resumes_without_losing_files(chat, superuser, monkeypatch):
    c, project, sid = chat
    _with_spec(c, project, sid, superuser, {
        "specs/001-ventas/spec.md": SPEC.replace("Draft", "Approved"),
        "specs/001-ventas/plan.md": "# Plan\n",
        "specs/001-ventas/tasks.md": "- [ ] T001 Reporte\n- [ ] T002 Comprobar\n"})
    monkeypatch.setattr(get_settings(), "ai_chat_max_rounds", 1)
    report = "reports/ventas/report.yaml"
    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": report, "content": "id: ventas\n"}]})]),
        _reply("Escribí el reporte; falta comprobarlo."),
    )
    r = _send(c, sid, "/speckit-implement")
    assert r.status_code == 202, r.text
    data = _session(c, sid)
    first = data["command_runs"][0]
    assert first["status"] == "interrupted"
    assert [f["path"] for f in first["files"]] == [report]
    last = data["messages"][-1]
    assert "/speckit-implement" in last["content"]
    assert last["suggestions"] == [{"command": "speckit-implement", "arguments": "",
                                    "spec": "001-ventas"}]
    assert (fs.project_root(project["slug"]) / report).read_text() == "id: ventas\n"

    monkeypatch.setattr(get_settings(), "ai_chat_max_rounds", 4)
    fake.SHARED.queue(_reply("Listo.", [_call("finish_command", {"summary": "ok"})]))
    assert _send(c, sid, "/speckit-implement").status_code == 202
    context = fake.SHARED.requests[-1]["context"]
    assert "Reanudación" in context and f"Archivos ya escritos: {report}" in context
    runs = _session(c, sid)["command_runs"]
    assert runs[0]["status"] == "completed"
    assert sql("SELECT resumed_from FROM assistant_command_run WHERE id = :i",
               i=runs[0]["id"])[0][0] == first["id"]
    assert sql("SELECT count(*) FROM project_file_revision WHERE path = :p", p=report)[0][0] == 1
