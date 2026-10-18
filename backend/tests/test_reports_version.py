"""Tests for the lightweight report data-version endpoint (feature 015, task T001)."""
from tests.conftest import client, reauth, signed_in, sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import SELECTION, run_worker_requests
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture


def test_version_matches_data_freshness_for_superuser(applied):
    """Superuser gets the same data_version/updated_at as /data freshness."""
    r = applied.get("/api/reports/ventas/version")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"data_version", "updated_at"}
    assert r.headers.get("Cache-Control") == "no-store"

    data = applied.get(f"/api/reports/ventas/data?{SELECTION}").json()
    assert body["data_version"] == data["freshness"]["data_version"]
    assert body["updated_at"] == data["freshness"]["updated_at"]


def test_version_requires_authentication(applied):
    """Unauthenticated requests are rejected with 401."""
    assert client().get("/api/reports/ventas/version").status_code == 401


def test_version_access_follows_grants(applied, user):
    """Plain users need a dashboard_access grant, same as /data."""
    u = signed_in("user@example.com")
    assert u.get("/api/reports/ventas/version").status_code == 403
    dash_id = sql("SELECT id FROM dashboard WHERE code = 'ventas'")[0][0]
    sql("INSERT INTO dashboard_access (user_id, dashboard_id, granted_by) "
        "VALUES (:u, :d, :u)", u=user.id, d=dash_id)
    assert u.get("/api/reports/ventas/version").status_code == 200
    assert u.get("/api/reports/nope/version").status_code == 404


def test_version_changes_after_new_succeeded_run(applied):
    """A new succeeded integration run changes data_version even without new rows."""
    v1 = applied.get("/api/reports/ventas/version").json()
    r = reauth(applied).post("/api/integrations/ventas-prueba/run", json={"kind": "full"})
    assert r.status_code == 202, r.text
    run_worker_requests()
    runs = applied.get("/api/integrations/ventas-prueba/runs").json()["items"]
    assert runs[0]["status"] == "succeeded", runs[0]

    v2 = applied.get("/api/reports/ventas/version").json()
    assert v2["data_version"] != v1["data_version"]
    data = applied.get(f"/api/reports/ventas/data?{SELECTION}").json()
    assert data["freshness"]["data_version"] == v2["data_version"]


def test_version_stable_and_does_not_write_cache(applied):
    """Calling /version is idempotent and never populates report_cache."""
    before = sql("SELECT count(*) FROM report_cache")[0][0]
    v1 = applied.get("/api/reports/ventas/version").json()
    v2 = applied.get("/api/reports/ventas/version").json()
    assert v1 == v2
    after = sql("SELECT count(*) FROM report_cache")[0][0]
    assert after == before
