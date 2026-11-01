"""`bizview theme preview`: the admin page's preview card, drawn offline (feature 047).

The author iterates without a server, so the card here is the same picture the appearance page
shows — a KPI figure with its badge, a four-bar chart and a two-series sparkline — drawn with the
theme's own tokens, light beside dark. SVG on purpose: no browser, no rasteriser, no dependency, and
the file opens in anything.
"""

from __future__ import annotations

from bizview_cli.theme import contrast, derive_tokens, shape_of

WIDTH = 360
HEIGHT = 220
PAD = 16


def _card(tokens: dict, mode: str, x: int, y: int, shape: dict, title: str) -> list[str]:
    """One preview card at (x, y): surface, title, KPI with badge, bars, sparkline."""
    width, height = WIDTH, HEIGHT
    radius = {"sm": 4, "md": 8, "lg": 14}[shape["radius"]]
    gap = 10 if shape["density"] == "compact" else 16
    kpi = {"md": 20, "lg": 26, "xl": 32}[shape["kpi_scale"]]
    badge_fill = tokens["positive"] if shape["badge"] == "filled" else "none"
    badge_text = (tokens["kpi_delta_bg"]["positive"] if shape["badge"] == "filled"
                  else tokens["positive"])
    ink = tokens["text"]
    parts = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" '
        f'fill="{tokens["surface"]}" stroke="{tokens["grid"]}"/>',
        f'<text x="{x + PAD}" y="{y + 22}" font-family="sans-serif" font-size="11" '
        f'fill="{tokens["muted"]}">{title}</text>',
        # KPI figure
        f'<text x="{x + PAD}" y="{y + 22 + gap + kpi}" font-family="sans-serif" '
        f'font-weight="700" font-size="{kpi}" fill="{ink}">1 234</text>',
        f'<rect x="{x + PAD}" y="{y + 30 + gap + kpi}" width="46" height="16" rx="4" '
        f'fill="{badge_fill}" stroke="{tokens["positive"]}"/>',
        f'<text x="{x + PAD + 23}" y="{y + 41 + gap + kpi}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="10" fill="{badge_text}">+12 %</text>',
    ]
    # four bars, drawn with the first four series colours
    base = y + height - PAD
    bar_w = 26
    for index in range(4):
        height_bar = 24 + index * 12
        parts.append(
            f'<rect x="{x + PAD + index * (bar_w + 8)}" y="{base - height_bar}" width="{bar_w}" '
            f'height="{height_bar}" rx="{max(2, radius // 2)}" '
            f'fill="{tokens["series"][index % len(tokens["series"])]}"/>')
    # two-series sparkline on the right
    x0, y0 = x + WIDTH // 2 + 10, y + 52
    for offset, colour in ((0, tokens["series"][0]), (8, tokens["series"][1])):
        points = " ".join(
            f"{x0 + step * 14},{y0 + 60 - (20 + ((step * 7 + offset) % 40)) - offset}"
            for step in range(9))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{colour}" '
                     f'stroke-width="2"/>')
    parts.append(f'<line x1="{x + PAD}" y1="{base}" x2="{x + width - PAD}" y2="{base}" '
                 f'stroke="{tokens["grid"]}"/>')
    return parts


def preview_svg(theme: dict) -> str:
    """The two cards side by side, each labelled with the measured text contrast."""
    shape = shape_of(theme)
    body: list[str] = []
    for index, mode in enumerate(("light", "dark")):
        tokens = derive_tokens(theme, mode)
        tokens["series"] = [theme[mode]["series"][i % len(theme[mode]["series"])]
                            for i in range(4)]
        ratio = contrast(theme[mode]["text"], theme[mode]["surface"])
        label = f"{mode} · text {ratio:.1f}:1"
        body += _card(tokens, mode, PAD + index * (WIDTH + PAD), PAD, shape, label)
    width = WIDTH * 2 + PAD * 3
    height = HEIGHT + PAD * 2
    background = theme["light"]["surface"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="Theme {theme.get("id")} in light and dark">'
            f'<rect width="{width}" height="{height}" fill="{background}"/>'
            + "".join(body) + "</svg>\n")
