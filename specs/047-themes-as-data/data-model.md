# Data model — 047 themes as data

## Theme (the authored file)

```yaml
id: acme-dark-blue            # ^[a-z][a-z0-9-]{1,39}$ — unique per installation
name: "Acme · azul"
name_en: "Acme · blue"
version: 1                    # the author's own counter; the server bumps on replace
light:
  surface: "#FFFFFF"
  card: "#F8FAFC"
  text: "#0F172A"
  muted: "#64748B"
  grid: "#E2E8F0"
  primary: "#0B5FFF"
  positive: "#16A34A"
  negative: "#DC2626"
  neutral: "#64748B"
  series: ["#0B5FFF", "#F59E0B", "#10B981", "#8B5CF6", "#EF4444", "#06B6D4", "#F97316", "#84CC16"]
dark:
  surface: "#0B1220"
  card: "#111C2E"
  text: "#E2E8F0"
  muted: "#94A3B8"
  grid: "#1E293B"
  primary: "#60A5FA"
  positive: "#4ADE80"
  negative: "#FB7185"
  neutral: "#CBD5E1"
  series: ["#60A5FA", "#FBBF24", "#34D399", "#A78BFA", "#F87171", "#22D3EE", "#FB923C", "#A3E635"]
shape:                        # optional, enums only
  radius: md                  # sm | md | lg
  density: normal             # compact | normal
  kpi_scale: lg               # md | lg | xl
  font: sans                  # sans | serif | mono
  badge: filled               # filled | outline
```

Validation rules (the same function for the CLI, the upload and the import):

| Rule | Detail |
|---|---|
| keys | only the ones above; an unknown key is refused (a theme is data, never CSS) |
| required | `id`, `name`, `name_en`, `version`, `light`, `dark`; every colour token in both sets |
| id | `^[a-z][a-z0-9-]{1,39}$` |
| colours | `^#[0-9A-Fa-f]{6}$` |
| series | 3 to 8 entries |
| shape | each value from its list; the block may be absent |
| size | ≤ 20 KB |
| contrast | `text`/`surface` ≥ 4.5, `primary`/`surface` ≥ 3, each series vs `card` ≥ 3, adjacent series ΔE ≥ 20 (sequential themes excepted, checked on lightness steps), `positive` vs `negative` hue distance — both modes |

A failure is `{path, code, message}` where the message names the tokens and the measured value,
e.g. `light.text vs light.surface: 3.9:1 (needs 4.5:1)`.

## Theme (the stored row)

| Column | Type | Notes |
|---|---|---|
| `id` | text, PK | the theme's id |
| `name`, `name_en` | text | as authored |
| `version` | int | bumped by the server on replace |
| `tokens` | jsonb | the whole authored file, verbatim |
| `origin` | text | `builtin` \| `upload` \| `project` |
| `project_id` | bigint FK, null | set for `origin = project` |
| `created_by` | bigint FK, null | null for built-ins |
| `created_at`, `updated_at` | timestamptz | |

Transitions: `upload` creates or replaces (`version + 1`, confirmation required); a `project` row is
created by an import and removed when its project is deleted; a `builtin` row is refreshed from the
product's file at bootstrap and can be neither replaced nor deleted. A theme referenced by any
report's `layout.theme.id` cannot be deleted.

## Derived runtime tokens

`derive_tokens(theme, mode)` produces what the renderers already consume, so 030's mapping, the PDF
mirror and their tests stay valid:

| Runtime | From |
|---|---|
| `series1..series8` | `series[]`, in order (absent entries fall back to the last one) |
| `kpi_text` | `text` |
| `kpi_surface` | `card` |
| `neutral`, `grid`, `surface`, `primary`, `positive`, `negative` | the same names |
| `kpi_delta_bg.positive` / `.negative` | `positive` / `negative` mixed with `card` at 88 % |
| shape → CSS | `--t-radius`, `--t-density`, `--t-kpi-scale`, `--t-font`, `--t-badge` |

## Report fields

| Field | Type | Rules |
|---|---|---|
| `layout.theme.id` | string | a theme that exists in the installation; unknown → validation problem, render falls back |
| `layout.theme.palette` | string | **deprecated alias** of `id`, accepted for one version |
| `layout.theme.mode` | `auto` \| `light` \| `dark` | default `auto`; the PDF always uses `light` |

## Installation setting

`appearance_settings.theme_id` (new column, nullable) next to `palette_preset` (kept and read as a
fallback: an installation that chose before this feature keeps its look because the built-in ids are
the same).

## Resolution

```
report.layout.theme.id (or .palette) → installation theme_id → palette_preset → "impacto"
```
`impacto` is guaranteed present because the migration seeds it and a built-in cannot be deleted.
