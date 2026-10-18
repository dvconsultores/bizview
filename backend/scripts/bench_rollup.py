"""Benchmark the daily rollup of a materialized report (feature 005 amendment, T041b, SC-A02).

    cd backend && BENCH_ROWS=5000000 uv run python scripts/bench_rollup.py

Opt-in developer tool; not part of CI. It runs in the BI database under its own throwaway schema
`app_test_bench_<hex>__ds_bench` (dropped at the end): a synthetic dataset of BENCH_ROWS rows over
3 years x BENCH_DIMS dimension combinations, created with `datasets.ensure_table` so the tables
follow the real dict column contract. It then measures, in seconds:

  * full build     `rollup.build_full` over the whole dataset,
  * 7-day refresh  `rollup.refresh_days` for the days an incremental run would touch,
  * cold views     BENCH_RUNS runs per view type (kpis, trend, ranking, table) on the rollup
                   route and on the raw path, reported as p95.

SC-A02: 50 million rows on the reference machine, cold views p95 < 1 s and the refresh after an
hourly incremental run < 30 s. Record the numbers and the machine in
`specs/005-vibe-reporting/research.md` (R11).
"""

import math
import os
import platform
import secrets
import shutil
import sys
import time
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The throwaway schema is the run's DB_SCHEMA, so every dataset of this process (`<schema>__ds_*`)
# lands inside it and nothing touches the installation's datasets. Set before importing settings.
BENCH_SCHEMA = os.environ.get("BENCH_SCHEMA") or f"app_test_bench_{secrets.token_hex(4)}"
os.environ["DB_SCHEMA"] = BENCH_SCHEMA

from app.config import get_settings
from app.db import get_engine
from app.engine import datasets, rollup
from app.engine import report as engine

INTEGRATION = "bench"
LINES = "sale_lines"
PRODUCTS = "products"
REPORT_ID = "bench-ventas-dia"
DAYS = 3 * 365

LINES_DS = {
    "primary_key": ["document_id", "line_no"],
    "date_column": "local_date",
    "columns": {
        "document_id": {"type": "text", "nullable": False},
        "line_no": {"type": "integer", "nullable": False},
        "local_date": {"type": "date", "nullable": False},
        "product_code": {"type": "text", "nullable": False},
        "quantity": {"type": "integer", "nullable": False},
        "net_amount": {"type": "numeric", "nullable": False},
    },
}
PRODUCTS_DS = {
    "primary_key": ["product_code"],
    "columns": {
        "product_code": {"type": "text", "nullable": False},
        "category": {"type": "text", "nullable": False},
        "brand": {"type": "text", "nullable": False},
    },
}

REPORT = {
    "id": REPORT_ID,
    "spec": f"specs/reports/900-{REPORT_ID}",
    "title": "Bench ventas dia",
    "description": "Reporte sintetico del benchmark de resumenes diarios",
    "icon": "chart-line",
    "materialize": "daily",
    "uses": {LINES: f"{INTEGRATION}.{LINES}", PRODUCTS: f"{INTEGRATION}.{PRODUCTS}"},
    "joins": [{"left": f"{LINES}.product_code", "right": f"{PRODUCTS}.product_code",
               "type": "left"}],
    "date": f"{LINES}.local_date",
    "metrics": {
        "net_sales": {"label": "Ventas netas", "format": "currency",
                      "sql": f"sum({LINES}.net_amount)"},
        "lines_count": {"label": "Lineas", "format": "integer", "sql": "count(*)"},
        "avg_amount": {"label": "Importe medio", "format": "currency",
                       "sql": f"avg({LINES}.net_amount)"},
        "max_amount": {"label": "Importe maximo", "format": "currency",
                       "sql": f"max({LINES}.net_amount)"},
    },
    "dimensions": {
        "product": {"label": "Producto", "sql": f"{PRODUCTS}.product_code"},
        "category": {"label": "Categoria", "sql": f"{PRODUCTS}.category"},
        "brand": {"label": "Marca", "sql": f"{PRODUCTS}.brand"},
    },
    "periods": {"default": "mtd", "allowed": ["mtd", "last_7_days", "last_12_months", "custom"]},
    "compare": {"default": "previous_period", "allowed": ["none", "previous_period"]},
    "views": [
        {"type": "kpis", "metrics": ["net_sales", "lines_count", "avg_amount"]},
        {"type": "trend", "metric": "net_sales", "grain": "auto"},
        {"type": "ranking", "dimension": "product", "metric": "net_sales", "limit": 10},
        {"type": "table", "dimensions": ["product"],
         "metrics": ["net_sales", "lines_count", "avg_amount", "max_amount"]},
    ],
    "filters": ["category"],
    "pdf": {"enabled": False},
}

INTEGRATION_DEF = {
    "id": INTEGRATION,
    "spec": f"specs/integrations/900-{INTEGRATION}",
    "source": "Origen del benchmark",
    "schedule": "*/30 * * * *",
    "timezone": "UTC",
    "datasets": {LINES: LINES_DS, PRODUCTS: PRODUCTS_DS},
}


def pg_conn():
    """A raw psycopg connection: `datasets.ensure_table` and `rollup.build_full`/`refresh_days`
    take the DBAPI connection of a pooled SQLAlchemy one."""
    conn = get_engine().connect()
    return conn, conn.connection.driver_connection


def dsn() -> str:
    return get_engine().url.set(drivername="postgresql").render_as_string(hide_password=False)


def drop_schema() -> None:
    """The throwaway schema of this run (datasets and the rollup table). Own connection, closed
    with a commit, and only after the run's connection is closed: nothing holds its locks."""
    with psycopg.connect(dsn()) as pg:
        pg.execute(f'DROP SCHEMA IF EXISTS "{datasets.schema_name(INTEGRATION)}" CASCADE')


def setup(pg, rows: int, dims: int) -> None:
    """Create the dataset tables with their dict column contract and fill them with data that
    covers `DAYS` days and `dims` product combinations."""
    for table, ds in ((LINES, LINES_DS), (PRODUCTS, PRODUCTS_DS)):
        datasets.ensure_table(pg, INTEGRATION, table, ds)
    schema = datasets.schema_name(INTEGRATION)
    pg.execute(
        f'INSERT INTO "{schema}"."{PRODUCTS}" (product_code, category, brand, _run_id) '
        f"SELECT 'P' || lpad(g::text, 6, '0'), 'C' || (g % 20), 'B' || (g % 50), 1 "
        f"FROM generate_series(1, {dims}) g"
    )
    pg.execute(
        f'INSERT INTO "{schema}"."{LINES}" '
        f"(document_id, line_no, local_date, product_code, quantity, net_amount, _run_id) "
        f"SELECT 'D' || lpad(g::text, 10, '0'), 1 + (g % 4), "
        # Day and product are decorrelated: every day sees every product, so the rollup covers
        # the full 3 years x `dims` cross product once BENCH_ROWS >= DAYS * dims (547,500).
        f"CURRENT_DATE - (g % {DAYS}), "
        f"'P' || lpad((1 + ((g / {DAYS}) % {dims}))::text, 6, '0'), "
        f"1 + (g % 9), ((g % 100000) / 100.0)::numeric(18, 2), 1 "
        f"FROM generate_series(1, {rows}) g"
    )
    pg.commit()


def bench_version() -> SimpleNamespace:
    """Stands in for an applied workspace version: the report engine only reads `id`, `checksum`
    and `artifacts` (the benchmark never routes through `report_rollup`, so `id` stays None)."""
    return SimpleNamespace(
        id=None, checksum="bench",
        artifacts={"integrations": {INTEGRATION: {"definition": INTEGRATION_DEF}},
                   "reports": {REPORT_ID: {"definition": REPORT}}})


def definition() -> rollup.Definition:
    """The rollup definition of the benchmark report, built exactly like the engine builds it:
    `rollup.definition(report_id, report_def, version.artifacts["integrations"])`."""
    return rollup.definition(REPORT_ID, REPORT, bench_version().artifacts["integrations"])


def contexts(d: rollup.Definition, types: dict) -> tuple[engine.Context, engine.Context]:
    """The raw context of the report and the same context routed to the built rollup (`Route` is
    what `engine.routed` builds from a ready `report_rollup` row)."""
    raw = engine.context(bench_version(), REPORT_ID)
    route = engine.Route(d.schema, d.table,
                         {mid: rollup.metric_sql(d, mid, types) for mid in d.metrics},
                         frozenset(d.dimensions))
    return raw, replace(raw, rollup=route)


def p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[max(math.ceil(0.95 * len(ordered)) - 1, 0)]


def run_views(path, sel, filters, tz: str, runs: int) -> dict[str, float]:
    """BENCH_RUNS runs of each view type over one path, returning p95 seconds per view type.
    Each view is warmed up once (the first query of a path can pay a pooled connection)."""
    results: dict[str, float] = {}
    for view in REPORT["views"]:
        fn = engine.VIEWS[view["type"]]
        fn(path, view, sel, filters, tz)
        samples = []
        for _ in range(runs):
            start = time.monotonic()
            fn(path, view, sel, filters, tz)
            samples.append(time.monotonic() - start)
        results[view["type"]] = p95(samples)
    return results


def machine(pg) -> dict:
    cpu = ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        cpu = platform.processor()
    ram = 0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                ram = int(line.split()[1]) // 1024
                break
    except OSError:
        pass
    usage = shutil.disk_usage(".")
    return {"cpu": cpu, "cores": os.cpu_count(), "ram_mb": ram,
            "disk_free_gb": round(usage.free / 1024**3, 1),
            "postgresql": pg.execute("SHOW server_version").fetchone()[0],
            "python": platform.python_version(), "os": platform.platform()}


def main() -> None:
    rows = int(os.environ.get("BENCH_ROWS", "5000000"))
    dims = int(os.environ.get("BENCH_DIMS", "500"))
    runs = int(os.environ.get("BENCH_RUNS", "20"))
    today = date.today()
    tz = get_settings().timezone

    conn, pg = pg_conn()
    try:
        info = machine(pg)
        print(f"benchmark rollup: {rows} rows, {dims} dimension combinations, "
              f"{runs} runs per view, {BENCH_SCHEMA}")
        setup(pg, rows, dims)
        d = definition()
        start = time.monotonic()
        built, types = rollup.build_full(pg, d)
        pg.commit()
        full_s = time.monotonic() - start
        print(f"full build: {full_s:.2f} s ({built} rollup rows)")

        days = [today - timedelta(days=n) for n in range(7)]
        start = time.monotonic()
        refreshed, inserted = rollup.refresh_days(pg, d, days)
        pg.commit()
        refresh_s = time.monotonic() - start
        print(f"7-day refresh: {refresh_s:.2f} s "
              f"({refreshed} rows deleted, {inserted} inserted)")

        raw, routed = contexts(d, types)
        sel, filters = engine.selection(
            raw, {"period": "custom", "from": str(today - timedelta(days=30)), "to": str(today)},
            today)
        on_rollup = run_views(routed, sel, filters, tz, runs)
        on_raw = run_views(raw, sel, filters, tz, runs)
        print(f"{'view':<10} {'rollup p95':>12} {'raw p95':>10}")
        for name in on_rollup:
            print(f"{name:<10} {on_rollup[name]:>11.3f}s {on_raw[name]:>9.3f}s")
        slowest = max(on_rollup.values())
        print(f"SC-A02 cold views p95 < 1 s: {slowest:.3f} s "
              f"({'ok' if slowest < 1 else 'over budget'})")
        print(f"SC-A02 refresh < 30 s: {refresh_s:.2f} s "
              f"({'ok' if refresh_s < 30 else 'over budget'})")
        print("machine: " + ", ".join(f"{k}={v}" for k, v in info.items()))
    finally:
        conn.close()
        drop_schema()


if __name__ == "__main__":
    main()
