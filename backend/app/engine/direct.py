"""Direct-source reports (feature 019): read-only engine path.

Direct reports read declared tables of an external PostgreSQL catalogue source or of the
BI database itself (`source: bi`) in read-only sessions. The deny-list decides which
logical `schema.table` names a direct report may select:

* always refused: PostgreSQL reserved schemas (`pg_catalog`, `information_schema`,
  `pg_toast*`), ephemeral/test schemas (`app_test_*`, `preview_*`), and
  `alembic_version`;
* additionally refused for the BI database: every table owned by the product (the
  SQLAlchemy metadata tables plus `alembic_version`); other tables (e.g. `ds_*` dataset
  tables) may be read.

Tests run under an isolated schema (`app_test_<hex>`) so physical table names never
touch the real `public` tables; `physical_schema`/`logical_schema` translate between
logical schema names and the physical PostgreSQL schema names.
"""
import contextlib
import contextvars
import functools
import logging
import math
import queue
import threading
import time
from collections.abc import Iterator
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import count

import psycopg
from bizview_cli import validate as wsv
from bizview_cli.validate import DIRECT_PRODUCT_MESSAGE, direct_reserved
from fastapi.encoders import jsonable_encoder
from psycopg import pq, sql
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db import get_engine, get_read_sessionmaker, get_sessionmaker, lock_key
from app.engine import extract
from app.engine.runner import _safe_message
from app.errors import ApiError
from app.i18n import t
from app.models import DIRECT_OUTCOMES, Base, DataSource, DirectReadLog, ReportCache
from app.security.netguard import BlockedAddress
from app.sources import service as sources_service
from app.sources.describe import MAX_COLUMNS, MAX_TABLES

log = logging.getLogger("app.direct")

PRODUCT_MESSAGE = DIRECT_PRODUCT_MESSAGE
DEFAULT_PORT = 5432


@functools.cache
def product_tables() -> frozenset[str]:
    """Lower-case ``schema.table`` names of every table owned by the product."""
    out = {"public.alembic_version"}
    for table in Base.metadata.tables.values():
        schema = table.schema or "public"
        out.add(f"{schema}.{table.name}".lower())
    return frozenset(out)


def refusal(schema: str, table: str, *, bi: bool) -> str | None:
    """Return a refusal message when a direct report cannot read ``schema.table``.

    The check uses logical names and is case-insensitive. Non-BI sources are only denied
    the PostgreSQL reserved/test schemas and ``alembic_version``; the BI database is
    additionally denied every product table.
    """
    if direct_reserved(schema, table):
        return PRODUCT_MESSAGE
    if bi and f"{schema}.{table}".lower() in product_tables():
        return PRODUCT_MESSAGE
    return None


def physical_schema(schema: str) -> str:
    """Logical BI-database schema name → physical PostgreSQL schema name.

    Production (``settings.db_schema == 'public'``) uses the logical name unchanged.
    Tests run under a private schema, so ``public`` maps to ``<test>__public`` and every
    other logical schema is namespaced with the same prefix.
    """
    settings = get_settings()
    if settings.db_schema != "public":
        return f"{settings.db_schema}__{schema}"
    return schema


def logical_schema(physical: str) -> str:
    """Inverse of :func:`physical_schema` for the view-dependency walk."""
    settings = get_settings()
    if settings.db_schema == "public":
        return physical
    if physical == settings.db_schema:
        return "public"
    prefix = settings.db_schema + "__"
    if physical.startswith(prefix):
        return physical[len(prefix):]
    return physical


def is_bi_database(source_settings: dict) -> bool:
    """True when a direct source points at the same host/port/database as the BI DB.

    Never logs or returns the DATABASE_URL_BI value. Host comparison is case-insensitive
    and stripped. Missing/empty host values on either side return False; non-numeric
    source ports return False; a missing source port defaults to 5432.
    """
    settings = get_settings()
    try:
        bi = make_url(settings.database_url_bi)
    except Exception:
        return False
    host = source_settings.get("host")
    if not isinstance(host, str) or not host.strip():
        return False
    if (host.strip().lower() != (bi.host or "").lower()):
        return False
    port = source_settings.get("port")
    if port is None:
        source_port = DEFAULT_PORT
    elif isinstance(port, int):
        source_port = port
    elif isinstance(port, str) and port.isdigit():
        source_port = int(port)
    else:
        return False
    bi_port = bi.port or DEFAULT_PORT
    if source_port != bi_port:
        return False
    database = source_settings.get("database")
    if (database or "").strip() != (bi.database or ""):
        return False
    return True


CODES = (
    "not_allowed",
    "unreachable",
    "timeout",
    "busy",
    "structure_changed",
    "product_table",
    "error",
)

MESSAGES = {
    "not_allowed": "Esta fuente no permite reportes directos",
    "unreachable": "No se pudo conectar con la fuente",
    "timeout": "La consulta superó el tiempo límite",
    "busy": "La fuente está ocupada",
    "structure_changed": "La estructura de la fuente cambió",
    "product_table": PRODUCT_MESSAGE,
    "error": "No se pudo leer la fuente",
}


class DirectError(Exception):
    """Error raised while reading a direct-report source."""

    def __init__(self, code: str, message: str | None = None):
        if code not in CODES:
            raise ValueError(f"unknown DirectError code: {code!r}")
        self.code = code
        self.message = message or t(f"direct.{code}")
        super().__init__(self.message)

    @classmethod
    def timeout(cls, seconds: int) -> "DirectError":
        return cls("timeout", t("direct.timeout_seconds", seconds=seconds))

    @classmethod
    def structure_changed(cls, missing: str) -> "DirectError":
        return cls("structure_changed",
                   t("direct.structure_missing", missing=missing))


@dataclass(frozen=True)
class DirectSource:
    """A validated direct-report source description."""
    key: str            # "bi" or the lower-case catalogue name (slot/lock/log key)
    label: str          # display name
    bi: bool            # the BI database: BI deny-list + physical schema mapping
    builtin: bool       # only the built-in `bi`
    source_id: int | None
    settings: dict = field(default_factory=dict, repr=False, compare=False)
    secrets: dict = field(default_factory=dict, repr=False, compare=False)   # never logged


RESOLVE_TTL_SECONDS = 10.0
_MISS = object()
_cache: dict[str, tuple[float, DirectSource | None]] = {}
_cache_lock = threading.Lock()


def clear_cache() -> None:
    """Drop cached catalogue source resolutions, dependency-walk results, and down marks."""
    with _cache_lock:
        _cache.clear()
    with _dep_lock:
        _dep_cache.clear()
    with _down_lock:
        _down_until.clear()
    with _source_bi_lock:
        _source_bi_cache.clear()


def _cached_source(low: str) -> DirectSource | object | None:
    """Return DirectSource on hit, None on cached refusal, or `_MISS` on cache miss."""
    with _cache_lock:
        hit = _cache.get(low)
        if hit is not None:
            expires, source = hit
            if time.monotonic() < expires:
                return source
            del _cache[low]
    return _MISS


def _cache_source(low: str, source: DirectSource | None) -> None:
    with _cache_lock:
        _cache[low] = (time.monotonic() + RESOLVE_TTL_SECONDS, source)


def resolve(name: str) -> DirectSource:
    """Resolve and validate a direct-report source name.

    ``bi`` (any case/space variant) resolves to the built-in BI source; anything else is
    an enabled postgresql catalogue source with its ``direct_reports`` flag on. Refusals
    are cached for ``RESOLVE_TTL_SECONDS``; a failure of the lookup itself (e.g. product
    database unreachable or decryption error) is never cached and raises ``error``.
    """
    low = (name or "").strip().lower()
    if not low:
        raise DirectError("not_allowed")
    if low == "bi":
        if not get_settings().direct_reports_bi:
            raise DirectError("not_allowed")
        return DirectSource("bi", "BI", True, True, None)

    hit = _cached_source(low)
    if hit is _MISS:
        refused = False
        try:
            with get_read_sessionmaker()() as db:
                src = sources_service.by_name(db, low)
                if src is None or src.kind != "postgresql" or not src.enabled \
                        or not src.direct_reports:
                    refused = True
                    raise DirectError("not_allowed")
                source = DirectSource(
                    low,
                    src.name,
                    is_bi_database(dict(src.settings or {})),
                    False,
                    src.id,
                    dict(src.settings or {}),
                    sources_service.secrets_of(src),
                )
                _cache_source(low, source)
        except DirectError:
            if refused:
                _cache_source(low, None)
            raise
        except Exception as e:
            log.warning("direct: source lookup failed (%s)", type(e).__name__)
            raise DirectError("error") from None
        return source
    if hit is None:
        raise DirectError("not_allowed")
    return hit


# --- Direct runner (security-critical) ------------------------------------------------------------

FETCH_CAP = 10_000
STRUCTURE_TIMEOUT_SECONDS = 10
DESCRIBE_TIMEOUT_SECONDS = 30
SLOT_POLL_SECONDS = 0.1
DOWN_SECONDS = 30.0
LOG_RETENTION_DAYS = 7

_semaphores: dict[tuple[str, int], threading.BoundedSemaphore] = {}
_sem_lock = threading.Lock()
_down_until: dict[str, float] = {}
_down_lock = threading.Lock()
_permits: contextvars.ContextVar[frozenset[str]] = contextvars.ContextVar(
    "direct_permits", default=frozenset()
)


def _semaphore(key: str, n: int) -> threading.BoundedSemaphore:
    with _sem_lock:
        sem = _semaphores.get((key, n))
        if sem is None:
            sem = threading.BoundedSemaphore(n)
            _semaphores[(key, n)] = sem
        return sem


def _mark_down(key: str) -> None:
    with _down_lock:
        _down_until[key] = time.monotonic() + DOWN_SECONDS


def _is_down(key: str) -> bool:
    with _down_lock:
        return time.monotonic() < _down_until.get(key, 0.0)


LOG_ASYNC = True
LOG_QUEUE_MAX = 1000
_log_queue: queue.Queue = queue.Queue(maxsize=LOG_QUEUE_MAX)
_log_thread: threading.Thread | None = None
_log_thread_lock = threading.Lock()


def _ensure_log_writer() -> None:
    global _log_thread
    with _log_thread_lock:
        if _log_thread is None or not _log_thread.is_alive():
            _log_thread = threading.Thread(target=_log_writer_loop, daemon=True)
            _log_thread.start()


def _log_writer_loop() -> None:
    while True:
        item = _log_queue.get()
        try:
            _write_log_row(**item)
        finally:
            _log_queue.task_done()


def _write_log_row(**fields) -> None:
    try:
        with get_sessionmaker().begin() as db:
            db.add(DirectReadLog(**fields))
    except Exception as e:
        log.warning("direct: read log not written (%s)", type(e).__name__)


def flush_log(timeout: float = 5.0) -> bool:
    """Wait until the async log queue is drained; returns True if drained."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _log_queue.unfinished_tasks == 0:
            return True
        time.sleep(0.01)
    return _log_queue.unfinished_tasks == 0


def log_read(report_id: str, source: str, *, duration_ms: int, rows: int,
             outcome: str, stale_served: bool = False) -> None:
    """Write one direct-read log line and one DirectReadLog row (errors swallowed)."""
    if outcome not in DIRECT_OUTCOMES:
        outcome = "error"
    duration_ms = max(0, duration_ms)
    rows = max(0, rows)
    log.info("direct read report=%s source=%s duration_ms=%d rows=%d outcome=%s stale=%s",
             report_id, source, duration_ms, rows, outcome, stale_served)
    fields = dict(
        report_id=report_id,
        source=source,
        duration_ms=duration_ms,
        rows=rows,
        outcome=outcome,
        stale_served=stale_served,
    )
    if LOG_ASYNC:
        _ensure_log_writer()
        try:
            _log_queue.put_nowait(fields)
        except queue.Full:
            log.warning("direct: read log queue full, row dropped")
    else:
        _write_log_row(**fields)


def prune_log(db) -> int:
    """Delete direct-read log rows older than LOG_RETENTION_DAYS. Returns rowcount."""
    cutoff = func.now() - timedelta(days=LOG_RETENTION_DAYS)
    result = db.execute(delete(DirectReadLog).where(DirectReadLog.occurred_at < cutoff))
    return result.rowcount


def _map_error(e: Exception, src: DirectSource, timeout_seconds: int) -> DirectError:
    """Map a psycopg error raised while talking to a direct source."""
    if isinstance(e, psycopg.errors.QueryCanceled):
        return DirectError.timeout(timeout_seconds)
    if isinstance(e, psycopg.OperationalError):
        return DirectError("unreachable")
    return DirectError("error", _safe_message(e, src.secrets))


# Per process, BI connections used by direct reads are at most 3 per held permit
# (sf lock + slot lock + query connection) = 3 x direct_report_concurrency x sources;
# waiters hold none.
@contextmanager
def _permit(key: str, deadline: float):
    """Take the source permit before any BI connection is opened, so a request waiting for a
    source holds no pooled connection.

    Nested `_slot` calls in the same context reuse the permit: Python's
    BoundedSemaphore is not reentrant, so check the contextvar first.
    """
    if key in _permits.get():
        yield
        return
    sem = _semaphore(key, get_settings().direct_report_concurrency)
    wait = max(0.0, deadline - time.monotonic())
    if not sem.acquire(timeout=wait):
        raise DirectError("busy")
    token = _permits.set(_permits.get() | {key})
    try:
        yield
    finally:
        _permits.reset(token)
        sem.release()


@contextmanager
def _slot(src: DirectSource, deadline: float):
    """Limit direct sessions per source: local semaphore + cross-process advisory slot."""
    n = get_settings().direct_report_concurrency
    own = src.key not in _permits.get()
    sem = _semaphore(src.key, n)
    if own:
        wait = max(0.0, deadline - time.monotonic())
        if not sem.acquire(timeout=wait):
            raise DirectError("busy")

    conn = None
    pg = None
    held = None
    try:
        try:
            conn = get_engine().connect()
        except Exception:
            raise DirectError("error", "No se pudo conectar con la base de datos BI") from None
        pg = conn.connection.driver_connection
        pg.autocommit = True
        try:
            while True:
                for slot in range(n):
                    key = lock_key("direct", src.key, str(slot))
                    try:
                        got = pg.execute(
                            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
                            (key,),
                        ).fetchone()[0]
                    except psycopg.Error:
                        conn.invalidate()
                        raise DirectError("error",
                                          "No se pudo conectar con la base de datos BI") from None
                    if got:
                        held = key
                        break
                if held is not None:
                    break
                if time.monotonic() + SLOT_POLL_SECONDS > deadline:
                    raise DirectError("busy")
                time.sleep(SLOT_POLL_SECONDS)
            yield
        finally:
            if held is not None:
                try:
                    unlocked = pg.execute(
                        "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                        (held,),
                    ).fetchone()[0]
                    if not unlocked or pg.closed or pg.broken:
                        conn.invalidate()
                except psycopg.Error:
                    conn.invalidate()
            if pg is not None and not pg.closed and not pg.broken:
                try:
                    pg.autocommit = False
                except Exception:
                    conn.invalidate()
    finally:
        if conn is not None:
            conn.close()
        if own:
            sem.release()


@contextmanager
def _connect(src: DirectSource, deadline: float,
             timeout_seconds: int) -> Iterator[psycopg.Connection]:
    """Yield a psycopg.Connection with `autocommit = True` and no open transaction.

    BI-pooled connections are sanitised and returned to the SQLAlchemy pool; catalogue
    connections are always closed. The caller must issue `BEGIN READ ONLY` and `ROLLBACK`.
    """
    if src.builtin:
        try:
            conn = get_engine().connect()
        except Exception:
            raise DirectError("unreachable") from None
        pg = None
        try:
            pg = conn.connection.driver_connection
            pg.autocommit = True
            yield pg
        finally:
            if pg is not None:
                if not pg.closed and not pg.broken \
                        and pg.info.transaction_status != pq.TransactionStatus.IDLE:
                    try:
                        pg.execute("ROLLBACK")
                    except Exception:
                        pass
                if not pg.closed and not pg.broken \
                        and pg.info.transaction_status == pq.TransactionStatus.IDLE:
                    try:
                        pg.autocommit = False
                    except Exception:
                        conn.invalidate()
                else:
                    conn.invalidate()
            conn.close()
    else:
        pg = None
        try:
            remaining = deadline - time.monotonic()
            connect_timeout_s = max(1, math.ceil(remaining)) if remaining > 0 else 1
            pg = extract._pg_connect(
                src.settings,
                src.secrets,
                get_settings(),
                timezone=get_settings().timezone,
                time_limit_s=timeout_seconds,
                connect_timeout_s=connect_timeout_s,
            )
            pg.autocommit = True
            yield pg
        except extract.ExtractError as e:
            raise DirectError("error", str(e)) from None
        except BlockedAddress:
            raise DirectError("error", t("direct.blocked_address")) from None
        except (psycopg.OperationalError, OSError):
            raise DirectError("unreachable") from None
        finally:
            if pg is not None:
                try:
                    if not pg.closed and pg.info.transaction_status != pq.TransactionStatus.IDLE:
                        pg.execute("ROLLBACK")
                except Exception:
                    pass
                try:
                    pg.close()
                except Exception:
                    log.warning("direct: close failed for source %s", src.key)


class DirectSession:
    """Read-only, time-limited session for one direct query or a whole report."""

    def __init__(self, pg: psycopg.Connection, src: DirectSource, deadline: float,
                 timeout_seconds: int, missing):
        self._pg = pg
        self._src = src
        self._deadline = deadline
        self._timeout_seconds = timeout_seconds
        self._missing = missing
        self.rows = 0
        self.description: list[tuple[str, int]] = []
        self._counter = count(1)
        self._active = False
        self._active_lock = threading.Lock()

    def _cancel(self):
        with self._active_lock:
            if not self._active:
                return
        try:
            self._pg.cancel_safe(timeout=2)
        except Exception:
            log.debug("direct: cancel failed", exc_info=True)

    def query(self, statement: sql.Composed, tz: str) -> list[tuple]:
        if self._pg.info.transaction_status != pq.TransactionStatus.INTRANS:
            raise DirectError("error", t("direct.session_invalid"))

        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise DirectError.timeout(self._timeout_seconds)

        try:
            checked_tz = extract.check_timezone(tz)

            # Server-side cursor: DECLARE ... CURSOR FOR accepts only a single SELECT/VALUES
            # and uses the extended protocol; no write statement and no second statement can
            # run here, and rows beyond FETCH_CAP are never transferred to the client.
            # Pipeline mode sends all statements in one round trip, but each still uses the
            # extended protocol, so a statement string can never contain a second command.
            name = f"bizview_direct_{next(self._counter)}"
            pipeline = (
                self._pg.pipeline()
                if psycopg.Pipeline.is_supported()
                else contextlib.nullcontext()
            )
            timer = threading.Timer(
                max(0.0, self._deadline - time.monotonic()),
                self._cancel,
            )
            timer.daemon = True
            with self._active_lock:
                self._active = True
            timer.start()
            try:
                with self._pg.cursor() as cur, self._pg.cursor() as fetch_cur:
                    with pipeline:
                        cur.execute(
                            sql.SQL("SET LOCAL statement_timeout = {}").format(
                                sql.Literal(max(1, int(remaining * 1000)))
                            )
                        )
                        cur.execute(
                            sql.SQL("SET LOCAL TimeZone = {}").format(
                                sql.Literal(checked_tz)
                            )
                        )
                        cur.execute(
                            sql.SQL("DECLARE {} NO SCROLL CURSOR FOR {}").format(
                                sql.Identifier(name), statement
                            )
                        )
                        fetch_cur.execute(
                            sql.SQL("FETCH FORWARD {} FROM {}").format(
                                sql.Literal(FETCH_CAP + 1), sql.Identifier(name)
                            )
                        )
                        cur.execute(sql.SQL("CLOSE {}").format(sql.Identifier(name)))
                    rows = fetch_cur.fetchall()
                    self.description = [
                        (d.name, d.type_code) for d in (fetch_cur.description or [])
                    ]
            finally:
                timer.cancel()
                with self._active_lock:
                    self._active = False
        except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn):
            item = self._missing()
            if item:
                raise DirectError.structure_changed(item) from None
            raise DirectError("structure_changed") from None
        except psycopg.Error as e:
            raise _map_error(e, self._src, self._timeout_seconds) from None

        if len(rows) > FETCH_CAP:
            raise DirectError("error", t("direct.too_many_rows"))
        self.rows += len(rows)
        return [tuple(row) for row in rows]


def _set_role(pg: psycopg.Connection, src: DirectSource) -> None:
    """Apply the read-only role for built-in bi sessions, defence in depth.

    Only the built-in ``bi`` source uses the application's BI connection; a catalogue
    source that points at the BI database connects with its own credentials chosen by
    the administrator, so this role is not applied there.
    """
    if not src.builtin:
        return
    role = get_settings().direct_bi_role
    if role:
        pg.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))


def _dependency_walk(pg: psycopg.Connection, schemas: list[str],
                     names: list[str]) -> list[tuple[str, str]]:
    stmt = sql.SQL(
        "WITH RECURSIVE rel(oid) AS ( "
        "SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE (n.nspname, c.relname) IN "
        "(SELECT * FROM unnest({schemas}::text[], {names}::text[])) "
        "UNION "
        "SELECT d.refobjid FROM rel "
        "JOIN pg_rewrite r ON r.ev_class = rel.oid "
        "JOIN pg_depend d ON d.classid = 'pg_rewrite'::regclass AND d.objid = r.oid "
        "AND d.refclassid = 'pg_class'::regclass AND d.refobjid <> rel.oid "
        ") "
        "SELECT n.nspname, c.relname FROM rel JOIN pg_class c ON c.oid = rel.oid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace"
    ).format(schemas=sql.Literal(schemas), names=sql.Literal(names))
    cur = pg.execute(stmt)
    rows = cur.fetchall()
    return [(row[0], row[1]) for row in rows]


_dep_cache: set[tuple] = set()
_dep_lock = threading.Lock()


def _check_dependencies(pg: psycopg.Connection, src: DirectSource,
                        physical_tables: dict[str, tuple[str, str]],
                        key: tuple) -> None:
    cacheable = key[0] is not None
    if cacheable:
        with _dep_lock:
            if key in _dep_cache:
                return
    schema_list = [t[0] for t in physical_tables.values()]
    name_list = [t[1] for t in physical_tables.values()]
    reachable = _dependency_walk(pg, schema_list, name_list)
    for r_schema, r_name in reachable:
        if refusal(logical_schema(r_schema), r_name, bi=True) is not None:
            raise DirectError("product_table")
    if cacheable:
        with _dep_lock:
            _dep_cache.add(key)


_FINGERPRINT_SQL = (
    "SELECT current_database(), "
    "extract(epoch FROM pg_postmaster_start_time())::text, "
    "current_setting('port')"
)

_bi_fingerprint_cache: tuple | None = None
_bi_fingerprint_lock = threading.Lock()
_source_bi_cache: dict[str, tuple[float, bool]] = {}
_source_bi_lock = threading.Lock()


def _fingerprint(pg: psycopg.Connection) -> tuple:
    cur = pg.execute(_FINGERPRINT_SQL)
    return tuple(cur.fetchone())


def _bi_fingerprint() -> tuple:
    global _bi_fingerprint_cache
    with _bi_fingerprint_lock:
        if _bi_fingerprint_cache is not None:
            return _bi_fingerprint_cache
        try:
            with get_engine().connect() as conn:
                pg = conn.connection.driver_connection
                pg.autocommit = True
                try:
                    fp = _fingerprint(pg)
                finally:
                    pg.autocommit = False
            _bi_fingerprint_cache = fp
            return fp
        except Exception:
            raise DirectError("error", "No se pudo conectar con la base de datos BI") from None


def _begin(pg: psycopg.Connection, src: DirectSource) -> tuple | None:
    """Start a read-only transaction, set role for builtin, and fingerprint non-builtin."""
    pipeline = (
        pg.pipeline()
        if psycopg.Pipeline.is_supported()
        else contextlib.nullcontext()
    )
    with pg.cursor() as cur, pg.cursor() as fp_cur:
        with pipeline:
            cur.execute("BEGIN READ ONLY")
            if src.builtin:
                role = get_settings().direct_bi_role
                if role:
                    cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            else:
                fp_cur.execute(_FINGERPRINT_SQL)
        return None if src.builtin else tuple(fp_cur.fetchone())


def _source_is_bi(pg: psycopg.Connection, src: DirectSource, fp: tuple | None = None) -> bool:
    now = time.monotonic()
    with _source_bi_lock:
        hit = _source_bi_cache.get(src.key)
        if hit is not None and now < hit[0]:
            return hit[1]
    if fp is None:
        fp = _fingerprint(pg)
    result = fp == _bi_fingerprint()
    with _source_bi_lock:
        _source_bi_cache[src.key] = (now + RESOLVE_TTL_SECONDS, result)
    return result


def _structure_on(pg: psycopg.Connection, src: DirectSource, tables: list[str],
                  *, as_bi: bool = False) -> dict[str, dict]:
    """Structure of logical `schema.table` names on an open READ ONLY transaction."""
    bi = src.bi or as_bi
    if not tables:
        return {}
    requested: list[tuple[str, str]] = []
    for name in tables:
        schema, table = name.split(".", 1)
        if refusal(schema, table, bi=bi) is None:
            requested.append((schema.lower(), table.lower()))

    if not requested:
        return {}

    physical_for_logical: dict[tuple[str, str], str] = {}
    schemas_list: list[str] = []
    tables_list: list[str] = []
    for schema, table in requested:
        if src.bi:
            p_schema = physical_schema(schema)
        else:
            p_schema = schema
        physical_for_logical[(p_schema, table)] = f"{schema}.{table}"
        schemas_list.append(p_schema)
        tables_list.append(table)

    stmt = sql.SQL(
        "SELECT table_schema, table_name, column_name, data_type "
        "FROM information_schema.columns "
        "WHERE (table_schema, table_name) IN "
        "(SELECT * FROM unnest({schemas}::text[], {tables}::text[])) "
        "AND has_table_privilege(format('%I.%I', table_schema, table_name), 'SELECT') "
        "ORDER BY table_schema, table_name, ordinal_position"
    ).format(schemas=sql.Literal(schemas_list), tables=sql.Literal(tables_list))
    cur = pg.execute(stmt)
    rows = cur.fetchall()

    result: dict[str, dict] = {}
    for p_schema, p_table, col_name, col_type in rows:
        logical_key = physical_for_logical.get((p_schema, p_table))
        if logical_key is None:
            continue
        entry = result.setdefault(logical_key, {
            "columns": {},
            "product_dependency": False,
            "reltuples": 0,
            "date_index_columns": [],
            "date_indexed": False,
        })
        entry["columns"][col_name] = col_type

    if result:
        info_stmt = sql.SQL(
            "SELECT n.nspname, c.relname, c.reltuples, "
            "ARRAY(SELECT a.attname FROM pg_index i "
            "      JOIN pg_attribute a ON a.attrelid = i.indrelid "
            "        AND a.attnum = i.indkey[0] "
            "      WHERE i.indrelid = c.oid "
            "      UNION "
            "      SELECT a.attname FROM pg_partitioned_table p "
            "      JOIN pg_attribute a ON a.attrelid = p.partrelid "
            "        AND a.attnum = p.partattrs[0] "
            "      WHERE p.partrelid = c.oid) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE (n.nspname, c.relname) IN "
            "(SELECT * FROM unnest({schemas}::text[], {tables}::text[]))"
        ).format(schemas=sql.Literal(schemas_list), tables=sql.Literal(tables_list))
        info_rows = pg.execute(info_stmt).fetchall()
        date_types = {"date", "timestamp with time zone", "timestamp without time zone"}
        for p_schema, p_table, reltuples, leading_cols in info_rows:
            logical_key = physical_for_logical.get((p_schema, p_table))
            if logical_key is None:
                continue
            entry = result[logical_key]
            entry["reltuples"] = int(reltuples)
            date_cols = sorted(
                name for name in leading_cols
                if str(entry["columns"].get(name)).lower() in date_types
            )
            entry["date_index_columns"] = date_cols
            entry["date_indexed"] = bool(date_cols)

    if bi:
        for logical_key, entry in result.items():
            schema, table = logical_key.split(".", 1)
            if src.bi:
                phys_schema = physical_schema(schema)
            else:
                phys_schema = schema
            deps = _dependency_walk(pg, [phys_schema], [table])
            entry["product_dependency"] = any(
                refusal(logical_schema(dep_schema), dep_name, bi=True) is not None
                for dep_schema, dep_name in deps
            )
    return result


class DirectRunner:
    """Executes read-only queries against a direct-report source."""

    def __init__(self, source: str, *, report_id: str, timeout_seconds: int = 15,
                 tables: dict[str, tuple[str, str]] | None = None,
                 columns: dict[str, dict[str, dict]] | None = None,
                 version_key: object = None):
        self.source = source
        self.report_id = report_id
        self.timeout_seconds = timeout_seconds
        self.tables = tables or {}
        self.columns = columns or {}
        self.version_key = version_key

    def physical_tables(self, src: DirectSource) -> dict[str, tuple[str, str]]:
        out = {}
        for alias, (schema, table) in self.tables.items():
            if src.bi:
                out[alias] = (physical_schema(schema), table)
            else:
                out[alias] = (schema, table)
        return out

    def _first_missing(self, pg: psycopg.Connection, src: DirectSource,
                       as_bi: bool = False) -> str | None:
        try:
            if not pg.closed and not pg.broken \
                    and pg.info.transaction_status != pq.TransactionStatus.IDLE:
                pg.execute("ROLLBACK")
            pg.execute("BEGIN READ ONLY")
            _set_role(pg, src)
            structures = _structure_on(
                pg,
                src,
                [f"{s}.{t}" for s, t in self.tables.values()],
                as_bi=as_bi,
            )
        except Exception:
            return None
        finally:
            try:
                if not pg.closed and not pg.broken \
                        and pg.info.transaction_status != pq.TransactionStatus.IDLE:
                    pg.execute("ROLLBACK")
            except Exception:
                pass

        for _alias, (schema, table) in self.tables.items():
            logical_name = f"{schema}.{table}".lower()
            if logical_name not in structures:
                return logical_name
        for alias, cols in self.columns.items():
            schema, table = self.tables.get(alias, (None, None))
            if schema is None:
                continue
            logical_name = f"{schema}.{table}".lower()
            if logical_name not in structures:
                continue
            for col_name in cols:
                if col_name not in structures[logical_name]["columns"]:
                    return col_name
        return None

    @contextmanager
    def session(self) -> Iterator[DirectSession]:
        start = time.monotonic()
        outcome = "error"
        src = None
        session = None
        as_bi = False
        try:
            deadline = start + self.timeout_seconds
            override = _deadline_override.get()
            if override is not None:
                deadline = min(deadline, override)
            src = resolve(self.source)
            for schema, table in self.tables.values():
                if refusal(schema, table, bi=src.bi) is not None:
                    raise DirectError("product_table")

            if _is_down(src.key):
                raise DirectError("unreachable")

            with _slot(src, deadline), _connect(src, deadline, self.timeout_seconds) as pg:
                try:
                    fp = _begin(pg, src)
                    if not src.builtin:
                        as_bi = _source_is_bi(pg, src, fp)
                        if as_bi and not src.bi:
                            for schema, table in self.tables.values():
                                if refusal(schema, table, bi=True) is not None:
                                    raise DirectError("product_table")
                    if src.bi or as_bi:
                        physical_tables = self.physical_tables(src)
                        key = (self.version_key, self.report_id,
                               tuple(sorted(physical_tables.items())))
                        _check_dependencies(pg, src, physical_tables, key)
                    session = DirectSession(
                        pg,
                        src,
                        deadline,
                        self.timeout_seconds,
                        missing=lambda: self._first_missing(pg, src, as_bi),
                    )
                except psycopg.Error as e:
                    raise _map_error(e, src, self.timeout_seconds) from None
                yield session
                outcome = "ok"
        except DirectError as e:
            outcome = e.code
            if src is not None and e.code == "unreachable":
                _mark_down(src.key)
            raise
        finally:
            source_key = src.key if src is not None else (
                (self.source or "").strip().lower() or "unknown")[:80]
            log_read(
                self.report_id,
                source_key,
                duration_ms=int((time.monotonic() - start) * 1000),
                rows=session.rows if session is not None else 0,
                outcome=outcome,
            )

def structure(source: str | DirectSource, tables: list[str]) -> dict:
    """Public structure inspection for a direct source. Never raises."""
    if isinstance(source, str):
        try:
            src = resolve(source)
        except DirectError as e:
            return {"error": e.message}
    else:
        src = source

    if _is_down(src.key):
        return {"error": MESSAGES["unreachable"]}

    deadline = time.monotonic() + STRUCTURE_TIMEOUT_SECONDS
    try:
        with _slot(src, deadline), _connect(src, deadline, STRUCTURE_TIMEOUT_SECONDS) as pg:
            result: dict = {}
            try:
                pg.execute("BEGIN READ ONLY")
                _set_role(pg, src)
                pg.execute(sql.SQL("SET LOCAL statement_timeout = {}").format(
                    sql.Literal(STRUCTURE_TIMEOUT_SECONDS * 1000)))
                as_bi = src.bi or (
                    not src.builtin and _source_is_bi(pg, src)
                )
                result = _structure_on(pg, src, tables, as_bi=as_bi)
            except DirectError as e:
                if e.code == "unreachable":
                    _mark_down(src.key)
                return {"error": e.message}
            except psycopg.Error as e:
                mapped = _map_error(e, src, STRUCTURE_TIMEOUT_SECONDS)
                if mapped.code == "unreachable":
                    _mark_down(src.key)
                return {"error": mapped.message}
            return {"tables": result}
    except DirectError as e:
        if e.code == "unreachable":
            _mark_down(src.key)
        return {"error": e.message}


def describe_bi() -> dict:
    """Structure of the installation BI database for direct reports.

    Logical schema names only; product tables, reserved/test schemas and views that reach a
    product table are removed; only relations the session may SELECT; never row values.
    """
    settings = get_settings()
    if not settings.direct_reports_bi:
        raise DirectError("not_allowed")

    src = DirectSource("bi", "BI", True, True, None)
    if _is_down(src.key):
        raise DirectError("unreachable")

    deadline = time.monotonic() + DESCRIBE_TIMEOUT_SECONDS
    try:
        with _slot(src, deadline), _connect(src, deadline, DESCRIBE_TIMEOUT_SECONDS) as pg:
            try:
                pg.execute("BEGIN READ ONLY")
                _set_role(pg, src)
                pg.execute(sql.SQL("SET LOCAL statement_timeout = {}").format(
                    sql.Literal(DESCRIBE_TIMEOUT_SECONDS * 1000)))

                rows = pg.execute(
                    """
                    SELECT c.oid, n.nspname, c.relname, c.relkind,
                           greatest(c.reltuples, 0)::bigint
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind IN ('r','v','m','p','f')
                      AND n.nspname NOT IN ('pg_catalog','information_schema')
                      AND n.nspname NOT LIKE 'pg_toast%'
                      AND n.nspname NOT LIKE 'pg_temp%'
                      AND has_table_privilege(c.oid, 'SELECT')
                    ORDER BY n.nspname, c.relname
                    """
                ).fetchall()

                kept: list[dict] = []
                view_oids: list[int] = []
                for oid, physical, relname, relkind, est_rows in rows:
                    if settings.db_schema != "public":
                        if physical != settings.db_schema \
                                and not physical.startswith(settings.db_schema + "__"):
                            continue
                    logical = logical_schema(physical)
                    if refusal(logical, relname, bi=True) is not None:
                        continue
                    kept.append({"oid": oid, "schema": logical,
                                 "physical_schema": physical,
                                 "name": relname,
                                 "kind": relkind, "estimated_rows": int(est_rows)})
                    if relkind in ("v", "m"):
                        view_oids.append(oid)

                if view_oids:
                    deps = pg.execute(
                        """
                        WITH RECURSIVE rel(root, oid) AS (
                            SELECT o, o FROM unnest(%s::oid[]) AS o
                            UNION
                            SELECT rel.root, d.refobjid
                            FROM rel
                            JOIN pg_rewrite r ON r.ev_class = rel.oid
                            JOIN pg_depend d
                              ON d.classid = 'pg_rewrite'::regclass
                             AND d.objid = r.oid
                             AND d.refclassid = 'pg_class'::regclass
                             AND d.refobjid <> rel.oid
                        )
                        SELECT rel.root, n.nspname, c.relname
                        FROM rel
                        JOIN pg_class c ON c.oid = rel.oid
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        """,
                        (view_oids,),
                    ).fetchall()

                    blocked: set[int] = set()
                    for root, physical, relname in deps:
                        logical = logical_schema(physical)
                        if refusal(logical, relname, bi=True) is not None:
                            blocked.add(root)

                    if blocked:
                        kept = [r for r in kept if r["oid"] not in blocked]

                truncated = len(kept) > MAX_TABLES
                kept = kept[:MAX_TABLES]

                tables: list[dict] = []
                if kept:
                    physical_schemas = [r["physical_schema"] for r in kept]
                    physical_names = [r["name"] for r in kept]

                    col_rows = pg.execute(
                        """
                        SELECT table_schema, table_name, column_name, data_type,
                               is_nullable = 'YES'
                        FROM information_schema.columns
                        WHERE (table_schema, table_name) IN
                              (SELECT * FROM unnest(%s::text[], %s::text[]))
                        ORDER BY table_schema, table_name, ordinal_position
                        """,
                        (physical_schemas, physical_names),
                    ).fetchall()

                    pk_rows = pg.execute(
                        """
                        SELECT tc.table_schema, tc.table_name, kcu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON kcu.constraint_name = tc.constraint_name
                         AND kcu.table_schema = tc.table_schema
                         AND kcu.table_name = tc.table_name
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND (tc.table_schema, tc.table_name) IN
                              (SELECT * FROM unnest(%s::text[], %s::text[]))
                        ORDER BY kcu.ordinal_position
                        """,
                        (physical_schemas, physical_names),
                    ).fetchall()

                    kind_map = {
                        "r": "table",
                        "p": "table",
                        "v": "view",
                        "m": "materialized_view",
                        "f": "foreign_table",
                    }

                    cols_by_table: dict[tuple[str, str], list[dict]] = {}
                    for p_schema, table_name, column_name, data_type, nullable in col_rows:
                        logical = logical_schema(p_schema)
                        cols_by_table.setdefault((logical, table_name), []).append({
                            "name": column_name,
                            "type": data_type,
                            "nullable": bool(nullable),
                        })

                    pks_by_table: dict[tuple[str, str], list[str]] = {}
                    for p_schema, table_name, column_name in pk_rows:
                        logical = logical_schema(p_schema)
                        pks_by_table.setdefault((logical, table_name), []).append(column_name)

                    for r in kept:
                        key = (r["schema"], r["name"])
                        cols = cols_by_table.get(key, [])
                        if len(cols) > MAX_COLUMNS:
                            cols = cols[:MAX_COLUMNS]
                        tables.append({
                            "schema": r["schema"],
                            "name": r["name"],
                            "kind": kind_map.get(r["kind"], "table"),
                            "estimated_rows": r["estimated_rows"],
                            "primary_key": pks_by_table.get(key, []),
                            "columns": cols,
                        })

                return {"kind": "postgresql", "tables": tables, "truncated": truncated}
            except psycopg.Error as e:
                raise _map_error(e, src, DESCRIBE_TIMEOUT_SECONDS) from None
    except DirectError as e:
        if e.code == "unreachable":
            _mark_down(src.key)
        raise


# --- Cache, single-flight and stale fallback (FR-008, FR-009) -------------------------------------

_deadline_override: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "direct_deadline", default=None
)

API_ERRORS = {
    "timeout": (503, "source_timeout"),
    "unreachable": (503, "source_unavailable"),
    "busy": (503, "source_busy"),
    "not_allowed": (409, "direct_not_allowed"),
    "structure_changed": (409, "direct_structure_changed"),
    "product_table": (409, "direct_product_table"),
    "error": (503, "source_error"),
}
STALE_CODES = frozenset({"timeout", "unreachable", "busy"})
STALE_HOURS = 24
SF_MAX = 1024


def api_error(e: DirectError) -> ApiError:
    status, code = API_ERRORS.get(e.code, (503, "source_error"))
    return ApiError(status, code, e.message)


_inflight: dict[tuple[str, str, str], Future] = {}
_inflight_lock = threading.Lock()


def _read(db, report_id: str, key: str, version: str) -> dict | None:
    return db.scalar(
        select(ReportCache.payload)
        .where(
            ReportCache.report_id == report_id,
            ReportCache.selection_hash == key,
            ReportCache.kind == "data",
            ReportCache.data_version == version,
        )
    )


def _store(ctx, key: str, version: str, payload: dict) -> None:
    try:
        old = (
            delete(ReportCache)
            .where(
                ReportCache.report_id == ctx.report_id,
                ReportCache.kind == "data",
                or_(
                    ReportCache.created_at < func.now() - timedelta(hours=STALE_HOURS),
                    ~ReportCache.data_version.like(f"v{ctx.version.id}-d%"),
                ),
            )
            .returning(ReportCache.report_id)
            .cte("old")
        )
        ins = (
            pg_insert(ReportCache)
            .values(
                report_id=ctx.report_id,
                selection_hash=key,
                data_version=version,
                kind="data",
                payload=payload,
            )
            .on_conflict_do_nothing()
            .add_cte(old)
        )
        session = get_read_sessionmaker()()
        try:
            session.execute(ins)
        finally:
            session.close()
    except Exception as e:
        log.warning("direct: cache not stored (%s)", type(e).__name__)


def _failure(db, ctx, key: str, e: DirectError, started: float) -> dict:
    if e.code in STALE_CODES:
        row = db.scalar(
            select(ReportCache.payload)
            .where(
                ReportCache.report_id == ctx.report_id,
                ReportCache.selection_hash == key,
                ReportCache.kind == "data",
                ReportCache.data_version.like(f"v{ctx.version.id}-d%"),
                ReportCache.created_at
                >= func.now() - timedelta(hours=STALE_HOURS),
            )
            .order_by(ReportCache.created_at.desc())
            .limit(1)
        )
        if isinstance(row, dict):
            freshness = dict(row.get("freshness") or {})
            freshness["stale"] = True
            freshness["stale_reason"] = e.code
            log_read(
                ctx.report_id,
                (ctx.direct.source or "").strip().lower()[:80],
                duration_ms=int((time.monotonic() - started) * 1000),
                rows=0,
                outcome=e.code,
                stale_served=True,
            )
            return {**row, "freshness": freshness}
    raise api_error(e) from None


def _lead(db, ctx, sel, filters, key, tz, version, deadline, engine) -> dict:
    spec = ctx.direct
    src_key = resolve(spec.source).key
    conn = None
    pg = None
    held = False
    lk = lock_key("direct-sf", ctx.report_id, key, version)
    with _permit(src_key, deadline):
        try:
            try:
                conn = get_engine().connect()
            except Exception:
                raise DirectError("error",
                                  "No se pudo conectar con la base de datos BI") from None
            pg = conn.connection.driver_connection
            pg.autocommit = True
            while True:
                try:
                    got = pg.execute(
                        "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
                        (lk,),
                    ).fetchone()[0]
                except psycopg.Error:
                    conn.invalidate()
                    raise DirectError("error",
                                      "No se pudo conectar con la base de datos BI") from None
                if got:
                    held = True
                    break
                hit = _read(db, ctx.report_id, key, version)
                if hit is not None:
                    return hit
                if time.monotonic() + SLOT_POLL_SECONDS > deadline:
                    raise DirectError("busy")
                time.sleep(SLOT_POLL_SECONDS)
            hit = _read(db, ctx.report_id, key, version)
            if hit is not None:
                return hit
            queried_at = datetime.now(UTC)
            reference = engine.render_reference()
            token = _deadline_override.set(deadline)
            try:
                views = engine.run_views(ctx, sel, filters, tz, reference=reference)
            finally:
                _deadline_override.reset(token)
            payload = jsonable_encoder({
                "selection": sel.to_json(),
                "filters": filters,
                "render_reference": reference,
                "freshness": {
                    "updated_at": queried_at,
                    "data_version": version,
                    "mode": "direct",
                    "source": spec.label,
                    "queried_at": queried_at,
                    "stale": False,
                },
                "views": views,
            })
            _store(ctx, key, version, payload)
            return payload
        finally:
            if held:
                try:
                    unlocked = pg.execute(
                        "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                        (lk,),
                    ).fetchone()[0]
                    if not unlocked or pg.closed or pg.broken:
                        conn.invalidate()
                except psycopg.Error:
                    conn.invalidate()
            if pg is not None and not pg.closed and not pg.broken:
                try:
                    pg.autocommit = False
                except Exception:
                    conn.invalidate()
            if conn is not None:
                conn.close()


def cached_data(db, ctx, sel, filters, key: str, tz: str) -> dict:
    """Return direct report data with cooperative caching.

    Flow: permission → cache read → in-process single-flight → cross-process advisory lock
    (with re-read) → run the direct source → store → return.
    On transient failure return a recent stale payload when available.
    """
    from app.engine import report as engine

    started = time.monotonic()
    spec = ctx.direct
    # FR-006: a source whose direct reports were turned off serves no cached figures either.
    # A failed lookup (product database down) still lets the cache answer.
    try:
        resolve(spec.source)
    except DirectError as e:
        if e.code == "not_allowed":
            raise api_error(e) from None
    version = engine.direct_version(ctx)
    hit = _read(db, ctx.report_id, key, version)
    if hit is not None:
        return hit

    k = (ctx.report_id, key, version)
    with _inflight_lock:
        existing = _inflight.get(k)
        if existing is not None:
            fut = existing
        else:
            fut = Future()
            if len(_inflight) < SF_MAX:
                _inflight[k] = fut
                registered = True
            else:
                registered = False

    if existing is None:
        deadline = time.monotonic() + spec.timeout_seconds
        try:
            result = _lead(db, ctx, sel, filters, key, tz, version, deadline, engine)
            fut.set_result(result)
            return result
        except BaseException as e:
            fut.set_exception(e)
            if isinstance(e, DirectError):
                return _failure(db, ctx, key, e, started)
            raise
        finally:
            if registered:
                with _inflight_lock:
                    if _inflight.get(k) is fut:
                        del _inflight[k]
    else:
        try:
            return fut.result(timeout=spec.timeout_seconds + 1)
        except FutureTimeout:
            e = DirectError.timeout(spec.timeout_seconds)
            return _failure(db, ctx, key, e, started)
        except DirectError as e:
            return _failure(db, ctx, key, e, started)


# --- Backend validation context (FR-011) ----------------------------------------------------------

def validation_context(db, app=None) -> wsv.DirectContext:
    """Build the DirectContext for workspace validation.

    `structure` is memoised per validation call; each miss runs one read-only
    query over information_schema with a 10 s timeout and never raises.
    """
    if app is None:
        app = get_settings()
    sources = {}
    for src in db.scalars(select(DataSource)):
        key = src.name.strip().lower()
        sources[key] = {
            "name": src.name,
            "kind": src.kind,
            "enabled": bool(src.enabled),
            "direct": bool(src.direct_reports),
            "bi": src.kind == "postgresql"
            and is_bi_database(dict(src.settings or {})),
        }

    def rows(iid: str, dataset: str) -> int | None:
        from sqlalchemy import text

        from app.engine import datasets
        schema = datasets.schema_name(iid).replace('"', '""')
        dataset_name = dataset.replace('"', '""')
        table = f'"{schema}"."{dataset_name}"'
        try:
            with db.begin_nested():
                result = db.execute(
                    text(
                        "SELECT reltuples::bigint FROM pg_class "
                        "WHERE oid = to_regclass(:t)"
                    ),
                    {"t": table},
                )
                v = result.scalar()
            return max(int(v), 0) if v is not None else None
        except Exception:
            return None

    from app.assistant.personal import personal_kind

    memo: dict[tuple[str, tuple[str, ...]], dict] = {}

    def structured(source: str, tables: list[str]) -> dict:
        skey = (source.strip().lower(),
                tuple(sorted(t.lower() for t in tables)))
        if skey in memo:
            return memo[skey]
        try:
            result = structure(source.strip(), list(tables))
        except Exception as e:
            log.warning("direct: structure check failed (%s)", type(e).__name__)
            result = {"error": "No se pudo comprobar la estructura de la fuente."}
        memo[skey] = result
        return result

    return wsv.DirectContext(
        sources=sources,
        bi_enabled=bool(app.direct_reports_bi),
        product_tables=product_tables(),
        structure=structured,
        personal_kind=lambda col: personal_kind(col),
        warn_rows=app.direct_report_warn_rows, dataset_rows=rows,
    )
