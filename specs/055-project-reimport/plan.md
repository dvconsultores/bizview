# Implementation Plan: Re-importing a project — the same project at a new revision

**Branch**: `055-project-reimport` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/055-project-reimport/spec.md`

## Summary

An import whose slug already exists stops creating a duplicate: it becomes a **revision** of that
project. A revision is a numbered snapshot of the project folder (`1, 2, 3…`), stored as a map of
`path → sha256` — the contents already live in `project_file_revision` (020), so a revision costs a row
and its diff, not a copy of 45 MB. The import gains three flags (`copy`, `dry_run`, `replace_draft`),
a diff shown before anything is written, and full-replacement semantics over the project's draft.
**Aplicar** marks the draft `aplicada` and the previous applied one `anterior`;
**Volver a la revisión anterior** writes that revision back as a new draft and applies it. Retention
keeps the newest `PROJECT_REVISIONS_KEEP` (default 20), never pruning the applied or previous ones.
The CLI gains the same mode and diff, computed against the workspace folder it is run in.

## Technical Context

**Language/Version**: Python 3.13 (FastAPI + SQLAlchemy 2, Alembic) and TypeScript 5 + React 19 (Vite)

**Primary Dependencies**: existing only — `bizview_cli.layout` (the path whitelist and `ID_RE`),
`bizview_cli.budgets` (the two allowances), `app.projects.fs` / `history` (atomic writes, per-file
revisions), `app.projects.apply` (composition and activate). No new library.

**Storage**: PostgreSQL — one table (`project_revision`) and one column (`project.revision_seq`).
No change to `project_file_revision` (020) and none to `workspace_version` (014/020).

**Testing**: `pytest` (backend, temp schema), `npx vitest run` (jsdom), Playwright (the e2e flow),
`npx tsc -b`, `npm run build`, the CLI suite for the diff.

**Target Platform**: the product's web app and API; the CLI runs where the workspace is.

**Performance Goals**: a diff of two file maps is O(files) in memory with no I/O; a re-import writes
each file once, like the import it replaces; the history list is one query plus one actor query.

**Constraints**: nothing is applied until the author presses **Aplicar** (IX); a project never writes
another project's files (037); the refusals of 043/049 keep their codes and leave nothing behind;
shares, grants, audit rows and loaded datasets are never touched by an import.

**Scale/Scope**: 1 table, 1 column, 1 migration, 5 endpoints (import flags + revisions list/download/
revert), 1 settings key, 1 CLI mode, 1 page section, 1 dialog.

## Constitution Check

| Principle | Gate | How this feature satisfies it |
| --- | --- | --- |
| I. Mobile-First | the import dialog and the revision list are designed at 375 px first | the diff is a countable summary with the lists behind a disclosure; the chip is a badge |
| II. Backend as ETL | untouched | no read of an origin; revisions are metadata |
| III. Source of Truth Is External | untouched | the project folder stays the working copy |
| IV. Separated Concerns | routes in `api`, rules in `projects/`, UI in `frontend/src` | diff, retention and revert live in `app/projects/revisions.py` |
| V. Fixed Technology Stack | no new component, no Git binary | a row and a file map; `zipfile` already ships the download |
| VII. One Product, Many Installations | the retention ceiling is configuration | `PROJECT_REVISIONS_KEEP`, reported with the list |
| IX. Spec-Driven Reporting | a project enters, validates and only then applies | a re-import writes a *draft*; **Aplicar** is still the only path to a version |
| 037 isolation | one project, its own folder | the re-import writes only `projects/<its slug>/`, and the lock is the project's |

No violation; nothing to justify in Complexity Tracking. No amendment: 037 and IX hold unchanged, and
the revision is a product concept, not a stack one.

## Project Structure

### Documentation (this feature)

```text
specs/055-project-reimport/
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0: what exists, why the snapshot is a map of hashes, the diff shape
├── quickstart.md      # Phase 1: the gates and the manual checks
└── tasks.md           # Phase 2
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0052_project_revisions.py  # project_revision + project.revision_seq
├── app/config.py                               # project_revisions_keep (default 20)
├── app/models.py                               # ProjectRevision, PROJECT_REVISION_* vocabularies
├── app/projects/revisions.py                   # NEW: snapshot, diff, create, prune, resolve content
├── app/projects/reimport.py                    # NEW: plan (dry run) and execute (full replacement)
├── app/projects/zip.py                         # match by slug; copy path renames ids; mode in the answer
├── app/projects/apply.py                       # mark draft applied / previous applied
├── app/projects/service.py                     # detail carries the revision chip; baseline on read
├── app/api/projects.py                         # import flags, /revisions, /revisions/{n}/zip, /revert
└── tests/test_project_reimport.py              # NEW: the flows of the spec
cli/
├── bizview_cli/importer.py                     # diff against the workspace folder; mode
├── bizview_cli/__main__.py                     # `import` prints mode + diff; --dry-run the diff only
└── bizview_cli/i18n/{es,en}.py                 # the new lines
frontend/
├── src/api/types.ts, src/api/projects.ts       # revision and diff types, the calls
├── src/components/projects/RevisionDiff.tsx    # NEW: the diff the author confirms
├── src/components/projects/RevisionList.tsx    # NEW: the history with download and revert
├── src/pages/projects/Projects.tsx             # copy checkbox, dry run, confirm, replace draft
├── src/pages/projects/ProjectWorkspace.tsx     # the revision chip and the list
└── src/i18n/{es,en}.ts                         # labels
```

**Structure Decision**: the revision concept is one module (`app/projects/revisions.py`) because three
callers need it — the importer, the apply and the revert — and a rule that lives in two of them is a
rule that will disagree with itself. The importer keeps its archive parsing and budget tally (043/049)
and delegates the matching, planning and writing.

## Phase 0 — Research (see [research.md](./research.md))

What the current import does with a taken slug, what a snapshot can reference instead of copying,
how the apply marks what it applied, how the editor records a save, and where the CLI can read a
project folder.

## Phase 1 — Design

- `project_revision`: `id`, `project_id`, `number` (unique per project), `status` in
  (`borrador`,`aplicada`,`anterior`,`reemplazada`), `source` in (`import`,`editor`), `files jsonb`
  (`{path: sha256}`), `summary jsonb` (`{files:{added,changed,removed,truncated}, specs:{…},
  ids:{…}, counts:{…}}`), `created_by`, `created_at`, `applied_at`; index `(project_id, number DESC)`.
- `project.revision_seq` mirrors the highest number so a concurrent import cannot reuse one.
- Diff shape: `{added[], changed[], removed[], specs:{added[],removed[]}, ids:{added[],removed[]},
  counts:{added,changed,removed,specs_added,specs_removed,ids_added,ids_removed}, truncated}`.
- Import response: `{project, mode, revision, diff, ignored, validation, budgets, themes}`; `revision`
  is `null` on a dry run; `needs_confirmation` when `replace_draft` was not sent and the draft carries
  editor revisions after the last import.
- API: `GET /api/projects/{slug}/revisions`,
  `GET /api/projects/{slug}/revisions/{number}/zip`,
  `POST /api/projects/{slug}/revisions/{number}/revert` (step-up, audited).
- Write order for a re-import: `fs.apply_ops(write…, delete…)` then `fs.apply_asset(…)` for the
  images, all under the project's advisory lock, then the revision row — so a failure leaves neither a
  half-written folder nor a revision claiming files that are not there.

## Phases

| Phase | Work |
| --- | --- |
| 1 | Model, migration, settings key, baseline on read |
| 2 | `revisions.py`: snapshot, diff, create, prune, content resolution |
| 3 | `reimport.py` + the import entry: matching by slug, dry run, replacement, copy renames |
| 4 | Apply marks the revision; revert writes and applies; audit |
| 5 | API endpoints and the detail payload |
| 6 | Frontend: diff, copy flag, replace-draft choice, chip, revision list |
| 7 | CLI mode and diff; i18n; help topic; `docs/IMPORT.md`; CHANGELOG |
| 8 | Tests: backend flows, unit components, e2e |

## Verification

- `cd backend && .venv/bin/python -m pytest tests/test_project_reimport.py -q`
- `cd backend && .venv/bin/python -m pytest tests/test_projects_api.py tests/test_migrations.py tests/test_guide.py -q`
- `cd frontend && npx tsc -b && npx vitest run && npm run build`
- `cd frontend && npx playwright test tests/e2e/project-reimport.spec.ts --project=chromium-375`
- `cd cli && uv run pytest tests/ -q`
