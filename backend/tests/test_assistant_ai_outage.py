"""An AI outage must not cost tokens, a run, or the work already written (feature 035, US2)."""
from __future__ import annotations

import pytest

from app.ai import AIError, ChatReply, ChatUsage, fake, state
from app.assistant import service
from app.config import get_settings
from tests.conftest import new_chat, signed_in


@pytest.fixture(autouse=True)
def clean_status(db):
    """The recorded outcome outlives a single test: start each one from a healthy installation."""
    from tests.conftest import sql

    sql("DELETE FROM ai_status")
    yield


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


def _send(client, sid: int, text: str):
    return client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": text}).json()


def _fails(code: str, detail: str = "boom", retry_after: float | None = None):
    def step(messages, tools, system):
        raise AIError(code, detail, retry_after=retry_after)
    return step


def _ok(text: str = "Listo."):
    return ChatReply(text=text, tool_calls=(), usage=ChatUsage(), model="fake")


def test_a_blocking_code_refuses_the_turn_without_calling_the_provider(superuser, db):
    """The installation is broken: say so, spend nothing, and keep the door closed."""
    client = signed_in("root@example.com")
    sid = new_chat(client)
    state.record_error("no_credit", "HTTP 402: Insufficient Balance", "deepseek-flash")

    body = _send(client, sid, "continua")

    assert fake.SHARED.requests == []                    # 0 provider calls (FR-007)
    last = body["messages"][-1]
    assert "no_credit" in last["content"]
    assert last["error"]["code"] == "no_credit"
    assert last["error"]["action"] == "admin_ai"
    assert last["error"]["request_id"]                  # the details block has its id


def test_a_transient_code_is_retried_once_and_then_answers(superuser, db):
    client = signed_in("root@example.com")
    fake.SHARED.queue(_fails("rate_limited", "HTTP 429", retry_after=0.01), _ok("Hola."))
    sid = new_chat(client)

    body = _send(client, sid, "hola")

    assert len(fake.SHARED.requests) == 2                # one bounded retry, not a loop
    assert body["messages"][-1]["content"] == "Hola."
    assert state.read()["last_error_code"] is None       # the success cleared the failure


def test_two_failures_with_the_same_code_stop_the_run(superuser, db):
    client = signed_in("root@example.com")
    fake.SHARED.queue(_fails("provider_error", "HTTP 500: <html>"), _fails("provider_error"))
    sid = new_chat(client)

    body = _send(client, sid, "hazlo")

    assert len(fake.SHARED.requests) == 2                # SC-002: never more
    last = body["messages"][-1]
    assert last["error"]["code"] == "provider_error"
    assert last["error"]["action"] is None       # nothing to press: it stopped after two tries
    assert state.read()["last_error_code"] == "provider_error"


def test_a_code_a_person_must_fix_is_not_retried(superuser, db):
    client = signed_in("root@example.com")
    fake.SHARED.queue(_fails("bad_key", "HTTP 401"), _ok())
    sid = new_chat(client)

    body = _send(client, sid, "hola")

    assert len(fake.SHARED.requests) == 1                # asking again cannot help
    assert body["messages"][-1]["error"]["code"] == "bad_key"
    assert state.blocked_reason() == "bad_key"


def test_the_refusal_disappears_when_a_success_is_recorded(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    state.record_error("no_credit", "402", "m")
    assert _send(client, sid, "hola")["messages"][-1]["error"]["code"] == "no_credit"

    state.record_ok("fake")                              # somebody fixed the account
    fake.SHARED.queue(_ok("Hola de nuevo."))
    body = _send(client, sid, "hola")
    assert body["messages"][-1]["content"] == "Hola de nuevo."
    assert len(fake.SHARED.requests) == 1


def test_the_contract_is_refused_while_blocked(superuser, db):
    """FR-007: no contract row, no provider call — the composer shows why."""
    from app.assistant.service import ai_blocked_code

    state.record_error("model_not_found", "HTTP 404: model: nope", "deepseek-flash")
    assert ai_blocked_code() == "model_not_found"
    state.record_ok("deepseek-chat")
    assert service.ai_blocked_code() is None
