"""Tests for multi-value report filters and the filter-options search (feature 012, task 002)."""
import re
from urllib.parse import quote

from types import SimpleNamespace
from datetime import date

import pytest

from app.engine import report as engine
from app.reports import pdf
from tests.conftest import sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import SELECTION
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture


def test_two_values_equal_the_sum_of_each(applied):
    r = applied.get(
        f"/api/reports/ventas/data?{SELECTION}&filter.product=P1&filter.product=P2")
    assert r.status_code == 200
    body = r.json()
    assert body["views"][0]["items"][0]["value"] == 11.75
    assert body["filters"] == {"product": ["P1", "P2"]}
    ranking = body["views"][2]["items"]
    keys = {row["key"] for row in ranking}
    assert {"P1", "P2"} <= keys


def test_cross_views_computes_source_and_ignore(monkeypatch):
    ctx = SimpleNamespace(
        definition={"filters": ["product"], "views": [
            {"id": "productos", "type": "ranking", "dimension": "product"},
            {"id": "clientes", "type": "ranking", "dimension": "cliente"},
        ]},
        dimensions={"product": {"label": "Producto"}, "cliente": {"label": "Cliente"}},
        report_id="r",
    )

    def fake(ctx, vdef, sel, filters, tz, reference=None, *, session=None):
        return {"id": vdef["id"], "filters": filters}

    monkeypatch.setattr(engine, "_run_view", fake)
    out = engine.cross_views(ctx, None, {"product": ["A"]}, "UTC")
    assert out["source_views"]["product"]["productos"]["filters"] == {}
    assert "ignore_views" not in out                    # product is a sheet filter
    out = engine.cross_views(ctx, None, {"cliente": ["ACME"]}, "UTC")
    assert out["source_views"]["cliente"]["clientes"]["filters"] == {}
    assert out["ignore_views"]["productos"]["filters"] == {}


def test_the_source_view_keeps_the_clicked_dimension(applied):
    # Feature 063: the ranking that owns `product` must still show every product.
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}&filter.product=P1")
    assert r.status_code == 200
    body = r.json()
    main = next(v for v in body["views"] if v.get("id") == "productos")
    source = body["source_views"]["product"]["productos"]
    assert {row["key"] for row in main["items"]} == {"P1"}
    assert {"P1", "P2"} <= {row["key"] for row in source["items"]}


def test_single_value_link_still_works(applied):
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}&filter.product=P1")
    assert r.status_code == 200
    body = r.json()
    assert body["views"][0]["items"][0]["value"] == 7.5
    assert body["filters"] == {"product": ["P1"]}

    r_dup = applied.get(
        f"/api/reports/ventas/data?{SELECTION}&filter.product=P1&filter.product=P1")
    assert r_dup.status_code == 200
    assert r_dup.headers["ETag"] == r.headers["ETag"]

    r_empty = applied.get(f"/api/reports/ventas/data?{SELECTION}&filter.product=")
    assert r_empty.status_code == 200
    body = r_empty.json()
    assert body["views"][0]["items"][0]["value"] == 11.75
    assert body["filters"] == {}


def test_any_declared_dimension_is_filterable_even_outside_filters():
    ctx = SimpleNamespace(
        definition={"periods": {}, "compare": {}, "filters": ["product"],
                    "dimensions": {}},
        dimensions={"product": {"label": "Producto", "sql": "p.code"},
                    "cliente": {"label": "Cliente", "sql": "c.name"}},
    )
    sel, filters = engine.selection(ctx, [("filter.cliente", "ACME")], date(2026, 11, 11))
    assert filters == {"cliente": ["ACME"]}
    assert sel.period == "mtd"


def test_unknown_filter_is_refused(applied):
    # Feature 063: any declared dimension is filterable; an undeclared id is a client error.
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}&filter.nope=x")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unknown_filter"


def test_too_many_values(applied):
    qs = "".join(f"&filter.product=P{i}" for i in range(51))
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}{qs}")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "too_many_values"

    qs = "".join(f"&filter.product=P{i}" for i in range(50))
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}{qs}")
    assert r.status_code == 200


def test_values_are_bound(applied):
    bad1 = "P1'; DROP TABLE dashboard;--"
    bad2 = 'x" OR 1=1'
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}"
                    f"&filter.product={quote(bad1)}"
                    f"&filter.product={quote(bad2)}"
                    f"&filter.product=P2")
    assert r.status_code == 200
    body = r.json()
    assert body["views"][0]["items"][0]["value"] == 4.25
    assert body["filters"] == {"product": sorted([bad1, bad2, "P2"])}
    assert sql("SELECT count(*) FROM dashboard")[0][0] >= 1


def test_filter_search(applied, monkeypatch):
    base = f"/api/reports/ventas/filters/product?{SELECTION}"

    r = applied.get(f"{base}&q=p1")
    assert r.status_code == 200
    assert r.json() == {"items": ["P1"], "truncated": False}

    r = applied.get(f"{base}&q={quote('%')}")
    assert r.status_code == 200
    assert r.json() == {"items": [], "truncated": False}

    r = applied.get(f"{base}&q={quote('_')}")
    assert r.status_code == 200
    assert r.json() == {"items": [], "truncated": False}

    r = applied.get(f"{base}&q=P_")
    assert r.status_code == 200
    assert r.json() == {"items": [], "truncated": False}

    r = applied.get(f"{base}&q=")
    assert r.status_code == 200
    assert r.json() == {"items": ["P1", "P2"], "truncated": False}

    monkeypatch.setattr(engine, "FILTER_OPTIONS_LIMIT", 1)
    r = applied.get(f"{base}&q=")
    assert r.status_code == 200
    assert r.json() == {"items": ["P1"], "truncated": True}
    monkeypatch.undo()

    r = applied.get(f"{base}&q={quote('P1\'')}")
    assert r.status_code == 200
    assert r.json() == {"items": [], "truncated": False}


def test_pdf_honours_multi_values(applied):
    r = applied.post(f"/api/reports/ventas/pdf?{SELECTION}"
                     f"&filter.product=P1&filter.product=P2")
    assert r.status_code == 200
    text = r.content.decode("latin-1")
    assert "(11,75 USD)" in text
    assert "Producto: P1, P2" in text

    r = applied.post(f"/api/reports/ventas/pdf?{SELECTION}&filter.product=P2")
    assert r.status_code == 200
    text = r.content.decode("latin-1")
    assert "(4,25 USD)" in text
    assert "(11,75 USD)" not in text


def test_cache_distinguishes_selections(applied):
    urls = {
        "none": f"/api/reports/ventas/data?{SELECTION}",
        "P1": f"/api/reports/ventas/data?{SELECTION}&filter.product=P1",
        "P2": f"/api/reports/ventas/data?{SELECTION}&filter.product=P2",
        "both": f"/api/reports/ventas/data?{SELECTION}&filter.product=P1&filter.product=P2",
        "both_rev": f"/api/reports/ventas/data?{SELECTION}&filter.product=P2&filter.product=P1",
    }
    etags = {name: applied.get(url).headers["ETag"] for name, url in urls.items()}
    assert len({etags["none"], etags["P1"], etags["P2"], etags["both"]}) == 4
    assert etags["both"] == etags["both_rev"]

    r = applied.get(urls["both_rev"])
    assert r.json()["views"][0]["items"][0]["value"] == 11.75

    r = applied.get(urls["both"], headers={"If-None-Match": etags["P1"]})
    assert r.status_code == 200
    assert r.headers["ETag"] == etags["both"]


def test_pdf_escapes_filter_values(applied):
    r = applied.post(f"/api/reports/ventas/pdf?{SELECTION}"
                     f"&filter.product=%3Cb&filter.product=a%26b")
    assert r.status_code == 200
    text = r.content.decode("latin-1")
    joined = "".join(re.findall(r"\((.*?)\) Tj", text))
    assert "Producto: <b, a&b" in joined


def _pdf_lines(content: bytes) -> list[str]:
    """Text of each visual line in an uncompressed ReportLab PDF, unescaped."""

    def unescaped(raw: bytes) -> str:
        return re.sub(
            rb"\\([0-7]{1,3}|.)",
            lambda m: bytes([int(m.group(1), 8)])
            if m.group(1)[:1] in b"01234567"
            else m.group(1),
            raw,
        ).decode("cp1252")

    out = []
    current = ""
    token = rb"\(((?:\\.|[^\\)])*)\) Tj|\bT\*|\bT[dDm]\b|\bET\b"
    for match in re.finditer(token, content):
        if match.group(0).endswith(b"Tj"):
            current += unescaped(match.group(1))
        else:
            if current:
                out.append(current)
                current = ""
    if current:
        out.append(current)
    return out


def test_pdf_meta_matches_context_block(applied):
    r = applied.post(f"/api/reports/ventas/pdf?{SELECTION}")
    assert r.status_code == 200
    lines = _pdf_lines(r.content)
    assert "Período: Personalizado (27 sep 2026 \u2013 28 sep 2026)" in lines
    assert "Comparado con: 25 sep 2026 \u2013 26 sep 2026" in lines
    full_name = applied.get("/api/me").json()["full_name"]
    assert f"Consultado por: {full_name}" in lines


def test_pdf_meta_without_comparison(applied):
    selection = SELECTION.replace("compare=previous_period", "compare=none")
    r = applied.post(f"/api/reports/ventas/pdf?{selection}")
    assert r.status_code == 200
    lines = _pdf_lines(r.content)
    assert "Comparado con: Sin comparación" in lines


def test_render_meta_matches_context_block_and_escapes_viewer():
    definition = {"title": "T", "dimensions": {}, "currency": "USD"}
    payload = {
        "selection": {
            "period": "mtd",
            "current": {"from": "2026-10-01", "to": "2026-10-02"},
            "previous": None,
            "partial": True,
        },
        "views": [],
        "filters": {},
    }
    content = pdf.render(
        definition,
        payload,
        organization="ACME",
        product="Customer A Reports",
        viewer="Ana <b>&",
    )
    lines = _pdf_lines(content)
    assert "Período: Mes en curso (01 oct 2026 \u2013 02 oct 2026, en curso)" in lines
    assert "Comparado con: Sin comparación" in lines
    assert "Consultado por: Ana <b>&" in lines
    assert not any(line.startswith("Consultado por: <b>") for line in lines)


def test_render_meta_omits_viewer_when_none():
    definition = {"title": "T", "dimensions": {}, "currency": "USD"}
    payload = {
        "selection": {
            "period": "mtd",
            "current": {"from": "2026-10-01", "to": "2026-10-02"},
            "previous": None,
            "partial": False,
        },
        "views": [],
        "filters": {},
    }
    content = pdf.render(
        definition,
        payload,
        organization="ACME",
        product="Customer A Reports",
    )
    lines = _pdf_lines(content)
    assert not any(line.startswith("Consultado por") for line in lines)


def test_a_truncated_ranking_and_full_rows(monkeypatch):
    """Feature 064: the payload says it was cut, and `full` lifts the view's own limit."""
    ctx = SimpleNamespace(
        metrics={"m": {"label": "Ventas", "format": "currency"}},
        dimensions={"product": {"label": "Producto", "sql": "products.name"}},
        report_id="r", direct=None, rollup=None, columns={"products": {"name": {"type": "text"}}},
    )
    selection = SimpleNamespace(current=None, previous=None)
    calls = {"rows": 0}

    def fake_aggregate(ctx, metrics, sel, filters, tz, *, group=None, order_metric=None,
                       limit=None, session=None, keys=None):
        if group:
            calls["rows"] += 1
            return [{"key": "A", "m": 50}, {"key": "B", "m": 30}, {"key": "C", "m": 20}][:limit]
        return [{"m": 100}]

    monkeypatch.setattr(engine, "aggregate", fake_aggregate)
    view = engine.view_ranking(ctx, {"metric": "m", "dimension": "product", "limit": 2},
                               selection, {}, "UTC")
    assert [item["key"] for item in view["items"]] == ["A", "B"]
    assert view["truncated"] is True

    full = engine.view_ranking(ctx, {"metric": "m", "dimension": "product", "limit": 2},
                               selection, {}, "UTC", full=True)
    assert [item["key"] for item in full["items"]] == ["A", "B", "C"]
    assert full["truncated"] is False


def test_full_uses_its_own_cache_entry(applied):
    normal = applied.get(f"/api/reports/ventas/data?{SELECTION}")
    full = applied.get(f"/api/reports/ventas/data?{SELECTION}&full=1")
    assert normal.status_code == full.status_code == 200
    assert normal.headers["etag"] != full.headers["etag"]
    assert all("truncated" in view for view in full.json()["views"]
               if view.get("type") in ("ranking", "table"))
