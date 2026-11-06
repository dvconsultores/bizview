# Writing a theme

## What it is for

A theme is a file of data — colours and a few shape decisions — that anyone writes outside Bizview,
with or without an AI, and that enters through Appearance or inside a project. It never carries CSS,
fonts or markup.

## Who can use it

Anyone preparing a project; uploading it to the installation is the **Superuser**'s job.

## How to

1. Copy `THEME.md` from the project: it carries the exact shape of the file and the rules that are
   checked.
2. Write `themes/<id>.yaml` with the tokens of `light` and `dark`.
3. Validate it without a server: `bizview theme validate themes/<id>.yaml`.
4. Look at it before uploading: `bizview theme preview themes/<id>.yaml --out preview.svg`.
5. Upload it in [Open Appearance](app:/admin/apariencia) with **Upload theme**, or leave it in
   `themes/` inside the project and it enters when the project is imported.

## Options

- `light` and `dark`: the same tokens in each mode. Colours are `#RRGGBB` and `series` holds 3
  to 8 entries.
- `strategy`: `categorical` or `sequential` (one colour family, checked on lightness steps).
- `shape`: `radius`, `density`, `kpi_scale`, `font` and `badge`, each from a closed list.

## Common problems

- "the file could not be read": the YAML has a syntax error, almost always a quote or the
  indentation.
- "… vs …: 3.9:1 (needs 4.5:1)": that pair of tokens misses the minimum contrast. Change the colour,
  not the rule.
- "series[1] vs series[2]: ΔE 4.0": two series look too much alike; separate the shades.
- The PDF always uses the theme's light variant, even when the report is dark.

## Related

- Appearance
- Define a report
- Project structure
