# Phase 1 — Data model: Report page polish

Five things carry state. Two are persisted (a new table, a new column), one is product data on disk,
one is a declarative field inside the report definition, and one is the existing URL/localStorage
state this feature reuses. No existing table changes shape.

## 1. `PalettePreset` — product data (files in the repo)

One JSON file per preset, `frontend/src/theme/palettes/<id>.json`, mirrored byte-identically in
`backend/app/reports/palettes/<id>.json`. Not a table: a preset ships with the product and every
installation has all five.

| Field | Type | Rules |
|---|---|---|
| `id` | string | equals the file name; one of `impacto`, `clasico`, `monocromo`, `contraste`, `daltonico` |
| `label_key` | string | i18n key suffix (`palette.impacto`, …) — no display text in the data |
| `strategy` | `"categorical" \| "sequential"` | tells the palette check which distinguishability rule applies |
| `light`, `dark` | object, one per theme | both required; the PDF uses `light` only |

Each of `light`/`dark` (identical shape, both complete — no inheritance between themes):

| Role | Type | Meaning | Web token | PDF use |
|---|---|---|---|---|
| `primary` | hex | the preset's own primary, used when branding would clash | `--c-chart-1` fallback, `--c-primary`*(never — interface keeps branding)* | title rule, KPI accent |
| `series1`…`series8` | hex ×8 | categorical series, in order | `--c-chart-1`…`--c-chart-8` | line/bar/pie series, table headers |
| `positive` | hex | favourable delta / value | `--c-success*` family anchor | delta text, positive KPI |
| `negative` | hex | unfavourable delta / value | `--c-danger*` family anchor | delta text, negative KPI |
| `neutral` | hex | no-comparison delta, secondary text | `--c-kpi-neutral` | delta text |
| `grid` | hex | chart grid lines | `--c-chart-grid` | grid, table lines |
| `surface` | hex | card surface the check measures against | `--c-kpi-surface` | block background |
| `kpi_text` | hex | KPI numeral colour | `--c-kpi-text` | KPI numeral |
| `kpi_delta_bg` | `{positive: hex, negative: hex}` | filled delta badge backgrounds | `--c-kpi-delta-bg-*` | delta badge fill |

**Invariants (enforced by `tests/unit/palette-presets.test.ts`, FR-010):**

1. Every `series[n]`, `positive` and `negative` reaches **≥3:1** against that theme's `surface`
   (`contraste`: **≥7:1**). *This is why `clasico` cannot ship with today's `chart-2` (`#98C3D8`,
   1.89:1) — research R4.*
2. Adjacent series ΔE (CIE76, Lab) **≥10** for `categorical` presets; for `sequential`
   (`monocromo`) monotonic lightness with ΔL\* **≥5** per step and ≥3:1 for every shade.
3. `positive` vs `negative` ΔE **≥25** and both ≥3:1 — the semantic pair can never be confused.
4. `kpi_text` **≥4.5:1** against `surface`; `kpi_delta_bg.*` text **≥4.5:1** against its own fill.
5. `grid` is subtle: **<1.8:1** against `surface`.
6. Both theme objects are complete; unknown role names are rejected by the type (`PalettePreset`) and
   by the test.
7. The backend mirror is byte-identical to the frontend file (drift = failing test).

## 2. `AppearanceSettings` — persisted (new singleton table)

`appearance_settings`, one row (`id = 1`), created by migration `0027_appearance_palette`. Mirrors the
`telegram_settings` singleton pattern.

| Column | Type | Rules |
|---|---|---|
| `id` | smallint PK | always `1` (check) |
| `palette_preset` | varchar(32) | not null, default `'impacto'`, check `IN` the five ids |
| `updated_at` | timestamptz | `server_default now()`, set on update |
| `updated_by` | bigint FK `app_user.id` | nullable (bootstrap row has no author) |

**Rules:** written only by `PUT /api/admin/appearance` (super user, CSRF, audited as
`appearance_updated`); read by `GET /api/admin/appearance`, by the PDF renderer and by `GET /api/config`
(public — the shared view is unauthenticated). An installation with no row (fresh or pre-0027 install
before the migration seeds it) behaves as `impacto`.

**State transitions:** `(any preset)` → `PUT` with another id → validate → write → audit. There is no
intermediate state; an invalid id is `422` and nothing changes.

## 3. Report definition — `layout.theme.palette` (declarative, versioned)

Inside the existing `layout` object of the report definition (026), so it travels with the workspace
version and reaches both renderers.

| Key | Type | Rules |
|---|---|---|
| `layout.theme` | object | optional; no other keys accepted (`additionalProperties: false`) |
| `layout.theme.palette` | string | optional; one of the five preset ids; absent = "use the installation's" |

**Validation:** `cli/bizview_cli/schemas/report.schema.json` (JSON Schema) and
`cli/bizview_cli/report_layout.py` (`_enum` → a `layout_range` issue naming the five ids, Spanish
message, same shape as every other enum field); hex literals remain refused by `_LITERAL`, so 026
FR-005 is intact. Typed as `ReportDefinition.layout?.theme?: { palette?: PaletteId }` in
`frontend/src/api/types.ts`.

**Relationship:** one report definition → zero or one palette override; zero → the installation
preset applies.

## 4. Effective preset — derived (no storage)

```text
effective = definition.layout.theme.palette
         ?? installation.palette_preset      (appearance_settings, default "impacto")
         ?? "impacto"
theme     = resolved viewer theme ("light" | "dark")  → web uses preset[theme]
pdf       = preset["light"]                            → always light (FR-006, FR-011)
```

Resolved identically by `frontend/src/theme/palette.ts` (web + shared view) and
`backend/app/reports/palette.py` (PDF). The value is applied by writing CSS custom properties on
`<html>` plus `data-palette="<id>"`; nothing is persisted per viewer.

## 5. `ShareLink.theme` — persisted (new nullable column)

| Column | Type | Rules |
|---|---|---|
| `theme` | varchar(5) | nullable; check `IN ('light','dark')`; `NULL` = "follow the viewer" (today's behaviour) |

**Rules:** set optionally at creation (`POST /api/sharing/links`); returned by
`GET /api/shared/{token}`; the shared view applies it **only** when the viewer has no stored
preference. Revocation, expiry and visit counting are untouched.

**Relationship:** one share link → zero or one forced theme; the viewer's browser preference
(`localStorage["bizview.theme"]`, existing) always wins after the first load.

## 6. Reused state (not changed by this feature)

| State | Where | Role here |
|---|---|---|
| `ReportSelection` (period, compare, custom range, filters) | query string, `lib/reportQuery.ts` | the sheet edits it; chips and meta line read it; unknown filter ids are ignored (existing behaviour) |
| Viewer theme preference | `localStorage["bizview.theme"]` + `app_user.theme` | shared view toggle writes the device value; `theme-init.js` still paints it before React |
| Installation branding (`--brand-*`) | env config + `index.css` | interface `primary` only; never series colours (research R6) |

## Deletion

`ParamsPanel.tsx` and `useReportPanelCollapsed` (and the `reportParams.collapse` /
`reportParams.expand` strings) have exactly one consumer — `ReportView`. The sheet replaces them, so
they are removed rather than left as dead code.
