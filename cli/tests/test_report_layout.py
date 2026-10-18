"""Layout declarativo: referencias, límites y avisos (feature 026, US4)."""
from pathlib import Path

import pytest
import yaml

from bizview_cli import authoring, report_layout, validate
from bizview_cli.report_layout import check_layout
from tests.conftest import write

REPORT = "reports/resumen/report.yaml"
VIEW_IDS = {"kpis": "resumen", "trend": "diaria", "ranking": "productos"}


def _issue(result, code, path):
    """El problema con ese código y puntero; acepta un Result o una lista de problemas."""
    issues = result if isinstance(result, list) else result.issues
    matches = [i for i in issues if i.code == code and i.path == path]
    assert matches, f"ningún issue {code} en {path}: {issues}"
    return matches[0]


def _layout_issues(ws: Path) -> list:
    """Los problemas que ve `check_layout` sobre el informe del workspace."""
    definition = yaml.safe_load((ws / REPORT).read_text(encoding="utf-8"))
    return check_layout(definition, file=REPORT)


def _dump(ws: Path, data: dict) -> None:
    write(ws, REPORT, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _edit_report(ws: Path, **changes) -> dict:
    """Reescribe report.yaml con los cambios de primer nivel indicados."""
    data = yaml.safe_load((ws / REPORT).read_text(encoding="utf-8"))
    data.update(changes)
    _dump(ws, data)
    return data


def _with_view_ids(ws: Path, *, table: bool = False) -> None:
    """Pone id a las vistas del workspace de prueba (el layout enlaza solo por id)."""
    data = yaml.safe_load((ws / REPORT).read_text(encoding="utf-8"))
    views = [{"id": VIEW_IDS[view["type"]], **view} for view in data["views"]]
    if table:
        views.append({"id": "detalle", "type": "table", "dimensions": ["product"],
                      "metrics": ["net_sales"], "limit": 100})
    data["views"] = views
    _dump(ws, data)


def _web(*components: dict, gutter: str | None = None) -> dict:
    web: dict = {"components": list(components)}
    if gutter is not None:
        web["gutter"] = gutter
    return {"web": web}


def _kpi(**over) -> dict:
    return {"id": "grafico", "type": "kpi", "view": "resumen", "metric": "net_sales", **over}


# ------------------------------------------------------------------- goldens


@pytest.mark.parametrize("name,source,rel", [
    ("golden", "origen_ventas", "reports/facturas-dia/report.yaml"),
    ("golden-direct", "bi", "reports/ventas-directo/report.yaml"),
])
def test_golden_layouts_are_valid_without_warnings(name, source, rel) -> None:
    root = Path(str(authoring.golden_root(name)))
    result = validate.validate(root, known_sources={source})
    assert result.issues == []
    assert result.ok is True

    report = yaml.safe_load((root / "projects" / "ejemplo" / rel).read_text(encoding="utf-8"))
    layout = report["layout"]
    ids = {view["id"] for view in report["views"]}
    refs = {c["view"] for c in layout.get("web", {}).get("components", []) if "view" in c}
    refs |= {b["view"] for b in layout.get("pdf", {}).get("blocks", []) if "view" in b}
    assert refs and refs <= ids


def test_golden_layout_binds_every_component_type() -> None:
    files = authoring.golden_files(authoring.GOLDEN["example"])
    report = yaml.safe_load(files["reports/facturas-dia/report.yaml"])
    components = report["layout"]["web"]["components"]
    assert [c["type"] for c in components] == ["kpi", "line", "bar", "table", "text"]
    assert {c["view"] for c in components if "view" in c} == {
        "resumen", "diaria", "estados", "detalle"}
    assert [c["span"] for c in components] == [12, 8, 4, 12, 12]


# ------------------------------------------------------------------- layout válido


def test_valid_layout_has_no_issues(ws) -> None:
    _with_view_ids(ws)
    components = [
        _kpi(span=12, delta="previous_period"),
        {"id": "linea", "type": "line", "view": "diaria", "x": "day", "series": ["net_sales"],
         "span": 8, "colors": ["series1"]},
        {"id": "ranking", "type": "bar", "view": "productos", "x": "product",
         "series": ["net_sales"], "span": 4, "colors": "primary"},
        {"id": "filtros", "type": "filters", "only": ["product"]},
        {"id": "nota", "type": "text", "text": "Datos del mes en curso.", "style": "caption"},
    ]
    _edit_report(ws, layout=_web(*components, gutter="md"))
    result = validate.validate(ws)
    assert result.issues == []
    assert result.ok is True


# ------------------------------------------------------------------- referencias


def test_view_reference_missing(ws) -> None:
    _with_view_ids(ws)
    _edit_report(ws, layout=_web(_kpi(view="fantasma")))
    result = validate.validate(ws)
    assert result.ok is False
    issue = _issue(result, "layout_view_missing", "/layout/web/components/0/view")
    assert issue.file == REPORT
    assert issue.level == "error"
    assert "components[0] 'grafico'" in issue.message
    assert "fantasma" in issue.message
    assert "resumen" in (issue.fix or "")


def test_view_without_id_cannot_be_referenced(ws) -> None:
    """Sin `id` en la vista el layout no puede enlazarla: el problema lo dice."""
    for value in ("resumen", "kpis"):
        _edit_report(ws, layout=_web(_kpi(view=value)))
        result = validate.validate(ws)
        assert result.ok is False
        issue = _issue(result, "layout_view_missing", "/layout/web/components/0/view")
        assert f"'{value}'" in issue.message
        assert "declara id en la vista" in (issue.fix or "")


def test_metric_missing(ws) -> None:
    _with_view_ids(ws)
    _edit_report(ws, layout=_web(_kpi(metric="fantasma")))
    result = validate.validate(ws)
    assert result.ok is False
    issue = _issue(result, "layout_metric_missing", "/layout/web/components/0/metric")
    assert "no existe la métrica 'fantasma'" in issue.message
    assert "net_sales" in (issue.fix or "")


def test_series_metric_missing(ws) -> None:
    _with_view_ids(ws)
    layout = _web({"id": "linea", "type": "line", "view": "diaria", "x": "day",
                   "series": ["net_sales", "fantasma"]})
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    issue = _issue(result, "layout_metric_missing", "/layout/web/components/0/series/1")
    assert "fantasma" in issue.message


def test_column_missing_in_report(ws) -> None:
    _with_view_ids(ws, table=True)
    layout = _web({"id": "detalle", "type": "table", "view": "detalle",
                   "columns": ["product", "fantasma"]})
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    issue = _issue(result, "layout_column_missing", "/layout/web/components/0/columns/1")
    assert "no existe la métrica ni la dimensión 'fantasma'" in issue.message


def test_column_missing_in_view(ws) -> None:
    """`orders` existe en el informe pero la vista detalle no lo expone."""
    _with_view_ids(ws, table=True)
    layout = _web({"id": "detalle", "type": "table", "view": "detalle",
                   "columns": ["product", "orders"]})
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    issue = _issue(result, "layout_column_missing", "/layout/web/components/0/columns/1")
    assert "la vista 'detalle' no expone la columna 'orders'" in issue.message


def test_filter_missing(ws) -> None:
    _with_view_ids(ws)
    _edit_report(ws, layout=_web({"id": "filtros", "type": "filters", "only": ["moneda"]}))
    result = validate.validate(ws)
    issue = _issue(result, "layout_filter_missing", "/layout/web/components/0/only/0")
    assert "no existe el filtro 'moneda'" in issue.message
    assert "product" in (issue.fix or "")


def test_pdf_block_references(ws) -> None:
    _with_view_ids(ws)
    layout = {"pdf": {"blocks": [
        {"id": "tabla", "type": "table", "view": "fantasma", "columns": ["net_sales"]},
        {"id": "grafico", "type": "chart", "view": "productos", "kind": "pie",
         "category": "product", "value": "fantasma"},
    ]}}
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    view_issue = _issue(result, "layout_view_missing", "/layout/pdf/blocks/0/view")
    assert "blocks[0] 'tabla'" in view_issue.message
    metric_issue = _issue(result, "layout_metric_missing", "/layout/pdf/blocks/1/value")
    assert "fantasma" in metric_issue.message


# ------------------------------------------------------------------- ids y límites


def test_duplicate_component_id(ws) -> None:
    _with_view_ids(ws)
    layout = _web(_kpi(), {"id": "grafico", "type": "line", "view": "diaria", "x": "day",
                           "series": ["net_sales"]})
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    issue = _issue(result, "layout_id_duplicate", "/layout/web/components/1/id")
    assert "el id 'grafico' ya está declarado en components[0]" in issue.message


def test_duplicate_block_id(ws) -> None:
    _with_view_ids(ws)
    layout = {"pdf": {"blocks": [
        {"id": "cabecera", "type": "header", "title": True},
        {"id": "cabecera", "type": "footer", "page_numbers": True},
    ]}}
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    issue = _issue(result, "layout_id_duplicate", "/layout/pdf/blocks/1/id")
    assert "ya está declarado en blocks[0]" in issue.message


def test_widths_must_match_columns(ws) -> None:
    """El esquema no puede contar dos listas: lo comprueba check_layout."""
    _with_view_ids(ws, table=True)
    layout = {"pdf": {"blocks": [{"id": "detalle", "type": "table", "view": "detalle",
                                  "columns": ["product", "net_sales"], "widths": [3]}]}}
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    assert result.ok is False
    issue = _issue(result, "layout_range", "/layout/pdf/blocks/0/widths")
    assert "widths tiene 1 entradas y columns 2" in issue.message


@pytest.mark.parametrize("component,path,substr", [
    ({"span": 13}, "/layout/web/components/0/span", "span = 13 está fuera del rango 1-12"),
    ({"top_n": 1}, "/layout/web/components/0/top_n", "top_n = 1 está fuera del rango 2-12"),
    ({"page_size": 4}, "/layout/web/components/0/page_size",
     "page_size = 4 está fuera del rango 5-200"),
])
def test_out_of_range_components_fail(ws, component, path, substr) -> None:
    """Fuera de los límites del esquema la validación falla (el esquema para el informe)."""
    _with_view_ids(ws)
    _edit_report(ws, layout=_web(_kpi(**component)))
    result = validate.validate(ws)
    assert result.ok is False
    assert any(i.path == path for i in result.issues), [str(i) for i in result.issues]
    assert any(i.level == "error" for i in result.issues)
    # y el comprobador compartido usa su propio código cuando no ve el esquema
    issue = _issue(_layout_issues(ws), "layout_range", path)
    assert substr in issue.message


def test_out_of_range_page(ws) -> None:
    _with_view_ids(ws)
    layout = {"pdf": {"page": {"size": "a3", "margins": {"top": 4, "left": 41}}}}
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    assert result.ok is False
    assert any(i.path == "/layout/pdf/page/size" for i in result.issues)
    issues = _layout_issues(ws)
    assert _issue(issues, "layout_range", "/layout/pdf/page/size")
    issue = _issue(issues, "layout_range", "/layout/pdf/page/margins/top")
    assert "margins.top = 4 está fuera del rango 5-40" in issue.message


# ------------------------------------------------------------------- colores y textos


def test_literal_color_does_not_validate(ws) -> None:
    _with_view_ids(ws)
    _edit_report(ws, layout=_web(_kpi(colors=["#ff0000"])))
    result = validate.validate(ws)
    assert result.ok is False
    assert any(i.path == "/layout/web/components/0/colors" for i in result.issues)
    issue = _issue(_layout_issues(ws), "layout_color_literal", "/layout/web/components/0/colors/0")
    assert "color literal '#ff0000'" in issue.message
    assert "series1" in (issue.fix or "")


@pytest.mark.parametrize("value,code", [
    ("#ff0000", "layout_color_literal"),
    ("rgb(1,2,3)", "layout_color_literal"),
    ("rgba(1,2,3,0.5)", "layout_color_literal"),
    ("hsl(0,0%,0%)", "layout_color_literal"),
    ("https://ejemplo.test/informe", "layout_address_forbidden"),
    ("url(x)", "layout_address_forbidden"),
    ("data:image/png;base64,AAA", "layout_address_forbidden"),
])
def test_colour_and_address_codes(value, code) -> None:
    """Un color literal y una dirección llevan códigos distintos, con su puntero."""
    definition = {
        "metrics": {"ventas": {"label": "Ventas"}},
        "dimensions": {"marca": {"label": "Marca"}},
        "views": [{"id": "resumen", "type": "kpis", "metrics": ["ventas"]}],
        "layout": {"web": {"components": [
            {"id": "nota", "type": "text", "text": value},
            {"id": "grafico", "type": "kpi", "view": "resumen", "metric": "ventas",
             "colors": [value]},
        ]}},
    }
    issues = check_layout(definition, file=REPORT)
    assert {i.code for i in issues} == {code}
    assert {i.level for i in issues} == {"error"}
    assert {i.path for i in issues} == {"/layout/web/components/0/text",
                                        "/layout/web/components/1/colors/0"}


def test_url_with_colour_function_reports_the_address() -> None:
    """Una dirección gana a un color cuando el texto lleva las dos cosas (lo más seguro)."""
    definition = {"layout": {"web": {"components": [
        {"id": "nota", "type": "text", "text": "url(#ff0000)"}]}}}
    issues = check_layout(definition, file=REPORT)
    assert [i.code for i in issues] == ["layout_address_forbidden"]
    assert issues[0].path == "/layout/web/components/0/text"


def test_color_roles_pass(ws) -> None:
    _with_view_ids(ws)
    _edit_report(ws, layout=_web(_kpi(colors=["primary", "series1"])))
    assert validate.validate(ws).ok is True


def test_address_anywhere_in_layout_is_rejected(ws) -> None:
    _with_view_ids(ws)
    _edit_report(ws, layout=_web({"id": "nota", "type": "text",
                                  "text": "Ver https://ejemplo.test/informe"}))
    result = validate.validate(ws)
    assert result.ok is False
    issue = _issue(result, "layout_address_forbidden", "/layout/web/components/0/text")
    assert issue.level == "error"
    assert "direcciones" in issue.message
    assert "direcciones" in str(issue.expected)


def test_font_name_only_on_text_components(ws) -> None:
    _with_view_ids(ws)
    _edit_report(ws, layout=_web({"id": "nota", "type": "text", "text": "Cifras del mes.",
                                  "font_name": "serif"}))
    assert validate.validate(ws).issues == []

    _edit_report(ws, layout=_web(_kpi(font_name="serif")))
    result = validate.validate(ws)
    assert result.ok is False
    assert any(i.path == "/layout/web/components/0/type" for i in result.issues)


def test_font_name_only_on_text_blocks(ws) -> None:
    _with_view_ids(ws)
    layout = {"pdf": {"blocks": [{"id": "nota", "type": "text", "text": "Cifras del mes.",
                                  "font_name": "mono"}]}}
    _edit_report(ws, layout=layout)
    assert validate.validate(ws).issues == []

    layout = {"pdf": {"blocks": [{"id": "grafico", "type": "chart", "view": "diaria",
                                  "kind": "line", "x": "day", "series": ["net_sales"],
                                  "font_name": "mono"}]}}
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    assert result.ok is False
    assert any(i.path == "/layout/pdf/blocks/0/type" for i in result.issues)


def test_unknown_component_type(ws) -> None:
    _with_view_ids(ws)
    _edit_report(ws, layout=_web({"id": "x", "type": "gauge", "view": "resumen"}))
    result = validate.validate(ws)
    assert result.ok is False
    assert any(i.path == "/layout/web/components/0/type" for i in result.issues)
    definition = yaml.safe_load((ws / REPORT).read_text(encoding="utf-8"))
    issue = _issue(check_layout(definition, file=REPORT), "layout_component_unknown",
                   "/layout/web/components/0/type")
    assert "fuera del catálogo" in issue.message


# ------------------------------------------------------------------- avisos


def test_pie_top_n_below_view_limit_warns(ws) -> None:
    _with_view_ids(ws)
    layout = _web({"id": "categorias", "type": "pie", "view": "productos",
                   "category": "product", "value": "net_sales", "top_n": 2})
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    assert result.ok is True                       # un aviso no rompe la validación
    issue = _issue(result, "layout_chart_unsuitable", "/layout/web/components/0/top_n")
    assert issue.level == "warning"
    assert "top_n >= 4" in issue.message
    assert {i.level for i in result.issues} == {"warning"}


def test_pie_top_n_within_view_limit_is_silent(ws) -> None:
    _with_view_ids(ws)
    layout = _web({"id": "categorias", "type": "pie", "view": "productos",
                   "category": "product", "value": "net_sales", "top_n": 6})
    _edit_report(ws, layout=layout)
    assert validate.validate(ws).issues == []


def test_line_over_unsorted_dimension_warns(ws) -> None:
    _with_view_ids(ws)
    layout = _web({"id": "linea", "type": "line", "view": "productos", "x": "product",
                   "series": ["net_sales"]})
    _edit_report(ws, layout=layout)
    result = validate.validate(ws)
    assert result.ok is True
    issue = _issue(result, "layout_chart_unsuitable", "/layout/web/components/0/x")
    assert issue.level == "warning"
    assert "no es una dimensión ordenada" in issue.message


def test_line_over_grain_and_ordered_dimension_is_silent(ws) -> None:
    data = yaml.safe_load((ws / REPORT).read_text(encoding="utf-8"))
    data["dimensions"]["mes"] = {"label": "Mes", "sql": "date_trunc('month', lines.local_date)"}
    data["views"] = [{"id": "diaria", "type": "trend", "metric": "net_sales", "grain": "day"}]
    data["layout"] = _web(
        {"id": "por_grano", "type": "line", "view": "diaria", "x": "day",
         "series": ["net_sales"]},
        {"id": "por_mes", "type": "line", "view": "diaria", "x": "mes",
         "series": ["net_sales"]},
    )
    _dump(ws, data)
    assert validate.validate(ws).issues == []


def test_pdf_with_legacy_keys_warns(ws) -> None:
    _with_view_ids(ws, table=True)
    layout = {"pdf": {"blocks": [{"id": "detalle", "type": "table", "view": "detalle"}]}}
    _edit_report(ws, layout=layout, pdf={"enabled": True, "orientation": "portrait",
                                         "views": [0]})
    result = validate.validate(ws)
    assert result.ok is True
    issue = _issue(result, "layout_pdf_legacy_views", "/layout/pdf")
    assert issue.level == "warning"
    assert "pdf.views" in issue.message
    assert "quita pdf.views" in (issue.fix or "")


# ------------------------------------------------------------------- sin layout


def test_report_without_layout_has_no_layout_issues(ws) -> None:
    result = validate.validate(ws)
    assert result.ok is True
    assert [i for i in result.issues if i.code.startswith("layout")] == []


@pytest.mark.parametrize("definition", [
    {},
    {"layout": None},
    {"layout": []},
    {"layout": {"web": "no soy un objeto", "pdf": 7}},
    {"layout": {"web": {"components": "no soy una lista"}}},
    {"layout": {"web": {"components": [None, 3, {"id": 5, "type": 6}]}}},
    {"layout": {"web": {"components": [{"id": "x", "type": "kpi", "view": ["no"]}]}}},
    {"layout": {"pdf": {"blocks": [{"id": None, "type": "chart", "kind": "pie",
                                    "top_n": "muchas"}]}}},
    {"layout": {"pdf": {"page": {"margins": "no"}}}},
    {"layout": {"web": {"components": [{"id": "x", "type": "table", "view": "v",
                                        "columns": "no", "widths": "tampoco"}]}}},
])
def test_check_layout_tolerates_malformed_shapes(definition) -> None:
    assert isinstance(check_layout(definition, file="x.yaml"), list)


def test_check_layout_needs_no_layout() -> None:
    assert check_layout({}, file="x.yaml") == []
    assert check_layout({"layout": {}}, file="x.yaml") == []


def test_catalogues_cover_every_type() -> None:
    schema = validate.SCHEMAS["report"].schema
    assert schema["$defs"]["web_component"]["properties"]["type"]["enum"] == list(
        report_layout.WEB_COMPONENT_TYPES)
    assert schema["$defs"]["pdf_block"]["properties"]["type"]["enum"] == list(
        report_layout.PDF_BLOCK_TYPES)
    assert schema["$defs"]["color_role"]["enum"] == list(report_layout.COLOR_ROLES)
