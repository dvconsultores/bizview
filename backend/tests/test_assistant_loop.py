"""Feature 017: agent loop, working state, history compaction, budget and preview PDF."""
from __future__ import annotations

import json

import pytest
from bizview_cli import authoring

from app.ai import AIError, ChatReply, ChatUsage, ToolCall, fake
from app.assistant import service, tools
from app.config import get_settings
from app.i18n import t
from app.models import AssistantMessage, AssistantSession
from app.projects.workview import for_session
from tests.conftest import new_chat, signed_in, sql, v2_files
from tests.test_assistant_api import (
    _chat_reply,
    _stored_session,
    _tool_call,
    _valid_draft_files,
)
from tests.test_assistant_preview import _draft, _run_preview, _session
from tests.test_runner import origin as origin
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import apply, lock
from tests.test_vibe_reporting import workspace as workspace

# 017 loop mechanics through plain-mode tools; the 021 command guard has its own tests.
pytestmark = pytest.mark.usefixtures("without_command_guard")


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


def _raise_context(messages, tools, system):
    raise AIError("context_too_long")


def _raise_rate_limited(messages, tools, system):
    raise AIError("rate_limited")


def _unwrap(content: str) -> str:
    """The JSON inside a tool result's untrusted-data block (021 plan §8)."""
    assert content.startswith('<datos origen="herramienta:'), content[:60]
    return content.split("\n", 1)[1].rsplit("\n</datos>", 1)[0]


def _new_session(client) -> int:
    return new_chat(client)


def _send(client, sid: int, text: str):
    return client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": text}).json()


def test_stable_system_prefix_across_rounds_and_sessions(superuser, db):
    client = signed_in("root@example.com")
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        ),
        _chat_reply("Listo."),
    )
    sid_a = _new_session(client)
    _send(client, sid_a, "propón")
    fake.SHARED.queue(_chat_reply("Hola."))
    sid_b = _new_session(client)
    _send(client, sid_b, "hola")

    assert len(fake.SHARED.requests) == 3
    for req in fake.SHARED.requests:
        assert req["system"] == service.system_prefix("es")
        context = req["context"]
        assert context.startswith("## Estado\n")
        assert "Tokens usados:" in context
    assert authoring.summary() in service.system_prefix("es")
    assert "## Estado" not in service.system_prefix("es")


def test_old_results_summarised_and_old_draft_args_compacted(superuser, db):
    client = signed_in("root@example.com")
    files = v2_files(_valid_draft_files())
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("propose_draft", {"files": files, "summary": "s"},
                                   call_id="c1")],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c2")],
            stop_reason="tool_use",
        ),
        _chat_reply("Listo."),
    )
    sid = _new_session(client)
    _send(client, sid, "propon")

    c1_call = next(
        m for m in fake.SHARED.requests[1]["messages"]
        if m["role"] == "assistant" and m["tool_calls"]
    )["tool_calls"][0]
    assert isinstance(c1_call["args"]["files"], dict)

    c1_call = next(
        m for m in fake.SHARED.requests[2]["messages"]
        if m["role"] == "assistant" and m["tool_calls"]
    )["tool_calls"][0]
    assert c1_call["args"]["files"] == sorted(files)
    c1_tool = next(
        m for m in fake.SHARED.requests[2]["messages"]
        if m["role"] == "tool" and m["tool_call_id"] == "c1"
    )
    assert c1_tool["content"] == "Propuso un borrador (4 archivos)."
    c2_tool = next(
        m for m in fake.SHARED.requests[2]["messages"]
        if m["role"] == "tool" and m["tool_call_id"] == "c2"
    )
    assert list(json.loads(_unwrap(c2_tool["content"])).keys()) == ["sources"]

    db.expire_all()
    stored = db.query(AssistantMessage).filter(
        AssistantMessage.session_id == sid,
        AssistantMessage.role == "assistant",
        AssistantMessage.tool_payload.isnot(None),
    ).order_by(AssistantMessage.id).all()
    assert stored[0].tool_payload["calls"][0]["args"]["files"] == sorted(files)

    fake.SHARED.queue(_chat_reply("Sigo."))
    _send(client, sid, "sigue")
    req3 = fake.SHARED.requests[3]
    assert req3["messages"][0]["role"] == "user"
    assert req3["messages"][0]["content"] == "propon"
    c1_tool3 = next(
        m for m in req3["messages"]
        if m["role"] == "tool" and m["tool_call_id"] == "c1"
    )
    assert c1_tool3["content"] == "Propuso un borrador (4 archivos)."
    c2_tool3 = next(
        m for m in req3["messages"]
        if m["role"] == "tool" and m["tool_call_id"] == "c2"
    )
    assert list(json.loads(_unwrap(c2_tool3["content"])).keys()) == ["sources"]


def test_working_state_cache_avoids_second_describe(superuser, db, pg_source):
    client = signed_in("root@example.com")
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("describe_source", {"name": "Origen prueba"},
                                   call_id="c1")],
            stop_reason="tool_use",
        ),
        _chat_reply("Listo."),
    )
    sid = _new_session(client)
    _send(client, sid, "describe")

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("describe_source", {"name": "Origen prueba"},
                                   call_id="c2")],
            stop_reason="tool_use",
        ),
        _chat_reply("Sigo."),
    )
    resp = _send(client, sid, "continúa")
    audit_count = sql("SELECT count(*) FROM audit_event WHERE kind = 'source_described'")[0][0]
    assert audit_count == 1
    tool_messages = [m for m in resp["messages"] if m["role"] == "tool"]
    assert tool_messages[-1]["content"] == "Usó la estructura ya consultada de «Origen prueba»."
    assert "Fuentes consultadas:" in fake.SHARED.requests[2]["context"]


def test_round_limit_posts_progress(superuser, db, monkeypatch):
    monkeypatch.setenv("AI_CHAT_MAX_ROUNDS", "2")
    get_settings.cache_clear()
    client = signed_in("root@example.com")
    for call_id in ("c1", "c2"):
        fake.SHARED.queue(
            _chat_reply(
                tool_calls=[_tool_call("list_sources", {}, call_id=call_id)],
                stop_reason="tool_use",
            )
        )
    fake.SHARED.queue(_chat_reply("Hecho: listé las fuentes. Siguiente: describir la tabla."))
    sid = _new_session(client)
    resp = _send(client, sid, "hola")
    messages = resp["messages"]
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"].startswith("Hecho: listé")
    assert "continúa" in messages[-1]["content"]
    assert len(fake.SHARED.requests) == 3
    last_req = fake.SHARED.requests[-1]
    assert last_req["tools"] == []
    assert len(last_req["messages"]) == 1
    assert last_req["messages"][0]["role"] == "user"
    assert "Acciones de este mensaje:" in last_req["messages"][0]["content"]
    assert "Consultó la lista de fuentes." in last_req["messages"][0]["content"]
    db.expire_all()
    s = db.get(AssistantSession, sid)
    assert s.working_state["progress"].startswith("Hecho:")
    assert s.stats["rounds"] == 3


def test_round_limit_composed_progress_when_model_fails(superuser, db, monkeypatch):
    monkeypatch.setenv("AI_CHAT_MAX_ROUNDS", "1")
    get_settings.cache_clear()
    client = signed_in("root@example.com")
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call(
                "update_notes",
                {"next": "describir la tabla", "done_add": ["listé las fuentes"]},
            )],
            stop_reason="tool_use",
        )
    )
    fake.SHARED.queue(_raise_rate_limited)
    sid = _new_session(client)
    resp = _send(client, sid, "hola")
    last = resp["messages"][-1]
    assert "Llegué al límite de 1 rondas" in last["content"]
    assert "Hecho: listé las fuentes" in last["content"]
    assert "Siguiente: describir la tabla" in last["content"]
    assert t(service._CONTINUE_HINT) in last["content"]


def test_round_limit_progress_follows_an_english_account(superuser, db, monkeypatch):
    """022 T047: the composed progress and its prompt use the owner's language."""
    from app.i18n import use_locale

    monkeypatch.setenv("AI_CHAT_MAX_ROUNDS", "1")
    get_settings.cache_clear()
    client = signed_in("root@example.com")
    assert client.patch("/api/me/preferences", json={"locale": "en"}).status_code == 200
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("update_notes", {"done_add": ["listed the sources"]})],
            stop_reason="tool_use",
        )
    )
    fake.SHARED.queue(_raise_rate_limited)
    sid = _new_session(client)
    last = _send(client, sid, "hello")["messages"][-1]["content"]
    assert "I reached the limit of 1 rounds for this message." in last
    assert "Done: listed the sources" in last
    assert "Next: continue with the draft" in last
    assert "Hecho:" not in last and "Siguiente:" not in last
    with use_locale("en"):
        assert t(service._CONTINUE_HINT) in last
        prompt = service._progress_prompt("hello", ["x"], 3)
    assert "Actions of this message:" in prompt and "«Done:» and «Next:»" in prompt


def test_no_budget_anywhere_in_the_context(superuser, db):
    """Feature 028 revision (owner, 2026-10-21: "make the ai unlimited").

    The context reports the tokens spent and never a ceiling or a percentage, in any mode: a
    percentage in the prompt makes the model stop on its own even though nothing stops it.
    """
    client = signed_in("root@example.com")
    s = _stored_session(db, superuser, status="open", tokens_used=9_000_000)
    body = client.get(f"/api/assistant/sessions/{s.id}").json()
    assert "budget_warning" not in body and "budget_max" not in body
    assert "token_budget" not in body
    assert body["tokens_used"] == 9_000_000

    fake.SHARED.queue(_chat_reply("Sí"))
    assert client.post(f"/api/assistant/sessions/{s.id}/messages",
                       json={"text": "hola"}).status_code == 202
    context = fake.SHARED.requests[-1]["context"]
    assert "Tokens usados: 9000000." in context
    assert "Presupuesto" not in context and "%" not in context
    assert "de 2000000 tokens" not in context


def test_session_json_has_agent_fields(superuser, db):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    resp = client.get(f"/api/assistant/sessions/{sid}")
    body = resp.json()
    assert body["working_state"] == {}
    assert isinstance(body["stats"], dict)
    assert body["readiness"]["ready"] is False
    assert body["readiness"]["pending"][0]["code"] == "draft"


def test_budget_route_is_gone(superuser, db):
    """The conversation budget was retired with its endpoint (feature 028 revision)."""
    client = signed_in("root@example.com")
    s = _stored_session(db, superuser, status="open")
    resp = client.post(f"/api/assistant/sessions/{s.id}/budget")
    assert resp.status_code in (404, 405)
    assert sql("SELECT count(*) FROM audit_event "
               "WHERE kind = 'assistant_budget_extended'") == [(0,)]


def test_invalid_json_is_repaired_once(superuser, db):
    client = signed_in("root@example.com")
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[ToolCall(
                id="c1",
                name="list_sources",
                args={},
                args_error="Expecting value (línea 1, columna 5)",
            )],
            stop_reason="tool_use",
        )
    )
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c2")],
            stop_reason="tool_use",
        )
    )
    fake.SHARED.queue(_chat_reply("Listo."))
    sid = _new_session(client)
    resp = _send(client, sid, "hola")
    assert resp["messages"][-1]["content"] == "Listo."
    c1_tool = next(
        m for m in fake.SHARED.requests[1]["messages"]
        if m["role"] == "tool" and m["tool_call_id"] == "c1"
    )
    assert "argumentos JSON no válidos" in c1_tool["content"]
    assert "vuelve a emitir la llamada completa" in c1_tool["content"]
    db.expire_all()
    stored = db.query(AssistantMessage).filter(
        AssistantMessage.session_id == sid,
        AssistantMessage.role == "assistant",
    ).order_by(AssistantMessage.id).first()
    assert stored.tool_payload["calls"][0]["args_error"] is not None
    tool_stored = db.query(AssistantMessage).filter(
        AssistantMessage.session_id == sid,
        AssistantMessage.role == "tool",
    ).order_by(AssistantMessage.id).first()
    assert tool_stored.content == "Argumentos no válidos en list_sources."


def test_invalid_json_twice_stops_and_keeps_draft(superuser, db):
    client = signed_in("root@example.com")
    draft = {"files": {"bizview.yaml": "name: demo\n"}, "summary": "s"}
    s = _stored_session(db, superuser, status="open", draft=draft)
    for call_id in ("c1", "c2"):
        fake.SHARED.queue(
            _chat_reply(
                tool_calls=[ToolCall(
                    id=call_id,
                    name="list_sources",
                    args={},
                    args_error="bad json",
                )],
                stop_reason="tool_use",
            )
        )
    fake.SHARED.queue(_chat_reply("No debe llegar."))
    resp = _send(client, s.id, "hola")
    assert resp["messages"][-1]["content"] == t(service._INVALID_ARGS_TEXT)
    assert len(fake.SHARED.requests) == 2
    db.expire_all()
    refreshed = db.get(AssistantSession, s.id)
    assert refreshed.draft == draft


def test_context_too_long_retries_with_latest_round(superuser, db):
    client = signed_in("root@example.com")
    s = _stored_session(db, superuser, status="open")
    db.add_all([
        AssistantMessage(session_id=s.id, role="user", content="antes"),
        AssistantMessage(session_id=s.id, role="assistant", content="ok"),
    ])
    db.commit()

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
            stop_reason="tool_use",
        )
    )
    fake.SHARED.queue(_raise_context)
    fake.SHARED.queue(_chat_reply("Listo."))
    resp = _send(client, s.id, "nuevo")
    assert resp["messages"][-1]["content"] == "Listo."
    assert len(fake.SHARED.requests) == 3
    assert [m["role"] for m in fake.SHARED.requests[2]["messages"]] == [
        "user", "assistant", "tool"
    ]
    assert fake.SHARED.requests[2]["messages"][0]["content"] == "nuevo"
    assert "antes" in fake.SHARED.requests[1]["messages"][0]["content"]


def test_context_too_long_twice_reports_error(superuser, db):
    client = signed_in("root@example.com")
    fake.SHARED.queue(_raise_context)
    fake.SHARED.queue(_raise_context)
    sid = _new_session(client)
    resp = _send(client, sid, "hola")
    assert resp["messages"][-1]["content"] == AIError("context_too_long").message
    assert len(fake.SHARED.requests) == 2


def test_reasoning_only_in_current_turn(superuser, db):
    client = signed_in("root@example.com")
    fake.SHARED.queue(
        ChatReply(
            text="",
            tool_calls=(_tool_call("list_sources", {}, call_id="c1"),),
            usage=ChatUsage(10, 5),
            model="fake",
            stop_reason="tool_use",
            reasoning="PENSANDO-XYZ",
        )
    )
    fake.SHARED.queue(_chat_reply("Listo."))
    sid = _new_session(client)
    _send(client, sid, "hola")
    assistant_msg = next(
        m for m in fake.SHARED.requests[1]["messages"] if m["role"] == "assistant"
    )
    assert assistant_msg["reasoning"] == "PENSANDO-XYZ"
    count = sql(
        "SELECT count(*) FROM assistant_message "
        "WHERE content LIKE :p OR tool_payload::text LIKE :p",
        p="%PENSANDO-XYZ%",
    )[0][0]
    assert count == 0

    fake.SHARED.queue(_chat_reply("Sigo."))
    _send(client, sid, "segundo")
    for msg in fake.SHARED.requests[2]["messages"]:
        assert msg["reasoning"] is None


def test_update_notes_tool(superuser, db):
    s = _stored_session(
        db,
        superuser,
        status="open",
        working_state={"inspected": {"o": {"public.t": "id int"}}},
    )
    long_goal = "x" * 400
    _, summary = tools.run_tool(
        db,
        superuser,
        s,
        "update_notes",
        {
            "goal": long_goal,
            "decisions_add": ["d1", "d2"],
            "step": "redactar",
            "done_add": ["listar fuentes"],
            "next": "describir",
        },
        get_settings(),
    )
    assert summary == "Actualizó las notas de trabajo."
    assert s.working_state["goal"] == long_goal[:tools.NOTES_TEXT_CHARS]
    assert s.working_state["decisions"] == ["d1", "d2"]
    assert s.working_state["done"] == ["listar fuentes"]
    assert s.working_state["step"] == "redactar"
    assert s.working_state["next"] == "describir"
    assert s.working_state["inspected"] == {"o": {"public.t": "id int"}}

    tools.run_tool(
        db,
        superuser,
        s,
        "update_notes",
        {"decisions_add": [f"d{i}" for i in range(25)]},
        get_settings(),
    )
    assert len(s.working_state["decisions"]) == tools.NOTES_MAX_ITEMS
    assert s.working_state["decisions"][0] == "d5"

    tools.run_tool(db, superuser, s, "update_notes", {"done_add": ["otra"]}, get_settings())
    assert s.working_state["done"] == ["listar fuentes", "otra"]

    tools.run_tool(db, superuser, s, "update_notes", {"goal": ""}, get_settings())
    assert "goal" not in s.working_state

    with pytest.raises(tools.ToolError):
        tools.run_tool(db, superuser, s, "update_notes", {}, get_settings())
    with pytest.raises(tools.ToolError):
        tools.run_tool(db, superuser, s, "update_notes", {"goal": 5}, get_settings())
    with pytest.raises(tools.ToolError):
        tools.run_tool(db, superuser, s, "update_notes", {"done_add": "x"}, get_settings())
    assert [spec["name"] for spec in tools.TOOL_SPECS][-5:] == [
        "update_notes", "get_app_guide", "get_project_overview", "finish_command",
        "suggest_command"]                                    # 023 and 021 tools come last


def test_preview_pdf_route(db, superuser, admin, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))
    client = signed_in("root@example.com")
    s0 = _session(db, superuser, _draft())
    resp = client.post(f"/api/assistant/sessions/{s0.id}/preview/report/ventas2/pdf")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "preview_not_ready"

    s = _run_preview(db, superuser, _draft())
    resp = client.post(
        f"/api/assistant/sessions/{s.id}/preview/report/ventas2/pdf"
        "?period=last_7_days&compare=none"
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert "ventas2-vista-previa.pdf" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF")

    resp = client.post(f"/api/assistant/sessions/{s.id}/preview/report/nope/pdf")
    assert resp.status_code == 404

    admin_client = signed_in("admin@example.com")
    resp = admin_client.post(f"/api/assistant/sessions/{s.id}/preview/report/ventas2/pdf")
    assert resp.status_code == 403


def test_recent_files_block_in_state_suffix(superuser, db):
    client = signed_in("root@example.com")
    sid = _new_session(client)

    files = v2_files(_valid_draft_files())
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=(
                _tool_call("propose_draft", {"files": files, "summary": "s"}, call_id="c1"),
            ),
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=(_tool_call("list_sources", {}, call_id="c2"),),
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=(_tool_call("list_sources", {}, call_id="c3"),),
            stop_reason="tool_use",
        ),
        _chat_reply("Listo."),
    )

    _send(client, sid, "propón")
    marker = "Archivos recientes"
    assert marker not in service.system_prefix("es")

    assert len(fake.SHARED.requests) == 4
    assert marker not in fake.SHARED.requests[0]["context"]

    for i in (1, 2):
        context = fake.SHARED.requests[i]["context"]
        assert marker in context
        after_marker = context.split(marker, 1)[1]
        assert "### reports/ventas2/report.yaml" in after_marker
        assert files["reports/ventas2/report.yaml"] in after_marker

    context3 = fake.SHARED.requests[3]["context"]
    assert marker not in context3

    db.expire_all()
    s = db.get(AssistantSession, sid)
    assert s.working_state["recent_files"] == [[], []]


def test_recent_files_block_is_capped(superuser, db):
    s = _stored_session(
        db,
        superuser,
        status="open",
        draft={
            "files": {
                "queries/a.sql": "a" * 20000,
                "queries/b.sql": "b" * 7000,
                "queries/c.sql": "c" * 10,
                "queries/old.sql": "OLDCONTENT",
            },
            "summary": "s",
        },
        working_state={
            "recent_files": [
                ["queries/c.sql"],
                ["queries/a.sql", "queries/b.sql", "queries/gone.sql"],
            ]
        },
    )

    text = service.state_text(s, get_settings(), [])
    assert text.startswith(service._STATE_HEADER)

    assert "### queries/a.sql" in text
    assert "a" * service.RECENT_FILE_CHARS in text
    assert "a" * (service.RECENT_FILE_CHARS + 1) not in text
    assert "truncado: 20000 caracteres; usa read_draft" in text

    assert "### queries/b.sql" in text
    assert "truncado: 7000 caracteres" in text

    assert "- queries/c.sql (omitido por tamaño; usa read_draft)" in text
    assert "OLDCONTENT" not in text
    assert "gone.sql" not in text

    idx_a = text.index("### queries/a.sql")
    idx_b = text.index("### queries/b.sql")
    assert idx_a < idx_b

    s.working_state = {"recent_files": "bad"}
    db.flush()
    text_bad = service.state_text(s, get_settings(), [])
    assert "Archivos recientes" not in text_bad


def test_a_long_turn_is_never_stopped_by_tokens(superuser, db, pg_source):
    """Feature 028 revision (owner, 2026-10-21: "make the ai unlimited").

    The pre-turn and mid-turn budget stops, and their "amplía el presupuesto" message, are gone:
    a turn that already spent nine million tokens keeps calling tools and finishes.
    """
    client = signed_in("root@example.com")
    s = _stored_session(db, superuser, status="open", tokens_used=9_000_000)

    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("update_notes",
                                   {"goal": "Ventas por día", "next": "proponer el borrador"},
                                   call_id="c1")],
            stop_reason="tool_use"),
        _chat_reply(
            tool_calls=[_tool_call("describe_source", {"name": "Origen prueba"}, call_id="c2")],
            stop_reason="tool_use"),
        _chat_reply(
            tool_calls=[_tool_call("propose_draft",
                                   {"files": v2_files(_valid_draft_files()), "summary": "Ventas 2"},
                                   call_id="c3")],
            stop_reason="tool_use"),
        _chat_reply("Listo."),
    )

    resp = _send(client, s.id, "construye el tablero")

    assert len(fake.SHARED.requests) == 4
    assert resp["messages"][-1]["content"] == "Listo."
    assert [m.get("tool_name") for m in resp["messages"] if m["role"] == "tool"] == [
        "update_notes", "describe_source", "propose_draft"]
    assert sql("SELECT count(*) FROM audit_event "
               "WHERE kind = 'assistant_budget_extended'") == [(0,)]
    db.expire_all()
    s = db.get(AssistantSession, s.id)
    assert s.status == "open"
    body = client.get(f"/api/assistant/sessions/{s.id}").json()
    assert body["draft"] is not None, [m["content"] for m in body["messages"]
                                      if m["role"] == "tool"]


def test_cached_heavy_round_counts_weighted_tokens(superuser, db):
    client = signed_in("root@example.com")
    fake.SHARED.queue(
        ChatReply(
            text="",
            tool_calls=(_tool_call("list_sources", {}, call_id="c1"),),
            usage=ChatUsage(input=10000, output=100, cached=9000),
            model="fake",
            stop_reason="tool_use",
        ),
        ChatReply(
            text="Listo.",
            tool_calls=(),
            usage=ChatUsage(input=2000, output=50, cached=0),
            model="fake",
        ),
    )
    sid = _new_session(client)
    _send(client, sid, "usa fuentes")
    db.expire_all()
    s = db.get(AssistantSession, sid)
    assert s.tokens_used == 4050
    assert s.stats["input_tokens"] == 12000
    assert s.stats["cached_tokens"] == 9000
    assert s.stats["output_tokens"] == 150

    resp = client.get(f"/api/assistant/sessions/{sid}")
    body = resp.json()
    assert "model" in body
    assert body["model"] == get_settings().ai_model_effective


def test_state_suffix_is_bounded_for_large_working_state(superuser, db):
    inspected = {
        "origen": {
            f"public.t{i:02d}": ", ".join(f"col{j} text" for j in range(60))
            for i in range(40)
        }
    }
    inspected["origen"]["consulta integrations/demo/queries/ventas.sql"] = (
        "revisada: columnas ok"
    )
    draft_files = {
        "integrations/demo/queries/ventas.sql": (
            "SELECT col1, col2 FROM public.t03 JOIN public.t07 ON true"
        )
    }
    for i in range(4):
        draft_files[f"integrations/demo/queries/grande{i}.sql"] = "x" * 9000
    recent_files = [[f"integrations/demo/queries/grande{i}.sql"] for i in range(4)]
    sess = _stored_session(
        db,
        superuser,
        status="open",
        draft={"summary": "draft grande", "files": draft_files},
        validation={
            "valid": False,
            "errors": [
                {
                    "entry": "report",
                    "file": "reports/demo/report.yaml",
                    "path": "/kpis/0",
                    "message": "falta value",
                    "fix": "agrega value",
                }
            ],
        },
        working_state={
            "inspected": inspected,
            "decisions": [f"decision {i}" for i in range(30)],
            "done": [f"done {i}" for i in range(30)],
            "recent_files": recent_files,
        },
        tokens_used=1000,
    )
    text = service.state_text(sess, get_settings(), ["hola"])
    assert len(text) <= service.STATE_MAX_CHARS + len(service._STATE_HEADER)
    assert "Archivos:" in text
    for path in draft_files:
        assert f"- {path} (" in text
    assert "Problemas de validación (1):" in text
    assert "falta value" in text
    assert "public.t03" in text and "col59 text" in text
    assert "public.t07" in text
    assert "public.t39 (60 columnas)" in text
    assert "public.t00" not in text
    assert "… y " in text
    assert "decision 0" not in text
    assert "decision 29" in text


def test_state_suffix_hard_cap_drops_recent_files_first(superuser, db):
    personal_big = {
        "origen": {
            f"columna_muy_larga_numero_{i}": "text" for i in range(400)
        }
    }
    draft_files = {"integrations/demo/queries/a.sql": "SELECT col1 FROM public.t1"}
    sess = _stored_session(
        db,
        superuser,
        status="open",
        draft={"summary": "resumen", "files": draft_files},
        working_state={
            "personal": personal_big,
            "recent_files": [["integrations/demo/queries/a.sql"]],
            "inspected": {"origen": {"public.t1": "id integer"}},
        },
        tokens_used=10,
    )
    text = service.state_text(sess, get_settings(), ["hola"])
    assert "(estado recortado; usa read_draft o describe_source)" in text
    assert "Archivos recientes" not in text
    assert "Archivos:" in text
    assert "- integrations/demo/queries/a.sql (" in text
    assert "Fuentes consultadas:" in text


def test_query_tables_basic():
    from app.assistant.personal import query_tables

    assert query_tables("WITH x AS (SELECT * FROM a.b) SELECT * FROM x JOIN c ON true") == {
        "a.b",
        "c",
    }
    assert query_tables("SELEC broken") == set()


def test_state_suffix_hard_cap_with_many_unbounded_blocks(superuser, db):
    draft = {
        "summary": "s" * 2000,
        "files": {
            f"integrations/demo/queries/consulta_{i:02d}.sql": "SELECT 1"
            for i in range(40)
        },
    }
    validation = {
        "valid": False,
        "errors": [
            {
                "file": f"integrations/demo/queries/consulta_{i:02d}.sql",
                "message": "m" * 400,
                "fix": "f" * 100,
            }
            for i in range(40)
        ],
    }
    working_state = {
        "personal": {
            f"fuente{s}": {f"columna_{s}_{c}": "email" for c in range(30)}
            for s in range(10)
        },
        "personal_confirmed": [f"columna_0_{c}" for c in range(30)],
        "goal": "g" * 2000,
        "step": "p" * 2000,
        "next": "n" * 2000,
        "progress": "r" * 2000,
        "decisions": ["d" * 300 for _ in range(10)],
        "edit_integrations": [f"integ_{i}" for i in range(200)],
        "recent_files": [["integrations/demo/queries/consulta_00.sql"]],
    }
    preview = {
        "status": "failed",
        "integrations": {
            f"integ_{i}": {"status": "failed", "message": "e" * 200}
            for i in range(30)
        },
    }
    sess = _stored_session(
        db,
        superuser,
        draft=draft,
        validation=validation,
        working_state=working_state,
        preview=preview,
        tokens_used=1000,
    )
    text = service.state_text(sess, get_settings(), ["hola"])
    assert len(text) <= service.STATE_MAX_CHARS + len(service._STATE_HEADER)
    assert service.TRUNCATED_MARKER in text
    assert "Archivos:" in text
    assert "Problemas de validación (40):" in text
    assert "Tokens usados:" in text
    assert "300 columnas marcadas en 10 fuentes" in text


def test_cacheable_prefix_between_rounds(superuser, db):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    fake.SHARED.queue(
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, call_id="c1")],
                    stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call("update_notes", {"next": "describir la tabla"},
                                           call_id="c2")],
                    stop_reason="tool_use"),
        _chat_reply("Listo."),
    )
    _send(client, sid, "propón")

    reqs = fake.SHARED.requests
    assert len(reqs) == 3
    for req in reqs:
        assert req["system"] == service.system_prefix("es")

    for prev, nxt in ((reqs[0], reqs[1]), (reqs[1], reqs[2])):
        k = -1
        for i, m in enumerate(prev["messages"]):
            if m["role"] == "assistant" and m.get("tool_calls"):
                k = i
        stable = prev["messages"][:k] if k >= 0 else prev["messages"]
        assert stable
        assert json.dumps(stable, ensure_ascii=False, sort_keys=True) == \
            json.dumps(nxt["messages"][:len(stable)], ensure_ascii=False, sort_keys=True)
        assert len(nxt["messages"]) > len(prev["messages"])

    for req in reqs:
        context = req["context"]
        assert isinstance(context, str) and context.startswith("## Estado")
        assert all(context not in m["content"] for m in req["messages"])

    assert "describir la tabla" in reqs[2]["context"]
    assert "describir la tabla" not in reqs[0]["context"]

    payload = fake.SHARED.payloads()[2]
    escaped = json.dumps(reqs[2]["context"], ensure_ascii=False)[1:-1]
    assert escaped in payload


def test_english_user_gets_english_prompt(superuser, db):
    sql("UPDATE app_user SET locale = 'en' WHERE email = 'root@example.com'")
    client = signed_in("root@example.com")
    fake.SHARED.queue(_chat_reply("Hello."))
    sid = _new_session(client)
    _send(client, sid, "hello")
    assert len(fake.SHARED.requests) == 1
    assert fake.SHARED.requests[0]["system"] == service.system_prefix("en")
    assert service.SYSTEM_PREFIX_EN != service.SYSTEM_PREFIX
    assert "respond always in English" in " ".join(service.SYSTEM_PREFIX_EN.split())
