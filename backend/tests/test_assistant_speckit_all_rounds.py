"""Feature 040 (A and B): the state machine loops back, `--only` and the task write guard.

The production run stayed at `verify` after `converge` had added T025–T028, told the human to
"open it in that order", and offered a fake fix that marked every task `[X]`.
"""
import pytest

from app.ai import fake
from app.assistant.commands import pipeline, runs
from app.assistant.commands.registry import REGISTRY
from app.config import get_settings
from tests.conftest import signed_in
from tests.test_assistant_api import _chat_reply, _tool_call
from tests.test_assistant_auto_mode import _send
from tests.test_assistant_commands_service import _with_spec, chat as chat  # noqa: F401
from tests.test_assistant_speckit_all_run import _finish, _open, _text


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


TASKS = ("# Tasks\n\n## Phase 1\n\n"
         "- [ ] T001 Crear `reports/ventas/report.yaml`\n"
         "- [ ] T002 Documentar el reporte\n")
BUILT = {
    "specs/001-ventas/spec.md": ("# Ventas\n\n**Tipo**: reporte\n**Status**: Draft\n\n"
                                 "Ventas por sucursal.\n"),
    "specs/001-ventas/plan.md": "# Plan\n\nReporte `reports/ventas/`.\n",
    "specs/001-ventas/tasks.md": TASKS,
    "reports/ventas/report.yaml": "id: ventas\n",
}


def _read_tasks(call_id="rd1"):
    """The model has to read a file before it may write it (021 base revision)."""
    return _chat_reply(tool_calls=[_tool_call("read_draft",
                                              {"paths": ["specs/001-ventas/tasks.md"]},
                                              call_id)], stop_reason="tool_use")


def _seed_plan(db, project, sid, command, cursor, files, *, spec="001-ventas", round_=1):
    """A plan whose cursor points at `cursor`, anchored on one finished run."""
    plan = pipeline.seed(None, None, [spec])
    plan = {**plan, "cursor": pipeline.STAGES.index(cursor), "round": round_}
    anchor = runs.create(db, session_id=sid, project_id=project["id"],
                         definition=REGISTRY[command], arguments="", locale="es", spec=spec,
                         pipeline=plan, status="running")
    runs.finish(anchor, "completed")
    plan = {**plan, "id": anchor.id}
    anchor.result = {**(anchor.result or {}), pipeline.PIPELINE_KEY: plan}
    # The HTTP turn claims the conversation with `FOR UPDATE` on another connection, so the rows
    # (and their key-share locks) must be committed before it starts.
    db.commit()
    return plan


# --------------------------------------------------------------------------- state machine

def test_converge_with_gaps_reopens_implement_and_counts_the_round(db, chat):
    _c, project, sid = chat
    plan = _seed_plan(db, project, sid, "speckit-converge", "verify", {})
    routed = pipeline.routed_state(db, plan, BUILT)
    assert pipeline.STAGES[routed["cursor"]] == "implement"
    assert routed["round"] == 2
    assert routed["after_implement"] == "converge"


def test_the_convergence_rounds_are_capped_then_verify(db, chat):
    """Two convergence runs already happened: the third gap goes through a verify cycle."""
    _c, project, sid = chat
    plan = _seed_plan(db, project, sid, "speckit-converge", "verify", {}, round_=2)
    routed = pipeline.routed_state(db, plan, BUILT)
    assert pipeline.STAGES[routed["cursor"]] == "implement"
    assert routed["after_implement"] == "verify"
    assert routed["verify_cycles"] == 1


def test_verify_failures_are_capped(db, chat):
    _c, project, sid = chat
    plan = _seed_plan(db, project, sid, "speckit-verify", "verify", {})
    for _ in range(pipeline.MAX_VERIFY_CYCLES):
        row = runs.create(db, session_id=sid, project_id=project["id"],
                          definition=REGISTRY["speckit-verify"], arguments="", locale="es",
                          spec="001-ventas", pipeline=plan, status="running")
        row.result = {**(row.result or {}), "verify": {"ok": False}}
        runs.finish(row, "completed")
    db.flush()
    routed = pipeline.routed_state(db, plan, {})
    # No more cycles: verify stays where it is and the run report carries the failure.
    assert pipeline.STAGES[routed["cursor"]] == "verify"


def test_an_implement_opened_by_a_verify_cycle_returns_to_verify(db, chat):
    _c, project, sid = chat
    plan = _seed_plan(db, project, sid, "speckit-implement", "converge", {})
    plan = {**plan, "after_implement": "verify"}
    routed = pipeline.routed_state(db, plan, BUILT)
    assert pipeline.STAGES[routed["cursor"]] == "verify"
    assert routed["after_implement"] is None


def test_verify_does_not_start_with_open_tasks_at_the_api(chat, superuser, db):
    c, project, sid = chat
    _with_spec(c, project, sid, superuser, BUILT)
    _seed_plan(db, project, sid, "speckit-converge", "verify", BUILT)
    fake.SHARED.queue(_open("speckit-verify", spec="001-ventas", call_id="v1"), _text())
    body = _send(c, sid, "continúa")
    commands = [run["command"] for run in body["command_runs"]]
    assert "speckit-implement" in commands
    assert "speckit-verify" not in commands
    reopened = next(run for run in body["command_runs"] if run["command"] == "speckit-implement")
    assert reopened["pipeline"]["round"] == 2
    assert any("ronda 2" in (m["content"] or "") for m in body["messages"])


# --------------------------------------------------------------------------- --only

def test_strip_only_reads_the_task_list():
    from app.assistant.commands import resolve

    assert resolve.strip_only("001-ventas --only T025,T026") == (("001-ventas"), ("T025", "T026"))
    assert resolve.strip_only("--only=t1 t2 001-ventas")[1] == ("T1", "T2")
    assert resolve.strip_only("001-ventas") == ("001-ventas", ())


def test_only_names_a_task_that_does_not_exist(chat, superuser, db):
    c, project, sid = chat
    _with_spec(c, project, sid, superuser, BUILT)
    _seed_plan(db, project, sid, "speckit-analyze", "implement", BUILT)
    fake.SHARED.queue(
        _open("speckit-implement", spec="001-ventas", call_id="i1"),
        _text())
    reply = c.post(f"/api/assistant/sessions/{sid}/messages",
                   json={"text": "/speckit-implement 001-ventas --only T999"})
    assert reply.status_code == 422
    assert reply.json()["error"]["code"] == "only_unknown"


def test_only_is_enforced_when_a_task_is_ticked(chat, superuser, db):
    c, project, sid = chat
    _with_spec(c, project, sid, superuser, BUILT)
    _seed_plan(db, project, sid, "speckit-analyze", "implement", BUILT)
    ticked_one = TASKS.replace("- [ ] T001", "- [X] T001")
    ticked_both = ticked_one.replace("- [ ] T002", "- [X] T002")
    fake.SHARED.queue(
        _chat_reply(tool_calls=[_tool_call(
            "run_command", {"command": "speckit-implement", "spec": "001-ventas",
                            "arguments": "--only T001"}, "i1")],
            stop_reason="tool_use"),
        _read_tasks(),
        _chat_reply(tool_calls=[_tool_call(
            "edit_draft", {"ops": [{"op": "write",
                                    "path": "specs/001-ventas/tasks.md",
                                    "content": ticked_one}]}, "w1")],
            stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call(
            "edit_draft", {"ops": [{"op": "write",
                                    "path": "specs/001-ventas/tasks.md",
                                    "content": ticked_both}]}, "w2")],
            stop_reason="tool_use"),
        _finish("Implementado lo pedido.", "f1"),
        _text())
    body = _send(c, sid, "continúa con la implementación")
    results = [m["content"] for m in body["messages"] if m["role"] == "tool"]
    assert any("T001" in str(item) or "escrit" in str(item).lower() for item in results)
    assert any("--only" in str(item) for item in results)


def test_another_command_cannot_tick_a_task(chat, superuser):
    c, project, sid = chat
    _with_spec(c, project, sid, superuser, BUILT)
    fake.SHARED.queue(
        _read_tasks(),
        _chat_reply(tool_calls=[_tool_call(
            "edit_draft", {"ops": [{"op": "write", "path": "specs/001-ventas/tasks.md",
                                    "content": TASKS.replace("- [ ] T001", "- [X] T001")}]},
            "w1")], stop_reason="tool_use"),
        _text())
    body = _send(c, sid, "/speckit-converge 001-ventas")
    results = [str(m["content"]) for m in body["messages"] if m["role"] == "tool"]
    assert any("Las tareas se marcan al implementarlas" in item for item in results)


def test_a_failed_final_verify_still_gets_its_fix_cycle(db, chat):
    """The plan ends at verify; a failure must reopen implement instead of ending the run."""
    _c, project, sid = chat
    plan = _seed_plan(db, project, sid, "speckit-verify", "verify", {})
    row = runs.create(db, session_id=sid, project_id=project["id"],
                      definition=REGISTRY["speckit-verify"], arguments="", locale="es",
                      spec="001-ventas", pipeline=plan, status="running")
    row.result = {**(row.result or {}), "verify": {"ok": False}}
    runs.finish(row, "completed")
    done = {**plan, "cursor": pipeline.TOTAL}
    db.flush()
    routed = pipeline.routed_state(db, done, {})
    assert pipeline.STAGES[routed["cursor"]] == "implement"
    assert routed["after_implement"] == "verify"
    assert routed["verify_cycles"] == 1
