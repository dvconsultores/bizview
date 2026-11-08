"""Every origin session is bounded, named and short-lived (feature 060).

The connection options are asserted on the arguments psycopg receives, so the test says what the
origin is told — not merely that a connection was made.
"""
import pytest

from app.config import Settings
from app.engine import extract


class Conn:
    closed = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def captured(monkeypatch):
    calls: list[dict] = []

    def connect(**kwargs):
        calls.append(kwargs)
        return Conn()

    monkeypatch.setattr(extract.postgresql, "connect_kwargs", lambda *_a, **_k: {
        "host": "erp.example", "port": 5432, "dbname": "erp", "user": "bizview",
        "password": "x", "sslmode": "require", "connect_timeout": 15,
        "application_name": "bizview", "options": "",
    })
    monkeypatch.setattr(extract.psycopg, "connect", connect)
    return calls


def test_the_session_is_named_after_the_integration_and_bounded(captured):
    extract._pg_connect({"host": "erp.example"}, {}, Settings(), timezone="UTC", time_limit_s=30,
                        integration="ventas-medicalvet")

    options = captured[0]["options"]
    assert captured[0]["application_name"] == "bizview-engine:ventas-medicalvet"
    assert "default_transaction_read_only=on" in options
    assert "statement_timeout=30000" in options
    assert "idle_in_transaction_session_timeout=30000" in options
    assert "idle_session_timeout=60000" in options
    # Ten seconds to connect, even though the source's own field says fifteen.
    assert captured[0]["connect_timeout"] == 10


def test_an_older_server_that_does_not_know_the_idle_timeouts_still_connects(captured, monkeypatch):
    first, second = True, {"done": False}
    conn = Conn()

    def connect(**kwargs):
        nonlocal first
        captured.append(kwargs)
        if first:
            first = False
            raise extract.psycopg.errors.InvalidParameterValue(
                "unrecognized configuration parameter \"idle_session_timeout\"")
        second["done"] = True
        return conn

    monkeypatch.setattr(extract.psycopg, "connect", connect)

    assert extract._pg_connect({"host": "erp.example"}, {}, Settings(), timezone="UTC",
                               time_limit_s=30) is conn
    assert len(captured) == 2
    assert "idle_session_timeout" in captured[0]["options"]
    assert "idle_session_timeout" not in captured[1]["options"]
    assert "default_transaction_read_only=on" in captured[1]["options"]
    assert second["done"] is True
