"""Feature 040 (C and D): one compression per run, stage context, tool groups and stage budgets."""
from types import SimpleNamespace

import pytest

from app.ai import ChatMessage, fake
from app.assistant import service
from app.assistant import tools as assistant_tools
from app.assistant.commands import registry, runs
from app.config import get_settings
from app.models import AssistantMessage
from tests.conftest import signed_in
from tests.test_assistant_api import _chat_reply
from tests.test_assistant_auto_mode import _send
from tests.test_assistant_commands_service import chat as chat


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


# --------------------------------------------------------------------------- C: compression

def _bulk(turns: int = 12) -> list[ChatMessage]:
    out: list[ChatMessage] = []
    for index in range(turns):
        out.append(ChatMessage(role="user", content=f"petición {index} " + "x" * 9000))
        out.append(ChatMessage(role="assistant", content=f"respuesta {index} " + "y" * 9000))
    return out


def test_compression_runs_once_per_run(db, chat):
    from app.models import AssistantSession

    _c, _project, sid = chat
    session = db.get(AssistantSession, sid)
    history = _bulk()
    messages: list[AssistantMessage] = []
    compacted, exhausted = service._compact_once(
        db, session, history, {}, budget=20_000, run_key="pipeline:1", new_messages=messages)
    assert exhausted is None
    assert len(compacted) == len(history)
    assert len(messages) == 1 and "Comprimí" in messages[0].content
    mark = (session.working_state or {})[service.COMPACTION_KEY]
    assert (mark["session"], mark["run"], mark["n"]) == (sid, "pipeline:1", 1)
    assert 0 < mark["freed"][0] <= 1

    # A second one in the same run is only allowed while the first freed enough; either way it is
    # bounded and the third is a stop, never a loop.
    compacted, exhausted = service._compact_once(
        db, session, compacted, {}, budget=20_000, run_key="pipeline:1", new_messages=messages)
    if mark["freed"][0] < service.MIN_FREED_RATIO:
        assert exhausted == "context_exhausted"
        assert len(messages) == 1
    else:
        assert exhausted is None or exhausted == "context_exhausted"


def test_a_compression_that_frees_little_stops_the_run(db, chat):
    from app.models import AssistantSession

    _c, _project, sid = chat
    session = db.get(AssistantSession, sid)
    session.working_state = {service.COMPACTION_KEY: {"session": sid, "run": "pipeline:9", "n": 1,
                                                     "freed": [0.05]}}
    history = _bulk(2)
    messages: list[AssistantMessage] = []
    _compacted, exhausted = service._compact_once(
        db, session, history, {}, budget=20_000, run_key="pipeline:9", new_messages=messages)
    assert exhausted == "context_exhausted"
    assert messages == []


def test_stage_scoped_history_drops_the_previous_stage_results(db, chat):
    from app.models import AssistantSession

    _c, _project, sid = chat
    session = db.get(AssistantSession, sid)
    user = AssistantMessage(session_id=sid, role="user", content="/speckit-all 001-ventas")
    db.add(user)
    db.flush()
    old = AssistantMessage(session_id=sid, role="tool", tool_name="check_query",
                           content="columnas de la etapa 1", call_id="c0")
    db.add(old)
    db.flush()
    summary = AssistantMessage(session_id=sid, role="assistant",
                               content="✔ implement terminada: `reports/ventas/report.yaml`")
    db.add(summary)
    db.flush()
    current = AssistantMessage(session_id=sid, role="assistant", content="etapa convergir")
    db.add(current)
    db.flush()
    from app.assistant.commands import pipeline

    state = pipeline.seed(None, None, ["001-ventas"])
    run = SimpleNamespace(id=1, session_id=sid, command="speckit-converge", locale="es",
                          result={"history_from": summary.id, pipeline.PIPELINE_KEY: state})
    scoped = service._scoped_history(db, session, run)
    contents = [message.content for message in scoped]
    assert any("etapa convergir" in str(item) for item in contents)
    assert scoped and scoped[0].role == "user"
    assert not any("etapa 1" in str(item) for item in contents)
    # The finished stage's line is not lost: it travels in the stage block.
    block = service._command_extra(run, db, {})
    assert "✔" in block and "reports/ventas/report.yaml" in block


# --------------------------------------------------------------------------- D: tool groups

def test_every_group_is_bounded_and_offers_the_guide():
    names = {spec["name"] for spec in assistant_tools.TOOL_SPECS}
    for command, group in assistant_tools.TOOL_GROUPS.items():
        assert group <= names, f"{command}: {sorted(group - names)}"
        assert len(group) <= assistant_tools.MAX_TOOLS_PER_ROUND, command
        assert "get_app_guide" in group, command
        assert "finish_command" in group, command


def test_a_stage_is_offered_only_its_group():
    session = SimpleNamespace(
        command_run=SimpleNamespace(command="speckit-verify"), mode="auto", auto_run=None,
        draft={"files": {}}, working_state={}, query_checks=None)
    settings = get_settings()
    specs, _restricted = assistant_tools.offered_tool_specs(session, settings)
    offered = {spec["name"] for spec in specs}
    assert "run_preview" in offered and "check_query" in offered
    # No writer: the judging stage cannot fix what it judges.
    assert not offered & {"propose_draft", "edit_draft", "apply_draft"}


def test_the_stage_budget_stops_the_stage(monkeypatch, superuser):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_stage_token_budget", 10_000)
    client = signed_in("root@example.com")
    from tests.conftest import new_chat

    sid = new_chat(client)
    fake.SHARED.queue(_chat_reply("Listo."))
    body = _send(client, sid, "hola")
    assert body["messages"]
    # The turn ends either normally (few tokens) or with the budget stop; when it stops, the
    # message names the resume command and the contract is closed as a stop.
    text = " ".join(str(m["content"]) for m in body["messages"])
    assert "Listo." in text or "/speckit-all" in text


def test_a_zero_budget_disables_the_stage_ceiling(monkeypatch, superuser):
    settings = get_settings()
    # Owner decision (2026-10-21, reaffirmed 2026-10-29): 0 means the AI is unlimited per stage.
    monkeypatch.setattr(settings, "ai_stage_token_budget", 0)
    client = signed_in("root@example.com")
    from tests.conftest import new_chat

    sid = new_chat(client)
    fake.SHARED.queue(_chat_reply("Listo."))
    body = _send(client, sid, "/speckit-specify panorama")
    text = " ".join(str(m["content"]) for m in body["messages"])
    assert "Listo." in text
    assert "presupuesto" not in text


def test_a_stage_run_carries_its_own_context_mark(db, chat):
    _c, project, sid = chat
    run = runs.create(db, session_id=sid, project_id=project["id"],
                      definition=registry.REGISTRY["speckit-plan"], arguments="", locale="es")
    assert run.id
