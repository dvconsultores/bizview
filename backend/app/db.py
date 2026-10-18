import re
import time
from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine, event, exc
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# Keep remote DB connections from hanging forever on silently dropped packets
TCP_LIVENESS = {
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
    "tcp_user_timeout": 60000,  # ms
}
# The BI database may be remote (~200 ms per round trip): a pooled connection is only pinged
# before use when it sat idle longer than this, instead of on every checkout (pool_pre_ping).
IDLE_PING_SECONDS = 60


def lock_key(*parts: object) -> str:
    """Advisory-lock key scoped to this installation's schema.

    Advisory locks are database-wide, so two schemas (test runs, the e2e
    backend) sharing one database must never contend for the same key.
    """
    return ":".join(["bizview", get_settings().db_schema, *(str(p) for p in parts)])


@lru_cache
def get_engine() -> Engine:
    """Engine on DATABASE_URL_BI. Tables use the default schema (public); when DB_SCHEMA is a
    test schema, every statement is transparently redirected to it."""
    settings = get_settings()
    engine = create_engine(
        settings.database_url_bi,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_overflow,
        pool_recycle=6 * 3600,   # TCP keepalives keep idle connections alive meanwhile
        connect_args=dict(TCP_LIVENESS),
    )

    @event.listens_for(engine, "checkin")
    def _remember_checkin(_dbapi_connection, record):
        record.info["checked_in"] = time.monotonic()

    @event.listens_for(engine, "checkout")
    def _ping_if_idle(dbapi_connection, record, _proxy):
        last = record.info.get("checked_in")
        if last is not None and time.monotonic() - last < IDLE_PING_SECONDS:
            return
        try:
            engine.dialect.do_ping(dbapi_connection)
        except Exception as e:  # dropped while idle: the pool retries with a new connection
            raise exc.DisconnectionError() from e
    if settings.db_schema != "public":
        schema = settings.db_schema  # validated: app_test_* only

        # Tests: every connection sees ONLY the test schema. Unqualified statements (including
        # Alembic's ALTER TABLE) land there, and nothing can resolve to the real `public`.
        @event.listens_for(engine, "connect")
        def _only_test_schema(dbapi_connection, _record):
            with dbapi_connection.cursor() as cur:
                cur.execute(f'SET search_path TO "{schema}"')
            dbapi_connection.commit()

        engine = engine.execution_options(schema_translate_map={None: schema})
    return engine


def warm_pool(count: int) -> None:
    """Open `count` pooled connections in parallel (at start-up, in the background), so the
    first requests do not pay for new connections to a remote database."""
    from concurrent.futures import ThreadPoolExecutor

    engine = get_engine()

    def open_one(_):
        try:
            return engine.connect()
        except Exception:   # unreachable now: requests will connect when they need to
            return None

    with ThreadPoolExecutor(max_workers=count) as pool:
        conns = list(pool.map(open_one, range(count)))
    for c in conns:
        if c is not None:
            c.close()   # back to the pool, still open


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(get_engine(), expire_on_commit=False)


# GET routes that write and must stay atomic: the Telegram sign-in claim (claim once, create the
# session, audit) and the audited source description.
TRANSACTIONAL_GETS = re.compile(r"^/api/(auth/telegram/status|sources/[^/]+/describe)$")


@lru_cache
def get_read_sessionmaker() -> sessionmaker[Session]:
    """Sessions without BEGIN/COMMIT (each statement commits on its own): two round trips fewer
    per read request against a remote database."""
    return sessionmaker(get_engine().execution_options(isolation_level="AUTOCOMMIT"),
                        expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """One transaction per request: commit on success, roll back on any error. GET/HEAD
    requests only read (plus single-statement bookkeeping such as the session's last-seen time),
    so they run without an explicit transaction.

    Always used through `DB` below (scope "function"): the commit must happen before the
    response is sent, or a client can act on it (e.g. use a new session cookie) before the data
    exists. FastAPI's default for yield dependencies runs the exit code after the response.
    """
    reads_only = (request.method in ("GET", "HEAD")
                  and not TRANSACTIONAL_GETS.match(request.url.path))
    db = (get_read_sessionmaker() if reads_only else get_sessionmaker())()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Request-scoped transaction that commits before the response is sent.
DB = Depends(get_db, scope="function")
