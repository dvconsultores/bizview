🇬🇧 English · 🇪🇸 [Español](es/THEMES.md)

# Themes

A theme is a **file of data**: colours and a few shape decisions. Never CSS, never a font, never
markup. Anyone — a person or any AI — writes it outside Bizview, and it enters only after the same
validator in `cli/bizview_cli/theme.py` accepts it, whether it is uploaded in Apariencia or arrives
inside a project.

A theme paints the charts, the KPI tiles and the PDF **and** — since feature 051 — the application
itself: the header band, the sidebar, the page background, the cards, the buttons, the inputs, the
tables, the dialogs and the bottom navigation. No component names a colour; one derivation turns the
theme into the semantic tokens every screen already paints with.

The published contract is [`cli/bizview_cli/schemas/theme.schema.json`](../cli/bizview_cli/schemas/theme.schema.json);
the page an author (or an AI) reads is `THEME.md` inside the authoring pack.

## The file

```yaml
id: acme-azul                 # ^[a-z][a-z0-9-]{1,39}$, unique per installation
name: "Acme · azul"
name_en: "Acme · blue"
version: 1
strategy: categorical         # categorical | sequential
light:
  surface: "#FFFFFF"          # page background
  card: "#F8FAFC"             # card background
  text: "#0F172A"             # main text
  muted: "#64748B"            # secondary text and axis labels
  grid: "#E2E8F0"             # grid lines
  primary: "#0B5FFF"          # interface accent
  positive: "#16A34A"
  negative: "#DC2626"
  neutral: "#64748B"
  delta_positive: "#BBF7D0"   # background of the "up" badge
  delta_negative: "#FECDD3"   # background of the "down" badge
  series: ["#0B5FFF", "#F59E0B", "#10B981", "#8B5CF6", "#EF4444", "#06B6D4", "#F97316", "#84CC16"]
  # optional, feature 051: the application's own chrome
  canvas: "#F7FAFF"           # page background behind the cards
  chrome: "#0B5FFF"           # the header and sidebar band
  chrome_text: "#FFFFFF"      # the ink on that band
  field: "#F3F7FF"            # input surfaces
  line: "#DCE4F0"             # borders
  accent: "#0B5FFF"           # links, selected states, the bottom bar
  warning: "#B45309"
dark:
  … the same keys, on the dark surface …
shape:                        # all optional, each from a closed list
  radius: md                  # sm | md | lg
  density: normal             # compact | normal
  kpi_scale: lg               # md | lg | xl
  font: sans                  # sans | serif | mono
  badge: filled               # filled | outline
  elevation: soft             # flat | soft | strong
  button: rounded             # rounded | pill | square
  nav: gradient               # gradient | solid | bar | outline
  divider: soft               # soft | strong
  heading: normal             # normal | tight
  card_border: hairline       # none | hairline | strong
app:                          # optional: pin any chrome token exactly, per mode
  light: { canvas: "#F4F7FA", ink: "#0F172A", primary: "#3A7393", … }
  dark: { … }
```

`light` and `dark` are both required, with every **report** token: the product paints in both modes
and a missing token would be a hole in one of them. The seven chrome tokens are optional — a theme
written before 051 declares none and the web derives them from its palette, so an old upload themes
the whole application instead of only the charts. `series` holds 3 to 8 colours; when it holds fewer
than eight the last one repeats, so a three-colour theme still fills an eight-bar chart. `shape`
tokens map to the custom properties the components read (`--radius-card`, `--radius-button`,
`--shadow-card`, `--card-border`, `--nav-mark`, `--heading-weight`, `--kpi-numeral*`, …), and no
component holds a literal colour.

## The rules that are checked

The validator measures; it does not opine. A theme is refused when:

| Rule | Value |
|---|---|
| Keys | only the ones above; anything else is refused (a theme is data, not CSS) |
| Colours | `#RRGGBB`, no alpha; `series` with 3 to 8 entries |
| Size | 20 KB at most |
| `text` on `surface` | contrast ≥ 4.5:1 |
| `primary` on `surface` | ≥ 3:1 |
| Every series on `surface` | ≥ 3:1 |
| Adjacent series | ΔE ≥ 10 (a `sequential` theme is checked on lightness steps ≥ 5 instead) |
| `positive` vs `negative` | ΔE ≥ 25, so the two are never confusable |
| `grid` on `surface` | < 1.8:1, so the grid never competes with the data |
| `chrome_text` on `chrome` | ≥ 4.5:1 (only when the theme declares them) |
| `text` on `field`, `text` on `canvas` | ≥ 4.5:1 |
| `accent` on `surface` | ≥ 3:1 |
| any token in `app` | must be a known chrome token, and the pairs it completes are checked |

Both modes are checked, each against its own surface. Every refusal names the pair of tokens and the
measurement, because that is what an author can act on:
`light.text vs light.surface: 3.9:1 (needs 4.5:1)`.

The six themes the product ships obey the same rules, and the CI gate re-checks them: a change to a
built-in that breaks its own contract fails the build.

## Authoring, offline

```sh
bizview theme validate themes/acme-azul.yaml        # 0 valid · 1 problems · 2 unreadable
bizview theme preview themes/acme-azul.yaml --out preview.svg
```

`preview.svg` draws the same card Apariencia draws — a KPI with its delta badge, four bars and a
two-series sparkline — in light and dark, with the theme's colours. It is SVG rather than PNG on
purpose: rasterising would need a headless browser or an image library, and neither is a dependency
of this project (research R11).

`THEME.md` in the authoring pack has one page of instructions to hand to an AI: produce the YAML,
respect the keys, keep the contrast, and output only the file.

## Where themes live

| Door | What happens |
|---|---|
| **Apariencia → Subir tema** | validated, stored with `origin = upload`; an existing id asks before replacing and bumps `version` |
| **A project's `themes/<id>.yaml`** | validated on import, stored with `origin = project` and the project's id; leaves the library when the project is deleted |
| **The product's own six** | seeded by the migration and refreshed from the shipped files at bootstrap; can be neither replaced nor deleted |

A theme a report names cannot be deleted: the refusal lists the reports. In Apariencia every theme
shows a light and a dark preview **of its own chrome** — the band included — its identity in one line,
its origin and its version, and offers apply, download (the file as it was authored), duplicate (as
the starting point for an edit) and delete. The four **identities** come first (`clasico`, `impacto`,
`elegante`, `contraste`); everything else the installation can still use — Daltónico, Monocromo, an
upload, a project's theme — follows under **Compatibilidad**, and applies exactly the same way.

## The four identities

| Theme | Identity | What makes it different |
|---|---|---|
| `clasico` | the product's own look, unchanged | steel-teal band, soft elevation, gradient navigation, 1.25 rem cards |
| `impacto` | Modern Executive | royal blue and cyan, pale blue canvas, large KPI scale, strong elevation, pill buttons, solid navigation |
| `elegante` | Premium Professional | warm cream canvas, graphite band, bronze accent, flat elevation, hairline cards, left-bar navigation |
| `contraste` | Precision High Contrast | white canvas, near-black band, gold accent, 2 px borders and dividers, no shadows, outlined navigation |

## Applying a theme

A super user presses **Usar en la instalación**. That is one request,
`PUT /api/admin/settings/theme` (super user only, audited as `theme_applied`). Once it returns, the
page re-reads `GET /api/config` and the whole application repaints — **no reload, no sign-out**. A
refusal repaints nothing and reports why.

The theme is also written to the device (`bizview.theme.tokens`) and `public/theme-init.js` replays it
before the first paint, so a reload never flashes the previous theme; `/api/config` reconciles it
afterwards. The user's Sistema/Claro/Oscuro preference is a separate dimension: changing the
installation theme never rewrites it, and changing it never changes the theme.

## What the derivation guarantees

`frontend/src/theme/derive.ts` writes every `--c-*` the chrome paints with and the geometry variables,
from the theme alone. Two properties are enforced rather than hoped for:

- an **accent** is moved along its own lightness until it reads at 4.5:1 on the surface *and* on its
  own tinted background, so a pale hue still works as a link or a selected state;
- **`ink-soft`** — the muted label the footer and the bottom bar use — is the lightest shade of the
  theme's muted ink that reaches 4.5:1 on both the surface and the canvas.

Both are checked for all six themes × two modes in `frontend/tests/unit/theme-derive.test.ts`, and by
axe in the browser (`frontend/tests/e2e/theme-application.spec.ts`). Clásico additionally pins its
whole chrome in `app`, and that test compares it token for token against the literals `index.css`
carried before 051, so the appearance the installation has today cannot drift.

## Per report

```yaml
layout:
  theme:
    id: acme-azul     # any theme of the installation
    mode: auto        # auto | light | dark
```

Resolution is report → installation → `impacto`, done once per page into the custom properties the
components read. `mode: dark` turns the report's own area dark while the application's chrome stays
as the viewer chose; a sun/moon action on the report overrides it for that session, and a share link
opens in the report's own mode first. The PDF always uses the theme's light variant.

`palette:` is the deprecated alias of `id`, accepted for one version so a report written before
themes had ids keeps applying.

## Where to look in the code

| Concern | File |
|---|---|
| The contract | `cli/bizview_cli/schemas/theme.schema.json` |
| The validator and the derivation | `cli/bizview_cli/theme.py` |
| The offline preview | `cli/bizview_cli/theme_preview.py` |
| The built-ins (web + the PDF's byte-identical mirror) | `frontend/src/theme/themes/`, `backend/app/reports/themes/` |
| The web derivation (chrome + geometry) | `frontend/src/theme/derive.ts` |
| Writing the variables, the device cache | `frontend/src/theme/palette.ts`, `frontend/public/theme-init.js` |
| The library | `backend/app/services/themes.py`, `backend/app/api/themes.py` |
| The page | `frontend/src/pages/admin/Appearance.tsx` |
| The report's own area and mode | `frontend/src/components/report/ReportArea.tsx` |
