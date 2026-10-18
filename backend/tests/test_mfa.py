"""Feature 004 / US3: two-step sign-in, pending sessions, recovery codes (FR-017 - FR-019)."""
import time

import pyotp
import pytest

from app import cli
from app.config import get_settings
from app.security import mfa
from tests.conftest import PASSWORD, client, make_user, reauth, signed_in, sql

T0 = 1_900_000_020.0  # fixed clock: step boundaries are predictable


@pytest.fixture
def clock(monkeypatch):
    now = {"t": T0}
    monkeypatch.setattr(mfa.time, "time", lambda: now["t"])
    return now


def code(secret: str, t: float) -> str:
    return pyotp.TOTP(secret).at(t)


def enroll(c, email_password=PASSWORD, t=T0) -> tuple[str, list[str]]:
    reauth(c, email_password)
    setup = c.post("/api/me/mfa/setup").json()
    assert setup["qr_svg"].startswith("data:image/svg+xml")
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    r = c.post("/api/me/mfa/enable", json={"code": code(setup["secret"], t)})
    assert r.status_code == 200, r.text
    return setup["secret"], r.json()["recovery_codes"]


def test_setup_requires_step_up(user):
    c = signed_in(user.email)
    r = c.post("/api/me/mfa/setup")
    assert r.status_code == 403 and r.json()["error"]["code"] == "reauth_required"


def test_enable_flow_and_secret_encrypted(user, clock):
    phone, laptop = signed_in(user.email), signed_in(user.email)
    reauth(phone)
    setup = phone.post("/api/me/mfa/setup").json()
    assert phone.post("/api/me/mfa/enable", json={"code": "000000"}).status_code == 422
    r = phone.post("/api/me/mfa/enable", json={"code": code(setup["secret"], T0)})
    codes = r.json()["recovery_codes"]
    assert len(codes) == 10 and len(set(codes)) == 10 and all(len(x) == 11 for x in codes)
    assert laptop.get("/api/me").status_code == 401          # other sessions ended
    me = phone.get("/api/me").json()
    assert me["mfa_enabled"] is True and me["recovery_codes_left"] == 10
    stored = sql("SELECT totp_secret_ct FROM app_user WHERE id = :i", i=user.id)[0][0]
    assert setup["secret"].encode() not in bytes(stored)
    assert "mfa_enabled" in [k for (k,) in sql("SELECT kind FROM audit_event")]


def test_sign_in_with_second_factor(user, clock):
    secret, _ = enroll(signed_in(user.email))
    c = client()
    r = c.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.json() == {"mfa_required": True}
    assert c.get("/api/me").status_code == 401                 # pending session is not a session
    assert c.get("/api/dashboards").status_code == 401
    replay = c.post("/api/auth/mfa", json={"code": code(secret, T0)})   # used at enrollment
    assert replay.status_code == 401 and replay.json()["error"]["code"] == "invalid_code"
    clock["t"] = T0 + 30
    ok = c.post("/api/auth/mfa", json={"code": code(secret, T0 + 30)})
    assert ok.status_code == 200 and ok.json()["user"]["email"] == user.email
    assert c.get("/api/me").status_code == 200
    assert sql("SELECT count(*) FROM user_session WHERE mfa_pending")[0][0] == 0


def test_recovery_code_single_use(user, clock):
    _, codes = enroll(signed_in(user.email))
    for expected in (200, 401):
        c = client()
        c.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
        r = c.post("/api/auth/mfa", json={"recovery_code": codes[0].lower()})
        assert r.status_code == expected
    assert "recovery_code_used" in [k for (k,) in sql("SELECT kind FROM audit_event")]


def test_pending_session_expires(user, clock):
    secret, _ = enroll(signed_in(user.email))
    c = client()
    c.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    sql("UPDATE user_session SET created_at = now() - interval '6 minutes' WHERE mfa_pending")
    clock["t"] = T0 + 60
    assert c.post("/api/auth/mfa", json={"code": code(secret, T0 + 60)}).status_code == 401


def test_wrong_codes_lock_the_account(user, clock):
    enroll(signed_in(user.email))
    c = client()
    c.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    statuses = [c.post("/api/auth/mfa", json={"code": "123456"}).status_code for _ in range(5)]
    assert statuses[:4] == [401] * 4 and statuses[4] == 423


def test_disable_needs_code_and_step_up(user, clock):
    c = signed_in(user.email)
    secret, _ = enroll(c)
    clock["t"] = T0 + 30
    assert c.post("/api/me/mfa/disable", json={"code": "000000"}).status_code == 422
    assert c.post("/api/me/mfa/disable", json={"code": code(secret, T0 + 30)}).status_code == 204
    assert c.get("/api/me").json()["mfa_enabled"] is False
    assert sql("SELECT count(*) FROM recovery_code")[0][0] == 0


@pytest.fixture
def internet(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "security_profile", "internet")
    monkeypatch.setattr(s, "site_address", "bi.example.com")
    return s


def enroll_pending(c, t=T0) -> tuple[str, list[str]]:
    """Enrol from the pending session the login handed out (no step-up: the password was just
    accepted, and the session may only enrol)."""
    setup = c.post("/api/me/mfa/setup")
    assert setup.status_code == 200, setup.text
    body = setup.json()
    r = c.post("/api/me/mfa/enable", json={"code": code(body["secret"], t)})
    assert r.status_code == 200, r.text
    return body["secret"], r.json()["recovery_codes"]


def test_internet_profile_requires_enrollment_for_admins(admin, user, internet, clock):
    c = client()
    r = c.post("/api/auth/login", json={"email": admin.email, "password": PASSWORD})
    assert r.status_code == 200
    assert r.json() == {"mfa_required": True, "mfa_enrollment_required": True}
    # The pending session is not a session: no normal route, no report data.
    assert c.get("/api/me").json()["mfa_enabled"] is False
    assert c.get("/api/reports/ventas/data").status_code == 401
    assert c.get("/api/admin/users").status_code == 401
    assert c.get("/api/dashboards").status_code == 401
    assert signed_in(user.email).get("/api/dashboards").status_code == 200   # users unaffected
    secret, _ = enroll_pending(c)
    me = c.get("/api/me").json()
    assert me["mfa_enabled"] is True and me["mfa_required"] is True
    assert c.get("/api/admin/users").status_code == 200
    assert c.get("/api/reports/ventas/data").status_code != 401   # enrolled: a real session
    clock["t"] = T0 + 30
    r = c.post("/api/me/mfa/disable", json={"code": code(secret, T0 + 30)})
    assert r.status_code == 403                                  # cannot opt out under internet


def test_private_profile_keeps_password_only_sessions_for_admins(admin, clock):
    c = signed_in(admin.email)                     # private: no second factor demanded
    assert c.get("/api/me").json()["mfa_enabled"] is False
    assert c.get("/api/reports/ventas/data").status_code != 401
    secret, _ = enroll(c)
    clock["t"] = T0 + 30
    assert c.post("/api/me/mfa/disable", json={"code": code(secret, T0 + 30)}).status_code == 204
    assert c.get("/api/me").json()["mfa_enabled"] is False


def test_superuser_reset_mfa_leaves_no_password_only_session(superuser, admin, internet, clock):
    admin_c = client()
    admin_c.post("/api/auth/login", json={"email": admin.email, "password": PASSWORD})
    enroll_pending(admin_c)
    assert admin_c.get("/api/admin/users").status_code == 200

    su = client()
    su.post("/api/auth/login", json={"email": superuser.email, "password": PASSWORD})
    enroll_pending(su)
    reauth(su)
    assert su.post(f"/api/admin/users/{admin.id}/mfa/reset").status_code == 204
    assert admin_c.get("/api/me").status_code == 401              # every session ended

    c = client()
    r = c.post("/api/auth/login", json={"email": admin.email, "password": PASSWORD})
    assert r.json() == {"mfa_required": True, "mfa_enrollment_required": True}
    assert c.get("/api/reports/ventas/data").status_code == 401
    assert c.get("/api/admin/users").status_code == 401


def test_super_user_resets_another_users_mfa(superuser, user, clock):
    enroll(signed_in(user.email))
    su = signed_in(superuser.email)
    r = su.post(f"/api/admin/users/{user.id}/mfa/reset")
    assert r.json()["error"]["code"] == "reauth_required"
    reauth(su)
    assert su.post(f"/api/admin/users/{user.id}/mfa/reset").status_code == 204
    c = client()
    assert "user" in c.post("/api/auth/login", json={"email": user.email,
                                                     "password": PASSWORD}).json()


def test_cli_resets_super_user_mfa(db, superuser, clock):
    enroll(signed_in(superuser.email))
    assert "reset" in cli.reset_superuser_mfa(db)
    db.commit()
    assert sql("SELECT totp_enabled_at FROM app_user WHERE id = :i", i=superuser.id) == [(None,)]


def test_verify_code_window_and_replay():
    user = make_user("v@example.com")
    from app.security.crypto import get_keyring
    secret = mfa.new_secret()
    mfa.store_pending_secret(user, secret, get_keyring())
    now = time.time()
    assert mfa.verify_code(user, pyotp.TOTP(secret).at(now - 30), get_keyring(), now=now)
    assert not mfa.verify_code(user, pyotp.TOTP(secret).at(now - 30), get_keyring(), now=now)
    assert not mfa.verify_code(user, pyotp.TOTP(secret).at(now - 90), get_keyring(), now=now)
    assert mfa.verify_code(user, pyotp.TOTP(secret).at(now + 30), get_keyring(), now=now)
