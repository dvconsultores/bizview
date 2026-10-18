"""Daily rollups (feature 005 amendment, T037b/T038): build/refresh equivalence, state,
savepoint failure semantics, ensure_version and the worker hook."""
import math
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import datasets, rollup, runner
from app.engine import report as engine
from app.models import WorkspaceVersion
from app.worker import Worker
from tests.conftest import signed_in, sql
from tests.test_runner import NOW, ORIGIN, ds_sql, ds_table
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import apply, lock
from tests.workspace_fixture import build, spec, write

ROLLUP_TABLE = f'"{datasets.schema_name("ventas-prueba")}"."mv_ventas_dia"'

REPORT = """
id: ventas-dia
spec: specs/reports/002-ventas-dia
title: Ventas por dia
description: Resumen diario materializado
icon: chart-line
materialize: daily
uses:
  lines: ventas-prueba.sale_lines
  products: ventas-prueba.products
joins: [{left: lines.product_code, right: products.product_code, type: left}]
date: lines.local_date
metrics:
  net_sales:
    label: Ventas netas
    format: currency
    sql: >-
      sum(case when lines.line_kind = 'sale' then lines.net_amount
      else -lines.net_amount end)
  lines_count: {label: Lineas, format: integer, sql: count(*)}
  avg_amount: {label: Importe medio, format: currency, sql: avg(lines.net_amount)}
  max_amount: {label: Importe maximo, format: currency, sql: max(lines.net_amount)}
dimensions:
  product: {label: Producto, sql: products.product_code}
periods: {default: mtd, allowed: [mtd, last_7_days, custom]}
compare: {default: previous_period, allowed: [none, previous_period, previous_year]}
views:
  - {type: kpis, metrics: [net_sales, lines_count]}
  - {type: trend, metric: net_sales, grain: auto}
  - {type: ranking, dimension: product, metric: net_sales, limit: 5}
  - {type: table, dimensions: [product], metrics: [net_sales, lines_count, avg_amount, max_amount]}
filters: [product]
pdf: {enabled: true}
"""


@pytest.fixture
def materialized(tmp_path, monkeypatch, origin, superuser):
    root = build(tmp_path / "cliente-bizview", ORIGIN)
    spec(root, "report", "002-ventas-dia")
    write(root, "reports/ventas-dia/report.yaml", REPORT)
    monkeypatch.setattr(get_settings(), "workspace_path", str(root))
    lock(root)
    apply(signed_in("root@example.com"))
    vid, artifacts = sql(
        "SELECT id, artifacts FROM workspace_version WHERE state = 'active'"
    )[0]
    return vid, artifacts


def run_version(vid, artifacts, kind, now=NOW):
    integ = artifacts["integrations"]["ventas-prueba"]
    return runner.run_integration(
        integ["definition"], integ["files"], version_id=vid, kind=kind, now=now
    )


def definition(artifacts):
    return rollup.definition(
        "ventas-dia", artifacts["reports"]["ventas-dia"]["definition"],
        artifacts["integrations"],
    )


def _component_map(artifacts):
    """component sql (canonical, as in the rollup table) -> column name."""
    return {c.sql: c.name for c in definition(artifacts).components}


def raw_by_day_product():
    rows = ds_sql(
        f"""
        SELECT l.local_date, p.product_code,
               SUM(CASE WHEN l.line_kind = 'sale' THEN l.net_amount
                        ELSE -l.net_amount END),
               COUNT(*), SUM(l.net_amount), COUNT(l.net_amount), MAX(l.net_amount)
        FROM {ds_table("ventas-prueba", "sale_lines")} l
        LEFT JOIN {ds_table("ventas-prueba", "products")} p
          ON p.product_code = l.product_code
        GROUP BY 1, 2
        """
    )
    return {
        (r[0], r[1]): (Decimal(str(r[2])), r[3], Decimal(str(r[4])), r[5], Decimal(str(r[6])))
        for r in rows
    }


def rollup_values(artifacts):
    cmap = _component_map(artifacts)
    net = next(n for s, n in cmap.items() if "line_kind" in s)
    cnt_all = next(n for s, n in cmap.items() if s == "COUNT(*)")
    sum_amt = next(n for s, n in cmap.items() if s.endswith('SUM("lines"."net_amount")'))
    cnt_amt = next(n for s, n in cmap.items() if s.endswith('COUNT("lines"."net_amount")'))
    max_amt = next(n for s, n in cmap.items() if "MAX" in s)
    rows = ds_sql(
        f"SELECT day, k_product, {net}, {cnt_all}, {sum_amt}, {cnt_amt}, {max_amt} "
        f"FROM {ROLLUP_TABLE}"
    )
    return {
        (r[0], r[1]): (
            Decimal(str(r[2])), r[3], Decimal(str(r[4])), r[5] or 0, Decimal(str(r[6]))
        )
        for r in rows
    }


def test_full_run_builds_rollup_equal_to_raw(materialized):
    vid, artifacts = materialized
    run = run_version(vid, artifacts, "full")
    assert run.status == "succeeded", run.message
    assert run.rollups["ventas-dia"]["ok"] is True
    assert run.rollups["ventas-dia"]["mode"] == "full"

    state = sql(
        "SELECT status, source_runs FROM report_rollup WHERE report_id = 'ventas-dia'"
    )[0]
    assert state[0] == "ready"
    assert state[1]["ventas-prueba"] == run.id

    assert rollup_values(artifacts) == raw_by_day_product()


def test_incremental_window_refresh_only_touched_days(materialized):
    vid, artifacts = materialized
    assert run_version(vid, artifacts, "full").status == "succeeded"
    sql("UPDATE origin_sales SET amount = '99' WHERE doc = 'A1' AND line = 1")
    run = run_version(vid, artifacts, "incremental")
    assert run.status == "succeeded", run.message
    assert run.rollups["ventas-dia"]["ok"] is True
    assert run.rollups["ventas-dia"]["mode"] == "window"
    assert rollup_values(artifacts) == raw_by_day_product()


def test_pk_row_moving_to_another_day(materialized):
    vid, artifacts = materialized
    assert run_version(vid, artifacts, "full").status == "succeeded"
    sql("UPDATE origin_sales SET completed_at = completed_at - interval '1 day' "
        "WHERE doc = 'A1' AND line = 2")
    run = run_version(vid, artifacts, "incremental")
    assert run.status == "succeeded", run.message
    assert run.rollups["ventas-dia"]["ok"] is True
    assert run.rollups["ventas-dia"]["mode"] == "window"
    assert rollup_values(artifacts) == raw_by_day_product()


def test_failed_refresh_keeps_previous_and_marks_stale(materialized, monkeypatch):
    vid, artifacts = materialized
    assert run_version(vid, artifacts, "full").status == "succeeded"
    before = ds_sql(f"SELECT * FROM {ROLLUP_TABLE} ORDER BY 1, 2 NULLS FIRST")

    def boom(*a, **k):
        raise RuntimeError("boom")

    with monkeypatch.context() as m:
        m.setattr(rollup, "refresh_days", boom)
        m.setattr(rollup, "build_full", boom)
        sql("UPDATE origin_sales SET amount = '77' WHERE doc = 'A1' AND line = 1")
        run = run_version(vid, artifacts, "incremental")
    assert run.status == "succeeded"
    assert run.message.startswith(
        "datos publicados; resumen diario no actualizado: ventas-dia"
    )
    assert run.rollups["ventas-dia"]["ok"] is False
    assert (
        sql("SELECT status FROM report_rollup WHERE report_id = 'ventas-dia'")[0][0]
        == "stale"
    )
    after = ds_sql(f"SELECT * FROM {ROLLUP_TABLE} ORDER BY 1, 2 NULLS FIRST")
    assert before == after

    # next run rebuilds in full and recovers
    run2 = run_version(vid, artifacts, "incremental")
    assert run2.status == "succeeded"
    assert run2.rollups.get("ventas-dia", {}).get("ok") is True
    assert (
        sql("SELECT status FROM report_rollup WHERE report_id = 'ventas-dia'")[0][0]
        == "ready"
    )
    assert rollup_values(artifacts) == raw_by_day_product()


def test_ensure_version_rebuilds_missing_and_drops_removed(materialized):
    vid, artifacts = materialized
    assert run_version(vid, artifacts, "full").status == "succeeded"
    sql(f"DROP TABLE {ROLLUP_TABLE}")
    assert rollup.ensure_version(vid) is False
    assert (
        sql("SELECT status FROM report_rollup WHERE report_id = 'ventas-dia'")[0][0]
        == "ready"
    )
    assert ds_sql(f"SELECT count(*) FROM {ROLLUP_TABLE}")[0][0] > 0

    sql("UPDATE workspace_version SET artifacts = jsonb_set(artifacts, "
        "'{reports,ventas-dia,definition,materialize}', '\"none\"') WHERE id = :v", v=vid)
    assert rollup.ensure_version(vid) is False
    assert (
        sql("SELECT count(*) FROM report_rollup WHERE report_id = 'ventas-dia'")[0][0]
        == 0
    )
    assert sql("SELECT to_regclass(:t)", t=ROLLUP_TABLE)[0][0] is None


def test_worker_rollups_tick(materialized, monkeypatch):
    vid, _ = materialized
    seen = {}

    def fake_ensure(version_id, **k):
        seen["version_id"] = version_id
        return True

    monkeypatch.setattr(rollup, "ensure_version", fake_ensure)
    w = Worker()
    w.version_id = vid
    job = w.rollups_tick(force=True)
    assert job is not None
    job.result()
    assert seen["version_id"] == vid
    assert w.rollup_pending is True
    w.pool.shutdown(wait=True)


def test_non_materialized_report_has_no_rollup(materialized):
    vid, artifacts = materialized
    assert run_version(vid, artifacts, "full").status == "succeeded"
    assert sql("SELECT count(*) FROM report_rollup WHERE report_id = 'ventas'")[0][0] == 0


def _eq(a, b):
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-9)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_eq(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b, strict=True))
    return a == b


def _routed_and_raw(db, vid, params, today):
    version = db.get(WorkspaceVersion, vid)
    raw = engine.cached_context(version, "ventas-dia")
    routed = engine.routed(db, raw)
    sel, filters = engine.selection(raw, params, today)
    return routed, raw, sel, filters


def test_routed_rollup_matches_raw(materialized):
    vid, artifacts = materialized
    assert run_version(vid, artifacts, "full").status == "succeeded"
    today = date(2026, 9, 29)
    cases = [
        {"period": "custom", "from": "2026-09-27", "to": "2026-09-28"},
        {"period": "custom", "from": "2026-08-01", "to": "2026-09-29"},
    ]
    with get_sessionmaker()() as db:
        for params in cases:
            for compare in ("none", "previous_period", "previous_year"):
                p = dict(params)
                if compare != "none":
                    p["compare"] = compare
                for fprod in ([], ["P1"]):
                    if fprod:
                        p["filter.product"] = fprod[0]
                    routed, raw, sel, filters = _routed_and_raw(db, vid, p, today)
                    assert routed.rollup is not None
                    rv = engine.run_views(routed, sel, filters, get_settings().timezone)
                    vv = engine.run_views(raw, sel, filters, get_settings().timezone)
                    assert _eq(rv, vv), f"mismatch for {p}"


def test_stale_rollup_not_routed(materialized):
    vid, artifacts = materialized
    assert run_version(vid, artifacts, "full").status == "succeeded"
    with get_sessionmaker()() as db:
        sql("UPDATE report_rollup SET status = 'stale' WHERE report_id = 'ventas-dia'")
        version = db.get(WorkspaceVersion, vid)
        raw = engine.cached_context(version, "ventas-dia")
        routed = engine.routed(db, raw)
        assert routed.rollup is None


def test_dropped_rollup_falls_back_and_marks_stale(materialized):
    vid, artifacts = materialized
    assert run_version(vid, artifacts, "full").status == "succeeded"
    today = date(2026, 9, 29)
    params = {"period": "custom", "from": "2026-09-27", "to": "2026-09-28"}
    with get_sessionmaker()() as db:
        routed, raw, sel, filters = _routed_and_raw(db, vid, params, today)
        assert routed.rollup is not None
        sql(f"DROP TABLE {ROLLUP_TABLE}")
        rv = engine.run_views(routed, sel, filters, get_settings().timezone)
        vv = engine.run_views(raw, sel, filters, get_settings().timezone)
        assert _eq(rv, vv)
        assert sql("SELECT status FROM report_rollup WHERE report_id = 'ventas-dia'")[0][0] \
            == "stale"


def test_direct_and_preview_never_routed(materialized):
    import dataclasses
    vid, artifacts = materialized
    assert run_version(vid, artifacts, "full").status == "succeeded"
    with get_sessionmaker()() as db:
        version = db.get(WorkspaceVersion, vid)
        raw = engine.cached_context(version, "ventas-dia")
        dctx = dataclasses.replace(
            raw, direct=engine.DirectSpec(source="bi", label="BI"))
        assert engine.routed(db, dctx).rollup is None
        prev = engine.PreviewVersion(id=version.id, artifacts=artifacts)
        pctx = engine.preview_context(prev, "ventas-dia", raw.definition,
                                      artifacts["integrations"], set(), 1)
        assert engine.routed(db, pctx).rollup is None


def test_joined_dataset_change_forces_full(materialized):
    vid, artifacts = materialized
    assert run_version(vid, artifacts, 'full').status == 'succeeded'
    sql('''INSERT INTO origin_sales VALUES ('A3', 1, 'sale', :t, 5, 'P9')''',
        t=NOW - timedelta(days=1))
    run = run_version(vid, artifacts, 'incremental')
    assert run.status == 'succeeded', run.message
    assert run.rollups['ventas-dia']['mode'] == 'full'
    assert rollup_values(artifacts) == raw_by_day_product()


def test_rollup_lock_key(materialized):
    from app.db import get_engine
    with get_engine().connect() as conn:
        pg = conn.connection.driver_connection
        rollup.lock(pg, 'ventas-dia')
        n = pg.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                       "AND pid = pg_backend_pid()").fetchone()[0]
        assert n >= 1
        pg.rollback()

