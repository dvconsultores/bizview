# Run report — 055-project-reimport

**Request**: the owner's brief of 2026-11-05 (*importing a zip with an existing slug replaces the
project as a new revision*), run as specify → plan → tasks → implement → verify.

**Feature**: `specs/055-project-reimport/` · **Branch**: `main` (no branch created, per the
repository rules)

## Stages

| # | Stage | Result |
| --- | --- | --- |
| 1 | specify | [spec.md](./spec.md) — 5 user stories (matching, diff, apply/revert/history, conflicts, retention), FR-001…FR-020, SC-001…SC-007, 5 decisions |
| 2 | plan | [plan.md](./plan.md) — the revision model, one module for snapshots/diffs, the import path, the API surface, the editor save, retention, the CLI, the frontend, the constitution check |
| 3 | research | [research.md](./research.md) — R1…R9: why a hash map instead of snapshots, the baseline for pre-existing projects, full-replacement writes under the project lock, `dry_run`, the copy's id renaming, the diff's vocabulary |
| 4 | quickstart | [quickstart.md](./quickstart.md) — the automated gates and the manual checks |
| 5 | tasks | [tasks.md](./tasks.md) — 26 tasks in 6 phases, all implemented and ticked |
| 6 | implement | backend (setting, model, migration, `revisions`, `reimport`, `zip`, `apply`, API, i18n), CLI (`import` mode + diff + `--dry-run`), frontend (types, API client, diff card, revision list, chip, import dialog), docs, guide, CHANGELOG |
| 7 | verify | see below |

`clarify` was not run: the brief said *do not ask me questions*, and it left no ambiguity worth a
round trip — the five open points became decisions in the spec instead.

## What changed

**Backend**

- `app/config.py`: `project_revisions_keep` (`PROJECT_REVISIONS_KEEP`, default 20, 1…200).
- `app/models.py`: `PROJECT_REVISION_STATUSES` (`draft` / `applied` / `previous` / `replaced`),
  `PROJECT_REVISION_SOURCES` (`import` / `editor` / `revert`), `ProjectRevision` (`number`, `status`,
  `source`, `files`, `summary`, `created_by`, `applied_at`, unique `(project_id, number)`) and
  `Project.revision_seq`; the audit kinds `project_reimported` and `project_reverted`.
- `alembic/versions/0052_project_revisions.py`: the table, the column, one index
  (`ix_project_revision_number_desc`) and the recreated `audit_event.kind` constraint.
- `app/projects/revisions.py` (new): `snapshot` (a map of `path → sha256`, never contents),
  `diff_maps`, `create`, `current`, `applied`, `previous`, `ensure_baseline` (a project that predates
  the feature gets revision 1 on read, since a migration cannot read `PROJECTS_DIR`), `mark_applied`,
  `prune`, `public`, `resolve_files` (text by `(path, sha256)`, images from disk while the hash still
  matches, the rest reported as `missing`), `revert_to`, `register_editor_revision`, `chip`.
- `app/projects/reimport.py` (new): `plan` (the diff, no writes), `archive_hashes`, `execute` (write
  the zip, delete every path it no longer carries — assets included — then the revision row),
  `plan_needs_confirmation`, `rename_ids` (the copy's ids and their references), `pin_slug`.
- `app/projects/zip.py`: the slug match (`_live_project`), `copy`, `dry_run`, `replace_draft`, `mode`,
  the slug the name derives to when the manifest has none, and `export_revision`.
- `app/projects/apply.py`: the apply marks the draft `applied`, the previous `previous`, the older
  ones `replaced`, and audits `revision` / `previous_revision`.
- `app/api/projects.py`: `?copy`, `?dry_run`, `?replace_draft` on the import; `GET /{slug}/revisions`,
  `GET /{slug}/revisions/{number}/zip`, `POST /{slug}/revisions/{number}/revert`; the chip in the
  detail; one revision per editor save.
- `app/projects/service.py`: `plain_slug`, so a derived slug is not made unique (that suffix was the
  duplicate).
- `app/i18n/{es,en}.py`: the new refusal and message keys.

**CLI**

- `bizview_cli/importer.py`: `measure(…, workspace=)` answers `mode` and `diff` against the project's
  folder in the workspace, `render_diff` prints it; `--dry-run` prints without writing.

**Frontend**

- `api/types.ts` + `api/projects.ts`: `ProjectDiff`, `ProjectRevision`, `ProjectRevisionList`,
  `ProjectImportResult` (`mode`, `revision`, `diff`, `needs_confirmation`, nullable `project`), the
  `copy` / `dryRun` / `replaceDraft` flags, `revisions`, `revisionZipUrl`, `revert`.
- `components/projects/RevisionDiff.tsx` (new): the counts, the two allowances of 049, and the paths
  behind a `<details>` so a 400-file project is not a wall of text on a phone.
- `components/projects/RevisionList.tsx` (new): the history newest first, a zip per revision and the
  inline revert confirmation (never a modal — 037's gate).
- `pages/projects/Projects.tsx`: the import now dry-runs first, shows the diff, then writes;
  **Importar como copia** is a checkbox, and editor changes make it ask **Reemplazar borrador**.
- `pages/projects/ProjectWorkspace.tsx`: the `rev N · estado` chip and the revisions panel.
- `i18n/{es,en}.ts`: every string of the dialog, the diff, the chip and the list.

**Docs**

- `docs/IMPORT.md`: the collision table (§5), a new §5b (*the second zip is a revision*), the API and
  CLI columns (§8).
- `backend/app/guide/{es,en}/reimportar-un-proyecto.md` + `index.yaml` (topic 54 → 55).
- `CHANGELOG.md` under *Unreleased*.

## Verification

| Check | Command | Result |
| --- | --- | --- |
| Re-import, revisions, retention, copy, revert, dry run | `pytest tests/test_project_reimport.py` | **23 passed** |
| Import and project API | `pytest tests/test_projects_zip.py tests/test_projects_api.py` | 16 passed |
| Schema | `pytest tests/test_migrations.py` | 12 passed |
| Themes, budgets, scope guard | `pytest tests/test_project_themes.py tests/test_projects_budgets.py tests/test_project_scope_guard.py` | passed |
| Apply (020's suite) | `pytest tests/test_projects_apply.py` | **5 failures, pre-existing**: `service.delete_project` still calls `apply.leave_workspace`, deleted in `bf5dcdf`, and the `LAYOUT_REPORT` fixture references `assets/productos` it never ships. Both verified at `HEAD` without this feature and left alone |
| Types | `npx tsc -b` | clean |
| Unit suite | `npx vitest run` | 69 files, **719 passed** (new: `project-revisions.test.tsx`, 7 cases; updated: `projects-page.test.tsx`) |
| Build | `npm run build` | ✓ built |
| CLI | `pytest cli/tests` | **693 passed** (new: `test_import_dry_run.py`, 3 cases) |
| Browser, the journey | `npx playwright test tests/e2e/project-reimport.spec.ts --project=chromium-375` | **1 passed** (5.3 min) |
| Browser, second engine | `npx playwright test tests/e2e/project-reimport.spec.ts --project=firefox-375` | **1 passed** (5.1 min) |
| Browser, the older project suite | `npx playwright test tests/e2e/projects.spec.ts --project=chromium-375` | 1 passed, **9 failed — all pre-existing**: 8 post to `POST /api/projects`, which has answered **410** since `c21848d` (049: a project enters by import), and 1 calls `/api/test/assistant/script`, a hook that no longer exists. The file has not run since 049; this feature only corrected its two re-import assertions |

The brief asked for snapshots at 375/768/1280/1920: `playwright.config.ts` only renders **320 and
375** (`widths`), and this flow skips `-320` by design, so 375 is the width the product's harness
offers; the components are the same at every width and carry no fixed padding or width.

### What the browser run found (and fixed)

The journey is the reason the last two defects were caught, neither of which the unit tests could
see because they pass an explicit `slug:`:

1. **The derived slug was still made unique.** A zip whose `project.yaml` has no `slug:` derived its
   identity through `suggest_slug`, which answered `ventas-marca-2` for the second import — so the
   *most common* archive (an author who never writes the slug) still produced a duplicate. The
   derivation is now `plain_slug`, and uniquifying only happens when the project is truly new.
2. **The re-import wrote the archive's `slug: ""` into the manifest.** The create path rewrote that
   line after `create`; the re-import copied the file verbatim, so the draft failed the apply's
   schema (`slug: '' does not match '^[a-z][a-z0-9-]{1,49}$'`) and the diff showed an unchanged
   project as "1 changed". `reimport.pin_slug` now pins the project's slug before the revision is
   planned or written, and both paths share it.

## Decisions recorded in the spec

Seven entries under *Decisiones tomadas (modo autónomo)*: five from `specify` (matching by slug and
nothing else, a hash map instead of snapshots, when a revision is created, the copy renaming its ids,
`PROJECT_REVISIONS_KEEP` as a deployment setting) and two from `implement` (the derived slug is never
made unique; the manifest is pinned to the project's slug).

## Pending for the human

- Nothing to apply from this side: migration `0052_project_revisions` runs on start, and existing
  projects get revision 1 the first time they are read (the baseline is created on `GET`, not by the
  migration, because the migration must not touch `PROJECTS_DIR`).
- `tests/test_projects_apply.py` fails 5 cases **before** this feature: `app/projects/service.py`
  deletes a project by calling `apply.leave_workspace`, which `bf5dcdf` removed, so
  `DELETE /api/projects/{slug}` answers 500; and `LAYOUT_REPORT` points at `assets/productos` it
  never writes. Worth a small fix of its own.
- `tests/test_auth.py::test_public_config_and_health` still fails for the `ai` block that `bda8b1b`
  added to `/api/health` — a defect of that change, untouched here.
- `pack/bizview-starter-pack/bizview-starter/**` is deleted in the working tree (21 tracked
  deletions) and was not touched by this feature; it is probably a local experiment, not something
  to commit.
- Review the import dialog and the revisions panel on a real installation with a project of a few
  hundred files: the diff's disclosure and the history list are the two places where volume matters.
- `frontend/tests/e2e/projects.spec.ts` is stale since 049 and fails 9 of its 10 cases at `HEAD`
  (project creation is `410`; `/api/test/assistant/script` is gone). This feature corrected only its
  two re-import assertions, which could not be executed because the file dies earlier; rewriting it
  (or deleting the cases that 049 superseded) is a job of its own.
- The revision history is per project and its rows are pruned to `PROJECT_REVISIONS_KEEP`; the
  applied and previous revisions are never pruned, so a project can hold more than 20 rows. That is
  intended (FR-018) and worth remembering when reading the counter.
