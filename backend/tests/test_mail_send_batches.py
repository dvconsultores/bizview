"""Delivery shape (feature 058, US1): no ceilings, batches, pacing, pause switch and sender mode.

What a sender sees is one send; what the provider sees is a handful of messages, spaced by
`EMAIL_SEND_RATE`, each carrying `EMAIL_BATCH_SIZE` recipients in BCC — or one message per address
when the installation asks for per-address bounce handling."""
import pytest

from app.mail import sends
from tests.conftest import MAIL_ENV, client, make_user, set_mail, signed_in, sql
from tests.fake_smtp import SmtpRecorder
from tests.test_mail_lists import create_list, members
from tests.test_mail_send import SEL, enable_mail, grant_user, send
from tests.test_runner import origin as origin
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import applied as applied
from tests.test_vibe_reporting import workspace as workspace


@pytest.fixture
def smtp(monkeypatch):
    recorder = SmtpRecorder()
    recorder.install(monkeypatch)
    return recorder


@pytest.fixture
def pact(monkeypatch):
    """The pacer's sleeps, recorded instead of waited, on a clock that only moves when it sleeps."""
    waits: list[float] = []
    clock = {"now": 1000.0}

    def fake_sleep(seconds: float) -> None:
        waits.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(sends, "sleep", fake_sleep)
    monkeypatch.setattr(sends.time, "monotonic", lambda: clock["now"])
    return waits


def many(count: int, domain: str = "cliente.com") -> list[str]:
    return [f"p{i}@{domain}" for i in range(count)]


def test_a_big_list_is_one_job_in_batches(applied, smtp, pact):
    """SC-002: 1.500 recipients (a list of 1.000 plus 500 addresses), ⌈1500/50⌉ = 30 messages."""
    enable_mail(domains=())
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "", "email_batch_size": 50,
                "email_send_rate": 0})
    c = signed_in("root@example.com")
    row = create_list(c, "Grande").json()
    # A list holds up to 1.000 members (FR-009); the send has no ceiling, so the rest are typed.
    assert c.put(f"/api/mail/lists/{row['id']}/members",
                 json={"members": members(*many(1000))}).status_code == 200

    r = send(c, lists=[row["id"]], emails=[f"q{i}@cliente.com" for i in range(500)])
    assert r.status_code == 201, r.text
    assert r.json()["count"] == 1500
    assert sql("SELECT count(*) FROM email_delivery")[0][0] == 1500

    assert sends.process_due() == 1500
    assert len(smtp.sent) == 30
    assert all(len(env["to"]) == 50 for env in smtp.envelopes)
    # The header shows the sender (the mail reads like a normal one) and the batch travels in BCC,
    # so a recipient never learns the others; the envelope carries the 50 addresses, not the sender.
    assert str(smtp.sent[0]["To"]) == "root@example.com"
    assert "p0@cliente.com" in str(smtp.sent[0]["Bcc"])
    assert "root@example.com" not in smtp.envelopes[0]["to"]
    assert pact == []                                     # rate 0: nothing is paced


def test_messages_are_paced(applied, smtp, pact):
    enable_mail(domains=())
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "", "email_batch_size": 5,
                "email_send_rate": 4})
    c = signed_in("root@example.com")
    row = create_list(c).json()
    c.put(f"/api/mail/lists/{row['id']}/members", json={"members": members(*many(15))})
    assert send(c, lists=[row["id"]]).status_code == 201

    assert sends.process_due() == 15
    assert len(smtp.sent) == 3
    # Two intervals between three messages, at most 1/4 s each (the recorder is faster than that,
    # so the pacer always asks to wait).
    assert len(pact) == 2
    assert all(0 < seconds <= 0.25 for seconds in pact)


def test_one_message_per_address_when_the_installation_asks(applied, smtp):
    enable_mail(domains=())
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "", "email_individual_messages": True,
                "email_send_rate": 0})
    c = signed_in("root@example.com")
    r = send(c, emails=many(4))
    assert r.status_code == 201
    assert sends.process_due() == 4
    assert len(smtp.sent) == 4
    assert [env["to"] for env in smtp.envelopes] == [[f"p{i}@cliente.com"] for i in range(4)]


def test_every_address_keeps_its_own_status_in_a_batch(applied, smtp):
    """A provider refusal marks the batch it was in, and the status is still per address."""
    enable_mail(domains=())
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "", "email_batch_size": 2,
                "email_send_rate": 0})
    c = signed_in("root@example.com")
    assert send(c, emails=many(4)).status_code == 201
    smtp.fail_times = 1                                   # the first message fails
    assert sends.process_due() == 4
    rows = dict(sql("SELECT status, count(*) FROM email_delivery GROUP BY 1"))
    # The batch that failed is re-queued with its backoff: the status is per address either way.
    assert rows == {"queued": 2, "sent": 2}
    assert sql("SELECT count(*) FROM email_delivery WHERE error IS NOT NULL")[0][0] == 2
    assert sql("SELECT count(*) FROM email_delivery WHERE attempts = 1")[0][0] == 4


def test_pausing_holds_the_queue_without_refusing(applied, smtp):
    enable_mail(domains=())
    c = signed_in("root@example.com")
    assert send(c, emails=["ana@cliente.com"]).status_code == 201
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "", "email_sending_paused": True})
    assert sends.process_due() == 0
    assert smtp.sent == []
    assert sql("SELECT status FROM email_delivery")[0][0] == "queued"
    assert c.get("/api/dashboards/ventas/email").json()["sending_paused"] is True
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "", "email_sending_paused": False})
    assert sends.process_due() == 1
    assert len(smtp.sent) == 1


def test_from_mode_installation_uses_the_installation_address(applied, smtp):
    enable_mail(domains=())
    set_mail(**{**MAIL_ENV, "email_allowed_domains": ""})
    c = signed_in("root@example.com")
    assert send(c, emails=["ana@cliente.com"]).status_code == 201
    sends.process_due()
    msg = smtp.sent[0]
    assert msg["From"].addresses[0].addr_spec == "bizview@cliente.com"
    assert msg["Reply-To"].addresses[0].addr_spec == "root@example.com"
    assert "Enviado por Super Usuario" in str(
        msg.get_body(preferencelist=("plain",)).get_content())


def test_from_mode_user_sends_as_the_sender(applied, smtp):
    enable_mail(domains=())
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "", "email_from_mode": "user"})
    c = signed_in("root@example.com")
    assert send(c, emails=["ana@cliente.com"]).status_code == 201
    sends.process_due()
    msg = smtp.sent[0]
    assert msg["From"].addresses[0].addr_spec == "root@example.com"
    assert msg["Reply-To"].addresses[0].addr_spec == "root@example.com"


def test_the_domain_filter_is_optional(applied, smtp):
    enable_mail(domains=())                              # EMAIL_ALLOWED_DOMAINS unset
    c = signed_in("root@example.com")
    assert send(c, emails=["quien@cualquier-dominio.example"]).status_code == 201
    # and when the installation sets it, it limits free addresses and list members alike
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "cliente.com"})
    r = send(c, emails=["quien@cualquier-dominio.example"])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["emails"] == "domain_not_allowed"
    row = create_list(c, "Externos").json()
    c.put(f"/api/mail/lists/{row['id']}/members", json={"members": members("x@otro.example")})
    r = send(c, lists=[row["id"]])
    assert r.status_code == 422
    assert r.json()["error"]["fields"]["emails"] == "domain_not_allowed"


def test_the_history_shows_the_kinds_and_lets_a_sender_resend_failures(applied, smtp):
    enable_mail(domains=())
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "", "email_batch_size": 1,
                "email_send_rate": 0})
    c = signed_in("root@example.com")
    r = send(c, emails=many(3))
    assert r.status_code == 201
    smtp.fail_for = {"p0@cliente.com": "recipient"}       # a permanent refusal, one address
    sends.process_due()
    send_id = r.json()["id"]

    history = c.get("/api/dashboards/ventas/email/sends").json()["items"]
    entry = next(item for item in history if item["id"] == send_id)
    assert entry["kinds"]["emails"] == 3
    assert entry["count"] == 3
    assert sum(1 for d in entry["deliveries"] if d["status"] == "failed") == 1

    r = c.post(f"/api/dashboards/ventas/email/sends/{send_id}/resend-failed")
    assert r.status_code == 201, r.text
    resent = r.json()
    assert resent["id"] != send_id
    assert resent["count"] == 1
    assert resent["kinds"]["resend_of"] == send_id
    smtp.fail_for = {}                                    # the address was fixed
    assert sends.process_due() == 1
    assert len(smtp.sent) == 3


def test_there_is_no_ceiling_and_no_throttle_anywhere(applied, smtp):
    """SC-003, the same promise twice: a big send and a burst of sends both go through."""
    enable_mail(domains=())
    set_mail(**{**MAIL_ENV, "email_allowed_domains": "", "email_send_rate": 0})
    c = signed_in("root@example.com")
    assert send(c, emails=many(64)).status_code == 201
    for _ in range(5):
        assert send(c, emails=["ana@cliente.com"]).status_code == 201
    assert sql("SELECT count(*) FROM email_send")[0][0] == 6
