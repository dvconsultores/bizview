"""Feature 039: `/speckit-all` through the API — the mode gate, the plan order and the report."""
import pytest
from sqlalchemy import text as sa_text

from app.ai import fake
from app.config import get_settings
from app.projects import fs
from tests.conftest import PASSWORD, new_chat, signed_in
from tests.test_assistant_api import _chat_reply, _tool_call
from tests.test_assistant_auto_mode import _send
from tests.test_assistant_commands_service import _with_spec
from tests.test_assistant_commands_service import chat as chat  # fixture


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


BRIEF = "Un tablero de facturas por día y estado, con PDF"

SPEC = ("# Facturas por día\n\n**Tipo**: reporte\n**Status**: Draft\n\n"
        "Facturas por día y estado.\n")
CLARIFIED = SPEC.replace(
    "Facturas por día y estado.\n",
    "Facturas por día y estado.\n\n## Clarifications\n\n- ¿Periodo? → A: día calendario\n\n"
    "## Decisiones tomadas (modo autónomo)\n\n"
    "- [clarify] Se agrupa por día — es el orden de las historias de la spec.\n")
PLAN = "# Plan\n\nReporte `reports/facturas/` sobre la base BI.\n"
TASKS = "# Tasks\n\n## Phase 1\n\n- [ ] T001 Crear reports/facturas/report.yaml\n"


def _write(path, content, call_id):
    return _chat_reply(tool_calls=[_tool_call("edit_draft",
                                              {"ops": [{"op": "write", "path": path,
                                                        "content": content}]}, call_id)],
                       stop_reason="tool_use")


def _open(command, spec=None, call_id="rc"):
    args = {"command": command}
    if spec:
        args["spec"] = spec
    return _chat_reply(tool_calls=[_tool_call("run_command", args, call_id)],
                       stop_reason="tool_use")

def _finish(text="Etapa hecha.", call_id="f1"):
    return _chat_reply(text, tool_calls=[_tool_call("finish_command", {"summary": text}, call_id)],
                       stop_reason="tool_use")


def _text(text="Listo."):
    return _chat_reply(text)


def test_in_ask_it_offers_the_switch_and_starts_nothing(superuser):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "ask"})
    body = _send(client, sid, f"/speckit-all {BRIEF}")
    assert "Pasar a Auto" in body["messages"][-1]["content"]
    assert body["command_runs"] == []
    assert fake.SHARED.requests == []


def test_until_is_validated_before_any_run(superuser):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    r = client.post(f"/api/assistant/sessions/{sid}/messages",
                    json={"text": f"/speckit-all {BRIEF} --until nope"})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "until_invalid"
    assert "verify" in r.json()["error"]["message"]


def test_the_plan_is_created_and_cannot_be_jumped(superuser):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    fake.SHARED.queue(
        _open("speckit-plan", call_id="rc1"),          # not the plan's next stage
        _open("speckit-all", call_id="rc2"),           # never inside a plan
        _open("speckit-specify", call_id="rc3"),
        _text())
    body = _send(client, sid, f"/speckit-all {BRIEF} --until tasks")
    runs = body["command_runs"]
    assert runs[-1]["command"] == "speckit-all"
    assert runs[-1]["arguments"] == BRIEF                 # the flags are not part of the brief
    assert runs[0]["command"] == "speckit-specify"
    assert runs[0]["pipeline"]["cursor"] == 1             # specify opened, clarify is next
    assert runs[0]["pipeline"]["until"] == "tasks"
    results = [m["content"] for m in body["messages"] if m["role"] == "tool"]
    assert any("/speckit-specify" in str(r) for r in results)
    commands = [run["command"] for run in runs]
    assert "speckit-plan" not in commands                 # refused, so never opened
    assert "speckit-specify" in commands


def test_the_plan_runs_to_the_dry_run_and_writes_the_report(superuser):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    project = client.get(f"/api/assistant/sessions/{sid}").json()["project"]
    folder = "001-facturas"
    fake.SHARED.queue(
        _open("speckit-specify", call_id="s1"),
        _write(f"specs/{folder}/spec.md", SPEC, "w1"),
        _write(f"specs/{folder}/checklists/requirements.md", "# Calidad\n\n- [X] CHK001 Hecho\n",
               "w2"),
        _finish("Spec escrita.", "f1"),
        _open("speckit-clarify", call_id="s2"),
        _write(f"specs/{folder}/spec.md", CLARIFIED, "w3"),
        _finish("Aclarada.", "f2"),
        _open("speckit-plan", call_id="s3"),
        _write(f"specs/{folder}/plan.md", PLAN, "w4"),
        _finish("Plan listo.", "f3"),
        _open("speckit-tasks", call_id="s4"),
        _write(f"specs/{folder}/tasks.md", TASKS, "w5"),
        _finish("Tareas listas.", "f4"),
        _text(),
    )
    body = _send(client, sid, f"/speckit-all {BRIEF} --until tasks")
    text = fs.read_text(project["slug"], f"specs/{folder}/run-report.md")
    assert "## Stages" in text
    for stage in ("specify", "clarify", "plan", "tasks"):
        assert f"| {stage} |" in text
    assert "analyze" not in text.split("## Decisiones tomadas")[0]
    # SC-005: the decision the clarify stage recorded is the one the report shows.
    assert ("- [clarify] Se agrupa por día — es el orden de las historias de la spec."
            in text)
    assert ("- [clarify] Se agrupa por día — es el orden de las historias de la spec."
            in fs.read_text(project["slug"], f"specs/{folder}/spec.md"))
    # SC-003: the only thing left for the human is applying.
    pending = text.split("## Pendiente para el humano")[-1]
    assert "Aplicar" in pending and "instruc" not in pending.lower()
    cards = [m for m in body["messages"] if m.get("run_report")]
    assert cards and cards[-1]["run_report"]["path"].endswith("run-report.md")
    assert cards[-1]["run_report"]["pending"] == ["Aplicar (el contrato no permite `apply`)."]


BUILT = {
    "specs/001-ventas/spec.md": ("# Ventas\n\n**Tipo**: reporte\n**Status**: Draft\n\n"
                                 "Ventas por sucursal.\n"),
    "specs/001-ventas/plan.md": "# Plan\n\nReporte `reports/ventas/`.\n",
    "specs/001-ventas/tasks.md": "# Tasks\n\n## Phase 1\n\n- [ ] T001 Crear el reporte\n",
}


def test_analyze_reopens_the_stage_that_fixes_but_cannot_jump(superuser):
    """US2 AC3: analyze writes nothing, so it goes back to the stage that owns the file."""
    client = signed_in("root@example.com")
    sid = new_chat(client)
    project = client.get(f"/api/assistant/sessions/{sid}").json()["project"]
    _with_spec(client, project, sid, superuser, BUILT)
    fake.SHARED.queue(
        _open("speckit-analyze", call_id="a1"),
        _open("speckit-verify", call_id="a2"),        # a jump, not a repair: refused
        _open("speckit-implement", call_id="a3"),     # the repair analyze may open
        _text())
    body = _send(client, sid, "/speckit-all 001-ventas")
    commands = [run["command"] for run in body["command_runs"]]
    assert "speckit-analyze" in commands
    assert "speckit-implement" in commands
    assert "speckit-verify" not in commands            # refused: not the plan's next stage


# --------------------------------------------------------------------------- stops and resume

def _contract(client, sid, limits):
    return client.post(f"/api/assistant/sessions/{sid}/contract",
                       json={"contract": {"goal": "el recorrido", "stages": ["draft", "preview"],
                                          "limits": limits},
                             "password": PASSWORD})


def test_a_token_limit_stops_the_plan_keeps_the_files_and_can_resume(chat, superuser, db):
    """US3 AC1 / SC-004 / T044: a spent contract stops the run where it is, with the report."""
    from app.ai import ChatUsage
    from app.assistant.commands import pipeline

    client, project, sid = chat
    _with_spec(client, project, sid, superuser, BUILT)
    client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "auto"})
    assert _contract(client, sid, {"tokens": 10_000}).status_code == 201

    # One reply that alone spends more than the contract allows, opening the analyze stage.
    from app.ai import ChatReply

    fake.SHARED.queue(ChatReply(
        text="", tool_calls=(_tool_call("run_command", {"command": "speckit-analyze"}, "rc1"),),
        usage=ChatUsage(input=12_000, output=100), model="fake", stop_reason="tool_use"))
    body = _send(client, sid, "/speckit-all 001-ventas")

    report = fs.read_text(project["slug"], "specs/001-ventas/run-report.md")
    assert "**Result**: stopped · limit:tokens" in report
    # Everything written before the stop is still there: nothing was rolled back.
    assert "Ventas por sucursal" in fs.read_text(project["slug"], "specs/001-ventas/spec.md")
    # The stage that was cut short is the one a resume repeats, not the one after it.
    state = pipeline.state_of(db, sid)
    assert pipeline.open_stage(state) == ("001-ventas", "analyze")
    cards = [m for m in body["messages"] if m.get("run_report")]
    assert cards and cards[-1]["run_report"]["result"] == "stopped"
    assert cards[-1]["run_report"]["stop_reason"] == "limit:tokens"


def test_detener_writes_the_report_and_resumes_at_the_same_stage(chat, superuser, db):
    """US3 AC2 / T040: "Detener" ends the plan cooperatively, with the report and the cursor."""
    from app.assistant import service
    from app.assistant.commands import pipeline, registry, runs
    from app.config import get_settings
    from app.models import AssistantSession

    c, project, sid = chat
    _with_spec(c, project, sid, superuser, BUILT)
    session = db.get(AssistantSession, sid)
    plan = pipeline.seed(None, None, ["001-ventas"])
    run = runs.create(db, session_id=sid, project_id=project["id"],
                      definition=registry.REGISTRY["speckit-implement"], arguments="",
                      locale="es", spec="001-ventas", pipeline=plan)
    run.result = {**(run.result or {}),
                  pipeline.PIPELINE_KEY: {**plan, "id": run.id, "cursor": 5,
                                          "specs": ["001-ventas"]}}
    db.execute(sa_text(f"UPDATE assistant_session SET busy_since = now() WHERE id = {sid}"))
    db.commit()
    db.refresh(session)

    service.stop(db, session, get_settings())
    db.commit()
    db.refresh(run)

    assert run.status == "interrupted"
    report = fs.read_text(project["slug"], "specs/001-ventas/run-report.md")
    assert "**Result**: stopped · stopped:user" in report
    state = pipeline.state_of(db, sid)
    # The implement run never finished, so a resume repeats implement — not converge.
    assert pipeline.open_stage(state) == ("001-ventas", "implement")
