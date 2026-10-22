"""Feature 028: the mode gate and the contract limits (FR-000, FR-003, FR-007, FR-012)."""
import pytest

from app.ai import fake
from app.assistant import auto
from app.config import get_settings
from app.models import AssistantSession, Project
from tests.conftest import PASSWORD, new_chat, signed_in, sql
from tests.test_assistant_api import _chat_reply, _tool_call


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


CONTRACT = {"goal": "reporte de ventas", "stages": ["draft", "preview", "apply"]}


def _confirm(client, sid, contract=None):
    return client.post(f"/api/assistant/sessions/{sid}/contract",
                       json={"contract": contract or CONTRACT, "password": PASSWORD})


def _send(client, sid, text="hazlo"):
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": text})
    assert r.status_code == 202, r.text
    return client.get(f"/api/assistant/sessions/{sid}").json()


def _tool_results(body):
    return [m for m in body["messages"] if m["role"] == "tool"]


def _offered(client, sid):
    """The tool names the service offers for this conversation, through the real filter."""
    from app.assistant import tools as assistant_tools
    from app.assistant.service import for_session
    from app.db import get_sessionmaker
    from app.models import AssistantSession

    with get_sessionmaker()() as db:
        session = db.get(AssistantSession, sid)
        from app.assistant.service import attach_auto_run

        attach_auto_run(db, session)
        view = for_session(db, session)
        specs, _ = assistant_tools.offered_tool_specs(view, get_settings())
        return {spec["name"] for spec in specs}


# --- Ask ---------------------------------------------------------------------------------

def test_ask_offers_reads_only_and_refuses_writes(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    r = client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "ask"})
    assert r.status_code == 200

    offered = _offered(client, sid)
    assert "propose_draft" not in offered and "edit_draft" not in offered
    assert "run_preview" not in offered and "update_notes" not in offered
    assert {"describe_source", "get_workspace", "read_draft"} <= offered

    fake.SHARED.queue(_chat_reply(tool_calls=[_tool_call("propose_draft",
                                                        {"files": {"a.md": "x"}})],
                                  stop_reason="tool_use"),
                      _chat_reply("No puedo escribir en modo Preguntar."))
    body = _send(client, sid)
    results = _tool_results(body)
    assert results and results[0]["tool_name"] == "propose_draft"
    assert "Preguntar" in results[0]["content"]
    assert sql("SELECT count(*) FROM assistant_auto_run") == [(0,)]


def test_ask_refuses_check_query_with_a_draft_path(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "ask"})
    fake.SHARED.queue(_chat_reply(tool_calls=[_tool_call(
        "check_query", {"path": "integrations/x/queries/y.sql"})], stop_reason="tool_use"),
        _chat_reply("Listo."))
    body = _send(client, sid)
    assert "Preguntar" in _tool_results(body)[0]["content"]


# --- Edit stays as it was ----------------------------------------------------------------

def test_auto_without_a_contract_offers_the_whole_channel(superuser, db):
    """A new conversation is Auto: the writes are offered, the contract opens with the call."""
    from app.assistant.commands import guard

    client = signed_in("root@example.com")
    sid = new_chat(client)
    offered = _offered(client, sid)
    # Auto keeps the execution channel even before any contract exists (feature 028 revision): the
    # channel is what lets the agent write, preview and apply instead of handing the clicks back.
    assert offered == (set(guard.allowed_tools(None)) - {"suggest_command"}
                       | {"set_current_spec", "run_command", "run_preview", "apply_draft"})


# --- Auto ---------------------------------------------------------------------------------

def test_auto_without_a_contract_opens_one_and_uses_the_auto_tools(superuser, db):
    """Owner, 2026-10-21: an Auto conversation is never left with read tools only.

    The channel used to be gated on a confirmed contract, so a spent contract (or a conversation
    that never ran one) answered "solo herramientas de lectura" and left the human the last clicks.
    Selecting Auto is the authorisation: the first stage/preview/apply opens the contract itself.
    """
    client = signed_in("root@example.com")
    sid = new_chat(client)
    client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "auto"})
    offered = _offered(client, sid)
    assert {"run_command", "run_preview", "apply_draft"} <= offered

    fake.SHARED.queue(_chat_reply(tool_calls=[_tool_call("apply_draft", {})],
                                  stop_reason="tool_use"),
                      _chat_reply("No hay nada que aplicar."))
    body = _send(client, sid)
    refusal = _tool_results(body)[0]["content"].lower()
    assert "contrato" not in refusal
    # Refused for the real reason (nothing to apply), and the turn survives so the agent can fix it.
    assert "borrador" in refusal
    assert any(m["content"] == "No hay nada que aplicar." for m in body["messages"])
    assert sql("SELECT count(*) FROM assistant_auto_run WHERE session_id = :i", i=sid) == [(1,)]


def test_contract_stages_clip_the_tools(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    assert _confirm(client, sid, contract={"goal": "x", "stages": ["draft", "preview"]}
                    ).status_code == 201
    offered = _offered(client, sid)
    assert "run_command" in offered and "run_preview" in offered
    assert "apply_draft" not in offered


def test_apply_is_refused_when_the_contract_stops_at_preview(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    assert _confirm(client, sid, contract={"goal": "x", "stages": ["draft", "preview"]}
                    ).status_code == 201
    fake.SHARED.queue(_chat_reply(tool_calls=[_tool_call("apply_draft", {})],
                                  stop_reason="tool_use"),
                      _chat_reply("Termino aquí."))
    body = _send(client, sid)
    assert "etapa" in _tool_results(body)[0]["content"].lower()
    assert sql("SELECT count(*) FROM workspace_version") == [(0,)]


def test_source_allow_list_refuses_an_unknown_source(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    r = _confirm(client, sid, contract={
        "goal": "x", "stages": ["draft"], "sources": [{"name": "otra"}]})
    assert r.status_code == 422          # an unknown source is a field error
    assert "sources" in r.json()["error"]["fields"]


def test_source_allow_list_matches_names_and_tables():
    contract = auto.RunContract.model_validate({
        "goal": "x", "stages": ["draft"],
        "sources": [{"name": "ERP", "tables": ["facturas"]}]})
    assert auto.source_refusal(contract, "erp") is None            # case-insensitive
    assert auto.source_refusal(contract, "erp", "FACTURAS") is None
    refused = auto.source_refusal(contract, "erp", "clientes")
    assert refused and refused.code == "assistant.contract.source_not_allowed"
    other = auto.source_refusal(contract, "otra")
    assert other and "ERP" not in other.message
    assert auto.source_refusal(None, "otra") is None               # no contract: no narrowing
    empty = auto.RunContract.model_validate({"goal": "x", "stages": ["draft"]})
    assert auto.source_refusal(empty, "cualquiera") is None


def test_preview_limit_zero_refuses_the_preview(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    contract = {"goal": "x", "stages": ["draft", "preview"],
                "limits": {"tokens": 100000, "previews": 0, "applies": 0,
                           "wall_clock_seconds": 600}}
    assert _confirm(client, sid, contract=contract).status_code == 201
    fake.SHARED.queue(_chat_reply(tool_calls=[_tool_call("run_preview", {})],
                                  stop_reason="tool_use"),
                      _chat_reply("No puedo previsualizar."))
    body = _send(client, sid)
    assert "límite" in _tool_results(body)[0]["content"].lower()


def test_mode_down_stops_the_run_and_keeps_the_draft(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    assert _confirm(client, sid).status_code == 201
    sql("UPDATE assistant_session SET busy_since = now() WHERE id = :i", i=sid)

    r = client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "edit"})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "edit"
    row = sql("SELECT status, stop_reason FROM assistant_auto_run WHERE session_id = :i", i=sid)
    assert row == [("stopped", "stopped:mode")]


def test_detener_marks_the_contract_stopped(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    assert _confirm(client, sid).status_code == 201
    sql("UPDATE assistant_session SET busy_since = now() WHERE id = :i", i=sid)

    assert client.post(f"/api/assistant/sessions/{sid}/stop").status_code == 200
    row = sql("SELECT status, stop_reason FROM assistant_auto_run WHERE session_id = :i", i=sid)
    assert row == [("stopped", "stopped:user")]
    summary = sql("SELECT summary IS NOT NULL FROM assistant_auto_run WHERE session_id = :i",
                  i=sid)
    assert summary == [(True,)]


# --- The gate itself ----------------------------------------------------------------------

def test_mode_gate_matrix():
    class S:
        mode = "ask"

    refusal = auto.mode_gate(S(), "propose_draft", {}, None)
    assert refusal and refusal.code == "assistant.mode.ask_refused"
    assert auto.mode_gate(S(), "describe_source", {}, None) is None
    assert auto.mode_gate(S(), "check_query", {"path": "x.sql"}, None) is not None
    assert auto.mode_gate(S(), "check_query", {}, None) is None
    assert auto.mode_gate(S(), "update_notes", {}, None) is not None

    S.mode = "auto"
    contract = auto.RunContract.model_validate({"goal": "x", "stages": ["draft"]})
    assert auto.mode_gate(S(), "run_command", {"command": "speckit-plan"}, contract) is None
    assert auto.mode_gate(S(), "run_preview", {}, contract) is not None      # stage clipped
    assert auto.mode_gate(S(), "apply_draft", {}, contract) is not None
    # No contract is the normal state between runs: the channel is open and the contract opens
    # with the call (owner, 2026-10-21).
    assert auto.mode_gate(S(), "apply_draft", {}, None) is None
    assert auto.mode_gate(S(), "run_preview", {}, None) is None
    assert auto.mode_gate(S(), "run_command", {}, None) is None

    S.mode = "edit"
    assert auto.mode_gate(S(), "apply_draft", {}, None).code == "assistant.contract.required"


def test_revoked_role_stops_the_next_tool_call(superuser, db):
    """Edge FR-028: the super user that confirmed the contract loses the role mid-run."""
    client = signed_in("root@example.com")
    sid = new_chat(client)
    assert _confirm(client, sid, contract={"goal": "x", "stages": ["draft"]}).status_code == 201
    sql("UPDATE app_user SET is_superuser = false, role = 'user' WHERE email = 'root@example.com'")

    fake.SHARED.queue(_chat_reply(tool_calls=[_tool_call("get_workspace", {})],
                                  stop_reason="tool_use"),
                      _chat_reply("Sin autorización."))
    r = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "sigue"})
    assert r.status_code in (202, 403)      # the request itself may already be refused
    if r.status_code == 202:
        body = client.get(f"/api/assistant/sessions/{sid}").json()
        tools = [m for m in body["messages"] if m["role"] == "tool"]
        assert tools and "revocada" in tools[0]["content"].lower()


def test_offered_names_never_widen_edit():
    base = frozenset({"describe_source", "propose_draft", "run_preview"})
    assert auto.offered_names("edit", None, base) == base
    assert "apply_draft" not in auto.offered_names("edit", None, base)
    auto_contract = auto.RunContract.model_validate({"goal": "x",
                                                     "stages": ["draft", "preview", "apply"]})
    widened = auto.offered_names("auto", auto_contract, base)
    assert {"apply_draft", "run_command", "run_preview"} <= widened


def test_the_agent_applies_inside_its_own_turn(superuser, db):
    """Reported: the run ended "Auto · detenido" and left "pulsa Vista previa y Aplicar".

    `apply_draft` runs inside the agent's own turn, which holds the busy claim, so the project's
    idle guard refused every autonomous apply with `assistant_busy`. The conversation doing the
    apply is now excluded from that guard, and a refusal comes back as a tool result.
    """
    from app.projects import apply as project_apply

    client = signed_in("root@example.com")
    sid = new_chat(client)
    client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "auto"})
    # Only the self-exclusion matters here: assert the guard ignores our own session.
    session = db.get(AssistantSession, sid)
    sql("UPDATE assistant_session SET busy_since = now() WHERE id = :i", i=sid)
    db.expire_all()
    session = db.get(AssistantSession, sid)
    project = db.get(Project, session.project_id)
    project_apply._ensure_idle(db, project, sid)          # no raise: it is our own claim
    with pytest.raises(Exception) as other:
        project_apply._ensure_idle(db, project, -1)        # another conversation: still refused
    assert getattr(other.value, "code", "") == "assistant_busy"
