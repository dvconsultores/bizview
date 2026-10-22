"""Feature 028: post-apply watch, auto rollback and visibility (FR-008, FR-009, SC-005)."""
from datetime import UTC, datetime

import pytest

from app.ai import ChatReply, ChatUsage, ToolCall, fake  # noqa: F401  (kept for the fixtures)
from app.assistant import auto, service
from app.config import get_settings
from app.models import AppUser, AssistantAutoRun, AssistantSession
from app.worker import Worker, _failed_checks
from tests.conftest import new_chat, signed_in, sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield
    get_settings.cache_clear()


class _Run:
    def __init__(self, status="succeeded", checks=None, message=None):
        self.id = 1
        self.status = status
        self.checks = checks or []
        self.message = message


def test_failed_checks_make_a_run_count_as_failed():
    assert _failed_checks(_Run(checks=[{"dataset": "d", "ok": True}])) is False
    assert _failed_checks(_Run(checks=[{"dataset": "d", "ok": False}])) is True
    assert _failed_checks(_Run(checks=[])) is False


def _version(db, *, state="previous", artifacts=None):
    """A workspace version row; `previous` by default (one row may be `active`)."""
    from app.models import WorkspaceVersion

    row = WorkspaceVersion(checksum=f"c-{state}-{datetime.now(UTC).timestamp()}", lock={},
                           specs={}, state=state,
                           artifacts=artifacts or {"reports": {}, "integrations": {}})
    db.add(row)
    db.commit()
    return row


def _armed_run(db, session, version_id=None, auto_rollback=True, integration="facturas"):
    contract = auto.RunContract.model_validate({
        "goal": "x", "stages": ["draft", "preview", "apply"],
        "auto_rollback": auto_rollback}).model_dump(mode="json")
    version_id = version_id or _version(db, artifacts={
        "reports": {}, "integrations": {integration: {}}}).id
    row = AssistantAutoRun(session_id=session.id, project_id=session.project_id,
                           contract=contract, status="applied", confirmed_by=session.created_by,
                           version_id=version_id, watch_integration=integration,
                           watch_state="pending")
    db.add(row)
    db.commit()
    return row


def test_watch_reports_failure_without_rollback(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    session = db.get(AssistantSession, sid)
    watch = _armed_run(db, session, auto_rollback=False)

    worker = Worker.__new__(Worker)          # only the watch path is exercised
    worker._resolve_auto_watch(_Run(status="failed", message="origen no responde"),
                               watch.version_id, "facturas")

    assert sql("SELECT watch_state FROM assistant_auto_run WHERE id = :i", i=watch.id) == \
        [("failed",)]
    messages = [row[0] for row in sql(
        "SELECT content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid)]
    assert any("origen no responde" in text for text in messages)


def test_watch_rolls_back_and_reports_in_the_conversation(superuser, db):
    """SC-005: with `auto_rollback` a failing first run restores the previous version."""
    client = signed_in("root@example.com")
    sid = new_chat(client)
    session = db.get(AssistantSession, sid)
    watch = _armed_run(db, session, auto_rollback=True)
    _version(db, state="active")          # the version the rollback comes back to

    worker = Worker.__new__(Worker)
    worker._resolve_auto_watch(_Run(status="failed", message="boom"), watch.version_id, "facturas")

    assert sql("SELECT watch_state FROM assistant_auto_run WHERE id = :i", i=watch.id) == \
        [("rolled_back",)]
    assert sql("SELECT kind FROM audit_event WHERE kind = 'workspace_rolled_back'")
    messages = [row[0] for row in sql(
        "SELECT content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid)]
    assert any("boom" in text for text in messages)
    assert any("versión anterior" in text for text in messages)


def test_watch_survives_a_failed_rollback(superuser, db, monkeypatch):
    """`auto_rollback` that cannot run must not kill the worker: it reports and marks failed."""
    from app.workspace import service as workspace_service

    def boom(db, actor, ip):
        raise RuntimeError("no previous version")

    monkeypatch.setattr(workspace_service, "rollback", boom)
    client = signed_in("root@example.com")
    sid = new_chat(client)
    session = db.get(AssistantSession, sid)
    watch = _armed_run(db, session, auto_rollback=True)

    worker = Worker.__new__(Worker)
    worker._resolve_auto_watch(_Run(status="failed", message="boom"), watch.version_id, "facturas")

    assert sql("SELECT watch_state FROM assistant_auto_run WHERE id = :i", i=watch.id) == \
        [("failed",)]
    messages = [row[0] for row in sql(
        "SELECT content FROM assistant_message WHERE session_id = :i ORDER BY id", i=sid)]
    assert any("boom" in text for text in messages)


def test_watch_ignores_another_integration(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    session = db.get(AssistantSession, sid)
    watch = _armed_run(db, session, integration="facturas")

    worker = Worker.__new__(Worker)
    worker._resolve_auto_watch(_Run(status="failed"), watch.version_id, "otra")
    assert sql("SELECT watch_state FROM assistant_auto_run WHERE id = :i", i=watch.id) == \
        [("pending",)]


def test_visible_to_grants_only_active_user_role_accounts(superuser, db):
    from app.models import Dashboard

    client = signed_in("root@example.com")
    sid = new_chat(client)
    session = db.get(AssistantSession, sid)
    person = AppUser(email="u@example.com", full_name="U", role="user", is_active=True,
                     must_change_password=False, failed_attempts=0, password_hash="x")
    db.add(person)
    dashboard = Dashboard(code="demo-auto", name="Demo", description="d", icon="chart-line",
                          status="available", report_id="demo")
    db.add(dashboard)
    db.commit()

    class _Version:
        def __init__(self):
            self.id = _version(db, artifacts={"reports": {"demo": {}},
                                              "integrations": {"facturas": {}}}).id
            self.artifacts = {"reports": {"demo": {}}, "integrations": {"facturas": {}}}

    version = _Version()
    run = _armed_run(db, session, version_id=version.id)
    service._grant_dashboards(db, version, session, run)
    db.commit()
    granted = sql("SELECT user_id FROM dashboard_access WHERE dashboard_id = :i", i=dashboard.id)
    assert granted == [(person.id,)]
    assert sql("SELECT kind FROM audit_event WHERE kind = 'dashboard_granted'")


def test_no_grants_when_the_contract_names_no_roles(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    session = db.get(AssistantSession, sid)
    run = _armed_run(db, session)

    class _Version:
        def __init__(self):
            self.id = _version(db, artifacts={"reports": {"demo": {}},
                                              "integrations": {"facturas": {}}}).id
            self.artifacts = {"reports": {"demo": {}}, "integrations": {"facturas": {}}}

    service.arm_auto_watch(db, session, run, _Version())
    db.commit()
    assert sql("SELECT watch_state, watch_integration FROM assistant_auto_run WHERE id = :i",
               i=run.id) == [("pending", "facturas")]
    assert sql("SELECT count(*) FROM dashboard_access") == [(0,)]


def test_arm_watch_without_integrations_does_not_watch(superuser, db):
    client = signed_in("root@example.com")
    sid = new_chat(client)
    session = db.get(AssistantSession, sid)

    class _Version:
        def __init__(self):
            self.id = _version(db).id
            self.artifacts = {"reports": {}, "integrations": {}}

    version = _Version()
    run = _armed_run(db, session, version_id=version.id)
    service.arm_auto_watch(db, session, run, version)
    db.commit()
    assert sql("SELECT watch_state FROM assistant_auto_run WHERE id = :i", i=run.id) == [(None,)]


def test_contract_grants_visibility_only_when_it_declares_it(superuser, db):
    """The contract is the only thing that can widen visibility (owner: no step-up by default)."""
    client = signed_in("root@example.com")
    sid = new_chat(client)
    contract = {"goal": "x", "stages": ["draft"], "visible_to": ["user"]}
    bad = client.post(f"/api/assistant/sessions/{sid}/contract",
                      json={"contract": contract, "password": "nope"})
    assert bad.status_code == 201
    assert sql("SELECT contract ->> 'visible_to' FROM assistant_auto_run") == [("[\"user\"]",)]
    assert sql("SELECT count(*) FROM assistant_auto_run") == [(1,)]


def test_the_agent_applies_from_its_own_turn(db, superuser, workspace):
    """The reported dead end: the agent could never apply — its own turn was "busy".

    `apply_draft` → `apply_project` → `_ensure_idle(project)` counted the conversation doing the
    apply, so every autonomous apply answered `assistant_busy`, the run stopped, and the human was
    left with "pulsa Vista previa y Aplicar".
    """
    from app.assistant.tools import run_tool
    from app.projects.workview import for_session
    from tests.test_assistant_apply import _applied, _draft_files, _session

    _applied(workspace)
    session = _session(db, superuser, _draft_files())
    session.mode = "auto"
    session.busy_since = datetime.now(UTC)          # the agent's own turn holds the claim
    db.commit()

    view = for_session(db, session)
    contract = auto.RunContract.model_validate({"goal": "aplica", "stages": ["preview", "apply"]})
    run = AssistantAutoRun(session_id=session.id, project_id=session.project_id,
                           contract=contract.model_dump(mode="json"), status="running",
                           confirmed_by=session.created_by)
    db.add(run)
    db.commit()
    session.auto_run = run

    result, summary = run_tool(db, superuser, view, "apply_draft", {}, get_settings())
    version_id = result.get("id")
    assert version_id, (result, summary)                # the applied version
    assert "versión" in summary.lower() or "version" in summary.lower()
    session = db.get(AssistantSession, session.id)
    assert session.applied_version_id == version_id     # it is the conversation's version
    # The run is closed by the turn's summary (`finish_auto_run`), so here only the contract's own
    # record of the apply is asserted.
    assert run.version_id == version_id and run.applies == 1 and run.status == "running"
