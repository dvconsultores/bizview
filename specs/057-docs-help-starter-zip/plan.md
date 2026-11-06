# Implementation Plan: Help, README and starter zip

**Branch**: `main` (no feature branches) | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/057-docs-help-starter-zip/spec.md`

## Summary

One pack, rendered three ways. `pack/bizview-starter-pack/` at the repository root is the only
source: the server renders it per project (`GET /api/projects/starter`), the release publishes it
with placeholders (`make starter-template` → committed `bizview-starter-template.zip`), and the CLI
writes it (`bizview init project`, and `bizview init workspace` into `projects/<slug>/`). The guide
loses the removed agent's section and gains `crear-con-ia` plus `importar-y-aplicar`; the README and
`docs/` describe the five steps and the real capability set.

## Technical Context

**Language/Version**: Python 3.12 (backend + CLI), TypeScript/React 19 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy, PyYAML, jsonschema (`bizview_cli`), Vite, Tailwind

**Storage**: PostgreSQL for the product schema; the pack and the committed template are files

**Testing**: pytest (backend, CLI), vitest (frontend), `sh scripts/gates/*.sh` (repository gates)

**Target Platform**: Linux server (Docker Compose) and mobile-first browsers

**Project Type**: web application (backend + frontend) with a published CLI

**Constraints**: bilingual es/en everywhere; no new dependency; no AI call inside the product; the
zip carries structure only, never a row value; markdown gate and vocabulary gate must pass

**Scale/Scope**: one new module in the CLI, one in the backend, two routes, one dialog, one section
and nine topics in the guide, seven documents

## Constitution Check

*GATE: must pass before Phase 0 research and again after Phase 1 design.*

| Principle | How this plan complies |
|---|---|
| I. Mobile first | the dialog is a single column at 320 px, tap targets ≥ 44 px, no table |
| II. Backend as ETL / nothing leaves the installation | the structure file is built by `sources.structure.build`, the generator 048/052 already uses; only that document travels |
| III. Source of truth is external | the pack is a template; the project is authored outside and imported |
| IV. Separated concerns by folder | `pack/` holds templates, `cli/bizview_cli/starter.py` renders, `backend/app/projects/starter.py` serves |
| V. Fixed stack | no new dependency; `zipfile`, `importlib.resources`, React, FastAPI |
| VI. Data tuning over raw storage | not applicable |
| VII. One product, many installations | the pack is versioned with the product; the template is resolved from the repository or an env override |
| VIII. AI optional and private | the pack's prompt is text; no key is needed in Bizview |
| IX. Spec-driven reporting | the pack carries `PROMPT.md`, `REQUEST.md`, `specs/`, the schemas and the rules; import still validates |
| Constraints: one contract | the schemas come from `cli/bizview_cli/schemas/`, copied at render time, never duplicated in the pack |

**Result**: PASS. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/057-docs-help-starter-zip/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
├── contracts/starter-api.md
└── tasks.md
```

### Source code

```text
pack/bizview-starter-pack/          the pack source (es/, en/, files/)
pack/bizview-starter-pack/files/    skeletons with {{placeholders}}
bizview-starter-template.zip        rendered template, committed (repo root)
Makefile                            `make starter-template`
scripts/build_starter_template.py   renders the template deterministically

cli/bizview_cli/starter.py          renderer: pack_dir(), render(), zip_bytes()
cli/bizview_cli/init.py             `init project`; `init workspace` writes the pack
cli/bizview_cli/__main__.py         the new subcommand
cli/tests/test_starter.py           combinations, validator, contents coverage, determinism

backend/app/projects/starter.py     build(), budget check, structure pack
backend/app/api/projects.py         GET /starter, GET /starter-template
backend/tests/test_starter_api.py   both routes

frontend/src/components/projects/StarterDialog.tsx
frontend/src/pages/projects/Projects.tsx
frontend/src/api/projects.ts, types.ts
frontend/src/i18n/es.ts, en.ts

backend/app/guide/index.yaml, es/*.md, en/*.md
README.md, README.es.md, docs/*.md, docs/es/*.md, CHANGELOG.md
```

## Phase 0 — Research

See [research.md](./research.md). Decisions: the single-source pack shipped inside the wheel by
`hatch` `force-include`; deterministic zip bytes (fixed timestamp, sorted entries); the skeleton
validates as a v2 project when rendered into `projects/<slug>/`; the template is served from the
repository with a render fallback.

## Phase 1 — Design

- [data-model.md](./data-model.md): the pack, the rendered files, the template, the structure document.
- [contracts/starter-api.md](./contracts/starter-api.md): the two routes and the CLI command.
- [quickstart.md](./quickstart.md): the validation scripted for a reviewer.

## Complexity Tracking

No violation to justify.
