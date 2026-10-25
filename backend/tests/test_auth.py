"""US1: sign-in, lockout, sessions, CSRF (FR-001 - FR-006)."""
from datetime import timedelta
from pathlib import Path

from tests.conftest import PASSWORD, client, make_user, signed_in, sql


def login(c, email, password):
    return c.post("/api/auth/login", json={"email": email, "password": password})


def test_login_ok_sets_http_only_cookie_and_returns_user(user):
    c = client()
    r = login(c, "  USER@Example.com ", PASSWORD)
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "user@example.com"
    cookie = r.headers["set-cookie"]
    assert "sid=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert c.get("/api/me").json()["id"] == user.id
    assert sql("SELECT last_login_at IS NOT NULL FROM app_user")[0][0]
    stored = sql("SELECT id_hash FROM user_session")[0][0]
    assert c.cookies["sid"].encode() not in bytes(stored)  # only the hash is stored


def test_failures_are_indistinguishable(user):
    make_user("off@example.com", active=False)
    bodies = [login(client(), "user@example.com", "wrong-password-x"),
              login(client(), "nobody@example.com", PASSWORD),
              login(client(), "off@example.com", PASSWORD)]
    assert {r.status_code for r in bodies} == {401}
    assert len({r.text for r in bodies}) == 1


def test_lockout_after_five_failures(user):
    c = client()
    for _ in range(4):
        assert login(c, user.email, "wrong-password-x").status_code == 401
    r = login(c, user.email, "wrong-password-x")
    assert r.status_code == 423
    assert 890 <= r.json()["error"]["retry_after_seconds"] <= 900
    r = login(c, user.email, PASSWORD)  # right password while locked
    assert r.status_code == 423
    kinds = [k for (k,) in sql("SELECT kind FROM audit_event ORDER BY id")]
    assert kinds.count("login_locked") == 1
    sql("UPDATE app_user SET locked_until = now() - interval '1 second'")
    assert login(c, user.email, PASSWORD).status_code == 200


def test_success_resets_failure_count(user):
    for _ in range(4):
        login(client(), user.email, "wrong-password-x")
    assert login(client(), user.email, PASSWORD).status_code == 200
    assert sql("SELECT failed_attempts FROM app_user")[0][0] == 0


def test_logout_ends_session(user):
    c = signed_in(user.email)
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/me").status_code == 401
    assert sql("SELECT count(*) FROM user_session")[0][0] == 0


def test_idle_and_absolute_expiry(user):
    c = signed_in(user.email)
    sql("UPDATE user_session SET last_seen_at = now() - :d", d=timedelta(days=7, minutes=1))
    assert c.get("/api/me").status_code == 401

    c = signed_in(user.email)
    sql("UPDATE user_session SET created_at = now() - :d", d=timedelta(days=30, minutes=1))
    assert c.get("/api/me").status_code == 401


def test_unauthenticated_requests_are_refused():
    r = client().get("/api/dashboards")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


def test_csrf_header_and_origin_required(user):
    from fastapi.testclient import TestClient

    from app.main import app
    bare = TestClient(app)
    r = bare.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
    r = client().post("/api/auth/login", json={"email": user.email, "password": PASSWORD},
                      headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client().post("/api/auth/login", json={"email": user.email, "password": PASSWORD},
                      headers={"Origin": "http://testserver"})
    assert r.status_code == 200


def test_api_responses_are_not_cached(user):
    r = signed_in(user.email).get("/api/me")
    assert r.headers["cache-control"] == "no-store"


def test_public_config_and_health():
    c = client()
    version = (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()
    assert c.get("/api/health").json() == {"status": "ok", "version": version}
    assert c.get("/api/config").json() == {"product_name": "Panel de prueba",
                                           "organization_name": "Cliente Demo",
                                           "logo_url": None, "version": version,
                                           "source_url": None, "license": "AGPL-3.0-or-later",
                                           "ai_enabled": False, "telegram_sign_in": False,
                                           "telegram_bot": None, "default_locale": "es",
                                           "footer_credit": "GlobalDV",
                                           "vision_enabled": False, "attachments_max_mb": 5,
                                           "attachments_max_per_message": 4,
                                           "google_auth": False,
                                           "palette_preset": "impacto",
                                           "palette_presets": ["impacto", "clasico", "monocromo",
                                                               "contraste", "daltonico"]}


def test_health_names_the_commit_the_image_was_built_from(monkeypatch):
    """Release images carry their commit: `curl /api/health` says whether a fix is deployed."""
    from app.api.health import _build
    from app.config import get_settings

    assert "commit" not in _build()                  # a development checkout has none
    monkeypatch.setattr(get_settings(), "bizview_commit", "3fb5fff")
    assert _build() == {"version": get_settings().version, "commit": "3fb5fff"}
