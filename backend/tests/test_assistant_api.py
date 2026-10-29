"""Feature 014: assistant API with the fake provider (never a live AI)."""
import json
import textwrap

import psycopg
import pytest
from sqlalchemy import select

from app.ai import ChatReply, ChatUsage, ToolCall, fake
from app.assistant import service
from app.assistant.preview import ai_error_text, outcome_lines, redact_values
from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import extract
from app.i18n import t
from app.models import AppUser, AssistantMessage, AssistantSession
from app.sources import service as sources
from app.sources.service import by_name, secrets_of
from tests.conftest import (
    TEST_SCHEMA,
    chat_project_id,
    chat_response,
    new_chat,
    signed_in,
    sql,
    v2_files,
)
from tests.test_assistant_preview import _draft
from tests.test_runner import ORIGIN
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import apply, lock
from tests.test_vibe_reporting import workspace as workspace  # fixture
from tests.workspace_fixture import REPORT


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


def _chat_reply(text="", tool_calls=(), stop_reason="end"):
    return ChatReply(
        text=text,
        tool_calls=tuple(tool_calls),
        usage=ChatUsage(input=10, output=5),
        model="fake",
        stop_reason=stop_reason,
    )


def _tool_call(name, args, call_id="call-1"):
    return ToolCall(id=call_id, name=name, args=args)


def _valid_draft_files():
    report_text = textwrap.dedent(REPORT.format(title="Ventas 2")).lstrip()
    report_text = report_text.replace("id: ventas\n", "id: ventas2\n")
    report_text = report_text.replace(
        "spec: specs/reports/001-ventas\n", "spec: specs/reports/002-ventas2\n"
    )
    return {
        "reports/ventas2/report.yaml": report_text,
        "specs/reports/002-ventas2/spec.md": (
            "# Ventas 2\n\n**Spec type**: report\n\n**Status**: Implemented\n"
        ),
        "specs/reports/002-ventas2/plan.md": "# Plan\n",
        "specs/reports/002-ventas2/tasks.md": "- [X] T001 hecho\n",
    }


def test_admin_gets_403(admin):
    client = signed_in("admin@example.com")
    resp = client.get("/api/assistant/sessions")
    assert resp.status_code == 403


def test_ai_not_configured(monkeypatch, superuser):
    monkeypatch.setenv("AI_PROVIDER", "none")
    get_settings.cache_clear()
    client = signed_in("root@example.com")
    resp = chat_response(client, "x")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ai_not_configured"


def test_create_session_and_tool_flow(superuser, db):
    client = signed_in("root@example.com")
    fake.SHARED.queue(
        _chat_reply(tool_calls=[_tool_call("list_sources", {})], stop_reason="tool_use"),
        _chat_reply(text="Hecho"),
    )
    resp = chat_response(client, "Mi sesión")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Mi sesión"
    assert data["status"] == "open"
    session_id = data["id"]

    resp = client.post(f"/api/assistant/sessions/{session_id}/messages", json={"text": "hola"})
    assert resp.status_code == 202
    messages = resp.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "assistant"]
    tool_msg = messages[2]
    assert tool_msg["tool_name"] == "list_sources"
    assert tool_msg["content"] == "Consultó la lista de fuentes."

    session = db.get(AssistantSession, session_id)
    assert session.tokens_used > 0
    stored = db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session_id)
        .order_by(AssistantMessage.id)
    ).all()
    assert [m.role for m in stored] == ["user", "assistant", "tool", "assistant"]
    assert stored[0].content == "hola"
    assert stored[1].tool_payload["calls"][0]["name"] == "list_sources"
    assert stored[2].tool_name == "list_sources"
    assert stored[2].tool_payload["call_id"] == "call-1"
    assert "result" in stored[2].tool_payload
    assert stored[3].content == "Hecho"


def test_propose_draft_and_session_shows_draft(superuser, db, workspace, without_command_guard):
    lock(workspace)
    apply(signed_in("root@example.com"))

    files = v2_files(_valid_draft_files())
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[_tool_call("propose_draft",
                                   {"files": files, "summary": "Ventas por producto 2"})],
            stop_reason="tool_use",
        ),
        _chat_reply(text="Listo"),
    )
    client = signed_in("root@example.com")
    resp = chat_response(client, "Draft")
    session_id = resp.json()["id"]
    resp = client.post(f"/api/assistant/sessions/{session_id}/messages", json={"text": "propón"})
    assert resp.status_code == 202
    session_data = resp.json()["session"]
    assert session_data["draft"] is not None
    assert "specs/001-ventas2/spec.md" in session_data["draft"]["files"]
    assert session_data["validation"]["valid"] is True


def test_tokens_never_stop_a_turn(superuser, db):
    """Feature 028 revision (owner, 2026-10-21: "make the ai unlimited"): no budget, no stop."""
    client = signed_in("root@example.com")
    session_id = chat_response(client).json()["id"]
    sql("UPDATE assistant_session SET tokens_used = 50000000 WHERE id = :id", id=session_id)
    fake.SHARED.reset()
    fake.SHARED.queue(_chat_reply("Hola."))

    resp = client.post(f"/api/assistant/sessions/{session_id}/messages", json={"text": "hola"})
    assert resp.status_code == 202
    msgs = resp.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[-1]["content"] == "Hola."
    assert len(fake.SHARED.payloads()) == 1
    assert "presupuesto" not in msgs[-1]["content"].lower()
    assert sql("SELECT count(*) FROM audit_event "
               "WHERE kind = 'assistant_budget_extended'") == [(0,)]


def test_max_rounds_stop(superuser, db, monkeypatch):
    monkeypatch.setenv("AI_CHAT_MAX_ROUNDS", "3")
    get_settings.cache_clear()
    client = signed_in("root@example.com")
    for i in range(3):
        fake.SHARED.queue(
            _chat_reply(
                tool_calls=[_tool_call("list_sources", {}, call_id=f"call-{i}")],
                stop_reason="tool_use",
            )
        )
    fake.SHARED.queue(_chat_reply("Hecho: x. Siguiente: y."))
    resp = chat_response(client)
    session_id = resp.json()["id"]
    resp = client.post(f"/api/assistant/sessions/{session_id}/messages", json={"text": "hola"})
    assert resp.status_code == 202
    messages = resp.json()["messages"]
    assert messages[-1]["role"] == "assistant"
    assert "Detuve la conversación" not in messages[-1]["content"]
    stops = [
        m for m in messages
        if m["role"] == "assistant" and "Hecho: x. Siguiente: y." in m["content"]
    ]
    assert len(stops) == 1


def test_archived_session_conflict(superuser, db):
    client = signed_in("root@example.com")
    resp = chat_response(client)
    session_id = resp.json()["id"]
    resp = client.post(f"/api/assistant/sessions/{session_id}/archive")
    assert resp.status_code == 200
    resp = client.post(f"/api/assistant/sessions/{session_id}/messages", json={"text": "hola"})
    assert resp.status_code == 409


def _stored_session(db, superuser, **fields) -> AssistantSession:
    s = AssistantSession(title="t", created_by=superuser.id,
                         project_id=chat_project_id(db, superuser.id), **fields)
    db.add(s)
    db.commit()
    return s


def test_applied_session_accepts_new_request(superuser, db, workspace):
    """US3/AC3 (020): a new request in an applied conversation reopens it; the project keeps
    its files and its preview."""
    lock(workspace)
    apply(signed_in("root@example.com"))
    version_id = sql("SELECT id FROM workspace_version WHERE state = 'active'")[0][0]
    s = _stored_session(db, superuser, status="applied", applied_version_id=version_id,
                        draft={"files": {}, "summary": "x"}, preview={"status": "succeeded"})
    fake.SHARED.queue(_chat_reply("Hola"))
    resp = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/messages",
                                               json={"text": "otro reporte"})
    assert resp.status_code == 202, resp.text
    body = resp.json()["session"]
    assert (body["status"], body["preview"]) == ("open", None)
    assert "project.yaml" in body["draft"]["files"]
    assert body["applied_version_id"] == version_id


def test_archived_session_message_conflict_text(superuser, db):
    s = _stored_session(db, superuser, status="archived")
    resp = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/messages",
                                               json={"text": "hola"})
    assert resp.status_code == 409
    assert "archivada" in resp.json()["error"]["message"]


def test_preview_outcome_redacts_values():
    lines = outcome_lines({"status": "failed", "integrations": {"x": {
        "status": "failed", "message": 'invalid input syntax for type integer: "ZETA-4242"',
        "datasets": {}, "checks": [{"dataset": "d", "type": "reconcile", "ok": False,
                                    "detail": "ZETA-4242 10.5"}]}}})
    text = "\n".join(lines)
    assert "ZETA-4242" not in text
    assert "comprobación reconcile no superada en d" in text
    assert "A1" not in redact_values("Key (doc)=(A1) already exists")
    assert outcome_lines(None) == [] and outcome_lines({"status": "pending"}) == []


def test_preview_outcome_names_the_structured_check_reason():
    lines = outcome_lines({"status": "failed", "integrations": {"x": {
        "status": "failed", "message": None, "datasets": {},
        "checks": [{"dataset": "altcoin_season", "type": "contract", "ok": False,
                    "detail": "snapshot_at: 3 valores vacíos", "key": "run.check.nulls",
                    "params": {"column": "snapshot_at", "n": 3}}]}}})
    text = "\n".join(lines)
    # C10: without the structured reason the agent iterated blind on the failing dataset.
    assert "comprobación contract no superada en altcoin_season" in text
    assert "snapshot_at" in text and "3" in text


def test_history_skips_preview_notices(superuser, db):
    s = _stored_session(db, superuser, status="open")
    db.add(AssistantMessage(session_id=s.id, role="user", content="hola"))
    db.add(AssistantMessage(session_id=s.id, role="tool", tool_name="preview",
                            content="Vista previa lista.",
                            tool_payload={"result": {"lines": []}}))
    db.commit()
    history = service._load_history(db, s.id)
    assert [m.role for m in history] == ["user"]


def test_preview_outcome_reaches_the_ai(superuser, db):
    """US2/AC3: the preview error goes to the provider redacted, never the raw value."""
    s = _stored_session(db, superuser, status="open")
    sql("UPDATE project SET preview = CAST(:p AS jsonb) WHERE id = :i", i=s.project_id,
        p=json.dumps({"status": "failed", "integrations": {"x": {
            "status": "failed", "message": "Key (doc)=(SECRETO-77) already exists",
            "datasets": {}, "checks": []}}}))     # 020: the preview lives on the project
    fake.SHARED.queue(_chat_reply("Lo corrijo"))
    resp = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/messages",
                                               json={"text": "¿qué pasó?"})
    assert resp.status_code == 202, resp.text
    payload = fake.SHARED.payloads()[-1]
    assert "Vista previa: failed" in payload
    assert "SECRETO-77" not in payload


def test_title_from_first_message():
    assert service.title_from("  Ventas por marca\nmás detalles") == "Ventas por marca"
    long = "Quiero un reporte de ventas netas por marca y vendedor actualizado cada media hora"
    title = service.title_from(long)
    assert title.endswith("…") and len(title) <= service.TITLE_LENGTH + 1
    assert long.startswith(title[:-1])
    assert service.title_from("   ") == service.DEFAULT_TITLE


def test_first_message_names_the_conversation(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    fake.SHARED.queue(_chat_reply("Claro"), _chat_reply("Listo"))
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Ventas por marca"})
    assert r.json()["session"]["title"] == "Ventas por marca"
    client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Otra cosa"})
    assert client.get(f"/api/assistant/sessions/{sid}").json()["title"] == "Ventas por marca"


def test_old_default_titles_show_the_first_message(superuser, db):
    # created before automatic naming
    s = AssistantSession(title=service.DEFAULT_TITLE, created_by=superuser.id,
                         project_id=chat_project_id(db, superuser.id))
    db.add(s)
    db.commit()
    db.add(AssistantMessage(session_id=s.id, role="user", content="Inventario por bodega"))
    db.commit()
    items = signed_in("root@example.com").get("/api/assistant/sessions").json()["sessions"]
    assert [i["title"] for i in items if i["id"] == s.id] == ["Inventario por bodega"]


def test_empty_answer_is_never_silent(superuser, db):
    s = _stored_session(db, superuser, status="open")
    fake.SHARED.queue(_chat_reply(""))
    r = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/messages",
                                           json={"text": "hola"})
    assert r.json()["messages"][-1]["content"] == t(service._EMPTY_TEXT)


def test_cut_answer_says_so(superuser, db):
    s = _stored_session(db, superuser, status="open")
    fake.SHARED.queue(_chat_reply("Aquí va el borrador...", stop_reason="max_tokens"))
    r = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/messages",
                                           json={"text": "hazlo"})
    last = r.json()["messages"][-1]["content"]
    assert last.startswith("Aquí va el borrador...") and "se cortó" in last
    assert fake.SHARED.requests[-1]["max_tokens"] == get_settings().ai_chat_max_tokens


def test_compact_tables_and_old_results_not_resent(superuser, db):
    from app.assistant.tools import compact_tables
    out = compact_tables({"kind": "supabase", "tables": [{"name": "invoice", "primary_key": ["id"],
        "columns": [{"name": "id", "type": "bigint", "nullable": False},
                    {"name": "monto", "type": "numeric", "nullable": True}]}]})
    assert out["tables"][0]["columns"] == ["id bigint", "monto numeric?"]

    s = _stored_session(db, superuser, status="open")
    big = {"tables": ["x" * 50 for _ in range(200)]}
    for m in (AssistantMessage(session_id=s.id, role="user", content="primero"),
              AssistantMessage(session_id=s.id, role="assistant", content="",
                               tool_payload={"calls": [{"id": "c1", "name": "describe_source",
                                                         "args": {"name": "A"}}]}),
              AssistantMessage(session_id=s.id, role="tool", tool_name="describe_source",
                               content="ok", tool_payload={"call_id": "c1", "result": big}),
              AssistantMessage(session_id=s.id, role="assistant", content="",
                               tool_payload={"calls": [{"id": "c2", "name": "list_sources",
                                                         "args": {}}]}),
              AssistantMessage(session_id=s.id, role="tool", tool_name="list_sources",
                               content="Consultó la lista de fuentes.",
                               tool_payload={"call_id": "c2", "result": {"sources": []}}),
              AssistantMessage(session_id=s.id, role="assistant", content="listo"),
              AssistantMessage(session_id=s.id, role="user", content="segundo")):
        db.add(m)
        db.commit()
    history = service._load_history(db, s.id)
    c1_tool = next(m for m in history if m.role == "tool" and m.tool_call_id == "c1")
    c2_tool = next(m for m in history if m.role == "tool" and m.tool_call_id == "c2")
    assert c1_tool.content == "ok"
    body = c2_tool.content.split("\n", 1)[1].rsplit("\n</datos>", 1)[0]   # 021 data block
    assert c2_tool.content.startswith('<datos origen="herramienta:list_sources"')
    assert list(json.loads(body).keys()) == ["sources"]


def test_audit_ids_go_in_detail_not_user_target(superuser, db):
    """audit_event.target_id references users: a session id that is no user id must not break."""
    sql("SELECT setval(pg_get_serial_sequence('assistant_session', 'id'), 900000)")
    s = AssistantSession(title="t", created_by=superuser.id,
                         project_id=chat_project_id(db, superuser.id))
    db.add(s)
    db.commit()
    resp = signed_in("root@example.com").post(f"/api/assistant/sessions/{s.id}/archive")
    assert resp.status_code == 200, resp.text
    assert sql("SELECT target_id, detail->>'session' FROM audit_event "
               "WHERE kind = 'assistant_session_archived'") == [(None, str(s.id))]


def test_payload_audit_no_secrets_or_rows(superuser, db, workspace, monkeypatch,
                                          without_command_guard):
    """SC-002 (014, extended in 017 with profile_source and check_query): no row value,
    password or connection detail ever reaches the provider."""
    lock(workspace)
    apply(signed_in("root@example.com"))
    sql("INSERT INTO origin_sales VALUES "
        "('ZETA-UNICO-4242', 9, 'zeta-tipo', now(), 98765.4321, 'ZETA-PROD-4242')")
    src = by_name(db, "Origen prueba")
    forbidden = [
        "ZETA-UNICO-4242", "ZETA-PROD-4242", "zeta-tipo", "98765",
        secrets_of(src)["password"], src.settings["host"], src.settings["username"],
        "zeta-db.interno", "10.11.12.13", "6543", "zeta_usuario",
        "zeta_base", "zeta-clave-4242",
    ]
    with get_sessionmaker().begin() as s:
        sources.create(
            s,
            s.get(AppUser, superuser.id),
            {
                "name": "Origen caido",
                "kind": "postgresql",
                "settings": {
                    "host": "zeta-db.interno",
                    "port": 6543,
                    "database": "zeta_base",
                    "username": "zeta_usuario",
                    "sslmode": "prefer",
                    "timeout_seconds": 15,
                },
                "secrets": {"password": "zeta-clave-4242"},
            },
            get_settings(),
            None,
        )
    real_pg_connect = extract._pg_connect

    def fake_pg_connect(*args, **kwargs):
        settings = args[0]
        if settings.get("host") == "zeta-db.interno":
            raise psycopg.OperationalError(
                'connection failed: connection to server at "zeta-db.interno" '
                "(10.11.12.13), port 6543 failed: FATAL:  password authentication "
                'failed for user "zeta_usuario"'
            )
        return real_pg_connect(*args, **kwargs)

    monkeypatch.setattr(extract, "_pg_connect", fake_pg_connect)
    files = v2_files(_valid_draft_files())
    failing = {p: t for p, t in _draft().items()
               if not p.startswith(("reports/", "specs/reports/"))}
    integration_yaml = failing["integrations/ventas-dos/integration.yaml"]
    assert "source: Origen prueba" in integration_yaml
    failing["integrations/ventas-dos/integration.yaml"] = integration_yaml.replace(
        "source: Origen prueba", "source: Origen caido"
    )
    failing = v2_files(failing, first=2)
    calls = [
        _tool_call("list_sources", {}, call_id="c1"),
        _tool_call("describe_source", {"name": "Origen prueba"}, call_id="c2"),
        _tool_call("profile_source",
                   {"name": "Origen prueba",
                    "table": f"{TEST_SCHEMA}.origin_sales"},
                   call_id="c5"),
        _tool_call("check_query",
                   {"source": "Origen prueba",
                    "sql": f"SELECT doc, kind, amount FROM {ORIGIN} "
                           "WHERE completed_at >= :window_start "
                           "AND completed_at < :window_end"},
                   call_id="c6"),
        _tool_call("get_workspace", {}, call_id="c3"),
        _tool_call("propose_draft",
                   {"files": files, "summary": "Ventas por producto 2"},
                   call_id="c4"),
        _tool_call("propose_draft",
                   {"files": failing, "summary": "Fuente caída"},
                   call_id="c7"),
        _tool_call("run_preview", {}, call_id="c8"),
    ]
    fake.SHARED.queue(
        *[_chat_reply(tool_calls=[c], stop_reason="tool_use") for c in calls],
        _chat_reply(text="Hecho"),
    )
    client = signed_in("root@example.com")
    resp = chat_response(client)
    session_id = resp.json()["id"]
    # mode `edit`: `run_preview`/`apply_draft` are refused in Auto without a run contract, and this
    # test is about the data boundary, not about modes (feature 028 FR-000).
    assert client.post(f"/api/assistant/sessions/{session_id}/mode",
                       json={"mode": "edit"}).status_code == 200
    resp = client.post(f"/api/assistant/sessions/{session_id}/messages",
                       json={"text": "audita"})
    assert resp.status_code == 202
    payloads = fake.SHARED.payloads()
    assert len(payloads) == 9
    for payload in payloads:
        for item in forbidden:
            assert item not in payload, f"forbidden value {item!r} leaked into payload"
    assert "No se pudo conectar con la fuente." in payloads[-1]
    tool_payload = sql(
        "SELECT tool_payload::text FROM assistant_message "
        "WHERE session_id = :s AND tool_name = 'run_preview'",
        s=session_id,
    )[0][0]
    assert "No se pudo conectar con la fuente." in tool_payload
    for item in forbidden:
        assert item not in tool_payload, f"forbidden value {item!r} leaked into tool_payload"
    preview_status = sql(
        "SELECT p.preview->>'status' FROM project p JOIN assistant_session s "
        "ON s.project_id = p.id WHERE s.id = :s",
        s=session_id,
    )[0][0]
    assert preview_status == "failed"


@pytest.mark.parametrize(
    "text_input",
    [
        'connection to server at "zeta-db.interno" (10.11.12.13), port 6543 failed',
        "could not translate host name zeta-db.interno to address: "
        "Name or service not known",
        "host=zeta-db.interno port=6543 dbname=zeta_base user=zeta_usuario",
        "postgresql://zeta_usuario:clave@zeta-db.interno:6543/zeta_base",
        "connect to [2001:db8::5]:6543 failed",
        "zeta_usuario@zeta-db.interno",
        "zeta-db.interno:6543, retry",
    ],
)
def test_redact_values_strips_connection_details(text_input):
    forbiddens = [
        "zeta-db.interno", "10.11.12.13", "6543", "zeta_usuario",
        "zeta_base", "2001:db8::5", "clave",
    ]
    redacted = redact_values(text_input)
    for item in forbiddens:
        assert item not in redacted, f"{item!r} leaked from {text_input!r}"


def test_ai_error_text_maps_connection_failures():
    operational = ('OperationalError: connection failed: connection to server at '
                   '"zeta-db.interno" failed')
    assert ai_error_text(operational) == "No se pudo conectar con la fuente."
    preview = {
        "status": "failed",
        "integrations": {
            "x": {
                "status": "failed",
                "message": operational,
                "datasets": {},
                "checks": [],
            }
        },
    }
    lines = outcome_lines(preview)
    joined = " ".join(lines)
    assert "No se pudo conectar con la fuente." in joined
    assert "zeta" not in joined
    sql_error = "UndefinedColumn: column no_existe does not exist"
    assert ai_error_text(sql_error) != "No se pudo conectar con la fuente."
    assert redact_values("relation ventas.sale_lines does not exist") == \
           "relation ventas.sale_lines does not exist"


def test_rename_session_trims_and_lists(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    before = client.get(f"/api/assistant/sessions/{sid}").json()["updated_at"]
    r = client.patch(f"/api/assistant/sessions/{sid}", json={"title": "  Ventas por marca  "})
    assert r.status_code == 200
    assert r.json()["title"] == "Ventas por marca"
    assert r.json()["updated_at"] == before
    listed = client.get("/api/assistant/sessions").json()["sessions"]
    row = next(s for s in listed if s["id"] == sid)
    assert row["title"] == "Ventas por marca"
    long_title = "x" * 120
    r = client.patch(f"/api/assistant/sessions/{sid}", json={"title": long_title})
    assert r.status_code == 200
    assert r.json()["title"] == long_title


@pytest.mark.parametrize("body", [
    {"title": ""},
    {"title": "   "},
    {"title": "x" * 121},
])
def test_rename_session_rejects_bad_titles(superuser, db, body):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    r = client.patch(f"/api/assistant/sessions/{sid}", json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert r.json()["error"]["message"] == "El nombre debe tener entre 1 y 120 caracteres."
    assert client.get(f"/api/assistant/sessions/{sid}").json()["title"] == service.DEFAULT_TITLE


def test_rename_session_extra_and_empty_body(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    r = client.patch(f"/api/assistant/sessions/{sid}", json={"title": "a", "color": "rojo"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert client.get(f"/api/assistant/sessions/{sid}").json()["title"] == service.DEFAULT_TITLE
    r = client.patch(f"/api/assistant/sessions/{sid}", json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert client.get(f"/api/assistant/sessions/{sid}").json()["title"] == service.DEFAULT_TITLE


def test_rename_session_permissions(superuser, db, admin):
    root = signed_in("root@example.com")
    sid = new_chat(root)
    admin_client = signed_in("admin@example.com")
    r = admin_client.patch(f"/api/assistant/sessions/{sid}", json={"title": "No"})
    assert r.status_code == 403

    other = AssistantSession(
        title="Ajena", created_by=admin.id, project_id=chat_project_id(db, admin.id), status="open",
    )
    db.add(other)
    db.commit()
    r = root.patch(f"/api/assistant/sessions/{other.id}", json={"title": "No"})
    assert r.status_code == 404
    db.refresh(other)
    assert other.title == "Ajena"
    r = root.patch(f"/api/assistant/sessions/{sid}", json={"title": "No"},
                   headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"


def test_rename_session_while_busy(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    sql("UPDATE assistant_session SET busy_since = now() WHERE id = :i", i=sid)
    assert client.get(f"/api/assistant/sessions/{sid}").json()["busy"] is True
    r = client.patch(f"/api/assistant/sessions/{sid}", json={"title": "Nombre nuevo"})
    assert r.status_code == 200
    assert r.json()["title"] == "Nombre nuevo"
    assert r.json()["busy"] is True
