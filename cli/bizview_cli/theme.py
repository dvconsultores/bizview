"""Themes as data (feature 047): the contract, and the tokens the renderers paint with.

A theme is a file of colour tokens and fixed shape choices — never CSS, never a font file, never
markup — so a person or any AI can write one outside BizView and it enters only through this
validation. Two layers, one answer:

1. `theme.schema.json` refuses the *shape* (unknown key, a colour that is not `#RRGGBB`, two
   series);
2. the rules below refuse a *look* no schema can express — text against its surface, a series
   against the card it is drawn on and against its neighbour, positive against negative — and every
   refusal names the tokens and the value measured, because that is what an author can act on.

`derive_tokens` turns the authored tokens into the runtime roles the web components and the PDF
already consume (`series1..8`, `kpi_text`, `kpi_delta_bg`, …), so the authored contract can change
without touching a renderer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from itertools import pairwise
from typing import Any

import yaml
from jsonschema import Draft202012Validator

COLOUR_TOKENS = ("surface", "card", "text", "muted", "grid", "primary", "positive", "negative",
                 "neutral", "delta_positive", "delta_negative")
MODES = ("light", "dark")
SHAPE_LISTS = {
    "radius": ("sm", "md", "lg"),
    "density": ("compact", "normal"),
    "kpi_scale": ("md", "lg", "xl"),
    "font": ("sans", "serif", "mono"),
    "badge": ("filled", "outline"),
}
SHAPE_DEFAULTS = {"radius": "md", "density": "normal", "kpi_scale": "lg", "font": "sans",
                  "badge": "filled"}
MAX_BYTES = 20 * 1024

#: The product's accessibility bar, the same one its own presets are held to (feature 030's gate:
#: `frontend/tests/unit/palette-presets.test.ts`). Changing a number here changes what the product
#: accepts, so the two must move together.
TEXT_CONTRAST = 4.5          # text against its surface (WCAG AA)
SERIES_CONTRAST = 3.0        # a series against the surface it is drawn on
SERIES_CONTRAST_STRICT = 7.0  # the theme that exists to be readable
SERIES_DELTA_E = 10.0        # adjacent series must look different
SEQUENTIAL_STEP = 5.0        # a single-hue ramp is checked on L* steps instead
POLARITY_DELTA_E = 25.0      # positive and negative must not be confusable
DELTA_CONTRAST = 4.5         # the badge's own text on its own background
GRID_MAX_CONTRAST = 1.8      # a grid line is subtle or it is a border


@dataclass(frozen=True)
class Problem:
    """One reason a theme is refused: where, which rule, and what was measured."""

    path: str
    code: str
    message: str

    def as_dict(self) -> dict:
        return {"path": self.path, "code": self.code, "message": self.message}


def _validator() -> Draft202012Validator:
    text = resources.files("bizview_cli.schemas").joinpath("theme.schema.json").read_text()
    return Draft202012Validator(json.loads(text))


_VALIDATOR = _validator()


# --- colour mathematics --------------------------------------------------------------------------

def _rgb(hex_colour: str) -> tuple[int, int, int]:
    value = hex_colour.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _channel(value: int) -> float:
    s = value / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    r, g, b = (_channel(v) for v in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _lab(hex_colour: str) -> tuple[float, float, float]:
    r, g, b = (_channel(v) for v in _rgb(hex_colour))
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # noqa: E731
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a: str, b: str) -> float:
    """CIE76 distance: enough to say «these two bars look the same» and cheap to explain."""
    la, aa, ba = _lab(a)
    lb, ab, bb = _lab(b)
    return ((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2) ** 0.5


# --- validation ----------------------------------------------------------------------------------

def _shape_problems(theme: dict) -> list[Problem]:
    """The look: contrast, distinguishability and polarity, on the surface each mode paints."""
    problems: list[Problem] = []
    sequential = (theme.get("strategy") or "categorical") == "sequential"
    strict = theme.get("id") == "contraste"      # the high-contrast theme answers to 7:1
    floor = SERIES_CONTRAST_STRICT if strict else SERIES_CONTRAST
    for mode in MODES:
        tokens = theme[mode]
        surface = tokens["surface"]
        series = list(tokens["series"])
        if contrast(tokens["text"], surface) < TEXT_CONTRAST:
            problems.append(Problem(
                f"{mode}.text", "contrast",
                f"{mode}.text vs {mode}.surface: {contrast(tokens['text'], surface):.2f}:1 "
                f"(needs {TEXT_CONTRAST:.1f}:1)"))
        for index, colour in enumerate(series):
            ratio = contrast(colour, surface)
            if ratio < floor:
                problems.append(Problem(
                    f"{mode}.series[{index}]", "contrast",
                    f"{mode}.series[{index}] vs {mode}.surface: {ratio:.2f}:1 "
                    f"(needs {floor:.1f}:1)"))
        for role in ("positive", "negative"):
            ratio = contrast(tokens[role], surface)
            if ratio < floor:
                problems.append(Problem(
                    f"{mode}.{role}", "contrast",
                    f"{mode}.{role} vs {mode}.surface: {ratio:.2f}:1 (needs {floor:.1f}:1)"))
            badge = contrast(tokens[role], tokens[f"delta_{role}"])
            if badge < DELTA_CONTRAST:
                problems.append(Problem(
                    f"{mode}.delta_{role}", "contrast",
                    f"{mode}.{role} on {mode}.delta_{role}: {badge:.2f}:1 "
                    f"(needs {DELTA_CONTRAST:.1f}:1)"))
        polarity = delta_e(tokens["positive"], tokens["negative"])
        if polarity < POLARITY_DELTA_E:
            problems.append(Problem(
                f"{mode}.positive", "polarity_confusion",
                f"{mode}.positive vs {mode}.negative: ΔE {polarity:.0f} "
                f"(needs {POLARITY_DELTA_E:.0f})"))
        if contrast(tokens["grid"], surface) >= GRID_MAX_CONTRAST:
            problems.append(Problem(
                f"{mode}.grid", "grid_too_strong",
                f"{mode}.grid vs {mode}.surface: {contrast(tokens['grid'], surface):.2f}:1 "
                f"(a grid line stays below {GRID_MAX_CONTRAST:.1f}:1)"))
        if sequential:
            steps = [abs(_lab(a)[0] - _lab(b)[0]) for a, b in pairwise(series)]
            for index, step in enumerate(steps):
                if step < SEQUENTIAL_STEP:
                    problems.append(Problem(
                        f"{mode}.series[{index}]", "series_similar",
                        f"{mode}.series[{index}]→[{index + 1}]: L* step {step:.1f} "
                        f"(needs {SEQUENTIAL_STEP:.0f})"))
        else:
            for index in range(len(series) - 1):
                distance = delta_e(series[index], series[index + 1])
                if distance < SERIES_DELTA_E:
                    problems.append(Problem(
                        f"{mode}.series[{index}]", "series_similar",
                        f"{mode}.series[{index}] vs {mode}.series[{index + 1}]: ΔE {distance:.1f} "
                        f"(needs {SERIES_DELTA_E:.0f})"))
    return problems


_CODES = {
    "additionalProperties": "unknown_key",
    "required": "missing_key",
    "minItems": "series_length",
    "maxItems": "series_length",
    "enum": "bad_enum",
}


def _schema_problems(data: Any) -> list[Problem]:
    """Every shape problem, not just the first: an author fixes them in one pass."""
    problems: list[Problem] = []
    seen: set[tuple[str, str]] = set()
    for error in sorted(_VALIDATOR.iter_errors(data),
                        key=lambda e: list(e.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path)
        code = _CODES.get(error.validator or "", "invalid")
        if error.validator == "pattern":
            code = "bad_id" if "id" in path or not path else "bad_hex"
        key = (path, code)
        if key in seen:
            continue
        seen.add(key)
        problems.append(Problem(path or "/", code, error.message))
    if not problems:
        return problems
    # A `required` error names only the first missing key; name them all, since a theme missing
    # three tokens is three fixes, not three round trips.
    if any(p.code == "missing_key" for p in problems):
        problems = [p for p in problems if p.code != "missing_key"]
        for missing in _missing_keys(data):
            problems.append(Problem(missing, "missing_key", f"{missing}: missing"))
    return problems


def _missing_keys(data: Any) -> list[str]:
    """Every required key missing, with its dotted path, for both modes."""
    missing: list[str] = []
    for key in ("id", "name", "name_en", "version", "light", "dark"):
        if key not in data:
            missing.append(key)
    for mode in MODES:
        tokens = data.get(mode)
        if not isinstance(tokens, dict):
            continue
        missing += [f"{mode}.{key}" for key in (*COLOUR_TOKENS, "series") if key not in tokens]
    return missing


def validate_theme(data: Any) -> list[Problem]:
    """Every reason `data` is not an acceptable theme; empty means accepted."""
    if not isinstance(data, dict):
        return [Problem("/", "invalid", "a theme is a mapping of tokens")]
    problems = _schema_problems(data)
    if problems:
        return problems
    return _shape_problems(data)


def default_shape() -> dict:
    return dict(SHAPE_DEFAULTS)


def shape_of(theme: dict) -> dict:
    return {**SHAPE_DEFAULTS, **(theme.get("shape") or {})}


def load_theme_text(text: str) -> tuple[dict | None, list[Problem]]:
    """Parse a YAML or JSON theme file; a syntax error is a problem, not an exception."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        return None, [Problem("/", "too_large",
                              f"theme is {len(text.encode('utf-8')) / 1024:.0f} KB, "
                              f"the cap is {MAX_BYTES // 1024} KB")]
    try:
        data = json.loads(text) if text.lstrip().startswith("{") else yaml.safe_load(text)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        return None, [Problem("/", "unparsable", f"the file could not be read: {exc}")]
    return data, validate_theme(data)


def derive_tokens(theme: dict, mode: str) -> dict:
    """The runtime roles the web components and the PDF consume, from the authored tokens."""
    tokens = theme[mode]
    series = list(tokens["series"])
    while len(series) < 8:                  # 3 to 8 authored; the chart maps eight roles
        series.append(series[-1])
    out = {
        "primary": tokens["primary"],
        "positive": tokens["positive"],
        "negative": tokens["negative"],
        "neutral": tokens["neutral"],
        "grid": tokens["grid"],
        "surface": tokens["surface"],
        "card": tokens["card"],
        "kpi_text": tokens["text"],
        "kpi_delta_bg": {"positive": tokens["delta_positive"],
                         "negative": tokens["delta_negative"]},
        "muted": tokens["muted"],
        "text": tokens["text"],
    }
    for index, colour in enumerate(series, start=1):
        out[f"series{index}"] = colour
    return out


def theme_to_preset(theme: dict) -> dict:
    """The shape `frontend/src/theme/palettes/*.json` and the PDF mirror have always had."""
    return {
        "id": theme["id"],
        "label_key": f"palette.{theme['id']}",
        "strategy": theme.get("strategy") or "categorical",
        "light": derive_tokens(theme, "light"),
        "dark": derive_tokens(theme, "dark"),
    }
