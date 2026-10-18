"""FR-007 - FR-009: super user from configuration, recovery."""
import pytest

from app import cli
from app.config import get_settings
from tests.conftest import client, make_user, signed_in, sql


@pytest.fixture
def run(db):
    def _run(command="bootstrap"):
        return cli.COMMANDS[command](db)
    return _run


def settings(monkeypatch, **kw):
    s = get_settings()
    for k, v in kw.items():
        monkeypatch.setattr(s, k, v)


def test_creates_super_user_once(run, db):
    assert run() == "created"
    db.commit()
    assert run() == "exists"
    rows = sql("SELECT email, role, is_superuser, must_change_password FROM app_user")
    assert rows == [("root@example.com", "admin", True, False)]
    assert [k for (k,) in sql("SELECT kind FROM audit_event")] == ["superuser_created"]


def test_super_user_can_sign_in_and_stored_password_wins(run, db, monkeypatch):
    run()
    db.commit()
    c = signed_in("root@example.com", "Sup3r-secret-pass")
    assert c.get("/api/me").json()["is_superuser"] is True
    settings(monkeypatch, super_user_password="Another-password-456")
    assert run() == "exists"
    db.commit()
    signed_in("root@example.com", "Sup3r-secret-pass")


@pytest.mark.parametrize("email,password,fragment", [
    (None, "Sup3r-secret-pass", "SUPER_USER_EMAIL"),
    ("root@example.com", None, "SUPER_USER_PASSWORD is missing"),
    ("root@example.com", "short", "too_short"),
    ("root@example.com", "root-and-more-chars", "contains_email"),
])
def test_refuses_missing_or_weak_config(run, monkeypatch, email, password, fragment):
    settings(monkeypatch, super_user_email=email, super_user_password=password)
    with pytest.raises(cli.ConfigError, match=fragment):
        run()


def test_main_exit_code_on_bad_config(monkeypatch):
    settings(monkeypatch, super_user_password=None)
    assert cli.main(["bootstrap"]) == 1


def test_existing_user_is_promoted(run, db):
    make_user("root@example.com", role="user")
    assert run() == "promoted"
    db.commit()
    assert sql("SELECT role, is_superuser FROM app_user") == [("admin", True)]


def test_recovery_resets_password_lock_and_sessions(run, db, monkeypatch):
    run()
    db.commit()
    c = signed_in("root@example.com", "Sup3r-secret-pass")
    sql("UPDATE app_user SET locked_until = now() + interval '10 minutes', "
        "password_hash = 'x'")
    settings(monkeypatch, super_user_password="Recovered-pass-789")
    assert run("reset-superuser-password") == "recovered"
    db.commit()
    assert c.get("/api/me").status_code == 401
    signed_in("root@example.com", "Recovered-pass-789")
    assert "superuser_recovered" in [k for (k,) in sql("SELECT kind FROM audit_event")]


def test_recovery_requires_matching_email(run, db, monkeypatch):
    run()
    db.commit()
    settings(monkeypatch, super_user_email="other@example.com")
    with pytest.raises(cli.ConfigError, match="does not match"):
        run("reset-superuser-password")


def test_login_page_without_super_user_still_answers():
    assert client().post("/api/auth/login",
                         json={"email": "x@example.com", "password": "y"}).status_code == 401
