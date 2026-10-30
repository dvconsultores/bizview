"""Integration runs (feature 005, research R4, FR-007 to FR-010).

One run = every dataset of one integration, all-or-nothing:

1. one advisory lock per integration (no overlapping runs); `running` rows left by a crashed
   worker are closed as failed;
2. per dataset: create/evolve the table, extract from the origin into a typed staging table
   (COPY; PostgreSQL itself applies the contract types), run the contract and spec checks;
3. only when every dataset passed: replace the window (or everything, for full loads) in one
   transaction. Any failure rolls back, so reports keep the previous data. For reports with
   `materialize: daily`, the rollups are refreshed inside the same publish transaction under a
   savepoint: a rollup failure keeps the data, marks the rollup stale and is recorded in
   `integration_run.rollups`.

Runs also honour a cooperative stop request (feature 013, US2): the runner checks the flag
between blocks, batches, checks and loads, and a watchdog thread polls it every 2 s and cancels
blocking origin/destination statements and HTTP calls, so a stop ends the run within seconds;
errors caused by that cancel are recorded as 'stopped'.

Messages stored in `integration_run.message` never contain credentials.
"""
import copy
import io
import logging
import queue
import threading
import time
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl
import psycopg
import yaml
from psycopg import sql
from psycopg.copy import QueuedLibpqWriter
from psycopg.generators import copy_to
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ai import redact
from app.config import Settings, get_settings
from app.db import get_engine, get_sessionmaker, lock_key
from app.engine import datasets, extract, rollup, transform
from app.engine.extract import ExtractError
from app.i18n import M, t, to_stored
from app.images import cache as images_cache
from app.models import AppUser, DataSource, IntegrationRun, WorkspaceVersion
from app.sources import service as sources

log = logging.getLogger("app.engine")
EPOCH = date(1900, 1, 1)
FULL_KINDS = ("full", "manual_full")


@dataclass
class Plan:
    name: str
    ds: dict
    full: bool
    start: datetime
    end: datetime
    table: datasets.TableState | None = None
    extracted: int = 0
    written: int = 0
    checks: list[dict] = field(default_factory=list)
    path: str = "rows"              # feature 008: "copy" | "rows" | "copy+polars" | "rows+polars"
    fallback: str | None = None     # SQLSTATE class name when the origin refused COPY
    transform_mode: str | None = None
    rows_in: int = 0
    transform_ms: int = 0


def window(ds: dict, *, full: bool, now: datetime, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Incremental: from local midnight `window_days` ago until now. Full: everything."""
    if full or "window_days" not in (ds.get("incremental") or {}):
        return datetime.combine(EPOCH, datetime.min.time(), tz), now
    local_today = now.astimezone(tz).date()
    start = local_today - timedelta(days=ds["incremental"]["window_days"])
    return datetime.combine(start, datetime.min.time(), tz), now


def _lock_key(integration_id: str) -> str:
    return lock_key("integration", integration_id)


def _stage(pg: psycopg.Connection, schema: str, name: str, columns: list[str]) -> str:
    staging = f"_stg_{name}"
    pg.execute(sql.SQL("CREATE TEMP TABLE {} ON COMMIT DROP AS SELECT {} FROM {}.{} WITH NO DATA")
               .format(sql.Identifier(staging), sql.SQL(", ").join(map(sql.Identifier, columns)),
                       sql.Identifier(schema), sql.Identifier(name)))
    return staging


def _copy(pg: psycopg.Connection, staging: str, columns: list[str], frame: pl.DataFrame) -> None:
    if frame.height == 0:
        return
    data = frame.select(columns).write_csv(include_header=False, null_value=r"\N")
    stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, NULL '\\N')").format(
        sql.Identifier(staging), sql.SQL(", ").join(map(sql.Identifier, columns)))
    try:
        with pg.cursor().copy(stmt) as cp:
            cp.write(data.encode())
    except psycopg.errors.DataError as e:
        raise ExtractError(M("run.contract", detail=_first_line(e))) from None


def _first_line(e: Exception) -> str:
    return (str(e).splitlines() or [type(e).__name__])[0][:300]


def _text_frame(rows: list, columns: list[str]) -> pl.DataFrame:
    """Rows → an all-text frame; PostgreSQL parses each value for the contract type on COPY."""
    if rows and isinstance(rows[0], dict):
        data = {c: [r.get(c) for r in rows] for c in columns}
    else:
        data = {c: [extract.text_value(r[i]) for r in rows] for i, c in enumerate(columns)}
    return pl.DataFrame(data, schema={c: pl.String for c in columns})


def _copy_bulk(pg: psycopg.Connection, staging: str, columns: list[str], *,
               source: DataSource, secrets: dict, app: Settings, query: str, params: dict,
               tz: str, time_left: int, deadline: float,
               check: Callable[[], None],
               cancel: extract.Cancel | None = None) -> int:
    """Feature 008: pipe the origin's COPY output into the typed staging table; returns rows.
    The destination COPY opens on the first block, so a refusal before any data leaves the
    runner's transaction usable for the fallback."""
    stmt = sql.SQL("COPY {} ({}) FROM STDIN (FORMAT text)").format(
        sql.Identifier(staging), sql.SQL(", ").join(map(sql.Identifier, columns)))
    cur = pg.cursor()
    opened = False
    try:
        with ExitStack() as stack:
            dest = None

            def write(block: bytes) -> None:
                nonlocal dest, opened
                if dest is None:
                    dest = stack.enter_context(cur.copy(stmt))
                    opened = True
                dest.write(block)

            extract.pg_copy(source.settings, secrets, app, query, params, columns=columns,
                            timezone=tz, time_limit_s=time_left, deadline=deadline,
                            write=write, check=check, cancel=cancel)
    except psycopg.errors.DataError as e:   # raised on write or when the COPY ends
        raise ExtractError(M("run.contract", detail=_first_line(e))) from None
    return cur.rowcount if opened else 0


def _extract_rows(pg: psycopg.Connection, plan: Plan, staging: str, *, source: DataSource,
                  secrets: dict, app: Settings, query: str, params: dict, deadline: float,
                  tz: str, check: Callable[[], None],
                  cancel: extract.Cancel | None = None) -> None:
    """Row path (feature 005): fallback for origins that refuse COPY (query) TO STDOUT."""
    columns = list(plan.ds["columns"])
    time_left = max(1, int(deadline - time.monotonic()))
    for got, rows in extract.pg_rows(source.settings, secrets, app, query, params,
                                     timezone=tz, time_limit_s=time_left, cancel=cancel):
        mismatch = extract.columns_mismatch(got, columns)
        if mismatch:
            raise mismatch
        frame = _text_frame(rows, got)
        _copy(pg, staging, columns, frame)
        plan.extracted += frame.height
        if time.monotonic() > deadline:
            raise ExtractError(M("run.timeout"))
        check()


def _extract(pg: psycopg.Connection, plan: Plan, staging: str, *, integration: dict,
             files: dict, source: DataSource, secrets: dict, app: Settings, deadline: float,
             tz: str, check: Callable[[], None],
             cancel: extract.Cancel | None = None,
             spill_label: str | None = None) -> None:
    ds, columns = plan.ds, list(plan.ds["columns"])
    params = {"window_start": plan.start, "window_end": plan.end}
    time_left = max(1, int(deadline - time.monotonic()))
    compiled = transform.compile(ds, tz)
    if compiled is not None:
        _extract_transformed(pg, plan, staging, compiled, files=files, source=source,
                             secrets=secrets, app=app, params=params, time_left=time_left,
                             deadline=deadline, tz=tz, check=check, cancel=cancel,
                             spill_label=spill_label)
        return
    ext = ds["extract"]
    if "query" in ext:
        if source.kind != "postgresql":
            raise ExtractError(M("run.sql_needs_postgres"))
        query = files[ext["query"]]
        plan.path = "copy"
        try:
            plan.extracted = _copy_bulk(pg, staging, columns, source=source, secrets=secrets,
                                        app=app, query=query, params=params, tz=tz,
                                        time_left=time_left, deadline=deadline, check=check,
                                        cancel=cancel)
        except extract.BulkUnsupported as e:
            plan.path, plan.fallback = "rows", e.reason
            log.info("%s: extracción por filas (%s)", plan.name, e.reason)
            _extract_rows(pg, plan, staging, source=source, secrets=secrets, app=app,
                          query=query, params=params, deadline=deadline, tz=tz, check=check,
                          cancel=cancel)
    else:
        request = yaml.safe_load(files[ext["request"]])
        fn = {"rest": extract.rest_rows, "soap": extract.soap_rows,
              "supabase": extract.supabase_rows}.get(source.kind)
        if fn is None:
            raise ExtractError(M("run.request_needs_http"))
        for rows in fn(source.settings, secrets, app, request, params, columns,
                       time_limit_s=time_left, cancel=cancel):
            frame = _text_frame(rows, columns)
            _copy(pg, staging, columns, frame)
            plan.extracted += frame.height
            if time.monotonic() > deadline:
                raise ExtractError(M("run.timeout"))
            check()


COPY_QUEUE_ITEMS = 64


class _BoundedWriter(QueuedLibpqWriter):
    """Bound the COPY writer: queue holds at most 64 items of ≤128 KiB, and each item is
    flushed to the network so libpq's output buffer cannot grow without bound; this still
    overlaps the upload with the origin download. Relies on psycopg 3.3 internals (`_queue`,
    `_pgconn`, `_worker_error`, `connection`, `copy_to`), pinned by uv.lock."""

    def __init__(self, cursor: psycopg.Cursor) -> None:
        super().__init__(cursor)
        self._queue = queue.Queue(maxsize=COPY_QUEUE_ITEMS)

    def worker(self) -> None:
        try:
            while data := self._queue.get():
                self.connection.wait(copy_to(self._pgconn, data, flush=True))
        except BaseException as ex:
            # Propagate the error to the main thread.
            self._worker_error = ex


class _CsvCopyOut:
    """One destination COPY open for the whole dataset, with a background bounded writer."""

    def __init__(self, pg: psycopg.Connection, staging: str, columns: list[str]):
        self._pg = pg
        self._staging = staging
        self._columns = columns
        self._stack = ExitStack()
        self._copy: psycopg.copy.Copy | None = None

    def _ensure(self) -> None:
        if self._copy is None:
            stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, NULL '\\N')").format(
                sql.Identifier(self._staging),
                sql.SQL(", ").join(map(sql.Identifier, self._columns)),
            )
            cur = self._stack.enter_context(self._pg.cursor())
            self._copy = self._stack.enter_context(cur.copy(stmt, writer=_BoundedWriter(cur)))

    def write(self, frame: pl.DataFrame) -> None:
        if frame.height == 0:
            return
        self._ensure()
        buf = io.BytesIO()
        frame.select(self._columns).write_csv(buf, include_header=False, null_value=r"\N")
        self._copy.write(buf.getbuffer())

    def __enter__(self) -> "_CsvCopyOut":
        self._stack.__enter__()
        return self

    def __exit__(self, *exc_info) -> bool:
        return self._stack.__exit__(*exc_info)


def _extract_transformed(pg: psycopg.Connection, plan: Plan, staging: str,
                         compiled: transform.Compiled, *, files: dict,
                         source: DataSource, secrets: dict, app: Settings,
                         params: dict, time_left: int, deadline: float,
                         tz: str, check: Callable[[], None],
                         cancel: extract.Cancel | None = None,
                         spill_label: str | None = None) -> None:
    ds = plan.ds
    columns = list(ds["columns"])
    plan.path = "rows+polars"
    plan.transform_mode = compiled.mode

    def make_sink(dest: _CsvCopyOut) -> transform.Sink:
        return transform.Sink(
            compiled,
            dest.write,
            check,
            deadline=deadline,
            label=f"{spill_label or 'run'}-{plan.name}",
        )

    try:
        with _CsvCopyOut(pg, staging, columns) as dest:
            sink = make_sink(dest)
            try:
                ext = ds["extract"]
                if "query" in ext:
                    if source.kind != "postgresql":
                        raise ExtractError(M("run.sql_needs_postgres"))
                    query = files[ext["query"]]
                    plan.path = "copy+polars"
                    splitter = transform.CopyTextSplitter(
                        sink.add, compiled.input_columns, compiled.batch_rows
                    )
                    fallback = False
                    try:
                        extract.pg_copy(
                            source.settings, secrets, app, query, params,
                            columns=compiled.input_columns, timezone=tz,
                            time_limit_s=time_left,
                            deadline=deadline, write=splitter.write, check=check,
                            cancel=cancel,
                        )
                    except extract.BulkUnsupported as e:
                        plan.path, plan.fallback = "rows+polars", e.reason
                        log.info(
                            "%s: extracción por filas con transformación (%s)",
                            plan.name, e.reason,
                        )
                        fallback = True
                    if fallback:
                        sink.close()
                        sink = make_sink(dest)
                        time_left = max(1, int(deadline - time.monotonic()))
                        for got, rows in extract.pg_rows(
                            source.settings, secrets, app, query, params,
                            timezone=tz, time_limit_s=time_left, cancel=cancel,
                        ):
                            mismatch = extract.columns_mismatch(got, compiled.input_columns)
                            if mismatch:
                                raise mismatch
                            frame = _text_frame(rows, got)
                            sink.add(frame, escaped=False)
                            if time.monotonic() > deadline:
                                raise ExtractError(M("run.timeout"))
                            check()
                    else:
                        splitter.close()
                else:
                    request = yaml.safe_load(files[ext["request"]])
                    fn = {"rest": extract.rest_rows, "soap": extract.soap_rows,
                          "supabase": extract.supabase_rows}.get(source.kind)
                    if fn is None:
                        raise ExtractError(
                            M("run.request_needs_http")
                        )
                    for rows in fn(source.settings, secrets, app, request, params,
                                   compiled.input_columns, time_limit_s=time_left,
                                   cancel=cancel):
                        frame = _text_frame(rows, compiled.input_columns)
                        sink.add(frame, escaped=False)
                        if time.monotonic() > deadline:
                            raise ExtractError(M("run.timeout"))
                        check()
                sink.finish()
            finally:
                plan.rows_in = sink.rows_in
                plan.extracted = sink.rows_out
                plan.transform_ms = sink.transform_ms
                sink.close()
    except psycopg.errors.DataError as e:
        raise ExtractError(M("run.contract", detail=_first_line(e))) from None


def _count(pg: psycopg.Connection, staging: str, condition: sql.Composable) -> int:
    return pg.execute(sql.SQL("SELECT count(*) FROM {} WHERE {}").format(
        sql.Identifier(staging), condition)).fetchone()[0]


def _check(plan: Plan, kind: str, ok: bool, detail: "M | str") -> None:
    text, key, params = to_stored(detail)
    plan.checks.append({"dataset": plan.name, "type": kind, "ok": ok,
                        "detail": text, "key": key, "params": params})


def _run_checks(pg: psycopg.Connection, plan: Plan, staging: str, *, files: dict,
                source: DataSource, secrets: dict, app: Settings, tz: str,
                deadline: float, stop_check: Callable[[], None],
                cancel: extract.Cancel | None = None) -> None:
    ds = plan.ds
    for col, c in ds["columns"].items():
        ident = sql.Identifier(col)
        if not c.get("nullable", True):
            n = _count(pg, staging, sql.SQL("{} IS NULL").format(ident))
            if n:
                _check(plan, "contract", False, M("run.check.nulls", column=col, n=n))
        if c.get("enum"):
            n = _count(pg, staging, sql.SQL("{} IS NOT NULL AND NOT ({}::text = ANY({}::text[]))")
                       .format(ident, ident, sql.Literal(c["enum"])))
            if n:
                _check(plan, "contract", False, M("run.check.enum", column=col, n=n,
                                         allowed=", ".join(map(str, c['enum']))))
        for bound, op in (("min", "<"), ("max", ">")):
            if bound in c:
                n = _count(pg, staging, sql.SQL("{} " + op + " {}").format(
                    ident, sql.Literal(c[bound])))
                if n:
                    _check(plan, "contract", False, M("run.check.bound", column=col, n=n,
                                             op=op, bound=c[bound]))
    if ds.get("primary_key"):
        keys = sql.SQL(", ").join(map(sql.Identifier, ds["primary_key"]))
        dup = pg.execute(sql.SQL("SELECT count(*) FROM (SELECT 1 FROM {} GROUP BY {} "
                                 "HAVING count(*) > 1) d").format(sql.Identifier(staging), keys)
                         ).fetchone()[0]
        if dup:
            _check(plan, "contract", False, M("run.check.duplicate_keys", n=dup))
    for check in ds.get("checks", []):
        if check["type"] == "row_count":
            ok = plan.extracted >= check.get("min", 0) and (
                "max" not in check or plan.extracted <= check["max"])
            _check(plan, "row_count", ok, M("run.check.rows", n=plan.extracted))
        elif check["type"] == "not_null":
            bad = {c: _count(pg, staging, sql.SQL("{} IS NULL").format(sql.Identifier(c)))
                   for c in check["columns"]}
            bad = {c: n for c, n in bad.items() if n}
            _check(plan, "not_null", not bad,
                   M("run.check.not_null",
                     detail=", ".join(f"{c}: {n}" for c, n in bad.items()))
                   if bad else M("run.check.no_nulls"))
        elif check["type"] == "reconcile":
            stop_check()
            _reconcile(pg, plan, staging, check, files=files, source=source, secrets=secrets,
                       app=app, tz=tz, deadline=deadline, cancel=cancel)


def _reconcile(pg: psycopg.Connection, plan: Plan, staging: str, check: dict, *, files: dict,
               source: DataSource, secrets: dict, app: Settings, tz: str,
               deadline: float, cancel: extract.Cancel | None = None) -> None:
    """Origin totals (the check's query) vs the extracted rows, grouped by the first column."""
    if source.kind != "postgresql":
        _check(plan, "reconcile", False, M("run.check.reconcile_needs_postgres"))
        return
    key, values = check["compare"][0], check["compare"][1:]
    tolerance = float(check.get("tolerance", 0.01))
    params = {"window_start": plan.start, "window_end": plan.end}
    cols, rows = extract.pg_all(source.settings, secrets, app, files[check["query"]], params,
                                timezone=tz,
                                time_limit_s=max(1, int(deadline - time.monotonic())),
                                cancel=cancel)
    if any(c not in cols for c in check["compare"]):
        _check(plan, "reconcile", False, M("run.check.reconcile_columns",
                                                   columns=", ".join(check['compare'])))
        return
    idx = [cols.index(c) for c in check["compare"]]
    origin = {str(r[idx[0]]): [float(r[i] or 0) for i in idx[1:]] for r in rows}
    ours_rows = pg.execute(sql.SQL("SELECT {}::text, {} FROM {} GROUP BY 1").format(
        sql.Identifier(key),
        sql.SQL(", ").join(sql.SQL("coalesce(sum({}), 0)").format(sql.Identifier(v))
                           for v in values),
        sql.Identifier(staging))).fetchall()
    ours = {str(r[0]): [float(v) for v in r[1:]] for r in ours_rows}
    diffs = []
    for k in sorted(set(origin) | set(ours)):
        a, b = origin.get(k, [0.0] * len(values)), ours.get(k, [0.0] * len(values))
        for v, x, y in zip(values, a, b, strict=True):
            if abs(x - y) > tolerance:
                diffs.append(t("run.check.reconcile_diff", group=k, value=v,
                               origin=f"{x:.2f}", loaded=f"{y:.2f}"))
    _check(plan, "reconcile", not diffs,
           "; ".join(diffs[:3]) + (f" (+{len(diffs) - 3})" if len(diffs) > 3 else "")
           if diffs else M("run.check.reconciled", n=len(origin)))


def _delete_window(plan: Plan) -> tuple[sql.Composable, tuple] | None:
    """The DELETE condition and its parameters, or None when the load replaces the whole table."""
    ds, date_col = plan.ds, plan.ds.get("date_column")
    if plan.full or not date_col:
        return None
    col = sql.Identifier(date_col)
    if ds["columns"][date_col]["type"] == "date":
        tz = plan.start.tzinfo
        return (sql.SQL("{} BETWEEN %s AND %s").format(col),
                (plan.start.date(), plan.end.astimezone(tz).date()))
    return sql.SQL("{} BETWEEN %s AND %s").format(col), (plan.start, plan.end)


def _load(pg: psycopg.Connection, plan: Plan, schema: str, staging: str, run_id: int,
          cap: rollup.Capture | None = None) -> None:
    ds, name = plan.ds, plan.name
    columns = list(ds["columns"])
    target = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(name))
    window = _delete_window(plan)
    if cap is not None:
        rollup.capture(pg, cap, dataset=name, ds=ds, window=window, schema=schema,
                       staging=staging)
    if window is None:
        pg.execute(sql.SQL("DELETE FROM {}").format(target))
    else:
        pg.execute(sql.SQL("DELETE FROM {} WHERE {}").format(target, window[0]), window[1])
    cols = sql.SQL(", ").join(map(sql.Identifier, columns))
    stmt = sql.SQL("INSERT INTO {} ({}, _run_id) SELECT {}, %s FROM {}").format(
        target, cols, cols, sql.Identifier(staging))
    if ds.get("primary_key"):
        updates = [sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
                   for c in columns if c not in ds["primary_key"]]
        updates += [sql.SQL("_run_id = EXCLUDED._run_id"), sql.SQL("_loaded_at = now()")]
        stmt += sql.SQL(" ON CONFLICT ({}) DO UPDATE SET {}").format(
            sql.SQL(", ").join(map(sql.Identifier, ds["primary_key"])),
            sql.SQL(", ").join(updates))
    plan.written = pg.execute(stmt, (run_id,)).rowcount


def _safe_message(e: Exception, secrets: dict) -> str:
    text = str(e) if isinstance(e, ExtractError) else f"{type(e).__name__}: {_first_line(e)}"
    for value in secrets.values():
        if isinstance(value, str) and len(value) >= 4:
            text = redact(text, value, limit=10_000)
    return redact(text, None, limit=500)


def _failure(e: Exception, secrets: dict) -> "M | str":
    if isinstance(e, ExtractError) and e.args and isinstance(e.args[0], M):
        return e.args[0]
    return _safe_message(e, secrets)


def _redactor(secrets: dict) -> Callable[[str], str]:
    def redact_text(text: str) -> str:
        for value in secrets.values():
            if isinstance(value, str) and len(value) >= 4:
                text = redact(text, value, limit=10_000)
        return redact(text, None, limit=500)
    return redact_text


class RunStopped(Exception):
    """Raised by the cooperative stop check when an operator requests the run to end."""

    def __init__(self, by: str | None) -> None:
        super().__init__(by)
        self.by = by


class StopFlag:
    """Reads `integration_run.stop_requested_at` at most once every `interval` seconds."""

    def __init__(self, run_id: int, *, interval: float = 2.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.run_id = run_id
        self.interval = interval
        self.clock = clock
        self._last: float | None = None
        self.requested = False
        self.by: str | None = None

    def poll(self) -> bool:
        requested, by = self._read()
        if requested:
            self.by = by
            self.requested = True
        return requested

    def __call__(self) -> None:
        if self.requested:
            raise RunStopped(self.by)
        now = self.clock()
        if self._last is not None and now - self._last < self.interval:
            return
        self._last = now
        if self.poll():
            raise RunStopped(self.by)

    def _read(self) -> tuple[bool, str | None]:
        with get_engine().connect() as conn:
            row = conn.execute(
                select(IntegrationRun.stop_requested_at, AppUser.full_name)
                .outerjoin(AppUser, AppUser.id == IntegrationRun.stop_requested_by)
                .where(IntegrationRun.id == self.run_id)
            ).first()
        return bool(row is not None and row[0] is not None), None if row is None else row[1]


@contextmanager
def _watchdog(stop, cancel: extract.Cancel, interval: float = 2.0):
    """Polls the stop flag from a background thread so a stop also interrupts blocking work
    (origin queries, destination statements, HTTP pages); once requested it cancels every
    interval until the block ends."""
    poll = getattr(stop, "poll", None)
    if poll is None:
        yield
        return
    done = threading.Event()

    def target() -> None:
        requested = False
        while not done.wait(interval):
            if not requested:
                try:
                    requested = poll()
                except Exception as e:
                    log.warning("stop watchdog: %s", type(e).__name__)
                    continue
            if requested:
                cancel.cancel()

    thread = threading.Thread(target=target, name="stop-watchdog", daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join(15)


def _stopped_message(by: str | None) -> M:
    return M("run.stopped_by", name=by) if by else M("run.stopped")


def set_message(run: IntegrationRun, message: "M | str | None") -> None:
    run.message, run.message_key, run.message_params = to_stored(message)


def _rows_entry(p: Plan) -> dict:
    entry = {
        "extracted": p.extracted,
        "written": p.written,
        "full": p.full,
        "path": p.path,
    }
    if p.fallback:
        entry["fallback"] = p.fallback
    if p.transform_mode is not None:
        entry["transform_mode"] = p.transform_mode
        entry["rows_in"] = p.rows_in
        entry["transform_ms"] = p.transform_ms
    return entry


def _finish(db: Session, run: IntegrationRun, status: str,
            message: "M | str | None", plans: list[Plan],
            redact: Callable[[str], str] | None = None) -> None:
    run.status, run.finished_at = status, datetime.now(UTC)
    run.message, run.message_key, run.message_params = to_stored(message, redact)
    run.rows = {p.name: _rows_entry(p) for p in plans}
    run.checks = [c for p in plans for c in p.checks]
    db.commit()


def run_integration(integration: dict, files: dict[str, str], *, version_id: int | None,
                    kind: str = "incremental", requested_by: int | None = None,
                    now: datetime | None = None) -> IntegrationRun:
    """Run one integration of the applied workspace version. Returns the finished run row."""
    app = get_settings()
    iid = integration["id"]
    tz_name = integration.get("timezone") or app.timezone
    try:
        tz = ZoneInfo(extract.check_timezone(tz_name))
    except ExtractError as e:
        with get_sessionmaker()() as db:
            run = IntegrationRun(integration_id=iid, version_id=version_id, kind=kind,
                                 status="failed", message=str(e), requested_by=requested_by,
                                 finished_at=datetime.now(UTC))
            db.add(run)
            db.commit()
            return run
    now = now or datetime.now(UTC)
    deadline = time.monotonic() + 60 * int(integration.get("time_limit_minutes") or 20)
    engine = get_engine()
    with engine.connect() as lock_conn, get_sessionmaker()() as db:
        pg_lock = lock_conn.connection.driver_connection
        got = pg_lock.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
                              (_lock_key(iid),)).fetchone()[0]
        pg_lock.commit()
        run = IntegrationRun(integration_id=iid, version_id=version_id, kind=kind,
                             status="running", requested_by=requested_by)
        if not got:
            run.status = "skipped"
            set_message(run, M("run.already_running"))
            run.finished_at = datetime.now(UTC)
            db.add(run)
            db.commit()
            return run
        try:
            # We hold the lock: any other `running` row of this integration is left over.
            db.execute(update(IntegrationRun)
                       .where(IntegrationRun.integration_id == iid,
                              IntegrationRun.status == "running")
                       .values(status="failed", finished_at=datetime.now(UTC),
                               message=to_stored(M("run.interrupted"))[0],
                               message_key="run.interrupted",
                               message_params=None))
            db.add(run)
            db.commit()
            return _run(db, run, integration, files, app=app, tz=tz, tz_name=tz_name,
                        now=now, deadline=deadline, kind=kind)
        finally:
            pg_lock.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                            (_lock_key(iid),))
            pg_lock.commit()


def _run(db: Session, run: IntegrationRun, integration: dict, files: dict, *, app: Settings,
         tz: ZoneInfo, tz_name: str, now: datetime, deadline: float,
         kind: str) -> IntegrationRun:
    iid = integration["id"]
    source = db.scalar(select(DataSource).where(
        DataSource.name.ilike(integration["source"].strip())))
    if source is None:
        _finish(db, run, "failed",
                M("run.source_missing", source=integration['source']), [])
        return run
    if not source.enabled:
        _finish(db, run, "skipped", M("run.source_disabled"), [])
        return run
    secrets: dict = {}
    plans: list[Plan] = []
    schema = datasets.schema_name(iid)
    stop = StopFlag(run.id)
    cancel = extract.Cancel()
    cap = None
    rollup_results: dict = {}
    try:
        secrets = sources.secrets_of(source)
        try:
            cap = rollup.new_capture(iid, rollup.active_definitions(db, run.version_id, iid))
        except Exception as e:      # a broken definition must never break the run itself
            log.warning("rollup definitions of %s unavailable: %s", iid, type(e).__name__)
        with get_engine().connect() as conn:
            pg = conn.connection.driver_connection
            try:
                with _watchdog(stop, cancel), cancel.track(pg):
                    pg.execute(sql.SQL("SET LOCAL TimeZone = {}").format(sql.Literal(tz_name)))
                    for name, ds in integration["datasets"].items():
                        stop()
                        state = datasets.ensure_table(pg, iid, name, ds)
                        full = (kind in FULL_KINDS or state.needs_full or bool(state.added)
                                or "window_days" not in (ds.get("incremental") or {}))
                        start, end = window(ds, full=full, now=now, tz=tz)
                        plan = Plan(name, ds, full, start, end, state)
                        plans.append(plan)
                        staging = _stage(pg, schema, name, list(ds["columns"]))
                        _extract(pg, plan, staging, integration=integration, files=files,
                                 source=source, secrets=secrets, app=app, deadline=deadline,
                                 tz=tz_name, check=stop, cancel=cancel,
                                 spill_label=str(run.id))
                        stop()
                        _run_checks(pg, plan, staging, files=files, source=source,
                                    secrets=secrets, app=app, tz=tz_name, deadline=deadline,
                                    stop_check=stop, cancel=cancel)
                    failed = [c for p in plans for c in p.checks if not c["ok"]]
                    if failed:
                        pg.rollback()
                        first = failed[0]
                        detail = ({"$m": first["key"], "params": first["params"]}
                                  if first["key"] else first["detail"])
                        _finish(db, run, "failed",
                                M("run.check_failed", dataset=first["dataset"],
                                  type=first["type"], detail=detail), plans)
                        return run
                    stop()
                    for plan in plans:
                        _load(pg, plan, schema, f"_stg_{plan.name}", run.id, cap)
                    if cap is not None:
                        stop()
                        rollup_results = rollup.after_load(
                            pg, run.id, iid, cap, schema=schema, restore_timezone=tz_name,
                            deadline=deadline, stop=stop,
                            safe_message=lambda e: _safe_message(e, secrets))
                    stop()
                pg.commit()
            except BaseException:
                pg.rollback()
                raise
    except RunStopped as e:
        log.info("integration %s run %s stopped", iid, run.id)
        db.rollback()
        _finish(db, run, "stopped", _stopped_message(e.by), plans)
        return run
    except Exception as e:
        if getattr(stop, "requested", False):
            log.info("integration %s run %s stopped (%s)", iid, run.id, type(e).__name__)
            db.rollback()
            _finish(db, run, "stopped", _stopped_message(getattr(stop, "by", None)), plans)
            return run
        log.warning("integration %s run %s failed: %s", iid, run.id, type(e).__name__)
        db.rollback()
        _finish(db, run, "failed", _failure(e, secrets), plans,
            redact=_redactor(secrets))
        return run
    message = None
    if rollup_results:
        run.rollups = rollup_results
        failed_rollups = rollup.failed_reports(rollup_results)
        if failed_rollups:
            message = M("run.rollup_failed",
                        reports=", ".join(failed_rollups))
    try:
        version = db.get(WorkspaceVersion, run.version_id) if run.version_id else None
        counts = images_cache.refresh_reports(db, version, iid)
        if counts["fetched"] or counts["failed"]:
            log.info("run %s: images fetched=%s failed=%s", run.id, counts["fetched"],
                     counts["failed"])
    except Exception:      # an image never fails a load
        log.warning("run %s: the image cache pass failed", run.id, exc_info=True)
    _finish(db, run, "succeeded", message, plans)
    return run


def run_preview(integration: dict, files: dict, *, session_id: int,
                now: datetime | None = None, max_window_days: int = 7,
                time_limit_s: int = 300) -> dict:
    """Run a draft integration into the session's preview schemas (feature 014): never the
    published `ds_*` schemas, no integration_run row, all-or-nothing like a real run."""
    app = get_settings()
    iid = integration["id"]
    secrets: dict = {}
    plans: list[Plan] = []
    preview_key = lock_key("preview", session_id)
    engine = get_engine()
    try:
        tz_name = extract.check_timezone(integration.get("timezone") or app.timezone)
    except ExtractError as e:
        return {"status": "failed", "message": str(e), "datasets": {}, "checks": []}
    tz = ZoneInfo(tz_name)
    now = now or datetime.now(UTC)
    deadline = time.monotonic() + time_limit_s

    def check() -> None:
        if time.monotonic() > deadline:
            raise ExtractError(M("run.preview_timeout"))

    with engine.connect() as lock_conn, get_sessionmaker()() as db:
        pg_lock = lock_conn.connection.driver_connection
        got = pg_lock.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (preview_key,)
        ).fetchone()[0]
        pg_lock.commit()
        if not got:
            return {"status": "skipped", "message": t("run.preview_running"),
                    "datasets": {}, "checks": []}
        try:
            source = db.scalar(select(DataSource).where(
                DataSource.name.ilike(integration["source"].strip())
            ))
            if source is None:
                return {"status": "failed",
                        "message": t("run.source_missing",
                                      source=integration['source']),
                        "datasets": {}, "checks": []}
            secrets = sources.secrets_of(source)
            with datasets.preview_schemas(datasets.preview_prefix(session_id)):
                schema = datasets.schema_name(iid)
                with engine.connect() as conn:
                    pg = conn.connection.driver_connection
                    try:
                        pg.execute(
                            sql.SQL("SET LOCAL TimeZone = {}").format(sql.Literal(tz_name))
                        )
                        for name, original in integration["datasets"].items():
                            check()
                            ds = copy.deepcopy(original)
                            inc = ds.get("incremental") or {}
                            if "window_days" in inc:
                                inc["window_days"] = min(int(inc["window_days"]),
                                                         max_window_days)
                            state = datasets.ensure_table(pg, iid, name, ds)
                            full = "window_days" not in inc
                            start, end = window(ds, full=full, now=now, tz=tz)
                            plan = Plan(name, ds, full, start, end, state)
                            plans.append(plan)
                            staging = _stage(pg, schema, name, list(ds["columns"]))
                            _extract(pg, plan, staging, integration=integration, files=files,
                                     source=source, secrets=secrets, app=app,
                                     deadline=deadline, tz=tz_name, check=check,
                                     spill_label=f"preview{session_id}")
                            _run_checks(pg, plan, staging, files=files, source=source,
                                        secrets=secrets, app=app, tz=tz_name,
                                        deadline=deadline, stop_check=check)
                        failed = [c for p in plans for c in p.checks if not c["ok"]]
                        if failed:
                            pg.rollback()
                            return {"status": "failed",
                                    "message": t("run.preview_check_failed"),
                                    "datasets": {}, "checks": failed}
                        for plan in plans:
                            _load(pg, plan, schema, f"_stg_{plan.name}", 0)
                        pg.commit()
                    except BaseException:
                        pg.rollback()
                        raise
            return {"status": "succeeded", "message": None,
                    "datasets": {p.name: {"rows": p.written} for p in plans}, "checks": []}
        except Exception as e:
            return {"status": "failed", "message": _safe_message(e, secrets),
                    "datasets": {}, "checks": []}
        finally:
            pg_lock.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (preview_key,))
            pg_lock.commit()
