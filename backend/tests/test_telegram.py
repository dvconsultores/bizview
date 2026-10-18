"""Telegram sign-in tests (feature 007). No live Telegram: FakeTelegram transport."""

import threading

import pyotp
import pytest

from app.config import get_settings
from app.db import get_sessionmaker
from app.security import mfa
from app.telegram import poller as poller_module
from app.telegram import service
from app.telegram.client import BotClient
from app.telegram.handler import handle_update
from app.telegram.poller import TelegramPoller
from tests.conftest import PASSWORD, client, client_from, make_user, reauth, signed_in, sql
from tests.fake_telegram import FakeTelegram


@pytest.fixture
def fake(monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setattr(
        service,
        "client_factory",
        lambda token: BotClient(token, transport=fake.transport()),
    )
    return fake


def configure(su, fake, *, check=True, enable=True):
    """PUT settings, optionally check and enable, asserting 200 each step."""
    r = su.put(
        "/api/admin/telegram",
        json={"bot_username": fake.bot_username, "token": fake.token},
    )
    assert r.status_code == 200, r.text
    if check:
        r = su.post("/api/admin/telegram/check")
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
    if enable:
        r = su.post("/api/admin/telegram/enabled", json={"enabled": True})
        assert r.status_code == 200, r.text
        assert r.json()["enabled"] is True
        # Nothing polls in tests: mark Telegram as reachable (FR-013 health check).
        sql("UPDATE telegram_settings SET last_poll_ok_at = now() + interval '1 hour'")


# --- US1: settings, check, enable --------------------------------------------------------------

def test_off_by_default(superuser):
    r = client().get("/api/config")
    assert r.status_code == 200
    assert r.json()["telegram_sign_in"] is False
    assert r.json()["telegram_bot"] is None

    c = signed_in(superuser.email)
    r = c.get("/api/admin/telegram")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["token_configured"] is False


def test_only_superuser_with_step_up(admin, superuser):
    c = signed_in(admin.email)
    assert c.get("/api/admin/telegram").status_code == 403
    assert c.put("/api/admin/telegram",
                 json={"bot_username": "XBot", "token": "x"}).status_code == 403
    assert c.post("/api/admin/telegram/check").status_code == 403
    assert c.post("/api/admin/telegram/enabled", json={"enabled": True}).status_code == 403

    c = signed_in(superuser.email)
    r = c.put("/api/admin/telegram", json={"bot_username": "XBot"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "reauth_required"
    assert c.post("/api/admin/telegram/check").json()["error"]["code"] == "reauth_required"
    assert c.post("/api/admin/telegram/enabled",
                  json={"enabled": True}).json()["error"]["code"] == "reauth_required"


def test_token_is_write_only(superuser, fake, caplog):
    caplog.set_level("DEBUG")
    sup = reauth(signed_in(superuser.email))
    configure(sup, fake)

    data = [
        sup.put("/api/admin/telegram",
                json={"bot_username": fake.bot_username, "token": fake.token}).text,
        sup.post("/api/admin/telegram/check").text,
        sup.post("/api/admin/telegram/enabled", json={"enabled": True}).text,
        sup.get("/api/admin/telegram").text,
        sup.get("/api/config").text,
        str(sql("SELECT detail FROM audit_event")),
        caplog.text,
    ]
    secret = fake.token
    assert secret not in " ".join(data)
    assert secret.split(":", 1)[1] not in " ".join(data)
    assert sql("SELECT token_ct IS NOT NULL FROM telegram_settings") == [(True,)]

    r = sup.get("/api/config")
    assert r.json()["telegram_sign_in"] is True
    assert r.json()["telegram_bot"] == fake.bot_username


@pytest.mark.parametrize(
    "mode,webhook,put_username,expected",
    [
        ("unauthorized", "", None, "invalid_credential"),
        ("timeout", "", None, "timeout"),
        ("network", "", None, "unreachable"),
        ("ok", "https://x.example/hook", None, "webhook_conflict"),
        ("ok", "", "OtroNombreBot", "name_mismatch"),
    ],
)
def test_check_reasons(superuser, fake, mode, webhook, put_username, expected):
    fake.mode = mode
    fake.webhook_url = webhook
    sup = reauth(signed_in(superuser.email))
    r = sup.put(
        "/api/admin/telegram",
        json={"bot_username": put_username or fake.bot_username, "token": fake.token},
    )
    assert r.status_code == 200, r.text
    r = sup.post("/api/admin/telegram/check")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": False, "reason": expected}

    state = sup.get("/api/admin/telegram").json()
    assert state["last_check_ok"] is False
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'telegram_checked'") == [(1,)]


def test_enable_requires_successful_check(superuser, fake):
    sup = reauth(signed_in(superuser.email))
    r = sup.put(
        "/api/admin/telegram",
        json={"bot_username": fake.bot_username, "token": fake.token},
    )
    assert r.status_code == 200

    r = sup.post("/api/admin/telegram/enabled", json={"enabled": True})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "telegram_check_required"

    r = sup.post("/api/admin/telegram/check")
    assert r.json()["ok"] is True
    r = sup.post("/api/admin/telegram/enabled", json={"enabled": True})
    assert r.status_code == 200
    assert r.json()["enabled"] is True
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'telegram_enabled'") == [(1,)]

    # Changing the token invalidates the check and disables sign-in.
    r = sup.put(
        "/api/admin/telegram",
        json={"bot_username": fake.bot_username, "token": "999999:ANOTHER-TOKEN"},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert r.json()["last_check_ok"] is None
    assert sup.get("/api/config").json()["telegram_sign_in"] is False


def test_validation(superuser, fake):
    sup = reauth(signed_in(superuser.email))
    for name in ("@bad", "nobotsuffix"):
        r = sup.put("/api/admin/telegram", json={"bot_username": name, "token": fake.token})
        assert r.status_code == 422
        assert r.json()["error"]["fields"]["bot_username"] == "invalid"

    r = sup.put("/api/admin/telegram", json={"bot_username": fake.bot_username, "token": "abc"})
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["token"] == "invalid"

    # Leading @ on a valid name is accepted and normalized.
    r = sup.put(
        "/api/admin/telegram",
        json={"bot_username": "@" + fake.bot_username, "token": fake.token},
    )
    assert r.status_code == 200
    assert r.json()["bot_username"] == fake.bot_username


def test_clear_token(superuser, fake):
    sup = reauth(signed_in(superuser.email))
    configure(sup, fake)

    r = sup.put("/api/admin/telegram", json={"bot_username": fake.bot_username, "token": ""})
    assert r.status_code == 200
    assert r.json()["token_configured"] is False
    assert r.json()["enabled"] is False

    r = sup.post("/api/admin/telegram/check")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "telegram_not_configured"


def test_disable_audited(superuser, fake):
    sup = reauth(signed_in(superuser.email))
    configure(sup, fake)

    r = sup.post("/api/admin/telegram/enabled", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'telegram_disabled'") == [(1,)]


# --- helpers for the bot side (feature 007, contracts/bot.md) ---------------------------------

def setup_bot(superuser, fake):
    configure(reauth(signed_in(superuser.email)), fake)


def bot(fake, update):
    with get_sessionmaker().begin() as db:
        handle_update(db, BotClient(fake.token, transport=fake.transport()), update)
    return fake


def token_from(link):
    return link.split("start=", 1)[1]


def buttons(fake):
    """Callback data list of the LAST sent message with an inline keyboard."""
    for msg in reversed(fake.sent):
        kb = msg.get("reply_markup", {}).get("inline_keyboard")
        if kb:
            return [btn["callback_data"] for row in kb for btn in row]
    return []


def link_telegram(fake, email, telegram_id=7001):
    """Full link flow; asserts the link was created."""
    u = reauth(signed_in(email))
    r = u.post("/api/me/telegram/link")
    assert r.status_code == 200, r.text
    bot(fake, fake.start(token_from(r.json()["deep_link"]), user_id=telegram_id))
    ok = next(d for d in buttons(fake) if d.startswith("ok:"))
    bot(fake, fake.press(ok, user_id=telegram_id))
    assert u.get("/api/me/telegram").json()["linked"] is True
    return u


def start_sign_in(fake, telegram_id=7001, ip=None):
    """Start a Telegram sign-in request and feed /start to the bot."""
    c = client_from(ip) if ip else client()
    r = c.post("/api/auth/telegram/start")
    assert r.status_code == 200, r.text
    body = r.json()
    token = token_from(body["deep_link"])
    bot(fake, fake.start(token, user_id=telegram_id))
    return c, body["match_code"], token


def press_code(fake, match_code, telegram_id=7001, right=True):
    """Press the right (or a wrong) code button on the last keyboard."""
    codes = [d for d in buttons(fake) if d.startswith("c:")]
    data = next(d for d in codes if d.endswith(f":{match_code}") == right)
    return bot(fake, fake.press(data, user_id=telegram_id))


# --- US2: linking ------------------------------------------------------------------------------

def test_link_and_unlink_own(user, superuser, fake):
    setup_bot(superuser, fake)
    u = link_telegram(fake, user.email)

    body = u.get("/api/me/telegram").json()
    assert body["linked"] is True
    assert body["display_name"] == "Ana Pérez"
    assert body["username"] == "ana_p"
    assert sql("SELECT actor_id, target_id FROM audit_event "
               "WHERE kind = 'telegram_linked'") == [(user.id, user.id)]

    assert u.delete("/api/me/telegram").status_code == 204
    assert u.get("/api/me/telegram").json()["linked"] is False
    assert sql("SELECT actor_id, target_id FROM audit_event "
               "WHERE kind = 'telegram_unlinked'") == [(user.id, user.id)]


def test_link_requires_step_up_and_availability(user, superuser, fake):
    assert reauth(signed_in(user.email)).post("/api/me/telegram/link").status_code == 404

    setup_bot(superuser, fake)
    r = signed_in(user.email).post("/api/me/telegram/link")
    assert r.status_code == 403 and r.json()["error"]["code"] == "reauth_required"


def test_telegram_account_linked_once(user, admin, superuser, fake):
    setup_bot(superuser, fake)
    link_telegram(fake, user.email, telegram_id=7001)

    # Another user tries to link the same Telegram account.
    adm = reauth(signed_in(admin.email))
    r = adm.post("/api/me/telegram/link")
    assert r.status_code == 200
    bot(fake, fake.start(token_from(r.json()["deep_link"]), user_id=7001))
    bot(fake, fake.press(next(d for d in buttons(fake) if d.startswith("ok:")), user_id=7001))
    assert "ya está vinculada a otro usuario" in fake.edited[-1]["text"]
    assert admin.email not in fake.edited[-1]["text"] and user.email not in fake.edited[-1]["text"]
    assert sql("SELECT count(*) FROM telegram_link") == [(1,)]

    # The same user cannot link a second account.
    r = reauth(signed_in(user.email)).post("/api/me/telegram/link")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "telegram_already_linked_self"


def test_foreign_and_expired_callbacks_ignored(user, superuser, fake):
    setup_bot(superuser, fake)
    r = reauth(signed_in(user.email)).post("/api/me/telegram/link")
    bot(fake, fake.start(token_from(r.json()["deep_link"]), user_id=7001))
    ok = next(d for d in buttons(fake) if d.startswith("ok:"))

    bot(fake, fake.press(ok, user_id=9999))                     # another Telegram user
    assert sql("SELECT count(*) FROM telegram_link") == [(0,)]

    sql("UPDATE telegram_request SET expires_at = now() - interval '1 second'")
    bot(fake, fake.press(ok, user_id=7001))                     # too late
    assert sql("SELECT count(*) FROM telegram_link") == [(0,)]


def test_admin_removes_link(user, admin, superuser, fake):
    setup_bot(superuser, fake)
    link_telegram(fake, user.email, telegram_id=7001)
    link_telegram(fake, superuser.email, telegram_id=7002)

    adm = signed_in(admin.email)
    assert adm.get(f"/api/admin/users/{user.id}").json()["telegram_linked"] is True
    adm = reauth(adm)
    assert adm.delete(f"/api/admin/users/{user.id}/telegram").status_code == 204
    assert sql("SELECT actor_id, target_id FROM audit_event "
               "WHERE kind = 'telegram_unlinked' AND target_id = :t", t=user.id) \
        == [(admin.id, user.id)]
    assert adm.delete(f"/api/admin/users/{superuser.id}/telegram").status_code == 403


# --- US3: sign-in ------------------------------------------------------------------------------

def test_sign_in_with_telegram(user, superuser, fake):
    setup_bot(superuser, fake)
    link_telegram(fake, user.email)

    c, match_code, _ = start_sign_in(fake)
    assert c.get("/api/auth/telegram/status").json() == {"status": "pending"}

    press_code(fake, match_code)
    r = c.get("/api/auth/telegram/status")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "signed_in"
    assert r.json()["user"]["email"] == user.email
    assert c.get("/api/me").status_code == 200
    assert sql("SELECT count(*) FROM audit_event "
               "WHERE kind = 'login_ok' AND detail->>'method' = 'telegram'") == [(1,)]
    assert c.get("/api/auth/telegram/status").json() == {"status": "expired"}


@pytest.mark.parametrize("reason", ["not_linked", "wrong_code", "cancelled"])
def test_refusals_are_counted(user, superuser, fake, reason):
    setup_bot(superuser, fake)
    link_telegram(fake, user.email)

    if reason == "not_linked":
        c, _, _ = start_sign_in(fake, telegram_id=8888, ip="192.0.2.77")
    else:
        c, match_code, _ = start_sign_in(fake, ip="192.0.2.77")
        if reason == "wrong_code":
            press_code(fake, match_code, right=False)
        else:
            bot(fake, fake.press(next(d for d in buttons(fake) if d.startswith("x:"))))

    body = c.get("/api/auth/telegram/status").json()
    assert body["status"] == "refused" and body["reason"] == reason and body["message"]
    assert sql("SELECT detail->>'method', detail->>'reason' FROM audit_event "
               "WHERE kind = 'login_failed'") == [("telegram", reason)]
    assert sql("SELECT failures FROM login_throttle WHERE ip = '192.0.2.77'") == [(1,)]
    assert c.get("/api/auth/telegram/status").json() == {"status": "expired"}


def test_inactive_and_locked_users_refused(user, superuser, fake):
    setup_bot(superuser, fake)
    link_telegram(fake, user.email)

    sql("UPDATE app_user SET is_active = false WHERE id = :i", i=user.id)
    c, match_code, _ = start_sign_in(fake)
    press_code(fake, match_code)
    r = c.get("/api/auth/telegram/status")
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"
    assert c.get("/api/me").status_code == 401

    sql("UPDATE app_user SET is_active = true, locked_until = now() + interval '10 minutes' "
        "WHERE id = :i", i=user.id)
    c, match_code, _ = start_sign_in(fake)
    press_code(fake, match_code)
    r = c.get("/api/auth/telegram/status")
    assert r.status_code == 423 and r.json()["error"]["code"] == "locked"


T0 = 1_900_000_020.0


@pytest.fixture
def clock(monkeypatch):
    now = {"t": T0}
    monkeypatch.setattr(mfa.time, "time", lambda: now["t"])
    return now


def enroll(c, t=T0):
    reauth(c)
    setup = c.post("/api/me/mfa/setup").json()
    r = c.post("/api/me/mfa/enable", json={"code": pyotp.TOTP(setup["secret"]).at(t)})
    assert r.status_code == 200
    return setup["secret"]


def internet_profile(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "security_profile", "internet")
    monkeypatch.setattr(s, "site_address", "bi.example.com")


def test_admin_two_step_on_internet_profile(admin, superuser, fake, clock, monkeypatch):
    setup_bot(superuser, fake)                  # private profile: the super user is not enrolled
    link_telegram(fake, admin.email)            # link first: enrolment makes sign-ins two-step
    secret = enroll(signed_in(admin.email))
    internet_profile(monkeypatch)

    c, match_code, _ = start_sign_in(fake)
    press_code(fake, match_code)
    assert c.get("/api/auth/telegram/status").json() == {"status": "mfa_required"}
    assert c.get("/api/me").status_code == 401

    clock["t"] = T0 + 30
    r = c.post("/api/auth/mfa", json={"code": pyotp.TOTP(secret).at(T0 + 30)})
    assert r.status_code == 200
    assert c.get("/api/me").status_code == 200


def test_temporary_password_user(superuser, fake):
    setup_bot(superuser, fake)
    temp = make_user("temp@example.com", must_change=True)
    sql("INSERT INTO telegram_link (user_id, telegram_id, display_name) "
        "VALUES (:u, 7001, 'Ana')", u=temp.id)

    c, match_code, _ = start_sign_in(fake)
    press_code(fake, match_code)
    r = c.get("/api/auth/telegram/status")
    assert r.json()["status"] == "signed_in"
    assert r.json()["user"]["must_change_password"] is True


def test_replay_and_binding(user, superuser, fake):
    setup_bot(superuser, fake)
    link_telegram(fake, user.email)

    c, match_code, token = start_sign_in(fake)
    bot(fake, fake.start(token, user_id=7001))                  # same /start again
    assert "ya no es válido" in fake.sent[-1]["text"]

    press_code(fake, match_code)
    assert client().get("/api/auth/telegram/status").json() == {"status": "expired"}   # no cookie
    assert c.get("/api/auth/telegram/status").json()["status"] == "signed_in"

    press_code(fake, match_code)                                # replayed press: no effect
    assert c.get("/api/auth/telegram/status").json() == {"status": "expired"}
    assert sql("SELECT count(*) FROM audit_event "
               "WHERE kind = 'login_ok' AND detail->>'method' = 'telegram'") == [(1,)]


def test_unreachable_telegram_keeps_password_sign_in(user, superuser, fake):
    setup_bot(superuser, fake)
    fake.mode = "network"
    r = client().post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200


def test_test_hooks_not_mounted():
    assert client().post("/api/test/telegram/update", json={}).status_code == 404


# --- convergence: Telegram unreachable (FR-013) and the poller (T033, T034) ---------------------

def test_start_refused_when_telegram_unreachable(user, superuser, fake):
    setup_bot(superuser, fake)
    sql("UPDATE telegram_settings SET last_poll_ok_at = now() - interval '10 minutes'")

    r = client().post("/api/auth/telegram/start")
    assert r.status_code == 503 and r.json()["error"]["code"] == "telegram_unavailable"
    r = reauth(signed_in(user.email)).post("/api/me/telegram/link")
    assert r.status_code == 503 and r.json()["error"]["code"] == "telegram_unavailable"

    r = client().post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200


@pytest.fixture
def poller():
    return TelegramPoller(threading.Event())


def test_poller_idle_when_unavailable(fake, poller):
    assert poller.poll_once() is False


def test_poller_handles_updates_and_persists_offset(user, superuser, fake, poller):
    setup_bot(superuser, fake)
    sql("UPDATE telegram_settings SET last_poll_ok_at = NULL")
    r = reauth(signed_in(user.email)).post("/api/me/telegram/link")
    assert r.status_code == 503                  # nothing polled yet: Telegram not proven reachable
    sql("UPDATE telegram_settings SET last_poll_ok_at = now()")
    r = reauth(signed_in(user.email)).post("/api/me/telegram/link")
    fake.start(token_from(r.json()["deep_link"]))  # update 1000

    assert poller.poll_once() is True
    assert sql("SELECT update_offset FROM telegram_settings") == [(1001,)]
    assert any(d.startswith("ok:") for d in buttons(fake))
    assert sql("SELECT last_poll_ok_at > now() - interval '1 minute' FROM telegram_settings") \
        == [(True,)]

    sent = len(fake.sent)
    assert poller.poll_once() is True
    assert len(fake.sent) == sent                # the update is not processed twice


def test_poller_skips_poison_update(superuser, fake, poller, monkeypatch):
    setup_bot(superuser, fake)
    first = fake.start("x")["update_id"]
    second = fake.start("x")["update_id"]
    original = poller_module.handle_update

    def bad_handle(db, bot, update):
        if update["update_id"] == first:
            raise RuntimeError("poison")
        original(db, bot, update)

    monkeypatch.setattr(poller_module, "handle_update", bad_handle)
    assert poller.poll_once() is True
    assert sql("SELECT update_offset FROM telegram_settings") == [(second + 1,)]


@pytest.mark.parametrize("mode,reason", [
    ("unauthorized", "invalid_credential"),
    ("conflict", "webhook_conflict"),
])
def test_poller_flags_bad_credential(superuser, fake, poller, mode, reason):
    setup_bot(superuser, fake)
    fake.mode = mode
    poller.stop.set()                            # the 60 s pause returns at once

    assert poller.poll_once() is True
    assert sql("SELECT last_check_ok, last_check->>'reason' FROM telegram_settings") \
        == [(False, reason)]
    assert client().get("/api/config").json()["telegram_sign_in"] is False


def test_bot_speaks_linked_account_language(user, superuser, fake):
    setup_bot(superuser, fake)
    link_telegram(fake, user.email)
    sql("UPDATE app_user SET locale = 'en' WHERE id = :i", i=user.id)
    start_sign_in(fake)
    assert fake.sent[-1]["text"].startswith("Sign-in request")
    assert "Cancel" in fake.sent[-1]["text"]


def test_bot_uses_telegram_language_when_unlinked(superuser, fake):
    setup_bot(superuser, fake)
    upd = fake.start("", user_id=9100)
    upd["message"]["text"] = "/start"
    upd["message"]["from"]["language_code"] = "en-US"
    bot(fake, upd)
    assert fake.sent[-1]["text"].startswith("To sign in or link your account")


def test_bot_defaults_to_spanish_without_language_code(superuser, fake):
    setup_bot(superuser, fake)
    upd = fake.start("", user_id=9101)
    bot(fake, upd)
    assert fake.sent[-1]["text"].startswith("Para ingresar o vincular tu cuenta")
