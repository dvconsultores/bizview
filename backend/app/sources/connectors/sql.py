"""Shared plumbing for the SQL kinds that speak DB-API 2.0 (feature 061).

SQLite, MySQL/MariaDB and SQL Server differ in their driver, their quoting, their way of saying
"this session is read-only" and their congestion message. Everything else — streaming a query in
batches, refusing a statement that is not a read, reporting the structure in the same shape
PostgreSQL does, and turning a driver error into the verdict card the product shows — is the same,
and lives here so a new kind is a small module.

Riding on DB-API is deliberate: `sqlite3` is stdlib, `PyMySQL` and `pymssql` are pure-Python or
wheel-only, so the published image needs no system package (research R2).
"""
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.ai import redact
from app.config import Settings
from app.sources.connectors.base import TestResult, fail

BATCH_ROWS = 20_000
CONNECT_TIMEOUT_S = 10
#: Sentences a read may begin with. Anything else is refused before it reaches the origin: no
#: engine here has a session-wide read-only switch as reliable as PostgreSQL's (spec FR-011).
READ_STARTS = re.compile(r"^\s*(select|with|show|describe|desc|explain|pragma)\b", re.IGNORECASE)
#: A statement word that writes. `WITH … DELETE` starts like a read, so the sentence is scanned
#: too, once its comments and literals are gone (a `'delete'` value is not a statement).
WRITES = re.compile(r"\b(insert|update|delete|merge|upsert|drop|create|alter|truncate|grant|"
                    r"revoke|call|exec|execute|copy|vacuum|reindex|attach|detach)\b",
                    re.IGNORECASE)
COMMENT_OR_SPACE = re.compile(r"^(\s+|--[^\n]*\n|/\*.*?\*/)*", re.DOTALL)
COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
LITERALS = re.compile(r"'(?:[^']|'')*'|\$(\$)?.*?\1\$", re.DOTALL)


class NotAllowed(Exception):
    """The security profile forbids this connection (plain text on the internet profile)."""


class ReadOnlyRefused(Exception):
    """The statement is not a read; nothing was sent to the origin."""


def read_only_query(query: str) -> str:
    """The query, or `ReadOnlyRefused` — the second layer of the read-only rule."""
    stripped = COMMENT_OR_SPACE.sub("", query)
    if not READ_STARTS.match(stripped):
        raise ReadOnlyRefused(query.strip()[:40])
    body = LITERALS.sub("''", COMMENTS.sub(" ", stripped))
    if WRITES.search(body):
        raise ReadOnlyRefused(query.strip()[:40])
    return query


def first_line(error: BaseException) -> str:
    text = str(error) or type(error).__name__
    return text.splitlines()[0][:300]


def safe(error: BaseException, secrets: dict) -> str:
    """The driver's first line with every secret value and every host removed."""
    text = first_line(error)
    for value in secrets.values():
        if isinstance(value, str) and len(value) >= 4:
            text = redact(text, value, limit=2_000)
    return redact(text, None, limit=300)


def quote(kind: str, name: str) -> str:
    """The identifier as this dialect writes it."""
    if kind == "mysql":
        return "`" + name.replace("`", "``") + "`"
    if kind == "mssql":
        return "[" + name.replace("]", "]]") + "]"
    return '"' + name.replace('"', '""') + '"'


def read_only_prefix(kind: str) -> str | None:
    """The statement that makes the session read-only, where the engine has one."""
    if kind == "mysql":
        return "SET SESSION TRANSACTION READ ONLY"
    if kind == "sqlite":
        return "PRAGMA query_only = ON"
    return None


@contextmanager
def session(connect: Callable[[], object], kind: str, *, time_limit_s: int) -> Iterator[object]:
    """A DB-API connection that cannot write: session flag where it exists, always closed."""
    conn = connect()
    try:
        cur = conn.cursor()
        prefix = read_only_prefix(kind)
        if prefix:
            try:
                cur.execute(prefix)
            except Exception:        # an older engine without the flag: the query rule still holds
                pass
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def rows(conn, query: str, params: dict | None, batch: int = BATCH_ROWS,
         check: Callable[[], None] | None = None) -> Iterator[tuple[list[str], list[tuple]]]:
    """Stream `(columns, rows)` batches of a read, never the whole result in memory."""
    read_only_query(query)
    cur = conn.cursor()
    try:
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        columns = [d[0] for d in (cur.description or [])]
        while True:
            if check is not None:
                check()
            chunk = cur.fetchmany(batch)
            if not chunk:
                break
            yield columns, [tuple(r) for r in chunk]
        if columns:
            yield columns, []
    finally:
        try:
            cur.close()
        except Exception:
            pass


def row_count(conn, query: str, params: dict | None = None) -> int:
    read_only_query(query)
    cur = conn.cursor()
    try:
        cur.execute(query, params) if params else cur.execute(query)
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        try:
            cur.close()
        except Exception:
            pass


def test_connection(kind: str, connect: Callable[[], object], *, version_query: str,
                    read_only_query_sql: str | None,
                    extra: Callable[[object], tuple[list[str], dict]] | None = None,
                    secrets: dict, app: Settings) -> TestResult:
    """The verdict card: reachable, authenticated, the database answered, read, TLS.

    `extra` adds the kind's own warnings and details (Griff: whether the login may write).
    """
    # A driver error here is classified per kind by the caller, which knows its own messages.
    conn = connect()
    warnings: list[str] = []
    details: dict = {}
    try:
        cur = conn.cursor()
        try:
            cur.execute(version_query)
            row = cur.fetchone()
        finally:
            cur.close()
        details["server_version"] = str(row[0])[:120] if row else ""
        if read_only_query_sql:
            cur = conn.cursor()
            try:
                cur.execute(read_only_query_sql)
                answer = cur.fetchone()
            except Exception:
                answer = None
            finally:
                cur.close()
            if answer is not None and not answer[0]:
                warnings.append("not_read_only")
        if extra is not None:
            extra_warnings, extra_details = extra(conn)
            warnings.extend(extra_warnings)
            details.update(extra_details)
    except Exception as e:
        return fail("error", safe(e, secrets), secrets)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return TestResult(True, warnings=warnings, details=details)
