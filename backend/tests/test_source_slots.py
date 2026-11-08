"""One ceiling of simultaneous origin sessions per source (feature 060).

The interesting half needs no database: the semaphore and its interruption. The cross-process slot is
one advisory lock on the product's own database, exercised against the test schema.
"""
import threading
import time

import pytest

from app.engine import source_slots


class Source:
    def __init__(self, kind: str = "postgresql", **settings) -> None:
        self.kind = kind
        self.settings = settings
        self.direct_reports = False
        self.bi_ready: dict = {}


@pytest.fixture(autouse=True)
def fresh_slots():
    source_slots.reset()
    yield
    source_slots.reset()


def test_the_defaults_protect_an_erp_origin():
    assert source_slots.limit_of(Source()) == 1
    assert source_slots.limit_of(Source("supabase")) == 2
    assert source_slots.limit_of(Source("rest")) == 4


def test_a_declared_ceiling_wins_and_a_bad_one_falls_back():
    assert source_slots.limit_of(Source(max_connections=5)) == 5
    assert source_slots.limit_of(Source(max_connections="quince")) == 1
    assert source_slots.limit_of(Source(max_connections=0)) == 1
    assert source_slots.limit_of(Source(max_connections=99)) == 1


def test_a_declared_warehouse_keeps_its_own_parallelism_for_direct_reads():
    source = Source()
    source.bi_ready = {"enabled": True, "schemas": ["ventas"], "max_parallel": 3}
    # Without an explicit `max_connections`, a BI-ready source is a warehouse, not the ERP origin.
    assert source_slots.limit_of(source, direct=True) == 3
    assert source_slots.limit_of(source) == 1
    source.settings["max_connections"] = 2
    assert source_slots.limit_of(source, direct=True) == 2


def test_two_tasks_on_one_lane_never_overlap():
    order: list[str] = []
    barrier = threading.Barrier(2, timeout=10)

    def work(name: str) -> None:
        barrier.wait()
        with source_slots.turn("erp", 1):
            order.append(f"{name}:in")
            time.sleep(0.15)
            order.append(f"{name}:out")

    threads = [threading.Thread(target=work, args=(n,)) for n in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    assert order in (["a:in", "a:out", "b:in", "b:out"], ["b:in", "b:out", "a:in", "a:out"])


def test_a_waiter_is_interruptible_and_leaves_the_lane_free():
    release = threading.Event()

    def hold() -> None:
        with source_slots.turn("erp", 1):
            release.wait(timeout=20)

    holder = threading.Thread(target=hold)
    holder.start()
    try:
        with pytest.raises(RuntimeError, match="stop"):
            with source_slots.turn("erp", 1, check=lambda: (_ for _ in ()).throw(
                    RuntimeError("stop"))):
                pass
    finally:
        release.set()
        holder.join(timeout=20)
    # The lane is free again: a third task gets it immediately.
    with source_slots.turn("erp", 1):
        assert True


def test_a_deadline_that_passes_fails_the_wait_instead_of_hanging():
    release = threading.Event()

    def hold() -> None:
        with source_slots.turn("erp", 1):
            release.wait(timeout=20)

    holder = threading.Thread(target=hold)
    holder.start()
    try:
        with pytest.raises(TimeoutError):
            with source_slots.turn("erp", 1, deadline=time.monotonic() + 0.3):
                pass
    finally:
        release.set()
        holder.join(timeout=20)


def test_an_exception_inside_the_turn_releases_the_lane():
    with pytest.raises(ValueError):
        with source_slots.turn("erp", 1):
            raise ValueError("boom")
    with source_slots.turn("erp", 1):
        assert True


def test_the_cross_process_slot_is_taken_and_given_back():
    """The advisory lock is what makes the ceiling hold between the worker and the API."""
    from app.db import get_engine

    source_slots.reset()
    with get_engine().connect() as conn:
        pg = conn.connection.driver_connection
        with source_slots.turn("erp-medicalvet", 1, pg=pg):
            held = pg.execute(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND granted").fetchone()[0]
            assert held >= 1
        after = pg.execute(
            "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND granted").fetchone()[0]
        assert after < held
