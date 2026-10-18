import logging
import re
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.config import get_settings
from app.db import get_sessionmaker
from app.errors import ApiError
from app.mail import sends
from app.models import AppUser, Dashboard
from tests.conftest import MAIL_ENV, client, make_user, set_mail, signed_in, sql
from tests.fake_smtp import SmtpRecorder
from tests.test_runner import origin as origin
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import SELECTION
from tests.test_vibe_reporting import applied as applied
from tests.test_vibe_reporting import workspace as workspace

MARKER = "Mk-Smtp-Send-8f1"
SEL = {
    "period": "custom",
    "from": "2026-09-27",
    "to": "2026-09-28",
    "compare": "previous_period",
}


@pytest.fixture
def smtp(monkeypatch):
    recorder = SmtpRecorder()
    recorder.install(monkeypatch)
    return recorder


def enable_mail(*, domains=("cliente.com",), sharing=False):
    set_mail(
        **{
            **MAIL_ENV,
            "email_allowed_domains": ",".join(domains),
            "share_links_enabled": sharing,
        }
    )


def grant_user(uid: int) -> int:
    dash_id = sql("SELECT id FROM dashboard WHERE code = 'ventas'")[0][0]
    sql(
        "INSERT INTO dashboard_access (user_id, dashboard_id, granted_by) "
        "VALUES (:u, :d, :u)",
        u=uid,
        d=dash_id,
    )
    return uid


def grant(email, *, role="user", name=None, active=True) -> int:
    user = make_user(email, role=role, full_name=name or email.split("@")[0], active=active)
    return grant_user(user.id)


def send(c, **body):
    payload = {"selection": SEL, **body}
    return c.post("/api/dashboards/ventas/email", json=payload)


def test_options_and_unavailable(applied, user):
    uid = grant_user(user.id)
    c = signed_in(user.email)
    data = c.get("/api/dashboards/ventas/email").json()
    assert data["available"] is False
    r = send(c, users=[uid])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_unavailable"
    enable_mail()
    data = c.get("/api/dashboards/ventas/email").json()
    assert data["available"] is True
    assert data["can_link"] is False
    assert data["allowed_domains"] == ["cliente.com"]
    outsider = make_user("outsider@example.com")
    r = signed_in(outsider.email).get("/api/dashboards/ventas/email")
    assert r.status_code == 403
    r = signed_in(outsider.email).post(
        "/api/dashboards/ventas/email", json={"selection": SEL, "users": [uid]}
    )
    assert r.status_code == 403


def test_recipient_rules(applied, user):
    enable_mail()
    c = signed_in("root@example.com")
    r = send(c, emails=["x@otro.com"])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["emails"] == "domain_not_allowed"
    r = send(c, emails=["not-an-email"])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["emails"] == "invalid"
    outsider = make_user("outsider2@example.com")
    r = send(c, users=[outsider.id])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["users"] == "no_access"
    inactive_id = grant("inactive@example.com", active=False)
    r = send(c, users=[inactive_id])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["users"] == "no_access"
    r = send(c)
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["recipients"] == "empty"
    r = send(c, emails=[f"p{i}@cliente.com" for i in range(21)])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["recipients"] == "too_many"
    assert sql("SELECT count(*) FROM email_send")[0][0] == 0


def test_link_only_for_admins_and_needs_sharing(applied, user, smtp):
    enable_mail()
    uid = grant_user(user.id)
    c = signed_in(user.email)
    r = send(c, users=[uid], link_days=7)
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["link_days"] == "admins_only"
    c = signed_in("root@example.com")
    r = send(c, users=[uid], link_days=7)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "sharing_disabled"
    r = send(c, users=[uid], attach_pdf=False)
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["attach_pdf"] == "nothing_to_send"
    r = send(c, users=[uid], selection={"bogus": "1"})
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["selection"] == "invalid"
    r = send(c, users=[uid], selection={"period": "ytd"})
    assert r.status_code == 422


def test_rate_limit_per_user(applied, user):
    enable_mail()
    uid = grant_user(user.id)
    dash_id = sql("SELECT id FROM dashboard WHERE code = 'ventas'")[0][0]
    sql(
        "INSERT INTO email_send (dashboard_id, requested_by, subject) "
        "SELECT :d, :u, 'x' FROM generate_series(1, 30)",
        d=dash_id,
        u=uid,
    )
    r = signed_in(user.email).post(
        "/api/dashboards/ventas/email", json={"selection": SEL, "users": [uid]}
    )
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"


def test_send_delivers_pdf_equal_to_download(applied, smtp):
    enable_mail()
    admin_id = grant("admin2@example.com", role="admin", name="Admin Dos")
    user_id = grant("user2@example.com", name="User Dos")
    c = signed_in("root@example.com")
    r = send(c, users=[user_id, admin_id], emails=["gerente@cliente.com"])
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "queued"
    assert len(data["deliveries"]) == 3
    assert all(d["status"] == "queued" and d["attempts"] == 0 for d in data["deliveries"])
    audit = sql("SELECT detail::text FROM audit_event WHERE kind = 'email_sent'")
    assert audit and '"recipients": 3' in audit[0][0]
    assert sends.process_due() == 3
    assert len(smtp.sent) == 3
    expected_recipients = {
        "user2@example.com",
        "admin2@example.com",
        "gerente@cliente.com",
    }
    assert set(smtp.recipients()) == expected_recipients
    download = applied.post(f"/api/reports/ventas/pdf?{SELECTION}")
    for msg in smtp.sent:
        attachments = smtp.attachments(msg)
        assert len(attachments) == 1
        filename, content = attachments[0]
        assert filename == "ventas-2026-09-27-2026-09-28.pdf"
        assert content == download.content
        assert msg["Subject"] == "Ventas"
        assert "bizview@cliente.com" in msg["From"]
        assert "Período: Personalizado" in smtp.text(msg)
    data = c.get("/api/dashboards/ventas/email").json()
    assert data["items"][0]["status"] == "sent"
    deliveries = data["items"][0]["deliveries"]
    assert all(d["status"] == "sent" and d["sent_at"] for d in deliveries)
    assert sends.process_due() == 0
    assert len(smtp.sent) == 3


def test_message_and_link(applied, smtp):
    enable_mail(sharing=True)
    c = signed_in("root@example.com")
    r = send(
        c,
        emails=["gerente@cliente.com"],
        message="Hola equipo\nRevisen",
        link_days=3,
    )
    assert r.status_code == 201
    assert sends.process_due() == 1
    assert len(smtp.sent) == 1
    msg = smtp.sent[0]
    text = smtp.text(msg)
    assert "Hola equipo" in text
    assert "http://testserver/s/" in text
    assert "(el enlace vence el" in text
    rows = sql("SELECT note FROM share_link")
    assert rows and rows[0][0].startswith("Correo: ")
    token = re.search(r"/s/([A-Za-z0-9_-]+)", text).group(1)
    assert client().get(f"/api/shared/{token}").status_code == 200


def test_transient_failures_retry_then_fail(applied, smtp, caplog):
    caplog.set_level(logging.DEBUG)
    enable_mail()
    smtp.mode = "server_text"
    c = signed_in("root@example.com")
    send(c, emails=["gerente@cliente.com"])
    t0 = datetime.now(UTC)
    assert sends.process_due(now=t0) == 1
    row = sql(
        "SELECT status, attempts, error, next_attempt_at FROM email_delivery"
    )[0]
    assert row.status == "queued"
    assert row.attempts == 1
    assert row.error == "El servidor de correo devolvió un error."
    assert row.next_attempt_at <= t0 + timedelta(minutes=1, seconds=2)
    assert sends.process_due(now=t0 + timedelta(seconds=30)) == 0
    assert sends.process_due(now=t0 + timedelta(minutes=2)) == 1
    row = sql("SELECT attempts FROM email_delivery")[0]
    assert row.attempts == 2
    assert sends.process_due(now=t0 + timedelta(minutes=10)) == 1
    row = sql("SELECT status, attempts, error, next_attempt_at FROM email_delivery")[0]
    assert row.status == "queued"
    assert row.attempts == 3
    assert row.next_attempt_at > t0 + timedelta(minutes=24)
    assert sends.process_due(now=t0 + timedelta(minutes=15)) == 0
    assert sends.process_due(now=t0 + timedelta(minutes=30)) == 1
    row = sql("SELECT status, attempts, error FROM email_delivery")[0]
    assert row.status == "failed"
    assert row.attempts == 4
    send_row = sql("SELECT status, finished_at FROM email_send")[0]
    assert send_row.status == "failed"
    assert send_row.finished_at is not None
    assert "password" not in row.error
    assert "451" not in row.error
    assert "password=" not in caplog.text


def test_retry_succeeds_and_partial(applied, smtp):
    enable_mail()
    c = signed_in("root@example.com")
    send(c, emails=["a@cliente.com", "b@cliente.com"])
    smtp.fail_for = {"b@cliente.com": "recipient"}
    assert sends.process_due() == 2
    rows = {
        r.recipient: r.status
        for r in sql("SELECT recipient, status FROM email_delivery")
    }
    assert rows["a@cliente.com"] == "sent"
    assert rows["b@cliente.com"] == "failed"
    send_row = sql("SELECT status FROM email_send")[0]
    assert send_row.status == "partial"


def test_retry_succeeds_after_transient(applied, smtp):
    enable_mail()
    smtp.fail_times = 1
    c = signed_in("root@example.com")
    send(c, emails=["a@cliente.com"])
    t0 = datetime.now(UTC)
    assert sends.process_due(now=t0) == 1
    row = sql("SELECT status, attempts FROM email_delivery")[0]
    assert row.status == "queued"
    assert row.attempts == 1
    assert sends.process_due(now=t0 + timedelta(minutes=2)) == 1
    row = sql("SELECT status FROM email_delivery")[0]
    assert row.status == "sent"
    send_row = sql("SELECT status FROM email_send")[0]
    assert send_row.status == "sent"


def test_access_rechecked_at_send_time(applied, user, smtp):
    enable_mail()
    uid = grant_user(user.id)
    c = signed_in("root@example.com")
    send(c, users=[uid])
    sql("DELETE FROM dashboard_access WHERE user_id = :u", u=uid)
    assert sends.process_due() == 1
    row = sql(
        "SELECT status, error FROM email_delivery ORDER BY id DESC LIMIT 1"
    )[0]
    assert row.status == "skipped"
    assert row.error == "El destinatario ya no tiene acceso al tablero."

    r = send(c, users=[uid])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["users"] == "no_access"

    requester_id = grant("requester@example.com", name="Requester")
    requester_c = signed_in("requester@example.com")
    send(requester_c, users=[requester_id])
    sql("DELETE FROM dashboard_access WHERE user_id = :u", u=requester_id)
    assert sends.process_due() == 1
    row = sql(
        "SELECT status, error FROM email_delivery ORDER BY id DESC LIMIT 1"
    )[0]
    assert row.status == "skipped"
    assert row.error == "Quien pidió el envío ya no tiene acceso al tablero."

    uid2 = grant("inactive2@example.com", name="Inactive")
    c = signed_in("root@example.com")
    send(c, users=[uid2])
    sql("UPDATE app_user SET is_active = false WHERE id = :u", u=uid2)
    assert sends.process_due() == 1
    row = sql(
        "SELECT status, error FROM email_delivery ORDER BY id DESC LIMIT 1"
    )[0]
    assert row.status == "skipped"
    assert row.error == "El destinatario ya no tiene acceso al tablero."


def test_mail_switched_off_waits(applied, smtp):
    enable_mail()
    c = signed_in("root@example.com")
    send(c, emails=["gerente@cliente.com"])
    set_mail(smtp_host=None)
    assert sends.process_due() == 1
    assert not smtp.sent
    row = sql("SELECT status, attempts FROM email_delivery")[0]
    assert row.status == "queued"
    assert row.attempts == 0
    set_mail(smtp_host="smtp.cliente.com")
    t0 = datetime.now(UTC)
    assert sends.process_due(now=t0 + timedelta(minutes=2)) == 1
    assert len(smtp.sent) == 1


def test_listing_scoped_to_requester(applied, user, smtp):
    enable_mail()
    uid = grant_user(user.id)
    c = signed_in(user.email)
    send(c, users=[uid])
    c = signed_in("root@example.com")
    send(c, emails=["gerente@cliente.com"])
    c = signed_in(user.email)
    items = c.get("/api/dashboards/ventas/email").json()["items"]
    assert len(items) == 1
    assert items[0]["requested_by"]["id"] == uid
    c = signed_in("root@example.com")
    items = c.get("/api/dashboards/ventas/email").json()["items"]
    assert len(items) == 2
    opts = c.get("/api/dashboards/ventas/email/recipients").json()["items"]
    assert all("email" in item for item in opts)
    assert any(item["name"] == "Super Usuario" for item in opts)
    c = signed_in(user.email)
    opts = c.get("/api/dashboards/ventas/email/recipients").json()["items"]
    assert all("email" not in item for item in opts)
    opts = c.get("/api/dashboards/ventas/email/recipients?q=ulis").json()["items"]
    assert len(opts) == 1
    assert opts[0]["name"] == "Ulises Usuario"


def test_smtp_password_never_leaks(applied, smtp, caplog):
    caplog.set_level(logging.DEBUG)
    enable_mail()
    set_mail(smtp_user="bizview@cliente.com", smtp_password=MARKER)
    smtp.mode = "auth"
    c = signed_in("root@example.com")
    send(c, emails=["gerente@cliente.com"])
    t0 = datetime.now(UTC)
    assert sends.process_due(now=t0) == 1
    assert len(smtp.connections) == 1
    row = sql("SELECT status, error FROM email_delivery")[0]
    assert row.status == "failed"
    assert row.error == "El servidor de correo rechazó el usuario o la contraseña."
    assert MARKER not in c.get("/api/dashboards/ventas/email").text
    assert MARKER not in caplog.text
    for table in ("email_delivery", "email_send", "audit_event", "share_link"):
        rows = sql(f"SELECT row_to_json(x)::text FROM {table} x")
        assert all(MARKER not in row[0] for row in rows)


def test_worker_method_delivers(applied, smtp):
    from app.worker import Worker

    enable_mail()
    c = signed_in("root@example.com")
    send(c, emails=["gerente@cliente.com"])
    worker = Worker()
    future = worker.take_email_sends(force=True)
    future.result(timeout=60)
    worker.pool.shutdown(wait=True)
    assert len(smtp.sent) == 1


def test_link_created_once_across_retries(applied, smtp):
    enable_mail(sharing=True)
    smtp.fail_times = 1
    c = signed_in("root@example.com")
    r = send(c, emails=["a@cliente.com"], message="Hola", link_days=3, attach_pdf=False)
    assert r.status_code == 201
    t0 = datetime.now(UTC)
    assert sends.process_due(now=t0) == 1
    assert sends.process_due(now=t0 + timedelta(minutes=2)) == 1
    assert len(smtp.sent) == 1
    assert sql("SELECT count(*) FROM share_link")[0][0] == 1
    token = re.search(r"/s/([A-Za-z0-9_-]+)", smtp.text(smtp.sent[0])).group(1)
    assert client().get(f"/api/shared/{token}").status_code == 200
    sel = sql("SELECT selection->'link' FROM email_send")[0][0]
    assert "ct" not in sel
    assert "id" in sel


def test_no_link_when_all_recipients_skipped(applied, user, smtp):
    enable_mail(sharing=True)
    uid = grant_user(user.id)
    c = signed_in("root@example.com")
    send(c, users=[uid], link_days=3)
    sql("DELETE FROM dashboard_access WHERE user_id = :u", u=uid)
    assert sends.process_due() == 1
    assert sql("SELECT count(*) FROM share_link")[0][0] == 0
    assert sql("SELECT status FROM email_delivery")[0][0] == "skipped"


def test_revoked_email_link_fails_retries(applied, smtp):
    from app.mail import send as mail_send

    enable_mail(sharing=True)
    smtp.fail_times = 1
    c = signed_in("root@example.com")
    send(c, emails=["a@cliente.com"], message="Hola", link_days=3, attach_pdf=False)
    t0 = datetime.now(UTC)
    assert sends.process_due(now=t0) == 1
    sql("UPDATE share_link SET revoked_at = now()")
    assert sends.process_due(now=t0 + timedelta(minutes=2)) == 1
    row = sql("SELECT status, error FROM email_delivery")[0]
    assert row.status == "failed"
    assert row.error == mail_send.reason("link_unavailable")
    assert sql("SELECT count(*) FROM share_link")[0][0] == 1


def test_email_links_count_toward_active_limit(applied, smtp):
    enable_mail(sharing=True)
    c = signed_in("root@example.com")
    for _ in range(19):
        r = c.post("/api/dashboards/ventas/links", json={"days": 7})
        assert r.status_code == 201
    r = send(c, emails=["a@cliente.com"], link_days=3, attach_pdf=False)
    assert r.status_code == 201
    r = c.get("/api/dashboards/ventas/links")
    assert r.status_code == 200
    listing = r.json()
    assert listing["active_count"] == 20
    r = c.get("/api/dashboards/ventas/email")
    assert r.status_code == 200
    options = r.json()
    assert options["links_active"] == 20
    assert options["links_max"] == 20
    r = c.post("/api/dashboards/ventas/links", json={"days": 7})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "too_many_links"
    r = send(c, emails=["b@cliente.com"], link_days=3, attach_pdf=False)
    assert r.status_code == 409
    error = r.json()["error"]
    assert error["code"] == "too_many_links"
    assert error["fields"] == {"link_days": "too_many_links"}
    r = send(c, emails=["c@cliente.com"], attach_pdf=True)
    assert r.status_code == 201
    assert sends.process_due() == 2
    linked = next(m for m in smtp.sent if m["To"] == "a@cliente.com")
    assert "/s/" in smtp.text(linked)
    r = c.get("/api/dashboards/ventas/links")
    listing = r.json()
    assert listing["active_count"] == 20
    items = listing["items"]
    assert len([i for i in items if i["active"]]) == 20
    assert sum(1 for i in items if i["origin"] == "email" and i["counted"]) == 1
    assert sum(1 for i in items if i["origin"] == "manual" and i["counted"]) == 19
    email_item = next(i for i in items if i["origin"] == "email")
    r = c.delete(f"/api/dashboards/ventas/links/{email_item['id']}")
    assert r.status_code == 204
    r = c.post("/api/dashboards/ventas/links", json={"days": 7})
    assert r.status_code == 201
    r = c.post("/api/dashboards/ventas/links", json={"days": 7})
    assert r.status_code == 409


def test_selection_params_limits():
    from app.errors import ApiError

    sel = {
        "period": "mtd",
        "compare": "previous_period",
        "filter.a": [f"v{i}" for i in range(30)],
        "filter.b": [f"v{i}" for i in range(30)],
    }
    pairs = sends.selection_params(sel)
    assert len(pairs) == 62

    sel51 = {"filter.a": [f"v{i}" for i in range(51)]}
    with pytest.raises(ApiError) as exc_info:
        sends.selection_params(sel51)
    assert exc_info.value.status == 422

    sel_period = {"period": ["2024-01", "2023-01"]}
    with pytest.raises(ApiError):
        sends.selection_params(sel_period)

    sel_keys = {f"filter.k{i}": ["v"] for i in range(21)}
    with pytest.raises(ApiError):
        sends.selection_params(sel_keys)


def test_worker_non_ascii_password_fails_without_traceback(applied, smtp, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    from app.mail import send as mail_send

    enable_mail()
    fragment = "Mk-Wrk-3d9"
    set_mail(smtp_user="bizview@cliente.com")
    monkeypatch.setattr(
        get_settings(), "smtp_password", SecretStr(f"Contraseña-{fragment}")
    )
    c = signed_in("root@example.com")
    r = send(c, emails=["gerente@cliente.com"])
    assert r.status_code == 201
    assert sends.process_due() == 1
    rows = sql("SELECT status, attempts, error FROM email_delivery")
    assert rows
    assert rows[0] == ("failed", 1, mail_send.reason("auth_failed"))
    rows = sql("SELECT status FROM email_send")
    assert rows and rows[0][0] == "failed"
    assert not smtp.sent
    assert "Traceback" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    assert fragment not in caplog.text
    r = c.get("/api/dashboards/ventas/email")
    assert fragment not in r.text


def test_email_html_includes_logo(applied, smtp, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "logo_url", "/branding/logo.svg")
    enable_mail(sharing=True)
    c = signed_in("root@example.com")
    r = send(c, emails=["gerente@cliente.com"], link_days=3)
    assert r.status_code == 201
    assert sends.process_due() == 1
    html = smtp.sent[0].get_body(preferencelist=("html",)).get_content()
    assert '<img src="http://testserver/branding/logo.svg" alt="Cliente Demo"' in html
    assert "<img" not in smtp.text(smtp.sent[0])
    monkeypatch.setattr(get_settings(), "logo_url", "")
    r = send(c, emails=["otro@cliente.com"], attach_pdf=True)
    assert r.status_code == 201
    assert sends.process_due() == 1
    html = smtp.sent[1].get_body(preferencelist=("html",)).get_content()
    assert "<img" not in html


def test_rate_limit_serialized_per_user(applied, user):
    enable_mail()
    uid = grant_user(user.id)
    sql(
        "INSERT INTO email_send (dashboard_id, requested_by, subject) "
        "SELECT d.id, :u, 'x' FROM dashboard d, generate_series(1, 29) "
        "WHERE d.code = 'ventas'",
        u=uid,
    )
    barrier = threading.Barrier(2)
    results: list[str] = []

    def worker():
        db = get_sessionmaker()()
        try:
            actor = db.get(AppUser, uid)
            dash = db.scalar(select(Dashboard).where(Dashboard.code == "ventas"))
            barrier.wait(timeout=60)
            try:
                sends.queue_send(
                    db,
                    actor,
                    dash,
                    user_ids=[uid],
                    emails=[],
                    subject=None,
                    message=None,
                    selection=SEL,
                    attach_pdf=True,
                    link_days=None,
                    ip=None,
                )
                time.sleep(0.3)
                db.commit()
                results.append("ok")
            except ApiError as e:
                db.rollback()
                results.append(str(e.status))
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert all(not t.is_alive() for t in threads)
    assert sorted(results) == ["429", "ok"]
    rows = sql("SELECT count(*) FROM email_send WHERE requested_by = :u", u=uid)
    assert rows and rows[0][0] == 30


def test_large_pdf_without_link_fails(applied, smtp, monkeypatch):
    enable_mail()
    c = signed_in("root@example.com")

    from app.mail import send as mail_send

    monkeypatch.setattr(
        sends.pdf,
        "render",
        lambda *args, **kwargs: b"%PDF-1.4\n" + b"0" * mail_send.MAX_ATTACHMENT,
    )

    r = send(c, emails=["gerente@cliente.com"])
    assert r.status_code == 201

    assert sends.process_due() == 1
    assert len(smtp.sent) == 0

    row = sql(
        "SELECT status, error FROM email_delivery ORDER BY id DESC LIMIT 1"
    )[0]
    assert row.status == "failed"
    assert row.error == mail_send.reason("too_large")
    assert sql("SELECT status FROM email_send")[0][0] == "failed"
    assert sql("SELECT COUNT(*) FROM share_link")[0][0] == 0


def test_large_pdf_with_link_sends_link_only(applied, smtp, monkeypatch):
    enable_mail(sharing=True)
    c = signed_in("root@example.com")

    from app.mail import send as mail_send

    monkeypatch.setattr(
        sends.pdf,
        "render",
        lambda *args, **kwargs: b"%PDF-1.4\n" + b"0" * mail_send.MAX_ATTACHMENT,
    )

    r = send(c, emails=["gerente@cliente.com"], message="Hola equipo", link_days=3)
    assert r.status_code == 201

    assert sends.process_due() == 1
    assert len(smtp.sent) == 1

    msg = smtp.sent[0]
    assert smtp.attachments(msg) == []
    text = smtp.text(msg)
    assert "http://testserver/s/" in text

    token = re.search(r"/s/([A-Za-z0-9_-]+)", text).group(1)
    assert client().get(f"/api/shared/{token}").status_code == 200

    row = sql(
        "SELECT status, error FROM email_delivery ORDER BY id DESC LIMIT 1"
    )[0]
    assert row.status == "sent"
    assert row.error is None


def test_recipients_get_their_language(applied, smtp):
    enable_mail()
    en_id = grant("english@example.com", name="English User")
    sql("UPDATE app_user SET locale = 'en' WHERE id = :i", i=en_id)
    es_id = grant("spanish@example.com", name="Spanish User")

    c = signed_in("root@example.com")
    r = send(c, users=[en_id, es_id], emails=["gerente@cliente.com"])
    assert r.status_code == 201
    assert sends.process_due() == 3

    by_to = {msg["To"]: msg for msg in smtp.sent}

    en_msg = by_to["english@example.com"]
    en_text = smtp.text(en_msg)
    assert "Period: Custom" in en_text
    assert "Please find the dashboard PDF attached." in en_text
    assert "Sent by" in en_text
    assert "Período" not in en_text
    assert "Adjuntamos" not in en_text

    es_msg = by_to["spanish@example.com"]
    es_text = smtp.text(es_msg)
    assert "Período: Personalizado" in es_text
    assert "Adjuntamos el tablero en PDF." in es_text

    ext_msg = by_to["gerente@cliente.com"]
    ext_text = smtp.text(ext_msg)
    assert "Período: Personalizado" in ext_text
    assert "Adjuntamos el tablero en PDF." in ext_text

    en_att = smtp.attachments(en_msg)
    es_att = smtp.attachments(es_msg)
    ext_att = smtp.attachments(ext_msg)
    assert en_att[0][0] == "ventas-2026-09-27-2026-09-28.pdf"
    assert en_att[0][1] != es_att[0][1]
    assert es_att[0][1] == ext_att[0][1]
