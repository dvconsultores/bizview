"""Stop a running integration (feature 013, US2)."""
import json
import threading
import time
from contextlib import contextmanager
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import psycopg
import pytest
import yaml
from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.engine import datasets, extract, runner
from app.models import AppUser
from app.security.netguard import Policy
from app.sources import service as sources
from app.sources.connectors import postgresql, rest
from app.worker import Worker
from tests.conftest import TEST_SCHEMA, reauth, signed_in, sql
from tests.test_netguard import fake_dns
from tests.test_runner import NOW, TZ, ds_sql, ds_table, lines, run
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.tls_helpers import StubServer


@contextmanager
def held_lock(integration_id: str):
    with get_engine().connect() as conn:
        pg = conn.connection.driver_connection
        pg.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))",
                   (runner._lock_key(integration_id),))
        pg.commit()
        try:
            yield
        finally:
            pg.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                       (runner._lock_key(integration_id),))
            pg.commit()


def lock_free(integration_id: str) -> bool:
    """True when no session holds the integration's advisory lock
    (queries pg_locks across all sessions, so a lock leaked on a pooled
    connection is detected even if the probe reuses that connection)."""
    with get_engine().connect() as conn:
        pg = conn.connection.driver_connection
        got = pg.execute(
            "SELECT NOT EXISTS ("
            "SELECT 1 FROM pg_locks "
            "WHERE locktype = 'advisory' AND granted AND "
            "database = (SELECT oid FROM pg_database WHERE datname = current_database()) AND "
            "objsubid = 1 AND "
            "((classid::bigint << 32) | objid::bigint) = hashtextextended(%s, 0)"
            ")",
            (runner._lock_key(integration_id),),
        ).fetchone()[0]
        pg.commit()
        return got


def _allow_loopback(monkeypatch):
    loop = Policy(allow_loopback_for_tests=True)
    for mod in (extract, rest, postgresql):
        monkeypatch.setattr(mod, "policy_from_settings", lambda s: loop)


@pytest.fixture
def slow_rest(monkeypatch, superuser):
    state = {"slow": False}

    def handler(h):
        query = parse_qs(urlsplit(h.path).query)
        page = int(query.get("page", ["1"])[0])
        if h.headers.get("Authorization") != "Bearer tok":
            h.send_response(401)
            h.send_header("Content-Length", "0")
            h.end_headers()
            return
        if state["slow"]:
            time.sleep(0.3)
            items = [{"id": page * 10 + 1}, {"id": page * 10 + 2}]
        elif page == 1:
            items = [{"id": 1}, {"id": 2}]
        else:
            items = []
        body = json.dumps({"data": {"items": items}}).encode()
        h.send_response(200)
        h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)

    server = StubServer(handler)
    _allow_loopback(monkeypatch)
    definition = {"id": "rest-lenta", "spec": "specs/integrations/003-rest-lenta",
                  "source": "API lenta", "schedule": "0 * * * *", "timezone": TZ,
                  "time_limit_minutes": 5,
                  "datasets": {"orders": {
                      "primary_key": ["id"], "columns": {"id": {"type": "bigint"}},
                      "extract": {"request": "requests/orders.yaml"},
                      "incremental": {"mode": "full"}}}}
    request = {"method": "GET", "path": "/orders", "records": "$.data.items",
               "fields": {"id": "id"},
               "pagination": {"type": "page", "param": "page", "size_param": "per_page",
                              "size": 2, "max_pages": 1000}}
    files = {"requests/orders.yaml": yaml.safe_dump(request)}

    with get_sessionmaker().begin() as db:
        sources.create(db, db.get(AppUser, superuser.id), {
            "name": "API lenta", "kind": "rest",
            "settings": {"base_url": f"http://stub.test:{server.port}/v1", "auth": "bearer",
                         "headers": [], "timeout_seconds": 5},
            "secrets": {"token": "tok"}}, get_settings(), None)
    fake_dns(monkeypatch, {"stub.test": ["127.0.0.1"]})   # unresolvable at create: accepted

    yield state, server, definition, files

    state["slow"] = False
    server.close()
    with get_engine().begin() as conn:
        datasets.drop_integration(conn.connection.driver_connection, "rest-lenta")


def test_stop_flag_reads_at_most_every_interval(monkeypatch):
    now = [0.0]
    calls = []

    def fake_read(self):
        calls.append(now[0])
        return (False, None)

    monkeypatch.setattr(runner.StopFlag, "_read", fake_read)
    flag = runner.StopFlag(1, clock=lambda: now[0])
    for t in (0.0, 1.0, 1.99, 2.0, 3.5, 4.0):
        now[0] = t
        flag()
    assert calls == [0.0, 2.0, 4.0]
    calls.clear()
    now[0] = 10.0

    def fake_read_stop(self):
        calls.append(now[0])
        return (True, "Ana Admin")

    monkeypatch.setattr(runner.StopFlag, "_read", fake_read_stop)
    with pytest.raises(runner.RunStopped) as exc:
        flag()
    assert exc.value.by == "Ana Admin"
    assert calls == [10.0]


def test_stop_during_bulk_copy_publishes_nothing(origin, monkeypatch):
    first = run()
    assert first.status == "succeeded"
    before = lines()
    before_products = ds_sql(
        f"SELECT product_code FROM {ds_table('ventas-prueba', 'products')} ORDER BY 1")
    sql("INSERT INTO origin_sales VALUES ('B9', 1, 'sale', :t, 2, 'P9')",
        t=NOW - timedelta(hours=1))

    class FakeStop:
        def __init__(self):
            self.calls = 0

        def __call__(self):
            self.calls += 1
            if self.calls == 3:
                raise runner.RunStopped("Ana Admin")

    fake = FakeStop()
    monkeypatch.setattr(runner, "StopFlag", lambda run_id: fake)
    r = run()
    assert r.status == "stopped"
    assert r.message == "detenida por Ana Admin"
    assert fake.calls == 3
    assert lines() == before
    assert ds_sql(
        f"SELECT product_code FROM {ds_table('ventas-prueba', 'products')} ORDER BY 1"
    ) == before_products
    assert sql("SELECT status, message, finished_at IS NOT NULL FROM integration_run "
               "WHERE id = :id", id=r.id) == [("stopped", "detenida por Ana Admin", True)]


def test_stop_slow_rest_run_via_api(slow_rest):
    state, server, definition, files = slow_rest
    first = runner.run_integration(definition, files, version_id=None, now=NOW)
    assert first.status == "succeeded"
    assert ds_sql(f"SELECT id FROM {ds_table('rest-lenta', 'orders')} ORDER BY id") == [
        (1,), (2,)]
    start = len(server.requests)
    state["slow"] = True
    result = []
    thread = threading.Thread(
        target=lambda: result.append(runner.run_integration(definition, files,
                                                           version_id=None, now=NOW)),
        daemon=True)
    thread.start()
    c = reauth(signed_in("root@example.com"))
    run_id = None
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and run_id is None:
            rows = sql("SELECT id FROM integration_run WHERE integration_id = 'rest-lenta' "
                       "AND status = 'running' ORDER BY id DESC")
            if rows:
                run_id = rows[0][0]
            else:
                time.sleep(0.1)
        assert run_id is not None, "the REST run did not start"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and len(server.requests) - start < 3:
            time.sleep(0.1)
        t0 = time.monotonic()
        r = c.post(f"/api/integrations/rest-lenta/runs/{run_id}/stop")
        assert r.status_code == 202
        assert r.json() == {"run_id": run_id, "stop_requested": True, "status": "running"}
        thread.join(30)
        assert not thread.is_alive()
        assert time.monotonic() - t0 < 30
    finally:
        state["slow"] = False
        thread.join(30)

    run_row = result[0]
    assert run_row.status == "stopped"
    assert run_row.message == "detenida por Super Usuario"
    assert ds_sql(f"SELECT id FROM {ds_table('rest-lenta', 'orders')} ORDER BY id") == [
        (1,), (2,)]
    root_id = sql("SELECT id FROM app_user WHERE email = 'root@example.com'")[0][0]
    assert sql("SELECT stop_requested_by, stop_requested_at IS NOT NULL "
               "FROM integration_run WHERE id = :id", id=run_id) == [(root_id, True)]
    assert sql("SELECT actor_id, detail FROM audit_event "
               "WHERE kind = 'integration_run_stopped'") == [
        (root_id, {"integration": "rest-lenta", "run_id": run_id,
                   "before": {"status": "running", "stop_requested": False},
                   "after": {"status": "running", "stop_requested": True}})]
    r = c.post(f"/api/integrations/rest-lenta/runs/{run_id}/stop")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_stop_endpoint_rules(superuser, admin):
    running = sql("INSERT INTO integration_run (integration_id, kind, status) "
                  "VALUES ('ventas-prueba', 'incremental', 'running') RETURNING id")[0][0]
    finished = sql("INSERT INTO integration_run (integration_id, kind, status) "
                   "VALUES ('ventas-prueba', 'incremental', 'succeeded') RETURNING id")[0][0]
    root_id = superuser.id

    admin_client = reauth(signed_in("admin@example.com"))
    r = admin_client.post(f"/api/integrations/ventas-prueba/runs/{running}/stop")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"

    root_no_step = signed_in("root@example.com")
    r = root_no_step.post(f"/api/integrations/ventas-prueba/runs/{running}/stop")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "reauth_required"

    root = reauth(signed_in("root@example.com"))
    r = root.post("/api/integrations/ventas-prueba/runs/999999/stop")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"

    r = root.post(f"/api/integrations/otra/runs/{running}/stop")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"

    r = root.post(f"/api/integrations/ventas-prueba/runs/{finished}/stop")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"

    with held_lock("ventas-prueba"):
        r = root.post(f"/api/integrations/ventas-prueba/runs/{running}/stop")
        assert r.status_code == 202
        assert r.json() == {"run_id": running, "stop_requested": True, "status": "running"}
        r = root.post(f"/api/integrations/ventas-prueba/runs/{running}/stop")
        assert r.status_code == 202
        assert r.json() == {"run_id": running, "stop_requested": True, "status": "running"}
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'integration_run_stopped'") == [
        (1,)]
    assert sql("SELECT stop_requested_by FROM integration_run WHERE id = :id",
               id=running) == [(root_id,)]

    r = root.get("/api/integrations/ventas-prueba/runs")
    run_item = next(item for item in r.json()["items"] if item["id"] == running)
    assert run_item["stop_requested_at"] is not None
    assert run_item["status"] == "running"


def test_stop_orphaned_run_finishes_at_once(superuser):
    running = sql("INSERT INTO integration_run (integration_id, kind, status) "
                  "VALUES ('ventas-prueba', 'incremental', 'running') RETURNING id")[0][0]
    root = reauth(signed_in("root@example.com"))
    r = root.post(f"/api/integrations/ventas-prueba/runs/{running}/stop")
    assert r.status_code == 202
    assert r.json() == {"run_id": running, "stop_requested": True, "status": "stopped"}
    assert lock_free("ventas-prueba")
    assert sql("SELECT status, message, finished_at IS NOT NULL, stop_requested_by "
               "FROM integration_run WHERE id = :id", id=running) == [
        ("stopped", "detenida por Super Usuario", True, superuser.id)]
    audit_rows = sql("SELECT detail, actor_id FROM audit_event "
                     "WHERE kind = 'integration_run_stopped' AND detail->>'run_id' = :rid",
                     rid=str(running))
    assert len(audit_rows) == 1
    detail, actor = audit_rows[0]
    assert detail["after"] == {"status": "stopped", "stop_requested": True}
    assert actor == superuser.id
    r = root.post(f"/api/integrations/ventas-prueba/runs/{running}/stop")
    assert r.status_code == 409


def test_stop_orphan_after_earlier_request(superuser):
    running = sql("INSERT INTO integration_run (integration_id, kind, status) "
                  "VALUES ('ventas-prueba', 'incremental', 'running') RETURNING id")[0][0]
    root = reauth(signed_in("root@example.com"))
    with held_lock("ventas-prueba"):
        r = root.post(f"/api/integrations/ventas-prueba/runs/{running}/stop")
        assert r.status_code == 202
        assert r.json() == {"run_id": running, "stop_requested": True, "status": "running"}
    assert lock_free("ventas-prueba")
    r = root.post(f"/api/integrations/ventas-prueba/runs/{running}/stop")
    assert r.status_code == 202
    assert r.json() == {"run_id": running, "stop_requested": True, "status": "stopped"}
    assert lock_free("ventas-prueba")
    audit_rows = sql("SELECT detail FROM audit_event WHERE kind = 'integration_run_stopped' "
                     "AND detail->>'run_id' = :rid ORDER BY id", rid=str(running))
    assert len(audit_rows) == 2
    assert audit_rows[0][0]["before"] == {"status": "running", "stop_requested": False}
    assert audit_rows[1][0]["before"] == {"status": "running", "stop_requested": True}


def test_worker_sweep_marks_only_orphaned_runs(superuser):
    sql("INSERT INTO integration_run (integration_id, kind, status) "
        "VALUES ('ventas-prueba', 'incremental', 'running')")
    sql("INSERT INTO integration_run (integration_id, kind, status) "
        "VALUES ('otra', 'incremental', 'running')")
    sql("INSERT INTO integration_run (integration_id, kind, status) "
        "VALUES ('otra', 'incremental', 'succeeded')")
    worker = Worker()
    try:
        with held_lock("otra"):
            assert worker.sweep_orphaned_runs() == 1
        assert lock_free("ventas-prueba")
        assert lock_free("otra")
        assert sql("SELECT count(*) FROM integration_run "
                   "WHERE integration_id = 'ventas-prueba' AND status = 'running'") == [(0,)]
        assert sql("SELECT status, message, finished_at IS NOT NULL FROM integration_run "
                   "WHERE integration_id = 'ventas-prueba'") == [
            ("failed", "el trabajador se reinició", True)]
        assert sql("SELECT status FROM integration_run WHERE integration_id = 'otra' "
                   "ORDER BY status") == [("running",), ("succeeded",)]
        assert worker.sweep_orphaned_runs() == 1
        assert lock_free("otra")
        assert sql("SELECT count(*) FROM integration_run WHERE integration_id = 'otra' "
                   "AND status = 'running'") == [(0,)]
    finally:
        worker.pool.shutdown(wait=True)


def test_cancel_call_and_track():
    c = extract.Cancel()
    assert c.call(lambda: 5) == 5
    with pytest.raises(ValueError, match="x"):
        c.call(lambda: (_ for _ in ()).throw(ValueError("x")))
    threading.Timer(0.3, c.cancel).start()
    t0 = time.monotonic()
    with pytest.raises(extract.Cancelled):
        c.call(lambda: time.sleep(10))
    assert time.monotonic() - t0 < 2
    assert c.cancelled
    with pytest.raises(extract.Cancelled):
        c.call(lambda: 1)
    with pytest.raises(extract.Cancelled):
        with c.track(object()):
            pass


def test_cancel_interrupts_running_statement():
    c = extract.Cancel()
    with get_engine().connect() as conn:
        pg = conn.connection.driver_connection
        timer = threading.Timer(0.5, c.cancel)
        try:
            with c.track(pg):
                timer.start()
                t0 = time.monotonic()
                with pytest.raises(psycopg.errors.QueryCanceled):
                    pg.execute("SELECT pg_sleep(30)")
                assert time.monotonic() - t0 < 10
                pg.rollback()
        finally:
            timer.cancel()


def test_stop_while_origin_query_blocks(origin, monkeypatch):
    assert run().status == "succeeded"
    before = lines()

    locked = threading.Event()
    release = threading.Event()

    def locker():
        with get_engine().connect() as lc:
            lc.execute(text(f'LOCK TABLE "{TEST_SCHEMA}".origin_sales IN ACCESS EXCLUSIVE MODE'))
            locked.set()
            release.wait(60)
            lc.rollback()

    thread = threading.Thread(target=locker, daemon=True)
    thread.start()
    assert locked.wait(10)

    t0 = [None]

    def fake_read(self):
        if t0[0] is not None and time.monotonic() - t0[0] > 1.0:
            return (True, "Ana Admin")
        return (False, None)

    monkeypatch.setattr(runner.StopFlag, "_read", fake_read)
    t0[0] = time.monotonic()
    try:
        r = run()
        elapsed = time.monotonic() - t0[0]
    finally:
        release.set()
        thread.join(30)

    assert r.status == "stopped"
    assert r.message == "detenida por Ana Admin"
    assert elapsed < 15
    assert lines() == before
