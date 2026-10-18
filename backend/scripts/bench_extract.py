"""Benchmark extraction paths: COPY pipe, row fallback, and copy+polars transform
(feature 008 + feature 005 amendment 2026-10-08).

    cd backend && BENCH_ROWS=1000000 uv run python scripts/bench_extract.py

Opt-in developer tool; not part of CI. Configure with BENCH_ROWS, BENCH_MODES (comma list,
default copy,rows,copy+polars, and may include whole for a whole-mode transform with ORDER BY id)
and BENCH_BATCH_ROWS (the transform's `batch_rows`; unset uses the engine default). Origin and
destination are BENCH_DATABASE_URL when set, else DATABASE_URL_BI; neither URL is ever printed.
Run both sides on the same host or LAN (SC-001): a remote link hides the COPY pipe's savings.
Writes only to a throwaway schema `app_test_bench_<hex>` (dropped at the end) and to temporary
tables. Each path runs in its own process, so time and peak memory are separate.
"""

import multiprocessing as mp
import os
import queue
import resource
import secrets
import sys
import time
from pathlib import Path

import psycopg
from sqlalchemy.engine import URL, make_url

# Ensure backend/ is on sys.path when running as `python scripts/bench_extract.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.engine import extract, runner, transform

COLUMNS = ["id", "txt", "amount", "ts", "d", "flag", "js"]
IN_COLUMNS = {
    "id": {"type": "bigint"},
    "txt": {"type": "text"},
    "amount": {"type": "numeric"},
    "ts": {"type": "timestamptz"},
    "d": {"type": "date"},
    "flag": {"type": "boolean"},
    "js": {"type": "text"},
}
OUT_COLUMNS = {
    "id": {"type": "bigint"},
    "txt": {"type": "text"},
    "amount": {"type": "numeric"},
    "ts": {"type": "timestamptz"},
    "d": {"type": "date"},
    "flag": {"type": "boolean"},
    "js": {"type": "text"},
}
BENCH_SQL = "SELECT id, upper(txt) AS txt, amount * 2 AS amount, ts, d, flag, js FROM input"
WHOLE_SQL = BENCH_SQL + " ORDER BY id"


def bench_url() -> URL:
    """The database of both sides: `BENCH_DATABASE_URL` when set (same host or LAN as the
    client, per SC-001), else the installation's `DATABASE_URL_BI`. Never printed."""
    return make_url(os.environ.get("BENCH_DATABASE_URL") or get_settings().database_url_bi)


def target() -> str:
    """Host, port and database only: what the numbers belong to, with no credentials."""
    u = bench_url()
    return f"{u.host}:{u.port or 5432}/{u.database}"


def origin_conn() -> tuple[dict, dict]:
    u = bench_url()
    settings = {"host": u.host, "port": u.port or 5432, "database": u.database,
                "username": u.username, "sslmode": "prefer", "timeout_seconds": 15}
    return settings, {"password": u.password}


def dsn() -> str:
    return bench_url().set(drivername="postgresql").render_as_string(hide_password=False)


def setup(schema: str, rows: int) -> None:
    with psycopg.connect(dsn()) as pg:
        pg.execute(f"CREATE SCHEMA {schema}")
        pg.execute(f"CREATE TABLE {schema}.src (id bigint, txt text, amount numeric(18,2), "
                   f"ts timestamptz, d date, flag boolean, js jsonb)")
        pg.execute(f"INSERT INTO {schema}.src SELECT g, md5(g::text), (g % 100000) / 100.0, "
                   f"now() + g * interval '1 second', (now() + g * interval '1 hour')::date, "
                   f"g % 2 = 0, jsonb_build_object('n', g, 't', md5(g::text)) "
                   f"FROM generate_series(1, {rows}) g")


def child(mode: str, schema: str, out: mp.Queue, batch_rows: int | None = None) -> None:
    settings, secrets_ = origin_conn()
    app = get_settings()
    query = f"SELECT {', '.join(COLUMNS)} FROM {schema}.src"
    cols = ", ".join(COLUMNS)
    transform_ms = 0
    with psycopg.connect(dsn()) as pg:
        pg.execute(f"CREATE TEMP TABLE dest (LIKE {schema}.src)")
        start = time.monotonic()
        if mode == "copy":
            with pg.cursor() as cur, cur.copy(f"COPY dest ({cols}) FROM STDIN (FORMAT text)") as d:
                extract.pg_copy(settings, secrets_, app, query, {}, columns=COLUMNS,
                                timezone="UTC", time_limit_s=3600,
                                deadline=time.monotonic() + 3600, write=d.write)
        elif mode in ("copy+polars", "whole"):
            transform_cfg = {
                "input": IN_COLUMNS,
                "sql": WHOLE_SQL if mode == "whole" else BENCH_SQL,
            }
            if batch_rows:
                transform_cfg["batch_rows"] = batch_rows
            ds = {"columns": OUT_COLUMNS, "transform": transform_cfg}
            compiled = transform.compile(ds, "UTC")
            with runner._CsvCopyOut(pg, "dest", COLUMNS) as dest:
                sink = transform.Sink(compiled, dest.write, lambda: None)
                splitter = transform.CopyTextSplitter(
                    sink.add, compiled.input_columns, compiled.batch_rows
                )
                extract.pg_copy(settings, secrets_, app, query, {}, columns=COLUMNS,
                                timezone="UTC", time_limit_s=3600,
                                deadline=time.monotonic() + 3600, write=splitter.write)
                splitter.close()
                sink.finish()
            transform_ms = sink.transform_ms
        else:
            for got, rows in extract.pg_rows(settings, secrets_, app, query, {},
                                             timezone="UTC", time_limit_s=3600):
                runner._copy(pg, "dest", COLUMNS, runner._text_frame(rows, got))
        seconds = time.monotonic() - start
        count = pg.execute("SELECT count(*) FROM dest").fetchone()[0]
    out.put((count, seconds, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, transform_ms))


def measure(mode: str, schema: str, batch_rows: int | None = None) -> tuple[int, float, int]:
    ctx = mp.get_context("spawn")
    out = ctx.Queue()
    p = ctx.Process(target=child, args=(mode, schema, out, batch_rows))
    p.start()
    result = None
    while result is None:
        try:
            result = out.get(timeout=1)
        except queue.Empty:
            if not p.is_alive():
                try:
                    result = out.get(timeout=5)      # the child may have just exited
                except queue.Empty:
                    # A child that fails before `out.put` (blocked address, no privileges, bad
                    # origin) would otherwise hang the benchmark here; its traceback is already
                    # on stderr.
                    p.join()
                    raise RuntimeError(f"path {mode!r} produced no result "
                                       f"(exit code {p.exitcode})") from None
    p.join()
    return result
    p.join()
    return result


def main() -> None:
    rows = int(os.environ.get("BENCH_ROWS", "100000"))
    modes = os.environ.get("BENCH_MODES", "copy,rows,copy+polars").split(",")
    batch_rows = int(os.environ["BENCH_BATCH_ROWS"]) if os.environ.get("BENCH_BATCH_ROWS") else None
    schema = f"app_test_bench_{secrets.token_hex(4)}"
    print(f"database: {target()} (origin and destination)")
    setup(schema, rows)
    try:
        results: dict[str, tuple[int, float, int, int]] = {}
        for mode in modes:
            results[mode] = measure(mode, schema, batch_rows)
        for mode, (n, _, _, _) in results.items():
            assert n == rows, (mode, n, rows)
        print(f"{'path':<12} {'rows':>10} {'seconds':>9} {'rows/s':>10} {'peak MB':>9} "
              f"{'transform ms':>12}")
        for mode, (n, s, kb, tms) in results.items():
            print(f"{mode:<12} {n:>10} {s:>9.2f} {n / s:>10,.0f} {kb / 1024:>9.1f} {tms:>12}")
        if "rows" in results and "copy" in results:
            print(f"speed-up rows/copy: {results['rows'][1] / results['copy'][1]:.1f}x")
        if "copy+polars" in results and "copy" in results:
            copy_s = results["copy"][1]
            polars_s = results["copy+polars"][1]
            overhead = (polars_s - copy_s) / copy_s * 100
            peak_mb = results["copy+polars"][2] / 1024
            print(
                f"SC-A01 overhead copy+polars vs copy: {overhead:+.1f}% "
                f"(target <= 30%), peak {peak_mb:.1f} MB (target < 300 MB)"
            )
        if "whole" in results and "copy" in results:
            copy_s = results["copy"][1]
            whole_s = results["whole"][1]
            overhead = (whole_s - copy_s) / copy_s * 100
            peak_mb = results["whole"][2] / 1024
            ms = results["whole"][3]
            print(
                f"whole mode vs copy: {overhead:+.1f}%, peak {peak_mb:.1f} MB, "
                f"transform {ms} ms"
            )
    finally:
        with psycopg.connect(dsn()) as pg:
            pg.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


if __name__ == "__main__":
    main()
