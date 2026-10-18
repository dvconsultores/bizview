"""Feature 005 / US5: access tokens and `describe` (structure only, never values)."""
import json

import pytest

from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import extract
from app.models import AppUser
from app.security.netguard import Policy
from app.sources import service as sources
from app.sources.connectors import rest
from tests.conftest import TEST_SCHEMA, client, reauth, signed_in, sql
from tests.test_netguard import fake_dns
from tests.test_runner import origin as origin
from tests.test_runner import pg_source as pg_source
from tests.tls_helpers import StubServer


def new_token(c, name="portátil") -> dict:
    r = reauth(c).post("/api/tokens", json={"name": name, "scopes": ["describe"],
                                            "expires_days": 30})
    assert r.status_code == 201, r.text
    return r.json()


def bearer(token: str):
    c = client()
    c.headers["Authorization"] = f"Bearer {token}"
    return c


def test_token_shown_once_and_stored_hashed(superuser):
    c = signed_in("root@example.com")
    assert c.post("/api/tokens", json={"name": "x"}).status_code == 403   # step-up first
    t = new_token(c)
    assert t["token"].startswith("bzv_") and len(t["token"]) > 40
    listed = c.get("/api/tokens").json()["items"]
    assert listed[0]["name"] == "portátil" and "token" not in listed[0] and listed[0]["active"]
    stored = sql("SELECT token_hash FROM api_token")[0][0]
    assert t["token"].encode() not in bytes(stored)
    kinds = [k for (k,) in sql("SELECT kind FROM audit_event")]
    assert "token_created" in kinds


def test_tokens_are_super_user_only(superuser, admin):
    assert signed_in("admin@example.com").get("/api/tokens").status_code == 403
    assert client().get("/api/tokens").status_code == 401


def test_describe_postgresql_structure_without_values(superuser, origin):
    t = new_token(signed_in("root@example.com"))
    r = bearer(t["token"]).get("/api/sources/Origen%20prueba/describe")
    assert r.status_code == 200, r.text
    body = r.json()
    table = next(x for x in body["tables"] if x["schema"] == TEST_SCHEMA
                 and x["name"] == "origin_sales")
    assert [c["name"] for c in table["columns"]] == ["doc", "line", "kind", "completed_at",
                                                     "amount", "product"]
    assert table["columns"][4]["type"] == "numeric"
    text = r.text
    for value in ("A1", "OLD", "10.50", "P2"):
        assert f'"{value}"' not in text
    detail = sql("SELECT detail FROM audit_event WHERE kind = 'source_described'")[0][0]
    assert detail == {"source": "Origen prueba", "key_id": t["id"]}
    last_used = signed_in("root@example.com").get("/api/tokens").json()["items"][0]
    assert last_used["last_used_at"]


def test_token_grants_nothing_else(superuser, pg_source):
    t = new_token(signed_in("root@example.com"))
    c = bearer(t["token"])
    for path in ("/api/sources", "/api/me", "/api/tokens", "/api/workspace", "/api/dashboards"):
        assert c.get(path).status_code == 401, path


def test_revoked_expired_and_demoted_tokens_refused(superuser, pg_source):
    c = signed_in("root@example.com")
    t = new_token(c)
    path = "/api/sources/Origen%20prueba/describe"
    assert c.delete(f"/api/tokens/{t['id']}", headers={}).status_code == 204
    assert bearer(t["token"]).get(path).status_code == 401
    t2 = new_token(c, "otro")
    sql("UPDATE api_token SET expires_at = now() - interval '1 minute' WHERE id = :i", i=t2["id"])
    assert bearer(t2["token"]).get(path).status_code == 401
    assert bearer("bzv_wrong").get(path).status_code == 401
    t3 = new_token(c, "tercero")
    sql("UPDATE app_user SET is_superuser = false WHERE id = :i", i=superuser.id)
    assert bearer(t3["token"]).get(path).status_code == 401
    assert "token_revoked" in [k for (k,) in sql("SELECT kind FROM audit_event")]


def test_session_super_user_can_describe_but_unknown_source_404(superuser, pg_source):
    c = signed_in("root@example.com")
    assert c.get("/api/sources/No%20existe/describe").status_code == 404


@pytest.fixture
def rest_source(monkeypatch, superuser):
    def handler(h):
        body = json.dumps({"data": {"items": [{"id": 7, "name": "Secreto SA", "ok": True,
                                               "price": 1.5, "tags": ["vip"]}],
                                    "next": None}}).encode()
        h.send_response(200)
        h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)

    server = StubServer(handler)
    loop = Policy(allow_loopback_for_tests=True)
    from app.sources import describe as describer
    for mod in (extract, rest, describer):
        monkeypatch.setattr(mod, "policy_from_settings", lambda s: loop)
    with get_sessionmaker().begin() as db:
        sources.create(db, db.get(AppUser, superuser.id), {
            "name": "API", "kind": "rest",
            "settings": {"base_url": f"http://stub.test:{server.port}/v1", "auth": "none",
                         "headers": [], "timeout_seconds": 5}, "secrets": {}},
            get_settings(), None)
    fake_dns(monkeypatch, {"stub.test": ["127.0.0.1"]})
    yield server
    server.close()


def test_describe_rest_shape(rest_source):
    c = signed_in("root@example.com")
    r = c.get("/api/sources/API/describe", params={"path": "/customers"})
    assert r.status_code == 200, r.text
    assert r.json()["shape"] == {"data": {"items": [{"id": "integer", "name": "string",
                                                     "ok": "boolean", "price": "number",
                                                     "tags": ["string"]}], "next": "null"}}
    assert "Secreto" not in r.text
    assert rest_source.requests[0]["path"] == "/v1/customers"
    assert c.get("/api/sources/API/describe",
                 params={"path": "http://evil.test/x"}).status_code == 502
