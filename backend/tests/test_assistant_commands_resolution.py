"""028 defect fix: every /speckit-* command resolves its target spec from its argument.

No live AI: the API tests script the fake provider, exactly like the other command suites.
"""
import json
from pathlib import Path

import pytest

from app.ai import ChatReply, ChatUsage, ToolCall, fake
from app.assistant.commands import resolve
from app.config import get_settings
from app.projects import fs
from tests.conftest import signed_in, sql

SPEC_A = ("# Feature Specification: Integración de facturas\n\n**Tipo**: integracion\n"
          "**Status**: Draft\n")
SPEC_B = "# Feature Specification: Ventas y facturación\n\n**Tipo**: reporte\n**Status**: Draft\n"
SPECS = [
    {"folder": "001-integracion-facturas", "title": "Integración de facturas"},
    {"folder": "002-ventas-facturacion", "title": "Ventas y facturación"},
]
PLAN = "# Plan\n\nContexto técnico.\n"


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


def _send(c, sid, text):
    return c.post(f"/api/assistant/sessions/{sid}/messages", json={"text": text})


def _session(c, sid):
    return c.get(f"/api/assistant/sessions/{sid}").json()


def _write(project_id, files, user_id):
    fs.apply_ops(project_id, [{"op": "write", "path": p, "content": t, "base_sha256": None,
                               "force": False} for p, t in files.items()],
                 {"kind": "user", "user_id": user_id, "session_id": None, "command": "edit"})


@pytest.fixture
def chat(superuser):
    c = signed_in("root@example.com")
    project = c.post("/api/projects", json={"name": "Artemisa"}).json()
    _write(project["id"], {
        "specs/001-integracion-facturas/spec.md": SPEC_A,
        "specs/002-ventas-facturacion/spec.md": SPEC_B,
    }, superuser.id)
    sid = c.post("/api/assistant/sessions", json={"project": project["slug"]}).json()["id"]
    assert c.patch(f"/api/assistant/sessions/{sid}",
                   json={"current_spec": "001-integracion-facturas"}).status_code == 200
    return c, project, sid


@pytest.mark.parametrize("arguments,current,expected,source", [
    # The exact strings of session 18.
    ("Plan del reporte 002-ventas-facturacion sobre el dataset invoices",
     "001-integracion-facturas", "002-ventas-facturacion", "argument"),
    ("001-integracion-facturas , actua de forma autónoma en todos los pasos",
     "002-ventas-facturacion", "001-integracion-facturas", "argument"),
    ("", "001-integracion-facturas", "001-integracion-facturas", "current"),
    ("la 002", "001-integracion-facturas", "002-ventas-facturacion", "number"),
    ("reporte 002", "001-integracion-facturas", "002-ventas-facturacion", "number"),
    ("spec 001", "002-ventas-facturacion", "001-integracion-facturas", "number"),
    ("Ventas y facturación", "001-integracion-facturas", "002-ventas-facturacion", "title"),
    ("ventas-facturacion", "001-integracion-facturas", "002-ventas-facturacion", "title"),
    # Negative cases: an unknown folder or number falls back to current_spec.
    ("003-no-existe", "001-integracion-facturas", "001-integracion-facturas", "current"),
    ("999", "002-ventas-facturacion", "002-ventas-facturacion", "current"),
])
def test_resolution_table(arguments, current, expected, source):
    resolution = resolve.resolve(SPECS, arguments, current)
    assert (resolution.spec, resolution.source) == (expected, source)


def test_resolution_without_any_candidate_returns_none():
    assert resolve.resolve([], "", None) == resolve.Resolution(None, None)


@pytest.mark.parametrize("arguments,expected", [
    ("--force", ""),
    ("reporte 002 --force", "reporte 002"),
    ("  plan   --force   detallado ", "plan detallado"),
])
def test_strip_force(arguments, expected):
    assert resolve.strip_force(arguments) == (expected, True)
    assert resolve.strip_force("plan detallado") == ("plan detallado", False)


def test_plan_on_explicit_spec_writes_that_spec_on_the_first_attempt(chat):
    c, project, sid = chat
    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": "specs/002-ventas-facturacion/plan.md",
             "content": PLAN}]})]),
        _reply("Plan escrito.", [_call("finish_command", {"summary": "plan 002"}, "call-2")]),
    )
    r = _send(c, sid, "/speckit-plan Plan del reporte 002-ventas-facturacion "
                      "sobre el dataset invoices")
    assert r.status_code == 202, r.text
    data = _session(c, sid)
    assert data["current_spec"] == "002-ventas-facturacion"
    run = data["command_runs"][0]
    assert (run["command"], run["spec"], run["resolved_from"], run["status"]) == (
        "speckit-plan", "002-ventas-facturacion", "argument", "completed")
    assert (fs.project_root(project["slug"]) / "specs/002-ventas-facturacion/plan.md"
            ).exists()
    assert not (fs.project_root(project["slug"]) /
                "specs/001-integracion-facturas/plan.md").exists()
    assert any("Spec actual: 002-ventas-facturacion" in m["content"]
               for m in data["messages"] if m["role"] == "assistant")


def test_number_and_empty_arguments_use_the_resolved_spec(chat, superuser):
    c, _, sid = chat
    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": "specs/002-ventas-facturacion/plan.md",
             "content": PLAN}]})]),
        _reply("Listo.", [_call("finish_command", {"summary": "ok"}, "call-2")]),
    )
    assert _send(c, sid, "/speckit-plan la 002").status_code == 202
    assert _session(c, sid)["command_runs"][0]["spec"] == "002-ventas-facturacion"

    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": "specs/002-ventas-facturacion/research.md",
             "content": "# Research\n"}]})]),
        _reply("Listo.", [_call("finish_command", {"summary": "ok"}, "call-2")]),
    )
    assert _send(c, sid, "/speckit-plan --force").status_code == 202
    run = _session(c, sid)["command_runs"][0]
    assert (run["spec"], run["resolved_from"], run["forced"]) == (
        "002-ventas-facturacion", "current", True)


def test_needs_spec_names_the_command_and_lists_the_project_specs(chat):
    c, _, sid = chat
    c.patch(f"/api/assistant/sessions/{sid}", json={"current_spec": ""})
    r = _send(c, sid, "/speckit-plan")
    assert r.status_code == 409
    error = r.json()["error"]
    assert error["code"] == "needs_spec"
    assert "Indica la spec: /speckit-plan 001-integracion-facturas" in error["message"]
    assert [item["folder"] for item in error["specs"]] == [
        "001-integracion-facturas", "002-ventas-facturacion"]
    assert fake.SHARED.requests == []


def test_specify_with_two_specs_sets_current_to_the_last(chat):
    c, _, sid = chat
    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": "specs/003-integracion-ventas/spec.md", "content": SPEC_A},
            {"op": "write", "path": "specs/004-reporte-ventas/spec.md", "content": SPEC_B},
        ]})]),
        _reply("Dos specs.", [_call("finish_command", {"summary": "specs 003 y 004"}, "call-2")]),
    )
    assert _send(c, sid, "/speckit-specify Un informe nuevo en dos partes").status_code == 202
    data = _session(c, sid)
    assert data["current_spec"] == "004-reporte-ventas"
    run = data["command_runs"][0]
    assert run["spec"] == "004-reporte-ventas"
    assert {entry["path"] for entry in run["files"]} == {
        "specs/003-integracion-ventas/spec.md", "specs/004-reporte-ventas/spec.md"}
    finished = next(m for m in data["messages"] if m.get("tool_name") == "finish_command")
    assert "003-integracion-ventas" in finished["content"]
    assert "004-reporte-ventas" in finished["content"]


def test_write_to_another_spec_is_misrouted_not_completed(chat):
    c, project, sid = chat
    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": "specs/002-ventas-facturacion/plan.md",
             "content": PLAN}]})]),
        _reply("No pude escribir.", [_call("finish_command", {"summary": "nada"}, "call-2")]),
    )
    assert _send(c, sid, "/speckit-plan 001-integracion-facturas").status_code == 202
    data = _session(c, sid)
    run = data["command_runs"][0]
    assert (run["status"], run["files"], run["misrouted_to"]) == (
        "misrouted", [], "002-ventas-facturacion")
    tool = next(m for m in data["messages"] if m.get("tool_name") == "edit_draft")
    assert tool["content"] == (
        "Este comando corre sobre 001-integracion-facturas. Para escribir en "
        "specs/002-ventas-facturacion/plan.md ejecuta /speckit-plan 002-ventas-facturacion.")
    assert not (fs.project_root(project["slug"]) /
                "specs/002-ventas-facturacion/plan.md").exists()


def test_second_plan_without_changes_skips_the_model_and_force_runs_it(chat):
    c, _, sid = chat
    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": "specs/001-integracion-facturas/plan.md",
             "content": PLAN}]})]),
        _reply("Listo.", [_call("finish_command", {"summary": "ok"}, "call-2")]),
    )
    assert _send(c, sid, "/speckit-plan 001-integracion-facturas").status_code == 202
    calls = len(fake.SHARED.requests)

    r = _send(c, sid, "/speckit-plan 001-integracion-facturas")
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == calls        # no provider call
    assert "plan.md ya existe" in r.json()["messages"][-1]["content"]

    fake.SHARED.queue(_reply("Regenerado.",
                             [_call("finish_command", {"summary": "ok"}, "call-3")]))
    r = _send(c, sid, "/speckit-plan 001-integracion-facturas --force")
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == calls + 1
    run = _session(c, sid)["command_runs"][0]
    assert (run["forced"], run["status"]) == (True, "completed")


def test_converge_with_zero_gaps_is_replayed_from_the_stored_run(chat, superuser):
    c, project, sid = chat
    _write(project["id"], {
        "specs/002-ventas-facturacion/plan.md": PLAN,
        "specs/002-ventas-facturacion/tasks.md": "- [X] T001 Reporte\n",
    }, superuser.id)
    fake.SHARED.queue(_reply("Sin huecos.", [_call("finish_command", {"summary": "sin huecos"})]))
    assert _send(c, sid, "/speckit-converge 002-ventas-facturacion").status_code == 202
    calls = len(fake.SHARED.requests)

    r = _send(c, sid, "/speckit-converge 002-ventas-facturacion")
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == calls
    assert "no encontró huecos" in r.json()["messages"][-1]["content"]


def test_read_draft_returns_the_hash_when_the_file_did_not_change(chat):
    c, _, sid = chat
    fake.SHARED.queue(
        _reply("", [_call("read_draft", {"paths": ["specs/001-integracion-facturas/spec.md"]})]),
        _reply("", [_call("read_draft", {"paths": ["specs/001-integracion-facturas/spec.md"]},
                          "call-2")]),
        _reply("Leído.", [_call("finish_command", {"summary": "ok"}, "call-3")]),
    )
    assert _send(c, sid, "/speckit-plan 001-integracion-facturas").status_code == 202
    reads = [m for m in _session(c, sid)["messages"] if m.get("tool_name") == "read_draft"]
    assert len(reads) == 2
    assert "sin cambios desde la lectura anterior" in reads[-1]["content"]


def test_a_huge_command_run_is_not_stopped_by_tokens(chat):
    """Feature 028 revision (owner, 2026-10-21: "make the ai unlimited").

    The 400k per-command ceiling is gone: a stage that writes a very large file keeps the work.
    """
    c, project, sid = chat
    huge = "x" * 80_000
    fake.SHARED.queue(ChatReply(
        text="",
        tool_calls=(_call("edit_draft", {"ops": [
            {"op": "write", "path": "specs/001-integracion-facturas/plan.md",
             "content": huge}]}),),
        usage=ChatUsage(), model="fake"))
    assert _send(c, sid, "/speckit-plan 001-integracion-facturas").status_code == 202
    data = _session(c, sid)
    assert all(run["status"] != "budget" for run in data["command_runs"])
    assert (fs.project_root(project["slug"]) /
            "specs/001-integracion-facturas/plan.md").exists()
    assert not any("techo" in m["content"] for m in data["messages"] if m["role"] == "assistant")


def test_set_current_spec_tool_and_suggestion_carry_the_spec(chat):
    c, _, sid = chat
    # `suggest_command` only exists outside Auto (feature 028: the agent runs the stage itself).
    assert c.post(f"/api/assistant/sessions/{sid}/mode",
                  json={"mode": "edit"}).status_code == 200
    fake.SHARED.queue(
        _reply("Trabajo en el reporte.", [
            _call("set_current_spec", {"spec_id": "002-ventas-facturacion"}),
            _call("suggest_command", {"command": "speckit-plan",
                                      "spec": "002-ventas-facturacion",
                                      "arguments": "el reporte"}, "call-2")]),
        _reply("Siguiente paso: el plan."),
    )
    assert _send(c, sid, "Trabaja en el reporte de ventas").status_code == 202
    data = _session(c, sid)
    assert data["current_spec"] == "002-ventas-facturacion"
    chip = next(m for m in data["messages"] if m.get("tool_name") == "set_current_spec")
    assert chip["content"] == "Spec actual: 002-ventas-facturacion"
    assert data["messages"][-1]["suggestions"] == [{
        "command": "speckit-plan", "spec": "002-ventas-facturacion",
        "arguments": "el reporte"}]


def test_post_current_spec_is_a_normal_request(chat):
    c, _, sid = chat
    r = c.post(f"/api/assistant/sessions/{sid}/spec",
               json={"spec": "002-ventas-facturacion"})
    assert r.status_code == 200, r.text
    assert r.json()["current_spec"] == "002-ventas-facturacion"
    assert r.json()["specs"][1]["stage"] == "especificada"


def test_session18_replay_writes_the_002_plan_on_the_first_attempt(superuser):
    c = signed_in("root@example.com")
    project = c.post("/api/projects", json={"name": "Artemisa"}).json()
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "session18.json").read_text(encoding="utf-8"))
    _write(project["id"], fixture["files"], superuser.id)
    sid = c.post("/api/assistant/sessions", json={"project": project["slug"]}).json()["id"]
    c.patch(f"/api/assistant/sessions/{sid}",
            json={"current_spec": fixture["current_spec"]})
    fake.SHARED.queue(
        _reply("", [_call("edit_draft", {"ops": [
            {"op": "write", "path": path, "content": content}
            for path, content in fixture["writes"].items()]})]),
        _reply("Plan del reporte listo.",
               [_call("finish_command", {"summary": "plan 002"}, "call-2")]),
    )
    assert _send(c, sid, fixture["command"]).status_code == 202
    data = _session(c, sid)
    assert data["current_spec"] == fixture["expected_spec"]
    run = data["command_runs"][0]
    assert (run["status"], run["spec"]) == ("completed", fixture["expected_spec"])
    for path in fixture["writes"]:
        assert (fs.project_root(project["slug"]) / path).exists()
    # The implemented 001 plan was never overwritten.
    assert sql("SELECT count(*) FROM project_file_revision WHERE path = :p",
               p="specs/001-integracion-facturas/plan.md")[0][0] == 1
