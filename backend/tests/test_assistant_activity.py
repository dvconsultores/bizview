"""Feature 017 Phase 15: run activity for the agent map (GET /activity)."""
import pytest

from app.ai import fake
from app.assistant import activity, service
from app.config import get_settings
from app.db import get_sessionmaker
from app.models import AssistantSession
from tests.conftest import make_user, new_chat, signed_in, sql
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


def _post_message(client, sid: int):
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.status_code == 202, r.json()
    return r.json()


def _get_activity(client, sid: int) -> dict:
    r = client.get(f"/api/assistant/sessions/{sid}/activity")
    assert r.status_code == 200, r.json()
    return r.json()


def _get_session(client, sid: int) -> dict:
    r = client.get(f"/api/assistant/sessions/{sid}")
    assert r.status_code == 200, r.json()
    return r.json()


def test_new_session_has_no_run(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    data = _get_activity(client, sid)
    assert data["busy"] is False
    assert isinstance(data["model"], str)
    assert data["run"] is None
    assert data["rounds"] == []
    assert data["background"] == []
    assert data["runs"] == []


def test_current_is_visible_while_a_tool_runs(superuser, monkeypatch):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    captured = {}

    def wrapper(*args, **kwargs):
        with get_sessionmaker()() as s:
            captured["activity"] = activity.activity_json(
                s, sid, superuser.id, get_settings()
            )
        return original(*args, **kwargs)

    original = service.run_tool
    monkeypatch.setattr(service, "run_tool", wrapper)

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=(_tool_call("list_sources", {}, call_id="c1"),),
            stop_reason="tool_use",
        )
    )
    fake.SHARED.queue(_chat_reply("Listo."))

    _post_message(client, sid)

    assert captured["activity"]["busy"] is True
    assert captured["activity"]["run"]["status"] == "running"
    assert captured["activity"]["run"]["current"]["tool"] == "list_sources"
    assert captured["activity"]["run"]["current"]["label"] == "Lista de fuentes"
    assert captured["activity"]["rounds"][-1]["tools"][-1]["status"] == "running"
    assert captured["activity"]["run"]["round"] == 1
    assert captured["activity"]["run"]["tokens"] == 15

    data = _get_activity(client, sid)
    assert data["busy"] is False
    assert data["run"]["status"] == "done"
    assert data["run"]["current"] is None
    assert data["run"]["finished_at"] is not None
    assert data["run"]["round"] == 2
    assert data["run"]["tokens"] == 30
    assert data["run"]["tools"] == 1
    assert data["rounds"][0]["n"] == 1
    assert data["rounds"][0]["tools"][0]["status"] == "ok"
    assert isinstance(data["rounds"][0]["tools"][0]["ms"], int)
    assert data["rounds"][0]["tools"][0]["ms"] >= 0
    assert data["rounds"][1] == {"n": 2, "tools": []}
    assert data["runs"][-1]["status"] == "done"
    assert data["runs"][-1]["rounds"] == 2
    assert data["runs"][-1]["tokens"] == 30
    assert data["runs"][-1]["tools"] == 1

    session_data = _get_session(client, sid)
    assert session_data["stats"]["runs"] == data["runs"]


def test_between_rounds_shows_finished_tool(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=(_tool_call("list_sources", {}, call_id="c1"),),
            stop_reason="tool_use",
        )
    )

    captured = {}

    def step(messages, tools, system):
        with get_sessionmaker()() as s:
            captured["activity"] = activity.activity_json(
                s, sid, superuser.id, get_settings()
            )
        return _chat_reply("Listo.")

    fake.SHARED.queue(step)

    _post_message(client, sid)

    assert captured["activity"]["run"]["current"] is None
    assert captured["activity"]["run"]["status"] == "running"
    assert captured["activity"]["rounds"][0]["tools"][0]["status"] == "ok"

    data = _get_activity(client, sid)
    assert data["run"]["status"] == "done"


def test_tool_error_is_marked(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=(_tool_call("describe_source", {}, call_id="c1"),),
            stop_reason="tool_use",
        )
    )
    fake.SHARED.queue(_chat_reply("Listo."))

    _post_message(client, sid)
    data = _get_activity(client, sid)
    assert data["rounds"][0]["tools"][0]["status"] == "error"
    assert data["run"]["status"] == "done"


def test_round_limit_status(superuser, monkeypatch):
    monkeypatch.setenv("AI_CHAT_MAX_ROUNDS", "1")
    get_settings.cache_clear()

    client = signed_in("root@example.com")
    sid = _new_session(client)

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=(_tool_call("list_sources", {}, call_id="c1"),),
            stop_reason="tool_use",
        )
    )
    fake.SHARED.queue(_chat_reply("Hecho: x\nSiguiente: y"))

    _post_message(client, sid)
    data = _get_activity(client, sid)
    assert data["run"]["status"] == "limit"
    assert data["run"]["tokens"] == 30


def test_unexpected_error_status(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=(_tool_call("list_sources", {}, call_id="c1"),),
            stop_reason="tool_use",
        )
    )

    def boom(messages, tools, system):
        raise RuntimeError("boom")

    fake.SHARED.queue(boom)

    _post_message(client, sid)
    data = _get_activity(client, sid)
    assert data["run"]["status"] == "error"
    assert data["busy"] is False
    assert data["runs"][-1]["status"] == "error"
    assert data["rounds"][0]["tools"][0]["status"] == "ok"


def test_stop_marks_run_stopped(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=(_tool_call("list_sources", {}, call_id="c1"),),
            stop_reason="tool_use",
        )
    )

    def step(messages, tools, system):
        with get_sessionmaker()() as s:
            session = s.get(AssistantSession, sid)
            service.stop(s, session, get_settings())
            s.commit()
        return _chat_reply(
            tool_calls=(_tool_call("list_sources", {}, call_id="c2"),),
            stop_reason="tool_use",
        )

    fake.SHARED.queue(step)
    fake.SHARED.queue(_chat_reply("Nunca."))

    _post_message(client, sid)
    data = _get_activity(client, sid)
    assert data["run"]["status"] == "stopped"
    assert data["busy"] is False
    assert data["run"]["current"] is None
    assert data["runs"][-1]["status"] == "stopped"
    assert len(fake.SHARED.requests) == 2


def test_dead_run_reported_as_error_and_closed_on_next_message(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    fake.SHARED.queue(_chat_reply("Hola."))
    _post_message(client, sid)

    sql(
        "UPDATE assistant_session SET working_state = "
        "jsonb_set(working_state, '{run,status}', '\"running\"') WHERE id = :i",
        i=sid,
    )

    data = _get_activity(client, sid)
    assert data["run"]["status"] == "error"

    fake.SHARED.queue(_chat_reply("Otra."))
    _post_message(client, sid)

    data = _get_activity(client, sid)
    assert data["run"]["id"] == 2
    assert data["run"]["status"] == "done"
    assert [r["status"] for r in data["runs"]] == ["done", "error", "done"]
    assert [r["id"] for r in data["runs"]] == [1, 1, 2]


def test_background_preview(superuser):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    project_id = sql("SELECT project_id FROM assistant_session WHERE id = :i", i=sid)[0][0]
    rows = sql(
        "INSERT INTO assistant_preview_request (session_id, project_id) "
        "VALUES (:i, :p) RETURNING id",
        i=sid, p=project_id,
    )
    preview_id = rows[0][0]

    data = _get_activity(client, sid)
    assert len(data["background"]) == 1
    assert data["background"][0]["kind"] == "preview"
    assert data["background"][0]["status"] == "pending"
    assert isinstance(data["background"][0]["since"], str)

    sql("UPDATE assistant_preview_request SET taken_at = now() WHERE id = :i", i=preview_id)
    data = _get_activity(client, sid)
    assert data["background"][0]["status"] == "running"

    sql(
        "UPDATE assistant_preview_request SET finished_at = now() WHERE id = :i",
        i=preview_id,
    )
    data = _get_activity(client, sid)
    assert data["background"] == []


def test_activity_is_owner_only(superuser):
    root = signed_in("root@example.com")
    sid = _new_session(root)

    other = make_user("other@example.com", role="admin")
    other_client = signed_in("other@example.com")

    r = other_client.get(f"/api/assistant/sessions/{sid}/activity")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"

    sql(
        "UPDATE assistant_session SET created_by = :u WHERE id = :s",
        u=other.id,
        s=sid,
    )
    r = root.get(f"/api/assistant/sessions/{sid}/activity")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"

    r = root.get("/api/assistant/sessions/999999999/activity")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
