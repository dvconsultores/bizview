"""Feature 027: Google sign-in (invite-only linking, PKCE, second factor kept).

No test reaches the network: the token endpoint is an `httpx.MockTransport` installed on
`app.auth.google.client`.
"""
import base64
import json
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pyotp
import pytest
from fastapi.testclient import TestClient

from app.auth import google
from app.config import get_settings
from app.main import app
from tests.conftest import PASSWORD, make_user, reauth, signed_in, sql

CLIENT_ID = "bizview-test.apps.googleusercontent.com"
CLIENT_SECRET = "sb-client-secret-value"
SUB = "109876543210987654321"


def browser() -> TestClient:
    """Redirects are the contract here, so they are never followed."""
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


def claims(email: str, **over) -> dict:
    payload = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "exp": int(time.time()) + 300,
        "email": email,
        "email_verified": True,
        "sub": SUB,
        "hd": email.rsplit("@", 1)[-1],
    }
    payload.update(over)
    return payload


def token(payload: dict) -> str:
    def b64(value: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return f"{b64({'alg': 'RS256', 'kid': 'test'})}.{b64(payload)}.c2ln"


def install_token(monkeypatch, payload: dict | None, *, status: int = 200) -> dict:
    """A fake https://oauth2.googleapis.com/token that records what was sent."""
    seen: dict = {}

    def handle(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["form"] = parse_qs(request.content.decode())
        if status != 200 or payload is None:
            return httpx.Response(status, json={"error": "invalid_client"})
        return httpx.Response(200, json={"id_token": token(payload)})

    def factory() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handle), timeout=5.0)

    monkeypatch.setattr(google, "client", factory)
    return seen


def start(c: TestClient):
    return c.get("/api/auth/google/start")


def begin(c: TestClient) -> str:
    response = start(c)
    assert response.status_code == 302, response.text
    return parse_qs(urlsplit(response.headers["location"]).query)["state"][0]


def callback(c: TestClient, *, state: str | None = None, code: str | None = "auth-code",
             error: str | None = None):
    params = {}
    if state is not None:
        params["state"] = state
    if code is not None:
        params["code"] = code
    if error is not None:
        params["error"] = error
    return c.get("/api/auth/google/callback", params=params)


def assert_password_still_works(email: str) -> None:
    c = TestClient(app, headers={"X-Requested-With": "fetch"})
    r = c.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text


def sessions() -> int:
    return sql("SELECT count(*) FROM user_session")[0][0]


# --- disabled by default (SC-001) -------------------------------------------------------------

def test_disabled_refuses_start_and_config():
    c = browser()
    assert c.get("/api/config").json()["google_auth"] is False
    r = start(c)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    assert "bv_google" not in c.cookies


def test_incomplete_client_is_reported_as_disabled(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "google_auth_enabled", True)
    monkeypatch.setattr(s, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(s, "google_client_secret", None)
    assert browser().get("/api/config").json()["google_auth"] is False
    assert start(browser()).status_code == 404


# --- start (FR-003, FR-004) -------------------------------------------------------------------

def test_enabled_config_and_start_redirect(user, google_on):
    assert browser().get("/api/config").json()["google_auth"] is True
    c = browser()
    r = start(c)
    assert r.status_code == 302
    url = urlsplit(r.headers["location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == \
        "https://accounts.google.com/o/oauth2/v2/auth"
    q = parse_qs(url.query)
    assert q["client_id"] == [CLIENT_ID]
    assert q["redirect_uri"] == ["https://bi.example.com/api/auth/google/callback"]
    assert q["response_type"] == ["code"]
    assert q["scope"] == ["openid email profile"]
    assert q["code_challenge_method"] == ["S256"]
    assert q["prompt"] == ["select_account"]
    assert q["state"] and q["code_challenge"]
    assert CLIENT_SECRET not in r.headers["location"]
    cookie = r.headers["set-cookie"]
    assert "bv_google=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Max-Age=600" in cookie


def test_redirect_uri_override_and_site_derivation(google_on, monkeypatch):
    assert google_on.google_redirect_uri_effective == \
        "https://bi.example.com/api/auth/google/callback"
    monkeypatch.setattr(google_on, "google_redirect_uri", "https://otro.example/x")
    assert google_on.google_redirect_uri_effective == "https://otro.example/x"


# --- callback refusals (FR-004, SC-005) -------------------------------------------------------

def test_callback_without_state_cookie_is_refused(google_on):
    c = browser()
    r = callback(c, state="forged-state")
    assert r.status_code == 302
    assert r.headers["location"] == "/ingresar?google_error=state"
    assert sessions() == 0
    assert "sid" not in c.cookies


def test_callback_state_mismatch_is_refused(user, google_on, monkeypatch):
    install_token(monkeypatch, claims(user.email))
    c = browser()
    begin(c)
    r = callback(c, state="a-different-state")
    assert r.headers["location"] == "/ingresar?google_error=state"
    assert sessions() == 0
    assert "bv_google" not in c.cookies
    assert sql("SELECT count(*) FROM google_link")[0][0] == 0
    assert_password_still_works(user.email)


def test_callback_disabled_after_start(user, google_on, monkeypatch):
    install_token(monkeypatch, claims(user.email))
    c = browser()
    state = begin(c)
    monkeypatch.setattr(get_settings(), "google_auth_enabled", False)
    r = callback(c, state=state)
    assert r.headers["location"] == "/ingresar?google_error=disabled"
    assert sessions() == 0
    assert "bv_google" not in c.cookies


def test_denied_and_provider_failures(user, google_on, monkeypatch):
    c = browser()
    r = callback(c, state=begin(c), code=None, error="access_denied")
    assert r.headers["location"] == "/ingresar?google_error=denied"

    c = browser()
    r = callback(c, state=begin(c), error="server_error")
    assert r.headers["location"] == "/ingresar?google_error=provider"

    install_token(monkeypatch, None, status=400)     # wrong secret, expired or reused code
    c = browser()
    r = callback(c, state=begin(c))
    assert r.headers["location"] == "/ingresar?google_error=provider"
    assert sessions() == 0
    assert [d for (d,) in sql("SELECT detail FROM audit_event "
                              "WHERE kind = 'google_sign_in_refused'")]
    assert_password_still_works(user.email)


# --- successful flow (US1, FR-006, FR-008, FR-009) --------------------------------------------

def test_successful_flow_links_and_signs_in(user, google_on, monkeypatch):
    seen = install_token(monkeypatch, claims(user.email))
    c = browser()
    r = callback(c, state=begin(c))
    assert r.status_code == 302
    assert r.headers["location"] == "/"
    assert "sid=" in r.headers["set-cookie"]
    assert "bv_google" not in c.cookies
    assert sql("SELECT google_sub, email FROM google_link WHERE user_id = :i",
               i=user.id) == [(SUB, "user@example.com")]
    assert seen["url"] == "https://oauth2.googleapis.com/token"
    assert seen["form"]["grant_type"] == ["authorization_code"]
    assert seen["form"]["code"] == ["auth-code"]
    assert seen["form"]["client_id"] == [CLIENT_ID]
    assert seen["form"]["client_secret"] == [CLIENT_SECRET]
    assert seen["form"]["redirect_uri"] == ["https://bi.example.com/api/auth/google/callback"]
    assert seen["form"]["code_verifier"][0]
    kinds = [k for (k,) in sql("SELECT kind FROM audit_event")]
    assert kinds.count("google_linked") == 1 and kinds.count("google_sign_in") == 1
    assert c.get("/api/me").status_code == 200          # an ordinary session, like any other


def test_second_flow_reuses_the_link(user, google_on, monkeypatch):
    install_token(monkeypatch, claims(user.email))
    c = browser()
    assert callback(c, state=begin(c)).headers["location"] == "/"
    assert callback(c, state=begin(c)).headers["location"] == "/"
    assert sql("SELECT count(*) FROM google_link")[0][0] == 1


def test_email_change_keeps_the_link_by_subject(user, google_on, monkeypatch):
    install_token(monkeypatch, claims(user.email))
    c = browser()
    callback(c, state=begin(c))
    install_token(monkeypatch, claims("renamed@example.com"))     # same sub, new address
    r = callback(c, state=begin(c))
    assert r.headers["location"] == "/"
    assert sql("SELECT google_sub, email FROM google_link") == [(SUB, "renamed@example.com")]
    assert sql("SELECT count(*) FROM google_link")[0][0] == 1


# --- invite-only linking (FR-007, SC-003) -----------------------------------------------------

def test_unknown_email_is_refused_and_creates_nothing(google_on, monkeypatch):
    install_token(monkeypatch, claims("stranger@example.com"))
    before = sql("SELECT count(*) FROM app_user")[0][0]
    c = browser()
    r = callback(c, state=begin(c))
    assert r.headers["location"] == "/ingresar?google_error=unknown_identity"
    assert sql("SELECT count(*) FROM app_user")[0][0] == before
    assert sql("SELECT count(*) FROM google_link")[0][0] == 0
    assert sessions() == 0


def test_inactive_user_is_refused(google_on, monkeypatch):
    make_user("off@example.com", active=False)
    install_token(monkeypatch, claims("off@example.com"))
    c = browser()
    r = callback(c, state=begin(c))
    assert r.headers["location"] == "/ingresar?google_error=inactive"
    assert sql("SELECT count(*) FROM google_link")[0][0] == 0
    assert sessions() == 0
    assert sql("SELECT is_active FROM app_user")[0][0] is False       # never promoted


def test_locked_user_is_refused(user, google_on, monkeypatch):
    sql("UPDATE app_user SET locked_until = now() + interval '10 minutes' WHERE id = :i",
        i=user.id)
    install_token(monkeypatch, claims(user.email))
    c = browser()
    r = callback(c, state=begin(c))
    assert r.headers["location"] == "/ingresar?google_error=inactive"
    assert sql("SELECT count(*) FROM google_link")[0][0] == 0
    assert sessions() == 0


def test_allowed_domains(google_on, monkeypatch):
    monkeypatch.setattr(google_on, "google_allowed_domains", "@otra.com, ejemplo.com")
    make_user("user@example.com", full_name="Ulises Usuario")
    install_token(monkeypatch, claims("user@example.com"))
    c = browser()
    r = callback(c, state=begin(c))
    assert r.headers["location"] == "/ingresar?google_error=domain"
    assert sessions() == 0

    monkeypatch.setattr(google_on, "google_allowed_domains", "otra.com ejemplo.com")
    install_token(monkeypatch, claims("ana@ejemplo.com"))
    make_user("ana@ejemplo.com")
    c = browser()
    assert callback(c, state=begin(c)).headers["location"] == "/"
    assert sql("SELECT count(*) FROM google_link")[0][0] == 1


# --- claim validation (FR-005) ----------------------------------------------------------------

@pytest.mark.parametrize("overrides", [
    {"aud": "some-other-client.apps.googleusercontent.com"},
    {"iss": "https://evil.example.com"},
    {"exp": 1_000_000},
    {"email_verified": False},
    {"email_verified": "true"},
    {"sub": ""},
])
def test_bad_claims_are_refused(user, google_on, monkeypatch, overrides):
    install_token(monkeypatch, claims(user.email, **overrides))
    c = browser()
    r = callback(c, state=begin(c))
    assert r.headers["location"] == "/ingresar?google_error=provider"
    assert sessions() == 0
    assert sql("SELECT count(*) FROM google_link")[0][0] == 0
    assert_password_still_works(user.email)


# --- the second factor survives (US2, SC-004) -------------------------------------------------

def test_internet_admin_still_needs_the_second_factor(admin, google_on, monkeypatch):
    c = signed_in(admin.email)
    reauth(c)
    setup = c.post("/api/me/mfa/setup").json()
    r = c.post("/api/me/mfa/enable", json={"code": pyotp.TOTP(setup["secret"]).now()})
    assert r.status_code == 200, r.text

    s = google_on
    monkeypatch.setattr(s, "security_profile", "internet")
    install_token(monkeypatch, claims(admin.email))

    c = browser()
    r = callback(c, state=begin(c))
    assert r.status_code == 302
    assert r.headers["location"] == "/ingresar?mfa=1"
    assert "sid=" in r.headers["set-cookie"]
    assert sql("SELECT count(*) FROM user_session WHERE mfa_pending")[0][0] == 1
    assert c.get("/api/reports/ventas/data").status_code == 401
    assert c.get("/api/me").status_code == 401
    assert_password_still_works(admin.email)


def test_internet_admin_without_mfa_may_only_enroll(admin, google_on, monkeypatch):
    monkeypatch.setattr(google_on, "security_profile", "internet")
    install_token(monkeypatch, claims(admin.email))
    c = browser()
    r = callback(c, state=begin(c))
    assert r.headers["location"] == "/ingresar?mfa=1"
    assert c.get("/api/reports/ventas/data").status_code == 401
    assert c.get("/api/admin/users").status_code == 401


# --- the forced password change is not bypassed (architect) -----------------------------------

def test_must_change_password_survives_google_sign_in(google_on, monkeypatch):
    invited = make_user("invited@example.com", must_change=True)
    install_token(monkeypatch, claims(invited.email))
    c = browser()
    assert callback(c, state=begin(c)).headers["location"] == "/"

    me = c.get("/api/me")
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True
    r = c.get("/api/reports/ventas/data")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "password_change_required"

    # Linking: the forced change is untouched by linking an identity.
    assert sql("SELECT must_change_password FROM app_user WHERE id = :i",
               i=invited.id)[0][0] is True
    assert sql("SELECT count(*) FROM google_link WHERE user_id = :i",
               i=invited.id)[0][0] == 1

    changed = c.post("/api/me/password", json={"current_password": PASSWORD,
                                               "new_password": "Otra-clave-larga-7"})
    assert changed.status_code == 204, changed.text
    assert c.get("/api/me").json()["must_change_password"] is False
    assert c.get("/api/reports/ventas/data").status_code not in (401, 403)

