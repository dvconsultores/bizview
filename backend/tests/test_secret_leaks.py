"""Feature 004, SC-001: no credential appears in API responses, logs, audit rows, or table data."""
import logging
import time

import pyotp

from app.sources import service
from tests.conftest import TEST_SCHEMA, reauth, signed_in, sql

MARKERS = ["Mk-PgPass-7a1", "Mk-Token-9b2", "Mk-Header-3c4", "Mk-ClientSecret-5d6"]


def test_no_credential_leaks_anywhere(superuser, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    su = reauth(signed_in(superuser.email))
    responses = []

    def call(method, path, **kw):
        r = su.request(method, path, **kw)
        responses.append(r.text)
        return r

    pg = call("POST", "/api/sources", json={
        "name": "PG", "kind": "postgresql",
        "settings": {"host": "203.0.113.9", "database": "d", "username": "u"},
        "secrets": {"password": MARKERS[0]}}).json()
    rest = call("POST", "/api/sources", json={
        "name": "REST", "kind": "rest",
        "settings": {"base_url": "https://203.0.113.9/api", "auth": "oauth2_client_credentials",
                     "token_url": "https://203.0.113.9/token", "client_id": "cid",
                     "headers": [{"name": "X-Key", "value": MARKERS[2], "secret": True}]},
        "secrets": {"client_secret": MARKERS[3]}}).json()
    call("PATCH", f"/api/sources/{rest['id']}",
         json={"settings": {**rest["settings"], "auth": "bearer"},
               "secrets": {"token": MARKERS[1]}})

    # A connector error echoing the credential must be redacted before it is stored/returned.
    from app.sources.connectors import base

    def leaky(kind, settings, secrets, app):
        detail = f"server said: bad password {secrets.get('password')}"
        return base.fail("auth_failed", detail, secrets)
    monkeypatch.setattr(service, "test_source", leaky)
    call("POST", f"/api/sources/{pg['id']}/test")
    for path in ("/api/sources", f"/api/sources/{pg['id']}", f"/api/sources/{rest['id']}",
                 "/api/security", "/api/admin/audit?limit=100", "/api/me"):
        call("GET", path)

    # Two-step sign-in secret
    setup = call("POST", "/api/me/mfa/setup").json()
    totp_secret = setup.pop("secret")
    call("POST", "/api/me/mfa/enable", json={"code": pyotp.TOTP(totp_secret).at(time.time())})
    responses = [r.replace(totp_secret, "") if "otpauth" in r else r for r in responses]

    everything = "\n".join(responses) + "\n" + caplog.text
    tables = [t for (t,) in sql("SELECT table_name FROM information_schema.tables "
                                "WHERE table_schema = :s", s=TEST_SCHEMA)]
    for table in tables:
        rows = sql(f'SELECT row_to_json(x)::text FROM "{table}" x')
        everything += "\n".join(str(r[0]) for r in rows)
    for marker in [*MARKERS, totp_secret]:
        assert marker not in everything, f"{marker!r} leaked"
