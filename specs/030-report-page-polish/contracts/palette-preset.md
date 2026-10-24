# Contract — palette preset files

Product data, one file per preset. Canonical copy in `frontend/src/theme/palettes/<id>.json`; the
backend keeps a byte-identical mirror in `backend/app/reports/palettes/<id>.json` (a test fails on
drift). No customer hue lives in code; the installation only chooses *which* file applies.

## File shape

```json
{
  "id": "impacto",
  "label_key": "palette.impacto",
  "strategy": "categorical",
  "light": {
    "primary": "#0B63F6",
    "series1": "#0B63F6",
    "series2": "#00897B",
    "series3": "#B45309",
    "series4": "#DB2777",
    "series5": "#7C3AED",
    "series6": "#15803D",
    "series7": "#C2410C",
    "series8": "#0E7490",
    "positive": "#15803D",
    "negative": "#B91C1C",
    "neutral": "#334155",
    "grid": "#E2E8F0",
    "surface": "#FFFFFF",
    "kpi_text": "#0F172A",
    "kpi_delta_bg": { "positive": "#DCFCE7", "negative": "#FEE2E2" }
  },
  "dark": { "...": "same roles, dark surface #0F172A" }
}
```

## Rules

| # | Rule | Enforced by |
|---|---|---|
| 1 | `id` equals the file name and is one of `impacto`, `clasico`, `monocromo`, `contraste`, `daltonico` | `palette-presets.test.ts`, CLI checker (`layout.theme.palette` enum) |
| 2 | Both `light` and `dark` present and complete (every role, no inheritance) | type `PalettePreset` (`tsc -b`) + test |
| 3 | Values are `#RRGGBB` hex, uppercase, no alpha | test |
| 4 | `series[n]`, `positive`, `negative` ≥3:1 vs that theme's `surface` (≥7:1 for `contraste`) | test |
| 5 | Adjacent series ΔE (CIE76) ≥10; `sequential` presets instead need monotonic ΔL\* ≥5 per step | test |
| 6 | `positive` vs `negative` ΔE ≥25, both ≥3:1 | test |
| 7 | `kpi_text` ≥4.5:1 vs `surface`; `kpi_delta_bg.*` label ≥4.5:1 on its fill | test |
| 8 | `grid` <1.8:1 vs `surface` (subtle) | test |
| 9 | Backend mirror byte-identical | `palette-presets.test.ts` |
| 10 | No preset may ship if any rule fails (FR-010) | `npm test` is a release gate |

## Web token mapping

| Role | CSS custom property written on `<html>` |
|---|---|
| `series1…8` | `--c-chart-1` … `--c-chart-8` |
| `positive` | `--c-success`, `--c-success-strong`, `--c-success-bright` (derived) |
| `negative` | `--c-danger`, `--c-danger-strong`, `--c-danger-bright` (derived) |
| `neutral` | `--c-kpi-neutral` |
| `grid` | `--c-chart-grid`, `--c-chart-axis` |
| `surface` | `--c-kpi-surface` |
| `kpi_text` | `--c-kpi-text` |
| `kpi_delta_bg.positive/.negative` | `--c-kpi-delta-bg-positive`, `--c-kpi-delta-bg-negative` |

The interface `primary` role keeps following installation branding; only chart series are guaranteed
to come from the preset (spec edge case "branding that clashes with a preset").

`impacto` additionally sets, through `:root[data-palette="impacto"]` in `src/index.css`:
`--kpi-numeral`, `--kpi-numeral-sm`, `--kpi-tracking`, `--radius-card`, `--shadow-card` (stronger in
dark). The other presets keep today's typography (FR-009).

## PDF mapping (light variant only)

`backend/app/reports/palette.py` returns a `ReportPalette` with ReportLab colours for: title rule and
KPI accent (`primary`), series 1–8, positive/negative deltas, grid and table lines, card surface, KPI
text. The renderers take every colour from it — no hex constant stays in `pdf.py` or `pdf_layout.py`.
