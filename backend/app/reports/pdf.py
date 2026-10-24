"""Report PDF (feature 005 FR-016): ReportLab, built from the SAME view payloads the screen gets,
so figures always match. Real text, logical reading order, AA contrast, the trend as a vector
chart plus its data table, title/author/language metadata (feature 001 research R9)."""
import io
from datetime import date, datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config import get_settings
from app.i18n import M, current, localized, t, use_locale
from app.reports.palette import ReportPalette, resolve
from app.reports.pdf_layout import DEFAULT_MARGINS, page_setup, pdf_document, render_layout

DASH = "\u2013"
PERIOD_LABELS = {
    "today": "Hoy",
    "yesterday": "Ayer",
    "last_7_days": "Últimos 7 días",
    "mtd": "Mes en curso",
    "last_month": "Mes anterior",
    "qtd": "Trimestre en curso",
    "ytd": "Año en curso",
    "last_12_months": "Últimos 12 meses",
    "custom": "Personalizado",
}


def _group(n: float, decimals: int) -> str:
    if current() == "en":
        text = f"{abs(n):,.{decimals}f}"
        return ("-" if n < 0 else "") + text
    text = f"{abs(n):,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return ("-" if n < 0 else "") + text


def fmt(value, kind: str = "number", currency: str = "USD") -> str:
    """Number formatting that follows the current report language."""
    if value is None:
        return "—"
    if kind == "text" or isinstance(value, str):
        return str(value)
    v = float(value)
    if kind == "currency":
        return f"{_group(v, 2)} {currency}"
    if kind == "integer":
        return _group(round(v), 0)
    if kind == "percent":
        return t("pdf.percent", value=_group(v, 1))
    return _group(v, 2) if v % 1 else _group(v, 0)


def fmt_change(change: dict | None) -> str:
    if not change:
        return "—"
    if change.get("new"):
        return t("pdf.new")
    if change.get("pct") is None:
        return "—"
    return ("+" if change["pct"] > 0 else "") + t("pdf.percent", value=_group(change["pct"], 1))


def fmt_date(d: str | date) -> str:
    d = date.fromisoformat(d) if isinstance(d, str) else d
    months = t("pdf.months").split(",")
    day = f"{d.day:02d}" if current() == "es" else str(d.day)
    return t("pdf.date", day=day, month=months[d.month - 1], year=str(d.year))


def _freshness_line(freshness: dict) -> str | None:
    """Dataset: last integration run (unchanged); direct (feature 019 FR-010): live or stale."""
    mode = freshness.get("mode")
    if mode != "direct":
        updated = freshness.get("updated_at")
        if not updated:
            return None
        u = datetime.fromisoformat(updated) if isinstance(updated, str) else updated
        return t("pdf.updated", date=fmt_date(u.date()), time=u.strftime("%H:%M"))

    time_raw = freshness.get("queried_at") or freshness.get("updated_at")
    if not time_raw:
        return None
    moment = datetime.fromisoformat(time_raw) if isinstance(time_raw, str) else time_raw
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo("UTC"))
    local_tz = ZoneInfo(get_settings().timezone)
    moment = moment.astimezone(local_tz)
    formatted = moment.strftime(t("pdf.datetime"))

    if freshness.get("stale"):
        return t("pdf.stale", when=formatted)

    source = freshness.get("source") or t("pdf.the_source")
    if source == "bi":
        source = str(M("report.bi_source"))
    return t("pdf.live", source=escape(source), when=formatted)


def _styles(palette: ReportPalette):
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], textColor=palette.ink, fontSize=18,
                                alignment=0, spaceAfter=2 * mm),
        "meta": ParagraphStyle("m", parent=base["Normal"], textColor=palette.muted, fontSize=9,
                               leading=12),
        "h2": ParagraphStyle("h", parent=base["Heading2"], textColor=palette.ink, fontSize=12,
                             spaceBefore=5 * mm, spaceAfter=2 * mm),
        "cell": ParagraphStyle("c", parent=base["Normal"], textColor=palette.ink, fontSize=9,
                               leading=11),
        "preview": ParagraphStyle("p", parent=base["Normal"], textColor=palette.primary,
                                  fontName="Helvetica-Bold", fontSize=10, leading=13),
    }


def _table(rows: list[list], widths: list[float], palette: ReportPalette,
           numeric_from: int = 1) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), palette.ink),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, palette.primary),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, palette.line),
        ("ALIGN", (numeric_from, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _trend_chart(view: dict, palette: ReportPalette) -> Drawing:
    width, height = 170 * mm, 55 * mm
    d = Drawing(width, height)
    plot = LinePlot()
    plot.x, plot.y, plot.width, plot.height = 14 * mm, 8 * mm, width - 18 * mm, height - 14 * mm
    cur = [(i, p["value"] or 0) for i, p in enumerate(view["points"])]
    data = [cur]
    if any("previous" in p for p in view["points"]):
        data.append([(i, p.get("previous") or 0) for i, p in enumerate(view["points"])])
    if len(cur) < 2:
        data = [[*s, (1, s[0][1] if s else 0)] for s in data]
    plot.data = data
    plot.lines[0].strokeColor, plot.lines[0].strokeWidth = palette.primary, 1.6
    if len(data) > 1:
        plot.lines[1].strokeColor, plot.lines[1].strokeWidth = palette.muted, 0.8
        plot.lines[1].strokeDashArray = (3, 2)
    plot.xValueAxis.visibleLabels = False
    plot.yValueAxis.labelTextFormat = lambda v: fmt(v, "number")
    plot.yValueAxis.labels.fontSize = 7
    d.add(plot)
    d.add(String(14 * mm, height - 4 * mm, t("pdf.legend_current") + (
        t("pdf.legend_previous") if len(data) > 1 else ""),
                 fontSize=7, fillColor=palette.muted))
    return d


def _layout_views(views: list, order) -> list:
    """Views in layout order; defaults to every view when order is not a list of valid ints."""
    if not isinstance(order, list):
        return list(views)
    result = []
    seen: set[int] = set()
    for item in order:
        if isinstance(item, bool) or not isinstance(item, int):
            continue
        if 0 <= item < len(views) and item not in seen:
            result.append(views[item])
            seen.add(item)
    return result


def title_text(definition: dict) -> str:
    """Report title in the request language (feature 022 falls back to the authored text)."""
    return localized(definition, "title") or definition["title"]


def meta_lines(definition: dict, payload: dict, viewer: str | None) -> list[str]:
    """Period, comparison, active filters, viewer and freshness of the request (both stories)."""
    sel = payload["selection"]
    period_id = sel.get("period")
    period_name_raw = PERIOD_LABELS.get(period_id)
    if period_name_raw:
        period_name = t(f"pdf.period.{period_id}")
    else:
        period_name = escape(period_id or "")
    period_dates = (f"{fmt_date(sel['current']['from'])} {DASH} "
                    f"{fmt_date(sel['current']['to'])}")
    if sel.get("partial"):
        period_dates += t("pdf.in_progress")
    if period_name:
        meta = [t("pdf.period_named", name=period_name, dates=period_dates)]
    else:
        meta = [t("pdf.period", dates=period_dates)]
    if sel.get("previous"):
        meta.append(t("pdf.compared", dates=f"{fmt_date(sel['previous']['from'])} {DASH} "
                                            f"{fmt_date(sel['previous']['to'])}"))
    else:
        meta.append(t("pdf.no_compare"))
    for dim, value in sorted((payload.get("filters") or {}).items()):
        values = value if isinstance(value, list) else [value]
        label = localized(definition["dimensions"].get(dim, {}), "label") or dim
        meta.append(f"{escape(label)}: {', '.join(escape(str(v)) for v in values)}")
    if viewer and viewer.strip():
        meta.append(t("pdf.viewer", name=escape(viewer.strip())))
    freshness_line = _freshness_line(payload.get("freshness") or {})
    if freshness_line:
        meta.append(freshness_line)
    return meta


def render(definition: dict, payload: dict, *, organization: str, product: str,
           viewer: str | None = None, preview: bool = False, layout: dict | None = None,
           locale: str | None = None, palette: ReportPalette | None = None) -> bytes:
    """`definition` = report definition JSON; `payload` = the data response (selection, views).

    `palette` is the resolved preset (030): callers pass the installation's one; without it the
    report's own `layout.theme.palette` resolves, falling back to `impacto`."""
    loc = locale or current()
    with use_locale(loc):
        pal = palette if palette is not None else resolve(definition)
        st = _styles(pal)
        cur = definition.get("currency", "USD")
        sel = payload["selection"]
        legacy = layout or definition.get("pdf_layout") or {}
        declarative = pdf_document(definition)
        if declarative is not None:
            # R2: layout.pdf.page wins over pdf.orientation, and pdf.views is ignored.
            pagesize, margins = page_setup(definition["layout"])
        else:
            pagesize, margins = (landscape(A4) if legacy.get("orientation") == "landscape"
                                 else A4), dict(DEFAULT_MARGINS)
        title = title_text(definition)
        doc_title = f"{title} ({t('pdf.preview')})" if preview else title
        subject = localized(definition, "description") or definition.get("description")
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=margins["left"] * mm,
                                rightMargin=margins["right"] * mm,
                                topMargin=margins["top"] * mm,
                                bottomMargin=margins["bottom"] * mm, title=doc_title,
                                author=organization or product, subject=subject,
                                creator=product, lang=loc, invariant=1, pageCompression=0)
        if declarative is not None:
            story = render_layout(definition=definition, payload=payload, styles=st,
                                  organization=organization, product=product, viewer=viewer,
                                  preview=preview, locale=loc, palette=pal)
            doc.build(story)
            return buf.getvalue()
        meta = meta_lines(definition, payload, viewer)
        story = []
        if preview:
            story.append(Paragraph(t("pdf.preview"), st["preview"]))
        story += [Paragraph(escape(title), st["title"]),
                  Paragraph(" · ".join(escape(x) for x in (organization, product) if x),
                            st["meta"]),
                  Paragraph("<br/>".join(meta), st["meta"]), Spacer(1, 3 * mm)]
        compare = bool(sel.get("previous"))
        for view in _layout_views(payload["views"], legacy.get("views")):
            if view["type"] == "kpis":
                head = [t("pdf.indicator"), t("pdf.value")] + (
                    [t("pdf.previous"), t("pdf.change")] if compare else [])
                rows = [head] + [[localized(k, "label") or k["label"],
                                  fmt(k["value"], k["format"], cur)]
                                 + ([fmt(k["previous"], k["format"], cur),
                                     fmt_change(k["change"])] if compare else [])
                                 for k in view["items"]]
                story += [Paragraph(t("pdf.summary"), st["h2"]),
                          _table(rows, [70 * mm, 40 * mm] +
                                 ([40 * mm, 30 * mm] if compare else []), pal)]
            elif view["type"] == "trend":
                view_label = localized(view, "label") or view["label"]
                head = [t("pdf.from"), view_label] + ([t("pdf.previous")] if compare else [])
                rows = [head] + [[fmt_date(p["bucket"]), fmt(p["value"], view["format"], cur)]
                                 + ([fmt(p.get("previous"), view["format"], cur)]
                                    if compare else [])
                                 for p in view["points"]]
                story += [KeepTogether([
                    Paragraph(t("pdf.trend", label=escape(view_label)), st["h2"]),
                    _trend_chart(view, pal)]),
                          _table(rows, [50 * mm, 50 * mm] + ([50 * mm] if compare else []), pal)]
            elif view["type"] == "ranking":
                view_label = localized(view, "label") or view["label"]
                view_title = localized(view, "title") or view["title"]
                dim_label = localized(view, "dimension_label") or view["dimension_label"]
                head = ["#", dim_label, view_label, t("pdf.share")] + (
                    [t("pdf.change")] if compare else [])
                rows = [head] + [[str(i + 1), Paragraph(
                    escape(str(it["key"] if it["key"] is not None else "—")), st["cell"]),
                                  fmt(it["value"], view["format"], cur),
                                  fmt(it["share"], "percent")]
                                 + ([fmt_change(it["change"])] if compare else [])
                                 for i, it in enumerate(view["items"])]
                story += [Paragraph(escape(view_title), st["h2"]),
                          _table(rows, [8 * mm, 82 * mm, 36 * mm, 26 * mm]
                                 + ([26 * mm] if compare else []), pal, numeric_from=2)]
            elif view["type"] == "table":
                cols = view["columns"]
                dims = sum(1 for c in cols if c["kind"] == "dimension")
                rows = [[localized(c, "label") or c["label"] for c in cols]] + [
                    [Paragraph(
                        escape(str(r.get(c["id"]) if r.get(c["id"]) is not None else "—")),
                        st["cell"]) if c["kind"] == "dimension"
                     else fmt(r.get(c["id"]), c.get("format", "number"), cur) for c in cols]
                    for r in view["rows"]]
                width = doc.width / len(cols)
                view_title = localized(view, "title") or view.get("title") or t("pdf.detail")
                story += [Paragraph(escape(view_title), st["h2"]),
                          _table(rows, [width] * len(cols), pal, numeric_from=dims)]
        doc.build(story)
        return buf.getvalue()
