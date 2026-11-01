"""Feature 030 follow-up (owner, 2026-10-23): a legacy `pdf:` report (no declarative layout)
answers every view shape the engine can produce, instead of failing with «Ocurrió un error
inesperado (referencia …)».

Feature 045 removed the draft preview, so the two assertions that pinned the preview *route* — the
watermark and the `preview_pdf_failed` wrapper — went with it; what is left is the rendering, which
is what a published report and a share link still use.

No database: `render` is a pure function over a definition and a payload.
"""
import pytest

from app.reports import pdf

DASH = "\u2013"


def _definition() -> dict:
    """`artemisa/reports/ventas-facturacion/report.yaml` as `definition_json` normalizes it."""
    return {
        "id": "ventas-facturacion",
        "title": "Ventas y facturación",
        "description": "Ingresos facturados y proporción de facturas pagadas.",
        "icon": "chart",
        "currency": "USD",
        "metrics": {
            "total_facturado": {"label": "Total facturado", "format": "currency",
                                "better": "higher"},
            "numero_facturas": {"label": "Número de facturas", "format": "integer",
                                "better": "higher"},
        },
        "dimensions": {"anio": {"label": "Año"}, "mes": {"label": "Mes"},
                       "estatus": {"label": "Estatus"}},
        "periods": {"default": "mtd", "allowed": ["mtd", "last_month", "ytd", "last_12_months"]},
        "compare": {"default": "previous_period",
                    "allowed": ["none", "previous_period", "previous_year"]},
        "views": [{"id": "resumen", "type": "kpis"},
                  {"id": "tendencia_diaria", "type": "trend"},
                  {"id": "por_estatus", "type": "ranking"},
                  {"id": "detalle_periodo", "type": "table"}],
        "filters": ["anio", "mes", "estatus"],
        "pdf": True,
        "pdf_layout": {"orientation": "landscape", "views": [0, 1, 2, 3]},
        "ai_narrative": False,
    }


def _payload(*, compare: bool = True, points: list | None = None,
             values: float | None = 1234.5) -> dict:
    points = points if points is not None else [
        {"bucket": "2026-10-01", "value": 10.0, "previous": 8.0},
        {"bucket": "2026-10-02", "value": 14.75, "previous": 9.0},
    ]
    previous = {"from": "2026-09-01", "to": "2026-09-30"} if compare else None
    return {
        "selection": {
            "current": {"from": "2026-10-01", "to": "2026-10-24"},
            "previous": previous,
            "period": "mtd",
            "compare": "previous_period" if compare else "none",
            "filters": {},
        },
        "filters": {},
        "freshness": {"updated_at": "2026-10-24T12:00:00Z", "data_version": "preview"},
        "views": [
            {"type": "kpis", "id": "resumen", "items": [
                {"metric": "total_facturado", "label": "Total facturado", "value": values,
                 "previous": 1000.0 if compare else None, "format": "currency",
                 "better": "higher",
                 "change": {"pct": 23.4, "new": False} if compare else None},
            ]},
            {"type": "trend", "id": "tendencia_diaria", "metric": "total_facturado",
             "label": "Total facturado", "format": "currency", "grain": "day",
             "points": points},
            {"type": "ranking", "id": "por_estatus", "metric": "total_facturado",
             "dimension": "estatus", "title": "Facturación por estatus",
             "label": "Total facturado", "dimension_label": "Estatus", "format": "currency",
             "items": [{"key": "paid", "value": 800.0, "share": 64.8,
                        "previous": 700.0 if compare else None,
                        "change": {"pct": 14.3, "new": False} if compare else None}]},
            {"type": "table", "id": "detalle_periodo",
             "title": "Detalle por año, mes y estatus",
             "columns": [{"id": "anio", "label": "Año", "kind": "dimension"},
                         {"id": "mes", "label": "Mes", "kind": "dimension"},
                         {"id": "estatus", "label": "Estatus", "kind": "dimension"},
                         {"id": "total_facturado", "label": "Total facturado",
                          "kind": "metric", "format": "currency"}],
             "rows": [{"anio": "2026", "mes": "2026-10-01T00:00:00", "estatus": "paid",
                       "total_facturado": 800.0}]},
        ],
    }


def _render(payload: dict) -> bytes:
    return pdf.render(_definition(), payload, organization="Cliente Demo", product="Bizview",
                      viewer="Superusuario")


@pytest.mark.parametrize("case", [
    {"compare": True},
    {"compare": False},
    {"compare": True, "points": []},
    {"compare": True, "points": [{"bucket": "2026-10-01", "value": None, "previous": None}]},
    {"compare": True, "points": [{"bucket": "2026-10-01", "value": 5.0, "previous": 4.0}]},
    {"compare": True, "values": None},
])
def test_a_legacy_report_renders_every_shape(case):
    """A published report must never 500 on a view shape it can render."""
    content = _render(_payload(**case))
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_the_report_never_renders_a_view_outside_its_declared_order():
    content = _render(_payload())
    # `pdf_layout.views: [0, 1, 2, 3]` → the ranking title is in the story; a view past the end is
    # skipped rather than raising (a draft can declare more views than the PDF lists).
    assert b"%PDF" in content
