"""Feature 004 / US1-US2: connectors against stubs and the Customer B origin (read-only)."""
import base64
import json
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

from app.config import Settings
from app.security import netguard
from app.security.netguard import Policy
from app.sources.connectors import postgresql, rest, soap
from app.sources.connectors import test_source as run_connector
from tests.test_netguard import fake_dns
from tests.tls_helpers import StubServer, TestCA, reply

APP = Settings(database_url_bi="postgresql://x@localhost/x", security_profile="private")
LOOP = Policy(allow_loopback_for_tests=True)


@pytest.fixture
def loopback(monkeypatch):
    """Stub servers listen on 127.0.0.1; allow it (tests only) and name it stub.test."""
    for mod in (rest, soap, postgresql):
        monkeypatch.setattr(mod, "policy_from_settings", lambda s: LOOP)
    fake_dns(monkeypatch, {"stub.test": ["127.0.0.1"]})


# --- REST -------------------------------------------------------------------------------------

def rest_settings(port, **kw):
    return {"base_url": f"http://stub.test:{port}/api", "test_path": "/ping", "auth": "none",
            "headers": [], "timeout_seconds": 5, **kw}


@pytest.mark.parametrize("auth,secrets,extra,check", [
    ("bearer", {"token": "tok-abc"}, {},
     lambda r: r["headers"].get("Authorization") == "Bearer tok-abc"),
    ("basic", {"password": "pw-1"}, {"username": "u"},
     lambda r: r["headers"].get("Authorization")
     == "Basic " + base64.b64encode(b"u:pw-1").decode()),
    ("api_key_header", {"api_key": "k-1"}, {"api_key_name": "X-Key"},
     lambda r: r["headers"].get("X-Key") == "k-1"),
    ("api_key_query", {"api_key": "k-2"}, {"api_key_name": "key"},
     lambda r: "key=k-2" in r["path"]),
])
def test_rest_auth_methods(loopback, auth, secrets, extra, check):
    server = StubServer(reply(200, b'{"ok":true}', {"content-type": "application/json"}))
    try:
        result = rest.test(rest_settings(server.port, auth=auth, **extra), secrets, APP)
        assert result.ok, result
        assert result.details == {"status": 200, "content_type": "application/json", "bytes": 11}
        assert check(server.requests[0])
        assert server.requests[0]["path"].startswith("/api/ping")
    finally:
        server.close()


def test_rest_oauth_client_credentials(loopback):
    def handler(h):
        if h.path == "/token":
            body = json.dumps({"access_token": "at-999", "token_type": "Bearer"}).encode()
            expected = "Basic " + base64.b64encode(b"cid:csecret").decode()
            ok = h.headers.get("Authorization") == expected
            reply(200 if ok else 401, body if ok else b"", {"content-type": "application/json"})(h)
        else:
            reply(200 if h.headers.get("Authorization") == "Bearer at-999" else 401)(h)
    server = StubServer(handler)
    try:
        s = rest_settings(server.port, auth="oauth2_client_credentials", client_id="cid",
                          token_url=f"http://stub.test:{server.port}/token", scope="read")
        assert rest.test(s, {"client_secret": "csecret"}, APP).ok
        assert b"grant_type=client_credentials" in server.requests[0]["body"]
        bad = rest.test(s, {"client_secret": "wrong"}, APP)
        assert (bad.ok, bad.code) == (False, "auth_failed") and "wrong" not in bad.message
    finally:
        server.close()


@pytest.mark.parametrize("status,code", [(401, "auth_failed"), (403, "auth_failed"),
                                         (404, "not_found"), (500, "invalid_response")])
def test_rest_status_mapping(loopback, status, code):
    server = StubServer(reply(status))
    try:
        assert rest.test(rest_settings(server.port), {}, APP).code == code
    finally:
        server.close()


def test_rest_redirect_not_followed(loopback):
    server = StubServer(reply(302, b"", {"location": "https://evil.example/collect"}))
    try:
        r = rest.test(rest_settings(server.port, auth="bearer"), {"token": "tok-zzz"}, APP)
        assert r.code == "invalid_response" and "evil.example" in r.message
        assert len(server.requests) == 1
    finally:
        server.close()


def test_rest_body_capped(loopback):
    server = StubServer(reply(200, b"x" * 3_000_000))
    try:
        assert rest.test(rest_settings(server.port), {}, APP).details["bytes"] == 1_000_000
    finally:
        server.close()


def test_rest_tls_with_private_ca(loopback):
    ca = TestCA()
    server = StubServer(reply(200), tls=ca.issue("stub.test"))
    try:
        s = rest_settings(server.port, base_url=f"https://stub.test:{server.port}")
        assert rest.test(s, {}, APP).code == "tls_error"            # unknown CA refused
        assert rest.test({**s, "ca_certificate": ca.pem}, {}, APP).ok
    finally:
        server.close()


def test_rest_blocked_by_default(monkeypatch):
    fake_dns(monkeypatch, {"stub.test": ["127.0.0.1"]})
    r = rest.test(rest_settings(9), {}, APP)
    assert r.code == "blocked_address"


def test_rest_http_refused_under_internet():
    internet = Settings(database_url_bi="postgresql://x@localhost/x", security_profile="internet",
                        site_address="bi.example.com")
    assert rest.test(rest_settings(9), {}, internet).code == "not_allowed_in_profile"


# --- SOAP -------------------------------------------------------------------------------------

WSDL = Path(__file__).with_name("fixtures") / "calculator.wsdl"


def soap_server(body: bytes, auth: str | None = None):
    def handler(h):
        if auth and h.headers.get("Authorization") != auth:
            reply(401)(h)
        else:
            reply(200, body, {"content-type": "text/xml"})(h)
    return StubServer(handler)


def soap_settings(port, **kw):
    return {"wsdl_url": f"http://stub.test:{port}/svc?wsdl", "auth": "none", "timeout_seconds": 5,
            **kw}


def test_soap_lists_operations_with_basic_auth(loopback):
    header = "Basic " + base64.b64encode(b"sap:pw-sap").decode()
    server = soap_server(WSDL.read_bytes(), auth=header)
    try:
        ok = soap.test(soap_settings(server.port, auth="basic", username="sap"),
                       {"password": "pw-sap"}, APP)
        assert ok.ok, ok
        ops = ok.details["services"][0]["ports"][0]["operations"]
        assert ops == ["Add", "Subtract"] and ok.details["operations"] == 2
        bad = soap.test(soap_settings(server.port, auth="basic", username="sap"),
                        {"password": "nope"}, APP)
        assert bad.code == "auth_failed"
    finally:
        server.close()


XXE = b"""<?xml version="1.0"?>
<!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/hostname">]>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/">&x;</definitions>"""
FILE_IMPORT = b"""<?xml version="1.0"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/" targetNamespace="urn:x">
  <import namespace="urn:y" location="file:///etc/passwd"/>
</definitions>"""


@pytest.mark.parametrize("payload", [XXE, FILE_IMPORT])
def test_soap_refuses_entities_and_local_files(loopback, payload):
    server = soap_server(payload)
    try:
        r = soap.test(soap_settings(server.port), {}, APP)
        assert r.ok is False and r.code == "invalid_response"
        assert "root:" not in r.message
    finally:
        server.close()


# --- PostgreSQL (Customer B origin, read-only) --------------------------------------------------

def origin_url() -> str | None:
    env = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    return os.environ.get("TEST_POSTGRES_SOURCE_URL") or env.get("DATABASE_URL_ORIGIN")


@pytest.mark.skipif(not origin_url(), reason="no origin URL available")
def test_postgresql_origin_read_only_checks():
    from urllib.parse import unquote, urlsplit
    u = urlsplit(origin_url())
    settings = {"host": u.hostname, "port": u.port or 5432, "database": u.path.strip("/"),
                "username": unquote(u.username or ""), "sslmode": "prefer", "timeout_seconds": 10}
    secrets = {"password": unquote(u.password or "")}
    result = run_connector("postgresql", settings, secrets, APP)
    assert result.ok, result
    assert result.details["server_version"].startswith("PostgreSQL")
    assert set(result.warnings) & {"superuser_account", "not_read_only"}   # account can write
    wrong = run_connector("postgresql", settings, {"password": "definitely-wrong"}, APP)
    assert wrong.code == "auth_failed" and "definitely-wrong" not in wrong.message
    closed = run_connector("postgresql", {**settings, "port": 1}, secrets, APP)
    assert closed.code in ("unreachable", "timeout")
    missing = run_connector("postgresql", {**settings, "database": "no_such_db_xyz"}, secrets, APP)
    assert missing.code == "not_found"


@pytest.mark.parametrize("message,code", [
    ('FATAL:  la autentificación password falló para el usuario «x»', "auth_failed"),
    ('FATAL:  password authentication failed for user "x"', "auth_failed"),
    ('FATAL:  no existe la base de datos «x»', "not_found"),
    ('FATAL:  database "x" does not exist', "not_found"),
    ('FATAL:  no existe el rol «x»', "auth_failed"),
    ('FATAL:  role "x" does not exist', "auth_failed"),
    ('connection timeout expired', "timeout"),
    ('SSL error: certificate verify failed', "tls_error"),
    ('Connection refused', "unreachable"),
])
def test_postgresql_error_classification_is_language_independent(message, code):
    assert postgresql._classify(Exception(message)) == code


def test_postgresql_blocked_and_profile():
    s = {"host": "127.0.0.1", "port": 5432, "database": "x", "username": "u",
         "sslmode": "require", "timeout_seconds": 2}
    assert postgresql.test(s, {"password": "p"}, APP).code == "blocked_address"
    internet = Settings(database_url_bi="postgresql://x@localhost/x", security_profile="internet",
                        site_address="bi.example.com")
    assert postgresql.test({**s, "sslmode": "disable"}, {"password": "p"}, internet).code == \
        "not_allowed_in_profile"


def test_netguard_used_by_all_connectors():
    assert netguard.guarded_client is rest.guarded_client is soap.guarded_client
