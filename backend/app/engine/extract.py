"""Extraction from origins with the feature 004 connectors (feature 005, research R4).

PostgreSQL: the spec's single read-only SELECT (checked again here with the shared rules) in a
read-only transaction, streamed through a server-side cursor; `:window_start`/`:window_end` are
bound as parameters, never spliced. REST/SOAP: the request definition, paginated, records and
fields picked by simple JSON paths. Every function yields batches of rows keyed by column.
Extraction can be interrupted from another thread through a Cancel (feature 013, US2).
"""
import json
import re
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from datetime import UTC, date, datetime
from decimal import Decimal
from itertools import pairwise
from typing import TypeVar
from urllib.parse import urljoin, urlsplit

import httpx
import psycopg
from bizview_cli import sqlsafety
from psycopg import sql as pgsql
from sqlglot.tokens import Tokenizer, TokenType

from app.config import Settings
from app.i18n import M
from app.security import profile
from app.security.netguard import guarded_client, policy_from_settings
from app.sources.connectors import postgresql, rest, soap
from app.sources.connectors.base import temp_pem

T = TypeVar("T")

BATCH_ROWS = 20_000
MAX_PAGE_BYTES = 20_000_000
DEFAULT_MAX_PAGES = 1_000


class Cancelled(Exception):
    """The run was stopped from another thread (feature 013, US2)."""


class Cancel:
    """Lets another thread interrupt blocking extraction work: cancels the running statement of
    every tracked psycopg connection (origin and destination) with cancel_safe(), closes tracked
    HTTP clients and wakes up call()."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._conns: list[psycopg.Connection] = []
        self._closers: list[Callable[[], None]] = []

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @contextmanager
    def track(self, conn: psycopg.Connection) -> Iterator[None]:
        if self.cancelled:
            raise Cancelled()
        with self._lock:
            self._conns.append(conn)
        try:
            yield
        finally:
            with self._lock:
                self._conns.remove(conn)

    @contextmanager
    def closing(self, close: Callable[[], None]) -> Iterator[None]:
        if self.cancelled:
            raise Cancelled()
        with self._lock:
            self._closers.append(close)
        try:
            yield
        finally:
            with self._lock:
                self._closers.remove(close)

    def cancel(self) -> None:
        self._event.set()
        with self._lock:
            conns = list(self._conns)
            closers = list(self._closers)
        for conn in conns:
            try:
                conn.cancel_safe(timeout=5)
            except Exception:
                pass
        for close in closers:
            try:
                close()
            except Exception:
                pass

    def call(self, fn: Callable[[], T]) -> T:
        if self.cancelled:
            raise Cancelled()
        done = threading.Event()
        result: dict[str, object] = {}

        def runner_thread() -> None:
            try:
                result["value"] = fn()
            except BaseException as e:
                result["error"] = e
            finally:
                done.set()

        thread = threading.Thread(target=runner_thread, name="extract-call", daemon=True)
        thread.start()
        while not done.wait(0.1):
            if self._event.is_set():
                raise Cancelled()
        if "error" in result:
            raise result["error"]  # type: ignore[operator]
        return result["value"]  # type: ignore[return-value]


def _tracked(cancel: Cancel | None, conn: psycopg.Connection):
    return cancel.track(conn) if cancel is not None else nullcontext()


def _closing(cancel: Cancel | None, close: Callable[[], None]):
    return cancel.closing(close) if cancel is not None else nullcontext()


def _call[R](cancel: Cancel | None, fn: Callable[[], R]) -> R:
    return cancel.call(fn) if cancel is not None else fn()


class ExtractError(Exception):
    """A run failure whose message is safe to store and show (no credentials)."""


class ExtractTimeout(ExtractError):
    """The origin did not answer in time."""


TIMEZONE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+){0,2}")


def check_timezone(name: str) -> str:
    """IANA name only: it goes into the origin session options (`-c TimeZone=…`), so anything
    else could smuggle other settings (e.g. turn off the read-only transaction)."""
    from zoneinfo import ZoneInfo

    if not isinstance(name, str) or len(name) > 64 or not TIMEZONE_RE.fullmatch(name):
        raise ExtractError(M("extract.bad_timezone"))
    try:
        ZoneInfo(name)
    except Exception:
        raise ExtractError(f"zona horaria desconocida: {name}") from None
    return name


def same_origin(base: str, url: str) -> str:
    """Credentials of a source are only ever sent to the source's own scheme and host."""
    if urlsplit(url)[:2] != urlsplit(base)[:2]:
        raise ExtractError(M("extract.other_host"))
    return url


# --- SQL -----------------------------------------------------------------------------------------

def to_psycopg(query: str) -> str:
    """`:name` placeholders → `%(name)s`, every other `%` doubled. Positions come from the SQL
    tokenizer, so `::casts`, string literals and comments are left alone."""
    problems = sqlsafety.check_query(query)
    if problems:
        raise ExtractError(f"consulta no permitida: {problems[0].message}")
    tokens = Tokenizer(dialect="postgres").tokenize(query)
    spans = []
    for a, b in pairwise(tokens):
        if a.token_type == TokenType.COLON and b.start == a.end + 1 and b.text in sqlsafety.PARAMS:
            spans.append((a.start, b.end + 1, b.text))
    out, pos = [], 0
    for start, end, name in spans:
        out += [query[pos:start].replace("%", "%%"), f"%({name})s"]
        pos = end
    out.append(query[pos:].replace("%", "%%"))
    return "".join(out).rstrip().rstrip(";")


def _pg_connect(settings: dict, secrets: dict, app: Settings, *, timezone: str,
                time_limit_s: int, connect_timeout_s: int | None = None) -> psycopg.Connection:
    check_timezone(timezone)
    if profile.sslmode_problem(settings.get("sslmode") or "require", app):
        raise ExtractError("la fuente requiere TLS en el perfil de seguridad actual")
    with temp_pem(settings.get("ca_certificate")) as ca_path:
        kwargs = postgresql.connect_kwargs(settings, secrets, app, ca_path)
        if connect_timeout_s is not None:
            current = int(kwargs.get("connect_timeout") or connect_timeout_s)
            kwargs["connect_timeout"] = max(1, min(current, connect_timeout_s))
        kwargs["options"] = (f"-c default_transaction_read_only=on "
                             f"-c statement_timeout={time_limit_s * 1000} -c TimeZone={timezone}")
        kwargs["application_name"] = "bizview-engine"
        return psycopg.connect(**kwargs)


def pg_rows(settings: dict, secrets: dict, app: Settings, query: str, params: dict, *,
            timezone: str, time_limit_s: int,
            cancel: Cancel | None = None) -> Iterator[tuple[list[str], list[tuple]]]:
    """Stream `(columns, rows)` batches of the extraction query."""
    q = to_psycopg(query)
    with _pg_connect(settings, secrets, app, timezone=timezone,
                     time_limit_s=time_limit_s) as conn, _tracked(cancel, conn), \
            conn.cursor(name="bizview_extract") as cur:
        cur.itersize = BATCH_ROWS
        cur.execute(q, params)
        columns = [d.name for d in cur.description or []]
        while True:
            rows = cur.fetchmany(BATCH_ROWS)
            if not rows:
                if columns:
                    yield columns, []
                break
            yield columns, rows
            columns = [d.name for d in cur.description or []]


BULK_SESSION = ("SET DateStyle = 'ISO, MDY'", "SET IntervalStyle = 'postgres'",
                "SET extra_float_digits = 3", "SET bytea_output = 'hex'")
BULK_UNSUPPORTED = (psycopg.errors.FeatureNotSupported, psycopg.errors.InsufficientPrivilege,
                    psycopg.errors.SyntaxError, psycopg.errors.UndefinedFunction)
SESSION_UNSUPPORTED = (psycopg.errors.FeatureNotSupported, psycopg.errors.UndefinedObject,
                       psycopg.errors.InvalidParameterValue, psycopg.errors.CantChangeRuntimeParam)
TIME_LIMIT = M("run.timeout")


class BulkUnsupported(Exception):
    """The origin refused `COPY (query) TO STDOUT` before sending any data (feature 008)."""

    def __init__(self, reason: str) -> None:
        # The SQLSTATE class name only: error messages may echo SQL or values.
        self.reason = reason
        super().__init__(reason)


class _WriteFailed(Exception):
    """Wraps an error raised by the destination, so it is not mistaken for an origin error."""

    def __init__(self, error: BaseException) -> None:
        self.error = error


def _first_line(e: Exception) -> str:
    return (str(e).splitlines() or [type(e).__name__])[0][:300]


def columns_mismatch(got: list[str], expected: list[str]) -> ExtractError | None:
    if set(got) == set(expected) and len(got) == len(expected):
        return None
    missing, extra = set(expected) - set(got), set(got) - set(expected)
    return ExtractError("las columnas de la consulta no coinciden con el contrato "
                        f"(faltan {sorted(missing)}, sobran {sorted(extra)})")


def pg_copy(settings: dict, secrets: dict, app: Settings, query: str, params: dict, *,
            columns: list[str], timezone: str, time_limit_s: int, deadline: float,
            write: Callable[[bytes], None],
            check: Callable[[], None] | None = None,
            cancel: Cancel | None = None) -> int:
    """Stream `COPY (query) TO STDOUT (FORMAT text)` block by block into `write` (feature 008,
    contracts/engine.md); returns the number of blocks written. No row becomes a Python value.
    `check` is called every block (before copying it) to allow a run to be stopped."""
    q = to_psycopg(query)
    blocks = 0
    with _pg_connect(settings, secrets, app, timezone=timezone,
                     time_limit_s=time_limit_s) as conn, _tracked(cancel, conn):
        for stmt in BULK_SESSION:          # deterministic text output (research R4)
            try:
                conn.execute(stmt)
            except SESSION_UNSUPPORTED as e:
                raise BulkUnsupported(type(e).__name__) from None
            except psycopg.Error as e:
                raise ExtractError(M("extract.failed", detail=_first_line(e))) from None
        # COPY takes no bind parameters: quote the engine's window datetimes client-side.
        rendered = psycopg.ClientCursor(conn).mogrify(q, params)
        probe = pgsql.SQL("SELECT * FROM ({}\n) AS q LIMIT 0").format(pgsql.SQL(rendered))
        with conn.cursor() as cur:
            try:
                cur.execute(probe, prepare=False)   # no params: `%` is not interpreted
                got = [c.name for c in cur.description or ()]
            except psycopg.errors.QueryCanceled:
                raise ExtractError(TIME_LIMIT) from None
            except psycopg.Error as e:
                raise ExtractError(M("extract.failed", detail=_first_line(e))) from None
        mismatch = columns_mismatch(got, columns)
        if mismatch:
            raise mismatch
        stmt = pgsql.SQL("COPY (SELECT {} FROM ({}\n) AS q) TO STDOUT (FORMAT text)").format(
            pgsql.SQL(", ").join(map(pgsql.Identifier, columns)), pgsql.SQL(rendered))
        try:
            with conn.cursor() as cur, cur.copy(stmt) as cp:
                for block in cp:
                    if time.monotonic() > deadline:
                        raise ExtractError(TIME_LIMIT)
                    if check is not None:
                        check()
                    try:
                        write(bytes(block))
                    except psycopg.Error as e:
                        raise _WriteFailed(e) from None
                    blocks += 1
        except _WriteFailed as w:
            raise w.error from None        # destination errors keep their own meaning
        except BULK_UNSUPPORTED as e:
            if blocks == 0:                # nothing sent yet: the runner may fall back
                raise BulkUnsupported(type(e).__name__) from None
            raise ExtractError(M("extract.failed", detail=_first_line(e))) from None
        except psycopg.errors.QueryCanceled:
            raise ExtractError(TIME_LIMIT) from None
        except psycopg.Error as e:
            raise ExtractError(M("extract.failed", detail=_first_line(e))) from None
    return blocks


def pg_all(settings: dict, secrets: dict, app: Settings, query: str, params: dict, *,
           timezone: str, time_limit_s: int, limit: int = 100_000,
           cancel: Cancel | None = None) -> tuple[list[str], list]:
    with _pg_connect(settings, secrets, app, timezone=timezone,
                     time_limit_s=time_limit_s) as conn, _tracked(cancel, conn):
        cur = conn.execute(to_psycopg(query), params)
        rows = cur.fetchmany(limit + 1)
        if len(rows) > limit:
            raise ExtractError(M("extract.reconcile_too_many", limit=limit))
        return [d.name for d in cur.description or []], rows


# --- JSON paths ----------------------------------------------------------------------------------

_PATH_PART = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def json_path(obj, path: str):
    """Minimal JSONPath: `$`, `$.a.b`, `a.b[0].c`. Missing parts → None."""
    path = path.strip()
    if path in ("", "$"):
        return obj
    if path.startswith("$"):
        path = path[1:].lstrip(".")
    for name, index in _PATH_PART.findall(path):
        if obj is None:
            return None
        if name:
            obj = obj.get(name) if isinstance(obj, dict) else None
        else:
            i = int(index)
            obj = obj[i] if isinstance(obj, list) and i < len(obj) else None
    return obj


def text_value(value) -> str | None:
    """JSON/SOAP value → text PostgreSQL parses for the contract type (on COPY)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, int | float | Decimal | str):
        return str(value)
    return json.dumps(value, default=str, ensure_ascii=False)


def _substitute(value, params: dict):
    """`{window_start}`, `{window_end}` (ISO timestamps) and `{window_start_date}`,
    `{window_end_date}` inside strings of params, body and path."""
    if isinstance(value, str):
        for name, v in params.items():
            value = value.replace("{" + name + "}", v.isoformat())
            value = value.replace("{" + name + "_date}", v.date().isoformat())
        return value
    if isinstance(value, dict):
        return {k: _substitute(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, params) for v in value]
    return value


def _field_text(value, unit: str | None) -> str | None:
    """`timestamp_units` applied at extraction (041): a declared epoch becomes ISO-8601 UTC.

    Anything that is not a plain number under `seconds`/`milliseconds` passes through raw, so
    PostgreSQL still names genuinely bad data; `iso8601` and undeclared columns are untouched.
    """
    if unit not in ("seconds", "milliseconds") or value is None or isinstance(value, bool):
        return text_value(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return text_value(value)
    if unit == "milliseconds":
        number /= 1000
    try:
        return datetime.fromtimestamp(number, UTC).isoformat()
    except (OverflowError, OSError, ValueError):
        return text_value(value)


def _records(payload, request: dict, columns: list[str]) -> list[dict]:
    records = json_path(payload, request["records"])
    if records is None:
        return []
    if not isinstance(records, list):
        raise ExtractError(f"'{request['records']}' no es una lista en la respuesta")
    fields = request["fields"]
    missing = [c for c in columns if c not in fields]
    if missing:
        raise ExtractError(M("extract.missing_fields", fields=", ".join(sorted(missing))))
    units = request.get("timestamp_units")
    if not isinstance(units, dict):
        units = {}
    return [
        {c: _field_text(json_path(r, fields[c]), units.get(c)) for c in columns}
        for r in records
    ]


def _paginate(fetch: Callable[[dict, str | None], tuple[object, dict]], request: dict,
              columns: list[str]) -> Iterator[list[dict]]:
    """Drive pagination. `fetch(extra_params, url_override)` → (payload, headers)."""
    page = request.get("pagination") or {"type": "none"}
    kind, size = page["type"], page.get("size")
    max_pages = page.get("max_pages") or DEFAULT_MAX_PAGES
    extra: dict = {}
    if size and page.get("size_param"):
        extra[page["size_param"]] = size
    if kind == "page":
        extra[page.get("param") or "page"] = 1
    elif kind == "offset":
        extra[page.get("param") or "offset"] = 0
    url = None
    for _ in range(max_pages):
        payload, headers = fetch(extra, url)
        rows = _records(payload, request, columns)
        if rows:
            yield rows
        if kind == "none" or not rows:
            return
        if kind == "page":
            if size and len(rows) < size:
                return
            extra[page.get("param") or "page"] += 1
        elif kind == "offset":
            if size and len(rows) < size:
                return
            extra[page.get("param") or "offset"] += len(rows)
        elif kind == "cursor":
            cursor = json_path(payload, page.get("cursor_path") or "$.next_cursor")
            if cursor in (None, ""):
                return
            extra[page.get("param") or "cursor"] = cursor
        elif kind == "link":
            url = _next_link(headers.get("link", ""))
            if not url:
                return
    raise ExtractError(M("extract.max_pages", max=max_pages))


def _next_link(header: str) -> str | None:
    for part in header.split(","):
        m = re.match(r'\s*<([^>]+)>\s*;(.*)', part)
        if m and re.search(r'rel\s*=\s*"?next"?', m.group(2)):
            return m.group(1)
    return None


def supabase_rows(settings: dict, secrets: dict, *args, **kwargs) -> Iterator[list[dict]]:
    """Supabase (feature 016): the REST extraction against <url>/rest/v1/ with its key."""
    from app.sources.connectors import supabase
    return rest_rows(supabase.rest_settings(settings), supabase.rest_secrets(secrets),
                     *args, **kwargs)


def rest_rows(settings: dict, secrets: dict, app: Settings, request: dict, params: dict,
              columns: list[str], *, time_limit_s: int,
              cancel: Cancel | None = None) -> Iterator[list[dict]]:
    base = settings["base_url"].rstrip("/") + "/"
    for key in ("base_url", "token_url"):
        if settings.get(key) and profile.url_problem(settings[key], app):
            raise ExtractError("la fuente requiere HTTPS en el perfil de seguridad actual")
    method = request.get("method") or "GET"
    path = _substitute(request.get("path") or "", params).lstrip("/")
    query = _substitute(request.get("params") or {}, params)
    body = _substitute(request.get("body"), params)
    timeout = float(min(time_limit_s, max(15, int(settings.get("timeout_seconds") or 15) * 4)))
    first = same_origin(base, urljoin(base, path))
    with guarded_client(policy=policy_from_settings(app), timeout=timeout,
                        verify=rest._verify(settings)) as client, _closing(cancel, client.close):
        headers, auth_params, auth = _call(cancel, lambda: rest.build_request(
            settings, secrets, client))

        def fetch(extra: dict, url: str | None):
            def get():
                if url is None:
                    target, q = first, {**query, **auth_params, **extra}
                else:
                    target, q = same_origin(base, urljoin(base, url)), auth_params
                with client.stream(method, target, headers=headers, params=q, auth=auth,
                                   json=body if method == "POST" else None) as r:
                    data = b""
                    for chunk in r.iter_bytes():
                        data += chunk
                        if len(data) > MAX_PAGE_BYTES:
                            raise ExtractError(M("extract.too_large"))
                    if r.status_code >= 300:
                        raise ExtractError(M("sources.http_status", status=r.status_code))
                    try:
                        return json.loads(data), dict(r.headers)
                    except ValueError:
                        raise ExtractError("la respuesta no es JSON") from None

            return _call(cancel, get)

        try:
            yield from _paginate(fetch, request, columns)
        except rest.OAuthError as e:
            raise ExtractError(M("extract.auth_rejected", detail=str(e))) from None
        except httpx.HTTPError as e:
            raise ExtractError(f"error de red: {type(e).__name__}") from None


def rest_once(settings: dict, secrets: dict, app: Settings, request: dict, params: dict, *,
              extra_params: dict | None = None, extra_headers: dict | None = None,
              time_limit_s: int) -> tuple[object, dict]:
    """One GET of a request definition (feature 017: check_query, profile_source) under the
    same HTTPS-profile, netguard, same-origin and size rules as rest_rows. Returns
    (payload or None when the body is empty, response headers with lower-case names)."""
    base = settings["base_url"].rstrip("/") + "/"
    for key in ("base_url", "token_url"):
        if settings.get(key) and profile.url_problem(settings[key], app):
            raise ExtractError("la fuente requiere HTTPS en el perfil de seguridad actual")
    method = (request.get("method") or "GET").upper()
    if method != "GET":
        raise ExtractError("solo se comprueban peticiones GET")
    path = _substitute(request.get("path") or "", params).lstrip("/")
    query = _substitute(request.get("params") or {}, params)
    timeout = float(min(time_limit_s, 30))
    target = same_origin(base, urljoin(base, path))
    with guarded_client(policy=policy_from_settings(app), timeout=timeout,
                        verify=rest._verify(settings)) as client:
        try:
            headers, auth_params, auth = rest.build_request(settings, secrets, client)
            headers = {**(extra_headers or {}), **headers}
            q = {**query, **auth_params, **(extra_params or {})}
            with client.stream(method, target, headers=headers, params=q, auth=auth) as r:
                data = b""
                for chunk in r.iter_bytes():
                    data += chunk
                    if len(data) > MAX_PAGE_BYTES:
                        raise ExtractError(M("extract.too_large"))
                if r.status_code >= 300:
                    raise ExtractError(M("sources.http_status", status=r.status_code))
                lower_headers = {k.lower(): v for k, v in r.headers.items()}
                if not data:
                    return None, lower_headers
                try:
                    return json.loads(data), lower_headers
                except ValueError:
                    raise ExtractError("la respuesta no es JSON") from None
        except rest.OAuthError as e:
            raise ExtractError(M("extract.auth_rejected", detail=str(e))) from None
        except httpx.TimeoutException:
            raise ExtractTimeout("tiempo agotado") from None
        except httpx.HTTPError as e:
            raise ExtractError(f"error de red: {type(e).__name__}") from None


def supabase_once(settings: dict, secrets: dict, *args, **kwargs) -> tuple[object, dict]:
    """Supabase one-shot GET: translate Supabase source settings/secrets to REST."""
    from app.sources.connectors import supabase
    return rest_once(supabase.rest_settings(settings), supabase.rest_secrets(secrets),
                     *args, **kwargs)


def soap_rows(settings: dict, secrets: dict, app: Settings, request: dict, params: dict,
              columns: list[str], *, time_limit_s: int,
              cancel: Cancel | None = None) -> Iterator[list[dict]]:
    from zeep.helpers import serialize_object

    if profile.url_problem(settings["wsdl_url"], app):
        raise ExtractError("la fuente requiere HTTPS en el perfil de seguridad actual")
    operation = request.get("operation")
    if not operation:
        raise ExtractError(M("extract.soap_operation_required"))
    call_params = _substitute(request.get("params") or {}, params)
    timeout = float(min(time_limit_s, max(15, int(settings.get("timeout_seconds") or 15) * 4)))
    with temp_pem(settings.get("client_certificate")) as cert_path, \
            temp_pem(secrets.get("client_key")) as key_path:
        cert = (cert_path, key_path) if cert_path and key_path else None
        http_client = guarded_client(policy=policy_from_settings(app), timeout=timeout,
                                     verify=rest._verify(settings), cert=cert)
    with http_client, _closing(cancel, http_client.close):
        client = _call(cancel, lambda: soap.build_client(settings, secrets, app, http_client))

        def fetch(extra: dict, _url):
            try:
                result = _call(cancel, lambda: getattr(client.service, operation)(
                    **{**call_params, **extra}))
            except Cancelled:
                raise
            except AttributeError:
                raise ExtractError(
                    M("extract.soap_operation_missing", operation=operation)
                ) from None
            except Exception as e:
                raise ExtractError(
                    M("extract.soap_operation_failed", error=type(e).__name__)
                ) from None
            return serialize_object(result, dict), {}

        yield from _paginate(fetch, request, columns)
