"""Feature 044 US2: the four visual PDF blocks and the images they embed.

The figures are read from the uncompressed PDF with the same reader the other layout suites use,
so a screen/PDF mismatch fails here (SC-001); the palette suite walks every preset and both
themes so a band or a segment can never carry a literal colour (SC-004).
"""
import base64
import io

import pytest

from app.reports import palette, pdf
from tests.test_reports_params import _pdf_lines

SELECTION = {
    "period": "custom",
    "current": {"from": "2026-09-01", "to": "2026-09-30"},
    "previous": None,
    "compare": "none",
    "partial": False,
    "grain": "day",
}



def _png() -> bytes:
    """A real 8x8 PNG: ReportLab reads it with PIL, so a hand-made header would fail."""
    from PIL import Image as Pillow

    buffer = io.BytesIO()
    Pillow.new("RGB", (8, 8), (200, 30, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


LOGO = "data:image/png;base64," + base64.b64encode(_png()).decode("ascii")


def _payload(logo: str | None = LOGO) -> dict:
    rows = [
        {"symbol": "BTC", "name": "Bitcoin", "price": 96420.5, "change": 2.4},
        {"symbol": "ETH", "name": "Ether", "price": 3120.75, "change": -1.8},
        {"symbol": "SOL", "name": "Solana", "price": 148.2, "change": 5.1},
    ]
    for row, source in zip(rows, (logo, "coins/ETH.png", logo), strict=False):
        row["logo"] = source
    return {
        "selection": SELECTION,
        "filters": {},
        "freshness": {"updated_at": "2026-10-01T10:00:00+00:00", "data_version": "v1-r1"},
        "views": [
            {"id": "resumen", "type": "kpis", "items": [
                {"metric": "miedo", "label": "Miedo y codicia", "format": "number",
                 "value": 42},
                {"metric": "btc", "label": "Dominancia BTC", "format": "percent",
                 "value": 58.3},
                {"metric": "eth", "label": "Dominancia ETH", "format": "percent",
                 "value": 12.4}]},
            {"id": "monedas", "type": "table",
             "columns": [{"id": "symbol", "label": "Símbolo", "kind": "dimension"},
                         {"id": "name", "label": "Nombre", "kind": "dimension"},
                         {"id": "price", "label": "Precio", "kind": "metric"},
                         {"id": "change", "label": "Cambio", "kind": "metric"}],
             "rows": rows,
             "summary": "Fichas de monedas."},
        ],
    }


def _definition(blocks: list[dict]) -> dict:
    return {
        "title": "Cripto",
        "description": "Panorama",
        "currency": "USD",
        "metrics": {"miedo": {"label": "Miedo y codicia", "format": "number", "sql": "1"},
                    "btc": {"label": "Dominancia BTC", "format": "percent", "sql": "1"},
                    "eth": {"label": "Dominancia ETH", "format": "percent", "sql": "1"}},
        "dimensions": {"symbol": {"label": "Símbolo", "sql": "s"},
                       "name": {"label": "Nombre", "sql": "n"}},
        "images": {"coins": {"folder": "assets/coins", "key": "symbol"}},
        "views": [{"id": "resumen", "type": "kpis", "metrics": ["miedo", "btc", "eth"]},
                  {"id": "monedas", "type": "table",
                   "dimensions": ["symbol", "name"], "metrics": ["miedo"]}],
        "layout": {"pdf": {"blocks": blocks}},
    }


def _render(blocks: list[dict], payload: dict | None = None) -> bytes:
    return pdf.render(_definition(blocks), payload or _payload(), organization="Acme",
                      product="Bizview", viewer="Ana", locale="es")


def test_gauge_prints_the_figure_and_its_label():
    lines = _pdf_lines(_render([{"id": "miedo", "type": "gauge", "view": "resumen",
                                 "metric": "miedo", "min": 0, "max": 100}]))
    assert "42" in lines
    assert "Miedo y codicia" in lines


def test_gauge_arc_bands_are_vector_shapes():
    content = _render([{"id": "miedo", "type": "gauge", "view": "resumen",
                        "metric": "miedo"}])
    assert b"/Subtype /Image" not in content        # the arc is drawn, never a raster


def test_index_prints_the_figure_and_both_ends():
    lines = _pdf_lines(_render([{"id": "indice", "type": "index", "view": "resumen",
                                 "metric": "miedo", "low_label": "Bitcoin",
                                 "high_label": "Altcoin"}]))
    assert "42" in lines
    assert "Bitcoin" in lines and "Altcoin" in lines


def test_share_prints_every_segment_and_the_rest():
    lines = _pdf_lines(_render([{"id": "reparto", "type": "share", "view": "resumen",
                                 "items": ["btc", "eth"], "remainder_label": "Otros"}]))
    assert "Dominancia BTC" in lines and "Dominancia ETH" in lines
    assert "Otros" in lines
    assert any("58" in line for line in lines)


def test_asset_tiles_embed_the_raster_and_draw_the_fallback():
    blocks = [{"id": "fichas", "type": "asset", "view": "monedas", "image": "coins",
               "columns": ["logo", "name", "symbol", "price", "change"], "limit": 3}]
    content = _render(blocks)
    lines = _pdf_lines(content)
    assert "Bitcoin" in lines and "Ether" in lines and "Solana" in lines
    assert "Solana" in lines
    assert any("96" in line for line in lines)       # the figure, formatted by the PDF rules
    assert b"/Subtype /Image" in content              # the data URI became an embedded raster
    assert "2,4 %" in lines and "-1,8 %" in lines    # the badge figures, signs included
    assert "\u25b2" not in "".join(lines)            # the arrow is a drawn triangle, not a glyph


def test_asset_without_an_embeddable_logo_draws_the_initial_circle():
    content = _render([{"id": "fichas", "type": "asset", "view": "monedas", "image": "coins",
                        "columns": ["logo", "name", "symbol", "price"]}],
                      payload=_payload(logo=None))
    lines = _pdf_lines(content)
    assert "Bitcoin" in lines
    assert "B" in lines                               # the initial of the fallback circle
    assert b"/Subtype /Image" not in content          # nothing to embed: the circle is vector


def test_a_block_kind_the_renderer_lacks_shows_the_error_card():
    lines = _pdf_lines(_render([{"id": "raro", "type": "mapa", "view": "resumen",
                                 "text": "No debe salir"}]))
    assert "No debe salir" not in lines
    assert any("No se pudo mostrar" in line for line in lines)


@pytest.mark.parametrize("preset", palette.PRESET_IDS)
@pytest.mark.parametrize("theme", palette.THEMES)
def test_every_gauge_band_and_share_segment_resolves_in_every_preset(preset, theme):
    data = palette.load_preset(preset)
    values = data[theme] if theme in data else data
    for role in (*__import__("app.reports.pdf_layout", fromlist=["GAUGE_ROLES"]).GAUGE_ROLES,
                 *__import__("app.reports.pdf_layout", fromlist=["SHARE_ROLES"]).SHARE_ROLES):
        assert role in values, f"{preset}/{theme} lacks {role}"
