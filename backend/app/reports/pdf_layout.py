"""Declarative PDF layout (feature 026, research R6 to R8).

`render_layout()` turns `definition["layout"]["pdf"]` into ReportLab flowables: one entry per
declared block, in the declared order. `page_setup()` returns the page size and the margins in
millimetres. A layout carries roles and names only — never a colour, a font file or a URL — so the
palette and the fonts live here, with the ones the fixed story already uses.

`pdf.render()` owns the document: it builds the story here when the report declares a layout and
keeps the fixed story for every report that does not (FR-009).
"""
import base64
import io
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String, Wedge
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, LETTER, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Flowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import get_settings
from app.engine import render_errors
from app.i18n import M, localized, t, tn
from app.reports.palette import ReportPalette, resolve

FONTS = {"sans": "Helvetica", "sans_bold": "Helvetica-Bold",
         "serif": "Times-Roman", "mono": "Courier"}
ALIGN = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}
PAGE_SIZES = {"a4": A4, "letter": LETTER}
DEFAULT_MARGINS = {"top": 12.0, "right": 10.0, "bottom": 12.0, "left": 10.0}
BLOCK_TYPES = ("header", "kpi_row", "chart", "table", "text", "page_break", "footer",
               "gauge", "index", "share", "asset")
CHART_KINDS = ("line", "area", "bar", "pie", "donut")
MIN_CHART_MM, MAX_CHART_MM, DEFAULT_CHART_MM = 30, 200, 60
MIN_MARGIN, MAX_MARGIN = 5.0, 40.0
DEFAULT_TOP_N = 6
DEFAULT_KIND = {"trend": "line", "ranking": "bar", "table": "bar", "kpis": "bar"}
# 044: the four visual blocks mirror their screen components exactly, palette roles included.
GAUGE_ROLES = ("negative", "series5", "neutral", "series3", "positive")
SHARE_ROLES = ("series1", "series2", "series3", "series4")
INDEX_ROLES = ("series1", "neutral", "series2")
INDEX_SLICES = 24
GAUGE_MAX_RADIUS, GAUGE_HOLE = 32 * mm, 0.76
ASSET_COLUMNS, ASSET_LIMIT = 4, 8
ASSET_LOGO = 10 * mm
BADGE_WIDTH, BADGE_HEIGHT, BADGE_ARROW = 24 * mm, 4.4 * mm, 2.2 * mm
BADGE_ARROW_X = 1.6 * mm
DATA_URI_RE = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,(.+)$", re.IGNORECASE)
LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
BOLD_RE = re.compile(r"\*\*([^*\n]+)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")

log = logging.getLogger("app.reports")


def _pdf():
    """The fixed-story module: it imports this one, so its helpers are reached late."""
    from app.reports import pdf
    return pdf


def pdf_document(definition: dict) -> dict | None:
    """The `layout.pdf` document of a report, or None when it declares no layout (FR-009)."""
    layout = definition.get("layout")
    if isinstance(layout, dict) and isinstance(layout.get("pdf"), dict):
        return layout["pdf"]
    return None


def page_setup(layout: dict) -> tuple[Any, dict[str, float]]:
    """(pagesize, márgenes en mm) desde layout.pdf.page, con los valores actuales por defecto."""
    doc = layout if isinstance(layout, dict) else {}
    pdf = doc.get("pdf") if isinstance(doc.get("pdf"), dict) else doc
    page = (pdf or {}).get("page")
    page = page if isinstance(page, dict) else {}
    size = PAGE_SIZES.get(str(page.get("size") or "a4").lower(), A4)
    if str(page.get("orientation") or "portrait").lower() == "landscape":
        size = landscape(size)
    declared = page.get("margins") if isinstance(page.get("margins"), dict) else {}
    return size, {side: _margin(declared.get(side), default)
                  for side, default in DEFAULT_MARGINS.items()}


def _margin(value, default: float) -> float:
    """Millimetres 5-40; anything else (absent, text, out of range) falls back to today's value."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(min(max(value, MIN_MARGIN), MAX_MARGIN))


def _content_width(layout: dict) -> float:
    size, margins = page_setup(layout)
    return size[0] - (margins["left"] + margins["right"]) * mm


def _content_height(layout: dict) -> float:
    size, margins = page_setup(layout)
    return size[1] - (margins["top"] + margins["bottom"]) * mm


def _styles(base: dict, palette: ReportPalette) -> dict:
    """The block styles, on top of the ones the fixed story already builds."""
    return {
        **base,
        "caption": ParagraphStyle("c26", parent=base["meta"], fontSize=8, leading=10,
                                  spaceBefore=1 * mm),
        "text": ParagraphStyle("x26", parent=base["cell"], fontSize=10, leading=14,
                               spaceAfter=2 * mm),
        "heading": ParagraphStyle("h26", parent=base["h2"], spaceBefore=2 * mm),
        "text_caption": ParagraphStyle("xc26", parent=base["cell"], fontSize=8, leading=11,
                                       textColor=palette.muted),
        "kpi_label": ParagraphStyle("kl26", parent=base["cell"], fontSize=8,
                                    textColor=palette.muted),
        "kpi_value": ParagraphStyle("kv26", parent=base["cell"], fontName="Helvetica-Bold",
                                    fontSize=13),
        "small": ParagraphStyle("s26", parent=base["meta"], fontSize=8),
        "cell_head": ParagraphStyle("ch26", parent=base["cell"], fontName="Helvetica-Bold",
                                    fontSize=9),
        "cell_bold": ParagraphStyle("cb26", parent=base["cell"], fontName="Helvetica-Bold",
                                    fontSize=9),
    }


@dataclass
class Layout:
    """What every block needs: the definition, its payload, the styles and the branding."""
    definition: dict
    payload: dict
    styles: dict
    organization: str
    product: str
    viewer: str | None
    preview: bool
    locale: str
    currency: str
    pdf: dict
    width: float
    blocks: list
    palette: ReportPalette
    index: int = 0


class Story:
    """The flowables in declared order plus the running height of the current page.

    ReportLab paginates when it builds the document, so the renderer keeps its own cursor: it is
    what tells a truncating table how many rows the page still holds."""

    def __init__(self, layout_doc: dict, styles: dict):
        self.width = _content_width(layout_doc)
        self.height = _content_height(layout_doc)
        self.styles = styles
        self.flowables: list = []
        self.used = 0.0

    @property
    def remaining(self) -> float:
        return max(self.height - self.used, 0.0)

    def add(self, *flowables) -> None:
        for flowable in flowables:
            self.flowables.append(flowable)
            if isinstance(flowable, PageBreak):
                self.used = 0.0
            else:
                self.used += _height(flowable, self.width, self.height) \
                    + _space(flowable, "getSpaceBefore") + _space(flowable, "getSpaceAfter")

    def space(self, height: float = 2 * mm) -> None:
        """The separator after a block, only when the page still holds it: an empty flowable that
        does not fit would open a blank page."""
        if self.height - self.used > height + 12:
            self.add(Spacer(1, height))


def _height(flowable, width: float, height: float) -> float:
    try:
        return float(flowable.wrap(width, height)[1])
    except Exception:      # a block that cannot measure itself never breaks the document
        return 0.0


def _space(flowable, name: str) -> float:
    """`spaceBefore`/`spaceAfter`: platypus adds them outside `wrap`, so the cursor does too."""
    getter = getattr(flowable, name, None)
    try:
        return float(getter()) if callable(getter) else 0.0
    except Exception:
        return 0.0


class Marker(Flowable):
    """Records where the next flowable starts: the probe document of a truncating table."""

    def __init__(self):
        self.y: float | None = None
        self.width = 0.0

    def wrap(self, width: float, height: float) -> tuple[float, float]:
        self.width = width
        return width, 1.0

    def draw(self) -> None:
        self.y = self.canv.absolutePosition(0, 0)[1]


class PageNumber(Flowable):
    """The page number where the footer lands: only the canvas knows it (feature 026)."""

    def __init__(self, style, text: str, height: float = 11.0):
        self.style = style
        self.text = text
        self.height = height
        self.width = 0.0

    def wrap(self, width: float, height: float) -> tuple[float, float]:
        self.width = width
        return width, self.height

    def draw(self) -> None:
        self.canv.setFont(self.style.fontName, self.style.fontSize)
        self.canv.setFillColor(self.style.textColor)
        self.canv.drawRightString(self.width, 2, self.text.format(n=self.canv.getPageNumber()))


def render_layout(*, definition: dict, payload: dict, styles, organization: str, product: str,
                  viewer: str | None, preview: bool, locale: str,
                  palette: ReportPalette | None = None) -> list:
    """Historia de flowables para definition["layout"]["pdf"].

    Feature 038: a block that cannot be drawn becomes its own error card — with the code and the
    block id — and the rest of the document still renders. Nothing here may leave the report
    without a page for one bad block."""
    pdf_doc = pdf_document(definition) or {}
    blocks = _declared_blocks(pdf_doc)
    pal = palette if palette is not None else resolve(definition)
    story = Story(definition.get("layout") or {}, _styles(styles, pal))
    ctx = Layout(definition=definition, payload=payload, styles=story.styles,
                 organization=organization, product=product, viewer=viewer, preview=preview,
                 locale=locale, currency=definition.get("currency", "USD"), pdf=pdf_doc,
                 width=story.width, blocks=blocks, palette=pal)
    for index, block in enumerate(blocks):
        ctx.index = index
        _render_block(ctx, block, story, payload)
    return story.flowables


def _declared_blocks(pdf_doc: dict) -> list[dict]:
    """Declared blocks in declared order, unknown types included so they can name themselves."""
    blocks = pdf_doc.get("blocks")
    if not isinstance(blocks, list):
        return []
    return [b for b in blocks if isinstance(b, dict)]


def _block_card(styles: dict, title: str, message: str, detail: str | None = None) -> list:
    """The card that replaces one block: its title, what happened, and the technical line."""
    out = [Paragraph(escape(title), styles["heading"]),
           Paragraph(escape(message), styles["text"])]
    if detail:
        out.append(Paragraph(escape(detail), styles["text_caption"]))
    return out


def _render_block(ctx: Layout, block: dict, story: Story, payload: dict) -> None:
    name = str(block.get("id") or block.get("type") or "?")
    kind = str(block.get("type") or "?")
    if kind not in BLOCK_TYPES:
        card = render_errors.card(
            render_errors.LAYOUT_COMPONENT_UNKNOWN,
            str(M("render.layout_component_unknown", component=name, type=kind)),
            report_id=ctx.definition.get("id"), reference=payload.get("render_reference"),
            component=name, type=kind)
        log.error("pdf block %s: unknown type %s (report %s, ref %s)", name, kind,
                  ctx.definition.get("id"), payload.get("render_reference"))
        story.add(*_block_card(ctx.styles, t("render.card_title", component=name),
                               card["message"], _card_detail(card)))
        return
    view = _view(ctx, block)
    if isinstance(view, dict) and view.get("error"):
        card = view["error"]
        story.add(*_block_card(ctx.styles, t("render.card_title", component=name),
                               str(card.get("message") or ""), _card_detail(card)))
        return
    if isinstance(view, dict) and view.get("empty"):
        story.add(*_block_card(ctx.styles, t("render.card_title", component=name),
                               str(view["empty"].get("message") or t("render.card_no_data")),
                               _card_detail(view["empty"])))
        return
    try:
        _BLOCKS[kind](ctx, block, story)
    except Exception as exc:     # one block never takes the document down
        reason = type(exc).__name__
        card = render_errors.card(
            render_errors.PDF_RENDER, str(M("render.pdf_block", block=name, reason=reason)),
            report_id=ctx.definition.get("id"), reference=payload.get("render_reference"),
            block=name, reason=reason)
        log.error("pdf block %s failed (report %s, ref %s): %s", name,
                  ctx.definition.get("id"), payload.get("render_reference"), reason)
        story.add(*_block_card(ctx.styles, t("render.card_title", component=name),
                               card["message"], _card_detail(card)))


def _card_detail(card: dict) -> str:
    """The technical line of a card: the code and the ids, never a row value."""
    parts = [f"{k}={v}" for k, v in card.items() if k != "message" and v not in (None, "")]
    return " · ".join(parts)


def _blocks(pdf_doc: dict) -> list[dict]:
    """Declared blocks of known types, in declared order (validation refuses the rest)."""
    blocks = pdf_doc.get("blocks")
    if not isinstance(blocks, list):
        return []
    return [b for b in blocks
            if isinstance(b, dict) and b.get("type") in BLOCK_TYPES]


def _view(ctx: Layout, block: dict) -> dict | None:
    """The payload view a block binds to, by declared id (the one indirection of R7)."""
    vid = block.get("view")
    if not isinstance(vid, str):
        return None
    views = ctx.payload.get("views") or []
    for view in views:
        if isinstance(view, dict) and view.get("id") == vid:
            return view
    for i, vdef in enumerate(ctx.definition.get("views") or []):
        if isinstance(vdef, dict) and vdef.get("id") == vid and i < len(views):
            return views[i]
    return None


def _role_colour(ctx: Layout, block: dict, index: int) -> Any:
    """The palette colour of the i-th series: the declared role when there is one (R8)."""
    roles = block.get("colors")
    roles = [roles] if isinstance(roles, str) else (roles if isinstance(roles, list) else [])
    role = roles[index] if index < len(roles) else None
    return ctx.palette.role(role, index)


def _hex(color: Any) -> str:
    """`#RRGGBB` of a palette colour, for the one place a colour rides inside markup."""
    red, green, blue = (round(channel * 255) for channel in (color.red, color.green, color.blue))
    return f"#{red:02X}{green:02X}{blue:02X}"


def _markdown(text: str, link: str) -> str:
    """The markdown subset of a layout text: bold, italics, links and line breaks (R9).

    The text is escaped first with the same escaping the fixed story uses, so a layout can never
    inject markup or HTML; only those four forms are turned back into markup."""
    out = escape(text.strip())
    out = LINK_RE.sub(rf'<link href="\2" color="{link}">\1</link>', out)
    out = BOLD_RE.sub(r"<b>\1</b>", out)
    out = ITALIC_RE.sub(r"<i>\1</i>", out)
    return out.replace("\n", "<br/>")


# --- Blocks --------------------------------------------------------------------------------------

def _header(ctx: Layout, block: dict, story: Story) -> None:
    flow: list = []
    if ctx.preview:
        flow.append(Paragraph(t("pdf.preview"), ctx.styles["preview"]))
    if block.get("logo", True):
        logo = _logo(block)
        if logo is not None:
            flow.append(logo)
        else:
            brand = " · ".join(escape(x) for x in (ctx.organization, ctx.product) if x)
            flow.append(Paragraph(brand, ctx.styles["meta"]))
    if block.get("title", True):
        flow.append(Paragraph(escape(_pdf().title_text(ctx.definition)), ctx.styles["title"]))
    subtitle = localized(ctx.definition, "description", ctx.locale)
    if block.get("subtitle", True) and subtitle:
        flow.append(Paragraph(escape(subtitle), ctx.styles["meta"]))
    if block.get("period", True):
        meta = _pdf().meta_lines(ctx.definition, ctx.payload, ctx.viewer)
        if meta:
            flow.append(Paragraph("<br/>".join(meta), ctx.styles["meta"]))
    story.add(*flow)
    story.space()


def _logo(block: dict) -> Any | None:
    """The installation logo when it is a local file; `logo_role: none` never shows it (VII)."""
    if str(block.get("logo_role") or "brand").lower() == "none":
        return None
    url = (get_settings().logo_url or "").strip()
    if not url or url.startswith(("http://", "https://", "//")):
        return None
    path = Path(url)
    if not path.is_file():
        return None
    try:
        image = Image(str(path))
        ratio = (image.imageHeight / image.imageWidth) if image.imageWidth else 1.0
        image.drawWidth, image.drawHeight = 25 * mm, 25 * mm * ratio
        return image
    except Exception:      # an unreadable image falls back to the product name
        return None


def _kpi_row(ctx: Layout, block: dict, story: Story) -> None:
    view = _view(ctx, block)
    items = _kpi_items(ctx, block, view)
    if not items:
        return
    per_row = block.get("columns") if isinstance(block.get("columns"), int) \
        and not isinstance(block.get("columns"), bool) else 0
    per_row = per_row if 1 <= per_row <= 8 else min(len(items), 4)
    for start in range(0, len(items), per_row):
        chunk = items[start:start + per_row]
        rows = [[Paragraph(escape(cell["label"]), ctx.styles["kpi_label"]) for cell in chunk],
                [Paragraph(escape(cell["value"]), ctx.styles["kpi_value"]) for cell in chunk]]
        if block.get("delta") and any(cell.get("delta") for cell in chunk):
            rows.append([Paragraph(escape(cell.get("delta") or "—"), ctx.styles["small"])
                         for cell in chunk])
        width = story.width / len(chunk)
        table = Table(rows, colWidths=[width] * len(chunk))
        table.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
            ("TEXTCOLOR", (0, 1), (-1, 1), ctx.palette.ink),
            ("LINEBELOW", (0, 1), (-1, 1), 0.6, ctx.palette.primary),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.add(table)
        story.space()


def _kpi_items(ctx: Layout, block: dict, view: dict | None) -> list[dict]:
    """One cell per requested metric of the bound view; a view without items has no cells."""
    items = (view or {}).get("items")
    if not isinstance(items, list):
        return []
    wanted = [m for m in (block.get("items") or []) if isinstance(m, str)]
    cells = []
    for item in items:
        if not isinstance(item, dict) or (wanted and item.get("metric") not in wanted):
            continue
        cells.append({
            "label": localized(item, "label", ctx.locale) or str(item.get("metric") or ""),
            "value": _pdf().fmt(item.get("value"), item.get("format", "number"), ctx.currency),
            "delta": _pdf().fmt_change(item.get("change")),
        })
    return cells


def _chart(ctx: Layout, block: dict, story: Story) -> None:
    view = _view(ctx, block)
    if not view:
        return
    labels, series = _series(ctx, block, view)
    series = _pick(block, series)
    kind = str(block.get("kind") or "").lower()
    kind = kind if kind in CHART_KINDS else DEFAULT_KIND.get(str(view.get("type")), "bar")
    height = _chart_height(block)
    if kind in ("line", "area") and labels and series:
        drawing = _line_chart(ctx, block, series, height)
    elif kind in ("pie", "donut") and labels and series:
        drawing = _pie_chart(ctx, block, labels, series[0][2], height, kind == "donut")
    elif labels and series:
        drawing = _bar_chart(ctx, block, labels, series, height)
    else:
        return          # nothing to draw: the view brings no figures for this kind
    caption = (localized(view, "summary", ctx.locale)
               or localized(view, "label", ctx.locale) or localized(view, "title", ctx.locale))
    flow = [drawing]
    if caption:
        flow.append(Paragraph(escape(t("pdf.caption", summary=caption)), ctx.styles["caption"]))
    story.add(KeepTogether(flow))
    story.space()


def _chart_height(block: dict) -> float:
    value = block.get("height_mm")
    if isinstance(value, bool) or not isinstance(value, int | float):
        value = DEFAULT_CHART_MM
    return min(max(float(value), MIN_CHART_MM), MAX_CHART_MM) * mm


def _series(ctx: Layout, block: dict, view: dict) -> tuple[list[str], list[tuple]]:
    """(category labels, [(metric id, series name, values)]) of the bound view."""
    kind = view.get("type")
    if kind == "trend":
        points = view.get("points") or []
        mid = str(view.get("metric") or "")
        return ([_axis_date(p.get("bucket")) for p in points],
                [(mid, localized(view, "label", ctx.locale) or mid,
                  [p.get("value") for p in points])])
    if kind == "ranking":
        items = view.get("items") or []
        mid = str(view.get("metric") or "")
        return ([_key(i.get("key")) for i in items],
                [(mid, localized(view, "label", ctx.locale) or mid,
                  [i.get("value") for i in items])])
    if kind == "table":
        cols = view.get("columns") or []
        rows = view.get("rows") or []
        dims = [c for c in cols if c.get("kind") != "metric"]
        mets = [c for c in cols if c.get("kind") == "metric"]
        if not dims or not mets:
            return [], []
        return ([_key(r.get(dims[0]["id"])) for r in rows],
                [(c["id"], localized(c, "label", ctx.locale) or c["id"],
                  [r.get(c["id"]) for r in rows]) for c in mets])
    if kind == "kpis":
        items = view.get("items") or []
        return ([localized(i, "label", ctx.locale) or str(i.get("metric") or "") for i in items],
                [("", "", [i.get("value") for i in items])])
    return [], []


def _axis_date(bucket) -> str:
    try:
        return _pdf().fmt_date(bucket)
    except (TypeError, ValueError):
        return _key(bucket)


def _key(value) -> str:
    return "—" if value is None else str(value)


def _pick(block: dict, series: list[tuple]) -> list[tuple]:
    """The declared `series[]` when it names any of the view's metrics, all of them otherwise."""
    wanted = [s for s in (block.get("series") or []) if isinstance(s, str)]
    picked = [s for s in series if s[0] in wanted]
    return picked or series


def _line_chart(ctx: Layout, block: dict, series: list[tuple], height: float) -> Drawing:
    width = ctx.width
    drawing = Drawing(width, height)
    plot = LinePlot()
    plot.x, plot.y = 14 * mm, 8 * mm
    plot.width, plot.height = width - 18 * mm, height - 14 * mm
    plot.data = [[(i, v or 0) for i, v in enumerate(s[2])] for s in series]
    for i, _serie in enumerate(plot.data):
        plot.lines[i].strokeColor = _role_colour(ctx, block, i)
        plot.lines[i].strokeWidth = 1.6 if i == 0 else 0.9
    plot.xValueAxis.visibleLabels = False
    plot.yValueAxis.labelTextFormat = lambda v: _pdf().fmt(v, "number")
    plot.yValueAxis.labels.fontSize = 7
    drawing.add(plot)
    return drawing


def _bar_chart(ctx: Layout, block: dict, labels: list[str], series: list[tuple],
               height: float) -> Drawing:
    width = ctx.width
    drawing = Drawing(width, height)
    horizontal = str(block.get("orientation") or "vertical").lower() == "horizontal"
    chart = HorizontalBarChart() if horizontal else VerticalBarChart()
    chart.x, chart.y = 16 * mm, 10 * mm
    chart.width, chart.height = width - 22 * mm, height - 16 * mm
    chart.data = [s[2] for s in series]
    for i, _serie in enumerate(chart.data):
        chart.bars[i].fillColor = _role_colour(ctx, block, i)
        chart.bars[i].strokeColor = ctx.palette.surface
    if block.get("stacked"):
        chart.stacked = 1
    chart.categoryAxis.categoryNames = [_trim(label) for label in labels]
    chart.categoryAxis.labels.fontSize = 6
    chart.valueAxis.labelTextFormat = lambda v: _pdf().fmt(v, "number")
    chart.valueAxis.labels.fontSize = 6
    chart.groupSpacing = 6
    drawing.add(chart)
    return drawing


def _pie_chart(ctx: Layout, block: dict, labels: list[str], values: list, height: float,
               donut: bool) -> Drawing:
    top_n = block.get("top_n")
    top_n = top_n if isinstance(top_n, int) and not isinstance(top_n, bool) else DEFAULT_TOP_N
    top_n = min(max(top_n, 2), 12)
    pairs = sorted(((v or 0, str(label)) for v, label in zip(values, labels, strict=False)),
                   key=lambda p: p[0], reverse=True)
    kept, rest = pairs[:top_n], pairs[top_n:]
    slices = [value for value, _label in kept]
    names = [label for _value, label in kept]
    if rest:
        slices.append(sum(value for value, _label in rest))
        names.append(localized(block, "other_label", ctx.locale) or t("pdf.other"))
    total = sum(slices)
    width = ctx.width
    drawing = Drawing(width, height)
    pie = Pie()
    pie.x, pie.y = 6 * mm, 4 * mm
    pie.width, pie.height = width - 70 * mm, height - 12 * mm
    pie.data = slices
    pie.labels = [f"{_trim(name)} {_pdf().fmt(v / total * 100, 'percent') if total else ''}"
                  for name, v in zip(names, slices, strict=True)]
    pie.sideLabels = 1
    pie.slices.strokeColor, pie.slices.strokeWidth = ctx.palette.surface, 0.6
    for i, _slice in enumerate(slices):
        pie.slices[i].fillColor = _role_colour(ctx, block, i)
        pie.slices[i].fontSize = 6
    drawing.add(pie)
    if donut:
        centre_x = pie.x + pie.width / 2
        centre_y = pie.y + pie.height / 2
        radius = min(pie.width, pie.height) / 4
        drawing.add(Circle(centre_x, centre_y, radius, fillColor=ctx.palette.surface,
                           strokeColor=ctx.palette.surface))
    return drawing


def _trim(label: str, limit: int = 18) -> str:
    return label if len(label) <= limit else f"{label[:limit - 1]}…"


def _table(ctx: Layout, block: dict, story: Story) -> None:
    view = _view(ctx, block)
    if not view:
        return
    columns, rows = _table_grid(ctx, block, view)
    if not columns:
        return
    widths = _column_widths(block, columns, story.width)
    head = [Paragraph(escape(localized(c, "label", ctx.locale) or c["id"]), ctx.styles["cell_head"])
            for c in columns]
    body = [[_cell(ctx, c, row) for c in columns] for row in rows]
    totals = _totals_row(ctx, block, view, columns)
    policy = str(block.get("overflow") or ctx.pdf.get("overflow") or "continue").lower()
    omitted = 0
    if policy == "truncate" and body:
        line = Paragraph(tn("pdf.more_rows", len(body)), ctx.styles["small"])
        reserve = (_height(line, story.width, story.height) + 2 * mm
                   + (_row_height(head, widths) if totals else 0.0)
                   + _tail(ctx, story))
        kept, omitted = _fit_rows(head, body, widths, _available(story, ctx) - reserve)
        body = body[:kept]
    table = Table([head, *body] + ([totals] if totals else []), colWidths=widths, repeatRows=1)
    table.setStyle(_table_style(ctx, columns, totals is not None))
    title = localized(view, "title", ctx.locale) or localized(block, "title", ctx.locale)
    flow = []
    if title:
        flow.append(Paragraph(escape(title), ctx.styles["h2"]))
    flow.append(table)
    if omitted:
        # The page is full by definition: a separator here would open a blank page.
        flow.append(Paragraph(tn("pdf.more_rows", omitted), ctx.styles["small"]))
        story.add(*flow)
        return
    story.add(*flow)
    story.space()


def _table_grid(ctx: Layout, block: dict, view: dict) -> tuple[list[dict], list[dict]]:
    """Declared columns (or the view's own) and the rows of the bound view."""
    kind = view.get("type")
    if kind == "table":
        columns, rows = list(view.get("columns") or []), list(view.get("rows") or [])
    elif kind == "ranking":
        dim, mid = view.get("dimension"), view.get("metric")
        columns = [{"id": dim, "label": view.get("dimension_label"), "kind": "dimension"},
                   {"id": mid, "label": view.get("label"), "kind": "metric",
                    "format": view.get("format", "number")}]
        rows = [{dim: i.get("key"), mid: i.get("value")} for i in view.get("items") or []]
    elif kind == "trend":
        mid, grain = view.get("metric"), view.get("grain") or "day"
        columns = [{"id": str(grain), "label": t("pdf.from"), "kind": "date"},
                   {"id": mid, "label": view.get("label"), "kind": "metric",
                    "format": view.get("format", "number")}]
        rows = [{str(grain): p.get("bucket"), mid: p.get("value")}
                for p in view.get("points") or []]
    else:
        return [], []
    wanted = [c for c in (block.get("columns") or []) if isinstance(c, str)]
    if wanted:
        picked = []
        for cid in wanted:
            match = next((c for c in columns if c["id"] == cid), None)
            if match is None and kind == "trend" and cid != view.get("metric"):
                match = {**columns[0], "id": cid}       # the grain column keeps the declared id
            if match and match["id"] not in [c["id"] for c in picked]:
                picked.append(match)
        columns = picked or columns
    return [c for c in columns if isinstance(c, dict) and "id" in c], rows


def _column_widths(block: dict, columns: list[dict], available: float) -> list[float]:
    weights = block.get("widths")
    weights = [w for w in weights if isinstance(w, int | float) and not isinstance(w, bool)] \
        if isinstance(weights, list) else []
    if len(weights) != len(columns) or not sum(weights):
        weights = [1.0] * len(columns)
    total = sum(weights)
    return [available * w / total for w in weights]


def _cell(ctx: Layout, column: dict, row: dict) -> Any:
    value = row.get(column["id"])
    if column.get("kind") == "metric":
        return _pdf().fmt(value, column.get("format", "number"), ctx.currency)
    if column.get("kind") == "date" and isinstance(value, str):
        return Paragraph(escape(_axis_date(value)), ctx.styles["cell"])
    return Paragraph(escape(_key(value)), ctx.styles["cell"])


def _totals_row(ctx: Layout, block: dict, view: dict, columns: list[dict]) -> list | None:
    """The engine's totals as the last row, outside the region ReportLab repeats."""
    if not block.get("totals") or not isinstance(view.get("totals"), dict):
        return None
    totals = view["totals"]
    label_at = next((i for i, c in enumerate(columns)
                     if not (c.get("kind") == "metric" and c["id"] in totals)), None)
    cells: list = []
    for i, column in enumerate(columns):
        if column.get("kind") == "metric" and column["id"] in totals:
            cells.append(_pdf().fmt(totals[column["id"]], column.get("format", "number"),
                                    ctx.currency))
        elif i == label_at:
            cells.append(Paragraph(escape(t("pdf.totals")), ctx.styles["cell_bold"]))
        else:
            cells.append("")
    return cells


def _table_style(ctx: Layout, columns: list[dict], has_totals: bool) -> TableStyle:
    commands = [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), ctx.palette.ink),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ctx.palette.primary),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, ctx.palette.line),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    numeric = [i for i, c in enumerate(columns) if c.get("kind") in ("metric", "date")]
    if numeric:
        commands.append(("ALIGN", (numeric[0], 0), (-1, -1), "RIGHT"))
    if has_totals:
        commands.append(("LINEABOVE", (0, -1), (-1, -1), 0.8, ctx.palette.primary))
        commands.append(("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9))
    return TableStyle(commands)


def _row_height(row: list, widths: list[float]) -> float:
    table = Table([row], colWidths=widths)
    return _height(table, sum(widths), 4000 * mm)


FRAME_PADDING = 6.0        # ReportLab's default padding inside the page frame


def _available(story: Story, ctx: Layout) -> float:
    """The room the next block really has: a probe document places a marker where it starts.

    ReportLab paginates when it builds the document, so nothing short of the frame knows the free
    height; the probe builds the story so far in a throw-away document with the same page, and the
    frame's own padding comes off the result."""
    size, margins = page_setup(ctx.definition["layout"])
    marker = Marker()
    try:
        doc = SimpleDocTemplate(io.BytesIO(), pagesize=size, leftMargin=margins["left"] * mm,
                                rightMargin=margins["right"] * mm, topMargin=margins["top"] * mm,
                                bottomMargin=margins["bottom"] * mm, invariant=1,
                                pageCompression=0)
        doc.build([*story.flowables, marker])
    except Exception:            # measuring never breaks the document: fall back to the cursor
        return story.remaining
    if marker.y is None:
        return story.remaining
    return max(marker.y - margins["bottom"] * mm - FRAME_PADDING, 0.0)


def _tail(ctx: Layout, story: Story) -> float:
    """The height the blocks declared after this one need on the same page (an upper bound)."""
    total = 0.0
    previous = ctx.index
    try:
        for offset, block in enumerate(ctx.blocks[previous + 1:], start=previous + 1):
            if block["type"] == "page_break":
                break   # what follows starts on a new page and does not constrain this one
            probe = Story(ctx.definition["layout"], ctx.styles)
            ctx.index = offset
            _BLOCKS[block["type"]](ctx, block, probe)
            total += probe.used
    finally:
        ctx.index = previous
    return total


def _fit_rows(head: list, body: list[list], widths: list[float],
              budget: float) -> tuple[int, int]:
    """How many rows fit the remaining height; the rest is counted, never drawn (T029)."""
    if budget <= 0 or not body:
        return 0, len(body)
    probe = Table([head, *body], colWidths=widths, repeatRows=1)
    probe.wrap(sum(widths), 4000 * mm)
    heights = list(getattr(probe, "_rowHeights", None) or [])
    if len(heights) != len(body) + 1:
        return len(body), 0
    used, kept = heights[0], 0
    for height in heights[1:]:
        if used + height > budget:
            break
        used += height
        kept += 1
    return kept, len(body) - kept


def _text(ctx: Layout, block: dict, story: Story) -> None:
    text = localized(block, "text", ctx.locale)
    if not text:
        return
    style = block.get("style") if block.get("style") in ("heading", "paragraph", "caption") \
        else "paragraph"
    base = ctx.styles["heading" if style == "heading"
                      else ("text_caption" if style == "caption" else "text")]
    paragraph_style = ParagraphStyle(
        f"b26-{block.get('id', 'text')}", parent=base,
        alignment=ALIGN.get(str(block.get("align") or "left").lower(), TA_LEFT))
    font = FONTS.get(str(block.get("font_name") or "").lower())
    if font:
        paragraph_style.fontName = font
    story.add(Paragraph(_markdown(text, _hex(ctx.palette.primary)), paragraph_style))


def _page_break(ctx: Layout, block: dict, story: Story) -> None:
    story.add(PageBreak())


def _footer(ctx: Layout, block: dict, story: Story) -> None:
    parts = []
    if block.get("generated_at", True):
        now = datetime.now(ZoneInfo(get_settings().timezone))
        parts.append(t("pdf.generated", date=_pdf().fmt_date(now.date()),
                       time=now.strftime("%H:%M")))
    legal = localized(block, "legal", ctx.locale)
    if legal:
        parts.append(escape(legal))
    if parts:
        story.add(Spacer(1, 2 * mm), Paragraph(" · ".join(parts), ctx.styles["small"]))
    if block.get("page_numbers"):
        story.add(PageNumber(ctx.styles["small"], t("pdf.page")))


# ------------------------------------------------------- visual blocks (feature 044)


def _metric_item(view: dict | None, metric: object) -> dict | None:
    """The `kpis` item a gauge, index or share block binds to, by metric id."""
    items = (view or {}).get("items")
    if not isinstance(items, list) or not isinstance(metric, str):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("metric") == metric:
            return item
    return None


def _scale(block: dict) -> tuple[float, float]:
    """`min`/`max` of the gauge and index scales: 0 to 100 when the report says nothing."""
    low = block.get("min")
    high = block.get("max")
    low = float(low) if isinstance(low, int | float) and not isinstance(low, bool) else 0.0
    high = float(high) if isinstance(high, int | float) and not isinstance(high, bool) else 100.0
    return (low, high) if high > low else (low, low + 100.0)


def _ratio(value: object, low: float, high: float) -> float | None:
    """Where the value sits on its scale, clamped to 0-1; None when it is not a number."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:      # NaN
        return None
    return min(1.0, max(0.0, (number - low) / (high - low)))


def _mix(ctx: Layout, roles: tuple[str, ...], position: float) -> Any:
    """A colour inside a role run: the palette steps between the declared roles."""
    steps = len(roles) - 1
    if steps <= 0:
        return ctx.palette.role(roles[0] if roles else None)
    span = min(max(position, 0.0), 1.0) * steps
    index = min(int(span), steps - 1)
    share = span - index
    left, right = ctx.palette.role(roles[index]), ctx.palette.role(roles[index + 1])
    return _blend(left, right, share)


def _blend(left, right, share: float):
    from reportlab.lib.colors import Color
    return Color(left.red + (right.red - left.red) * share,
                 left.green + (right.green - left.green) * share,
                 left.blue + (right.blue - left.blue) * share)


def _swatch(ctx: Layout, role: str, index: int):
    return ctx.palette.role(role, index)


def _gauge(ctx: Layout, block: dict, story: Story) -> None:
    """Semicircular gauge: five equal bands by role, a needle at the value, the figure inside."""
    item = _metric_item(_view(ctx, block), block.get("metric"))
    if item is None:
        return
    low, high = _scale(block)
    ratio = _ratio(item.get("value"), low, high)
    radius = min(GAUGE_MAX_RADIUS, (ctx.width - 6 * mm) / 2)
    centre_x, centre_y = ctx.width / 2, 2 * mm
    height = centre_y + radius + 2 * mm
    drawing = Drawing(ctx.width, height)
    bands = len(GAUGE_ROLES)
    for i, role in enumerate(GAUGE_ROLES):
        band = Wedge(centre_x, centre_y, radius, 180 - (i + 1) * 180 / bands,
                     180 - i * 180 / bands)
        band.fillColor = _swatch(ctx, role, i)
        band.strokeColor = None
        drawing.add(band)
    # The bands are pie slices, so a half disc punched out of them leaves the ring: only the
    # half above the chord is painted, which keeps the block's box tight.
    hole = Wedge(centre_x, centre_y, radius * GAUGE_HOLE, 0, 180)
    hole.fillColor = ctx.palette.surface
    hole.strokeColor = None
    drawing.add(hole)
    if ratio is not None:
        angle = math.pi * (1 - ratio)
        needle = Line(centre_x, centre_y, centre_x + radius * math.cos(angle),
                      centre_y + radius * math.sin(angle))
        needle.strokeColor = ctx.palette.ink
        needle.strokeWidth = 2
        drawing.add(needle)
    hub = Circle(centre_x, centre_y, 2.4 * mm)
    hub.fillColor = ctx.palette.ink
    hub.strokeColor = None
    drawing.add(hub)
    shown = _pdf().fmt(item.get("value"), item.get("format", "number"), ctx.currency)
    figure = String(centre_x, centre_y + radius * 0.12, shown,
                    fontSize=_figure_size(radius, shown), textAnchor="middle")
    figure.fillColor = ctx.palette.ink
    figure.fontName = "Helvetica-Bold"
    drawing.add(figure)
    story.add(KeepTogether([drawing]))
    _caption(ctx, story, _item_label(ctx, item, block), centred=True)
    story.space()


def _figure_size(radius: float, shown: str) -> float:
    """The figure's font size: big in the middle of the arc, shrunk so a long one still fits."""
    room = radius * GAUGE_HOLE * 1.6
    return max(6.0, min(radius * 0.26, room / (0.58 * max(len(shown), 1))))


def _index(ctx: Layout, block: dict, story: Story) -> None:
    """Two-ended index bar: the figure, a band from one role to the other, a marker."""
    item = _metric_item(_view(ctx, block), block.get("metric"))
    if item is None:
        return
    low, high = _scale(block)
    ratio = _ratio(item.get("value"), low, high)
    width = ctx.width
    height = 22 * mm
    drawing = Drawing(width, height)
    label = _item_label(ctx, item, block)
    shown = _pdf().fmt(item.get("value"), item.get("format", "number"), ctx.currency)
    figure = String(0, height - 4 * mm, shown, fontSize=15, textAnchor="start")
    figure.fillColor = ctx.palette.ink
    figure.fontName = "Helvetica-Bold"
    drawing.add(figure)
    if label:
        sub = String(0, height - 8.5 * mm, label, fontSize=7.5, textAnchor="start")
        sub.fillColor = ctx.palette.muted
        drawing.add(sub)
    bar_y, bar_h = 5 * mm, 2.6 * mm
    slice_w = width / INDEX_SLICES
    for i in range(INDEX_SLICES):
        piece = Rect(i * slice_w, bar_y, slice_w + 0.4, bar_h)
        piece.fillColor = _mix(ctx, INDEX_ROLES, (i + 0.5) / INDEX_SLICES)
        piece.strokeColor = None
        drawing.add(piece)
    if ratio is not None:
        marker = Rect(width * ratio - 0.5 * mm, bar_y - 1.4 * mm, 1 * mm, bar_h + 2.8 * mm)
        marker.fillColor = ctx.palette.ink
        marker.strokeColor = None
        drawing.add(marker)
    for text, anchor_x, align in ((localized(block, "low_label", ctx.locale), 0, "start"),
                                  (localized(block, "high_label", ctx.locale), width, "end")):
        if not text:
            continue
        end = String(anchor_x, 1 * mm, str(text), fontSize=7.5, textAnchor=align)
        end.fillColor = ctx.palette.muted
        drawing.add(end)
    story.add(KeepTogether([drawing]))
    story.space()


def _share(ctx: Layout, block: dict, story: Story) -> None:
    """Share bar: the figures by segment and a stacked bar whose rest is the declared label."""
    view = _view(ctx, block)
    wanted = [m for m in (block.get("items") or []) if isinstance(m, str)]
    segments = []
    total = 0.0
    for i, metric in enumerate(wanted):
        item = _metric_item(view, metric)
        if item is None:
            continue
        value = item.get("value")
        try:
            number = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            number = 0.0
        total += number
        segments.append({"label": _item_label(ctx, item, block), "value": number,
                         "colour": _swatch(ctx, SHARE_ROLES[i % len(SHARE_ROLES)], i)})
    if not segments:
        return
    rest_label = localized(block, "remainder_label", ctx.locale)
    if rest_label:
        segments.append({"label": str(rest_label), "value": max(0.0, 100.0 - total),
                         "colour": _swatch(ctx, SHARE_ROLES[len(segments) % len(SHARE_ROLES)],
                                           len(segments))})
    width = ctx.width
    height = 20 * mm
    drawing = Drawing(width, height)
    cell = width / len(segments)
    for i, segment in enumerate(segments):
        dot = Circle(i * cell + 1.2 * mm, height - 2.4 * mm, 1.1 * mm)
        dot.fillColor = segment["colour"]
        dot.strokeColor = None
        drawing.add(dot)
        caption = String(i * cell + 3.6 * mm, height - 3.1 * mm, segment["label"][:28],
                         fontSize=7, textAnchor="start")
        caption.fillColor = ctx.palette.muted
        drawing.add(caption)
        figure = String(i * cell, height - 8 * mm,
                        _pdf().fmt(segment["value"], "percent", ctx.currency), fontSize=11,
                        textAnchor="start")
        figure.fillColor = ctx.palette.ink
        figure.fontName = "Helvetica-Bold"
        drawing.add(figure)
    bar_x, bar_y, bar_h = 0.0, 1 * mm, 3 * mm
    for segment in segments:
        part = min(100.0, max(0.0, segment["value"])) / 100 * width
        if part <= 0:
            continue
        piece = Rect(bar_x, bar_y, part, bar_h)
        piece.fillColor = segment["colour"]
        piece.strokeColor = None
        drawing.add(piece)
        bar_x += part
    story.add(KeepTogether([drawing]))
    story.space()


def _asset(ctx: Layout, block: dict, story: Story) -> None:
    """Asset tiles: logo, name, figure and signed badge, `limit` rows of the bound table."""
    view = _view(ctx, block)
    rows = (view or {}).get("rows")
    if not isinstance(rows, list) or not rows:
        return
    roles = _asset_roles(block)
    limit = block.get("limit")
    limit = limit if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0 \
        else ASSET_LIMIT
    visible = [r for r in rows[:limit] if isinstance(r, dict)]
    if not visible:
        return
    cells = [_asset_cell(ctx, block, roles, row) for row in visible]
    width = ctx.width / ASSET_COLUMNS
    grid = []
    for start in range(0, len(cells), ASSET_COLUMNS):
        chunk = cells[start:start + ASSET_COLUMNS]
        chunk += [[] for _ in range(ASSET_COLUMNS - len(chunk))]
        grid.append(chunk)
    table = Table(grid, colWidths=[width] * ASSET_COLUMNS)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.add(KeepTogether([table]))
    story.space()


def _asset_roles(block: dict) -> dict[str, str | None]:
    """`columns` is positional for an asset tile: image, title, subtitle, value, delta."""
    columns = [c if isinstance(c, str) and c else None for c in (block.get("columns") or [])]
    columns += [None] * (5 - len(columns))
    return dict(zip(("image", "title", "subtitle", "value", "delta"), columns, strict=False))


def _asset_cell(ctx: Layout, block: dict, roles: dict[str, str | None],
                row: dict) -> list:
    """One tile: the logo (or its initial), the name, the figure and the badge."""
    out = []
    key = roles.get("image")
    title = _cell_text(row, roles.get("title"))
    logo = _asset_logo(ctx, row.get(key) if key else None, block.get("image"), title)
    if logo is not None:
        out.append(logo)
    if title:
        out.append(Paragraph(escape(title), ctx.styles["cell_bold"]))
    subtitle = _cell_text(row, roles.get("subtitle"))
    if subtitle:
        out.append(Paragraph(escape(subtitle), ctx.styles["text_caption"]))
    figure = row.get(roles.get("value")) if roles.get("value") else None
    out.append(Paragraph(escape(_pdf().fmt(figure, "number", ctx.currency)),
                         ctx.styles["kpi_value"]))
    badge = _badge(ctx, row.get(roles.get("delta")) if roles.get("delta") else None)
    if badge is not None:
        out.append(badge)
    return out


def _cell_text(row: dict, column: str | None) -> str:
    if not column:
        return ""
    value = row.get(column)
    return "" if value is None else str(value)


def _badge(ctx: Layout, value: object) -> Any | None:
    """The signed badge: a triangle pointing up or down, in the palette pair of its sign.

    The standard PDF fonts carry no ▲/▼ glyph, so the arrow is drawn as a triangle instead of
    typed: the badge reads the same as the screen tile (044 FR-003)."""
    try:
        number = float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None
    if number is None:
        return None
    up = number >= 0
    ink = ctx.palette.positive if up else ctx.palette.negative
    backing = ctx.palette.kpi_delta_bg_positive if up else ctx.palette.kpi_delta_bg_negative
    text = _pdf().fmt(number, "percent", ctx.currency)
    width = BADGE_WIDTH
    drawing = Drawing(width, BADGE_HEIGHT)
    pill = Rect(0, 0, width, BADGE_HEIGHT, rx=BADGE_HEIGHT / 2, ry=BADGE_HEIGHT / 2)
    pill.fillColor = backing
    pill.strokeColor = None
    drawing.add(pill)
    triangle = Polygon([BADGE_ARROW_X, BADGE_HEIGHT / 2 - BADGE_ARROW / 2,
                        BADGE_ARROW_X + BADGE_ARROW, BADGE_HEIGHT / 2 - BADGE_ARROW / 2,
                        BADGE_ARROW_X + BADGE_ARROW / 2, BADGE_HEIGHT / 2 + BADGE_ARROW / 2]
                       if up else
                       [BADGE_ARROW_X, BADGE_HEIGHT / 2 + BADGE_ARROW / 2,
                        BADGE_ARROW_X + BADGE_ARROW, BADGE_HEIGHT / 2 + BADGE_ARROW / 2,
                        BADGE_ARROW_X + BADGE_ARROW / 2, BADGE_HEIGHT / 2 - BADGE_ARROW / 2])
    triangle.fillColor = ink
    triangle.strokeColor = None
    drawing.add(triangle)
    figure = String(BADGE_ARROW_X + BADGE_ARROW + 1.2 * mm, BADGE_HEIGHT / 2 - 2.2, text,
                    fontSize=7, textAnchor="start")
    figure.fillColor = ink
    drawing.add(figure)
    return drawing


def _asset_logo(ctx: Layout, value: object, image_set: object, title: str) -> Any | None:
    """The embedded raster when the row carries one, the initial circle otherwise.

    The payload inlines project images as data URIs so the PDF embeds exactly the bytes the
    screen shows (042 R5 keeps the client from guessing a path); anything else — a site path, a
    third-party address — draws the `initial` fallback of FR-005."""
    blob = _data_uri(value)
    if blob is not None:
        try:
            reader = ImageReader(io.BytesIO(blob))
            size = reader.getSize()
            image = Image(io.BytesIO(blob), width=ASSET_LOGO, height=ASSET_LOGO,
                          kind="bound")
            if size:      # keep the aspect and round it: the tiles show a circle
                image.drawHeight = ASSET_LOGO
                image.drawWidth = ASSET_LOGO
            return image
        except Exception:      # an unreadable image is a fallback, never a failed document
            log.warning("asset image in set %s could not be embedded", image_set)
    return _initial_circle(ctx, title)


def _data_uri(value: object) -> bytes | None:
    if not isinstance(value, str):
        return None
    match = DATA_URI_RE.match(value.strip())
    if match is None:
        return None
    try:
        return base64.b64decode(match.group(2), validate=False)
    except (ValueError, TypeError):
        return None


def _initial_circle(ctx: Layout, name: str) -> Any | None:
    """FR-005 `initial`: a circle in a palette colour by hash of the key, its first letter in it."""
    letter = (name or "?").strip()[:1].upper() or "?"
    colour = ctx.palette.series[sum(name.encode("utf-8")) % len(ctx.palette.series)]
    drawing = Drawing(ASSET_LOGO, ASSET_LOGO)
    circle = Circle(ASSET_LOGO / 2, ASSET_LOGO / 2, ASSET_LOGO / 2)
    circle.fillColor = colour
    circle.strokeColor = None
    drawing.add(circle)
    initial = String(ASSET_LOGO / 2, ASSET_LOGO / 2 - 2.4, letter, fontSize=11,
                     textAnchor="middle")
    initial.fillColor = ctx.palette.surface
    initial.fontName = "Helvetica-Bold"
    drawing.add(initial)
    return drawing


def _item_label(ctx: Layout, item: dict, block: dict) -> str:
    """The label under a figure: the metric's own, then the block's title."""
    return (localized(item, "label", ctx.locale) or localized(block, "title", ctx.locale)
            or str(item.get("metric") or ""))


def _caption(ctx: Layout, story: Story, text: str, centred: bool = False) -> None:
    if not text:
        return
    style = ctx.styles["caption"]
    if centred:
        style = ParagraphStyle("cap26c", parent=style, alignment=TA_CENTER)
    story.add(Paragraph(escape(text), style))


_BLOCKS = {"header": _header, "kpi_row": _kpi_row, "chart": _chart, "table": _table,
           "text": _text, "page_break": _page_break, "footer": _footer,
           "gauge": _gauge, "index": _index, "share": _share, "asset": _asset}
