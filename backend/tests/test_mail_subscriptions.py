import re
from datetime import UTC, datetime, timedelta

import pytest

from app.config import get_settings
from app.db import get_sessionmaker
from app.mail import sends, subscriptions
from tests.conftest import MAIL_ENV, make_user, set_mail, signed_in, sql
from tests.fake_smtp import SmtpRecorder
from tests.test_runner import origin as origin
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import applied as applied
from tests.test_vibe_reporting import workspace as workspace


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
    user = make_user(
        email, role=role, full_name=name or email.split("@")[0], active=active
    )
    return grant_user(user.id)


def create_sub(c, **body):
    payload = {
        "frequency": "daily",
        "hour": 8,
        "period": "mtd",
        "attach_pdf": True,
        "users": [],
        "emails": ["gerente@cliente.com"],
    }
    payload.update(body)
    return c.post("/api/dashboards/ventas/subscriptions", json=payload)


def test_next_due_daily_weekly_monthly():
    tz = "America/Caracas"
    after = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)  # Monday 08:00 local
    assert subscriptions.next_due("daily", 9, None, None, after, tz) == datetime(
        2026, 10, 5, 13, 0, tzinfo=UTC
    )
    assert subscriptions.next_due("daily", 7, None, None, after, tz) == datetime(
        2026, 10, 6, 11, 0, tzinfo=UTC
    )
    assert subscriptions.next_due("weekly", 9, 0, None, after, tz) == datetime(
        2026, 10, 5, 13, 0, tzinfo=UTC
    )
    assert subscriptions.next_due("weekly", 7, 0, None, after, tz) == datetime(
        2026, 10, 12, 11, 0, tzinfo=UTC
    )
    assert subscriptions.next_due("weekly", 9, 4, None, after, tz) == datetime(
        2026, 10, 9, 13, 0, tzinfo=UTC
    )
    assert subscriptions.next_due("monthly", 9, None, 5, after, tz) == datetime(
        2026, 10, 5, 13, 0, tzinfo=UTC
    )
    assert subscriptions.next_due("monthly", 7, None, 5, after, tz) == datetime(
        2026, 11, 5, 11, 0, tzinfo=UTC
    )
    after2 = datetime(2026, 12, 15, 0, 0, tzinfo=UTC)
    result = subscriptions.next_due("monthly", 0, None, 1, after2, tz)
    assert result == datetime(2027, 1, 1, 4, 0, tzinfo=UTC)
    assert result > after2
    assert subscriptions.next_due("monthly", 0, None, 1, result, tz) > result


def test_crud_and_audit(applied, user):
    enable_mail()
    uid = grant_user(user.id)
    c = signed_in("root@example.com")
    r = create_sub(
        c,
        frequency="weekly",
        weekday=2,
        hour=8,
        period="last_7_days",
        users=[uid],
        emails=["gerente@cliente.com"],
    )
    assert r.status_code == 201
    sub = r.json()
    assert sub["frequency"] == "weekly"
    assert sub["weekday"] == 2
    assert sub["period_label"] == "Últimos 7 días"
    recipients = sub["recipients"]
    assert {"user_id": uid, "name": "Ulises Usuario"} in recipients
    assert {"email": "gerente@cliente.com"} in recipients
    assert datetime.fromisoformat(sub["next_due_at"]) > datetime.now(UTC)
    root_id = sql("SELECT id FROM app_user WHERE email = 'root@example.com'")[0][0]
    assert sub["created_by"]["id"] == root_id

    items = c.get("/api/dashboards/ventas/subscriptions").json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == sub["id"]

    r = c.patch(
        f"/api/dashboards/ventas/subscriptions/{sub['id']}", json={"paused": True}
    )
    assert r.status_code == 200
    assert r.json()["paused"] is True
    audit = sql(
        "SELECT detail::text FROM audit_event "
        "WHERE kind = 'email_subscription_updated' ORDER BY id DESC LIMIT 1"
    )
    assert audit and '"fields": ["paused"]' in audit[0][0]

    r = c.patch(
        f"/api/dashboards/ventas/subscriptions/{sub['id']}",
        json={"frequency": "monthly", "monthday": 3},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["frequency"] == "monthly"
    assert updated["weekday"] is None
    assert updated["monthday"] == 3
    assert updated["next_due_at"] != sub["next_due_at"]

    r = c.patch(
        f"/api/dashboards/ventas/subscriptions/{sub['id']}", json={"hour": None}
    )
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["hour"] == "required"

    r = c.delete(f"/api/dashboards/ventas/subscriptions/{sub['id']}")
    assert r.status_code == 204
    assert c.get("/api/dashboards/ventas/subscriptions").json()["items"] == []
    kinds = {row.kind for row in sql("SELECT kind FROM audit_event")}
    assert "email_subscription_created" in kinds
    assert "email_subscription_updated" in kinds
    assert "email_subscription_deleted" in kinds


def test_rules(applied, user):
    uid = grant_user(user.id)
    c = signed_in(user.email)
    assert c.get("/api/dashboards/ventas/subscriptions").status_code == 403
    assert create_sub(c, users=[uid]).status_code == 403

    c = signed_in("root@example.com")
    r = create_sub(c, users=[uid])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_unavailable"

    enable_mail()
    r = create_sub(c, users=[uid], period="custom")
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["period"] == "not_allowed"
    r = create_sub(c, users=[uid], period="ytd")
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["period"] == "not_allowed"
    r = create_sub(c, users=[uid], frequency="weekly")
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["weekday"] == "required"
    r = create_sub(c, users=[uid], link_days=7)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "sharing_disabled"
    r = create_sub(c, users=[uid], emails=["x@otro.com"])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["emails"] == "domain_not_allowed"

    dash_id = sql("SELECT id FROM dashboard WHERE code = 'ventas'")[0][0]
    creator = sql("SELECT id FROM app_user WHERE email = 'root@example.com'")[0][0]
    sql(
        "INSERT INTO email_subscription (dashboard_id, created_by, frequency, hour, "
        "period, next_due_at) SELECT :d, :u, 'daily', 8, 'mtd', now() + interval '1 day' "
        "FROM generate_series(1, 20)",
        d=dash_id,
        u=creator,
    )
    r = create_sub(c, users=[uid])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "too_many_subscriptions"


def test_tick_sends_once_and_advances(applied, smtp):
    enable_mail()
    c = signed_in("root@example.com")
    r = create_sub(c)
    assert r.status_code == 201
    sub_id = r.json()["id"]
    sql(
        "UPDATE email_subscription SET next_due_at = now() - interval '1 minute' "
        "WHERE id = :s",
        s=sub_id,
    )
    now = datetime.now(UTC)
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, now) == 1
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, now) == 0
    from app.worker import Worker

    assert Worker().email_subscriptions_tick(now=now, force=True) == 0
    rows = sql(
        "SELECT subscription_id, requested_by, subject FROM email_send"
    )
    assert len(rows) == 1
    assert rows[0].subscription_id == sub_id
    assert rows[0].requested_by == sql(
        "SELECT id FROM app_user WHERE email = 'root@example.com'"
    )[0][0]
    assert rows[0].subject == "Ventas · Mes en curso"
    sub = sql(
        "SELECT last_due_at, next_due_at FROM email_subscription WHERE id = :s",
        s=sub_id,
    )[0]
    assert sub.last_due_at is not None
    assert sub.next_due_at > now
    assert sends.process_due(now=now) == 1
    assert len(smtp.sent) == 1
    msg = smtp.sent[0]
    assert msg["To"] == "gerente@cliente.com"
    attachments = smtp.attachments(msg)
    assert len(attachments) == 1
    filename, content = attachments[0]
    assert filename.startswith("ventas-")
    assert b"Super Usuario" not in content


def test_concurrent_ticks_claim_once(applied):
    enable_mail()
    c = signed_in("root@example.com")
    r = create_sub(c)
    assert r.status_code == 201
    sql("UPDATE email_subscription SET next_due_at = now() - interval '1 minute'")
    now = datetime.now(UTC)
    s1 = get_sessionmaker()()
    s2 = get_sessionmaker()()
    try:
        a = subscriptions.tick(s1, now)
        b = subscriptions.tick(s2, now)
        s1.commit()
        s2.commit()
    finally:
        s1.close()
        s2.close()
    assert a == 1
    assert b == 0
    assert sql("SELECT count(*) FROM email_send")[0][0] == 1


def test_paused_subscription_not_sent(applied):
    enable_mail()
    c = signed_in("root@example.com")
    r = create_sub(c, paused=True)
    assert r.status_code == 201
    sql("UPDATE email_subscription SET next_due_at = now() - interval '1 minute'")
    now = datetime.now(UTC)
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, now) == 0
    assert sql("SELECT count(*) FROM email_send")[0][0] == 0


def test_deactivated_recipient_dropped(applied, user):
    enable_mail()
    uid = grant_user(user.id)
    c = signed_in("root@example.com")
    r = create_sub(c, users=[uid], emails=["gerente@cliente.com"])
    assert r.status_code == 201
    sql("UPDATE app_user SET is_active = false WHERE id = :u", u=uid)
    sql("UPDATE email_subscription SET next_due_at = now() - interval '1 minute'")
    now = datetime.now(UTC)
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, now) == 1
    rows = sql("SELECT recipient FROM email_delivery")
    assert [row.recipient for row in rows] == ["gerente@cliente.com"]

    sql("DELETE FROM email_delivery")
    sql("DELETE FROM email_send")
    c.delete(f"/api/dashboards/ventas/subscriptions/{r.json()['id']}")
    sql("UPDATE app_user SET is_active = true WHERE id = :u", u=uid)
    r = create_sub(c, users=[uid], emails=[])
    assert r.status_code == 201
    sub_id = r.json()["id"]
    sql("DELETE FROM dashboard_access WHERE user_id = :u", u=uid)
    sql(
        "UPDATE email_subscription SET next_due_at = now() - interval '1 minute' "
        "WHERE id = :s",
        s=sub_id,
    )
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, now) == 0
    assert sql("SELECT count(*) FROM email_send")[0][0] == 0
    sub = sql(
        "SELECT last_due_at, next_due_at FROM email_subscription WHERE id = :s",
        s=sub_id,
    )[0]
    assert sub.last_due_at is not None
    assert sub.next_due_at > now


def test_unpause_recomputes_next_due(applied):
    enable_mail()
    c = signed_in("root@example.com")
    r = create_sub(c)
    assert r.status_code == 201
    sub_id = r.json()["id"]
    r = c.patch(
        f"/api/dashboards/ventas/subscriptions/{sub_id}", json={"paused": True}
    )
    assert r.status_code == 200
    sql(
        "UPDATE email_subscription SET next_due_at = now() - interval '1 day' "
        "WHERE id = :s",
        s=sub_id,
    )
    r = c.patch(
        f"/api/dashboards/ventas/subscriptions/{sub_id}", json={"paused": False}
    )
    assert r.status_code == 200
    next_due = datetime.fromisoformat(r.json()["next_due_at"])
    assert next_due > datetime.now(UTC)
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, datetime.now(UTC)) == 0
    assert sql("SELECT count(*) FROM email_send")[0][0] == 0


def test_subscription_reuses_its_link(applied, smtp):
    from tests.conftest import client

    enable_mail(sharing=True)
    c = signed_in("root@example.com")
    r = create_sub(c, link_days=7)
    assert r.status_code == 201
    sub_id = r.json()["id"]

    def run() -> str:
        sql(
            "UPDATE email_subscription SET next_due_at = now() - interval '1 minute' "
            "WHERE id = :s",
            s=sub_id,
        )
        now = datetime.now(UTC)
        with get_sessionmaker().begin() as db:
            assert subscriptions.tick(db, now) == 1
        assert sends.process_due(now=now) == 1
        last = smtp.sent[-1]
        return re.search(r"/s/([A-Za-z0-9_-]+)", smtp.text(last)).group(1)

    token1 = run()
    assert token1
    rows = sql("SELECT count(*) FROM share_link")
    assert rows[0][0] == 1

    token2 = run()
    assert token2 == token1
    rows = sql("SELECT count(*) FROM share_link")
    assert rows[0][0] == 1
    sends_rows = sql("SELECT id, selection FROM email_send ORDER BY id")
    assert len(sends_rows) == 2
    first_selection = sends_rows[0][1]
    second_selection = sends_rows[1][1]
    assert "ct" not in first_selection["link"]
    assert first_selection["link"]["sub"] == sub_id
    assert "ct" in second_selection["link"]
    assert second_selection["link"]["sub"] == sub_id
    link_id = second_selection["link"]["id"]

    listing = c.get("/api/dashboards/ventas/links").json()
    assert listing["active_count"] == 0
    items = [i for i in listing["items"] if i["origin"] == "subscription"]
    assert len(items) == 1
    assert items[0]["counted"] is False
    for _ in range(20):
        r = c.post("/api/dashboards/ventas/links", json={"days": 7})
        assert r.status_code == 201
    r = c.post("/api/dashboards/ventas/links", json={"days": 7})
    assert r.status_code == 409

    sql(
        "UPDATE share_link SET expires_at = now() + interval '12 hours' "
        "WHERE id = :i",
        i=link_id,
    )
    token3 = run()
    assert token3 != token1
    listing = c.get("/api/dashboards/ventas/links").json()
    sub_items = [i for i in listing["items"] if i["origin"] == "subscription"]
    assert len(sub_items) == 2
    revoke_id = max(i["id"] for i in sub_items if i["active"] and i["id"] != link_id)
    r = c.delete(f"/api/dashboards/ventas/links/{revoke_id}")
    assert r.status_code == 204
    token4 = run()
    assert token4 not in (token1, token3)
    listing = c.get("/api/dashboards/ventas/links").json()
    sub_items = [i for i in listing["items"] if i["origin"] == "subscription"]
    assert len(sub_items) == 3
    rows = sql("SELECT count(*) FROM email_send WHERE selection->'link' ? 'ct'")
    assert rows[0][0] == 1
    assert client().get(f"/api/shared/{token4}").status_code == 200
    assert client().get(f"/api/shared/{token3}").status_code == 404


def test_deleting_subscription_strips_link_ciphertext(applied, smtp):
    enable_mail(sharing=True)
    c = signed_in("root@example.com")
    r = create_sub(c, link_days=7)
    assert r.status_code == 201
    sub = r.json()
    sql(
        "UPDATE email_subscription SET next_due_at = now() - interval '1 minute' "
        "WHERE id = :s",
        s=sub["id"],
    )
    now = datetime.now(UTC)
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, now) == 1
    assert sends.process_due(now=now) == 1
    rows = sql("SELECT selection FROM email_send")
    assert rows and "ct" in rows[0][0]["link"]

    r = c.delete(f"/api/dashboards/ventas/subscriptions/{sub['id']}")
    assert r.status_code == 204
    rows = sql("SELECT subscription_id, selection FROM email_send")
    assert rows
    assert rows[0][0] is None
    assert rows[0][1]["link"] == {"id": rows[0][1]["link"]["id"], "sub": sub["id"]}
    listing = c.get("/api/dashboards/ventas/links").json()
    items = [i for i in listing["items"] if i["origin"] == "subscription"]
    assert len(items) == 1


def test_list_carries_installation_timezone(applied, monkeypatch):
    monkeypatch.setattr(get_settings(), "timezone", "America/Caracas")
    enable_mail()
    c = signed_in("root@example.com")
    r = c.get("/api/dashboards/ventas/subscriptions")
    assert r.status_code == 200
    assert r.json()["timezone"] == "America/Caracas"


def test_pause_and_delete_while_email_is_off(applied):
    enable_mail()
    c = signed_in("root@example.com")
    r = create_sub(c)
    assert r.status_code == 201
    sub_id = r.json()["id"]

    set_mail(smtp_host=None)

    r = c.get("/api/dashboards/ventas/subscriptions")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert [item["id"] for item in body["items"]] == [sub_id]

    r = create_sub(c)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_unavailable"

    r = c.patch(f"/api/dashboards/ventas/subscriptions/{sub_id}", json={"paused": True})
    assert r.status_code == 200
    assert r.json()["paused"] is True

    r = c.delete(f"/api/dashboards/ventas/subscriptions/{sub_id}")
    assert r.status_code == 204

    r = c.get("/api/dashboards/ventas/subscriptions")
    assert r.status_code == 200
    assert r.json()["items"] == []

    r = c.get("/api/dashboards/ventas/email")
    assert r.status_code == 200
    assert r.json()["available"] is False


def _make_due(sub_id: int) -> None:
    sql(
        "UPDATE email_subscription SET next_due_at = now() - interval '1 minute' "
        "WHERE id = :s",
        s=sub_id,
    )


def test_scheduled_run_includes_link_and_pdf(applied, smtp):
    enable_mail(sharing=True)
    c = applied
    r = create_sub(c, link_days=5)
    assert r.status_code == 201
    sub_id = r.json()["id"]

    _make_due(sub_id)
    now = datetime.now(UTC)
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, now) == 1
    assert sends.process_due(now=now) == 1

    row = sql(
        "SELECT link_days, attach_pdf FROM email_send WHERE subscription_id = :s",
        s=sub_id,
    )[0]
    assert row.link_days == 5
    assert row.attach_pdf is True

    assert len(smtp.sent) == 1
    msg = smtp.sent[0]
    attachments = smtp.attachments(msg)
    assert len(attachments) == 1
    filename, content = attachments[0]
    assert filename.startswith("ventas-") and filename.endswith(".pdf")
    assert content.startswith(b"%PDF")

    text = smtp.text(msg)
    assert "/s/" in text
    assert "(el enlace vence el" in text
    token = re.search(r"/s/([A-Za-z0-9_-]+)", text).group(1)

    assert sql("SELECT COUNT(*) FROM share_link")[0][0] == 1
    link = sql("SELECT created_at, expires_at FROM share_link")[0]
    delta = link.expires_at - link.created_at
    assert abs(delta - timedelta(days=5)) < timedelta(seconds=60)

    from tests.conftest import client

    assert client().get(f"/api/shared/{token}").status_code == 200

    listing = c.get("/api/dashboards/ventas/links").json()
    assert len(listing["items"]) == 1
    assert listing["items"][0]["origin"] == "subscription"
    assert listing["items"][0]["counted"] is False
    assert listing["active_count"] == 0

    # Second run reuses the same token.
    _make_due(sub_id)
    now = datetime.now(UTC)
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, now) == 1
    assert sends.process_due(now=now) == 1
    assert len(smtp.sent) == 2
    text2 = smtp.text(smtp.sent[1])
    assert f"/s/{token}" in text2
    assert sql("SELECT COUNT(*) FROM share_link")[0][0] == 1


def test_scheduled_run_with_sharing_off_sends_pdf_only(applied, smtp):
    enable_mail(sharing=True)
    c = applied
    r = create_sub(c, link_days=7, attach_pdf=True)
    assert r.status_code == 201
    sub_id = r.json()["id"]

    enable_mail(sharing=False)

    _make_due(sub_id)
    now = datetime.now(UTC)
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, now) == 1

    row = sql(
        "SELECT link_days, attach_pdf FROM email_send WHERE subscription_id = :s",
        s=sub_id,
    )[0]
    assert row.link_days is None
    assert row.attach_pdf is True

    assert sends.process_due(now=now) == 1
    assert len(smtp.sent) == 1
    msg = smtp.sent[0]
    attachments = smtp.attachments(msg)
    assert len(attachments) == 1
    filename, content = attachments[0]
    assert filename.startswith("ventas-") and filename.endswith(".pdf")
    assert content.startswith(b"%PDF")
    assert "/s/" not in smtp.text(msg)
    assert sql("SELECT COUNT(*) FROM share_link")[0][0] == 0


def test_scheduled_link_only_skipped_when_sharing_off(applied, smtp):
    enable_mail(sharing=True)
    c = applied
    r = create_sub(c, attach_pdf=False, link_days=7)
    assert r.status_code == 201
    sub_id = r.json()["id"]

    enable_mail(sharing=False)

    _make_due(sub_id)
    now = datetime.now(UTC)
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, now) == 0

    assert sql("SELECT COUNT(*) FROM email_send")[0][0] == 0
    sub = sql(
        "SELECT last_due_at, next_due_at FROM email_subscription WHERE id = :s",
        s=sub_id,
    )[0]
    assert sub.last_due_at is not None
    assert sub.next_due_at > now

    assert sends.process_due(now=now) == 0
    assert len(smtp.sent) == 0
    assert sql("SELECT COUNT(*) FROM share_link")[0][0] == 0


def test_pause_resume_with_sharing_off(applied):
    enable_mail(sharing=True)
    c = applied
    r = create_sub(c, link_days=7)
    assert r.status_code == 201
    sub_id = r.json()["id"]

    enable_mail(sharing=False)

    r = c.patch(f"/api/dashboards/ventas/subscriptions/{sub_id}", json={"paused": True})
    assert r.status_code == 200
    assert r.json()["paused"] is True

    sql(
        "UPDATE email_subscription SET next_due_at = :due WHERE id = :s",
        due=datetime.now(UTC) - timedelta(days=1),
        s=sub_id,
    )

    r = c.patch(f"/api/dashboards/ventas/subscriptions/{sub_id}", json={"paused": False})
    assert r.status_code == 200
    assert r.json()["paused"] is False
    assert datetime.fromisoformat(r.json()["next_due_at"]) > datetime.now(UTC)

    rows = sql("SELECT link_days FROM email_subscription WHERE id = :s", s=sub_id)
    assert rows[0].link_days == 7

    r = c.patch(f"/api/dashboards/ventas/subscriptions/{sub_id}", json={"link_days": 3})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "sharing_disabled"

    r = c.patch(f"/api/dashboards/ventas/subscriptions/{sub_id}", json={"hour": 9})
    assert r.status_code == 200


def test_pause_resume_with_unavailable_recipients(applied, user):
    enable_mail()
    uid = grant_user(user.id)
    c = applied
    r = create_sub(c, users=[uid], emails=["gerente@cliente.com"])
    assert r.status_code == 201
    sub_id = r.json()["id"]

    sql("UPDATE app_user SET is_active = false WHERE id = :u", u=uid)
    enable_mail(domains=("otro.com",))

    r = c.patch(f"/api/dashboards/ventas/subscriptions/{sub_id}", json={"paused": True})
    assert r.status_code == 200
    assert r.json()["paused"] is True

    r = c.patch(f"/api/dashboards/ventas/subscriptions/{sub_id}", json={"paused": False})
    assert r.status_code == 200
    assert r.json()["paused"] is False

    rows = sql("SELECT recipients FROM email_subscription WHERE id = :s", s=sub_id)
    assert rows[0].recipients == [{"user_id": uid}, {"email": "gerente@cliente.com"}]

    r = c.patch(f"/api/dashboards/ventas/subscriptions/{sub_id}", json={"hour": 9})
    assert r.status_code == 422


def test_period_label_and_auto_subject_follow_the_viewer(applied, smtp):
    """022 T049/T050: subscription period and automatic send subjects in the viewer's language."""
    enable_mail()
    c = signed_in("root@example.com")
    sub_id = create_sub(c, period="last_7_days").json()["id"]
    assert c.patch("/api/me/preferences", json={"locale": "en"}).status_code == 200
    listed = c.get("/api/dashboards/ventas/subscriptions").json()["items"]
    assert next(s for s in listed if s["id"] == sub_id)["period_label"] == "Last 7 days"

    sql("UPDATE email_subscription SET next_due_at = now() - interval '1 minute' WHERE id = :s",
        s=sub_id)
    with get_sessionmaker().begin() as db:
        assert subscriptions.tick(db, datetime.now(UTC)) == 1
    assert sql("SELECT subject FROM email_send")[0].subject == "Ventas · Últimos 7 días"
    history = c.get("/api/dashboards/ventas/email").json()["items"]
    assert [s["subject"] for s in history] == ["Ventas · Last 7 days"]
    assert c.patch("/api/me/preferences", json={"locale": "es"}).status_code == 200
    history = c.get("/api/dashboards/ventas/email").json()["items"]
    assert [s["subject"] for s in history] == ["Ventas · Últimos 7 días"]
