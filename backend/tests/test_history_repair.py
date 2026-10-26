"""Feature 036, US3: a conversation that already lost its pairing can be repaired.

The migration does this once for every conversation; `POST /sessions/{id}/repair` does it for one,
on demand, which is what the reader presses when the bubble says «history_invalid».
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.ai import ChatReply, ChatUsage, fake
from app.assistant import history, repair
from app.config import get_settings
from app.models import AssistantMessage, AssistantSession
from tests.conftest import chat_project_id, signed_in, sql


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


def _broken_session(db, owner) -> AssistantSession:
    """The production shape: a note between the call and its result, plus a preview notice."""
    session = AssistantSession(title="roto", created_by=owner.id,
                               project_id=chat_project_id(db, owner.id))
    db.add(session)
    db.flush()
    db.add(AssistantMessage(session_id=session.id, role="user", content="continua"))
    db.add(AssistantMessage(session_id=session.id, role="assistant", content="",
                            tool_payload={"calls": [{"id": "call_00_g9JN", "name": "apply_draft",
                                                      "args": {}}]}))
    db.add(AssistantMessage(session_id=session.id, role="assistant",
                            content="Contrato del run autorizado: draft, preview, apply."))
    db.add(AssistantMessage(session_id=session.id, role="tool", tool_name="apply_draft",
                            content="Aplicó la versión 12.",
                            tool_payload={"call_id": "call_00_g9JN",
                                          "result": {"version": 12}}))
    db.add(AssistantMessage(session_id=session.id, role="tool", tool_name="preview",
                            content="Vista previa lista.",
                            tool_payload={"result": {"lines": []}}))
    db.commit()
    return session


def test_repair_pairs_the_result_and_flags_the_preview_notice(superuser, db):
    session = _broken_session(db, superuser)

    report = repair.repair(db, session.id)
    db.flush()

    assert report["paired"] == 1
    assert report["orphans"] == 1                     # the preview notice cannot be replayed
    rows = {row.tool_name: row for row in db.scalars(
        select(AssistantMessage).where(AssistantMessage.session_id == session.id))}
    applied = rows["apply_draft"]
    assert applied.assistant_message_id is not None      # paired with the turn that asked
    assert applied.call_id == "call_00_g9JN" and applied.orphan is False
    assert rows["preview"].orphan is True                # a preview notice cannot be replayed

    built = history.build(history.load(db, session.id, window=None))
    assert [m.role for m in built.messages] == ["user", "assistant", "tool", "assistant"]
    assert built.dropped == [f"tool:{rows['preview'].id}:-"]   # the notice stays in the panel only


def test_repair_is_idempotent(superuser, db):
    session = _broken_session(db, superuser)
    repair.repair(db, session.id)
    db.flush()
    again = repair.repair(db, session.id)
    assert again == {"call_ids": 0, "paired": 0, "orphans": 0}


def test_the_endpoint_repairs_and_audits(superuser, db):
    session = _broken_session(db, superuser)
    client = signed_in("root@example.com")

    body = client.post(f"/api/assistant/sessions/{session.id}/repair").json()

    assert body["paired"] == 1 and body["orphans"] == 1
    assert body["replayable"] is True
    assert sql("SELECT kind, detail->>'session' FROM audit_event "
               "WHERE kind = 'assistant_conversation_repaired'") == [
        ("assistant_conversation_repaired", str(session.id))]


def test_only_a_superuser_can_repair(superuser, admin, db):
    """The assistant routes are super-user only; repair keeps that rule."""
    session = _broken_session(db, superuser)
    assert signed_in(admin.email).post(
        f"/api/assistant/sessions/{session.id}/repair").status_code == 403


def test_repairing_makes_the_conversation_send_again(superuser, db):
    session = _broken_session(db, superuser)
    client = signed_in("root@example.com")

    # The builder already pairs by call id, so the reader can talk again the moment they upgrade;
    # the repair stores that pairing so it no longer depends on the order of the rows.
    before = history.build(history.load(db, session.id, window=None))
    assert before.noted == [] and [m.role for m in before.messages][:3] == [
        "user", "assistant", "tool"]

    assert client.post(f"/api/assistant/sessions/{session.id}/repair").json()["replayable"]

    fake.SHARED.queue(ChatReply(text="Sigo aquí.", tool_calls=(), usage=ChatUsage(),
                                model="fake"))
    assert client.post(f"/api/assistant/sessions/{session.id}/messages",
                       json={"text": "continua"}).status_code == 202
    for _ in range(100):
        body = client.get(f"/api/assistant/sessions/{session.id}").json()
        if not body["busy"]:
            break
        import time
        time.sleep(0.2)
    assert body["messages"][-1]["content"] == "Sigo aquí."
    # The provider received the repaired exchange, with the result answering its own call.
    sent = fake.SHARED.requests[-1]["messages"]
    roles = [message["role"] for message in sent]
    assert "tool" in roles
    assert roles[roles.index("tool") - 1] == "assistant"


def test_repair_all_walks_every_conversation(superuser, db):
    first = _broken_session(db, superuser)
    second = _broken_session(db, superuser)
    by_session = repair.repair_everything(db)
    assert by_session.get(first.id) == 1 and by_session.get(second.id) == 1
