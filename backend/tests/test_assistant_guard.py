"""Guards del bucle de asistente: memo por ejecución, límite de descubrimiento y timeouts."""

from __future__ import annotations

import textwrap

import pytest

from app.ai import AIError, fake
from app.assistant import origin, service, tools
from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import extract
from app.i18n import t
from app.models import AppUser, AssistantSession
from app.sources import service as sources
from tests.conftest import (
    new_chat,
    project_view,
    signed_in,
    sql,
    v2_files,
    write_project,
)
from tests.test_assistant_api import (
    _chat_reply,
    _stored_session,
    _tool_call,
    _valid_draft_files,
)

# 017 run mechanics (memo, discovery limit, timeouts) through plain-mode tools; the 021 command
# guard has its own tests.
pytestmark = pytest.mark.usefixtures("without_command_guard")


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def api_source(superuser):
    with get_sessionmaker().begin() as s:
        sources.create(
            s,
            s.get(AppUser, superuser.id),
            {
                "name": "Origen API",
                "kind": "supabase",
                "settings": {"url": "https://203.0.113.9"},
                "secrets": {"service_key": "clave-de-prueba"},
            },
            get_settings(),
            None,
        )
    yield


@pytest.fixture()
def describe_calls(monkeypatch):
    calls: list[str | None] = []

    def fake_describe(kind, settings, secrets, app, path=None):
        calls.append(path)
        if path:
            return {
                "kind": kind,
                "path": "/" + path,
                "shape": {"id": "integer", "total": "number"},
            }
        return {
            "kind": kind,
            "tables": [
                {
                    "name": "facturas",
                    "primary_key": ["id"],
                    "columns": [
                        {"name": "id", "type": "bigint", "nullable": False},
                        {"name": "total", "type": "numeric", "nullable": True},
                    ],
                }
            ],
            "truncated": False,
        }

    monkeypatch.setattr(tools, "describe", fake_describe)
    return calls


@pytest.fixture()
def supabase_calls(monkeypatch):
    calls: list[str] = []

    def fake_supabase_once(settings, secrets, app, request, params, **kwargs):
        calls.append(request["path"])
        if kwargs.get("extra_headers", {}).get("Prefer") == "count=exact":
            return [], {"content-range": "*/42"}
        return [{"id": 1, "total": 2.5}], {}

    monkeypatch.setattr(extract, "supabase_once", fake_supabase_once)
    return calls


def _post_message(client, sid, text):
    return client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": text})


def _new_session(client):
    return new_chat(client)


def _tool_results(sid):
    rows = sql(
        "SELECT tool_payload FROM assistant_message "
        "WHERE session_id = :i AND role = 'tool' ORDER BY id",
        i=sid,
    )
    return [r[0]["result"] for r in rows]


def _last_assistant(sid):
    rows = sql(
        "SELECT content FROM assistant_message "
        "WHERE session_id = :i AND role = 'assistant' ORDER BY id DESC LIMIT 1",
        i=sid,
    )
    return rows[0][0]


def test_normalise_target_and_normalise_table():
    assert origin.normalise_table("supabase", " /public.facturas") == "facturas"
    assert origin.normalise_table("supabase", "facturas") == "facturas"
    assert origin.normalise_table("supabase", "public.FACTURAS") == "FACTURAS"
    assert origin.normalise_table("postgresql", "public.facturas") == "public.facturas"
    assert tools.normalise_target(
        "describe_source", {"name": " Origen API ", "path": "/public.Facturas"}, "supabase"
    ) == "origen api|facturas"
    assert tools.normalise_target(
        "describe_source", {"name": " Origen API ", "path": "facturas"}, "supabase"
    ) == "origen api|facturas"
    assert tools.normalise_target(
        "describe_source", {"name": " Origen API ", "path": "public.facturas"}, "supabase"
    ) == "origen api|facturas"
    assert tools.normalise_target(
        "describe_source", {"name": "Origen API", "path": "public.facturas"}, "postgresql"
    ) == "origen api|public.facturas"
    assert tools.normalise_target("get_authoring_guide", {"topic": None}) == "index"
    assert tools.normalise_target("get_authoring_guide", {"topic": "example-supabase"}) == (
        "example-supabase"
    )
    assert tools.normalise_target(
        "check_query", {"source": "Origen API", "sql": "SELECT  1\n FROM x"}, "supabase"
    ) == tools.normalise_target(
        "check_query", {"source": "Origen API", "sql": "SELECT 1 FROM x"}, "supabase"
    )
    assert tools.normalise_target("propose_draft", {"files": {}}) is None


def test_is_discovery_rule():
    assert tools.is_discovery("list_sources", {})
    assert tools.is_discovery("describe_source", {"name": "x"})
    assert tools.is_discovery("get_authoring_guide", {"topic": "x"})
    assert tools.is_discovery("check_query", {"source": "x", "sql": "SELECT 1"})
    assert not tools.is_discovery("check_query", {"source": "x", "path": "a.yaml"})
    assert not tools.is_discovery("propose_draft", {})


def test_describe_repeat_memo_and_audit_once(superuser, db, api_source, describe_calls):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    fake.SHARED.queue(
        _chat_reply(
            tool_calls=[
                _tool_call("describe_source", {"name": "Origen API", "path": "facturas"},
                           "c1"),
            ],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[
                _tool_call("describe_source", {"name": "origen api", "path": "/facturas"},
                           "c2"),
            ],
            stop_reason="tool_use",
        ),
        _chat_reply(
            tool_calls=[
                _tool_call("describe_source", {"name": "Origen API", "path": "public.facturas"},
                           "c3"),
            ],
            stop_reason="tool_use",
        ),
        _chat_reply("Listo."),
    )
    r = _post_message(client, sid, "explora facturas")
    assert r.status_code == 202

    results = _tool_results(sid)
    assert len(results) == 3
    assert describe_calls == ["facturas"]
    assert "ya_consultado" not in results[0]
    assert results[1]["ya_consultado"] is True
    assert results[1]["note"] == tools.REPEAT_NOTE
    assert results[2]["ya_consultado"] is True
    assert results[2]["note"] == tools.REPEAT_NOTE
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'source_described'")[0][0] == 1


def test_refresh_honoured_once_per_run(superuser, db, api_source, describe_calls):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    fake.SHARED.queue(
        _chat_reply(tool_calls=[_tool_call("describe_source", {"name": "Origen API"},
                                           "c1")], stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call("describe_source", {"name": "Origen API",
                                                               "refresh": True}, "c2")],
                    stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call("describe_source", {"name": "Origen API",
                                                               "refresh": True}, "c3")],
                    stop_reason="tool_use"),
        _chat_reply("Listo."),
    )
    r = _post_message(client, sid, "explora")
    assert r.status_code == 202

    assert describe_calls == [None, None]
    results = _tool_results(sid)
    assert "ya_consultado" not in results[0]
    assert "ya_consultado" not in results[1]
    assert results[2]["ya_consultado"] is True
    assert results[2]["note"] == tools.REPEAT_NOTE


def test_memo_cleared_per_run(superuser, db, api_source, describe_calls):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    fake.SHARED.queue(
        _chat_reply(tool_calls=[_tool_call("describe_source", {"name": "Origen API"},
                                           "c1")], stop_reason="tool_use"),
        _chat_reply("Hecho."),
        _chat_reply(tool_calls=[_tool_call("describe_source", {"name": "Origen API"},
                                           "c2")], stop_reason="tool_use"),
        _chat_reply("Listo."),
    )
    r = _post_message(client, sid, "explora")
    assert r.status_code == 202
    r = _post_message(client, sid, "otra vez")
    assert r.status_code == 202

    results = _tool_results(sid)
    assert len(results) == 2
    assert "ya_consultado" not in results[1]
    assert results[1].get("cached") is True
    assert describe_calls == [None]


def test_discovery_limit_restricts_then_returns_after_draft(
    superuser, db, api_source, monkeypatch
):
    monkeypatch.setenv("AI_AGENT_DISCOVERY_LIMIT", "3")
    get_settings.cache_clear()
    client = signed_in("root@example.com")
    sid = _new_session(client)
    fake.SHARED.queue(
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, "c1")], stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, "c2")], stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, "c3")], stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call("get_workspace", {}, "c4")],
                    stop_reason="tool_use"),
        _chat_reply(
            tool_calls=[
                _tool_call("propose_draft", {"files": v2_files(_valid_draft_files()),
                                             "summary": "Ventas 2"}, "c5")
            ],
            stop_reason="tool_use",
        ),
        _chat_reply("Listo."),
    )
    r = _post_message(client, sid, "hazlo")
    assert r.status_code == 202

    reqs = fake.SHARED.requests
    assert len(reqs) == 6
    for req in reqs[:3]:
        names = [t["name"] for t in req["tools"]]
        assert "describe_source" in names
        assert tools.DISCOVERY_DONE_TEXT not in req["context"]
    restricted = {*tools.DRAFT_TOOLS, "get_app_guide"}     # 023: the guide stays offered
    assert {t["name"] for t in reqs[3]["tools"]} == restricted
    assert tools.DISCOVERY_DONE_TEXT in reqs[3]["context"]
    assert {t["name"] for t in reqs[4]["tools"]} == restricted
    assert tools.DISCOVERY_DONE_TEXT in reqs[4]["context"]
    names_after_draft = [t["name"] for t in reqs[5]["tools"]]
    assert "describe_source" in names_after_draft
    assert tools.DISCOVERY_DONE_TEXT not in reqs[5]["context"]

    results = _tool_results(sid)
    assert results[3] == {"error": tools.DISCOVERY_DONE_TEXT}


def test_discovery_counter_resets_each_run(superuser, db, api_source, monkeypatch):
    monkeypatch.setenv("AI_AGENT_DISCOVERY_LIMIT", "3")
    get_settings.cache_clear()
    client = signed_in("root@example.com")
    sid = _new_session(client)
    fake.SHARED.queue(
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, "c1")], stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, "c2")], stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, "c3")], stop_reason="tool_use"),
        _chat_reply("Hecho."),
        _chat_reply(tool_calls=[_tool_call("get_workspace", {}, "c4")],
                    stop_reason="tool_use"),
        _chat_reply("Listo."),
    )
    r = _post_message(client, sid, "primera")
    assert r.status_code == 202
    r = _post_message(client, sid, "segunda")
    assert r.status_code == 202

    reqs = fake.SHARED.requests
    assert len(reqs) == 6
    names_first_run = [t["name"] for t in reqs[0]["tools"]]
    assert "describe_source" in names_first_run
    names_second_run = [t["name"] for t in reqs[4]["tools"]]
    assert "get_workspace" in names_second_run
    assert tools.DISCOVERY_DONE_TEXT not in reqs[4]["context"]


def test_direct_check_query_sql_non_postgres(superuser, db, api_source, supabase_calls):
    s = project_view(db, superuser.id)
    tools.reset_run(s)
    actor = db.get(AppUser, superuser.id)
    result, summary = tools.run_tool(
        db, actor, s, "check_query", {"source": "Origen API",
                                      "sql": "SELECT id FROM facturas"}, get_settings()
    )
    assert result["ok"] is False
    assert result["error"] == origin.SQL_NOT_SUPPORTED.format(kind="Supabase")
    assert "no admite SQL" in summary
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'source_described'")[0][0] == 0
    assert supabase_calls == []
    assert tools.discovery_count(s) == 1
    assert not (s.query_checks)


def test_direct_profile_supabase_once_and_repeat(superuser, db, api_source, supabase_calls):
    s = project_view(db, superuser.id)
    actor = db.get(AppUser, superuser.id)
    tools.reset_run(s)
    result, _ = tools.run_tool(
        db, actor, s, "profile_source", {"name": "Origen API",
                                         "table": "public.facturas"}, get_settings()
    )
    assert supabase_calls == ["facturas"]
    assert result["row_count"] == 42
    assert result["solo_conteo"] is True
    assert result["note"] == origin.COUNT_ONLY_NOTE
    assert result["columns"] == []
    result2, _ = tools.run_tool(
        db, actor, s, "profile_source", {"name": "Origen API",
                                         "table": "/facturas"}, get_settings()
    )
    assert result2["ya_consultado"] is True
    assert "42 filas" in result2["anterior"]
    assert result2["note"] == tools.REPEAT_NOTE
    assert supabase_calls == ["facturas"]
    tools.reset_run(s)
    result3, _ = tools.run_tool(
        db, actor, s, "profile_source", {"name": "Origen API",
                                         "table": "facturas"}, get_settings()
    )
    assert "ya_consultado" not in result3
    assert supabase_calls == ["facturas", "facturas"]


def test_direct_describe_normalises_path(superuser, db, api_source, describe_calls):
    s = project_view(db, superuser.id)
    actor = db.get(AppUser, superuser.id)
    result, _ = tools.run_tool(
        db, actor, s, "describe_source", {"name": "Origen API",
                                          "path": "/public.facturas"}, get_settings()
    )
    assert describe_calls == ["facturas"]
    assert result["path"] == "/facturas"


def test_direct_check_query_request_file_memo_respects_content(
    superuser, db, api_source, supabase_calls
):
    actor = db.get(AppUser, superuser.id)
    draft_files = {
        "integrations/facturas/requests/lista.yaml": textwrap.dedent(
            """\
            method: GET
            path: facturas
            params:
              select: id,total
            records: $
            fields:
              id: id
              total: total
            """
        )
    }
    s = project_view(db, superuser.id, draft_files)
    tools.reset_run(s)
    result, _ = tools.run_tool(
        db, actor, s, "check_query",
        {"source": "Origen API", "path": "integrations/facturas/requests/lista.yaml"},
        get_settings(),
    )
    assert "ya_consultado" not in result
    assert supabase_calls == ["facturas"]
    result2, _ = tools.run_tool(
        db, actor, s, "check_query",
        {"source": "Origen API", "path": "integrations/facturas/requests/lista.yaml"},
        get_settings(),
    )
    assert result2["ya_consultado"] is True
    assert result2["note"] == tools.REPEAT_NOTE
    assert supabase_calls == ["facturas"]

    new_files = dict(draft_files)
    new_files["integrations/facturas/requests/lista.yaml"] = draft_files[
        "integrations/facturas/requests/lista.yaml"
    ].replace("select: id,total", "select: id,total,fecha")
    write_project(s.project.id, new_files, superuser.id)
    s.refresh()
    result3, _ = tools.run_tool(
        db, actor, s, "check_query",
        {"source": "Origen API", "path": "integrations/facturas/requests/lista.yaml"},
        get_settings(),
    )
    assert "ya_consultado" not in result3
    assert supabase_calls == ["facturas", "facturas"]
    assert tools.discovery_count(s) == 0


def _raise_timeout(messages, tools, system):
    # 035: a timeout and a connection failure are the same code (provider_down).
    raise AIError("provider_down")


def test_timeout_retry_once_then_success(superuser, db, api_source):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    fake.SHARED.queue(_raise_timeout, _chat_reply("Listo."))
    r = _post_message(client, sid, "hola")
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == 2
    assert _last_assistant(sid) == "Listo."


def test_timeout_twice_stops_with_progress(superuser, db):
    client = signed_in("root@example.com")
    session_obj = _stored_session(
        db, superuser, status="open",
        working_state={
            "done": ["describí la tabla facturas"],
            "next": "comprobar la consulta",
        },
    )
    sid = session_obj.id
    fake.SHARED.queue(_raise_timeout, _raise_timeout, _chat_reply("no debe llegar"))
    r = _post_message(client, sid, "continúa")
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == 2
    last = _last_assistant(sid)
    assert last.startswith("No se pudo hablar con el proveedor de IA")
    assert "Hecho: describí la tabla facturas" in last
    assert "Siguiente: comprobar la consulta" in last
    assert t(service._CONTINUE_HINT) in last
    db.expire_all()
    s = db.get(AssistantSession, sid)
    assert s.working_state["progress"].startswith("No se pudo hablar con el proveedor de IA")


def test_timeout_retry_is_once_per_run(superuser, db, api_source):
    client = signed_in("root@example.com")
    sid = _new_session(client)
    fake.SHARED.queue(
        _chat_reply(tool_calls=[_tool_call("list_sources", {}, "c1")],
                    stop_reason="tool_use"),
        _raise_timeout,
        _raise_timeout,
    )
    r = _post_message(client, sid, "explora")
    assert r.status_code == 202
    assert len(fake.SHARED.requests) == 3
    last = _last_assistant(sid)
    assert last.startswith("No se pudo hablar con el proveedor de IA")


def test_direct_check_query_memo_follows_integration_yaml(
    superuser, db, api_source, supabase_calls
):
    actor = db.get(AppUser, superuser.id)
    draft_files = {
        "integrations/facturas/requests/lista.yaml": textwrap.dedent(
            """\
            method: GET
            path: facturas
            params:
              select: id,total
            records: $
            fields:
              id: id
              total: total
            """
        ),
        "integrations/facturas/integration.yaml": textwrap.dedent(
            """\
            name: Facturas
            datasets:
              facturas:
                extract:
                  request: requests/lista.yaml
                columns:
                  id: {type: integer}
                  total: {type: numeric}
                  fecha: {type: date}
            """
        ),
    }
    s = project_view(db, superuser.id, draft_files)
    tools.reset_run(s)
    result, _ = tools.run_tool(
        db, actor, s, "check_query",
        {"source": "Origen API", "path": "integrations/facturas/requests/lista.yaml"},
        get_settings(),
    )
    assert "ya_consultado" not in result
    assert supabase_calls == ["facturas"]
    result2, _ = tools.run_tool(
        db, actor, s, "check_query",
        {"source": "Origen API", "path": "integrations/facturas/requests/lista.yaml"},
        get_settings(),
    )
    assert result2["ya_consultado"] is True
    assert supabase_calls == ["facturas"]

    draft_files["integrations/facturas/integration.yaml"] = textwrap.dedent(
        """\
        name: Facturas
        datasets:
          facturas:
            extract:
              request: requests/lista.yaml
            columns:
              id: {type: integer}
              total: {type: numeric}
        """
    )
    write_project(s.project.id, draft_files, superuser.id)
    s.refresh()
    result3, _ = tools.run_tool(
        db, actor, s, "check_query",
        {"source": "Origen API", "path": "integrations/facturas/requests/lista.yaml"},
        get_settings(),
    )
    assert "ya_consultado" not in result3
    assert supabase_calls == ["facturas", "facturas"]


def test_timeout_retry_sends_heartbeat(superuser, db, api_source, monkeypatch):
    original = service._commit_round
    seen_counts = []

    def recorder(db, session, claim):
        seen_counts.append(len(fake.SHARED.requests))
        return original(db, session, claim)

    monkeypatch.setattr(service, "_commit_round", recorder)
    fake.SHARED.queue(_raise_timeout, _chat_reply("Listo."))
    client = signed_in("root@example.com")
    sid = _new_session(client)
    r = _post_message(client, sid, "Hola")
    assert r.status_code == 202
    assert _last_assistant(sid) == "Listo."
    assert 1 in seen_counts


def test_check_query_memo_a_b_a_resyncs_readiness(
    superuser, db, api_source, supabase_calls
):
    from app.assistant import readiness

    actor = db.get(AppUser, superuser.id)
    text_a = textwrap.dedent(
        """\
        method: GET
        path: facturas
        params:
          select: id,total
        records: $
        fields:
          id: id
          total: total
        """
    )
    text_b = text_a.replace("select: id,total", "select: id,total,fecha")
    path = "integrations/facturas/requests/lista.yaml"
    s = project_view(db, superuser.id, {path: text_a})
    tools.reset_run(s)

    def check():
        return tools.run_tool(
            db, actor, s, "check_query",
            {"source": "Origen API", "path": path},
            get_settings(),
        )[0]

    # A: real check
    result = check()
    assert "ya_consultado" not in result
    assert supabase_calls == ["facturas"]
    sha_a = readiness.file_sha(text_a)
    assert s.query_checks[path]["sha256"] == sha_a
    assert "deps" in s.query_checks[path]

    # A repeated: memo hit
    result = check()
    assert result["ya_consultado"] is True
    assert supabase_calls == ["facturas"]

    # B: real check
    write_project(s.project.id, {path: text_b}, superuser.id)
    s.refresh()
    result = check()
    assert "ya_consultado" not in result
    assert supabase_calls == ["facturas", "facturas"]
    assert s.query_checks[path]["sha256"] == readiness.file_sha(text_b)

    # Back to A: must be a real check because the stored check belongs to B
    write_project(s.project.id, {path: text_a}, superuser.id)
    s.refresh()
    result = check()
    assert "ya_consultado" not in result
    assert supabase_calls == ["facturas", "facturas", "facturas"]
    assert s.query_checks[path]["sha256"] == sha_a
    pending = readiness.compute(s)["pending"]
    assert not any(
        item.get("code") == "query_check" and item.get("file") == path
        for item in pending
    )

    # A again: memo valid now
    result = check()
    assert result["ya_consultado"] is True
    assert supabase_calls == ["facturas", "facturas", "facturas"]
