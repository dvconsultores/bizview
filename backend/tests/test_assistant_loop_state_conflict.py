"""Feature 040, Step 0: an `IntegrityError` in the loop is a named state conflict.

The production run of `/speckit-all` ended with «Ocurrió un error inesperado (IntegrityError)»
after three context compressions. The constraint name is what makes such a stop actionable, and a
stage re-entry must free the active-run slot *before* it inserts the next run.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.ai import fake
from app.assistant import service
from app.assistant.commands import pipeline, runs
from app.assistant.commands.registry import REGISTRY
from app.config import get_settings
from app.db import get_sessionmaker
from app.errors import StateConflict, constraint_of
from app.i18n import use_locale
from tests.conftest import new_chat, signed_in
from tests.test_assistant_api import _chat_reply, _tool_call
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


class _Diag:
    def __init__(self, constraint: str) -> None:
        self.constraint_name = constraint


class _Orig(Exception):
    def __init__(self, message: str, constraint: str) -> None:
        super().__init__(message)
        self.diag = _Diag(constraint)


def _integrity_error(constraint="ux_command_run_active"):
    orig = _Orig(f'duplicate key value violates unique constraint "{constraint}"', constraint)
    return IntegrityError("INSERT INTO assistant_command_run ...", {}, orig)


def test_constraint_of_reads_psycopg_diagnostics():
    assert constraint_of(_integrity_error()) == "ux_command_run_active"


def test_constraint_of_falls_back_to_the_message():
    error = IntegrityError("stmt", {}, Exception(
        'duplicate key value violates unique constraint "assistant_auto_run_index"'))
    assert constraint_of(error) == "assistant_auto_run_index"
    assert constraint_of(None) is None
    assert constraint_of(ValueError("boom")) is None


def test_state_conflict_carries_the_constraint_and_the_stop_reason():
    conflict = StateConflict("ux_command_run_active")
    assert conflict.constraint == "ux_command_run_active"
    assert conflict.stop_reason == "blocked:loop_state_conflict:ux_command_run_active"
    with use_locale("es"):
        text = service._error_text(conflict)
    assert "ux_command_run_active" in text
    assert "error inesperado" not in text.lower()


def test_a_stage_re_entry_frees_the_active_slot_before_inserting(db, superuser, chat):
    """The 039 defect: `finish` + `create` in one flush wrote the INSERT first (040 Step 0)."""
    _client, project, sid = chat
    template = REGISTRY["speckit-implement"]
    first = runs.create(db, session_id=sid, project_id=project["id"], definition=template,
                        arguments="", locale="es")
    runs.finish(first, "completed")
    # No flush in between: `create` has to free the slot itself or the partial unique index
    # `ux_command_run_active` refuses the second row.
    second = runs.create(db, session_id=sid, project_id=project["id"], definition=template,
                         arguments="", locale="es")
    db.flush()
    assert (first.status, second.status) == ("completed", "running")


def test_an_integrity_error_in_the_turn_is_a_named_stop(monkeypatch, superuser):
    def explode(*_args, **_kwargs):
        raise _integrity_error()

    monkeypatch.setattr(service, "run_tool", explode)
    fake.SHARED.queue(_chat_reply(tool_calls=[_tool_call("list_sources", {}, "c1")],
                                  stop_reason="tool_use"))
    client = signed_in("root@example.com")
    sid = new_chat(client)
    body = client.post(f"/api/assistant/sessions/{sid}/messages",
                       json={"text": "lista las fuentes"}).json()
    last = body["messages"][-1]
    assert "ux_command_run_active" in last["content"]
    assert "error inesperado" not in last["content"].lower()


def test_an_integrity_error_keeps_the_pipeline_cursor(monkeypatch, superuser):
    """US3: a failed write keeps the stage, so `/speckit-all <spec>` resumes there."""
    def explode(*_args, **_kwargs):
        raise _integrity_error("ux_auto_run_active")

    monkeypatch.setattr(service, "run_tool", explode)
    fake.SHARED.queue(_chat_reply(tool_calls=[
        _tool_call("run_command", {"command": "speckit-specify"}, "c1")],
        stop_reason="tool_use"))
    client = signed_in("root@example.com")
    sid = new_chat(client)
    body = client.post(f"/api/assistant/sessions/{sid}/messages",
                       json={"text": "/speckit-all un tablero de facturas"}).json()
    assert "ux_auto_run_active" in body["messages"][-1]["content"]
    with get_sessionmaker()() as db:
        state = pipeline.state_of(db, sid)
    # The plan exists but did not advance past the stage that failed.
    assert state is None or state["cursor"] == 0
