# Implementation Plan: Visual components and project images

**Branch**: `044-visual-components-and-assets` (work on the current branch; no branch is created —
repository policy) | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/044-visual-components-and-assets/spec.md`

## Summary

Dashboards and PDFs need four visual components (asset, gauge, index, share) and images that come
from the project itself. Half of it is already in the tree: 042 Batch C added the four kinds to
`cli/bizview_cli/schemas/report.schema.json` and to `frontend/src/components/report/LayoutRenderer.tsx`,
so the screen renders them today. What this feature adds:

1. **`assets/` inside a project** — a new allowed folder, content-sniffed on write, versioned with
   the project, exported back in the zip and served by the product (US1).
2. **`images:` declarations and `image:` on components** — the lookup (asset by key → cached URL →
   fallback) becomes declarative and validated (US1/US3).
3. **The PDF half of the four components** — `backend/app/reports/pdf_layout.py` has none of them
   (US2).
4. **`image_url` columns cached by the worker** — third-party logos fetched once, served locally
   (US3).

The riskiest part is not the drawing: it is that the published contract (schema + allowlist) changes,
so the authoring skeleton and the example project must ship in the same release.

## Technical Context

**Language/Version**: Python 3.13 (backend, `uv`), TypeScript + React (frontend, Vite)

**Primary Dependencies**: FastAPI, SQLAlchemy 2 + Alembic, ReportLab (`backend/app/reports/pdf_layout.py`),
httpx with the existing `backend/app/security/netguard.py` guard; React + Tailwind; `jsonschema`
via `cli/bizview_cli/validate.py`

**Storage**: PostgreSQL for metadata; files under `PROJECTS_DIR/<slug>/assets/…` for project images.
The cached URL images need a directory of their own — **not** `attachments/`, which 043 removes.

**Testing**: `pytest` (backend), `vitest` (frontend unit), Playwright (browser matrix at 320/375 px),
`bizview validate` golden projects in `cli/bizview_cli/golden*`

**Target Platform**: Linux server (Docker Compose), mobile-first web UI

**Project Type**: web service + SPA + CLI

**Performance Goals**: images ≤ 300 KB each, ≤ 25 MB per project; at most 500 new URL images per
integration run; a dashboard with 40 logos renders without a perceptible delay on a 375 px phone

**Constraints**: palette roles are the only colour source (030); no new stack component (constitution
V); no AI anywhere (VIII/IX); `cli/bizview_cli/workspace_template/` is untouched

**Scale/Scope**: the reference project ships 483 logos; a project folder stays under 25 MB

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1.*

| Principle | Gate | Result |
|---|---|---|
| I Mobile-first | new components usable at 320 px, WCAG 2.2 AA, `alt` on every image | PASS — tested at 320/375 px in the browser matrix |
| II/VI Backend as ETL | images are static files; the URL cache fetches once per value and never blocks a load | PASS — see research R4 |
| III Source of truth external | `image_url` fetches are read-only GETs under `netguard` policy | PASS |
| IV Separated concerns | assets under the project folder; cache outside it, in the data volume | PASS |
| V Fixed stack | ReportLab draws the PDF shapes; no new framework. SVG in PDF is the one place V could bend — R3 settles it without a new dependency | PASS with R3's rule |
| VII One product, many installations | assets are project configuration, versioned with the project | PASS |
| VIII AI optional/private | no AI in this feature | PASS |
| IX Spec-driven | `images:` and the components are declarative and validated | PASS |

No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/044-visual-components-and-assets/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── project-assets.md      # the folder, its limits and the serving route
│   └── report-images.md       # the declarative `images:` block and `image:` on components
└── tasks.md             # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
cli/bizview_cli/
├── layout.py                    # + assets/ in PROJECT_PATTERNS, FOLDER_PATTERNS, ALLOWED_TEXT
├── schemas/report.schema.json   # + images: block, + image: on components
├── validate.py                  # + image-set checks (folder exists, key is declared)
└── golden*/                     # example project gains assets/coins + the four components

backend/app/
├── projects/
│   ├── assets.py                # NEW: sniffing, SVG sanitisation, lookup by key, normalisation
│   ├── fs.py                    # + read_asset (binary, size-capped), assets listed with the tree
│   └── zip.py                   # export/import carry assets/
├── api/projects.py              # + GET /{slug}/assets/{path} with ETag + immutable caching
├── reports/pdf_layout.py        # + gauge, index, share, asset blocks; raster embedding
├── engine/extract.py            # + column kind image_url (kept as text)
├── engine/runner.py             # + image-cache pass after a successful load
├── images/                      # NEW: the URL cache (fetch, hash, record, sweep)
└── config.py                    # + IMAGE_CACHE_DIR and its retention knobs

frontend/src/
├── components/report/LayoutRenderer.tsx   # already renders the four; + images in table/asset
└── api/types.ts                           # + images on the report payload
```

## Phasing

- **Phase A — the folder and the contract.** `assets/` in the allowlist with content sniffing;
  `zip.py` carrying it both ways; `GET /{slug}/assets/{path}` with ETag; SVG sanitisation. This
  alone makes US1 possible with a hand-edited report.
- **Phase B — `images:` and `image:`.** Schema, validator, renderer lookup (asset → fallback), the
  table cell and the asset tile; the example project.
- **Phase C — the PDF half.** Four block kinds in `pdf_layout.py` plus raster embedding; the
  screen/PDF figure test.
- **Phase D — the URL cache.** `image_url` columns, the worker pass, the cache directory and its
  settings, the once-a-day retry rule.

Each phase leaves the product shippable: A ships images, B ships them declaratively, C ships them in
PDF, D ships remote logos.

## Open decisions carried into Phase 0

- **R1** Where assets sit and how they are served (route, ETag, share links).
- **R2** SVG: sanitise and serve, or refuse?
- **R3** SVG in the PDF: which rule avoids a new dependency.
- **R4** The URL cache: directory, settings, failure semantics.
- **R5** Where `image:` sits relative to the existing positional `columns` of the asset tile.
