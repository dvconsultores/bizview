"""Feature 017: PDF layout options (orientation, view order, preview)."""
from app.config import get_settings
from app.reports import pdf
from tests.test_reports_params import _pdf_lines

PORTRAIT_MEDIABOX = b"/MediaBox [ 0 0 595.2756 841.8898 ]"
LANDSCAPE_MEDIABOX = b"/MediaBox [ 0 0 841.8898 595.2756 ]"


def _definition(**pdf_layout) -> dict:
    return {"title": "Ventas", "dimensions": {}, "currency": "USD", **pdf_layout}


def _payload() -> dict:
    return {
        "selection": {
            "period": "mtd",
            "current": {"from": "2026-10-01", "to": "2026-10-02"},
            "previous": None,
            "partial": False,
        },
        "views": [
            {"type": "kpis", "items": [
                {"label": "Ventas netas", "value": 11.75, "format": "currency",
                 "previous": None, "change": None}]},
            {"type": "trend", "label": "Ventas diarias", "format": "currency",
             "points": [{"bucket": "2026-10-01", "value": 5.0},
                        {"bucket": "2026-10-02", "value": 6.75}]},
            {"type": "ranking", "title": "Top productos", "dimension_label": "Producto",
             "label": "Ventas", "format": "currency",
             "items": [{"key": "ERP", "value": 8.0, "share": 68.1, "change": None},
                       {"key": "CRM", "value": 3.75, "share": 31.9, "change": None}]},
        ],
        "filters": {},
        "freshness": {},
    }


def _render(definition=None, payload=None, **kwargs) -> bytes:
    return pdf.render(definition or _definition(), payload or _payload(),
                      organization="Acme", product="Bizview", **kwargs)


def test_default_renders_all_views_portrait():
    content = _render()
    lines = _pdf_lines(content)
    assert PORTRAIT_MEDIABOX in content
    assert "Resumen" in lines
    assert "Tendencia: Ventas diarias" in lines
    assert "Top productos" in lines


def test_landscape_orientation_from_definition():
    content = _render(_definition(pdf_layout={"orientation": "landscape"}))
    assert LANDSCAPE_MEDIABOX in content
    assert PORTRAIT_MEDIABOX not in content


def test_views_order_and_omission():
    definition = _definition(pdf_layout={"views": [2, 0]})
    lines = _pdf_lines(_render(definition))
    assert "Top productos" in lines
    assert "Resumen" in lines
    assert "Tendencia: Ventas diarias" not in lines
    assert lines.index("Top productos") < lines.index("Resumen")


def test_invalid_layout_views_ignored():
    definition = _definition(pdf_layout={"views": [5, "x", True, 0, 0]})
    lines = _pdf_lines(_render(definition))
    assert lines.count("Resumen") == 1
    assert "Tendencia: Ventas diarias" not in lines
    assert "Top productos" not in lines


def test_preview_title_and_label():
    content = _render(preview=True)
    lines = _pdf_lines(content)
    assert "Vista previa" in lines
    assert b"/Title (Ventas \\(Vista previa\\))" in content


def test_no_preview_has_no_label_or_preview_title():
    content = _render(preview=False)
    lines = _pdf_lines(content)
    assert "Vista previa" not in lines
    assert b"/Title (Ventas)" in content
    assert b"/Title (Ventas \\(Vista previa\\))" not in content


def test_layout_kwarg_overrides_definition():
    definition = _definition(pdf_layout={"orientation": "landscape", "views": [1]})
    content = _render(definition, layout={"orientation": "portrait", "views": [2]})
    lines = _pdf_lines(content)
    assert PORTRAIT_MEDIABOX in content
    assert "Top productos" in lines
    assert "Tendencia: Ventas diarias" not in lines


def test_direct_freshness_live_line(monkeypatch):
    monkeypatch.setattr(get_settings(), "timezone", "America/Caracas")
    payload = _payload()
    payload["freshness"] = {
        "updated_at": "2026-10-08T12:34:56.123456+00:00",
        "data_version": "v12-d123",
        "mode": "direct",
        "source": "BI de esta instalación",
        "queried_at": "2026-10-08T15:04:00+00:00",
        "stale": False,
    }
    lines = _pdf_lines(_render(payload=payload))
    assert "Datos en vivo · BI de esta instalación · consultado 08/10/2026 11:04" in lines


def test_direct_freshness_stale_line(monkeypatch):
    monkeypatch.setattr(get_settings(), "timezone", "America/Caracas")
    payload = _payload()
    payload["freshness"] = {
        "updated_at": "2026-10-08T12:34:56.123456+00:00",
        "data_version": "v12-d123",
        "mode": "direct",
        "source": "BI de esta instalación",
        "queried_at": "2026-10-08T15:04:00+00:00",
        "stale": True,
        "stale_reason": "timeout",
    }
    lines = _pdf_lines(_render(payload=payload))
    assert "Datos de 08/10/2026 11:04; la fuente no respondió" in lines
    assert "Datos en vivo" not in lines


def test_dataset_freshness_unchanged():
    payload = _payload()
    payload["freshness"] = {"updated_at": "2026-10-08T15:04:00+00:00", "data_version": "x"}
    lines = _pdf_lines(_render(payload=payload))
    assert "Datos actualizados: 08 oct 2026 15:04" in lines


def test_direct_source_label_escaped(monkeypatch):
    monkeypatch.setattr(get_settings(), "timezone", "America/Caracas")
    payload = _payload()
    payload["freshness"] = {
        "updated_at": "2026-10-08T12:34:56.123456+00:00",
        "data_version": "v12-d123",
        "mode": "direct",
        "source": "<b>&",
        "queried_at": "2026-10-08T15:04:00+00:00",
        "stale": False,
    }
    lines = _pdf_lines(_render(payload=payload))
    assert any("<b>&" in line for line in lines)
    assert any("Datos en vivo" in line for line in lines)


def test_english_pdf_has_no_spanish_fixed_text():
    lines = "\n".join(_pdf_lines(_render(locale="en")))
    assert "Period:" in lines
    assert "Summary" in lines
    assert "11.75 USD" in lines
    for text in ["Período", "Resumen", "Comparado con", "Tendencia", "Desde",
                 "Indicador", "del total"]:
        assert text not in lines


def test_spanish_pdf_unchanged_by_default():
    lines = "\n".join(_pdf_lines(_render()))
    assert "Período: Mes en curso" in lines
    assert "11,75 USD" in lines


def test_english_labels_from_en_fields():
    definition = _definition()
    definition["title_en"] = "Sales"
    lines = _pdf_lines(_render(definition=definition, locale="en"))
    assert "Sales" in [line.strip() for line in lines]
