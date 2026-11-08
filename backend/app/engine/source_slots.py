"""One ceiling of simultaneous origin sessions per source (feature 060).

An origin database is somebody else's system: its `max_connections` is shared with the application
that owns it, and the reported production incident was that application taking every slot. BizView
therefore never opens more sessions on one source than that source declares
(`settings["max_connections"]`, default 1 for a PostgreSQL origin and 2 for a hosted API), whatever
the work is — a scheduled run, a manual one, a structure scan, `describe` or a direct read.

Two bounds, applied together:

* a process-wide semaphore per `(source, limit)`, which bounds the worker's threads and the API's;
* a cross-process slot on the product's own database — `pg_try_advisory_lock` on a namespace of its
  own — so the worker and the API cannot each take the ceiling at the same time. It uses a
  connection the caller already holds (the runner's integration lock), never a new one.

With more than one API replica the semaphore is per replica; `docs/INSTALL.md` says so. The run path,
which is the one that filled the origin, is exact because of the advisory slot.
"""
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import psycopg
from psycopg import sql

#: What an installation gets without configuring anything: the tightest value that still lets a
#: PostgreSQL origin be read (one session, reused across the datasets of a run), and the two a
#: hosted API source can use without tripping its own rate limiter.
DEFAULTS: dict[str, int] = {"postgresql": 1, "supabase": 2, "rest": 4, "soap": 4}
FALLBACK = 1
MIN, MAX = 1, 20
#: How often a waiter for the cross-process slot asks again, and checks for a stop request.
POLL_SECONDS = 0.5
NS = "source:"

_semaphores: dict[tuple[str, int], threading.BoundedSemaphore] = {}
_lock = threading.Lock()


def limit_of(source, *, direct: bool = False) -> int:
    """The source's declared ceiling, or the default of its kind; a bad value never raises.

    An explicit `max_connections` always wins. Without one, a source that a super user declared
    BI-ready (048) keeps the concurrency its own declaration names for direct reads — it is a
    warehouse, not the ERP origin this default protects — and everything else gets the kind's
    default.
    """
    settings = getattr(source, "settings", None) or {}
    raw = settings.get("max_connections") if isinstance(settings, dict) else None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = None
    if value is not None and MIN <= value <= MAX:
        return value
    default = DEFAULTS.get(getattr(source, "kind", ""), FALLBACK)
    if direct and "max_connections" not in settings:
        declared = _declared_parallel(source)
        if declared is not None:
            return max(default, declared)
    return default


def _declared_parallel(source) -> int | None:
    """The `max_parallel` of a source's BI-ready declaration, when it has one."""
    from app.sources import bi_ready

    try:
        if not bi_ready.enabled(source):
            return None
        return int(bi_ready.limits(source).get("max_parallel") or 0) or None
    except Exception:
        return None


def _semaphore(key: str, limit: int) -> threading.BoundedSemaphore:
    with _lock:
        sem = _semaphores.get((key, limit))
        if sem is None:
            sem = threading.BoundedSemaphore(limit)
            _semaphores[(key, limit)] = sem
        return sem


def free(key: str, limit: int) -> bool:
    """Whether a permit is instantly available — for a message, never for a decision."""
    sem = _semaphore(key, limit)
    if sem.acquire(blocking=False):
        sem.release()
        return True
    return False


def reset() -> None:
    """Drop every semaphore: tests do it between cases, nothing else needs it."""
    with _lock:
        _semaphores.clear()


@contextmanager
def turn(key: str, limit: int, *, deadline: float | None = None,
         check: Callable[[], None] | None = None,
         pg: psycopg.Connection | None = None) -> Iterator[None]:
    """Hold the source's permit for the duration of the block, waiting if another task has it.

    `check` runs between polls (a run passes its stop flag, so an operator's stop interrupts the
    wait); `deadline` is a `time.monotonic()` value after which waiting fails with `TimeoutError`;
    `pg` is a product-database connection the caller already holds, used for the cross-process slot.
    """
    sem = _semaphore(key, limit)
    wait = None if deadline is None else max(0.0, deadline - time.monotonic())
    while not sem.acquire(timeout=POLL_SECONDS if wait is None else min(POLL_SECONDS, max(wait, 0.0))):
        if check is not None:
            check()
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError(key)
    held: list[str] = []
    try:
        if pg is not None:
            _take_slot(pg, key, deadline=deadline, check=check)
            held.append(key)
        yield
    finally:
        for slot in held:
            try:
                pg.execute(sql.SQL("SELECT pg_advisory_unlock(hashtextextended({}, 0))")
                           .format(sql.Literal(NS + slot)))
            except Exception:       # a closed connection releases the lock by itself
                pass
        sem.release()


def _take_slot(pg: psycopg.Connection, key: str, *, deadline: float | None,
               check: Callable[[], None] | None) -> None:
    stmt = sql.SQL("SELECT pg_try_advisory_lock(hashtextextended({}, 0))").format(
        sql.Literal(NS + key))
    while True:
        if pg.execute(stmt).fetchone()[0]:
            return
        if check is not None:
            check()
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError(key)
        time.sleep(POLL_SECONDS)
