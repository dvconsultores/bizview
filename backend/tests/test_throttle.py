"""Feature 004: per-address sign-in throttling (FR-020, SC-005)."""
from datetime import UTC, datetime, timedelta

import pytest

from app.security import throttle
from tests.conftest import PASSWORD, client_from, make_user, sql


class Clock:
    def __init__(self):
        self._now = datetime(2026, 1, 5, 10, 7, 30, tzinfo=UTC)

    def set(self, value):
        self._now = value

    def advance(self, **kwargs):
        self._now = self._now + timedelta(**kwargs)


@pytest.fixture
def clock(monkeypatch):
    """Pin throttle's clock mid-window so 20 slow requests cannot straddle a window boundary."""
    holder = Clock()

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return holder._now

        @classmethod
        def fromtimestamp(cls, ts, tz=None):
            return datetime.fromtimestamp(ts, tz)

    monkeypatch.setattr(throttle, "datetime", FakeDateTime)
    return holder


def attempt(c, email, password="wrong-password-x"):
    return c.post("/api/auth/login", json={"email": email, "password": password})


def test_twenty_failures_across_accounts_block_the_address(clock, user):
    for i in range(3):
        make_user(f"u{i}@example.com")
    c = client_from("203.0.113.7")
    emails = [f"u{i % 3}@example.com" for i in range(12)] + [f"ghost{i}@example.com"
                                                             for i in range(8)]
    codes = [attempt(c, e).status_code for e in emails]
    assert 429 not in codes
    r = attempt(c, user.email, PASSWORD)                     # even the right password
    assert r.status_code == 429
    assert r.json()["error"]["retry_after_seconds"] == 451
    attempt(c, user.email)
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'login_rate_limited'")[0][0] == 1
    other = client_from("203.0.113.8")
    assert attempt(other, user.email, PASSWORD).status_code == 200


def test_throttle_window_expires(clock, user):
    c = client_from("198.51.100.4")
    for _ in range(20):
        attempt(c, "nobody@example.com")
    assert attempt(c, user.email, PASSWORD).status_code == 429
    clock.advance(minutes=16)
    assert attempt(c, user.email, PASSWORD).status_code == 200


def test_reauth_failures_count(clock, user):
    from tests.conftest import client_from as cf
    c = cf("192.0.2.10")
    assert c.post("/api/auth/login", json={"email": user.email,
                                           "password": PASSWORD}).status_code == 200
    for _ in range(4):
        assert c.post("/api/auth/reauth", json={"password": "wrong-pass-x"}).status_code == 401
    assert sql("SELECT failures FROM login_throttle WHERE ip = '192.0.2.10'")[0][0] == 4
