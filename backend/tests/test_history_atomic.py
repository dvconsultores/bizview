"""Feature 036, US2: a round is written in one transaction, so a failure cannot orphan a result."""
from __future__ import annotations

import threading
import time

import pytest

from app.ai import ChatReply, ChatUsage, ToolCall, fake
from app.assistant import history, service
from app.config import get_settings
from app.db import get_sessionmaker
from app.models import AssistantSession
from tests.conftest import new_chat, signed_in, sql


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


def _send(client, sid: int, text: str):
    return client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": text})


def _tool_call(name: str = "list_sources", call_id: str = "call_1") -> ChatReply:
    return ChatReply(text="", tool_calls=(ToolCall(call_id, name, {}),), usage=ChatUsage(),
                     model="fake", stop_reason="tool_use")


def _ok(text: str = "Listo.") -> ChatReply:
    return ChatReply(text=text, tool_calls=(), usage=ChatUsage(), model="fake")


def _messages(client, sid: int) -> list[dict]:
    """The conversation once the worker finished: the 202 body predates the failure note."""
    for _ in range(100):
        body = client.get(f"/api/assistant/sessions/{sid}").json()
        if not body["busy"]:
            return body["messages"]
        time.sleep(0.2)
    raise AssertionError("the run never finished")


def _tool_rows(sid: int) -> int:
    return sql("SELECT count(*) FROM assistant_message WHERE session_id = :i AND role = 'tool'",
               i=sid)[0][0]


def _calls(sid: int) -> int:
    return sql("SELECT count(*) FROM assistant_message WHERE session_id = :i "
               "AND role = 'assistant' AND tool_payload ? 'calls'", i=sid)[0][0]


def test_a_tool_that_blows_up_persists_no_tool_rows(superuser, db, monkeypatch):
    """The round dies in the middle: nothing of it is written, and the reason is."""
    client = signed_in("root@example.com")
    sid = new_chat(client)

    def boom(*args, **kwargs):
        raise RuntimeError("the tool died")

    monkeypatch.setattr(service, "run_tool", boom)
    fake.SHARED.queue(_tool_call())
    resp = _send(client, sid, "explora")
    assert resp.status_code == 202, resp.text

    assert _tool_rows(sid) == 0                 # no result row survived the round
    contents = [m["content"] for m in _messages(client, sid) if m["role"] == "assistant"]
    assert any("error" in content.lower() for content in contents)
    # The turn that asked for the tool is stored (it must be, or Detener could not release the
    # claim), and the next payload notes the unanswered call instead of sending a dangling one.
    built = history.build(history.load(db, sid, window=None))
    assert built.noted == ["call_1"]
    assert [m.role for m in built.messages][:2] == ["user", "assistant"]

    # The claim is released, so the conversation is usable again.
    assert sql("SELECT busy_since IS NOT NULL FROM assistant_session WHERE id = :i",
               i=sid) == [(False,)]


def test_the_next_turn_sends_after_the_failed_round(superuser, db, monkeypatch):
    client = signed_in("root@example.com")
    sid = new_chat(client)

    def boom(*args, **kwargs):
        raise RuntimeError("the tool died")

    original = service.run_tool
    monkeypatch.setattr(service, "run_tool", boom)
    fake.SHARED.queue(_tool_call())
    _send(client, sid, "explora")
    _messages(client, sid)                       # the failed round is written before we go on

    monkeypatch.setattr(service, "run_tool", original)
    fake.SHARED.queue(_ok("Ahora sí."))
    assert _send(client, sid, "continua").status_code == 202
    body = {"messages": _messages(client, sid)}
    assert body["messages"][-1]["content"] == "Ahora sí."
    assert body["messages"][-1].get("error") is None


def test_stopping_mid_round_persists_no_tool_rows(superuser, db, monkeypatch):
    """Detener during a tool: the round rolls back and only the stop note is stored."""
    client = signed_in("root@example.com")
    sid = new_chat(client)
    stopped: dict = {}

    def stop_then_answer(*args, **kwargs):
        # Another connection presses Detener while the tool is running, then the tool returns.
        def press():
            with get_sessionmaker()() as s:
                session = s.get(AssistantSession, sid)
                service.stop(s, session, get_settings())
                s.commit()
        thread = threading.Thread(target=press)
        thread.start()
        thread.join()
        stopped["done"] = True
        return {"ok": True}, "Consultó la lista de fuentes."

    monkeypatch.setattr(service, "run_tool", stop_then_answer)
    fake.SHARED.queue(_tool_call())
    resp = _send(client, sid, "explora")
    assert resp.status_code == 202, resp.text
    assert stopped.get("done") is True

    assert _tool_rows(sid) == 0
    contents = [m["content"] for m in _messages(client, sid) if m["role"] == "assistant"]
    assert any(service.t(service._STOPPED_TEXT) in content for content in contents)
    built = history.build(history.load(db, sid, window=None))
    assert built.noted == ["call_1"]          # the lost result is a note, never a block


def test_a_complete_round_is_stored_once_with_its_results(superuser, db):
    """The healthy path still writes the assistant turn and its results, now in one go."""
    client = signed_in("root@example.com")
    sid = new_chat(client)
    fake.SHARED.queue(_tool_call(), _ok())
    resp = _send(client, sid, "explora")
    assert resp.status_code == 202, resp.text

    assert _calls(sid) == 1
    assert _tool_rows(sid) == 1
    rows = sql("SELECT role, coalesce(tool_payload->>'call_id',''), id FROM assistant_message "
               "WHERE session_id = :i AND role IN ('assistant','tool') ORDER BY id", i=sid)
    tool_row = next(row for row in rows if row[0] == "tool")
    assert tool_row[1] == "call_1"
    # The assistant turn that asked for it is stored before it, as one unit.
    assert tool_row[2] > next(row[2] for row in rows if row[0] == "assistant")
