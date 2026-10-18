"""Feature 013 (US1/US3): integration controls API and controls-aware worker scheduling."""
import shutil
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.config import get_settings
from app.worker import Worker
from tests.conftest import reauth, signed_in, sql
from tests.test_runner import ORIGIN
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import apply, lock
from tests.test_vibe_reporting import workspace as workspace  # fixture
from tests.workspace_fixture import build

CONTROL_KINDS = ["integration_paused", "integration_resumed", "integration_schedule_changed"]
LONG_CRON = "0 3 * * " + ",".join(["1"] * 60)


def control_audits():
    return sql("SELECT kind, detail, actor_id FROM audit_event WHERE kind = ANY(:kinds) "
               "ORDER BY id", kinds=CONTROL_KINDS)


def run_worker_requests():
    w = Worker()
    w.take_requests()
    w.pool.shutdown(wait=True)


@pytest.fixture
def active_version_id():
    return sql("SELECT id FROM workspace_version WHERE state = 'active'")[0][0]


def control_fields(c, integration="ventas-prueba"):
    items = c.get("/api/integrations").json()["items"]
    item = next(i for i in items if i["id"] == integration)
    return item["control"], item["next_run"], item["running_run_id"]


def test_get_defaults(applied):
    ctl, top_next, running = control_fields(applied)
    assert ctl["paused"] is False
    assert ctl["schedule_source"] == "spec"
    assert ctl["window"] is None
    assert ctl["next_run"] is not None
    assert top_next == ctl["next_run"]
    assert running is None


def test_control_requires_superuser_and_stepup(applied, admin):
    c = signed_in("admin@example.com")
    r = c.put("/api/integrations/ventas-prueba/control", json={"paused": True})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"

    c = signed_in("root@example.com")
    r = c.put("/api/integrations/ventas-prueba/control", json={"paused": True})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "reauth_required"


def test_pause_resume_and_audit(applied):
    c = reauth(applied)
    r = c.put("/api/integrations/ventas-prueba/control", json={"paused": True})
    assert r.status_code == 200, r.text
    assert r.json()["control"]["paused"] is True
    assert r.json()["control"]["next_run"] is None

    ctl, top_next, _ = control_fields(c)
    assert ctl["paused"] is True
    assert ctl["next_run"] is None
    assert top_next is None

    root_id = sql("SELECT id FROM app_user WHERE email = 'root@example.com'")[0][0]
    rows = control_audits()
    assert rows[-1][0] == "integration_paused"
    assert rows[-1][1]["before"] == {"paused": False}
    assert rows[-1][1]["after"] == {"paused": True}
    assert rows[-1][2] == root_id

    r = c.put("/api/integrations/ventas-prueba/control", json={"paused": False})
    assert r.status_code == 200
    assert r.json()["control"]["paused"] is False
    assert r.json()["control"]["next_run"] is not None

    ctl, top_next, _ = control_fields(c)
    assert ctl["paused"] is False
    assert ctl["next_run"] is not None
    assert top_next is not None

    rows = control_audits()
    assert rows[-1][0] == "integration_resumed"
    assert rows[-1][1]["before"] == {"paused": True}
    assert rows[-1][1]["after"] == {"paused": False}


@pytest.mark.parametrize(
    "payload,field,code",
    [
        ({"schedule": "bad"}, "schedule", "invalid_cron"),
        ({"schedule": "*/2 * * * *"}, "schedule", "too_frequent"),
        ({"window_start": "06:00"}, "window_start", "window_incomplete"),
        ({"window_start": "06:00", "window_end": "06:00"}, "window_start", "window_empty"),
        ({"full_rebuild_cron": "*/1 * * * *"}, "full_rebuild_cron", "too_frequent"),
        ({"schedule": LONG_CRON}, "schedule", "too_long"),
        ({"full_rebuild_cron": LONG_CRON}, "full_rebuild_cron", "too_long"),
    ],
)
def test_control_422_cases(applied, payload, field, code):
    c = reauth(applied)
    r = c.put("/api/integrations/ventas-prueba/control", json=payload)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["fields"][field] == code
    assert sql("SELECT count(*) FROM integration_control")[0][0] == 0
    assert len(control_audits()) == 0


def test_noop_put_does_not_create_row_or_audit(applied):
    c = reauth(applied)
    r = c.put("/api/integrations/ventas-prueba/control", json={"paused": False})
    assert r.status_code == 200, r.text
    assert sql("SELECT count(*) FROM integration_control")[0][0] == 0
    assert len(control_audits()) == 0


def test_schedule_override_window_and_restore(applied):
    c = reauth(applied)
    r = c.put("/api/integrations/ventas-prueba/control",
              json={"schedule": "*/15 * * * *", "window_start": "06:00",
                    "window_end": "22:00"})
    assert r.status_code == 200, r.text
    ctl = r.json()["control"]
    assert ctl["schedule"] == "*/15 * * * *"
    assert ctl["schedule_source"] == "override"
    assert ctl["schedule_words"] == "Cada 15 minutos"
    assert ctl["window"] == {"start": "06:00", "end": "22:00"}

    rows = control_audits()
    schedule_rows = [r for r in rows if r[0] == "integration_schedule_changed"]
    assert len(schedule_rows) == 1
    detail = schedule_rows[0][1]
    assert detail["before"]["schedule"] is None
    assert detail["after"]["schedule"] == "*/15 * * * *"
    assert detail["after"]["window_start"] == "06:00"
    assert detail["after"]["window_end"] == "22:00"

    r = c.put("/api/integrations/ventas-prueba/control",
              json={"schedule": None, "window_start": None, "window_end": None})
    assert r.status_code == 200, r.text
    ctl = r.json()["control"]
    assert ctl["schedule_source"] == "spec"
    assert ctl["window"] is None

    rows = control_audits()
    schedule_rows = [r for r in rows if r[0] == "integration_schedule_changed"]
    assert schedule_rows[-1][1]["before"]["schedule"] == "*/15 * * * *"
    assert schedule_rows[-1][1]["after"]["schedule"] is None


def test_idempotent_put_no_extra_audit(applied):
    c = reauth(applied)
    r = c.put("/api/integrations/ventas-prueba/control", json={"paused": True})
    assert r.status_code == 200
    before = len(control_audits())

    r = c.put("/api/integrations/ventas-prueba/control", json={"paused": True})
    assert r.status_code == 200
    after = len(control_audits())
    assert after == before


def test_unknown_integration_404(applied):
    c = reauth(applied)
    r = c.put("/api/integrations/nope/control", json={"paused": True})
    assert r.status_code == 404


def test_worker_reload_sees_control_change(applied):
    w = Worker()
    w.reload()
    item = applied.get("/api/integrations").json()["items"][0]
    spec_schedule = item["control"]["spec_schedule"]
    jobs = {j.id for j in w.scheduler.get_jobs()}
    assert f"ventas-prueba:incremental:{spec_schedule}" in jobs
    old_ids = {id(j) for j in w.scheduler.get_jobs()}

    w.reload()
    assert {id(j) for j in w.scheduler.get_jobs()} == old_ids

    c = reauth(applied)
    r = c.put("/api/integrations/ventas-prueba/control", json={"schedule": "*/15 * * * *"})
    assert r.status_code == 200

    w.reload()
    jobs = {j.id for j in w.scheduler.get_jobs()}
    assert "ventas-prueba:incremental:*/15 * * * *" in jobs
    assert f"ventas-prueba:incremental:{spec_schedule}" not in jobs


def test_run_scheduled_honours_pause_window_and_manual_ignores(applied, monkeypatch,
                                                               active_version_id):
    calls = []

    class FakeRun:
        id = None
        status = "succeeded"

    def fake_run(*args, **kwargs):
        calls.append(kwargs.get("kind"))
        return FakeRun()

    monkeypatch.setattr("app.worker.runner.run_integration", fake_run)

    c = reauth(applied)
    r = c.put("/api/integrations/ventas-prueba/control", json={"paused": True})
    assert r.status_code == 200

    w = Worker()
    w.run_scheduled(active_version_id, "ventas-prueba", "incremental")
    assert calls == []

    r = c.put("/api/integrations/ventas-prueba/control",
              json={"paused": False, "window_start": "06:00", "window_end": "07:00"})
    assert r.status_code == 200

    tz = ZoneInfo(get_settings().timezone)
    outside = datetime(2026, 1, 1, 12, 0, tzinfo=tz).astimezone(UTC)
    inside = datetime(2026, 1, 1, 6, 30, tzinfo=tz).astimezone(UTC)

    w.run_scheduled(active_version_id, "ventas-prueba", "incremental", now=outside)
    assert calls == []

    w.run_scheduled(active_version_id, "ventas-prueba", "incremental", now=inside)
    assert calls == ["incremental"]

    r = c.put("/api/integrations/ventas-prueba/control", json={"paused": True})
    assert r.status_code == 200
    r = c.post("/api/integrations/ventas-prueba/run", json={"kind": "incremental"})
    assert r.status_code == 202, r.text
    run_worker_requests()
    assert "manual_incremental" in calls


def test_window_timezone_rejected_without_touching_existing_control(applied):
    c = reauth(applied)
    before = sql("SELECT count(*) FROM integration_control")[0][0]

    r = c.put("/api/integrations/ventas-prueba/control",
              json={"window_start": "06:00+02:00", "window_end": "22:00"})
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == {"window_start": "window_timezone"}

    r = c.put("/api/integrations/ventas-prueba/control",
              json={"window_start": "06:00", "window_end": "22:00Z"})
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == {"window_end": "window_timezone"}

    assert sql("SELECT count(*) FROM integration_control")[0][0] == before
    assert len(control_audits()) == 0


def test_control_kept_when_integration_leaves_and_returns(applied, workspace):
    c = reauth(applied)
    r = c.put("/api/integrations/ventas-prueba/control",
              json={"paused": True, "schedule": "*/15 * * * *"})
    assert r.status_code == 200, r.text

    shutil.rmtree(workspace / "integrations")
    shutil.rmtree(workspace / "reports")
    lock(workspace)
    version = apply(c)
    assert version["integrations"] == []

    r = c.get("/api/integrations")
    assert all(item["id"] != "ventas-prueba" for item in r.json()["items"])
    assert sql("SELECT paused, schedule FROM integration_control "
               "WHERE integration_id = 'ventas-prueba'") == [(True, "*/15 * * * *")]

    worker = Worker()
    try:
        worker.reload()
        assert not any(
            job.id.startswith("ventas-prueba:") for job in worker.scheduler.get_jobs())
    finally:
        worker.pool.shutdown(wait=True)

    r = c.put("/api/integrations/ventas-prueba/control", json={"paused": True})
    assert r.status_code == 404

    build(workspace, ORIGIN)
    lock(workspace)
    version = apply(c)
    assert version["integrations"] == ["ventas-prueba"]

    r = c.get("/api/integrations")
    item = next(item for item in r.json()["items"] if item["id"] == "ventas-prueba")
    assert item["control"]["paused"] is True
    assert item["control"]["schedule"] == "*/15 * * * *"
    assert item["control"]["schedule_source"] == "override"
    assert item["control"]["next_run"] is None
    assert item["next_run"] is None

    worker = Worker()
    try:
        worker.reload()
        ids = [job.id for job in worker.scheduler.get_jobs()]
        assert "ventas-prueba:incremental:*/15 * * * *" in ids
    finally:
        worker.pool.shutdown(wait=True)
