# Themes

A theme is a **file of data**: colours and a few shape decisions. Never CSS, never a font, never
markup. Anyone — a person or any AI — writes it outside Bizview, and it enters only after the same
validator in `cli/bizview_cli/theme.py` accepts it, whether it is uploaded in Apariencia or arrives
inside a project.

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
dark:
  … the same keys, on the dark surface …
shape:                        # all optional, each from a closed list
  radius: md                  # sm | md | lg
  density: normal             # compact | normal
  kpi_scale: lg               # md | lg | xl
  font: sans                  # sans | serif | mono
  badge: filled               # filled | outline
```

`light` and `dark` are both required, with every token: the product paints in both modes and a
missing token would be a hole in one of them. `series` holds 3 to 8 colours; when it holds fewer
than eight the last one repeats, so a three-colour theme still fills an eight-bar chart. `shape`
tokens map to the custom properties the components read (`--t-radius`, `--t-density`,
`--t-kpi-scale`, `--t-font`, `--t-badge`), and no component holds a literal colour.

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

Both modes are checked, each against its own surface. Every refusal names the pair of tokens and the
measurement, because that is what an author can act on:
`light.text vs light.surface: 3.9:1 (needs 4.5:1)`.

The five themes the product ships obey the same rules, and the CI gate re-checks them: a change to a
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
| **The product's own five** | seeded by the migration and refreshed from the shipped files at bootstrap; can be neither replaced nor deleted |

A theme a report names cannot be deleted: the refusal lists the reports. In Apariencia every theme
shows a light and a dark preview, its origin and its version, and offers apply, download (the file as
it was authored), duplicate (as the starting point for an edit) and delete.

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
| The library | `backend/app/services/themes.py`, `backend/app/api/themes.py` |
| The page | `frontend/src/pages/admin/Appearance.tsx` |
| The report's own area and mode | `frontend/src/components/report/ReportArea.tsx` |
