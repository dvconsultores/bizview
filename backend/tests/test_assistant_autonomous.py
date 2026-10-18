"""Feature 017 amendment 2026-10-05: autonomous runs (FR-018..FR-020)."""

import threading

import pytest

from app.ai import fake
from app.assistant import readiness, service
from app.config import get_settings
from app.i18n import t
from tests.conftest import new_chat, signed_in, sql
from tests.test_assistant_api import _chat_reply, _stored_session, _tool_call


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


def _threaded(monkeypatch):
    threads: list[threading.Thread] = []

    def runner(*args):
        t = threading.Thread(target=service.run_turn, args=args, daemon=True)
        threads.append(t)
        t.start()

    monkeypatch.setattr(service, "RUNNER", runner)
    return threads


def _join(threads):
    for th in threads:
        th.join(10)
        assert not th.is_alive()


def test_send_returns_202_and_run_finishes_in_background(superuser, db, monkeypatch):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    threads = _threaded(monkeypatch)
    gate = threading.Event()

    def first(messages, tools, system):
        assert gate.wait(10)
        return _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        )

    fake.SHARED.queue(first, _chat_reply("Listo."))
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202
    assert [m["role"] for m in r.json()["messages"]] == ["user"]
    assert r.json()["session"]["busy"] is True
    assert sql("SELECT busy_since FROM assistant_session WHERE id = :i", i=sid)[0][0] is not None

    gate.set()
    _join(threads)

    session = client.get(f"/api/assistant/sessions/{sid}").json()
    assert session["busy"] is False
    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
    )
    assert [row[0] for row in rows] == ["user", "assistant", "tool", "assistant"]
    assert rows[-1][1] == "Listo."
    assert sql("SELECT busy_since FROM assistant_session WHERE id = :i", i=sid)[0][0] is None


def test_capacity_full_is_refused(superuser, db, monkeypatch):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(service, "_SLOTS", slots)
    slots.acquire()

    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "assistant_capacity"
    assert r.json()["error"]["message"] == t(service.CAPACITY_TEXT)
    assert sql("SELECT count(*) FROM assistant_message WHERE session_id = :i", i=sid)[0][0] == 0
    assert sql("SELECT busy_since FROM assistant_session WHERE id = :i", i=sid)[0][0] is None
    assert fake.SHARED.requests == []

    slots.release()
    fake.SHARED.queue(_chat_reply("Hola."))
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202
    assert slots.acquire(blocking=False) is True
    slots.release()


def test_budget_extends_automatically_and_is_audited(superuser, db):
    client = signed_in("root@example.com")
    s = _stored_session(db, superuser, status="open", tokens_used=199990)
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        ),
        _chat_reply("Sigo."),
    )
    r = client.post(f"/api/assistant/sessions/{s.id}/messages", json={"text": "Continúa"})
    assert r.status_code == 202
    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=s.id
    )
    assert rows[-1][1] == "Sigo."
    assert sql("SELECT token_budget FROM assistant_session WHERE id = :i", i=s.id)[0][0] == 300000
    audit = sql(
        "SELECT actor_id, ip, detail FROM audit_event WHERE kind = 'assistant_budget_extended'"
    )
    assert audit == [(None, None, {"session": s.id, "from": 200000, "to": 300000, "auto": True})]
    assert len(fake.SHARED.requests) == 2


def test_hard_budget_max_stops_the_run(superuser, db, monkeypatch):
    monkeypatch.setenv("AI_CHAT_BUDGET_MAX", "200000")
    get_settings.cache_clear()
    client = signed_in("root@example.com")
    s = _stored_session(db, superuser, status="open", tokens_used=199990)
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        ),
        _chat_reply("No debe llegar."),
    )
    r = client.post(f"/api/assistant/sessions/{s.id}/messages", json={"text": "Continúa"})
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == 1
    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=s.id
    )
    assert rows[-1][1].startswith(t(service._BUDGET_TEXT))
    assert t(service._BUDGET_HINT) in rows[-1][1]
    assert "AI_CHAT_BUDGET_MAX" in rows[-1][1]
    assert "conversación nueva" in rows[-1][1]
    audit_count = sql(
        "SELECT count(*) FROM audit_event WHERE kind = 'assistant_budget_extended'"
    )[0][0]
    assert audit_count == 0
    assert sql("SELECT token_budget FROM assistant_session WHERE id = :i", i=s.id)[0][0] == 200000


def test_stop_releases_claim_and_run_exits_quietly(superuser, db, monkeypatch):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    threads = _threaded(monkeypatch)
    reached = threading.Event()
    gate = threading.Event()

    def round2(messages, tools, system):
        reached.set()
        assert gate.wait(10)
        return _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c2")],
            stop_reason="tool_use",
        )

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        ),
        round2,
        _chat_reply("Nunca."),
    )
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202
    assert reached.wait(10)

    r = client.post(f"/api/assistant/sessions/{sid}/stop")
    assert r.status_code == 200
    assert r.json()["busy"] is False
    assert sql("SELECT busy_since FROM assistant_session WHERE id = :i", i=sid)[0][0] is None

    gate.set()
    _join(threads)

    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
    )
    assert [row[0] for row in rows] == ["user", "assistant", "tool", "assistant"]
    assert rows[-1][1] == t(service._STOPPED_TEXT)
    assert t(service._UNEXPECTED_TEXT) not in [row[1] for row in rows]
    assert "Nunca." not in [row[1] for row in rows]
    assert len(fake.SHARED.requests) == 2
    assert sql("SELECT busy_since FROM assistant_session WHERE id = :i", i=sid)[0][0] is None

    monkeypatch.setattr(service, "RUNNER", service.run_turn)
    fake.SHARED.reset()
    fake.SHARED.queue(_chat_reply("Otra vez."))
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Otra vez"})
    assert r.status_code == 202
    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
    )
    assert rows[-1][1] == "Otra vez."
    assert t(service._INTERRUPTED_TEXT) not in [row[1] for row in rows]


def test_stop_when_not_running_and_permissions(superuser, admin, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)

    r = client.post(f"/api/assistant/sessions/{sid}/stop")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "not_running"

    sql(
        "UPDATE assistant_session SET busy_since = now() - interval '2 hours' WHERE id = :i",
        i=sid,
    )
    r = client.post(f"/api/assistant/sessions/{sid}/stop")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "not_running"

    admin_client = signed_in("admin@example.com")
    r = admin_client.post(f"/api/assistant/sessions/{sid}/stop")
    assert r.status_code == 403

    sql("UPDATE assistant_session SET busy_since = now() WHERE id = :i", i=sid)
    r = client.post(f"/api/assistant/sessions/{sid}/stop")
    assert r.status_code == 200
    assert r.json()["busy"] is False
    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
    )
    assert rows[-1][1] == t(service._STOPPED_TEXT)
    assert sql("SELECT busy_since FROM assistant_session WHERE id = :i", i=sid)[0][0] is None


def test_readiness_reached_stops_the_run(superuser, db, monkeypatch):
    state = {"ready": False}
    monkeypatch.setattr(
        readiness,
        "compute",
        lambda session, user_texts=None: {"ready": state["ready"], "pending": []},
    )
    client = signed_in("root@example.com")
    sid = new_chat(client)

    def step1(messages, tools, system):
        state["ready"] = True
        return _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        )

    fake.SHARED.queue(step1, _chat_reply("No debe llegar."))
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == 1
    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
    )
    project = client.get(f"/api/assistant/sessions/{sid}").json()["project"]["name"]
    assert rows[-1][1] == t(service._READY_TEXT, summary=project)   # 020: the project is the draft


def test_readiness_reached_keeps_model_text(superuser, db, monkeypatch):
    state = {"ready": False}
    monkeypatch.setattr(
        readiness,
        "compute",
        lambda session, user_texts=None: {"ready": state["ready"], "pending": []},
    )
    client = signed_in("root@example.com")
    sid = new_chat(client)

    def step1(messages, tools, system):
        state["ready"] = True
        return _chat_reply(
            text="Listo para aplicar: ventas.",
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        )

    fake.SHARED.queue(step1, _chat_reply("No debe llegar."))
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == 1
    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
    )
    assert rows[-1][0] == "tool"
    assert t(service._READY_TEXT, summary="el borrador") not in [row[1] for row in rows]


def test_already_ready_draft_does_not_stop_early(superuser, db, monkeypatch):
    monkeypatch.setattr(
        readiness,
        "compute",
        lambda session, user_texts=None: {"ready": True, "pending": []},
    )
    client = signed_in("root@example.com")
    sid = new_chat(client)
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        ),
        _chat_reply("Cambié el título."),
    )
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == 2
    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
    )
    assert rows[-1][1] == "Cambié el título."


def test_repeated_failing_call_stops(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("describe_source", {}, call_id="c1")],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[_tool_call("describe_source", {}, call_id="c2")],
            stop_reason="tool_use",
        ),
        _chat_reply("No debe llegar."),
    )
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == 2
    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
    )
    last = rows[-1][1]
    assert last.startswith(
        "Detuve el trabajo: describe_source falló dos veces seguidas"
    )
    assert "El nombre de la fuente es obligatorio." in last
    assert "Hecho:" in last
    assert "Siguiente:" in last


def test_different_failing_calls_do_not_stop(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("describe_source", {}, call_id="c1")],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c2")],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[_tool_call("describe_source", {}, call_id="c3")],
            stop_reason="tool_use",
        ),
        _chat_reply("Sigo."),
    )
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == 4
    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
    )
    assert rows[-1][1] == "Sigo."


def test_round_limit_default_is_60():
    from app.config import Settings

    assert Settings.model_fields["ai_chat_max_rounds"].default == 60
    assert Settings.model_fields["ai_agent_max_concurrent"].default == 4


def test_stopped_run_late_error_is_not_posted(superuser, db, monkeypatch):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    threads = _threaded(monkeypatch)
    reached = threading.Event()
    gate = threading.Event()

    def round2(messages, tools, system):
        reached.set()
        assert gate.wait(10)
        raise RuntimeError("boom")

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        ),
        round2,
        _chat_reply("Nunca."),
    )
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202
    assert reached.wait(10)

    r = client.post(f"/api/assistant/sessions/{sid}/stop")
    assert r.status_code == 200
    assert r.json()["busy"] is False
    assert sql("SELECT busy_since FROM assistant_session WHERE id = :i", i=sid)[0][0] is None

    gate.set()
    _join(threads)

    rows = sql(
        "SELECT role, content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
    )
    assert [row[0] for row in rows] == ["user", "assistant", "tool", "assistant"]
    assert rows[-1][1] == t(service._STOPPED_TEXT)
    assert all(row[1] != t(service._UNEXPECTED_TEXT) for row in rows)
    state = sql("SELECT working_state FROM assistant_session WHERE id = :i", i=sid)[0][0]
    assert state["run"]["status"] == "stopped"


def test_stopped_run_late_error_never_reaches_newer_run(superuser, db, monkeypatch):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    threads = _threaded(monkeypatch)
    reached_a = threading.Event()
    gate_a = threading.Event()
    reached_b = threading.Event()
    gate_b = threading.Event()

    def round_a2(messages, tools, system):
        reached_a.set()
        assert gate_a.wait(10)
        raise RuntimeError("boom")

    def first_b(messages, tools, system):
        reached_b.set()
        assert gate_b.wait(10)
        return _chat_reply("Listo B.")

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        ),
        round_a2,
        first_b,
    )

    try:
        r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
        assert r.status_code == 202
        assert reached_a.wait(10)

        r = client.post(f"/api/assistant/sessions/{sid}/stop")
        assert r.status_code == 200

        r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Otra"})
        assert r.status_code == 202
        assert reached_b.wait(10)

        gate_a.set()
        threads[0].join(10)
        assert not threads[0].is_alive()

        rows = sql(
            "SELECT content FROM assistant_message WHERE session_id = :i", i=sid
        )
        assert all(row[0] != service._UNEXPECTED_TEXT for row in rows)
        busy = sql(
            "SELECT busy_since FROM assistant_session WHERE id = :i", i=sid
        )[0][0]
        assert busy is not None
        state = sql(
            "SELECT working_state FROM assistant_session WHERE id = :i", i=sid
        )[0][0]
        assert state["run"]["status"] == "running"

        gate_b.set()
        _join(threads)

        rows = sql(
            "SELECT content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid
        )
        assert rows[-1][0] == "Listo B."
        assert all(row[0] != service._UNEXPECTED_TEXT for row in rows)
        busy = sql(
            "SELECT busy_since FROM assistant_session WHERE id = :i", i=sid
        )[0][0]
        assert busy is None
        state = sql(
            "SELECT working_state FROM assistant_session WHERE id = :i", i=sid
        )[0][0]
        assert state["run"]["status"] == "done"
    finally:
        gate_a.set()
        gate_b.set()
