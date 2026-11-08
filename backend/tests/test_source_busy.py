"""A connection-slot refusal is its own condition, and a run waits it out (feature 060).

No database: the classifier, the backoff and the connect retry are exercised against exceptions and
a fake origin, which is exactly the shape the production incident had.
"""
import time

import psycopg
import pytest

from app.config import Settings
from app.engine import busy, extract, runner


class Busy(psycopg.OperationalError):
    """An origin refusing the connection the way PostgreSQL does when it is full."""

    def __init__(self, message: str, sqlstate: str = "53300") -> None:
        super().__init__(message)
        self.sqlstate = sqlstate


def test_too_many_clients_is_recognised_from_the_sqlstate():
    error = Busy('FATAL: lo siento, ya tenemos demasiados clientes')
    classified = extract.busy_of(error)
    assert classified is not None
    assert classified.sqlstate == "53300"
    assert "demasiados clientes" in classified.detail


@pytest.mark.parametrize("sqlstate", ["53200", "57P03", "08001", "08006"])
def test_the_sibling_sqlstates_are_busy_too(sqlstate):
    assert extract.busy_of(Busy("anything", sqlstate)) is not None


@pytest.mark.parametrize("text", [
    "FATAL: sorry, too many clients already",
    "no more connections allowed (max_client_conn)",
    "server_login_retry",
    "FATAL: remaining connection slots are reserved for non-replication superuser connections",
])
def test_a_pooler_refusal_without_a_sqlstate_is_recognised_by_its_words(text):
    classified = extract.busy_of(psycopg.OperationalError(text))
    assert classified is not None
    assert classified.sqlstate is None
    assert classified.detail


@pytest.mark.parametrize("error", [
    psycopg.OperationalError("connection refused"),
    psycopg.OperationalError("timeout expired"),
    psycopg.errors.QueryCanceled("canceling statement due to statement timeout"),
    psycopg.errors.InsufficientPrivilege("permission denied for table ventas"),
    psycopg.errors.DataError("invalid input syntax for type integer"),
    ValueError("not a database error"),
])
def test_every_other_failure_keeps_its_own_meaning(error):
    assert extract.busy_of(error) is None


def test_the_backoff_is_exponential_with_jitter():
    delays = busy.delays(4, 15)
    assert len(delays) == 3
    # 15 s, 45 s, 2 min — each within ±20 % of the step it belongs to.
    for got, expected in zip(delays, (15, 45, 135), strict=True):
        assert expected * 0.8 <= got <= expected * 1.2
    assert busy.delays(1, 15) == []


def test_a_wait_is_cut_short_by_a_stop_request():
    calls = {"n": 0}

    def check():
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("stopped")

    started = time.monotonic()
    with pytest.raises(RuntimeError, match="stopped"):
        busy.wait(300, check=check)
    assert time.monotonic() - started < 5


def test_a_wait_stops_at_the_deadline_instead_of_overrunning_it():
    assert busy.wait(300, deadline=time.monotonic() + 0.2, sleep=lambda _s: None) in (True, False)


def _source(settings=None):
    class Source:
        kind = "postgresql"
        settings = {"host": "10.175.123.46", "database": "erp", "username": "bizview"}
        secrets: dict = {}

    return Source()


def test_two_refusals_then_success_end_with_three_attempts(monkeypatch):
    attempts = {"n": 0}

    class Conn:
        pass

    def fake_connect(*_args, **_kwargs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise extract.SourceBusy("53300", "FATAL: sorry, too many clients already")
        return Conn()

    monkeypatch.setattr(extract, "_pg_connect", fake_connect)
    slept: list[float] = []
    conn, record = runner._open_origin(_source(), {}, Settings(),
                                       integration_id="ventas-medicalvet",
                                       tz="UTC", deadline=time.monotonic() + 600,
                                       check=lambda: None,
                                       wait=lambda s, **_k: slept.append(s) or True)
    assert isinstance(conn, Conn)
    assert record["attempts"] == 3 and record["sqlstate"] == "53300"
    assert attempts["n"] == 3
    assert len(slept) == 2     # the two waits before the third attempt


def test_every_attempt_refused_reports_what_happened(monkeypatch):
    def fake_connect(*_args, **_kwargs):
        raise extract.SourceBusy("53300", "FATAL: lo siento, ya tenemos demasiados clientes")

    monkeypatch.setattr(extract, "_pg_connect", fake_connect)
    with pytest.raises(runner.OriginBusy) as caught:
        runner._open_origin(_source(), {}, Settings(), integration_id="ventas-medicalvet",
                            tz="UTC", deadline=time.monotonic() + 600,
                            check=lambda: None, wait=lambda *_a, **_k: True)
    record = caught.value.record
    assert record["attempts"] == 4
    assert record["sqlstate"] == "53300"
    assert record["waited_s"] >= 0
    assert "demasiados clientes" in record["detail"]
    assert "10.175.123.46" not in record["detail"]


def test_a_wait_past_the_run_deadline_ends_busy_rather_than_killed(monkeypatch):
    monkeypatch.setattr(extract, "_pg_connect",
                        lambda *_a, **_k: (_ for _ in ()).throw(
                            extract.SourceBusy("53300", "too many clients")))
    with pytest.raises(runner.OriginBusy):
        runner._open_origin(_source(), {}, Settings(), integration_id="x", tz="UTC",
                            deadline=time.monotonic(), check=lambda: None,
                            wait=lambda *_a, **_k: False)


def test_the_connection_funnel_turns_the_driver_error_into_a_busy(monkeypatch):
    monkeypatch.setattr(extract.postgresql, "connect_kwargs", lambda *_a, **_k: {
        "host": "erp.example", "port": 5432, "dbname": "erp", "user": "bizview",
        "password": "x", "sslmode": "require", "application_name": "", "options": "",
    })

    def refuse(**_kwargs):
        raise Busy("FATAL: sorry, too many clients already")

    monkeypatch.setattr(extract.psycopg, "connect", refuse)
    source = _source()
    with pytest.raises(extract.SourceBusy) as caught:
        extract._pg_connect(source.settings, {}, Settings(), timezone="UTC", time_limit_s=30)
    assert caught.value.sqlstate == "53300"
    assert "10.175.123.46" not in caught.value.detail


def test_the_application_name_names_the_integration():
    assert extract.app_name("ventas-medicalvet") == "bizview-engine:ventas-medicalvet"
    assert extract.app_name(None) == "bizview-engine"
    assert len(extract.app_name("x" * 100)) == extract.APP_NAME_MAX


def test_the_session_options_hold_a_slot_for_less_time():
    assert "idle_in_transaction_session_timeout=30000" in extract.IDLE_OPTIONS
    assert "idle_session_timeout=60000" in extract.IDLE_OPTIONS


def test_the_wait_in_words_is_shared_by_both_languages():
    assert runner.wait_words(45) == "45 s"
    assert runner.wait_words(420) == "7 min"
