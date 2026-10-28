"""Feature 041: root causes of the /speckit-all dead end (guard deadlock, report conflict,
epoch units, no-progress stop).
"""

from types import SimpleNamespace

import pytest

from app.ai import fake
from app.assistant import tools
from app.assistant.commands import pipeline
from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import extract
from app.i18n import t
from app.models import AppUser
from app.sources import service as sources
from tests.conftest import new_chat, project_view, signed_in, sql
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


def test_a_check_that_read_no_shape_still_blocks():
    path = "integrations/cmc/requests/rates.yaml"
    session = _session({path: {"ok": False, "keys": [], "error": "x"}})
    ops = [
        {
            "op": "write",
            "path": path,
            "content": "records: $.data\nfields:\n  symbol: $.symbol\n",
        }
    ]

    with pytest.raises(tools.ToolError):
        tools._requests_checked(session, ops)


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
    # Distinct call ids on purpose: the detector must compare names and args only.
    fake.SHARED.queue(
        *[
            _chat_reply(
                tool_calls=[_tool_call("list_sources", {}, call_id=f"c{i}")],
                stop_reason="tool_use",
            )
            for i in range(1, 6)
        ]
    )

    response = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "hola"})
    assert response.status_code == 202

    # The third identical round with no file written ends the turn.
    assert len(fake.SHARED.requests) == 3

    rows = sql(
        "SELECT content FROM assistant_message "
        "WHERE session_id = :i AND role = 'assistant' ORDER BY id DESC LIMIT 1",
        i=sid,
    )
    # "assistant.no_progress" is added by the fix.
    assert rows[0][0] == t("assistant.no_progress", rounds=3, tools="list_sources")
