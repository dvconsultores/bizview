"""Feature 017 Phase 10: per-round durability and the busy claim of a conversation."""
import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.ai import AIError, fake
from app.assistant import service
from app.config import get_settings
from app.db import get_engine
from app.i18n import t
from tests.conftest import TEST_SCHEMA, new_chat, reauth, signed_in, sql
from tests.test_assistant_api import _chat_reply, _tool_call


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


def _new_session(client) -> int:
    return new_chat(client)


def _busy(sid: int) -> bool:
    return sql("SELECT busy_since IS NOT NULL FROM assistant_session WHERE id = :i",
               i=sid)[0][0]


def test_round_is_committed_while_next_round_runs(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    seen: dict = {}

    def round2(messages, tools, system):
        seen["count"] = sql(
            "SELECT count(*) FROM assistant_message WHERE session_id = :i", i=sid)[0][0]
        seen["tokens"] = sql(
            "SELECT tokens_used FROM assistant_session WHERE id = :i", i=sid)[0][0]
        seen["busy"] = _busy(sid)
        return _chat_reply("Listo.")

    fake.SHARED.queue(
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
                    stop_reason="tool_use"),
        round2,
    )
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202, r.json()

    assert seen["count"] == 3
    assert seen["tokens"] == 15
    assert seen["busy"] is True

    assert _busy(sid) is False
    assert r.json()["session"]["busy"] is False


def test_unexpected_error_keeps_committed_rounds_and_releases(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    def boom(messages, tools, system):
        raise RuntimeError("boom")

    fake.SHARED.queue(
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
                    stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, call_id="c2")],
                    stop_reason="tool_use"),
        boom,
    )
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202

    assert sql("SELECT count(*) FROM assistant_message WHERE session_id = :i", i=sid)[0][0] == 6
    assert sql("SELECT tokens_used FROM assistant_session WHERE id = :i", i=sid)[0][0] == 30
    assert _busy(sid) is False

    contents = [m["content"] for m in r.json()["messages"] if m["role"] == "assistant"]
    assert t(service._UNEXPECTED_TEXT) in contents

    fake.SHARED.queue(_chat_reply("Sigo."))
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Sigo"})
    assert r.status_code == 202
    contents = [m["content"] for m in r.json()["messages"] if m["role"] == "assistant"]
    assert service._INTERRUPTED_TEXT not in contents


def test_provider_error_releases_busy(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    def rate_limited(messages, tools, system):
        raise AIError("rate_limited")

    fake.SHARED.queue(rate_limited)
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202
    assert _busy(sid) is False


def test_concurrent_send_while_busy_is_refused(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    sql("UPDATE assistant_session SET busy_since = now() WHERE id = :i", i=sid)

    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "assistant_busy"
    assert "sigue trabajando" in r.json()["error"]["message"]

    assert sql("SELECT count(*) FROM assistant_message WHERE session_id = :i", i=sid)[0][0] == 0
    assert fake.SHARED.requests == []
    assert _busy(sid) is True

    r = client.get(f"/api/assistant/sessions/{sid}")
    assert r.json()["busy"] is True
    r = client.get("/api/assistant/sessions")
    assert r.json()["sessions"][0]["busy"] is True


def test_stale_claim_is_reclaimed_with_notice(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    sql("UPDATE assistant_session SET busy_since = now() - interval '2 hours' WHERE id = :i",
        i=sid)

    r = client.get(f"/api/assistant/sessions/{sid}")
    assert r.json()["busy"] is False

    fake.SHARED.queue(_chat_reply("Hola."))
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202, r.json()

    msgs = r.json()["messages"]
    assert msgs[0]["role"] == "assistant"
    assert msgs[0]["content"] == t(service._INTERRUPTED_TEXT)
    assert msgs[1]["role"] == "user"
    assert msgs[-1]["role"] == "assistant"
    assert msgs[-1]["content"] == "Hola."
    assert _busy(sid) is False


def test_actions_refused_while_busy(superuser):
    client = reauth(signed_in("root@example.com"))
    sid = _new_session(client)
    sql("UPDATE assistant_session SET busy_since = now() WHERE id = :i", i=sid)
    budget_before = sql("SELECT token_budget FROM assistant_session WHERE id = :i", i=sid)[0][0]

    for path in [
        f"/api/assistant/sessions/{sid}/preview",
        f"/api/assistant/sessions/{sid}/apply",
        f"/api/assistant/sessions/{sid}/archive",
        f"/api/assistant/sessions/{sid}/budget",
    ]:
        r = client.post(path)
        assert r.status_code == 409, (path, r.json())
        assert r.json()["error"]["code"] == "assistant_busy"

    assert sql("SELECT status FROM assistant_session WHERE id = :i", i=sid)[0][0] == "open"
    assert sql("SELECT token_budget FROM assistant_session WHERE id = :i", i=sid)[0][0] == \
        budget_before
    assert sql("SELECT count(*) FROM audit_event WHERE kind IN "
               "('assistant_session_archived', 'assistant_budget_extended')")[0][0] == 0


def test_release_only_clears_own_claim(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    sql("UPDATE assistant_session SET busy_since = now() WHERE id = :i", i=sid)
    service._release(sid, datetime(2020, 1, 1, tzinfo=UTC))
    assert _busy(sid) is True


def test_heartbeat_refreshes_busy_since_each_round(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    seen = {"round1": None, "round2": None, "round3": None}

    def round1(messages, tools, system):
        seen["round1"] = sql(
            "SELECT busy_since FROM assistant_session WHERE id = :i", i=sid)[0][0]
        return _chat_reply(tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
                           stop_reason="tool_use")

    def round2(messages, tools, system):
        seen["round2"] = sql(
            "SELECT busy_since FROM assistant_session WHERE id = :i", i=sid)[0][0]
        return _chat_reply(tool_calls=[_tool_call("list_sources", {}, call_id="c2")],
                           stop_reason="tool_use")

    def round3(messages, tools, system):
        seen["round3"] = sql(
            "SELECT busy_since FROM assistant_session WHERE id = :i", i=sid)[0][0]
        return _chat_reply("Listo.")

    fake.SHARED.queue(round1, round2, round3)
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202, r.json()
    assert seen["round1"] is not None
    assert seen["round2"] is not None
    assert seen["round3"] is not None
    assert seen["round1"] < seen["round2"] < seen["round3"]
    assert _busy(sid) is False


def test_lost_claim_stops_turn(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    def round1(messages, tools, system):
        return _chat_reply(tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
                           stop_reason="tool_use")

    def round2(messages, tools, system):
        sql("UPDATE assistant_session SET busy_since = now() + interval '1 second' WHERE id = :i",
            i=sid)
        return _chat_reply(tool_calls=[_tool_call("list_sources", {}, call_id="c2")],
                           stop_reason="tool_use")

    def round3(messages, tools, system):
        return _chat_reply("Nunca.")

    fake.SHARED.queue(round1, round2, round3)
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202, r.json()
    count = sql("SELECT count(*) FROM assistant_message WHERE session_id = :i", i=sid)[0][0]
    assert count == 3
    assert _busy(sid) is True
    assert len(fake.SHARED.requests) == 2
    assert not any(m["content"] == service._UNEXPECTED_TEXT for m in r.json()["messages"])


def test_guard_answers_while_row_is_locked(superuser):
    client = reauth(signed_in("root@example.com"))
    sid = _new_session(client)
    sql("UPDATE assistant_session SET busy_since = now() WHERE id = :i", i=sid)
    with get_engine().connect() as conn:
        conn.execute(text(f'SET LOCAL search_path TO "{TEST_SCHEMA}"'))
        conn.execute(text("SELECT id FROM assistant_session WHERE id = :i FOR UPDATE"),
                     {"i": sid})
        start = time.monotonic()
        r = client.post(f"/api/assistant/sessions/{sid}/archive")
        elapsed = time.monotonic() - start
        assert r.status_code == 409, r.json()
        assert r.json()["error"]["code"] == "assistant_busy"
        assert elapsed < 5
        conn.rollback()
    status = sql("SELECT status FROM assistant_session WHERE id = :i", i=sid)[0][0]
    assert status == "open"
