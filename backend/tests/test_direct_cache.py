import dataclasses
import threading
import time
from datetime import date

import bizview_cli.validate as wsv
import pytest
import yaml
from sqlalchemy import event, text

from app.api import reports
from app.config import get_settings
from app.db import get_engine, get_read_sessionmaker, lock_key
from app.engine import direct, report
from app.errors import ApiError
from app.mail import sends
from tests.conftest import signed_in, sql
from tests.test_mail_send import enable_mail, send
from tests.test_mail_send import smtp as smtp
from tests.test_runner import origin as origin
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import applied as applied
from tests.test_vibe_reporting import workspace as workspace

REAL_RUN_VIEWS = report.run_views
BUCKET_A = 1_000_000 * 300 + 1
BUCKET_B = BUCKET_A + 300


@pytest.fixture(autouse=True)
def _clear_direct_cache():
    direct.clear_cache()
    direct._inflight.clear()
    yield
    direct.clear_cache()
    direct._inflight.clear()


@pytest.fixture
def seeded():
    phys = direct.physical_schema("ds_direct19c")
    sql(f'DROP SCHEMA IF EXISTS "{phys}" CASCADE')
    sql(f'CREATE SCHEMA "{phys}"')
    sql(f'CREATE TABLE "{phys}".sales (day date, amount numeric, product text)')
    sql(f"""INSERT INTO "{phys}".sales VALUES
            ('2026-09-01', 10.5, 'A'), ('2026-09-02', 20.0, 'B'), ('2026-09-03', 5.25, 'A')""")
    yield phys
    sql(f'DROP SCHEMA "{phys}" CASCADE')


def definition(**direct_over):
    return {
        "title": "Ventas directo",
        "date": "s.day",
        "direct": {"source": "bi", "tables": {"s": {"table": "ds_direct19c.sales", "columns": {
            "day": {"type": "date"}, "amount": {"type": "numeric"}, "product": {"type": "text"}}}},
            **direct_over},
        "metrics": {"total": {"label": "Total", "sql": "sum(s.amount)", "format": "number"}},
        "dimensions": {"product": {"label": "Producto", "sql": "s.product"}},
        "views": [{"type": "kpis", "metrics": ["total"]},
                  {"type": "table", "dimensions": ["product"], "metrics": ["total"],
                   "limit": 1000}],
        "filters": ["product"],
    }


def make_ctx(**direct_over):
    return report._build_context("vd", definition(**direct_over),
                                 report.PreviewVersion(id=901, artifacts={}), {}, None)


def selection(ctx):
    return report.selection(ctx, {"period": "custom", "from": "2026-09-01",
                                  "to": "2026-09-30", "compare": "none"},
                            date(2026, 9, 30))


def _db():
    return get_read_sessionmaker()()


def _fill(db, ctx, sel, filters, key):
    return direct.cached_data(db, ctx, sel, filters, key, "UTC")


# T017

def test_context_direct_mapping(seeded):
    ctx = make_ctx()
    assert ctx.tables == {"s": (direct.physical_schema("ds_direct19c"), "sales")}
    assert ctx.integrations == []
    assert isinstance(ctx.runner, direct.DirectRunner)
    assert ctx.runner.tables == {"s": ("ds_direct19c", "sales")}
    assert ctx.direct == report.DirectSpec("bi", "bi", 300, 15, 500)
    ctx2 = make_ctx(source="Origen prueba", cache_seconds=120, timeout_seconds=5, max_rows=2)
    assert ctx2.direct == report.DirectSpec("Origen prueba", "Origen prueba", 120, 5, 2)


def test_context_refuses_product_table():
    d = definition()
    d["direct"]["tables"]["s"] = {"table": "public.app_user",
                                  "columns": {"id": {"type": "integer"}}}
    with pytest.raises(ApiError) as exc:
        report._build_context("vd", d, report.PreviewVersion(id=901, artifacts={}), {}, None)
    assert exc.value.status == 409
    assert exc.value.code == "direct_product_table"
    d = definition()
    d["direct"]["tables"]["s"] = {"table": "app_test_x.t",
                                  "columns": {"id": {"type": "integer"}}}
    d["direct"]["source"] = "Origen prueba"
    with pytest.raises(ApiError) as exc:
        report._build_context("vd", d, report.PreviewVersion(id=901, artifacts={}), {}, None)
    assert exc.value.status == 409
    assert exc.value.code == "direct_product_table"


def test_definition_json_direct_key():
    ctx = make_ctx(cache_seconds=120)
    assert report.definition_json(ctx)["direct"] == {
        "source": "bi", "cache_seconds": 120}


def test_view_table_limit_capped(seeded):
    ctx = make_ctx(max_rows=1)
    views = report.run_views(ctx, *selection(ctx), "UTC")
    table = next(v for v in views if v["type"] == "table")
    assert len(table["rows"]) == 1


# T018

def test_bucket_version(monkeypatch):
    ctx = make_ctx()
    monkeypatch.setattr(report, "_epoch", lambda: 1000 * 300 + 5)
    assert report.data_version(None, ctx) == ("v901-d1000", None)
    monkeypatch.setattr(report, "_epoch", lambda: 1001 * 300 + 5)
    assert report.data_version(None, ctx) == ("v901-d1001", None)
    ctx60 = make_ctx(cache_seconds=60)
    monkeypatch.setattr(report, "_epoch", lambda: 1000 * 60 + 5)
    assert report.data_version(None, ctx60) == ("v901-d1000", None)


# T019

def test_cached_data_miss_then_hit(seeded, monkeypatch):
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    counter = {"n": 0}
    orig = direct.DirectRunner.session

    def counting(self):
        counter["n"] += 1
        return orig(self)

    monkeypatch.setattr(direct.DirectRunner, "session", counting)
    db = _db()
    try:
        p1 = direct.cached_data(db, ctx, sel, filters, key, "UTC")
        assert counter["n"] == 1
        fr = p1["freshness"]
        assert fr["mode"] == "direct"
        assert fr["source"] == "bi"
        assert fr["stale"] is False
        assert fr["data_version"] == report.direct_version(ctx)
        assert fr["queried_at"] is not None
        kpis = next(v for v in p1["views"] if v["type"] == "kpis")
        assert kpis["items"][0]["value"] == 35.75
        p2 = direct.cached_data(db, ctx, sel, filters, key, "UTC")
        assert p2 == p1
        assert counter["n"] == 1
    finally:
        db.close()


def test_single_flight_ten_concurrent(seeded, monkeypatch):
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    calls = {"n": 0}

    def slow_run(*a, **kw):
        calls["n"] += 1
        time.sleep(0.5)
        return REAL_RUN_VIEWS(*a, **kw)

    monkeypatch.setattr(report, "run_views", slow_run)
    barrier = threading.Barrier(10)
    results = []
    errors = []
    lock = threading.Lock()

    def worker():
        db = _db()
        try:
            barrier.wait()
            r = direct.cached_data(db, ctx, sel, filters, key, "UTC")
            with lock:
                results.append(r)
        except Exception as e:
            with lock:
                errors.append(e)
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert calls["n"] == 1
    assert all(r == results[0] for r in results)


def test_stale_fallback(seeded, monkeypatch):
    monkeypatch.setattr(reports, "_today", lambda: date(2026, 9, 30))
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    for code in ("unreachable", "timeout", "busy"):
        sql("DELETE FROM report_cache")
        direct._inflight.clear()
        monkeypatch.setattr(report, "run_views", REAL_RUN_VIEWS)
        monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)
        db = _db()
        try:
            old = _fill(db, ctx, sel, filters, key)
        finally:
            db.close()
        monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)
        monkeypatch.setattr(report, "run_views", lambda *a, _c=code, **kw: (
            _ for _ in ()).throw(direct.DirectError(_c)))
        db = _db()
        try:
            p = direct.cached_data(db, ctx, sel, filters, key, "UTC")
            fr = p["freshness"]
            assert fr["stale"] is True
            assert fr["stale_reason"] == code
            assert fr["data_version"] == old["freshness"]["data_version"]
            assert fr["queried_at"] == old["freshness"]["queried_at"]
            data = reports._data(db, ctx, [("period", "custom"), ("from", "2026-09-01"),
                                           ("to", "2026-09-30"), ("compare", "none")])
            assert data["etag"].endswith('-stale"')
        finally:
            db.close()


def test_stale_older_than_24h_ignored(seeded, monkeypatch):
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    sql("DELETE FROM report_cache")
    direct._inflight.clear()
    monkeypatch.setattr(report, "run_views", REAL_RUN_VIEWS)
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)
    db = _db()
    try:
        _fill(db, ctx, sel, filters, key)
    finally:
        db.close()
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)
    monkeypatch.setattr(report, "run_views", lambda *a, **kw: (_ for _ in ()).throw(
        direct.DirectError("unreachable")))
    sql("UPDATE report_cache SET created_at = now() - interval '25 hours'")
    db = _db()
    try:
        with pytest.raises(ApiError) as exc:
            direct.cached_data(db, ctx, sel, filters, key, "UTC")
        assert exc.value.status == 503
        assert exc.value.code == "source_unavailable"
    finally:
        db.close()


def test_errors_without_cache(monkeypatch):
    cases = {
        "timeout": (503, "source_timeout"),
        "unreachable": (503, "source_unavailable"),
        "busy": (503, "source_busy"),
        "structure_changed": (409, "direct_structure_changed"),
        "not_allowed": (409, "direct_not_allowed"),
        "product_table": (409, "direct_product_table"),
        "error": (503, "source_error"),
    }
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    for code, (status, api_code) in cases.items():
        sql("DELETE FROM report_cache")
        direct._inflight.clear()
        monkeypatch.setattr(report, "run_views", lambda *a, _c=code, **kw: (
            _ for _ in ()).throw(direct.DirectError(_c)))
        db = _db()
        try:
            with pytest.raises(ApiError) as exc:
                direct.cached_data(db, ctx, sel, filters, key, "UTC")
            assert exc.value.status == status
            assert exc.value.code == api_code
        finally:
            db.close()


def test_structure_changed_not_stale(seeded, monkeypatch):
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    sql("DELETE FROM report_cache")
    direct._inflight.clear()
    monkeypatch.setattr(report, "run_views", REAL_RUN_VIEWS)
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)
    db = _db()
    try:
        _fill(db, ctx, sel, filters, key)
    finally:
        db.close()
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)
    monkeypatch.setattr(report, "run_views", lambda *a, **kw: (_ for _ in ()).throw(
        direct.DirectError("structure_changed")))
    db = _db()
    try:
        with pytest.raises(ApiError) as exc:
            direct.cached_data(db, ctx, sel, filters, key, "UTC")
        assert exc.value.status == 409
        assert exc.value.code == "direct_structure_changed"
    finally:
        db.close()


def test_follower_wait_bounded(seeded, monkeypatch):
    ctx = make_ctx(timeout_seconds=1)
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)

    def slow_run(*a, **kw):
        time.sleep(4)
        return REAL_RUN_VIEWS(*a, **kw)

    monkeypatch.setattr(report, "run_views", slow_run)
    leader_done = threading.Event()
    errors = []

    def leader():
        db = _db()
        try:
            direct.cached_data(db, ctx, sel, filters, key, "UTC")
        except Exception as e:
            errors.append(e)
        finally:
            db.close()
            leader_done.set()

    t = threading.Thread(target=leader)
    t.start()
    time.sleep(0.2)
    db = _db()
    t0 = time.monotonic()
    try:
        with pytest.raises(ApiError) as exc:
            direct.cached_data(db, ctx, sel, filters, key, "UTC")
        assert exc.value.status == 503
        assert exc.value.code == "source_timeout"
        assert time.monotonic() - t0 < 2.6
    finally:
        db.close()
    t.join(timeout=10)


def test_cleanup_keeps_same_version_buckets(seeded, monkeypatch):
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    sql("DELETE FROM report_cache")
    direct._inflight.clear()
    monkeypatch.setattr(report, "run_views", REAL_RUN_VIEWS)
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)
    db = _db()
    try:
        _fill(db, ctx, sel, filters, key)
        sql("INSERT INTO report_cache (report_id, selection_hash, data_version, kind, "
            "payload) VALUES ('vd', :k, 'v900-d1', 'data', '{}'::jsonb)", k=key)
        sql("INSERT INTO report_cache (report_id, selection_hash, data_version, kind, "
            "payload) VALUES ('vd', :k, 'v901-d1', 'data', '{}'::jsonb)", k=key)
        sql("INSERT INTO report_cache (report_id, selection_hash, data_version, kind, "
            "payload, created_at) VALUES ('vd', :k, 'v901-d2', 'data', '{}'::jsonb, "
            "now() - interval '25 hours')", k=key)
        sql("INSERT INTO report_cache (report_id, selection_hash, data_version, kind, "
            "payload) VALUES ('vd', :k, 'v900-d1', 'narrative', '{}'::jsonb)", k=key)
        monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)
        direct._inflight.clear()
        direct.cached_data(db, ctx, sel, filters, key, "UTC")
        rows = sql("SELECT data_version, kind FROM report_cache ORDER BY data_version, kind")
        assert ("v900-d1", "narrative") in rows
        assert ("v901-d1", "data") in rows
        assert ("v900-d1", "data") not in rows
        assert ("v901-d2", "data") not in rows
        assert (f"v901-d{1_000_000}", "data") in rows
        assert (f"v901-d{1_000_001}", "data") in rows
    finally:
        db.close()


def _advisory_free(key, version):
    conn = get_engine().connect()
    pg = None
    try:
        pg = conn.connection.driver_connection
        pg.autocommit = True
        return bool(pg.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
            (lock_key("direct-sf", "vd", key, version),)).fetchone()[0])
    finally:
        try:
            if pg is not None and not pg.closed and not pg.broken:
                pg.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                           (lock_key("direct-sf", "vd", key, version),))
                pg.autocommit = False
        except Exception:
            pass
        conn.close()


def test_sf_lock_released(seeded, monkeypatch):
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    monkeypatch.setattr(report, "run_views", REAL_RUN_VIEWS)
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)
    version_a = report.direct_version(ctx)
    db = _db()
    try:
        direct.cached_data(db, ctx, sel, filters, key, "UTC")
    finally:
        db.close()
    assert _advisory_free(key, version_a)
    sql("DELETE FROM report_cache")
    monkeypatch.setattr(report, "run_views", lambda *a, **kw: (_ for _ in ()).throw(
        direct.DirectError("unreachable")))
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)
    version_b = report.direct_version(ctx)
    direct._inflight.clear()
    db = _db()
    try:
        with pytest.raises(ApiError):
            direct.cached_data(db, ctx, sel, filters, key, "UTC")
    finally:
        db.close()
    assert _advisory_free(key, version_b)


def test_sf_cap_computes_alone(seeded, monkeypatch):
    monkeypatch.setattr(direct, "SF_MAX", 0)
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    db = _db()
    try:
        p = direct.cached_data(db, ctx, sel, filters, key, "UTC")
        assert any(v["type"] == "kpis" for v in p["views"])
        assert direct._inflight == {}
    finally:
        db.close()


# T020

def test_data_etag_and_filters(seeded, monkeypatch):
    monkeypatch.setattr(reports, "_today", lambda: date(2026, 9, 30))
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)
    db = _db()
    try:
        data = reports._data(db, ctx, [("period", "custom"), ("from", "2026-09-01"),
                                       ("to", "2026-09-30"), ("compare", "none")])
        assert data["etag"] == f'"{report.direct_version(ctx)}-{key}"'
        items, truncated = reports.filter_values(ctx, "product", sel, None)
        assert items == ["A", "B"]
        assert truncated is False
        monkeypatch.setattr(report, "filter_options",
                            lambda *a, **kw: (_ for _ in ()).throw(
                                direct.DirectError("timeout")))
        with pytest.raises(ApiError) as exc:
            reports.filter_values(ctx, "product", sel, None)
        assert exc.value.status == 503
        assert exc.value.code == "source_timeout"
    finally:
        db.close()


# T021

def test_email_direct_failure_marks_delivery_failed(applied, smtp, monkeypatch, caplog):
    enable_mail()
    c = signed_in("root@example.com")
    assert send(c, emails=["gerente@cliente.com"]).status_code == 201
    orig_ctx = sends.links.report_context

    def fake_ctx(db, dash):
        c2 = orig_ctx(db, dash)
        if c2 is None:
            return None
        return dataclasses.replace(c2, direct=report.DirectSpec(
            "bi", "bi"))

    monkeypatch.setattr(sends.links, "report_context", fake_ctx)
    monkeypatch.setattr(sends.reports, "_data",
                        lambda *a, **kw: (_ for _ in ()).throw(
                            ApiError(503, "source_unavailable",
                                     "No se pudo conectar con la fuente")))
    sends.process_due()
    assert smtp.sent == []
    rows = sql("SELECT status, error FROM email_delivery")
    assert rows == [("failed", "No se pudo generar el PDF: No se pudo conectar con la fuente")]
    assert not any(r.exc_info for r in caplog.records if r.levelname == "ERROR")


# T022

def test_validation_context_sources(pg_source):
    db = _db()
    try:
        ctx = direct.validation_context(db)
        src = ctx.sources["origen prueba"]
        assert src == {"name": "Origen prueba", "kind": "postgresql", "enabled": True,
                       "direct": False, "bi": True}
        assert ctx.bi_enabled is True
        assert "public.app_user" in ctx.product_tables
        assert ctx.warn_rows == get_settings().direct_report_warn_rows
        assert ctx.personal_kind("email") is not None
        assert ctx.personal_kind("amount") is None
    finally:
        db.close()


def test_validation_context_structure(seeded, monkeypatch):
    db = _db()
    try:
        ctx = direct.validation_context(db)
        result = ctx.structure("bi", ["ds_direct19c.sales", "ds_direct19c.nope"])
        assert set(result["tables"]) == {"ds_direct19c.sales"}
        cols = result["tables"]["ds_direct19c.sales"]["columns"]
        assert cols == {"day": "date", "amount": "numeric", "product": "text"}
        entry = result["tables"]["ds_direct19c.sales"]
        assert "product_dependency" in entry
        assert "reltuples" in entry
        assert "date_indexed" in entry
        calls = {"n": 0}
        orig_structure = direct.structure

        def counted(*a, **kw):
            calls["n"] += 1
            return orig_structure(*a, **kw)

        monkeypatch.setattr(direct, "structure", counted)
        ctx2 = direct.validation_context(db)
        ctx2.structure("bi", ["ds_direct19c.sales", "ds_direct19c.nope"])
        ctx2.structure("bi", ["ds_direct19c.sales", "ds_direct19c.nope"])
        assert calls["n"] == 1
        bad = ctx2.structure("no-existe", ["a.b"])
        assert "error" in bad
    finally:
        db.close()


def test_validation_context_validates_workspace(seeded, tmp_path):
    spec_dir = tmp_path / "specs" / "reports" / "001-vd"
    spec_dir.mkdir(parents=True)
    (tmp_path / "bizview.yaml").write_text("name: demo\n")
    (spec_dir / "spec.md").write_text(
        "# Ventas directo\n\n**Spec type**: report\n\n**Status**: Approved\n\n"
        "**Modo**: directo\n\n**Fuente**: bi\n\n**Tablas**: ds_direct19c.sales\n\n"
        "**Mantenido por**: proceso ERP\n\n**Volumen esperado**: 3 filas\n")
    (spec_dir / "plan.md").write_text("# Plan\n")
    (spec_dir / "tasks.md").write_text("- [X] T001 hecho\n")
    rep_dir = tmp_path / "reports" / "vd"
    rep_dir.mkdir(parents=True)
    rep_yaml = {
        "id": "vd", "spec": "specs/reports/001-vd", "title": "Ventas directo",
        "direct": {"source": "bi", "tables": {"s": {"table": "ds_direct19c.sales",
                    "columns": {"day": {"type": "date"}, "amount": {"type": "numeric"},
                                "missing_col": {"type": "text"}}}}},
        "date": "s.day", "metrics": {"total": {"label": "Total", "sql": "sum(s.amount)"}},
        "views": [{"type": "kpis", "metrics": ["total"]}],
    }
    with open(rep_dir / "report.yaml", "w") as f:
        yaml.safe_dump(rep_yaml, f, sort_keys=False)
    db = _db()
    try:
        result = wsv.validate(tmp_path, direct=direct.validation_context(db))
        codes = {i.code for i in result.issues}
        assert "direct_column_missing" in codes
        assert any("missing_col" in i.message for i in result.issues)
    finally:
        db.close()
    del rep_yaml["direct"]["tables"]["s"]["columns"]["missing_col"]
    with open(rep_dir / "report.yaml", "w") as f:
        yaml.safe_dump(rep_yaml, f, sort_keys=False)
    db = _db()
    try:
        result = wsv.validate(tmp_path, direct=direct.validation_context(db))
        codes = {i.code for i in result.issues}
        assert not any(c.startswith("direct_") for c in codes)
    finally:
        db.close()


def test_stale_served_logged(seeded, monkeypatch):
    sql("DELETE FROM direct_read_log")
    monkeypatch.setattr(direct, "LOG_ASYNC", True)
    ctx = make_ctx()
    sel, filters = selection(ctx)
    key = report.selection_hash(sel, filters)

    monkeypatch.setattr(report, "run_views", REAL_RUN_VIEWS)
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)
    db = _db()
    try:
        direct.cached_data(db, ctx, sel, filters, key, "UTC")
    finally:
        db.close()

    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)
    monkeypatch.setattr(
        report,
        "run_views",
        lambda *a, **kw: (_ for _ in ()).throw(direct.DirectError("unreachable")),
    )
    db = _db()
    try:
        p = direct.cached_data(db, ctx, sel, filters, key, "UTC")
    finally:
        db.close()
    assert p["freshness"]["stale"] is True

    assert direct.flush_log()
    rows = sql(
        "SELECT outcome, stale_served FROM direct_read_log "
        "WHERE report_id = 'vd' AND stale_served"
    )
    assert rows == [("unreachable", True)]


# T049

def test_waiters_hold_no_bi_connection(seeded, monkeypatch):
    monkeypatch.setattr(get_settings(), "direct_report_concurrency", 1)
    ctx = make_ctx(timeout_seconds=30)
    sel, filters = selection(ctx)

    def slow_run_views(*args, **kwargs):
        time.sleep(0.2)
        return REAL_RUN_VIEWS(*args, **kwargs)

    monkeypatch.setattr(report, "run_views", slow_run_views)

    dbs = []
    try:
        for _ in range(10):
            db = _db()
            db.execute(text("SELECT 1"))
            dbs.append(db)

        pool = get_engine().pool
        baseline = pool.checkedout()
        peak = [baseline]
        plock = threading.Lock()

        def on_checkout(*_a):
            with plock:
                peak[0] = max(peak[0], pool.checkedout())

        event.listen(pool, "checkout", on_checkout)
        try:
            barrier = threading.Barrier(10)
            results = []
            errors = []
            rlock = threading.Lock()

            def worker(i):
                try:
                    barrier.wait()
                    res = direct.cached_data(
                        dbs[i], ctx, sel, filters, f"t049-{i}", "UTC"
                    )
                    with rlock:
                        results.append(res)
                except Exception as exc:
                    with rlock:
                        errors.append(exc)

            threads = [
                threading.Thread(target=worker, args=(i,)) for i in range(10)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=60)

            assert not errors
            assert len(results) == 10
            for res in results:
                assert res["freshness"]["mode"] == "direct"
            # sf lock + slot lock + query connection per held permit
            assert peak[0] - baseline <= 3 * 1
        finally:
            event.remove(pool, "checkout", on_checkout)
    finally:
        for db in dbs:
            db.close()
