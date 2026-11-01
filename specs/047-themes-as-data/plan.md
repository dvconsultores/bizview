# Implementation Plan: Themes as data, authored outside

**Branch**: `main` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/047-themes-as-data/spec.md`

## Summary

Publish a **theme** format — a file of tokens — and make every surface render from it. The five
built-in palettes are rewritten in that format and keep their exact look; the runtime tokens the
screens and the PDF already consume (`series1..8`, `kpi_text`, `kpi_delta_bg`, …) are **derived**
from the authored tokens, so 030's rendering and its contrast gate stay intact while the *authored*
contract becomes the published one. Themes are stored in a table, uploaded and applied in Apariencia,
declared per report, shipped inside a project zip, and validated by one schema three consumers read.

## Technical Context

**Language/Version**: Python 3.12 (backend, CLI), TypeScript 5 / React 19 (frontend), PostgreSQL 16.

**Primary Dependencies**: existing only — `jsonschema` (already the CLI's, used by every artifact
schema) validates the theme's *shape*, and a hand-written pass adds what a schema cannot say: the
contrast, series-ΔE and polarity mathematics, with the measured value in the message.

**Storage**: one new table `theme` (tokens as JSONB), a migration seeding the five built-ins, and
`report.yaml`'s `layout.theme.{id,mode}` (with `palette` kept as a deprecated alias).

**Testing**: `pytest` (backend), `vitest` (frontend), the existing palette/contrast gates extended to
run over every theme in the database seed and the built-in files, and the CLI's own suite.

**Target Platform**: the self-hosted installation (web + PDF) and the author's machine (CLI).

**Project Type**: full-stack product feature (schema + CLI + storage/API + admin UI + report
rendering + project import/export + docs).

**Performance Goals**: the resolved theme is computed once per page and per PDF render; a theme is
≤ 20 KB and read from a cached map, so no measurable cost.

**Constraints**: no new dependency; no colour literals in components (the existing lint rule stays);
the PDF keeps its byte-identical mirror discipline; `layout.theme.palette` must keep validating for
one version.

**Scale/Scope**: 5 built-in themes, 1 schema, 2 renderers, 1 admin page, 1 report field pair, 1 CLI
command group, 2 documents and a help topic.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Mobile-first | The theme changes colour and shape tokens only; the appearance page and the report toolbar keep their 320 px layouts and add one select, one toggle and a grid of cards | PASS |
| II. Nothing runs unvalidated | A theme enters the database only after the validator accepts it — upload, project import and the seed all go through the same function | PASS |
| IV. Separated concerns by folder | The contract lives in `cli/bizview_cli/schemas/` and the rules in `cli/`; the backend reads it, the frontend derives CSS variables, the pack ships it | PASS |
| V. Fixed technology stack | No component added: the schema is data, the validator is Python already in the tree, the UI is React already in the tree | PASS |
| VII. One product, many installations | A theme is configuration and data — the installation's choice and a project's artifact, never a code fork | PASS |
| VIII. AI optional and private | The authoring page tells an AI how to write tokens; a theme carries colours and enums, so the AI receives no data | PASS |
| IX. Spec-driven reporting | `themes/<id>.yaml` is a declarative artifact validated like the rest, and the engine refuses an unvalidated one | PASS |

No violation; no amendment (the brief agrees). Recorded simplification: the contrast/distinguishability
mathematics is duplicated between the TypeScript gate and the Python validator today; this feature
keeps the Python one authoritative for *acceptance* and leaves the TS gate as the renderer's own
check, and a task asserts they agree on the five built-ins.

## Project Structure

### Documentation (this feature)

```text
specs/047-themes-as-data/
├── spec.md
├── plan.md                     # this file
├── research.md                 # Phase 0
├── data-model.md               # Phase 1
├── quickstart.md               # Phase 1
├── contracts/
│   ├── theme-format.md         # the published contract, prose + the schema's shape
│   ├── theme-api.md            # the endpoints and their refusals
│   └── theme-resolution.md     # report → installation → default, and the mode rules
└── tasks.md
```

### Source Code (repository root)

```text
cli/bizview_cli/
├── schemas/theme.schema.json          NEW: the single source of the contract
├── theme.py                           NEW: validate a theme file, derive runtime tokens
├── validate.py                        + themes/ inside a project are validated as artifacts
└── __main__.py                        + `bizview theme validate|preview`

backend/app/
├── models.py                          + Theme (tokens JSONB, origin, project_id, version)
├── alembic/versions/0042_themes.py    NEW: table + seed of the five built-ins
├── api/themes.py                      NEW: GET/POST/DELETE admin, GET viewer, settings
├── api/appearance.py                  the installation theme becomes a theme id
├── reports/palette.py                 resolves a theme's tokens → the PDF's colours
├── reports/pdf.py                     reads the resolved theme
├── projects/zip.py                    themes/*.yaml in and out
└── projects/validate (via compose)     a report's theme id must exist

frontend/src/
├── theme/themes/*.yaml → .json         the five built-ins in the new format
├── theme/palette.ts → theme.ts         derived runtime tokens + CSS variables
├── theme/ThemeContext.tsx              applies the resolved theme, per report mode
├── pages/admin/Appearance.tsx          the library, the upload, the preview cards
├── components/report/ReportView.tsx    the sun/moon toggle, the report-area mode
└── api/types.ts                        Theme, ThemeTokens, report theme fields

docs/THEMES.md                          NEW;  backend/app/guide/{es,en}/temas.md  NEW
backend/app/guide/index.yaml            a topic in the admin section
```

**Structure Decision**: the contract belongs to `cli/` (it already owns the artifact schemas the
backend and the pack read); the built-ins are product data in the frontend's theme folder with a
byte-identical mirror for the PDF, exactly as 030 established; the admin UI stays on the existing
Apariencia page rather than a new screen.

## Complexity Tracking

| Simplification | Why |
|---|---|
| Two-layer validation, one entry point | `theme.schema.json` through `jsonschema` refuses the shape (unknown key, bad hex, 2 series) with the path it already formats for every artifact; the hand-written pass refuses a *look* (contrast, ΔE, polarity) that no schema can express. `validate_theme()` runs both, so callers see one answer. |
| Runtime tokens derived, not authored | Keeping `series1..8`/`kpi_text`/`kpi_delta_bg` as derived values keeps 030's CSS-variable mapping, its PDF mirror and its tests untouched, so this feature cannot regress the rendering it is meant to make configurable. |
| `preview` renders in the console, not a browser | `bizview theme preview` writes the same SVG the admin preview card draws (a KPI card, a four-bar chart and a two-series sparkline) so an author can iterate offline; reusing the React component would need a headless browser, which is a dependency. |
