# Implementation Plan: themes that repaint the application

**Feature**: `051-theme-application` · **Spec**: [spec.md](./spec.md) · **Created**: 2026-11-02

## Context from the code

| Piece | Where | What it does today |
|---|---|---|
| Semantic tokens | `frontend/src/index.css` (`:root`, `:root[data-theme="dark"]`) | ~60 literals per mode; the chrome of every screen reads these |
| Tailwind map | `frontend/tailwind.config.js` | `rgb(var(--c-<name>) / <alpha-value>)`; adding a token = adding a name here |
| Theme data | `frontend/src/theme/themes/*.json` ↔ `backend/app/reports/themes/*.json` | report palette + `shape` |
| Contract | `cli/bizview_cli/schemas/theme.schema.json`, `cli/bizview_cli/theme.py` | shape + look validation; `derive_tokens` |
| Runtime apply | `frontend/src/theme/palette.ts#applyThemeVariables` | writes `--c-chart-*`, `--c-kpi-*`, `--t-*`, `data-palette` |
| Shared state | `frontend/src/theme/ThemeContext.tsx` | installation theme ← `GET /api/config` (`BrandingContext`), one fetch at start |
| Admin | `frontend/src/pages/admin/Appearance.tsx` | applies via `PUT /api/admin/settings/theme`, then `window.location.reload()` |

Two facts measured, not assumed:

1. `--t-*` (radius, density, kpi-scale, font, badge) are **never read** by any stylesheet or
   component — `grep -rn "var(--t-" src/` yields nothing. The `shape` block is inert.
2. `:root[data-palette="impacto"]` is the only theme-keyed CSS in the product; every other theme
   changes chart colours and nothing else.

## Architecture decision

**A theme declares its chrome; one derivation turns it into every semantic token; components keep
using the semantic tokens they already use.**

```
theme.json (data)               deriveChrome(theme, mode)                 <html> custom properties
 ├ light/dark report tokens  →  chrome tokens (authored or derived)   →   --c-canvas … --c-ink-faint
 ├ light/dark chrome tokens  →  ramps: ink / accent / status / lines  →   --c-primary* --c-danger* …
 └ shape enums               →  geometry: radii, elevation, nav, …    →   --radius-card, --nav-* …
```

Rejected alternatives: four per-theme stylesheets (four copies of the product), a second provider
(fragmenting state), rewriting components against a design-token library (a second styling system).

## Contract changes (`cli/bizview_cli/schemas/theme.schema.json`)

Optional, additive — every theme authored before this feature stays valid (**FR-021**):

```jsonc
"light" | "dark": { …, "canvas": "#F4F7FA", "chrome": "#3A7393", "chrome_text": "#FFFFFF",
                        "field": "#EFF4F8", "line": "#E2E8F0", "accent": "#3A7393",
                        "warning": "#B45309" }
"shape": { "radius": "sm|md|lg", "density": …, "kpi_scale": …, "font": …, "badge": …,
           "elevation": "flat|soft|strong", "button": "rounded|pill|square",
           "nav": "gradient|solid|bar|outline", "divider": "soft|strong",
           "heading": "normal|tight", "card_border": "none|hairline|strong" }
```

`cli/bizview_cli/theme.py` gains the token names, the enum lists, defaults and three contrast rules:
`chrome_text` on `chrome` ≥ 4.5, `text` on `field` ≥ 4.5, `accent` on `surface` ≥ 3.0 (FR-023).

## Derivation (`frontend/src/theme/derive.ts`, new)

Pure functions, no React, no DOM:

- `chromeOf(theme, mode)` → the seven chrome tokens, authored value first, else derived by mixing
  the theme's own report tokens (`canvas` ← surface tinted with primary; `chrome` ← primary shaded;
  `chrome_text` ← whichever of white/text a 4.5:1 check accepts; `field` ← surface↔card; `line` ←
  `grid`; `accent` ← primary; `warning` ← a fixed amber warmed toward the theme's muted ink).
- `semanticVariables(theme, mode)` → every `--c-*` the chrome paints with, including the ink ramp
  (text→surface mixes), the accent ramp, the status roles (`negative`→danger, `positive`→success,
  chrome `warning`), `on-primary` chosen by contrast, `chrome`/`on-chrome`.
- `designVariables(theme, mode)` → `--radius-card|button|field|nav`, `--shadow-card|raised` (per mode
  and `elevation`), `--card-border`, `--divider`, `--heading-weight`, `--kpi-numeral*`,
  `--kpi-tracking`, `--nav-*`, `--chrome-grad-*`.

`palette.ts#applyThemeVariables` writes `semanticVariables + designVariables + chart roles`, sets
`data-palette`, `data-nav`, `data-elevation`, `data-card-border`, and the `meta[theme-color]`.
`themeStyle()` (report scoping) uses the same two functions.

**Clásico byte-identity** (FR-010): `clasico.json` carries the **full authored chrome set**, copied
from today's `index.css` literals; a unit test compares `semanticVariables(clasico, mode)` against a
golden map frozen from today's stylesheet, so any accidental drift fails CI.

## Shape actually applied

| Enum | Variables | Consumed by |
|---|---|---|
| `radius` | `--radius-card`, `--radius-button`, `--radius-field`, `--radius-nav` | `tailwind.config.js` (`rounded-card`, `rounded-btn`, `rounded-field`), `Button`, `SegmentedControl`, inputs |
| `elevation` | `--shadow-card`, `--shadow-raised` | `shadow-card`, `shadow-raised` |
| `card_border` | `--card-border` | `Card` (`border-[length:var(--card-border)]`) |
| `nav` | `data-nav` + `--nav-*` | `.nav-active` rules in `index.css`, applied by `AppShell` |
| `divider` | `--divider` | `.section-divider` / `PageHeader` border |
| `heading` | `--heading-weight`, `--heading-tracking` | `.page-title`, `.section-title` |
| `kpi_scale` | `--kpi-numeral*`, `--kpi-tracking` | `KpiGrid` (already) |
| `badge` | `--t-badge` | `Badge` variant default |

`index.css` keeps Clásico's literals as the **pre-JS fallback** and drops the `[data-palette="impacto"]`
block (replaced by the derived variables).

## Instant application (FR-004…FR-006)

1. `BrandingContext` gains `refresh()` (re-fetch `/api/config`), exposed as `useRefreshBranding()`.
2. `Appearance.apply()`: `await PUT` → `await refresh()` → toast. No `window.location.reload()`.
3. `applyThemeVariables` also writes the resolved variables to `localStorage`
   (`bizview.theme.tokens`), and `public/theme-init.js` replays them before first paint, so a reload
   shows the right theme immediately and `/api/config` reconciles afterwards (version-stamped
   payload; the cache is ignored when it is older than 30 days or malformed).

## Themes

| id | identity | chrome anchors (light / dark) |
|---|---|---|
| `clasico` | today's BizView | copied verbatim from `index.css` |
| `impacto` | Modern Executive | `#EEF6FC`/`#101E35` canvas, `#1769C2`/`#0F91C9` chrome, cyan accent, 1rem cards, `nav: solid`, `elevation: strong` |
| `elegante` | Premium Professional | `#F7F5F0`/`#171B23`, graphite chrome, bronze `#A47B45` accent, `radius: sm`, `nav: bar`, `elevation: flat`, `heading: tight` |
| `contraste` | Precision High Contrast | `#FFFFFF`/`#121722`, near-black chrome, `#F0C85A` accent, `nav: outline`, `card_border: strong`, `elevation: flat`, series ≥ 7:1 |
| `daltonico`, `monocromo` | compatibility | keep their report palettes; chrome authored to stay Clásico-like |

`elegante` is registered in `models.PALETTE_PRESET_IDS`, `reports/palette.PRESET_IDS`,
`services/themes.BUILTIN_IDS`, `frontend` `PaletteId`/`BUILTIN_THEMES`/`THEMES`, the i18n labels, and
seeded by migration `0048_official_themes` (also refreshing the built-ins' rows and widening the
`appearance_settings` check constraint).

## Migration `0048_official_themes`

- Upsert the six built-in theme rows from `backend/app/reports/themes/*.json` (a built-in row is the
  product's file, not the install's — 047's rule).
- `appearance_settings.palette_preset` check gains `elegante`; existing rows untouched.
- No data loss; downgrade restores the five-id constraint and removes the `elegante` row only if
  nothing references it.

## Screens

- **Appearance**: official group (four cards) + compatibility group; each card shows name, one-line
  identity, light/dark preview **including the chrome band**, active marker + disabled action.
- **Shell**: header band and sidebar band use `bg-chrome-gradient`, `text-on-chrome`; nav item
  active state uses `.nav-active`; bottom navigation unchanged in geometry.
- No other page changes: they already paint with semantic tokens.

## Tests

| Layer | File | Asserts |
|---|---|---|
| Contract | `cli/tests/test_theme.py` | new tokens/enums accepted; bad enum refused; chrome contrast rules; old files still valid |
| Backend | `backend/tests/test_themes_contract.py` | `elegante` registered and seeded; unknown id refused; PUT only for super user; `/api/config` exposes it |
| Derivation | `frontend/tests/unit/theme-derive.test.ts` | Clásico golden map; AA (4.5:1) for all 8 variants on text/ink/field/chrome pairs; the four themes differ in ≥ 5 dimensions |
| Wiring | `frontend/tests/unit/theme-application.test.ts` | `applyThemeVariables` writes the chrome vars, `data-nav`/`data-elevation`; meta theme-color |
| Guards | `frontend/tests/unit/design-guards.test.ts` (extend) | no component hardcodes a hex; no second theme provider |
| E2E | `frontend/tests/e2e/theme-application.spec.ts` | apply each theme → chrome computed colours change with no reload; persistence across reload; 8 combinations no overflow at 375/1440; reference dashboard screenshots ×4 ×2 |

## Risks

- **Clásico drift** → golden-map test (above) is the gate.
- **Contrast regressions on derived ramps** → the 8-variant AA test computes from the same functions.
- **Flash on reload** → device cache replay; the token payload is validated before use.
- **PDF drift** → `derive_tokens`/report roles untouched; the existing mirror test still guards it.
