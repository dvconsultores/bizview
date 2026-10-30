# Prompt — 047-themes-as-data: themes authored outside (with any AI), uploaded, validated, applied to any dashboard

Paste everything below the line into the coding agent with the repository open. Depends on 043
WS-E (palette resolved to CSS variables that every component reads); runs well alongside 044.

---

You are working on the BizView repository. Read `.specify/memory/constitution.md`,
`specs/043-bizview-refactor-external-authoring/spec.md` (WS-E) and
`specs/044-visual-components-assets/spec.md`. Implement **047-themes-as-data** end to end as
`/speckit-specify` (from this text) → `/speckit-plan 047-themes-as-data` → `/speckit-tasks` →
`/speckit-implement`. Do not ask me questions; take the decisions written here.

## Goal

A theme is a **data file of tokens** (never CSS, fonts or markup) that anyone — a person or any
AI — writes outside Bizview against a published schema, uploads in Apariencia or ships inside a
project zip, and applies to the installation or to any dashboard. Built-in presets (`impacto`,
`clasico`, `monocromo`, `contraste`, `daltonico`) become themes in the same format. Every
dashboard, share link, TV mode and PDF renders from the theme's tokens only.

## 1. Theme format (contract)

`cli/bizview_cli/schemas/theme.schema.json` (single source for CLI, backend, pack):

```yaml
id: acme-dark-blue            # ^[a-z][a-z0-9-]{1,39}$ ; unique per installation
name: "Acme · azul"
name_en: "Acme · blue"
version: 1
light:
  surface: "#FFFFFF"          # page background
  card: "#F8FAFC"
  text: "#0F172A"
  muted: "#64748B"
  grid: "#E2E8F0"
  primary: "#0B5FFF"
  positive: "#16A34A"
  negative: "#DC2626"
  neutral: "#64748B"
  series: ["#0B5FFF", "#F59E0B", "#10B981", "#8B5CF6", "#EF4444", "#06B6D4", "#F97316", "#84CC16"]   # 3–8
dark:
  … same keys …
shape:                        # all optional, from fixed enums
  radius: md                  # sm | md | lg
  density: normal             # compact | normal
  kpi_scale: lg               # md | lg | xl
  font: sans                  # sans | serif | mono   (built-in families only)
  badge: filled               # filled | outline
```

Rules enforced by the validator (`bizview theme validate <file>` and on upload):
- all keys present for `light` and `dark`; hex colours only; `series` 3–8 entries;
- the palette check from 030/043-E: text vs surface ≥ 4.5:1 (AA), series vs card ≥ 3:1,
  adjacent series distinguishable (ΔE ≥ 20), positive/negative not confusable (hue distance),
  primary vs surface ≥ 3:1 — for both light and dark; failures name the pair and the measured
  ratio;
- no other keys (`additionalProperties: false`); size ≤ 20 KB.

Built-in presets are converted to this format under `frontend/src/theme/themes/*.yaml` (mirrored
to the PDF renderer), and the palette check runs on them in CI as today.

## 2. Authoring with any AI

- The authoring pack gains `THEME.md`: one page telling an AI to produce `themes/<id>.yaml` from a
  brand guide, a screenshot or a description, with the schema, the contrast rules, and the
  instruction to output only the YAML. The pack also carries `theme.schema.json`.
- `bizview theme validate` and `bizview theme preview <file> --out preview.png` (renders the
  Apariencia preview card offline with the same components) so the author can iterate without
  the server.

## 3. Upload, library, apply

- **Apariencia** (standard admin page per 043 WS-E): the theme grid shows built-in and uploaded
  themes with the same live preview cards (KPI + badge, 4-bar chart, 2-series sparkline; light
  and dark side by side). Actions: "Subir tema" (YAML, validated, replaces same id with
  confirmation and version bump), "Descargar", "Duplicar" (as a starting point for an AI edit),
  "Eliminar" (refused while any report references it; built-ins cannot be deleted), "Usar en la
  instalación".
- **Per dashboard**: `layout.theme.palette: <theme id>` in `report.yaml` (rename the key to
  `layout.theme.id` with `palette` kept as a deprecated alias for one version) and
  `layout.theme.mode: auto | light | dark`; the Parámetros panel's "Paleta" selector lists all
  themes and the mode; the choice is saved on the report (super user) or per viewer (session) as
  030 defines.
- **Project zip**: `themes/*.yaml` inside a project are imported with it (validated like any
  artifact; collisions handled like ids in 031: rename/replace/skip) and listed in Apariencia
  with the project as origin. Export includes them.
- **Mode**: `mode: dark` forces the report area dark regardless of the app theme (chrome stays
  as the user chose); a sun/moon toggle on the report lets the viewer override; share links open
  in the report's mode first; PDF is always the theme's light variant.
- **Resolution**: report theme → installation theme → `impacto`; resolved once per page into CSS
  custom properties (043-E) and into the PDF palette; no component may read a literal colour
  (lint rule stays).

## 4. Storage and API

- Table `theme(id, name, name_en, version, tokens jsonb, origin: builtin|upload|project,
  project_id NULL, created_by, created_at, updated_at)`; Alembic migration seeds the built-ins.
- `GET/POST/DELETE /api/admin/themes`, `GET /api/themes/{id}` (viewers), `PUT
  /api/admin/settings/theme` (installation default); audit on upload/replace/delete/apply.
- Caching: theme JSON served with ETag; frontend settings store invalidates on change.

## Tests

- Schema + validator: valid/invalid fixtures (missing key, bad hex, 2 series, contrast failure
  naming the pair); built-ins all pass; `bizview theme validate` exit codes.
- Upload: replace with version bump; delete refused while referenced; project-shipped theme
  imported, listed with origin, exported back.
- Apply: selecting a theme changes `--series-1` and `--surface` on a rendered report in the
  same session and after reload; `mode: dark` forces the report area dark with the app in light;
  share link opens in the report's mode; PDF uses the light variant (snapshot).
- Preview cards contain SVG with the theme's colours (snapshot per theme × mode).
- Live eval (opt-in): from `THEME.md` and a reference screenshot, an AI produces a theme that
  validates on first upload in ≥ 4 of 5 runs.

## Deliverables

- Schema, validator, CLI commands, migration, API, Apariencia changes, report schema fields
  (`theme.id`, `theme.mode`), `THEME.md` in the pack, `es.ts`/`en.ts`, docs (`docs/THEMES.md` +
  help topic), CHANGELOG under Unreleased.
- Constitution check in the plan: I (mobile-first; shape tokens only from enums), V (no new
  component), VII (themes are configuration/data), IX (declarative, validated). No amendment.

Commits: (1) schema + validator + built-ins converted + CI, (2) storage + API + migration, (3)
Apariencia grid/upload/preview, (4) report fields + resolution + mode + share/PDF, (5) project
import/export of themes, (6) CLI + THEME.md + docs + CHANGELOG.
