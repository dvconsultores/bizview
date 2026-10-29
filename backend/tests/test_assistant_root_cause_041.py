"""Feature 041: root causes of the /speckit-all dead end (guard deadlock, report conflict,
epoch units, no-progress stop).
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.ai import fake
from app.assistant import tools
from app.assistant.commands import pipeline
from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import extract
from app.i18n import t
from app.models import AppUser, AssistantMessage, AssistantSession
from app.sources import service as sources
from tests.conftest import new_chat, project_view, signed_in, sql, write_project
from tests.test_assistant_api import _chat_reply, _tool_call

pytestmark = pytest.mark.usefixtures("without_command_guard")

SUPABASE_REQUEST = """\
method: GET
path: facturas
params:
  select: id,total
records: $
fields:
  id: id
  total: total
"""


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
        sources.create(s, s.get(AppUser, superuser.id),
            {"name": "Origen API", "kind": "supabase",
             "settings": {"url": "https://203.0.113.9"},
             "secrets": {"service_key": "clave-de-prueba"}},
            get_settings(), None)
    yield


@pytest.fixture()
def supabase_calls(monkeypatch):
    calls: list[str] = []

    def fake_supabase_once(settings, secrets, app, request, params, **kwargs):
        calls.append(request["path"])
        return [{"id": 1, "total": 2.5}], {}

    monkeypatch.setattr(extract, "supabase_once", fake_supabase_once)
    return calls


def _session(query_checks=None, command="speckit-implement"):
    return SimpleNamespace(command_run=SimpleNamespace(command=command), query_checks=query_checks)


def test_run_check_stores_the_keys_of_the_shape(db, superuser, api_source, supabase_calls):
    path = "integrations/facturas/requests/lista.yaml"
    actor = db.get(AppUser, superuser.id)
    session = project_view(db, superuser.id, {path: SUPABASE_REQUEST})
    tools.reset_run(session)

    tools.run_tool(
        db,
        actor,
        session,
        "check_query",
        {"source": "Origen API", "path": path},
        get_settings(),
    )

    assert supabase_calls == ["facturas"]
    entry = session.query_checks[path]
    assert entry["ok"] is True
    # The guard can only name the real keys if the check stored them.
    assert entry["keys"] == ["id", "total"]


def test_a_failed_check_with_a_read_shape_lets_the_agent_fix_the_fields():
    path = "integrations/cmc/requests/rates.yaml"
    entry = {
        "sha256": "x",
        "ok": False,
        "keys": ["symbol", "hour"],
        "columns": ["symbol", "hour"],
        "error": "column hour does not exist",
        "at": None,
    }
    session = _session({path: entry})
    ops = [
        {
            "op": "write",
            "path": path,
            "content": "records: $.data\nfields:\n  symbol: $.symbol\n  hour: $.hour\n",
        }
    ]

    # The last check did read the shape, so the agent may correct the file.
    assert tools._requests_checked(session, ops) is None


def test_a_failed_check_with_a_wrong_column_names_the_real_keys():
    path = "integrations/cmc/requests/rates.yaml"
    entry = {
        "sha256": "x",
        "ok": False,
        "keys": ["symbol", "hour"],
        "columns": ["symbol", "hour"],
        "error": "column hour does not exist",
        "at": None,
    }
    session = _session({path: entry})
    ops = [
        {
            "op": "write",
            "path": path,
            "content": "records: $.data\nfields:\n  symbol: $.symbol\n  ghost: $.ghost\n",
        }
    ]

    with pytest.raises(tools.ToolError) as error:
        tools._requests_checked(session, ops)

    assert "ghost" in str(error.value)
    assert "symbol" in str(error.value)


def test_an_unchecked_request_still_blocks():
    path = "integrations/cmc/requests/rates.yaml"
    session = _session({})
    ops = [
        {
            "op": "write",
            "path": path,
            "content": "records: $.data\nfields:\n  symbol: $.symbol\n",
        }
    ]

    with pytest.raises(tools.ToolError):
        tools._requests_checked(session, ops)


def test_a_structural_failure_lets_the_agent_fix_records():
    path = "integrations/cmc/requests/rates.yaml"
    session = _session(
        {
            path: {
                "sha256": "x",
                "ok": False,
                "keys": [],
                "columns": [],
                "error": "'$.data' no es una lista en la respuesta",
                "at": None,
            }
        }
    )
    ops = [
        {
            "op": "write",
            "path": path,
            "content": "records: $\nfields:\n  value: $.data.value\n",
        }
    ]

    # The check ran and read no shape (records points at an object), so the corrective write
    # must land — blocking here was the production deadlock (run 133).
    assert tools._requests_checked(session, ops) is None


def test_an_unchecked_request_without_fields_may_be_created():
    path = "integrations/cmc/requests/rates.yaml"
    session = _session({})
    ops = [
        {
            "op": "write",
            "path": path,
            "content": "method: GET\npath: rates\nrecords: $.data\n",
        }
    ]

    # A new file must be creatable or check_query has nothing to check (C8: creation deadlock).
    assert tools._requests_checked(session, ops) is None


def test_extract_reads_an_object_as_one_record():
    payload = {"data": {"value": 42, "classification": "Greed"}}
    request = {
        "records": "$.data",
        "fields": {"value": "$.value", "classification": "$.classification"},
    }

    # An object at the records path is one record (production endpoints return a single object).
    result = extract._records(payload, request, ["value", "classification"])

    assert result == [{"value": "42", "classification": "Greed"}]


OBJECT_REQUEST = """\
method: GET
path: facturas
records: $.data
fields:
  id: id
  total: total
"""


def test_check_query_reads_the_keys_of_an_object_response(
    db, superuser, api_source, monkeypatch
):
    def fake_supabase_once(settings, secrets, app, request, params, **kwargs):
        return {"data": {"id": 1, "total": 2.5}}, {}

    monkeypatch.setattr(extract, "supabase_once", fake_supabase_once)
    path = "integrations/facturas/requests/lista.yaml"
    actor = db.get(AppUser, superuser.id)
    session = project_view(db, superuser.id, {path: OBJECT_REQUEST})
    tools.reset_run(session)

    tools.run_tool(
        db,
        actor,
        session,
        "check_query",
        {"source": "Origen API", "path": path},
        get_settings(),
    )

    entry = session.query_checks[path]
    assert entry["ok"] is True
    assert entry["keys"] == ["id", "total"]


def test_scoped_history_finds_the_anchor_beyond_the_window(db, superuser):
    from app.assistant import service as assistant_service

    client = signed_in("root@example.com")
    sid = new_chat(client)
    session = db.get(AssistantSession, sid)

    db.add(AssistantMessage(session_id=sid, role="user", content="Objetivo: panorama cripto"))
    for i in range(35):
        db.add(AssistantMessage(session_id=sid, role="assistant", content=f"ronda {i}"))
    db.flush()
    last_id = db.scalar(
        select(AssistantMessage.id)
        .where(AssistantMessage.session_id == sid)
        .order_by(AssistantMessage.id.desc())
        .limit(1)
    )

    run = SimpleNamespace(
        result={pipeline.PIPELINE_KEY: {"id": 1}, "history_from": last_id},
        spec=None,
    )

    # With a single user message older than the 30-row window the stage opened with an empty
    # history and died `blocked:ai_history_invalid` (C7).
    messages = assistant_service._scoped_history(db, session, run)

    assert messages
    assert messages[0].role == "user"
    assert "Objetivo" in messages[0].content


def test_a_third_identical_read_is_refused(db, superuser):
    # en producción el modelo releyó dos archivos sin cambios cientos de veces y agotó el
    # contexto (C13).
    path = "specs/001-x/spec.md"
    session = project_view(db, superuser.id, {path: "# X\n"})
    tools.reset_run(session)
    actor = db.get(AppUser, superuser.id)
    tools.run_tool(db, actor, session, "read_draft", {"paths": [path]}, get_settings())
    tools.run_tool(db, actor, session, "read_draft", {"paths": [path]}, get_settings())
    with pytest.raises(tools.ToolError):
        tools.run_tool(db, actor, session, "read_draft", {"paths": [path]}, get_settings())


def test_a_changed_file_resets_the_read_counter(db, superuser):
    path = "specs/001-x/spec.md"
    session = project_view(db, superuser.id, {path: "# X\n"})
    tools.reset_run(session)
    actor = db.get(AppUser, superuser.id)
    tools.run_tool(db, actor, session, "read_draft", {"paths": [path]}, get_settings())
    tools.run_tool(db, actor, session, "read_draft", {"paths": [path]}, get_settings())
    write_project(session.project.id, {path: "# X2\n"}, superuser.id)
    tools.run_tool(db, actor, session, "read_draft", {"paths": [path]}, get_settings())
    tools.run_tool(db, actor, session, "read_draft", {"paths": [path]}, get_settings())


def test_the_run_report_does_not_reopen_an_applied_project():
    from app.projects.service import changed_files

    applied = {"project.yaml": "a"}
    current = {"project.yaml": "a", "specs/001-x/run-report.md": "# informe"}
    # C15: the pipeline writes its report after the apply snapshot; a generated file must not
    # flip the project back to «Cambios sin aplicar».
    assert changed_files(applied, current) == {"added": [], "changed": [], "removed": []}


def test_the_run_report_is_replaced_not_conflicted(db, superuser):
    session = project_view(db, superuser.id, {"specs/001-x/spec.md": "# X\n"})
    state = {"id": None, "specs": ["001-x"], "cursor": 0}

    pipeline.write_report(
        db, session, "001-x", state, result="stopped", stop="limite"
    )
    # Second report for the same spec must replace the file instead of raising FileChanged.
    pipeline.write_report(db, session, "001-x", state, result="ready")

    session.refresh()
    assert "ready" in session.files()["specs/001-x/run-report.md"]


def test_extract_converts_declared_epoch_units():
    payload = {
        "data": [{"ts": 1758067200, "ms": 1758067200000, "iso": "2025-09-17T00:00:00Z", "raw": "x"}]
    }
    request = {
        "records": "$.data",
        "fields": {"ts": "$.ts", "ms": "$.ms", "iso": "$.iso", "raw": "$.raw"},
        "timestamp_units": {
            "ts": "seconds",
            "ms": "milliseconds",
            "iso": "iso8601",
            "raw": "seconds",
        },
    }

    rows = extract._records(payload, request, ["ts", "ms", "iso", "raw"])

    assert rows[0]["ts"] == "2025-09-17T00:00:00+00:00"
    assert rows[0]["ms"] == "2025-09-17T00:00:00+00:00"
    assert rows[0]["iso"] == "2025-09-17T00:00:00Z"
    # A non-numeric value under a declared unit passes through raw.
    assert rows[0]["raw"] == "x"


def test_three_identical_rounds_without_progress_stop_the_stage(superuser):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    # Each stuck round fails the edit and succeeds a read, which keeps the per-call brake quiet;
    # distinct call ids on purpose — the detector must compare names and args only.
    ops = [{"op": "replace", "path": "specs/001-x/no-existe.md", "old": "a", "new": "b"}]
    fake.SHARED.queue(
        *[
            _chat_reply(
                tool_calls=[
                    _tool_call("list_sources", {}, call_id=f"a{i}"),
                    _tool_call("edit_draft", {"ops": ops}, call_id=f"b{i}"),
                ],
                stop_reason="tool_use",
            )
            for i in range(1, 6)
        ]
    )

    response = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "hola"})
    assert response.status_code == 202

    # The third identical stuck round with no file written ends the turn.
    assert len(fake.SHARED.requests) == 3

    rows = sql(
        "SELECT content FROM assistant_message "
        "WHERE session_id = :i AND role = 'assistant' ORDER BY id DESC LIMIT 1",
        i=sid,
    )
    # "assistant.no_progress" is added by the fix.
    assert rows[0][0] == t("assistant.no_progress", rounds=3,
                           tools="edit_draft, list_sources")
