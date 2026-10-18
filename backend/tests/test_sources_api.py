"""Feature 004 / US1: data-source catalogue API (FR-001 - FR-006, FR-011, FR-012)."""
import pytest

from app.config import get_settings
from app.sources import service
from app.sources.connectors import TestResult
from tests.conftest import client, make_user, reauth, signed_in, sql

PW = "Origin-Secret-9f3k"
PG = {"name": "ERP ventas", "kind": "postgresql", "description": "Origen",
      "settings": {"host": "203.0.113.9", "port": 5432, "database": "erp", "username": "bi_ro"},
      "secrets": {"password": PW}}


@pytest.fixture
def su(superuser):
    return reauth(signed_in(superuser.email))


def create(c, body=None):
    r = c.post("/api/sources", json=body or PG)
    assert r.status_code == 201, r.text
    return r.json()


def test_crud_and_secrets_are_write_only(su):
    src = create(su)
    assert src["secret_fields"] == ["password"] and PW not in str(src)
    assert src["settings"]["sslmode"] == "require" and src["settings"]["timeout_seconds"] == 15
    for r in (su.get("/api/sources"), su.get(f"/api/sources/{src['id']}")):
        assert r.status_code == 200 and PW not in r.text
    raw = sql("SELECT secrets_ct, settings::text FROM data_source")[0]
    assert PW.encode() not in bytes(raw[0]) and PW not in raw[1]
    # omitted keeps, value replaces, null clears
    su.patch(f"/api/sources/{src['id']}", json={"settings": {**PG["settings"], "port": 6543}})
    assert service.secrets_of(_row(src["id"]))["password"] == PW
    su.patch(f"/api/sources/{src['id']}", json={"secrets": {"password": "New-Pass-123"}})
    assert service.secrets_of(_row(src["id"]))["password"] == "New-Pass-123"
    r = su.patch(f"/api/sources/{src['id']}", json={"secrets": {"password": None}})
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"secrets.password": "required"}
    assert su.delete(f"/api/sources/{src['id']}").status_code == 204
    kinds = [k for (k,) in sql("SELECT kind FROM audit_event WHERE kind LIKE 'source%' "
                               "ORDER BY id")]
    assert kinds == ["source_created", "source_updated", "source_updated", "source_deleted"]
    details = str(sql("SELECT detail FROM audit_event"))
    assert PW not in details and "New-Pass-123" not in details and "credentials" in details


def _row(source_id):
    from app.db import get_sessionmaker
    from app.models import DataSource
    with get_sessionmaker()() as s:
        return s.get(DataSource, source_id)


def test_duplicate_name_any_case(su):
    create(su)
    r = su.post("/api/sources", json={**PG, "name": "erp VENTAS"})
    assert r.status_code == 409


def test_kind_is_immutable(su):
    src = create(su)
    r = su.patch(f"/api/sources/{src['id']}", json={"kind": "rest"})
    assert r.status_code == 422


@pytest.mark.parametrize("host", ["127.0.0.1", "169.254.169.254", "localhost", "backend",
                                  "metadata.google.internal"])
def test_blocked_destinations_refused_on_save(su, host):
    r = su.post("/api/sources", json={**PG, "settings": {**PG["settings"], "host": host}})
    if host == "metadata.google.internal":           # unresolvable here: allowed to save
        assert r.status_code in (201, 422)
        return
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["settings.host"] == "blocked_address"


def test_only_super_user(admin, user, superuser):
    for who in (admin, user):
        c = reauth(signed_in(who.email))
        assert c.get("/api/sources").status_code == 403
        assert c.post("/api/sources", json=PG).status_code == 403
    assert client().get("/api/sources").status_code == 401


def test_mutations_and_tests_need_step_up(superuser):
    c = signed_in(superuser.email)
    for method, path in (("POST", "/api/sources"), ("POST", "/api/sources/test")):
        r = c.request(method, path, json=PG)
        assert r.json()["error"]["code"] == "reauth_required"


def test_profile_rules_http_vs_https(su, monkeypatch):
    rest = {"name": "API", "kind": "rest",
            "settings": {"base_url": "http://203.0.113.9/api", "auth": "bearer"},
            "secrets": {"token": "tok-123456"}}
    assert su.post("/api/sources", json=rest).status_code == 201          # private: http ok
    plain = {**PG, "name": "plano", "settings": {**PG["settings"], "sslmode": "disable"}}
    assert su.post("/api/sources", json=plain).status_code == 201
    s = get_settings()
    monkeypatch.setattr(s, "security_profile", "internet")
    monkeypatch.setattr(s, "site_address", "bi.example.com")
    monkeypatch.setattr(s, "cookie_secure", True)
    # internet: admins need two-step; enroll quickly for this test
    import time

    from tests.test_mfa import enroll
    enroll(su, t=time.time())
    r = su.post("/api/sources", json={**rest, "name": "API2"})
    assert r.json()["error"]["fields"] == {"settings.base_url": "not_allowed_in_profile"}
    types = su.get("/api/sources/types").json()
    pg_ssl = next(f for f in types["postgresql"]["fields"] if f["name"] == "sslmode")
    assert pg_ssl["options"] == ["require", "verify-full"]
    saved = su.get("/api/sources").json()["items"]
    api_src = next(x for x in saved if x["name"] == "API")
    res = su.post(f"/api/sources/{api_src['id']}/test").json()          # re-checked at test time
    assert res["ok"] is False and res["code"] == "not_allowed_in_profile"


def test_rest_headers_and_types(su):
    body = {"name": "Headers", "kind": "rest",
            "settings": {"base_url": "https://203.0.113.9", "auth": "none",
                         "headers": [{"name": "X-Tenant", "value": "mv", "secret": False},
                                     {"name": "X-Secret", "value": "hdr-secret-1",
                                      "secret": True}]},
            "secrets": {}}
    src = create(su, body)
    assert src["secret_fields"] == ["header:x-secret"]
    assert "hdr-secret-1" not in str(src)
    assert src["settings"]["headers"][1] == {"name": "X-Secret", "secret": True}
    bad = {**body, "name": "Bad", "settings": {**body["settings"],
                                               "headers": [{"name": "Host", "value": "x"}]}}
    assert su.post("/api/sources", json=bad).status_code == 422


def test_saved_test_records_result(su, monkeypatch):
    src = create(su)
    monkeypatch.setattr(service, "test_source",
                        lambda kind, s, sec, app: TestResult(False, "auth_failed"))
    r = su.post(f"/api/sources/{src['id']}/test")
    assert r.json()["code"] == "auth_failed"
    got = su.get(f"/api/sources/{src['id']}").json()["last_test"]
    assert got["ok"] is False and got["code"] == "auth_failed"


def test_legacy_import_once(db):
    s = get_settings()
    url = f"postgresql://legacy_user:{PW}@203.0.113.9:5433/erp?sslmode=prefer"
    object.__setattr__(s, "database_url_origin", url)
    try:
        assert service.import_legacy_origin(db, s) == "imported"
        db.commit()
        assert service.import_legacy_origin(db, s) == "skipped"
    finally:
        object.__setattr__(s, "database_url_origin", None)
    row = sql("SELECT name, settings, imported, secrets_ct FROM data_source")
    assert len(row) == 1
    name, settings, imported, ct = row[0]
    assert name == "Origen (importado)" and imported
    assert settings["database"] == "erp" and settings["port"] == 5433
    assert settings["sslmode"] == "prefer" and PW.encode() not in bytes(ct)
    assert "source_imported" in [k for (k,) in sql("SELECT kind FROM audit_event")]


def test_security_overview(su):
    body = su.get("/api/security").json()
    assert body["profile"] == "private" and body["http_allowed"] is True
    ids = {c["id"] for c in body["checks"]}
    assert {"https", "secret_key", "admin_mfa", "admin_networks", "key_rotation"} <= ids
    assert make_user("adm@example.com", role="admin")


def test_testing_unsaved_changes_uses_stored_secrets(su, monkeypatch):
    src = create(su)
    seen = {}

    def fake(kind, settings, secrets, app):
        seen.update(settings=settings, secrets=secrets)
        return TestResult(True)
    monkeypatch.setattr(service, "test_source", fake)
    r = su.post(f"/api/sources/{src['id']}/test",
                json={"settings": {**PG["settings"], "port": 6000}})
    assert r.json()["ok"] is True
    assert seen["settings"]["port"] == 6000 and seen["secrets"] == {"password": PW}
    assert su.get(f"/api/sources/{src['id']}").json()["last_test"] is None   # nothing saved
