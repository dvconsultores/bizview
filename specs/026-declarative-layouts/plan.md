# Implementation Plan: Declarative layouts for dashboards and PDF reports

**Branch**: `026-declarative-layouts` | **Date**: 2026-10-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/026-declarative-layouts/spec.md`

## Summary

One optional `layout` object joins the report definition (`reports/<id>/report.yaml`) with a `web`
half and a `pdf` half. Both are declarative documents with no expressions, no code and no literal
colours; both bind to the report's declared views, metrics, dimensions and filters **by id only**.
The schema lives in `cli/bizview_cli/schemas/report.schema.json`, which is already the single source
that the CLI validator, the backend (`from bizview_cli import validate as wsv`) and the Asistente's
authoring summary (`cli/bizview_cli/authoring.py`) all read.

Rendering is product code on both sides: a new `LayoutRenderer` in the frontend composes the
dashboard from the component catalogue, and a new `PdfLayoutRenderer` in
`backend/app/reports/` maps blocks to ReportLab flowables and `reportlab.graphics.charts`. Both read
the same payload from the same engine call (`backend/app/api/reports.py::_data` feeds both the JSON
route and `pdf.render`), so figure parity is structural rather than a promise; the two derived facts
that would otherwise be computed twice — a per-view text summary (accessibility, PDF alt text) and
table totals — are produced once in `backend/app/engine/report.py` and consumed by both renderers.

Absent `layout`, nothing changes: the web keeps deriving its composition from `data.views`
(`frontend/src/components/report/ReportViews.tsx`) and the PDF keeps the `pdf` config it has today.

## Technical Context

**Language/Version**: Python 3.11+ (backend, CLI), TypeScript + React 19 + Vite (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, ReportLab (platypus and, new in use here,
`reportlab.graphics.charts` — part of the installed ReportLab, not a new package), `jsonschema`
Draft 2020-12, `yaml`; React 19, Vite, Tailwind CSS; the app's own SVG chart components. **No new
dependency and no new stack component** (constitution V). Recharts stays a declared stack component
and stays unused by this feature (see *Findings that touch the spec*, item 2).

**Storage**: PostgreSQL, **no schema change**. The layout is part of the report definition: it
travels as a workspace artifact (`WorkspaceVersion.artifacts["reports"]`), the engine exposes it in
the normalized definition JSON (`backend/app/engine/report.py::definition_json`), and the frontend
receives it on `GET /api/reports/:id` (unknown definition keys are already preserved verbatim).

**Testing**: `pytest` (`backend/tests`, `cli/tests`), `vitest` (`frontend/src/**/*.test.tsx`),
Playwright e2e (`frontend/tests/e2e`, phones at 320/375 px, desktop 1280×900). PDF assertions use the
existing uncompressed-stream text reader `backend/tests/test_reports_params.py::_pdf_lines` — no PDF
parsing dependency is added.

**Target Platform**: Docker Compose (Caddy edge, backend, worker) against an external PostgreSQL;
the CLI runs in the customer's workstation and in CI.

**Project Type**: web application — FastAPI backend + React frontend + a shared Python CLI that owns
the artifact schemas.

**Performance Goals**: PDF with 4 blocks and a 500-row table under 10 s (SC-003); dashboard response
unchanged (API under 200 ms on optimized models, constitution II); no new queries to any source.

**Constraints**: layouts carry no executable content (FR-002, SC-004); the AI never emits rendering
code (FR-012); PDFs only from the backend with ReportLab, `application/pdf` only; branding resolved
from the installation by role (VII); mobile-first at 375 px (2.1); every user-visible string in
Spanish and English.

**Scale/Scope**: 8 web components (`kpi`, `line`, `area`, `bar`, `pie`/`donut`, `table`, `text`,
`filters`, `spacer`) and 8 PDF blocks (`page`, `header`, `kpi_row`, `chart`, `table`, `text`,
`page_break`, `footer`); one schema addition; ~3 new frontend modules plus adapters; one PDF
renderer; CLI validation with errors and warnings; guide text plus golden layouts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / constraint | How this feature complies | Verdict |
|---|---|---|
| I. Mobile-first | The declared order **is** the phone order; the 12-column grid is applied only from the desktop breakpoint; SC-001 measures 375 px and 1280 px, Playwright runs 320/375 px. | PASS |
| II / VI. Backend as ETL, tuning | No new query path: both renderers consume the payload of one `engine.run_views()` call over optimized models; the layout changes composition, never data access. | PASS |
| III. Source of truth external | Untouched; no origin connection, no SQL in layouts. | PASS |
| IV. Separated concerns | Schema in `cli/` (shared with backend + guide), web renderer in `frontend/`, PDF renderer and its block mapping in `backend/app/reports/`. No cross-folder shortcut. | PASS |
| V. Fixed stack | Recharts and ReportLab are already stack components; `reportlab.graphics.charts` ships inside ReportLab. Nothing added, replaced or removed. | PASS |
| VII. One product, many installations | Layouts name semantic roles and font names; the installation's theme/branding resolves them. No customer names, logos, hex colours or paths in a layout. | PASS |
| VIII. AI optional and private | No change to provider inputs. The AI receives the report schema fragment it already receives (now including the layout) and emits YAML only. | PASS |
| IX. Spec-driven reporting | The layout is declarative customer logic; `bizview validate` and `compose.validate_project()` reject a layout that fails, so "no spec, no run" extends to layouts (FR-013). | PASS |
| Constraints (PDF, html2canvas, i18n) | PDF stays backend/ReportLab with `application/pdf`; html2canvas untouched; new strings in both catalogues; layout text uses the `text`/`text_en` convention. | PASS |

**Post-design re-check**: PASS. No violations, so **Complexity Tracking is empty**.

**Supporting libraries used, with reason** (constitution V): `reportlab.graphics.charts` (vector bar
and pie drawings inside the existing ReportLab dependency — avoids rasterising charts server-side);
`jsonschema` Draft 2020-12 (already the artifact validator, supports the internal `$ref`s the layout
definitions use). No other library is introduced.

## Project Structure

### Documentation (this feature)

```text
specs/026-declarative-layouts/
├── spec.md              # Feature specification (owner's draft, adopted)
├── plan.md              # This file
├── research.md          # Phase 0: decisions, rationale, alternatives
├── data-model.md        # Phase 1: entities, fields, validation rules
├── quickstart.md        # Phase 1: runnable validation scenarios
├── contracts/
│   ├── layout-web.md    # layout.web document contract
│   ├── layout-pdf.md    # layout.pdf document contract
│   └── renderer-api.md  # renderer interfaces, engine payload additions, problem shape
├── checklists/
│   └── requirements.md  # spec quality checklist (/speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
cli/
├── bizview_cli/
│   ├── schemas/report.schema.json   # CHANGED: $defs "web_layout" and "pdf_layout", optional top-level "layout"
│   ├── report_layout.py             # NEW: reference checks + chart-suitability warnings (one implementation)
│   ├── validate.py                  # CHANGED: call the checks; keep the SCHEMAS registry
│   ├── authoring.py                 # CHANGED: layout lines in _report_summary(); layout fragment for the guide
│   ├── golden/projects/ejemplo/reports/facturas-dia/report.yaml        # CHANGED: golden dashboard layout (SC-001)
│   └── golden-direct/projects/ejemplo/reports/ventas-directo/report.yaml # CHANGED: golden one-page PDF layout (SC-003)
└── tests/test_report_layout.py      # NEW

backend/
├── app/
│   ├── engine/report.py             # CHANGED: expose "layout" and "layout_problems"; add per-view "summary"/"totals"
│   ├── reports/pdf.py               # CHANGED: PdfLayoutRenderer entry, block dispatch
│   ├── reports/pdf_layout.py        # NEW: block -> flowable mapping (chart kinds, overflow policy, footer)
│   ├── assistant/tools.py           # CHANGED: content check on draft YAML (FR-012/SC-004)
│   ├── assistant/readiness.py       # CHANGED: both layout halves asked for by the completeness check (FR-011)
│   └── assistant/guide/{es,en}/     # CHANGED: definir-un-reporte.md documents the catalogue with examples
└── tests/
    ├── test_pdf_declarative_layout.py  # NEW: blocks, overflow, one page, 500-row budget
    └── test_layout_parity.py           # NEW: dashboard payload vs PDF text, same filters/period (SC-002)

frontend/
├── src/
│   ├── api/types.ts                       # CHANGED: layout types on ReportDefinition
│   ├── components/report/LayoutRenderer.tsx# NEW: web grid + component dispatch + error card
│   ├── components/report/charts/          # NEW: bar/stacked/pie/donut/sparkline built on the app's SVG primitives
│   ├── components/report/ReportViews.tsx  # CHANGED: delegate to LayoutRenderer when layout.web exists
│   ├── components/report/DataTable.tsx    # CHANGED: optional columns/totals/sort/page size from the layout
│   ├── index.css                          # CHANGED: --c-chart-1..8 series tokens (light + dark)
│   └── i18n/{es,en}.ts                    # CHANGED: new renderer strings
└── tests/
    ├── e2e/layout.spec.ts                 # NEW: 375 px and 1280 px, both themes, a11y summary
    └── components/report/*.test.tsx       # NEW: unit tests per component kind
```

**Structure Decision**: the existing three-folder split is kept exactly as constitution IV defines it.
The layout schema goes where every other artifact schema already is (the CLI package, which the
backend imports and the Asistente's guide is generated from), so there is one schema for the CLI, the
backend, the studio editor and the AI. The renderers stay in the folder that owns rendering: web in
`frontend/`, PDF in `backend/app/reports/` (constitution IV: "PDF report code belongs to the backend").

## Findings that touch the spec

Three facts found while mapping the code; each needs the Owner's word because it changes spec wording
or a budget, not the intent. None of them reshapes the feature.

1. **A `pdf` object already exists, and it is not called `pdf_layout`.** The schema declares
   `pdf: {enabled, orientation, views}`; the engine publishes it to the API as `pdf_layout`
   (`backend/app/engine/report.py`), which is what `pdf.render()` reads. Six call sites gate the
   export on `definition["pdf"]`, including the mail attachments
   (`backend/app/mail/subscriptions.py`, `backend/app/mail/sends.py`) and the shared link. The plan
   therefore keeps `pdf.enabled` as the export gate, lets `layout.pdf.page.orientation` win when a
   layout declares it, and keeps `pdf.orientation`/`pdf.views` honoured when there is no layout
   (FR-009). FR-004's `page` block is not reduced; it just becomes the preferred place for
   orientation.
2. **FR-006's wording does not match the code: the frontend does not use Recharts.** Charts are the
   app's own SVG (`frontend/src/components/report/TrendChart.tsx`,
   `RankingTable.tsx`), and there is no bar, stacked bar, pie, donut, sparkline, top-N "otros",
   table sorting, table totals or pagination anywhere in `frontend/src`. So FR-006's "maps components
   to existing Recharts-based chart components" is not available as written: the catalogue needs new
   chart kinds. The plan extends the existing SVG primitives rather than adopting Recharts inside
   this feature (no new dependency, the theming, currency, gap and tooltip behaviour are already
   tested there), and asks the Owner to re-word FR-006 as "maps components to the report's chart and
   table components".
3. **SC-001's "visual tests in the frontend suite" needs its first snapshot.** No Playwright test
   uses `toHaveScreenshot` today; the suite asserts geometry, text and axe results. The plan adds
   screenshot assertions for the seeded layout at 375 px and 1280 px in both themes; if the Owner
   prefers no new snapshot mechanism, the same coverage is expressible as order/span/geometry
   assertions and SC-001 should say so.

Unrelated to this plan but noted from the spec's assumptions: no spec numbered 026 exists in
`specs/`, so the demo-installation spec can take 027 with nothing to renumber inside this repository.

## Complexity Tracking

> No constitution violation to justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
