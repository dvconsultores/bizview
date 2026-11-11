"""Feature 054: the Google policy — domains from the card, alta automática and role rules.

No test reaches the network: the token endpoint is an `httpx.MockTransport` installed on
`app.auth.google.client`, exactly as feature 027's suite does.
"""
import base64
import json
import time
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import google
from app.config import get_settings
from app.main import app
from app.services import google_policy as policy
from tests.conftest import make_user, reauth, signed_in, sql

CLIENT_ID = "bizview-test.apps.googleusercontent.com"
CLIENT_SECRET = "sb-client-secret-value"
SUB = "109876543210987654321"


def browser() -> TestClient:
    return TestClient(app, headers={"X-Requested-With": "fetch"}, follow_redirects=False)


@pytest.fixture
def google_on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "google_auth_enabled", True)
    monkeypatch.setattr(s, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(s, "google_client_secret", CLIENT_SECRET)
    monkeypatch.setattr(s, "google_allowed_domains", None)
    monkeypatch.setattr(s, "google_redirect_uri", None)
    monkeypatch.setattr(s, "site_address", "bi.example.com")
    return s


def identity(**over) -> dict:
    payload = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "exp": int(time.time()) + 300,
        "email": "persona@example.org",
        "email_verified": True,
        "sub": SUB,
        "name": "Persona Nueva",
        "hd": "example.org",
    }
    payload.update(over)
    return payload


def fake_exchange(monkeypatch, payload: dict) -> None:
    """Answer the token endpoint with an ID token carrying `payload`."""

    def b64(value: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    def handle(request: httpx.Request) -> httpx.Response:
        parse_qs(request.content.decode())          # the form is built, not asserted here
        token = f"{b64({'alg': 'RS256'})}.{b64(payload)}.c2ln"
        return httpx.Response(200, json={"id_token": token})

    monkeypatch.setattr(
        google, "client",
        lambda: httpx.Client(transport=httpx.MockTransport(handle), timeout=5.0),
    )


def sign_in_with_google(monkeypatch, payload: dict) -> httpx.Response | TestClient:
    """Run the whole flow: start (sets the state cookie) then the callback."""
    fake_exchange(monkeypatch, payload)
    c = browser()
    start = c.get("/api/auth/google/start")
    assert start.status_code == 302, start.text
    path = start.headers["location"]
    from urllib.parse import urlsplit
    state = parse_qs(urlsplit(path).query)["state"][0]
    return c.get(f"/api/auth/google/callback?code=fake&state={state}")


def google_session(monkeypatch, payload: dict) -> TestClient:
    """The same flow, keeping the client so the session it opened can be inspected."""
    fake_exchange(monkeypatch, payload)
    c = browser()
    from urllib.parse import urlsplit

    start = c.get("/api/auth/google/start")
    assert start.status_code == 302, start.text
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    landed = c.get(f"/api/auth/google/callback?code=fake&state={state}")
    assert landed.headers["location"] == "/", landed.headers["location"]
    return c


# --- Settings: the card writes what the callback reads ---------------------------------------

def test_domains_come_from_env_until_the_card_saves(superuser, google_on, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_allowed_domains", "example.com, @acme.io")
    c = reauth(signed_in("root@example.com"))
    body = c.get("/api/admin/google").json()
    assert body["settings"]["allowed_domains"] == ["example.com", "acme.io"]
    assert body["settings"]["domains_from_env"] is True
    assert body["settings"]["auto_provision"] is False
    assert body["settings"]["default_role"] == "user"
    assert body["settings"]["default_access"] == {"mode": "none"}


def test_a_mis_typed_env_value_is_reported_and_never_opens_the_door(superuser, google_on,
                                                                  monkeypatch):
    """T030: `GOOGLE_ALLOWED_DOMAINS` is a seed, not a licence. A URL in it used to show up as a
    domain, refuse everybody (`domain_not_allowed`) and look like a working policy."""
    monkeypatch.setattr(get_settings(), "google_allowed_domains",
                        "https://www.getbizview.com; getbizview.com")
    c = reauth(signed_in("root@example.com"))
    body = c.get("/api/admin/google").json()["settings"]
    assert body["allowed_domains"] == ["getbizview.com"]           # the usable half survives
    assert body["domains_rejected"] == ["https://www.getbizview.com;"]

    # Only rejects: the list is not "empty means any" — it admits nobody until it is saved.
    monkeypatch.setattr(get_settings(), "google_allowed_domains", "https://www.getbizview.com;")
    body = c.get("/api/admin/google").json()["settings"]
    assert body["allowed_domains"] == [] and body["domains_rejected"]
    monkeypatch.setattr(get_settings(), "google_allowed_domains", "")
    assert c.get("/api/admin/google").json()["settings"]["domains_rejected"] == []


def test_saving_domains_overrides_env_and_is_audited(superuser, google_on, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_allowed_domains", "example.com")
    c = reauth(signed_in("root@example.com"))
    saved = c.put("/api/admin/google", json={
        "allowed_domains": ["@Example.ORG", "example.org"],
        "auto_provision": True,
        "default_role": "user",
        "default_access": {"mode": "none"},
        "apply_rules_to_existing": False,
    })
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["settings"]["allowed_domains"] == ["example.org"]   # normalised and deduplicated
    assert body["settings"]["domains_from_env"] is False
    audit = sql("select detail from audit_event where kind = 'google_settings_updated'")
    assert audit and audit[0][0]["before"]["allowed_domains"] == ["example.com"]
    assert audit[0][0]["after"]["allowed_domains"] == ["example.org"]


def test_settings_validation(superuser, google_on):
    c = reauth(signed_in("root@example.com"))
    bad_role = c.put("/api/admin/google", json={
        "allowed_domains": ["example.org"], "default_role": "superuser"})
    assert bad_role.status_code == 422
    bad_domain = c.put("/api/admin/google", json={"allowed_domains": ["no es un dominio"]})
    assert bad_domain.status_code == 422
    unknown_dashboard = c.put("/api/admin/google", json={
        "allowed_domains": [], "default_access": {"mode": "list", "codes": ["nope"]}})
    assert unknown_dashboard.status_code == 422


def test_admin_endpoints_need_the_superuser_and_a_step_up(admin, google_on):
    c = signed_in("admin@example.com")
    assert c.get("/api/admin/google").status_code == 403


def test_rules_are_ordered_and_first_match_wins(superuser, google_on):
    c = reauth(signed_in("root@example.com"))
    domain = c.post("/api/admin/google/rules", json={
        "condition": "domain", "value": ["example.org"], "role": "admin",
        "access": {"mode": "all_public"}})
    assert domain.status_code == 201, domain.text
    email = c.post("/api/admin/google/rules", json={
        "condition": "email", "value": ["cfo@example.org"], "role": "user",
        "access": {"mode": "none"}})
    assert email.status_code == 201, email.text

    from app.db import get_sessionmaker
    with get_sessionmaker()() as db:
        first = policy.matching_rule(db, "cfo@example.org")
        assert first is not None and first.condition == "email"      # inserted at the top
        other = policy.matching_rule(db, "otra@example.org")
        assert other is not None and other.condition == "domain"

        # Swapping the order swaps the outcome (SC-004).
        ids = [r.id for r in policy.list_rules(db)]
        policy.reorder_rules(db, _superuser(), [ids[1], ids[0]], None)
        first = policy.matching_rule(db, "cfo@example.org")
        assert first is not None and first.condition == "domain"
        db.rollback()


def _superuser():
    from sqlalchemy import select

    from app.db import get_sessionmaker
    from app.models import AppUser

    with get_sessionmaker()() as db:
        return db.scalar(select(AppUser).where(AppUser.is_superuser.is_(True)))


def test_rule_validation_refuses_superuser_and_group(superuser, google_on):
    c = reauth(signed_in("root@example.com"))
    role = c.post("/api/admin/google/rules", json={
        "condition": "domain", "value": ["example.org"], "role": "superuser"})
    assert role.status_code == 422
    assert role.json()["error"]["fields"]["role"]
    group = c.post("/api/admin/google/rules", json={
        "condition": "group", "value": ["eng"], "role": "user"})
    assert group.status_code == 422
    assert group.json()["error"]["fields"]["condition"]


def test_deleting_a_rule_keeps_positions_contiguous(superuser, google_on):
    c = reauth(signed_in("root@example.com"))
    for domain in ("a.org", "b.org", "c.org"):
        c.post("/api/admin/google/rules", json={
            "condition": "domain", "value": [domain], "role": "user",
            "access": {"mode": "none"}})
    items = c.get("/api/admin/google/rules").json()["items"]
    assert [item["position"] for item in items] == [0, 1, 2]
    c.delete(f"/api/admin/google/rules/{items[1]['id']}")
    items = c.get("/api/admin/google/rules").json()["items"]
    assert [item["position"] for item in items] == [0, 1]


# --- Provisioning -----------------------------------------------------------------------------

def test_auto_provision_creates_one_user_with_the_defaults(superuser, google_on, monkeypatch):
    c = reauth(signed_in("root@example.com"))
    dashboard = sql("select code from dashboard where status = 'available' limit 1")
    codes = [row[0] for row in dashboard]
    c.put("/api/admin/google", json={
        "allowed_domains": ["example.org"], "auto_provision": True, "default_role": "user",
        "default_access": {"mode": "list", "codes": codes}})

    first = sign_in_with_google(monkeypatch, identity())
    assert first.status_code in (302, 307), first.text
    assert first.headers["location"] == "/"

    rows = sql("select id, email, role, auth_provider, password_hash, is_active, "
               "must_change_password from app_user where email = 'persona@example.org'")
    assert len(rows) == 1
    user_id, _email, role, provider, password_hash, active, must_change = rows[0]
    assert (role, provider, password_hash, active, must_change) == \
        ("user", "google", None, True, False)
    granted = sql("select dashboard.code from dashboard_access join dashboard "
                  "on dashboard.id = dashboard_access.dashboard_id where user_id = :u",
                  u=user_id)
    assert sorted(row[0] for row in granted) == sorted(codes)

    # A second sign-in reuses the account (same subject) and creates nothing.
    again = sign_in_with_google(monkeypatch, identity())
    assert again.status_code in (302, 307)
    assert len(sql("select id from app_user where email = 'persona@example.org'")) == 1


def test_an_admin_is_provisioned_without_explicit_grants(superuser, google_on, monkeypatch):
    """T031: the access value is for `user` accounts; an admin sees the whole catalogue by role."""
    c = reauth(signed_in("root@example.com"))
    codes = [row[0] for row in sql("select code from dashboard where status = 'available' limit 1")]
    c.put("/api/admin/google", json={
        "allowed_domains": ["example.org"], "auto_provision": True, "default_role": "admin",
        "default_access": {"mode": "list", "codes": codes}})

    assert sign_in_with_google(monkeypatch, identity()).status_code in (302, 307)
    row = sql("select id, role from app_user where email = 'persona@example.org'")[0]
    assert row[1] == "admin"
    assert sql("select dashboard_id from dashboard_access where user_id = :u", u=row[0]) == []
    detail = sql("select detail from audit_event where kind = 'google_user_provisioned'")[0][0]
    assert detail["dashboards"] == []


def test_a_foreign_domain_is_refused_generically_and_audited(superuser, google_on, monkeypatch):
    c = reauth(signed_in("root@example.com"))
    c.put("/api/admin/google", json={"allowed_domains": ["example.org"], "auto_provision": True})
    refused = sign_in_with_google(monkeypatch, identity(email="ajeno@otro.com"))
    assert refused.headers["location"] == "/ingresar?google_error=domain_not_allowed"
    assert sql("select id from app_user where email = 'ajeno@otro.com'") == []
    detail = sql("select detail from audit_event where kind = 'google_sign_in_refused'")
    assert detail[0][0]["reason"] == "domain_not_allowed"


def test_provisioning_off_refuses_an_unknown_account(google_on, monkeypatch):
    refused = sign_in_with_google(monkeypatch, identity())
    assert refused.headers["location"] == "/ingresar?google_error=no_user"
    assert sql("select id from app_user where email = 'persona@example.org'") == []


def test_a_provisioned_account_cannot_use_the_password_form(superuser, google_on, monkeypatch):
    c = reauth(signed_in("root@example.com"))
    c.put("/api/admin/google", json={"allowed_domains": ["example.org"], "auto_provision": True})
    sign_in_with_google(monkeypatch, identity())

    attempt = TestClient(app, headers={"X-Requested-With": "fetch"}).post(
        "/api/auth/login", json={"email": "persona@example.org", "password": "cualquiera"})
    assert attempt.status_code == 401
    assert attempt.json()["error"]["code"] == "invalid_credentials"
    detail = sql("select detail from audit_event where kind = 'login_failed' "
                 "and detail ? 'no_credential'")
    assert detail


def test_an_admin_creates_an_account_for_google_only(superuser, google_on, monkeypatch):
    """Convergence 054b: no password, no temporary flag, Google works and the form is refused."""
    c = signed_in("root@example.com")
    made = c.post("/api/admin/users", json={
        "email": "google.only@example.org", "full_name": "Solo Google", "role": "user"})
    assert made.status_code == 201, made.text
    body = made.json()
    assert (body["has_password"], body["auth_provider"], body["must_change_password"]) == \
        (False, "google", False)
    assert sql("select password_hash, must_change_password, auth_provider from app_user "
               "where email = 'google.only@example.org'") == [(None, False, "google")]
    assert "user_created_without_password" in [
        k for (k,) in sql("select kind from audit_event")]

    attempt = TestClient(app, headers={"X-Requested-With": "fetch"}).post(
        "/api/auth/login", json={"email": "google.only@example.org", "password": "cualquiera"})
    assert attempt.status_code == 401
    assert attempt.json()["error"]["code"] == "invalid_credentials"

    signed = google_session(monkeypatch, identity(email="google.only@example.org"))
    me = signed.get("/api/me")
    assert me.status_code == 200
    assert me.json()["has_password"] is False
    assert me.json()["must_change_password"] is False

    # The administrator can add a password later: from then on the temporary flag rules apply.
    user_id = sql("select id from app_user where email = 'google.only@example.org'")[0][0]
    reset = c.post(f"/api/admin/users/{user_id}/password",
                   json={"temporary_password": "Temporal-pass-91"})
    assert reset.status_code == 204, reset.text
    pw = TestClient(app, headers={"X-Requested-With": "fetch"}).post(
        "/api/auth/login", json={"email": "google.only@example.org",
                                 "password": "Temporal-pass-91"})
    assert pw.status_code == 200
    assert pw.json()["user"]["must_change_password"] is True
    again = google_session(monkeypatch, identity(email="google.only@example.org"))
    assert again.get("/api/me").json()["must_change_password"] is False


def test_an_admin_gives_a_provisioned_account_its_password(superuser, google_on, monkeypatch):
    """FR-012: the existing reset is the only way in — hash written, change forced, link kept."""
    c = reauth(signed_in("root@example.com"))
    c.put("/api/admin/google", json={"allowed_domains": ["example.org"], "auto_provision": True})
    sign_in_with_google(monkeypatch, identity())
    user_id = sql("select id from app_user where email = 'persona@example.org'")[0][0]

    reset = c.post(f"/api/admin/users/{user_id}/password",
                   json={"temporary_password": "Temporal-pass-91"})
    assert reset.status_code == 204, reset.text
    assert sql("select password_hash is not null from app_user where id = :u", u=user_id)[0][0]

    pw = browser()
    first = pw.post("/api/auth/login", json={
        "email": "persona@example.org", "password": "Temporal-pass-91"})
    assert first.status_code == 200, first.text
    assert first.json()["user"]["must_change_password"] is True
    # The reset forces the change: the session may reach nothing else until it happens.
    blocked = pw.get("/api/dashboards")
    assert blocked.json()["error"]["code"] == "password_change_required"
    # The Google link is untouched: the same account signs in with Google again.
    again = sign_in_with_google(monkeypatch, identity())
    assert again.status_code in (302, 307)
    assert len(sql("select id from app_user where email = 'persona@example.org'")) == 1


def test_rules_apply_to_new_accounts_and_never_to_superusers(superuser, google_on, monkeypatch):
    c = reauth(signed_in("root@example.com"))
    c.put("/api/admin/google", json={"allowed_domains": ["example.org"], "auto_provision": True,
                                     "default_role": "user"})
    c.post("/api/admin/google/rules", json={
        "condition": "email", "value": ["jefa@example.org"], "role": "admin",
        "access": {"mode": "none"}})

    sign_in_with_google(monkeypatch, identity(email="jefa@example.org", sub="sub-jefa"))
    role = sql("select role from app_user where email = 'jefa@example.org'")
    assert role[0][0] == "admin"


def test_existing_users_keep_their_role_unless_the_toggle_is_on(superuser, google_on,
                                                                monkeypatch):
    make_user("existente@example.org", role="user")
    c = reauth(signed_in("root@example.com"))
    c.put("/api/admin/google", json={"allowed_domains": ["example.org"], "auto_provision": False,
                                     "apply_rules_to_existing": False})
    c.post("/api/admin/google/rules", json={
        "condition": "domain", "value": ["example.org"], "role": "admin",
        "access": {"mode": "none"}})

    sign_in_with_google(monkeypatch, identity(email="existente@example.org"))
    assert sql("select role from app_user where email = 'existente@example.org'")[0][0] == "user"
    assert sql("select id from audit_event where kind = 'google_rule_applied'") == []

    c.put("/api/admin/google", json={"allowed_domains": ["example.org"], "auto_provision": False,
                                     "apply_rules_to_existing": True})
    sign_in_with_google(monkeypatch, identity(email="existente@example.org"))
    assert sql("select role from app_user where email = 'existente@example.org'")[0][0] == "admin"
    applied = sql("select detail from audit_event where kind = 'google_rule_applied'")
    assert applied and applied[0][0]["rule"] is not None


def test_a_rule_never_touches_the_superuser(superuser, google_on, monkeypatch):
    c = reauth(signed_in("root@example.com"))
    c.put("/api/admin/google", json={"allowed_domains": ["example.org"], "auto_provision": False,
                                     "apply_rules_to_existing": True})
    c.post("/api/admin/google/rules", json={
        "condition": "email", "value": ["root@example.com"], "role": "user",
        "access": {"mode": "none"}})
    sign_in_with_google(monkeypatch, identity(email="root@example.com", sub="sub-root"))
    row = sql("select role, is_superuser from app_user where email = 'root@example.com'")
    assert row[0][0] == "admin" and row[0][1] is True
