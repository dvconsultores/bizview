"""Feature 018: email settings come from the installation environment (FR-012);
there is no email page in Administración (FR-013)."""
import logging
import smtplib

import pytest
from pydantic import SecretStr, ValidationError

from app import cli
from app.config import Settings, get_settings
from app.mail import send as mail_send
from app.mail import settings as mail_settings
from app.security import profile
from tests.conftest import MAIL_ENV, reauth, set_mail, signed_in, sql
from tests.fake_smtp import SmtpRecorder

PASSWORD_MARKER = "Mk-Smtp-Pass-4e7"
ENV = {
    **MAIL_ENV,
    "smtp_user": "bizview@cliente.com",
    "smtp_password": PASSWORD_MARKER,
    "email_allowed_domains": "cliente.com,@Socio.COM",
}


@pytest.fixture
def smtp(monkeypatch):
    recorder = SmtpRecorder()
    recorder.install(monkeypatch)
    return recorder


def settings_of(**values) -> Settings:
    return Settings(database_url_bi="postgresql://u@localhost/db", **values)


def test_status_off_by_default():
    data = mail_settings.status()
    assert data["enabled"] is False
    assert data["configured"] is False
    assert data["sharing_enabled"] is False
    assert data["password_configured"] is False
    assert data["missing"] == []
    assert data["port"] == 587
    assert data["security"] == "starttls"
    assert data["allowed_domains"] == []
    assert "password" not in data
    assert [k for k in data if "password" in k] == ["password_configured"]


def test_mail_routes_are_gone(superuser):
    c = reauth(signed_in(superuser.email))
    assert c.get("/api/admin/mail").status_code == 404
    assert c.post("/api/admin/mail/test").status_code == 404
    assert c.put("/api/admin/mail", json={}).status_code in (404, 405)
    assert c.post("/api/admin/mail/enabled", json={"enabled": True}).status_code in (404, 405)
    assert c.post("/api/admin/mail/sharing", json={"enabled": True}).status_code in (404, 405)


def test_status_reflects_environment():
    set_mail(**{**ENV, "share_links_enabled": True})
    data = mail_settings.status()
    assert data["enabled"] is True
    assert data["configured"] is True
    assert data["missing"] == []
    assert data["host"] == "smtp.cliente.com"
    assert data["port"] == 587
    assert data["security"] == "starttls"
    assert data["security_allowed"] is True
    assert data["username"] == "bizview@cliente.com"
    assert data["password_configured"] is True
    assert data["sender_name"] == "Bizview"
    assert data["sender_address"] == "bizview@cliente.com"
    assert data["allowed_domains"] == ["cliente.com", "socio.com"]
    assert data["sharing_enabled"] is True
    assert PASSWORD_MARKER not in str(data)


def test_missing_reports_incomplete_environment(superuser):
    set_mail(smtp_host="smtp.cliente.com")
    data = mail_settings.status()
    assert data["enabled"] is False
    assert data["missing"] == ["SMTP_FROM"]


def test_environment_validation():
    s = settings_of(
        smtp_host="", smtp_password="", smtp_port="", share_links_enabled=""
    )
    assert s.smtp_host is None
    assert s.smtp_password is None
    assert s.smtp_port == 587
    assert s.share_links_enabled is False

    assert settings_of(smtp_port=465).smtp_security_effective == "ssl"
    assert settings_of(smtp_port=587).smtp_security_effective == "starttls"
    assert settings_of(smtp_security=" NONE ").smtp_security == "none"
    assert settings_of(smtp_from=" Bizview@Cliente.COM ").smtp_from == "bizview@cliente.com"
    assert settings_of(
        email_allowed_domains=" @Cliente.com, socio.com,cliente.com"
    ).email_domains == ["cliente.com", "socio.com"]
    assert settings_of(smtp_from_name="None").smtp_from_name == "None"

    for kwargs in [
        {"smtp_port": 0},
        {"smtp_port": 70000},
        {"smtp_security": "tls"},
        {"smtp_host": "smtp cliente"},
        {"smtp_user": "usuário"},
        {"smtp_user": "a\nb"},
        {"smtp_from": "a,b@cliente.com"},
        {"smtp_from_name": "a\r\nBcc: x@y.co"},
        {"email_allowed_domains": "cliente"},
        {"email_allowed_domains": ",".join(f"d{i}.com" for i in range(51))},
        {"smtp_password": "x" * 257},
        {"smtp_password": "a\nb"},
    ]:
        with pytest.raises(ValidationError):
            settings_of(**kwargs)

    secret = "Contraseña-Mk-Env-5a1"
    with pytest.raises(ValidationError) as exc:
        settings_of(smtp_password=secret)
    assert "Mk-Env-5a1" not in str(exc.value)
    assert "SMTP_PASSWORD" in str(exc.value)


def test_internet_profile_refuses_no_tls_at_start():
    base = dict(
        security_profile="internet",
        site_address="bi.cliente.com",
        cookie_secure=True,
        smtp_host="smtp.cliente.com",
        smtp_from="bizview@cliente.com",
        direct_reports_bi=False,   # 019's DIRECT_BI_ROLE rule is tested on its own
    )
    with pytest.raises(profile.ProfileError, match="SMTP_SECURITY"):
        profile.enforce_at_start(settings_of(**base, smtp_security="none"))
    profile.enforce_at_start(settings_of(**base, smtp_security="starttls"))
    profile.enforce_at_start(settings_of(security_profile="private", smtp_security="none"))


def test_status_flags_no_tls_in_internet_profile(monkeypatch):
    set_mail(**{**MAIL_ENV, "smtp_security": "none"})
    monkeypatch.setattr(get_settings(), "security_profile", "internet")
    assert mail_settings.status()["security_allowed"] is False
    monkeypatch.setattr(get_settings(), "security_profile", "private")
    assert mail_settings.status()["security_allowed"] is True


def test_cli_test_email_success(smtp):
    set_mail(**ENV)
    exit_code = cli.main(["mail-test", "root@example.com"])
    assert exit_code == 0
    assert len(smtp.sent) == 1
    assert smtp.sent[0]["To"] == "root@example.com"
    assert smtp.sent[0]["Subject"] == "Correo de prueba"
    conn = smtp.connections[0]
    assert conn["port"] == 587
    assert conn["starttls"] is True
    assert conn["login"] == ("bizview@cliente.com", PASSWORD_MARKER)
    rows = sql("SELECT kind, detail::text AS detail FROM audit_event")
    assert any(row[0] == "email_test_sent" and '"ok": true' in row[1] for row in rows)
    assert all(PASSWORD_MARKER not in (row[1] or "") for row in rows)


def test_test_email_requires_configuration(smtp):
    assert mail_settings.deliver_test("a@cliente.com") == "not_configured"
    assert cli.main(["mail-test", "a@cliente.com"]) == 1
    assert smtp.connections == []


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("auth", "auth_failed"),
        ("refused", "connection_failed"),
        ("timeout", "timeout"),
        ("tls", "tls_failed"),
        ("no_starttls", "tls_unavailable"),
    ],
)
def test_cli_test_email_failures_are_sanitized(smtp, caplog, mode, expected):
    caplog.set_level(logging.DEBUG)
    smtp.mode = mode
    set_mail(**ENV)
    exit_code = cli.main(["mail-test", "root@example.com"])
    assert exit_code == 1
    assert f"({expected})" in caplog.text
    assert mail_send.reason(expected) in caplog.text
    assert PASSWORD_MARKER not in caplog.text
    app_log = "".join(rec.getMessage() for rec in caplog.records if rec.name.startswith("app"))
    assert "smtp.cliente.com" not in app_log
    rows = sql(
        "SELECT detail::text FROM audit_event WHERE kind = 'email_test_sent' "
        "ORDER BY id DESC LIMIT 1"
    )
    assert rows and f'"reason": "{expected}"' in rows[0][0]


def test_ssl_by_port(smtp):
    set_mail(**{**ENV, "smtp_port": 465, "smtp_security": None})
    exit_code = cli.main(["mail-test", "root@example.com"])
    assert exit_code == 0
    conn = smtp.connections[0]
    assert conn["ssl"] is True
    assert conn["starttls"] is False


def test_non_ascii_password_test_email_sanitized(smtp, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    set_mail(**ENV)
    fragment = "Mk-Uni-7c2"
    monkeypatch.setattr(get_settings(), "smtp_password", SecretStr(f"Contraseña-{fragment}"))
    exit_code = cli.main(["mail-test", "root@example.com"])
    assert exit_code == 1
    assert "(auth_failed)" in caplog.text
    assert mail_send.reason("auth_failed") in caplog.text
    assert fragment not in caplog.text
    assert "Traceback" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    rows = sql(
        "SELECT detail::text FROM audit_event WHERE kind = 'email_test_sent' "
        "ORDER BY id DESC LIMIT 1"
    )
    assert rows and '"reason": "auth_failed"' in rows[0][0]
    assert fragment not in rows[0][0]


def test_no_smtp_settings_table():
    assert sql("SELECT to_regclass('email_settings')")[0][0] is None


def test_normalize_email_rejects_address_lists():
    for bad in [
        "root,postmaster,x@cliente.com",
        "a;b@cliente.com",
        "<a>b@cliente.com",
        "a b@cliente.com",
        '"a"@cliente.com',
        ".a@cliente.com",
        "a..b@cliente.com",
        ("a" * 65) + "@cliente.com",
    ]:
        assert mail_settings.normalize_email(bad) is None

    assert (
        mail_settings.normalize_email("Ana.Perez+ventas@Cliente.com")
        == "ana.perez+ventas@cliente.com"
    )
    assert mail_settings.normalize_email("o'brien@cliente.com") == "o'brien@cliente.com"


def test_internet_profile_refuses_stale_no_tls_at_send_time(monkeypatch, smtp):
    from app.mail import send as mail_send

    cfg = mail_send.SmtpConfig(
        host="smtp.cliente.com",
        port=25,
        security="none",
        username="u",
        password="p",
        sender_name=None,
        sender_address="bizview@cliente.com",
    )
    msg = mail_send.build_message(
        cfg=cfg,
        to="a@cliente.com",
        subject="x",
        organization="Org",
        product="BizView",
        dashboard_name="D",
        period_label=None,
        note=None,
        link_url=None,
        link_expires=None,
        attachment=None,
    )

    monkeypatch.setattr(get_settings(), "security_profile", "internet")
    with pytest.raises(mail_send.MailError) as exc_info:
        mail_send.deliver(cfg, msg)
    assert exc_info.value.code == "tls_required"
    assert exc_info.value.permanent is True
    assert smtp.connections == []

    monkeypatch.setattr(get_settings(), "security_profile", "private")
    mail_send.deliver(cfg, msg)
    assert len(smtp.sent) == 1
    assert smtp.envelopes[-1] == {"from": "bizview@cliente.com", "to": ["a@cliente.com"]}


def test_transport_maps_unicode_errors(smtp, monkeypatch):
    cfg = mail_send.SmtpConfig(
        host="smtp.cliente.com",
        port=587,
        security="starttls",
        username="bizview@cliente.com",
        password="pwñ",
        sender_name="Bizview",
        sender_address="bizview@cliente.com",
    )
    msg = mail_send.build_message(
        cfg=cfg,
        to="a@cliente.com",
        subject="x",
        organization="Org",
        product="BizView",
        dashboard_name="D",
        period_label=None,
        note=None,
        link_url=None,
        link_expires=None,
        attachment=None,
    )
    with pytest.raises(mail_send.MailError) as exc_info:
        mail_send.smtp_transport(cfg, msg)
    assert exc_info.value.code == "auth_failed"
    assert exc_info.value.permanent is True
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert "pwñ" not in str(exc_info.value)

    cfg = mail_send.SmtpConfig(
        host="smtp.cliente.com",
        port=587,
        security="starttls",
        username="bizview@cliente.com",
        password="ascii-pass",
        sender_name="Bizview",
        sender_address="bizview@cliente.com",
    )
    msg = mail_send.build_message(
        cfg=cfg,
        to="a@cliente.com",
        subject="x",
        organization="Org",
        product="BizView",
        dashboard_name="D",
        period_label=None,
        note=None,
        link_url=None,
        link_expires=None,
        attachment=None,
    )

    def boom(self, *args, **kwargs):
        raise ValueError("x")

    monkeypatch.setattr(smtplib.SMTP, "send_message", boom)
    with pytest.raises(mail_send.MailError) as exc_info:
        mail_send.smtp_transport(cfg, msg)
    assert exc_info.value.code == "smtp_error"
    assert exc_info.value.permanent is True


def test_logo_src():
    assert mail_send.logo_src(None, "http://h") is None
    assert mail_send.logo_src("", "http://h") is None
    assert mail_send.logo_src("  ", "http://h") is None
    assert mail_send.logo_src("/branding/logo.svg", "http://testserver") == (
        "http://testserver/branding/logo.svg"
    )
    assert mail_send.logo_src("/branding/logo.svg", "https://bi.cliente.com/") == (
        "https://bi.cliente.com/branding/logo.svg"
    )
    assert mail_send.logo_src("https://cdn.cliente.com/l.png", None) == (
        "https://cdn.cliente.com/l.png"
    )
    assert mail_send.logo_src("//evil.example/l.png", "http://h") is None
    assert mail_send.logo_src("javascript:alert(1)", "http://h") is None
    assert mail_send.logo_src("data:image/png;base64,AAA", "http://h") is None
    assert mail_send.logo_src("/branding/logo.svg", None) is None
    assert mail_send.logo_src("logo.svg", "http://h") is None


def test_test_email_includes_logo(smtp, monkeypatch):
    monkeypatch.setattr(get_settings(), "logo_url", "/branding/logo.svg")
    monkeypatch.setattr(get_settings(), "site_address", ":80")
    set_mail(**ENV)
    exit_code = cli.main(["mail-test", "root@example.com"])
    assert exit_code == 0
    html = smtp.sent[0].get_body(preferencelist=("html",)).get_content()
    assert '<img src="http://localhost/branding/logo.svg" alt="Cliente Demo"' in html
    plain = smtp.text(smtp.sent[0])
    assert "<img" not in plain

    cfg = mail_send.SmtpConfig(
        host="smtp.cliente.com",
        port=587,
        security="starttls",
        username="bizview@cliente.com",
        password="ascii-pass",
        sender_name="Bizview",
        sender_address="bizview@cliente.com",
    )
    msg = mail_send.build_message(
        cfg=cfg,
        to="a@cliente.com",
        subject="x",
        organization="Org",
        product="BizView",
        dashboard_name="D",
        period_label=None,
        note=None,
        link_url=None,
        link_expires=None,
        attachment=None,
    )
    html = msg.get_body(preferencelist=("html",)).get_content()
    assert "<img" not in html

    msg = mail_send.build_message(
        cfg=cfg,
        to="a@cliente.com",
        subject="x",
        organization='A & "B"',
        product="BizView",
        dashboard_name="D",
        period_label=None,
        note=None,
        link_url=None,
        link_expires=None,
        attachment=None,
        logo_url='https://x.example/l.png?a=1&b="2"',
    )
    html = msg.get_body(preferencelist=("html",)).get_content()
    assert 'src="https://x.example/l.png?a=1&amp;b=&quot;2&quot;"' in html
    assert 'alt="A &amp; &quot;B&quot;"' in html

