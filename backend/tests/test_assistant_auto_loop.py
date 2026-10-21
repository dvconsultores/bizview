"""Feature 028: the Auto loop — stage switch, summary, blocked endings (FR-004, FR-004b, FR-006)."""
import pytest

from app.ai import ChatReply, ChatUsage, ToolCall, fake
from app.assistant import auto, service
from app.config import get_settings
from app.projects import fs
from tests.conftest import PASSWORD, signed_in, sql

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


def _send(c, sid, text="hazlo"):
    return c.post(f"/api/assistant/sessions/{sid}/messages", json={"text": text})


def _session(c, sid):
    return c.get(f"/api/assistant/sessions/{sid}").json()


def _write(project_id, files, user_id):
    fs.apply_ops(project_id, [{"op": "write", "path": p, "content": t, "base_sha256": None,
                               "force": False} for p, t in files.items()],
                 {"kind": "user", "user_id": user_id, "session_id": None, "command": "edit"})


def _confirm(c, sid, contract):
    r = c.post(f"/api/assistant/sessions/{sid}/contract",
               json={"contract": contract, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()


def test_auto_run_ends_with_the_summary_and_the_contract_closed(chat):
    c, project, sid = chat
    _write(project["id"], {"specs/001-ventas/spec.md": SPEC}, 1)
    _confirm(c, sid, {"goal": "reporte de ventas", "stages": ["draft", "preview"]})

    fake.SHARED.queue(_reply("Escribo la spec."), _reply("Nada más que hacer."))
    assert _send(c, sid).status_code == 202

    body = _session(c, sid)
    last = body["messages"][-1]
    assert "Resumen del run" in last["content"]
    assert body["contract_status"] == "stopped"
    assert body["mode"] == "auto"                    # the mode stays; the contract is spent
    row = sql("SELECT status, summary IS NOT NULL FROM assistant_auto_run WHERE session_id = :i",
              i=sid)
    assert row == [("stopped", True)]
    assert sql("SELECT kind FROM audit_event WHERE kind = 'assistant_run_stopped'")


def test_auto_never_claims_applied_without_a_version(chat):
    c, project, sid = chat
    _write(project["id"], {"specs/001-ventas/spec.md": SPEC}, 1)
    _confirm(c, sid, {"goal": "x", "stages": ["draft", "preview"]})
    fake.SHARED.queue(_reply("Listo."))
    _send(c, sid)
    row = sql("SELECT status, stop_reason FROM assistant_auto_run WHERE session_id = :i", i=sid)
    assert row == [("stopped", "completed")]         # never `applied` without a version


def test_run_command_switches_the_stage_and_records_a_command_run(chat):
    c, project, sid = chat
    _write(project["id"], {"specs/001-ventas/spec.md": SPEC}, 1)
    _confirm(c, sid, {"goal": "x", "stages": ["draft"]})

    fake.SHARED.queue(
        _reply(calls=[_call("run_command", {"command": "speckit-plan", "spec": "001-ventas"})]),
        _reply("Sigo con el plan."))
    assert _send(c, sid).status_code == 202

    runs = sql("SELECT command, spec, resolved_from, status FROM assistant_command_run "
               "WHERE session_id = :i ORDER BY id", i=sid)
    assert runs and runs[-1][0] == "speckit-plan" and runs[-1][1] == "001-ventas"
    assert runs[-1][2] == "argument"
    stage = sql("SELECT stage FROM assistant_auto_run WHERE session_id = :i", i=sid)
    assert stage == [("plan",)]


def test_run_command_without_a_spec_fails_loudly(chat):
    c, _project, sid = chat
    _confirm(c, sid, {"goal": "x", "stages": ["draft"]})
    fake.SHARED.queue(
        _reply(calls=[_call("run_command", {"command": "speckit-plan"})]),
        _reply("No hay spec."))
    _send(c, sid)
    tool = next(m for m in _session(c, sid)["messages"] if m["role"] == "tool")
    assert "spec" in tool["content"].lower()


def test_auto_chains_the_next_stage_after_finish_command(chat):
    """FR-004: a finished stage does not end the run — the agent opens the next one itself.

    This is the reported defect: after `/speckit-plan` the conversation waited for another message.
    """
    c, project, sid = chat
    _write(project["id"], {"specs/001-ventas/spec.md": SPEC,
                           "specs/001-ventas/plan.md": "# Plan\n\nPlan de ventas.\n"}, 1)
    _confirm(c, sid, {"goal": "x", "stages": ["draft", "preview"]})

    fake.SHARED.queue(
        _reply(calls=[_call("run_command", {"command": "speckit-plan", "spec": "001-ventas"})]),
        _reply(calls=[_call("finish_command", {"summary": "Plan escrito."})]),
        _reply(calls=[_call("run_command", {"command": "speckit-tasks", "spec": "001-ventas"})]),
        _reply(calls=[_call("finish_command", {"summary": "Tareas escritas."})]),
        _reply("Todo listo."))
    assert _send(c, sid).status_code == 202

    body = _session(c, sid)
    runs = sql("SELECT command, status FROM assistant_command_run WHERE session_id = :i "
               "ORDER BY id", i=sid)
    assert [row[0] for row in runs] == ["speckit-plan", "speckit-tasks"]
    assert all(row[1] == "completed" for row in runs)
    nudges = [m["content"] for m in body["messages"]
              if m["role"] == "assistant" and m.get("content")
              and "terminada" in m["content"].lower()]
    assert len(nudges) == 2                       # one per closed stage, no question to the user
    assert "Resumen del run" in body["messages"][-1]["content"]


def test_auto_blocked_reason_flags_instructions_to_the_human():
    assert service.auto_blocked_reason("Perfecto. Ahora pulsa Aplicar para terminar.") is not None
    assert service.auto_blocked_reason("Selecciona la spec 002 en el encabezado.") is not None
    assert service.auto_blocked_reason("Now select the spec 002.") is not None
    assert service.auto_blocked_reason("Press the Apply button.") is not None
    assert service.auto_blocked_reason("Apliqué la versión 3; todo correcto.") is None
    assert service.auto_blocked_reason("") is None


def test_a_blocked_ending_is_stored_and_never_applied(chat):
    c, project, sid = chat
    _write(project["id"], {"specs/001-ventas/spec.md": SPEC}, 1)
    _confirm(c, sid, {"goal": "x", "stages": ["draft", "preview"]})
    fake.SHARED.queue(_reply("Listo. Pulsa Aplicar cuando quieras."))
    _send(c, sid)
    row = sql("SELECT status, stop_reason FROM assistant_auto_run WHERE session_id = :i", i=sid)
    assert row[0][0] == "stopped"
    assert row[0][1] is None or row[0][1].startswith("blocked:")
    messages = _session(c, sid)["messages"]
    assert "Resumen del run" in messages[-1]["content"]


def test_mode_block_is_one_line_and_only_in_auto():
    """The prompt is not rewritten per mode: `ask` needs nothing (the tools enforce it)."""

    class Ask:
        mode = "ask"

    assert service.mode_block(Ask(), get_settings()) == []

    class Auto:
        mode = "auto"

    lines = service.mode_block(Auto(), get_settings())
    text = " ".join(lines)
    assert "Modo Auto" in text and "run_command" in text
    assert len([line for line in lines if line.strip()]) == 1


def test_contract_limits_stop_the_run(chat, monkeypatch):
    c, project, sid = chat
    _write(project["id"], {"specs/001-ventas/spec.md": SPEC}, 1)
    _confirm(c, sid, {"goal": "x", "stages": ["draft"],
                      "limits": {"tokens": 10000, "previews": 0, "applies": 0,
                                 "wall_clock_seconds": 600}})
    sql("UPDATE assistant_auto_run SET tokens = 20000 WHERE session_id = :i", i=sid)
    fake.SHARED.queue(_reply("Escribo."), _reply("Fin."))
    _send(c, sid)
    row = sql("SELECT status, stop_reason FROM assistant_auto_run WHERE session_id = :i", i=sid)
    assert row == [("stopped", "limit:tokens")]


def test_limit_refusal_helpers():
    contract = auto.RunContract.model_validate({"goal": "x", "stages": ["draft", "preview"],
                                                "limits": {"tokens": 10000, "previews": 1,
                                                           "applies": 0,
                                                           "wall_clock_seconds": 60}})

    class Run:
        previews = 1
        applies = 0
        confirmed_at = None
        started_at = None

    run = Run()
    assert auto.limit_refusal(contract, run, previews=1) is None
    refused = auto.limit_refusal(contract, run, previews=2)
    assert refused and refused.limit == "previews"
    assert auto.limit_refusal(contract, run, applies=1).limit == "applies"
    assert auto.limit_refusal(contract, run, tokens=10000).limit == "tokens"
    assert auto.used_json(run)["previews"] == 1
