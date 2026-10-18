"""US3: own password change and the temporary-password gate (FR-014, FR-015, FR-017)."""
import pytest

from tests.conftest import PASSWORD, client, make_user, signed_in, sql

NEW = "Brand-new-pass-42"


def change(c, current, new):
    return c.post("/api/me/password", json={"current_password": current, "new_password": new})


def test_change_ends_other_sessions_and_keeps_current(user):
    phone, laptop = signed_in(user.email), signed_in(user.email)
    assert change(phone, PASSWORD, NEW).status_code == 204
    assert phone.get("/api/me").status_code == 200
    assert laptop.get("/api/me").status_code == 401
    signed_in(user.email, NEW)
    assert client().post("/api/auth/login",
                         json={"email": user.email, "password": PASSWORD}).status_code == 401


def test_wrong_current_counts_toward_lockout(user):
    c = signed_in(user.email)
    for _ in range(4):
        r = change(c, "wrong-password-x", NEW)
        assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"
    assert change(c, "wrong-password-x", NEW).status_code == 423
    assert c.get("/api/me").status_code == 401  # locked → sessions ended


@pytest.mark.parametrize("new,code", [
    ("short", "too_short"),
    ("x" * 129, "too_long"),
    ("my-user-password", "contains_email"),
    (PASSWORD, "same_as_current"),
])
def test_rules(user, new, code):
    r = change(signed_in(user.email), PASSWORD, new)
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == {"new_password": code}


def test_temporary_password_gate():
    make_user("temp@example.com", must_change=True)
    c = signed_in("temp@example.com")
    assert c.get("/api/me").json()["must_change_password"] is True
    for path in ("/api/dashboards", "/api/dashboards/ventas", "/api/admin/users"):
        r = c.get(path)
        assert r.status_code == 403 and r.json()["error"]["code"] == "password_change_required"
    assert change(c, PASSWORD, NEW).status_code == 204
    assert c.get("/api/me").json()["must_change_password"] is False
    assert c.get("/api/dashboards").status_code == 200
    assert "password_changed" in [k for (k,) in sql("SELECT kind FROM audit_event")]


# --- theme preference (feature 006, contracts/api.md) ----------------------------------------

def set_theme(c, body):
    return c.patch("/api/me/preferences", json=body)


def test_theme_defaults_to_system_and_persists(user):
    c = signed_in(user.email)
    assert c.get("/api/me").json()["theme"] == "system"
    r = set_theme(c, {"theme": "dark"})
    assert r.status_code == 200 and r.json() == {"theme": "dark", "locale": None}
    assert signed_in(user.email).get("/api/me").json()["theme"] == "dark"   # another device
    assert set_theme(c, {"theme": "dark"}).status_code == 200                # idempotent
    assert sql("SELECT theme FROM app_user WHERE id = :i", i=user.id) == [("dark",)]


@pytest.mark.parametrize("body", [{"theme": "sepia"}, {}, {"theme": "dark", "extra": 1}])
def test_theme_rejects_invalid_values(user, body):
    r = set_theme(signed_in(user.email), body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert sql("SELECT theme FROM app_user WHERE id = :i", i=user.id) == [("system",)]


def test_theme_requires_session_and_csrf_header(user):
    assert set_theme(client(), {"theme": "dark"}).status_code == 401
    c = signed_in(user.email)
    c.headers.pop("X-Requested-With")
    r = set_theme(c, {"theme": "dark"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"


def test_theme_allowed_with_temporary_password():
    make_user("temp-theme@example.com", must_change=True)
    c = signed_in("temp-theme@example.com")
    assert set_theme(c, {"theme": "light"}).status_code == 200
    assert c.get("/api/me").json()["theme"] == "light"


def test_attachments_notice_is_shown_once_per_account(user):
    """Feature 024 FR-006: the image notice is accepted once and holds on every device."""
    phone, laptop = signed_in(user.email), signed_in(user.email)
    assert phone.get("/api/me").json()["attachments_notice_at"] is None

    assert phone.post("/api/me/attachments-notice").status_code == 204
    stamped = phone.get("/api/me").json()["attachments_notice_at"]
    assert stamped is not None
    assert laptop.get("/api/me").json()["attachments_notice_at"] == stamped

    assert phone.post("/api/me/attachments-notice").status_code == 204
    assert phone.get("/api/me").json()["attachments_notice_at"] == stamped     # idempotent
    assert sql("SELECT count(*) FROM audit_event WHERE kind LIKE 'attachment%'")[0][0] == 0


def test_attachments_notice_needs_a_session_and_the_csrf_header(user):
    assert client().post("/api/me/attachments-notice").status_code == 401
    c = signed_in(user.email)
    c.headers.pop("X-Requested-With")
    r = c.post("/api/me/attachments-notice")
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
