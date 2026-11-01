"""Feature 048 (FR-009): a direct report may store its figures once a day."""
from datetime import UTC, date, datetime, timedelta

import pytest

from app.engine import snapshot
from tests.conftest import sql

SELECTION = {"period": "mtd", "from": "2026-11-01", "to": "2026-11-01", "compare": "none"}


@pytest.fixture
def session():
    from app.db import get_sessionmaker

    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()


def payload(total: int = 10) -> dict:
    return {"selection": SELECTION, "views": [],
            "freshness": {"updated_at": "2026-11-01T10:00:00Z", "mode": "dataset",
                          "data_version": f"v{total}"}}


def test_the_figures_of_a_day_are_stored_once(session):
    snapshot.store(session, "ventas", selection=SELECTION, filters={}, payload=payload(10),
                   source="Almacén")
    session.commit()
    snapshot.store(session, "ventas", selection=SELECTION, filters={}, payload=payload(12),
                   source="Almacén")
    session.commit()
    assert sql("SELECT count(*) FROM direct_snapshot") == [(1,)]
    stored = snapshot.latest(session, "ventas", selection=SELECTION, filters={})
    assert stored is not None
    assert stored["payload"]["freshness"]["data_version"] == "v12"
    assert stored["day"] == datetime.now(UTC).date().isoformat()


def test_different_parameters_are_different_snapshots(session):
    snapshot.store(session, "ventas", selection=SELECTION, filters={"region": ["norte"]},
                   payload=payload(1), source="Almacén")
    snapshot.store(session, "ventas", selection=SELECTION, filters={"region": ["sur"]},
                   payload=payload(2), source="Almacén")
    session.commit()
    assert sql("SELECT count(*) FROM direct_snapshot") == [(2,)]
    north = snapshot.latest(session, "ventas", selection=SELECTION, filters={"region": ["norte"]})
    assert north["payload"]["freshness"]["data_version"] == "v1"
    assert snapshot.latest(session, "ventas", selection=SELECTION,
                           filters={"region": ["este"]}) is None


def test_the_newest_day_wins(session):
    snapshot.store(session, "ventas", selection=SELECTION, filters={}, payload=payload(1),
                   source="Almacén", day=date(2026, 10, 30))
    snapshot.store(session, "ventas", selection=SELECTION, filters={}, payload=payload(2),
                   source="Almacén", day=date(2026, 11, 1))
    session.commit()
    assert snapshot.latest(session, "ventas", selection=SELECTION,
                          filters={})["day"] == "2026-11-01"


def test_old_snapshots_are_pruned(session):
    old = datetime.now(UTC).date() - timedelta(days=snapshot.KEEP_DAYS + 1)
    snapshot.store(session, "ventas", selection=SELECTION, filters={}, payload=payload(1),
                   source="Almacén", day=old)
    snapshot.store(session, "ventas", selection=SELECTION, filters={}, payload=payload(2),
                   source="Almacén")
    session.commit()
    assert snapshot.prune(session) == 1
    session.commit()
    assert sql("SELECT count(*) FROM direct_snapshot") == [(1,)]


def test_a_stored_payload_says_how_old_it_is():
    labelled = snapshot.labelled(payload(), "2026-10-31")
    assert labelled["freshness"]["mode"] == "snapshot"
    assert labelled["freshness"]["snapshot_day"] == "2026-10-31"
    assert labelled["freshness"]["data_version"] == "v10"


def test_only_a_daily_direct_report_is_snapshotted():
    assert snapshot.is_daily({"materialize": "daily"}) is True
    assert snapshot.is_daily({"materialize": "none"}) is False
    assert snapshot.is_daily({}) is False
    assert snapshot.is_daily(None) is False
