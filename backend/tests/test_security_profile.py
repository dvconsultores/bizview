"""Feature 004: security option and admin network allow-list (FR-016, FR-017, FR-022)."""
import pytest

from app.config import Settings, get_settings
from app.security import profile
from tests.conftest import client_from, reauth, signed_in, sql


def settings(**kw) -> Settings:
    return Settings(database_url_bi="postgresql://x@localhost/x", **kw)


def test_profile_resolution():
    assert settings(security_profile="auto").profile == "private"
    assert settings(security_profile="auto", site_address="bi.example.com").profile == "internet"
    assert settings(site_address="bi.example.com", security_profile="private").profile == "private"
    assert settings(security_profile="internet").profile == "internet"


@pytest.mark.parametrize("kw,fragment", [
    ({"security_profile": "internet"}, "domain"),
    ({"security_profile": "internet", "site_address": "bi.example.com", "cookie_secure": False},
     "COOKIE_SECURE"),
])
def test_internet_profile_refuses_insecure_start(kw, fragment):
    with pytest.raises(profile.ProfileError, match=fragment):
        profile.enforce_at_start(settings(**kw))


def test_internet_profile_accepts_secure_start():
    profile.enforce_at_start(settings(security_profile="internet", site_address="bi.example.com",
                                      cookie_secure=True, direct_bi_role="bizview_direct"))


def test_internet_profile_requires_direct_bi_role():
    with pytest.raises(profile.ProfileError, match="DIRECT_BI_ROLE"):
        profile.enforce_at_start(settings(security_profile="internet",
                                          site_address="bi.example.com", cookie_secure=True))


def test_internet_profile_no_role_needed_when_direct_reports_off():
    profile.enforce_at_start(settings(security_profile="internet", site_address="bi.example.com",
                                      cookie_secure=True, direct_reports_bi=False))


def test_http_rules_per_profile():
    private = settings()
    internet = settings(security_profile="internet", site_address="bi.example.com")
    assert profile.url_problem("http://erp.local/ws", private) is None
    assert profile.url_problem("http://erp.local/ws", internet) == "not_allowed_in_profile"
    assert profile.url_problem("https://erp.example.com", internet) is None
    assert profile.url_problem("ftp://x", private) == "invalid_url"
    assert profile.sslmode_problem("disable", private) is None
    assert profile.sslmode_problem("disable", internet) == "not_allowed_in_profile"
    assert profile.sslmode_problem("require", internet) is None


def test_admin_allow_list(monkeypatch, superuser, user):
    monkeypatch.setattr(get_settings(), "admin_allowed_networks", "10.0.0.0/8, 2001:db8::/32")
    inside, outside = client_from("10.1.2.3"), client_from("203.0.113.50")
    for c in (inside, outside):
        c.post("/api/auth/login", json={"email": superuser.email, "password": "Correct-horse-9"})
    assert inside.get("/api/admin/users").status_code == 200
    r = outside.get("/api/admin/users")
    assert r.status_code == 403 and r.json()["error"]["code"] == "address_not_allowed"
    assert outside.get("/api/dashboards").status_code == 200            # the rest keeps working
    outside.get("/api/admin/users")
    n = sql("SELECT count(*) FROM audit_event WHERE kind = 'admin_address_refused'")[0][0]
    assert n == 1                                                        # audited once per hour


def test_reauth_endpoint(user):
    c = signed_in(user.email)
    assert c.get("/api/me").json()["reauth_valid_until"] is None
    reauth(c)
    assert c.get("/api/me").json()["reauth_valid_until"] is not None
    assert "reauth_ok" in [k for (k,) in sql("SELECT kind FROM audit_event")]
