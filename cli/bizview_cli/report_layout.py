"""Reglas de layout.web, layout.pdf y layout.theme que el esquema JSON no puede expresar.

Referencias (vista, métrica, columna de la vista y filtro), catálogo de tipos, ids duplicados,
límites numéricos, colores literales, direcciones y avisos de idoneidad del gráfico. El validador
y el Asistente comparten este módulo, así que los problemas son idénticos en los dos (FR-014);
`backend/app/projects/compose.py` los recibe a través de `bizview_cli.validate`.

Una vista declara un `id` opcional en `views` y el layout enlaza **solo** por ese id (FR-002): el
informe es una lista ordenada, así que no hay enlace por índice. Una vista sin `id` no se puede
referenciar y `check_layout` lo dice con `layout_view_missing` y la pista de declararlo.

Este módulo no es `bizview_cli/layout.py`: ese es el espacio de trabajo del proyecto (feature 020)
y no se toca.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bizview_cli.validate import Issue

WEB_COMPONENT_TYPES = ("kpi", "line", "area", "bar", "pie", "donut", "table", "gauge", "share",
                       "index", "asset", "text", "filters",
                       "spacer")
PDF_BLOCK_TYPES = ("header", "kpi_row", "chart", "table", "text", "page_break", "footer")
CHART_KINDS = ("line", "area", "bar", "pie", "donut")
COLOR_ROLES = ("primary", "positive", "negative", "neutral", "muted",
               *(f"series{n}" for n in range(1, 9)))
FONT_NAMES = ("sans", "sans_bold", "serif", "mono")
GUTTERS = ("sm", "md", "lg")
GRAINS = ("auto", "day", "week", "month", "quarter", "year", "date", "bucket")
PDF_SIZES = ("a4", "letter")
PDF_ORIENTATIONS = ("portrait", "landscape")
PDF_OVERFLOWS = ("continue", "truncate")
LOGO_ROLES = ("brand", "none")
TEXT_STYLES = ("heading", "paragraph", "caption")
TEXT_ALIGNS = ("left", "center", "right")
KPI_DELTAS = ("previous_period", "none")
BAR_ORIENTATIONS = ("vertical", "horizontal")
SPACER_SIZES = ("sm", "md", "lg")
# Presets de paleta (FR-008): los ids que comparten el CLI, el backend y la interfaz.
PALETTE_PRESETS = ("impacto", "clasico", "monocromo", "contraste", "daltonico")

SPAN_BOUNDS = (1, 12)
TOP_N_BOUNDS = (2, 12)
PAGE_SIZE_BOUNDS = (5, 200)
HEIGHT_MM_BOUNDS = (30, 200)
MARGIN_BOUNDS = (5, 40)
TEXT_MAX = 500
TITLE_MAX = 80
OTHER_LABEL_MAX = 40
LEGAL_MAX = 200

# Un pie con menos del 40% de las categorías de la vista pierde el resto en «otros» (R10).
TOP_N_SHARE = 0.4
_VIEW_LIMIT_DEFAULT = {"ranking": 10, "table": 100}

_DATED_FUNC = re.compile(r"date_trunc|to_char|strftime|extract\s*\(", re.I)
_DATE_WORDS = frozenset({
    "fecha", "date", "dia", "día", "day", "mes", "month", "año", "ano", "year", "semana", "week",
    "periodo", "period", "trimestre", "quarter", "hora", "time", "ts", "timestamp", "timestamptz",
})
# El layout solo admite roles y textos: ni colores literales ni direcciones (R8).
_HEX = (r"(?<![0-9A-Za-z])"
        r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})"
        r"(?![0-9A-Za-z])")
_COLOR_FUNC = r"\b(?:rgba?|hsla?)\s*\("
_URL_FUNC = r"\burl\s*\("
_SCHEME = r"://|(?<![0-9A-Za-z])data:"
_COLOR_LITERAL = re.compile(rf"{_HEX}|{_COLOR_FUNC}", re.I)
_ADDRESS = re.compile(rf"{_URL_FUNC}|{_SCHEME}", re.I)
# «¿este texto está prohibido aquí?»: la unión de las dos reglas, para los campos de color.
_LITERAL = re.compile(rf"{_HEX}|{_COLOR_FUNC}|{_URL_FUNC}|{_SCHEME}", re.I)
_NO_ADDRESS = "sin direcciones: el branding y los enlaces los resuelve la instalación"


def check_layout(definition: dict, *, file: str, entry: str = "report") -> list[Issue]:
    """Comprobaciones de referencias (errores) y de idoneidad de gráficos (avisos) de
    layout.web/layout.pdf."""

    if not isinstance(definition, dict):
        return []
    layout = definition.get("layout")
    if not isinstance(layout, dict):
        return []
    facts = _facts(definition)
    out: list[Issue] = []
    for path, value in _texts(layout, "/layout"):
        if value.strip() and _LITERAL.search(value):
            out.append(_literal(path, value, file, entry))
    web = layout.get("web")
    if isinstance(web, dict):
        _web(web, facts, file, entry, out)
    theme = layout.get("theme")
    if isinstance(theme, dict):
        _theme(theme, file, entry, out)
        if "palette" not in theme:
            # A theme was started and left without a palette: the installation's applies, so this
            # is a warning with a one-click pin (035 FR-013). A report with no theme at all says
            # nothing on purpose and stays quiet.
            out.append(_issue(
                entry, "layout_palette_missing",
                "layout.theme no fija paleta: se usa la de la instalación", file=file,
                path="/layout/theme/palette", level="warning",
                fix=f"fija la paleta {PALETTE_PRESETS[0]} en layout.theme.palette",
                fix_data={"file": file, "json_path": "/layout/theme/palette", "op": "set",
                          "value": PALETTE_PRESETS[0]}))
    pdf = layout.get("pdf")
    if isinstance(pdf, dict):
        _pdf(pdf, facts, file, entry, out)
        if _legacy_pdf(definition):
            out.append(_issue(
                entry, "layout_pdf_legacy_views",
                "layout.pdf está declarado junto a pdf.views/pdf.orientation, que se ignoran:"
                " el orden y la orientación los define layout.pdf",
                file=file, path="/layout/pdf", level="warning",
                fix="quita pdf.views y pdf.orientation de report.yaml",
            ))
    return out


# ---------------------------------------------------------------- hechos del informe


@dataclass(frozen=True)
class _Facts:
    """Ids que el informe declara, para comprobar las referencias del layout."""

    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]
    filters: tuple[str, ...]
    views: dict[str, dict]
    types: frozenset[str]
    ordered: frozenset[str]
    date: str | None

    @property
    def columns(self) -> tuple[str, ...]:
        return self.metrics + self.dimensions

    def view(self, view_id: object) -> dict | None:
        return self.views.get(view_id) if isinstance(view_id, str) else None


def _facts(definition: dict) -> _Facts:
    metrics = _keys(definition.get("metrics"))
    dimensions = _keys(definition.get("dimensions"))
    filters = tuple(f for f in _as_list(definition.get("filters")) if isinstance(f, str))
    views: dict[str, dict] = {}
    types: set[str] = set()
    for view in _as_list(definition.get("views")):
        if not isinstance(view, dict):
            continue
        view_id = _view_id(view)
        if view_id is not None and view_id not in views:
            views[view_id] = view
        view_type = view.get("type")
        if view_id is None and isinstance(view_type, str) and view_type not in types:
            types.add(view_type)
    date = definition.get("date")
    date = date if isinstance(date, str) else None
    dims = definition.get("dimensions")
    dims = dims if isinstance(dims, dict) else {}
    ordered = frozenset(did for did in dimensions if _ordered(dims.get(did), date))
    return _Facts(metrics, dimensions, filters, views, frozenset(types), ordered, date)


def _view_id(view: dict) -> str | None:
    """Id declarado por la vista; sin id, el layout no puede enlazarla (FR-002)."""

    view_id = view.get("id")
    return view_id.strip() if isinstance(view_id, str) and view_id.strip() else None


def _ordered(dimension: object, date: str | None) -> bool:
    """True cuando la dimensión se ordena en el tiempo: la columna de fecha o un SQL de fecha."""

    sql = dimension.get("sql") if isinstance(dimension, dict) else None
    if not isinstance(sql, str):
        return False
    text = sql.strip()
    if date is not None and text == date:
        return True
    if _DATED_FUNC.search(text):
        return True
    token = text.rsplit(".", 1)[-1]
    return bool(_DATE_WORDS & set(re.split(r"[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", token.casefold())))


def _view_columns(view: dict) -> set[str]:
    """Ids que la vista expone como columnas: sus dimensiones y sus métricas."""

    out = set()
    for key in ("dimensions", "metrics"):
        out.update(v for v in _as_list(view.get(key)) if isinstance(v, str))
    for key in ("dimension", "metric"):
        value = view.get(key)
        if isinstance(value, str):
            out.add(value)
    return out


def _view_limit(view: dict) -> int | None:
    """Límite de categorías de la vista; el del motor cuando la vista no lo declara."""

    limit = view.get("limit")
    if isinstance(limit, int) and not isinstance(limit, bool):
        return limit
    return _VIEW_LIMIT_DEFAULT.get(view.get("type"))


def _legacy_pdf(definition: dict) -> bool:
    """True cuando el informe conserva pdf.views/pdf.orientation junto al layout."""

    pdf = definition.get("pdf")
    if not isinstance(pdf, dict):
        return False
    return any(key in pdf for key in ("views", "orientation"))


# ------------------------------------------------------------------ layout.theme


def _theme(theme: dict, file: str, entry: str, out: list[Issue]) -> None:
    """Comprueba layout.theme: solo el id de un preset de paleta (FR-008).

    Un color literal aquí lo denuncia el recorrido de textos de `check_layout`, no `_enum`.
    """

    _enum(out, entry, file, "/layout/theme/palette", "palette", theme.get("palette"),
          PALETTE_PRESETS)


# ------------------------------------------------------------------ layout.web


def _web(web: dict, facts: _Facts, file: str, entry: str, out: list[Issue]) -> None:
    """Comprueba layout.web: componentes, ids únicos, referencias y límites."""

    _enum(out, entry, file, "/layout/web/gutter", "gutter", web.get("gutter"), GUTTERS)
    seen: dict[str, int] = {}
    for i, comp in enumerate(_as_list(web.get("components"))):
        if not isinstance(comp, dict):
            continue
        where = f"/layout/web/components/{i}"
        label = _label("components", i, comp)
        _duplicate(seen, comp.get("id"), i, label, where + "/id", "components", file, entry, out)
        type_ = comp.get("type")
        if isinstance(type_, str) and type_ not in WEB_COMPONENT_TYPES:
            out.append(_issue(
                entry, "layout_component_unknown",
                f"{label}: tipo de componente '{type_}' fuera del catálogo", file=file,
                path=where + "/type", expected={"enum": list(WEB_COMPONENT_TYPES)},
                fix=_use("uno de los tipos del catálogo", WEB_COMPONENT_TYPES)))
        view = _view_ref(comp.get("view"), where + "/view", label, facts, file, entry, out)
        for key in ("metric", "value"):
            _metric(comp.get(key), f"{where}/{key}", label, key, facts, file, entry, out)
        for key in ("series", "items"):
            _metric_list(comp.get(key), f"{where}/{key}", label, key, facts, file, entry, out)
        columns = _column_list(comp.get("columns"), f"{where}/columns", label, facts,
                               file, entry, out)
        if type_ == "table" and view is not None and columns:
            _view_prefix(columns, view, comp.get("view"), where + "/columns", label, file, entry,
                         out)
        if type_ == "filters":
            _only(comp.get("only"), where + "/only", label, facts, file, entry, out)
        _bounds(comp, where, label, file, entry, out)
        _roles(comp, where, label, file, entry, out)
        if type_ in ("line", "area"):
            _x_suitable(comp.get("x"), view, facts, where + "/x", label, file, entry, out)
        if type_ in ("pie", "donut"):
            _top_n_suitable(comp.get("top_n"), view, where + "/top_n", label, file, entry, out)


# ------------------------------------------------------------------ layout.pdf


def _pdf(pdf: dict, facts: _Facts, file: str, entry: str, out: list[Issue]) -> None:
    """Comprueba layout.pdf: página, bloques, ids únicos, referencias y límites."""

    _enum(out, entry, file, "/layout/pdf/overflow", "overflow", pdf.get("overflow"),
          PDF_OVERFLOWS)
    _page(pdf.get("page"), file, entry, out)
    seen: dict[str, int] = {}
    for i, block in enumerate(_as_list(pdf.get("blocks"))):
        if not isinstance(block, dict):
            continue
        where = f"/layout/pdf/blocks/{i}"
        label = _label("blocks", i, block)
        _duplicate(seen, block.get("id"), i, label, where + "/id", "blocks", file, entry, out)
        type_ = block.get("type")
        if isinstance(type_, str) and type_ not in PDF_BLOCK_TYPES:
            out.append(_issue(
                entry, "layout_block_unknown",
                f"{label}: tipo de bloque '{type_}' fuera del catálogo", file=file,
                path=where + "/type", expected={"enum": list(PDF_BLOCK_TYPES)},
                fix=_use("uno de los tipos del catálogo", PDF_BLOCK_TYPES)))
        view = _view_ref(block.get("view"), where + "/view", label, facts, file, entry, out)
        if type_ == "chart":
            _enum(out, entry, file, where + "/kind", f"{label}: kind", block.get("kind"),
                  CHART_KINDS)
        if block.get("kind") in ("line", "area"):
            _x_suitable(block.get("x"), view, facts, where + "/x", label, file, entry, out)
        if block.get("kind") in ("pie", "donut"):
            _top_n_suitable(block.get("top_n"), view, where + "/top_n", label, file, entry, out)
        _metric(block.get("value"), f"{where}/value", label, "value", facts, file, entry, out)
        for key in ("items", "series"):
            _metric_list(block.get(key), f"{where}/{key}", label, key, facts, file, entry, out)
        columns = _column_list(block.get("columns"), f"{where}/columns", label, facts,
                               file, entry, out)
        if type_ == "table" and view is not None and columns:
            _view_prefix(columns, view, block.get("view"), where + "/columns", label, file,
                         entry, out)
        _widths(block.get("widths"), block.get("columns"), where + "/widths", label, file, entry,
                out)
        _bounds(block, where, label, file, entry, out)
        _block_enums(block, where, label, file, entry, out)


def _page(page: object, file: str, entry: str, out: list[Issue]) -> None:
    """Comprueba layout.pdf.page: tamaños con nombre y márgenes en milímetros."""

    if not isinstance(page, dict):
        return
    where = "/layout/pdf/page"
    _enum(out, entry, file, where + "/size", "page.size", page.get("size"), PDF_SIZES)
    _enum(out, entry, file, where + "/orientation", "page.orientation", page.get("orientation"),
          PDF_ORIENTATIONS)
    margins = page.get("margins")
    if isinstance(margins, dict):
        for side, value in margins.items():
            if isinstance(side, str):
                _range(out, entry, file, f"{where}/margins/{side}", f"margins.{side}", value,
                       MARGIN_BOUNDS)


# ------------------------------------------------------------------ referencias


def _view_ref(view_id: object, path: str, label: str, facts: _Facts, file: str, entry: str,
              out: list[Issue]) -> dict | None:
    """layout_view_missing: la vista referenciada, o None con el problema ya anotado.

    El enlace es solo por id (FR-002): una vista sin `id` no se puede referenciar.
    """

    if view_id is None:
        return None
    view = facts.view(view_id)
    if view is not None:
        return view
    declared = view_id if isinstance(view_id, str) and view_id in facts.types else None
    detail = f"; la vista de tipo '{declared}' no declara id" if declared else ""
    names = _names(facts.views)
    if names:
        detail += f"; vistas declaradas: {names}"
    out.append(_issue(
        entry, "layout_view_missing",
        f"{label}: no existe la vista '{view_id}'{detail}", file=file, path=path,
        expected={"enum": sorted(facts.views)},
        fix="declara id en la vista y referencia ese id" if declared
        else f"usa el id de una vista declarada: {names}" if names
        else "declara id en la vista y referencia ese id"))
    return None


def _metric(value: object, path: str, label: str, field: str, facts: _Facts, file: str,
            entry: str, out: list[Issue]) -> None:
    """layout_metric_missing: un id que debe ser una métrica declarada."""

    if value is None:
        return
    if isinstance(value, str) and value in facts.metrics:
        return
    names = _names(facts.metrics)
    out.append(_issue(
        entry, "layout_metric_missing",
        f"{label}: no existe la métrica '{value}' en {field}", file=file, path=path,
        expected={"enum": list(facts.metrics)},
        fix=f"usa una métrica declarada: {names}" if names else "declara la métrica en metrics"))


def _metric_list(value: object, path: str, label: str, field: str, facts: _Facts, file: str,
                 entry: str, out: list[Issue]) -> None:
    """layout_metric_missing por cada id de una lista de métricas (series, items)."""

    if value is None:
        return
    for i, item in enumerate(_as_list(value)):
        _metric(item, f"{path}/{i}", label, field, facts, file, entry, out)


def _column_list(value: object, path: str, label: str, facts: _Facts, file: str, entry: str,
                 out: list[Issue]) -> tuple[str, ...]:
    """layout_column_missing: cada columna debe ser una métrica o dimensión declarada."""

    columns: list[str] = []
    if value is None:
        return ()
    for i, item in enumerate(_as_list(value)):
        if not isinstance(item, str):
            continue
        if item in facts.columns:
            columns.append(item)
            continue
        out.append(_issue(
            entry, "layout_column_missing",
            f"{label}: no existe la métrica ni la dimensión '{item}' en columns", file=file,
            path=f"{path}/{i}", expected={"enum": list(facts.columns)},
            fix=_use("una métrica o dimensión declarada", facts.columns)))
    return tuple(columns)


def _view_prefix(columns: tuple[str, ...], view: dict, view_id: object, path: str, label: str,
                 file: str, entry: str, out: list[Issue]) -> None:
    """layout_column_missing: las columnas de una tabla deben existir en su vista."""

    available = sorted(_view_columns(view))
    for i, column in enumerate(columns):
        if column in available:
            continue
        out.append(_issue(
            entry, "layout_column_missing",
            f"{label}: la vista '{view_id}' no expone la columna '{column}'", file=file,
            path=f"{path}/{i}", expected={"enum": available},
            fix=f"usa una columna de la vista {view_id}: {', '.join(available)}" if available
            else f"declara la columna en la vista {view_id}"))


def _only(value: object, path: str, label: str, facts: _Facts, file: str, entry: str,
          out: list[Issue]) -> None:
    """layout_filter_missing: los filtros del componente son filtros declarados."""

    if value is None:
        return
    names = _names(facts.filters)
    items = _as_list(value)
    for i, item in enumerate(items):
        if isinstance(item, str) and item in facts.filters:
            continue
        out.append(_issue(
            entry, "layout_filter_missing",
            f"{label}: no existe el filtro '{item}' en only", file=file, path=f"{path}/{i}",
            expected={"enum": list(facts.filters)},
            fix=f"usa un filtro declarado en filters: {names}" if names
            else "quita la referencia o declara el filtro en filters",
            fix_data={"file": file,
                      "json_path": path if len(items) == 1 else f"{path}/{i}",
                      "op": "remove", "value": None}))


# --------------------------------------------------------------- ids y límites


def _duplicate(seen: dict[str, int], value: object, index: int, label: str, path: str,
               kind: str, file: str, entry: str, out: list[Issue]) -> None:
    """layout_id_duplicate: el id de un componente o bloque se repite."""

    if not isinstance(value, str) or not value:
        return
    first = seen.get(value)
    if first is None:
        seen[value] = index
        return
    out.append(_issue(
        entry, "layout_id_duplicate",
        f"{label}: el id '{value}' ya está declarado en {kind}[{first}]", file=file, path=path,
        fix=f"usa un id único en {kind}"))


def _bounds(node: dict, where: str, label: str, file: str, entry: str,
            out: list[Issue]) -> None:
    """Límites numéricos y de longitud (el esquema los cubre; aquí son defensivos)."""

    _range(out, entry, file, f"{where}/span", f"{label}: span", node.get("span"), SPAN_BOUNDS)
    _range(out, entry, file, f"{where}/top_n", f"{label}: top_n", node.get("top_n"),
           TOP_N_BOUNDS)
    _range(out, entry, file, f"{where}/page_size", f"{label}: page_size", node.get("page_size"),
           PAGE_SIZE_BOUNDS)
    _range(out, entry, file, f"{where}/height_mm", f"{label}: height_mm", node.get("height_mm"),
           HEIGHT_MM_BOUNDS)
    for key, limit in (("title", TITLE_MAX), ("title_en", TITLE_MAX),
                       ("other_label", OTHER_LABEL_MAX), ("other_label_en", OTHER_LABEL_MAX),
                       ("legal", LEGAL_MAX), ("legal_en", LEGAL_MAX), ("text", TEXT_MAX),
                       ("text_en", TEXT_MAX)):
        _maxlen(out, entry, file, f"{where}/{key}", f"{label}: {key}", node.get(key), limit)
    for key in ("text", "text_en"):
        value = node.get(key)
        if isinstance(value, str) and not value.strip():
            out.append(_issue(
                entry, "layout_range", f"{label}: {key} no puede estar vacío", file=file,
                path=f"{where}/{key}", expected={"minLength": 1},
                fix=f"escribe un {key} de 1 a {TEXT_MAX} caracteres"))


def _widths(value: object, columns: object, path: str, label: str, file: str, entry: str,
            out: list[Issue]) -> None:
    """layout_range: widths tiene exactamente tantas entradas como columns."""

    if not isinstance(value, list):
        return
    n = len(_as_list(columns))
    if n and len(value) != n:
        out.append(_issue(
            entry, "layout_range",
            f"{label}: widths tiene {len(value)} entradas y columns {n}", file=file, path=path,
            expected={"minItems": n, "maxItems": n},
            fix=f"declara {n} pesos en widths, uno por columna"))


def _range(out: list[Issue], entry: str, file: str, path: str, what: str, value: object,
           bounds: tuple[int, int]) -> None:
    """layout_range para un entero fuera de rango."""

    if isinstance(value, bool) or not isinstance(value, int):
        return
    low, high = bounds
    if low <= value <= high:
        return
    out.append(_issue(
        entry, "layout_range", f"{what} = {value} está fuera del rango {low}-{high}", file=file,
        path=path, expected={"minimum": low, "maximum": high},
        fix=f"usa un valor entre {low} y {high}"))


def _maxlen(out: list[Issue], entry: str, file: str, path: str, what: str, value: object,
            limit: int) -> None:
    """layout_range para un texto más largo que su límite."""

    if isinstance(value, str) and len(value) > limit:
        out.append(_issue(
            entry, "layout_range", f"{what} tiene {len(value)} caracteres (máximo {limit})",
            file=file, path=path, expected={"maxLength": limit},
            fix=f"acorta {what} a {limit} caracteres o menos"))


def _enum(out: list[Issue], entry: str, file: str, path: str, what: str, value: object,
          allowed: tuple[str, ...]) -> None:
    """layout_range para un valor fuera de su catálogo; un literal lo denuncia el color."""

    if not isinstance(value, str) or value in allowed or _LITERAL.search(value):
        return
    out.append(_issue(
        entry, "layout_range", f"{what} '{value}' no es un valor admitido", file=file, path=path,
        expected={"enum": list(allowed)}, fix=_use("uno de", allowed)))


def _roles(node: dict, where: str, label: str, file: str, entry: str,
           out: list[Issue]) -> None:
    """Los roles de color del componente web y su fuente con nombre."""

    colors = node.get("colors")
    if colors is not None:
        values = _as_list(colors) if isinstance(colors, list) else [colors]
        for i, role in enumerate(values):
            path = f"{where}/colors/{i}" if isinstance(colors, list) else f"{where}/colors"
            _enum(out, entry, file, path, f"{label}: colors", role, COLOR_ROLES)
    _enum(out, entry, file, f"{where}/font_name", f"{label}: font_name", node.get("font_name"),
          FONT_NAMES)
    _enum(out, entry, file, f"{where}/delta", f"{label}: delta", node.get("delta"), KPI_DELTAS)
    _enum(out, entry, file, f"{where}/style", f"{label}: style", node.get("style"), TEXT_STYLES)
    _enum(out, entry, file, f"{where}/size", f"{label}: size", node.get("size"), SPACER_SIZES)
    _enum(out, entry, file, f"{where}/orientation", f"{label}: orientation",
          node.get("orientation"), BAR_ORIENTATIONS)


def _block_enums(node: dict, where: str, label: str, file: str, entry: str,
                 out: list[Issue]) -> None:
    """Los catálogos del bloque PDF: rol del logo, estilo, alineación y política de tabla."""

    for key, allowed in (("logo_role", LOGO_ROLES), ("style", TEXT_STYLES),
                         ("align", TEXT_ALIGNS), ("overflow", PDF_OVERFLOWS),
                         ("font_name", FONT_NAMES)):
        _enum(out, entry, file, f"{where}/{key}", f"{label}: {key}", node.get(key), allowed)


# -------------------------------------------------------------------- avisos


def _x_suitable(x: object, view: dict | None, facts: _Facts, path: str, label: str, file: str,
                entry: str, out: list[Issue]) -> None:
    """layout_chart_unsuitable: un eje de línea sobre una dimensión no ordenada."""

    if not isinstance(x, str) or not x.strip():
        return
    if x in GRAINS or x in facts.ordered or (facts.date is not None and x == facts.date):
        return
    grain = view.get("grain") if isinstance(view, dict) else None
    if isinstance(grain, str) and x == grain:
        return
    out.append(_issue(
        entry, "layout_chart_unsuitable",
        f"{label}: el eje x = '{x}' no es una dimensión ordenada ni una granularidad"
        f" ({', '.join(GRAINS)}); el renderizador lo dibuja como barras", file=file, path=path,
        level="warning", fix="usa una dimensión de fecha, la granularidad de la vista o"
        " el tipo bar"))


def _top_n_suitable(top_n: object, view: dict | None, path: str, label: str, file: str,
                    entry: str, out: list[Issue]) -> None:
    """layout_chart_unsuitable: un pie que agrupa en «otros» más del 60% de las categorías."""

    if view is None or isinstance(top_n, bool) or not isinstance(top_n, int):
        return
    limit = _view_limit(view)
    if limit is None:
        return
    minimum = math.ceil(limit * TOP_N_SHARE)
    if top_n >= minimum:
        return
    out.append(_issue(
        entry, "layout_chart_unsuitable",
        f"{label}: top_n = {top_n} sobre {limit} categorías de la vista agrupa el resto en"
        f" «otros»; usa top_n >= {minimum}", file=file, path=path, level="warning",
        fix=f"usa top_n entre {minimum} y 12 o filtra las categorías"))


# -------------------------------------------------------------------- auxiliares


def _issue(entry: str, code: str, message: str, *, file: str, path: str,
           expected: dict | None = None, fix: str | None = None,
           level: str = "error", fix_data: dict | None = None) -> Issue:
    """Crea un `validate.Issue`; la importación es diferida porque validate importa este módulo."""

    from bizview_cli.validate import Issue

    return Issue(entry, code, message, level=level, file=file, path=path, expected=expected,
                 fix=fix, fix_data=fix_data)


def _ptr(*parts: str | int) -> str:
    """RFC 6901, con el mismo escape que el validador."""

    from bizview_cli.validate import _pointer

    return _pointer(list(parts))


def _texts(node: object, path: str) -> Iterator[tuple[str, str]]:
    """Cada texto de un nodo del layout con su puntero JSON."""

    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _texts(value, path + _ptr(str(key)))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _texts(value, path + _ptr(i))


def _literal(path: str, value: str, file: str, entry: str) -> Issue:
    """Un color literal y una dirección tienen códigos distintos, cada uno con su `expected`.

    Una dirección gana cuando el texto lleva las dos cosas (`url(#ff0000)`): es lo más seguro.
    """

    if _ADDRESS.search(value):
        return _issue(
            entry, "layout_address_forbidden",
            f"{path}: no se admiten direcciones ('{value}') en el layout; el branding y los"
            " enlaces los resuelve la instalación", file=file, path=path,
            expected={"description": _NO_ADDRESS},
            fix="quita la dirección: el logo y los enlaces vienen de la instalación")
    return _issue(
        entry, "layout_color_literal",
        f"{path}: color literal '{value}'; usa un rol semántico", file=file, path=path,
        expected={"enum": list(COLOR_ROLES)}, fix=_use("uno de los roles", COLOR_ROLES))


def _as_list(value: object) -> list:
    """The value as a list, tolerating a malformed shape."""

    if isinstance(value, list):
        return value
    return [] if value is None else [value]


def _keys(node: object) -> tuple[str, ...]:
    """String keys of a mapping, tolerating a malformed shape."""

    return tuple(k for k in node if isinstance(k, str)) if isinstance(node, dict) else ()


def _label(kind: str, index: int, node: dict) -> str:
    """`components[1] 'tendencia'` para los mensajes."""

    item_id = node.get("id")
    if isinstance(item_id, str) and item_id:
        return f"{kind}[{index}] '{item_id}'"
    return f"{kind}[{index}]"


def _names(values: object, limit: int = 12) -> str:
    """Sorted names for a message, capped."""

    names = sorted(values) if isinstance(values, dict | tuple | list | set | frozenset) else []
    if len(names) > limit:
        return ", ".join(names[:limit]) + f" (y {len(names) - limit} más)"
    return ", ".join(names)


def _use(what: str, values: tuple[str, ...]) -> str:
    """`usa uno de: a, b`."""

    return f"usa {what}: {', '.join(values)}"
