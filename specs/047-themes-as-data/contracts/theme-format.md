# Contract — the theme file

## What it is

A theme is **data**: colours and choices from fixed lists. It is never CSS, never a font file, never
markup. The published schema is `cli/bizview_cli/schemas/theme.schema.json`; the validator that
accepts it is `cli/bizview_cli/theme.py`, and the backend, the CLI and the authoring pack read both.

## Shape

See [data-model.md](../data-model.md) for the full example. Summary:

| Field | Required | Rule |
|---|---|---|
| `id` | yes | `^[a-z][a-z0-9-]{1,39}$` |
| `name`, `name_en` | yes | 1–60 characters each |
| `version` | yes | integer ≥ 1 |
| `light`, `dark` | yes | the ten colour tokens; `series` 3–8 entries |
| `shape` | no | `radius`, `density`, `kpi_scale`, `font`, `badge`, each from its list |
| anything else | — | refused |

## Refusals (what an author reads)

| Code | Message shape |
|---|---|
| `unknown_key` | `shape.glow: not a theme token` |
| `missing_key` | `dark.card: missing` |
| `bad_hex` | `light.primary: "#0B5FF" is not #RRGGBB` |
| `series_length` | `light.series: 2 colours, the theme needs 3 to 8` |
| `bad_enum` | `shape.font: "Inter" is not one of sans, serif, mono` |
| `too_large` | `theme is 24 KB, the cap is 20 KB` |
| `contrast` | `light.text vs light.surface: 3.9:1 (needs 4.5:1)` |
| `series_similar` | `light.series[2] vs light.series[3]: ΔE 12 (needs 20)` |
| `polarity_confusion` | `light.positive vs light.negative: hues 14° apart (needs 30°)` |

Exit code of `bizview theme validate <file>`: `0` valid, `1` invalid (every problem printed),
`2` the file could not be read or parsed.

## Authoring page

`cli/bizview_cli/workspace_template/files/THEME.md` — one page for an AI: the schema, the contrast
rules with the exact thresholds, an example, and the instruction to output only the YAML. The pack
also ships `theme.schema.json`.
