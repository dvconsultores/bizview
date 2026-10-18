"""Feature 018 (FR-013): `python -m app.cli mail-test <address>` checks the SMTP_* settings."""
import logging

import pytest

from app import cli
from tests.conftest import MAIL_ENV, set_mail, sql

PASSWORD = "Mk-Cli-Pass-9d1"


@pytest.fixture
def smtp(monkeypatch):
    from tests.fake_smtp import SmtpRecorder

    recorder = SmtpRecorder()
    recorder.install(monkeypatch)
    return recorder


def mail_env(**overrides):
    values = {**MAIL_ENV, **overrides}
    return set_mail(**values)


def cli_log_text(caplog):
    return "\n".join(
        rec.getMessage() for rec in caplog.records if rec.name.startswith("app.cli")
    )


def last_test_audit() -> str:
    return sql(
        "SELECT detail::text FROM audit_event WHERE kind = 'email_test_sent' "
        "ORDER BY id DESC LIMIT 1"
    )[0][0]


def test_mail_test_success(caplog, smtp):
    mail_env(smtp_user="bizview@cliente.com", smtp_password=PASSWORD)
    caplog.set_level(logging.DEBUG)
    assert cli.main(["mail-test", "ana@cliente.com"]) == 0
    assert len(smtp.sent) == 1
    assert smtp.sent[0]["To"] == "ana@cliente.com"
    assert smtp.sent[0]["Subject"] == "Correo de prueba"
    assert "test email sent to ana@cliente.com" in caplog.text
    row = last_test_audit()
    assert '"via": "cli"' in row
    assert '"ok": true' in row
    assert PASSWORD not in caplog.text
    for (detail,) in sql("SELECT detail::text FROM audit_event"):
        assert PASSWORD not in (detail or "")


def test_mail_test_normalizes_address(caplog, smtp):
    mail_env(smtp_user="bizview@cliente.com", smtp_password=PASSWORD)
    caplog.set_level(logging.DEBUG)
    assert cli.main(["mail-test", " Ana@Cliente.COM "]) == 0
    assert len(smtp.sent) == 1
    assert smtp.sent[0]["To"] == "ana@cliente.com"


@pytest.mark.parametrize(
    "mode,code",
    [
        ("auth", "auth_failed"),
        ("refused", "connection_failed"),
        ("timeout", "timeout"),
        ("tls", "tls_failed"),
    ],
)
def test_mail_test_failures(caplog, smtp, mode, code):
    from app.mail.send import reason

    mail_env(smtp_user="bizview@cliente.com", smtp_password=PASSWORD)
    smtp.mode = mode
    caplog.set_level(logging.DEBUG)
    assert cli.main(["mail-test", "ana@cliente.com"]) == 1
    log_text = cli_log_text(caplog)
    assert f"({code})" in log_text
    assert reason(code) in log_text
    assert PASSWORD not in log_text
    assert PASSWORD not in caplog.text
    assert "smtp.cliente.com" not in log_text
    assert "Traceback" not in caplog.text
    assert f'"reason": "{code}"' in last_test_audit()


def test_mail_test_not_configured(caplog, smtp):
    caplog.set_level(logging.DEBUG)
    assert cli.main(["mail-test", "ana@cliente.com"]) == 1
    assert len(smtp.connections) == 0
    log_text = cli_log_text(caplog)
    assert "SMTP_HOST" in log_text
    assert "SMTP_FROM" in log_text


def test_mail_test_partially_configured(caplog, smtp):
    set_mail(smtp_host="smtp.cliente.com")
    caplog.set_level(logging.DEBUG)
    assert cli.main(["mail-test", "ana@cliente.com"]) == 1
    assert len(smtp.connections) == 0
    log_text = cli_log_text(caplog)
    assert "set SMTP_FROM in" in log_text
    assert "SMTP_HOST" not in log_text


def test_mail_test_invalid_address(caplog, smtp):
    mail_env(smtp_user="bizview@cliente.com", smtp_password=PASSWORD)
    caplog.set_level(logging.DEBUG)
    assert cli.main(["mail-test", "no-es-correo"]) == 1
    assert cli.main(["mail-test", "a@x.com,b@y.com"]) == 1
    assert len(smtp.connections) == 0
    log_text = cli_log_text(caplog)
    assert "no-es-correo" not in log_text
    assert "a@x.com,b@y.com" not in log_text


def test_mail_test_missing_address(caplog, smtp):
    mail_env()
    caplog.set_level(logging.DEBUG)
    assert cli.main(["mail-test"]) == 1
    assert len(smtp.connections) == 0
    assert "mail-test needs one email address" in cli_log_text(caplog)
