"""Report palette (feature 030, research R5) resolved from a theme (feature 047).

The six built-ins are **themes** — one JSON file per theme under `themes/`, a byte-identical
mirror of `frontend/src/theme/themes/`, in the format `cli/bizview_cli/schemas/theme.schema.json`
publishes — so an installation only chooses *which* one applies and no customer hue lives in code.
The runtime roles the PDF paints with (`series1..8`, `kpi_text`, `kpi_delta_bg`, …) are derived
from the theme's tokens by the same function the CLI and the web app use.

The PDF always renders the theme's **light** variant (FR-006, FR-011 and 047 FR-021); the dark
variant exists for the web and is never resolved here.

Standard library plus ReportLab only: nothing in this module imports from `frontend/`.
"""
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from reportlab.lib.colors import Color, HexColor

PRESET_IDS: tuple[str, ...] = ("impacto", "clasico", "elegante", "monocromo", "contraste",
                                "daltonico")
DEFAULT_PRESET = "impacto"
THEME_DIR = Path(__file__).resolve().parent / "themes"
SERIES_ROLES = tuple(f"series{i}" for i in range(1, 9))
THEME_MODES = ("auto", "light", "dark")
THEME_ROLES = ("primary", *SERIES_ROLES, "positive", "negative", "neutral", "grid", "surface",
               "kpi_text")
THEMES = ("light", "dark")


@dataclass(frozen=True)
class ReportPalette:
    """Every colour a renderer needs, resolved from one preset (data-model §4).

    `ink`, `muted` and `line` are the renderers' fixed roles: they are derived from `kpi_text`,
    `neutral` and `grid` so the layout keeps no hex constant of its own."""

    preset: str
    primary: Color
    series: tuple[Color, ...]
    positive: Color
    negative: Color
    neutral: Color
    grid: Color
    surface: Color
    kpi_text: Color
    kpi_delta_bg_positive: Color
    kpi_delta_bg_negative: Color
    ink: Color
    muted: Color
    line: Color

    def role(self, name: Any, index: int = 0) -> Color:
        """A declared colour role (026 R8) as a drawing colour.

        An unknown, absent or non-string role falls back to the series order, exactly as the
        declarative renderer always did."""
        key = str(name).strip().lower().replace("_", "") if isinstance(name, str) else ""
        fixed = {
            "primary": self.primary, "positive": self.positive, "negative": self.negative,
            "neutral": self.neutral, "muted": self.muted, "grid": self.grid,
            "surface": self.surface, "ink": self.ink, "line": self.line,
        }
        if key in fixed:
            return fixed[key]
        digits = key.removeprefix("series")
        if key.startswith("series") and digits.isdigit() and 1 <= int(digits) <= len(self.series):
            return self.series[int(digits) - 1]
        return self.series[index % len(self.series)]


@cache
def load_theme(theme_id: str) -> dict:
    """The authored theme, both modes included.

    An id outside `PRESET_IDS` raises `KeyError`: installs and definitions validate the id before
    they store it, so reaching this with an unknown one is a caller bug, not user input.
    Malformed shipped data raises `ValueError`."""
    if theme_id not in PRESET_IDS:
        raise KeyError(theme_id)
    data = json.loads((THEME_DIR / f"{theme_id}.json").read_text(encoding="utf-8"))
    from bizview_cli.theme import validate_theme

    problems = validate_theme(data)
    if problems:
        raise ValueError(f"theme {theme_id}: {problems[0].message}")
    return data


@cache
def load_preset(preset_id: str) -> dict:
    """The preset shape the renderers consume, derived from the theme (feature 047)."""
    from bizview_cli.theme import theme_to_preset

    data = theme_to_preset(load_theme(preset_id))
    _check(preset_id, data)
    return data


def _check(preset_id: str, data: dict) -> None:
    """The contract's shape rules, for the data this build ships (contracts/palette-preset.md)."""
    if data.get("id") != preset_id:
        raise ValueError(f"palette {preset_id}: id is {data.get('id')!r}")
    if data.get("strategy") not in ("categorical", "sequential"):
        raise ValueError(f"palette {preset_id}: strategy is {data.get('strategy')!r}")
    for theme in THEMES:
        values = data.get(theme)
        if not isinstance(values, dict):
            raise ValueError(f"palette {preset_id}: no {theme} theme")
        missing = [role for role in THEME_ROLES if role not in values]
        if missing:
            raise ValueError(f"palette {preset_id}: {theme} misses {', '.join(missing)}")
        delta_bg = values.get("kpi_delta_bg")
        if not isinstance(delta_bg, dict) or {"positive", "negative"} - set(delta_bg):
            raise ValueError(f"palette {preset_id}: {theme}.kpi_delta_bg is incomplete")
        hexes = [values[role] for role in THEME_ROLES] + [delta_bg["positive"],
                                                          delta_bg["negative"]]
        if any(not _is_hex(value) for value in hexes):
            raise ValueError(f"palette {preset_id}: {theme} has a value that is not #RRGGBB")


def _is_hex(value: Any) -> bool:
    """`#RRGGBB`, uppercase, no alpha (contract rule 3)."""
    return isinstance(value, str) and len(value) == 7 and value[0] == "#" and \
        all(char in "0123456789ABCDEF" for char in value[1:])


def is_preset(value: Any) -> bool:
    """Whether `value` names one of the presets this build ships."""
    return isinstance(value, str) and value in PRESET_IDS


def declared_theme(definition: dict | None) -> str | None:
    """`layout.theme.id` of a report definition, or None when it declares none.

    `layout.theme.palette` is the deprecated alias of the same field (047 R10): a project written
    before themes had ids keeps applying, and the id wins when both appear."""
    layout = (definition or {}).get("layout")
    theme = layout.get("theme") if isinstance(layout, dict) else None
    if not isinstance(theme, dict):
        return None
    for key in ("id", "palette"):
        value = theme.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def declared_mode(definition: dict | None) -> str:
    """`layout.theme.mode` of a report definition: `auto` unless it says otherwise (§3)."""
    layout = (definition or {}).get("layout")
    theme = layout.get("theme") if isinstance(layout, dict) else None
    mode = theme.get("mode") if isinstance(theme, dict) else None
    return mode if mode in THEME_MODES else "auto"


# Kept for the callers written against 030; `palette` is the same field as `id`.
declared_preset = declared_theme


def installation_preset(db: Any = None) -> str:
    """The installation's theme (`appearance_settings`, features 030 and 047).

    Best effort, like `/api/config`: a missing table, row or unreachable database falls back to
    `DEFAULT_PRESET` instead of failing a PDF. Imported lazily so this module stays dependency-free
    for the renderer and the tests that read the JSON directly."""
    if db is None:
        return DEFAULT_PRESET
    try:
        from app.models import AppearanceSettings

        row = db.get(AppearanceSettings, 1)
        if row is None:
            return DEFAULT_PRESET
        return row.theme_id or row.palette_preset or DEFAULT_PRESET
    except Exception:   # the PDF must render even with the settings unreadable
        return DEFAULT_PRESET


def resolve(definition: dict | None = None, installation_preset: str | None = None,
            db: Any = None) -> ReportPalette:
    """The effective palette: the report's theme, else the installation's, else `impacto`.

    Always the light variant (data-model §4, FR-021): paper has no dark mode. An unknown id falls
    back to `DEFAULT_PRESET` instead of failing: the web and the PDF keep rendering when a value
    slipped past the checker. `db` is needed only for a theme the installation uploaded — a
    built-in is a file this build ships."""
    chosen = declared_theme(definition) or installation_preset or DEFAULT_PRESET
    return report_palette(chosen, db)


def report_palette(theme_id: str, db: Any = None) -> ReportPalette:
    """One theme as drawing colours: a built-in from its file, anything else from its row."""
    if is_preset(theme_id):
        return _report_palette(theme_id)
    tokens = _stored_tokens(theme_id, db)
    if tokens is None:
        return _report_palette(DEFAULT_PRESET)
    return _palette_from(theme_id, tokens)


def _stored_tokens(theme_id: str, db: Any) -> dict | None:
    """The authored file of an uploaded or project theme, or None when it is not there."""
    if db is None:
        return None
    try:
        from app.models import Theme

        row = db.get(Theme, theme_id)
    except Exception:   # a PDF must not fail because the library could not be read
        return None
    if row is None or not isinstance(row.tokens, dict):
        return None
    return row.tokens


def _palette_from(theme_id: str, tokens: dict) -> ReportPalette:
    """The runtime roles, through the same derivation the web app and the CLI use."""
    from bizview_cli.theme import derive_tokens

    return _palette_values(theme_id, derive_tokens(tokens, "light"))


@cache
def _report_palette(preset_id: str) -> ReportPalette:
    values = load_preset(preset_id)["light"]
    return _palette_values(preset_id, values)


def _palette_values(preset_id: str, values: dict) -> ReportPalette:
    ink = HexColor(values["kpi_text"])
    neutral = HexColor(values["neutral"])
    grid = HexColor(values["grid"])
    return ReportPalette(
        preset=preset_id,
        primary=HexColor(values["primary"]),
        series=tuple(HexColor(values[role]) for role in SERIES_ROLES),
        positive=HexColor(values["positive"]),
        negative=HexColor(values["negative"]),
        neutral=neutral,
        grid=grid,
        surface=HexColor(values["surface"]),
        kpi_text=ink,
        kpi_delta_bg_positive=HexColor(values["kpi_delta_bg"]["positive"]),
        kpi_delta_bg_negative=HexColor(values["kpi_delta_bg"]["negative"]),
        ink=ink,
        muted=neutral,
        line=grid,
    )
