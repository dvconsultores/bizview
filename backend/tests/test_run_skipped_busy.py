"""A busy origin pauses the run: `skipped_busy`, no data touched, one notification per streak.

The "origin" is the pattern `test_runner.py` established: the BI database read through a read-only
session, here with `_pg_connect` refusing on cue. What is asserted is the contract of the incident —
the run is amber, the data and its freshness are untouched, and the operators are told once.
"""
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import extract, runner
from app.models import AuditEvent, IntegrationRun

from tests.conftest import sql
from tests.test_runner import NOW, TZ, ds_sql, ds_table, integration, lines  # noqa: F401

BUSY = 'FATAL: lo siento, ya tenemos demasiados clientes'


@pytest.fixture
def origin(superuser):
    """The same fixture `test_runner` uses: a PostgreSQL source reading this schema's table."""
    from sqlalchemy.engine import make_url

    from app.db import get_engine
    from app.engine import datasets
    from app.models import AppUser
    from app.sources import service as sources

    url = make_url(get_settings().database_url_bi)
    with get_sessionmaker().begin() as db:
        actor = db.get(AppUser, superuser.id)
        sources.create(db, actor, {
            "name": "Origen prueba", "kind": "postgresql",
            "settings": {"host": url.host, "port": url.port or 5432, "database": url.database,
                         "username": url.username, "sslmode": "prefer", "timeout_seconds": 15},
            "secrets": {"password": url.password}}, get_settings(), None)
    sql("DROP TABLE IF EXISTS origin_sales")
    sql("CREATE TABLE origin_sales (doc text, line int, kind text, completed_at timestamptz, "
        "amount numeric, product text)")
    from datetime import timedelta
    rows = [("A1", 1, "sale", NOW - timedelta(days=1), "10.50", "P1"),
            ("A1", 2, "sale", NOW - timedelta(days=1), "4.25", "P2"),
            ("A2", 1, "return", NOW - timedelta(days=2), "3", "P1")]
    for r in rows:
        sql("INSERT INTO origin_sales VALUES (:d, :l, :k, :t, CAST(:a AS numeric), :p)",
            d=r[0], l=r[1], k=r[2], t=r[3], a=r[4], p=r[5])
    yield
    with get_engine().begin() as c:
        datasets.drop_integration(c.connection.driver_connection, "ventas-prueba")
    sql("DROP TABLE IF EXISTS origin_sales")


def refuse(*_args, **_kwargs):
    raise extract.SourceBusy("53300", BUSY)


def run(**over):
    definition, files = integration(**over)
    return runner.run_integration(definition, files, version_id=None, kind="incremental", now=NOW)


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    """The schedule is asserted in `test_source_busy`; here the waits must not cost minutes."""
    monkeypatch.setattr(runner.busy, "wait", lambda *_a, **_k: True)


def busy_runs() -> list[IntegrationRun]:
    with get_sessionmaker()() as db:
        return list(db.scalars(select(IntegrationRun).where(
            IntegrationRun.status == "skipped_busy").order_by(IntegrationRun.id)))


def audit_events() -> list[AuditEvent]:
    with get_sessionmaker()() as db:
        return list(db.scalars(select(AuditEvent).where(
            AuditEvent.kind == "integration_busy")))


def test_a_busy_origin_ends_skipped_busy_with_the_origin_words(origin, monkeypatch):
    monkeypatch.setattr(extract, "_pg_connect", refuse)

    r = run()

    assert r.status == "skipped_busy"
    assert "no admite más conexiones" in r.message
    assert "4 intentos" in r.message
    assert "demasiados clientes" in r.message
    assert r.busy["sqlstate"] == "53300"
    assert r.busy["attempts"] == 4
    assert r.busy["waited_s"] >= 0
    # No credential and no host anywhere in what is stored and shown.
    get_settings().product_name  # noqa: B018 - keeps the settings import honest
    assert "10.175" not in r.message and "password" not in (r.busy or {})


def freshness() -> tuple[str, object]:
    """What a report's `data_version` is derived from: the last *successful* run of the integration."""
    return ds_sql("SELECT count(*), max(finished_at) FROM integration_run "
                  "WHERE integration_id = 'ventas-prueba' AND status = 'succeeded'")[0]


def test_a_busy_run_leaves_the_data_and_its_freshness_untouched(origin, monkeypatch):
    assert run().status == "succeeded"
    before_rows = lines()
    before_freshness = freshness()
    before_runs = ds_sql("SELECT count(*) FROM integration_run WHERE status = 'succeeded'")[0][0]

    monkeypatch.setattr(extract, "_pg_connect", refuse)
    busy = run()

    assert busy.status == "skipped_busy"
    assert lines() == before_rows
    # Freshness is the last successful load: the busy run is not one, so nothing moves.
    assert freshness() == before_freshness
    assert ds_sql("SELECT count(*) FROM integration_run WHERE status = 'succeeded'")[0][0] == before_runs


def test_retrying_then_succeeding_is_a_normal_success(origin, monkeypatch):
    real = extract._pg_connect
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise extract.SourceBusy("53300", BUSY)
        return real(*args, **kwargs)

    monkeypatch.setattr(extract, "_pg_connect", flaky)

    r = run()

    assert r.status == "succeeded", r.message
    assert calls["n"] == 3
    # The retry record survives on a successful run too: the history explains the delay.
    assert r.busy["attempts"] == 3


def _busy_row(status: str = "skipped_busy", *, started: datetime | None = None,
              integration: str = "ventas-prueba") -> IntegrationRun:
    """A finished run row of the integration, without paying for a real load."""
    from app.engine.runner import _finish  # noqa: F401 - the shape is what matters

    with get_sessionmaker().begin() as db:
        run = IntegrationRun(integration_id=integration, kind="incremental", status=status,
                             started_at=started or datetime.now(UTC),
                             finished_at=datetime.now(UTC),
                             busy={"sqlstate": "53300", "attempts": 4, "waited_s": 285,
                                   "detail": BUSY})
        db.add(run)
        db.flush()
    return run


def notify(run: IntegrationRun, integration: str = "ventas-prueba") -> bool:
    with get_sessionmaker()() as db:
        return runner.busy.notify_if_due(db, db.get(IntegrationRun, run.id), integration)


def test_three_consecutive_busy_runs_notify_once_and_a_fourth_stays_quiet(monkeypatch):
    told = [notify(_busy_row()), notify(_busy_row()), notify(_busy_row()), notify(_busy_row())]

    assert told == [False, False, True, False]
    events = audit_events()
    assert len(events) == 1
    assert events[0].detail["integration"] == "ventas-prueba"
    assert events[0].detail["streak"] == 3
    assert events[0].detail["sqlstate"] == "53300"


def test_a_run_that_is_not_busy_closes_the_streak_and_the_next_one_is_announced_again():
    for _ in range(3):
        notify(_busy_row())
    assert len(audit_events()) == 1

    _busy_row("succeeded")
    with get_sessionmaker()() as db:
        assert runner.busy.streak(db, "ventas-prueba") == 0

    told = [notify(_busy_row()) for _ in range(3)]
    assert told == [False, False, True]
    assert len(audit_events()) == 2


def test_a_stopped_run_neither_extends_nor_resets_the_streak():
    notify(_busy_row())
    _busy_row("stopped")
    notify(_busy_row())
    told = notify(_busy_row())
    assert told is True
    assert len(audit_events()) == 1
    with get_sessionmaker()() as db:
        assert runner.busy.streak(db, "ventas-prueba") == 3


def test_the_hint_names_the_hour_the_origin_was_quiet():
    now = datetime.now(UTC)
    # Two busy runs at one hour, one at another: the emptiest hour is the one with a single run.
    for hour in (3, 3, 3, 14):
        _busy_row(started=now.replace(hour=hour, minute=5, second=0, microsecond=0))
    with get_sessionmaker()() as db:
        hint = runner.busy.hint(db, "ventas-prueba", tz="UTC", now=now)
    assert hint["busy_today"] == 4
    assert hint["quiet_hour"] == 14


def test_no_hint_without_enough_history():
    now = datetime.now(UTC)
    for _ in range(2):
        _busy_row(started=now.replace(hour=9, minute=0, second=0, microsecond=0))
    with get_sessionmaker()() as db:
        hint = runner.busy.hint(db, "ventas-prueba", tz="UTC", now=now)
    assert hint["busy_today"] == 2
    assert hint["quiet_hour"] is None
