"""Feature 041: the production dead end replayed inside the real /speckit-implement loop."""

import pytest

from app.ai import fake
from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import extract
from app.models import AppUser
from app.projects import fs
from app.sources import service as sources
from tests.test_assistant_commands_service import _call, _reply, _send, _session
from tests.test_assistant_commands_service import chat as chat
from tests.test_assistant_commands_service import fake_provider as fake_provider

SPEC_PATH = "specs/001-mercado-cripto/spec.md"
PLAN_PATH = "specs/001-mercado-cripto/plan.md"
TASKS_PATH = "specs/001-mercado-cripto/tasks.md"
INTEGRATION_PATH = "integrations/mercado-cripto/integration.yaml"
REQUEST_PATH = "integrations/mercado-cripto/requests/global-metrics.yaml"

SPEC = """\
# Mercado cripto

**Tipo**: integracion

**Status**: Approved

Métricas globales del mercado cripto.
"""

PLAN = "# Plan\n\nIntegración integrations/mercado-cripto sobre la fuente Origen API.\n"

TASKS = "# Tasks\n\n## Phase 1\n\n- [ ] T001 Corregir fields de global-metrics.yaml\n"

INTEGRATION = """\
id: mercado-cripto
spec: specs/001-mercado-cripto
source: Origen API
schedule: "*/15 * * * *"
datasets:
  global:
    description: Métricas globales del mercado en una captura.
    columns:
      snapshot_at:
        type: timestamptz
      total_market_cap:
        type: numeric
    primary_key: [snapshot_at]
    date_column: snapshot_at
    incremental:
      mode: full
    extract:
      request: requests/global-metrics.yaml
"""

REQUEST_WRONG = """\
method: GET
path: global-metrics
records: $
fields:
  snapshot_at: snapshot
  total_market_cap: quote_total
"""

# One call corrects the mapping, ticks the task and flips the status.
FIX_OPS = [
    {
        "op": "replace",
        "path": REQUEST_PATH,
        "old": "  total_market_cap: quote_total\n",
        "new": "  total_market_cap: total_market_cap\ntimestamp_units:\n  snapshot_at: seconds\n",
    },
    {"op": "replace", "path": TASKS_PATH, "old": "- [ ] T001", "new": "- [X] T001"},
    {
        "op": "replace",
        "path": SPEC_PATH,
        "old": "**Status**: Approved",
        "new": "**Status**: Implemented",
    },
]


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
def market_shape(monkeypatch):
    def fake_supabase_once(settings, secrets, app, request, params, **kwargs):
        return [{"snapshot": 1758067200, "total_market_cap": 1.5}], {}

    monkeypatch.setattr(extract, "supabase_once", fake_supabase_once)
    return fake_supabase_once


def test_implement_fixes_a_wrong_request_after_a_failed_check(chat, superuser, api_source,
                                                              market_shape):
    client, project, sid = chat
    files = {
        SPEC_PATH: SPEC,
        PLAN_PATH: PLAN,
        TASKS_PATH: TASKS,
        INTEGRATION_PATH: INTEGRATION,
        REQUEST_PATH: REQUEST_WRONG,
    }
    fs.apply_ops(project["id"],
                 [{"op": "write", "path": path, "content": text, "base_sha256": None,
                   "force": True} for path, text in files.items()],
                 {"kind": "user", "user_id": 1, "session_id": None, "command": "edit"})

    fake.SHARED.queue(
        # Round 1: no check ran yet, so the guard refuses the write.
        _reply(calls=[_call("edit_draft", {"ops": FIX_OPS}, call_id="e1")]),
        # Round 2: the check fails on `quote_total`, but it reads the shape's keys.
        _reply(calls=[_call("check_query",
                            {"source": "Origen API", "path": REQUEST_PATH}, call_id="q1")]),
        # Round 3: the same write is now allowed (041).
        _reply(calls=[_call("edit_draft", {"ops": FIX_OPS}, call_id="e2")]),
        _reply(calls=[_call("finish_command", {"summary": "Mercado cripto listo"},
                            call_id="f1")]),
    )

    _send(client, sid, "/speckit-implement 001-mercado-cripto")

    session = _session(client, sid)
    assert session["command_runs"][0]["status"] == "completed"

    tool_texts = [message["content"] or "" for message in session["messages"]
                  if message["role"] == "tool"]
    assert any("Antes de escribir" in text for text in tool_texts)

    assistant_texts = [message["content"] or "" for message in session["messages"]
                       if message["role"] == "assistant"]
    assert not any("error inesperado" in text for text in assistant_texts)

    listed, _ = fs.list_files(project["slug"])
    assert REQUEST_PATH in listed
    request = fs.read_text(project["slug"], REQUEST_PATH)
    assert "total_market_cap: total_market_cap" in request
    assert "timestamp_units" in request
    assert "- [X] T001" in fs.read_text(project["slug"], TASKS_PATH)
