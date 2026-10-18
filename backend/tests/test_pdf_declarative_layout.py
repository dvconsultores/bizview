"""Feature 026 US2: the declarative PDF layout (block order, one page, overflow, budget) and the
engine facts the renderer reads (`layout`, `layout_problems`, `views[].summary`, `views[].totals`).

The PDF text is read with the uncompressed-stream reader the other PDF suites use, and the page
count is counted in the same bytes; no PDF parsing dependency is added (research R14).
"""
import re
import sys
import time
import types
from datetime import date
from typing import ClassVar

import pytest

from app.engine import periods
from app.engine import report as engine
from app.reports import pdf
from app.reports.pdf_layout import DEFAULT_MARGINS, page_setup
from tests.test_reports_params import _pdf_lines

PORTRAIT_MEDIABOX = b"/MediaBox [ 0 0 595.2756 841.8898 ]"
LANDSCAPE_MEDIABOX = b"/MediaBox [ 0 0 841.8898 595.2756 ]"
LETTER_MEDIABOX = b"/MediaBox [ 0 0 612 792 ]"
SELECTION = {
    "period": "custom",
    "current": {"from": "2026-09-01", "to": "2026-09-30"},
    "previous": {"from": "2026-08-02", "to": "2026-08-31"},
    "compare": "previous_period",
    "partial": False,
    "grain": "day",
}


def _products(count: int) -> tuple[list[str], list[float]]:
    return [f"P{i:04d}" for i in range(1, count + 1)], [float(i) for i in range(1, count + 1)]


def _payload(rows: int = 3) -> dict:
    products, values = _products(rows)
    return {
        "selection": SELECTION,
        "filters": {"producto": ["P0001"]},
        "freshness": {"updated_at": "2026-10-01T10:00:00+00:00", "data_version": "v1-r1"},
        "views": [
            {"id": "resumen", "type": "kpis", "items": [
                {"metric": "ventas", "label": "Ventas netas", "format": "currency",
                 "value": 12480.0, "previous": 11000.0, "change": {"pct": 13.5}},
                {"metric": "pedidos", "label": "Pedidos", "format": "integer", "value": 320,
                 "previous": 300, "change": {"pct": 6.7}}],
             "summary": "Resumen de indicadores.",
             "summary_en": "Summary of indicators."},
            {"id": "diaria", "type": "trend", "metric": "ventas", "label": "Ventas netas",
             "format": "currency", "grain": "day",
             "points": [{"bucket": "2026-09-01", "value": 5.0},
                        {"bucket": "2026-09-02", "value": 6.75}],
             "summary": "Serie diaria de ventas.",
             "summary_en": "Daily sales series."},
            {"id": "producto", "type": "ranking", "metric": "ventas", "dimension": "producto",
             "title": "Ventas netas por Producto", "label": "Ventas netas",
             "dimension_label": "Producto", "format": "currency",
             "items": [{"key": "ERP", "value": 8000.0, "share": 64.1, "change": None},
                       {"key": "CRM", "value": 4480.0, "share": 35.9, "change": None}],
             "summary": "Ranking por producto.",
             "summary_en": "Ranking by product."},
            {"id": "detalle", "type": "table", "title": None,
             "columns": [{"id": "producto", "label": "Producto", "kind": "dimension"},
                         {"id": "ventas", "label": "Ventas netas", "kind": "metric",
                          "format": "currency"}],
             "rows": [{"producto": p, "ventas": v} for p, v in zip(products, values,
                                                                   strict=True)],
             "summary": "Detalle por producto.",
             "summary_en": "Details by product.",
             "totals": {"ventas": 12480.0}},
        ],
    }


def _definition(blocks: list[dict], **pdf_layout) -> dict:
    return {
        "title": "Ventas",
        "description": "Resumen de ventas",
        "currency": "USD",
        "date": "lines.local_date",
        "uses": {"lines": "ventas-prueba.sale_lines"},
        "dimensions": {"producto": {"label": "Producto", "sql": "lines.product_code"}},
        "metrics": {"ventas": {"label": "Ventas netas", "format": "currency",
                               "sql": "sum(lines.net_amount)"},
                    "pedidos": {"label": "Pedidos", "format": "integer",
                                "sql": "count(distinct lines.document_id)"}},
        "views": [{"id": "resumen", "type": "kpis", "metrics": ["ventas", "pedidos"]},
                  {"id": "diaria", "type": "trend", "metric": "ventas", "grain": "auto"},
                  {"id": "producto", "type": "ranking", "dimension": "producto",
                   "metric": "ventas"},
                  {"id": "detalle", "type": "table", "dimensions": ["producto"],
                   "metrics": ["ventas"]}],
        "layout": {"pdf": {**pdf_layout, "blocks": blocks}},
    }


def _render(blocks: list[dict], payload: dict | None = None, *, legacy: dict | None = None,
            definition: dict | None = None, **pdf_layout) -> bytes:
    """A report with a layout; `legacy` plays the role of the ignored `pdf` config (R2)."""
    definition = definition if definition is not None else _definition(blocks, **pdf_layout)
    if legacy is not None:
        definition["pdf_layout"] = legacy
    return pdf.render(definition, payload or _payload(), organization="Acme", product="Bizview",
                      viewer="Ana", layout=legacy)


def _index(lines: list[str], text: str) -> int:
    return next(i for i, line in enumerate(lines) if text in line)


def _pages(content: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", content))


def _header_block() -> dict:
    return {"id": "cabecera", "type": "header", "title": True, "subtitle": True, "period": True,
            "logo": True, "logo_role": "brand"}


def _table_block(rows: int, **extra) -> dict:
    return {"id": "producto_tabla", "type": "table", "view": "detalle", "title": "Detalle",
            "columns": ["producto", "ventas"], "widths": [3, 1], "totals": True, **extra}


def test_blocks_render_in_declared_order():
    blocks = [_header_block(),
              {"id": "nota", "type": "text", "text": "Nota del autor"},
              {"id": "kpis", "type": "kpi_row", "view": "resumen",
               "items": ["ventas", "pedidos"], "delta": True},
              {"id": "grafico", "type": "chart", "view": "diaria", "kind": "line",
               "x": "fecha", "series": ["ventas"], "height_mm": 60},
              _table_block(3),
              {"id": "pie", "type": "footer", "generated_at": False, "page_numbers": False,
               "legal": "Documento de prueba"}]
    lines = _pdf_lines(_render(blocks))
    order = [_index(lines, "Resumen de ventas"), _index(lines, "Nota del autor"),
             _index(lines, "Ventas netas"), _index(lines, "Descripción: Serie diaria de ventas."),
             _index(lines, "Detalle"), _index(lines, "Documento de prueba")]
    assert order == sorted(order), order
    assert "Vista previa" not in lines


def test_one_page_layout_produces_exactly_one_page():
    blocks = [_header_block(),
              {"id": "kpis", "type": "kpi_row", "view": "resumen", "items": ["ventas"]},
              {"id": "grafico", "type": "chart", "view": "diaria", "kind": "line"},
              _table_block(3),
              {"id": "pie", "type": "footer", "generated_at": False, "legal": "Legal"}]
    content = _render(blocks)
    assert _pages(content) == 1


def test_table_truncate_ends_with_the_more_rows_line():
    content = _render([_header_block(), _table_block(200, overflow="truncate"),
                       {"id": "pie", "type": "footer", "generated_at": False, "legal": "Legal"}],
                      payload=_payload(200))
    lines = _pdf_lines(content)
    drawn = [line for line in lines if re.fullmatch(r"P\d{4}", line)]
    more = [line for line in lines if re.fullmatch(r"y \d+ filas más", line)]
    assert len(more) == 1, lines[-5:]
    omitted = int(re.search(r"\d+", more[0]).group())
    assert omitted == 200 - len(drawn)
    assert omitted > 0
    assert "Total" in lines and "12.480,00 USD" in lines
    assert _pages(content) == 1 and "Legal" in lines      # it stops at the page boundary


def test_table_continue_repeats_the_header_on_the_next_page():
    content = _render([_header_block(), _table_block(200, overflow="continue")],
                      payload=_payload(200))
    lines = _pdf_lines(content)
    assert _pages(content) > 1
    assert not [line for line in lines if re.fullmatch(r"y \d+ filas más", line)]
    assert sum(1 for line in lines if line == "Producto") >= 2


def test_unknown_block_type_is_not_rendered_and_does_not_crash():
    blocks = [_header_block(),
              {"id": "raro", "type": "mapa", "view": "diaria", "text": "No debe salir"},
              {"id": "mapa2", "type": "chart3d", "view": "diaria"},
              {"id": "pie", "type": "footer", "generated_at": False, "legal": "Documento"}]
    lines = _pdf_lines(_render(blocks))
    assert "No debe salir" not in lines
    assert "Documento" in lines
    assert _pages(_render(blocks)) == 1


def test_large_table_renders_under_the_budget():
    blocks = [_header_block(),
              {"id": "kpis", "type": "kpi_row", "view": "resumen", "items": ["ventas", "pedidos"]},
              _table_block(500, overflow="continue"),
              {"id": "pie", "type": "footer", "generated_at": False, "page_numbers": True}]
    started = time.monotonic()
    content = _render(blocks, payload=_payload(500))
    elapsed = time.monotonic() - started
    print(f"\n500-row declarative PDF: {elapsed:.2f} s, {len(content)} bytes")
    assert elapsed < 10


def test_landscape_from_the_layout_wins_over_the_legacy_orientation():
    content = _render([_header_block(), _table_block(3)],
                      legacy={"orientation": "portrait", "views": [0]},
                      page={"orientation": "landscape"})
    assert LANDSCAPE_MEDIABOX in content
    assert PORTRAIT_MEDIABOX not in content


def test_named_page_size_and_margins_are_honoured():
    size, margins = page_setup({"pdf": {"page": {"size": "letter",
                                                "margins": {"top": 5, "bottom": 40}}}})
    assert margins == {"top": 5.0, "right": 10.0, "bottom": 40.0, "left": 10.0}
    assert (size[0], size[1]) == (612, 792)
    assert page_setup({"pdf": {}})[1] == DEFAULT_MARGINS
    _, clamped = page_setup({"pdf": {"page": {"margins": {"left": 1, "right": 99}}}})
    assert clamped["left"] == 5.0 and clamped["right"] == 40.0      # 5 to 40 mm are the bounds
    content = _render([_header_block(), _table_block(3)], page={"size": "letter"})
    assert LETTER_MEDIABOX in content


def test_without_a_layout_the_legacy_pdf_config_still_applies():
    definition = _definition([_header_block()])
    del definition["layout"]
    definition["pdf_layout"] = {"orientation": "landscape", "views": [1]}
    content = pdf.render(definition, _payload(), organization="Acme", product="Bizview")
    lines = _pdf_lines(content)
    assert LANDSCAPE_MEDIABOX in content
    assert "Tendencia: Ventas netas" in lines
    assert "Resumen" not in lines


def test_text_block_markdown_and_alignment():
    lines = _pdf_lines(_render([{"id": "nota", "type": "text", "align": "center",
                                "text": "**Negrita** y *cursiva* con [enlace](https://acme.test)"}]))
    line = next(line for line in lines if "Negrita" in line)
    assert "**" not in line and "*cursiva*" not in line
    assert "Negrita y cursiva con enlace" in line


def test_chart_caption_is_the_engine_summary():
    captions = [line for line in _pdf_lines(_render([{"id": "grafico", "type": "chart",
                                                     "view": "producto", "kind": "pie",
                                                     "top_n": 6}]))
                if line.startswith("Descripción: ")]
    assert captions == ["Descripción: Ranking por producto."]


def test_pie_keeps_top_n_and_groups_the_rest():
    payload = _payload()
    payload["views"][2]["items"] = [{"key": f"P{i}", "value": float(10 - i), "share": 10.0}
                                    for i in range(4)]
    lines = _pdf_lines(_render([{"id": "grafico", "type": "chart", "view": "producto",
                                 "kind": "pie", "top_n": 2}], payload=payload))
    assert any("otros" in line for line in lines), lines
    assert any(line.startswith("P0 ") for line in lines)


# --- engine facts the renderer reads (data-model §7, contracts/renderer-api.md §1) ---------------

class _Version:
    id = 7
    checksum = "c26"
    artifacts: ClassVar[dict] = {"workspace": {"currency": "USD"}}


def _context(definition: dict) -> engine.Context:
    """A report bound to a version: the derived facts need no database and no integration."""
    return engine.Context("ventas", definition, _Version(),
                          {"lines": ("public", "sale_lines")},
                          {"lines": {"local_date": {"type": "date"},
                                     "net_amount": {"type": "numeric"},
                                     "document_id": {"type": "text"},
                                     "product_code": {"type": "text"}}},
                          [])


def _selection() -> periods.Selection:
    return periods.Selection("custom", periods.Range(date(2026, 9, 1), date(2026, 9, 30)),
                             "none", None, False, "day")


def _empty_views() -> list[dict]:
    return [{"type": "kpis", "items": [{"metric": "ventas", "label": "Ventas netas",
                                        "format": "currency", "value": 5.0}]},
            {"type": "trend", "metric": "ventas", "label": "Ventas netas",
             "format": "currency", "grain": "day",
             "points": [{"bucket": "2026-09-02", "value": 5.0}]},
            {"type": "ranking", "metric": "ventas", "label": "Ventas netas",
             "dimension": "producto", "dimension_label": "Producto", "format": "currency",
             "items": [{"key": "P1", "value": 5.0, "share": 100.0}]},
            {"type": "table", "title": None, "columns": [], "rows": []}]


def test_definition_json_carries_the_layout_and_its_warnings(monkeypatch):
    definition = _definition([_header_block(), _table_block(3)])
    out = engine.definition_json(_context(definition))
    assert out["layout"] == definition["layout"]
    assert out["layout_problems"] == []         # the checker ships with the CLI package

    from bizview_cli.validate import Issue
    checker = types.ModuleType("bizview_cli.report_layout")
    checker.check_layout = lambda definition, *, file, entry="report": [
        Issue(entry, "layout_color_literal", "color", level="error", file=file,
              path="/layout/web"),
        Issue(entry, "layout_chart_unsuitable", "unsuitable chart", level="warning", file=file,
              path="/layout/web/components/1/x", expected={"type": "string"})]
    monkeypatch.setitem(sys.modules, "bizview_cli.report_layout", checker)
    problems = engine.definition_json(_context(definition))["layout_problems"]
    assert problems == [{"level": "warning", "code": "layout_chart_unsuitable",
                         "path": "/layout/web/components/1/x", "message": "unsuitable chart",
                         "expected": {"type": "string"}}]


def test_definition_json_without_a_layout_keeps_its_shape(monkeypatch):
    definition = _definition([_header_block()])
    del definition["layout"]
    monkeypatch.setitem(sys.modules, "bizview_cli.report_layout", None)
    out = engine.definition_json(_context(definition))
    assert "layout" not in out and "layout_problems" not in out
    assert out["pdf_layout"] == {"orientation": "portrait", "views": None}


def test_view_facts_add_the_summary_always_and_totals_only_when_asked(monkeypatch):
    calls: list[list[str]] = []

    def fake_aggregate(ctx, metric_ids, r, filters, tz, *, group=None, order_metric=None,
                       limit=None, keys=None, session=None):
        """La firma real de `aggregate`: estos hechos derivados no consultan ninguna base."""
        calls.append(list(metric_ids))
        return [{m: 2.0 for m in metric_ids}]

    monkeypatch.setattr(engine, "aggregate", fake_aggregate)
    definition = _definition([_table_block(3)])          # the table block declares totals: true
    views = _empty_views()
    engine._view_facts(_context(definition), definition["views"], views, _selection(), {}, "UTC")
    assert calls == [["ventas"]]                         # los totales salen de `aggregate`
    for view in views[:3]:
        assert view["summary"] and view["summary_en"]
        assert "totals" not in view
    assert views[3]["summary"].startswith("Sin datos")   # the table view has no rows
    assert views[3]["totals"] == {"ventas": 2.0}         # the engine's aggregation, not row sums

    without = _definition([_table_block(3)])
    without["layout"]["pdf"]["blocks"][0]["totals"] = False
    views = _empty_views()
    engine._view_facts(_context(without), without["views"], views, _selection(), {}, "UTC")
    assert calls == [["ventas"]]                         # sin totals no hay segunda agregación
    assert "totals" not in views[3]


def test_view_summaries_are_localised_sentences():
    definition = _definition([_header_block()])
    ctx = _context(definition)
    views = _empty_views()
    engine._view_facts(ctx, definition["views"], views, _selection(), {}, "UTC")
    assert views[0]["summary"] == ("Indicadores del 1 al 30 de septiembre de 2026: "
                                   "Ventas netas 5,00 USD.")
    assert views[1]["summary"] == ("Ventas netas por día del 1 al 30 de septiembre de 2026; "
                                   "máximo 5,00 USD el 2.")
    assert views[2]["summary"] == ("Ventas netas por Producto del 1 al 30 de septiembre de 2026: "
                                   "P1 encabeza con 5,00 USD (100,0 % del total).")
    assert views[1]["summary_en"] == ("Ventas netas by day from September 1 to 30, 2026; "
                                      "highest 5.00 USD on 2.")


@pytest.mark.parametrize("locale", ["es", "en"])
def test_view_id_travels_when_the_definition_declares_one(monkeypatch, locale):
    def fake_aggregate(ctx, metric_ids, r, filters, tz, *, group=None, order_metric=None,
                       limit=None, keys=None, session=None):
        """La firma real de `aggregate`: el identificador de la vista no necesita base."""
        names = [name for name, _ in group or []]
        if names == ["bucket"]:
            return [{"bucket": date(2026, 9, 2), **{m: 5.0 for m in metric_ids}}]
        if names == ["key"]:
            return [{"key": "P1", **{m: 5.0 for m in metric_ids}}]
        return [{m: 5.0 for m in metric_ids}]

    monkeypatch.setattr(engine, "aggregate", fake_aggregate)
    definition = _definition([_header_block()])
    for view, vid in zip(definition["views"], ("resumen", "diaria", "producto", "detalle"),
                         strict=True):
        view["id"] = vid
    views = [engine.VIEWS[v["type"]](_context(definition), v, _selection(), {}, "UTC")
             for v in definition["views"][:3]]
    with __import__("app.i18n", fromlist=["use_locale"]).use_locale(locale):
        assert [v["id"] for v in views] == ["resumen", "diaria", "producto"]
