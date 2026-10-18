"""Feature 026 SC-002: the dashboard payload and the PDF show the same figures for one query.

The payload comes from the real route (the engine over the fixture workspace) and the PDF is
rendered from that same payload, so a figure that disagrees between the two outputs fails here.
Each view also carries the engine-generated `summary` — the web `aria-label` and the PDF chart
caption — and the sentence is asserted in the PDF text, not just in the payload.
"""
import re

from app.reports import pdf
from tests.test_reports_params import _pdf_lines
from tests.test_runner import origin as origin
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import SELECTION
from tests.test_vibe_reporting import applied as applied
from tests.test_vibe_reporting import workspace as workspace

VIEW_IDS = ("resumen", "diaria", "producto")


def _named(definition: dict) -> dict:
    """The view ids the layout binds to, declared by the schema (`id` is optional)."""
    for view, vid in zip(definition["views"], VIEW_IDS, strict=False):
        view.setdefault("id", vid)
    return definition


def _text(content: bytes) -> str:
    """The PDF text as one line: a wrapped sentence is still the same sentence."""
    return re.sub(r"\s+", " ", " ".join(_pdf_lines(content)))


def _figures(payload: dict, currency: str) -> list[str]:
    """Every figure of the payload as both renderers write it (engine formats, one helper)."""
    out = []
    for view in payload["views"]:
        if view["type"] == "kpis":
            out += [pdf.fmt(i["value"], i["format"], currency) for i in view["items"]]
        elif view["type"] == "trend":
            out += [pdf.fmt(p["value"], view["format"], currency) for p in view["points"]]
        elif view["type"] == "ranking":
            out += [pdf.fmt(i["value"], view["format"], currency) for i in view["items"]]
        elif view["type"] == "table":
            out += [pdf.fmt(r.get(c["id"]), c.get("format", "number"), currency)
                    for r in view["rows"] for c in view["columns"] if c["kind"] == "metric"]
    return [figure for figure in out if figure != "—"]


def _layout() -> dict:
    """One composition: the figures of every view and, above each one, its caption sentence."""
    return {"pdf": {"blocks": [
        {"id": "cabecera", "type": "header", "title": True, "subtitle": True, "period": True},
        {"id": "resumen", "type": "kpi_row", "view": "resumen",
         "items": ["net_sales", "orders", "avg_ticket"]},
        {"id": "resumen_caption", "type": "chart", "view": "resumen", "kind": "bar"},
        {"id": "diaria_caption", "type": "chart", "view": "diaria", "kind": "line",
         "series": ["net_sales"]},
        {"id": "diaria", "type": "table", "view": "diaria", "columns": ["day", "net_sales"],
         "widths": [1, 1]},
        {"id": "producto_caption", "type": "chart", "view": "producto", "kind": "pie"},
        {"id": "producto", "type": "table", "view": "producto",
         "columns": ["product", "net_sales"], "widths": [3, 1]},
        {"id": "pie", "type": "footer", "generated_at": False, "legal": "Documento de prueba"},
    ]}}


def test_payload_and_pdf_agree_on_every_figure(applied):
    payload = applied.get(f"/api/reports/ventas/data?{SELECTION}").json()
    definition = _named(applied.get("/api/reports/ventas").json())
    definition["layout"] = _layout()

    text = _text(pdf.render(definition, payload, organization="Acme", product="Bizview",
                            viewer="Ana"))
    figures = _figures(payload, definition["currency"])
    assert figures, payload["views"]
    for figure in figures:
        assert figure in text, figure
    for view in payload["views"]:
        assert view["summary"] in text, view["summary"]
        assert view["summary_en"] != view["summary"]      # the sentence travels in both languages
    assert "Documento de prueba" in text

    # The route's own PDF (this report declares no layout) prints the same figures: both outputs
    # read one payload, which is what makes parity structural (research R7).
    route = applied.post(f"/api/reports/ventas/pdf?{SELECTION}")
    assert route.status_code == 200
    fixed = _text(route.content)
    for figure in figures:
        assert figure in fixed, figure
