# Tasks: Re-importing a project — the same project at a new revision

**Feature**: `055-project-reimport` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Legend: `[P]` parallel-safe, `[US1]`…`[US5]` user story from the spec. Order is execution order; a
task is ticked only when it is implemented and its file exists.

## Phase 1 — the revision the project owns

- [x] T001 `backend/app/config.py`: `project_revisions_keep` (default 20, 1…200)
- [x] T002 `backend/app/models.py`: `PROJECT_REVISION_STATUSES`, `PROJECT_REVISION_SOURCES`,
      `ProjectRevision` (`number`, `status`, `source`, `files`, `summary`, `created_by`, `applied_at`,
      unique `(project_id, number)`), `Project.revision_seq`
- [x] T003 `backend/alembic/versions/0052_project_revisions.py`: the table, the column and the indexes
- [x] T004 `[P]` `backend/tests/test_migrations.py`: `APP_TABLES` gains `project_revision`

## Phase 2 — one module for snapshots, diffs and retention

- [x] T005 `backend/app/projects/revisions.py`: `snapshot`, `diff_maps`, `create`, `ensure_baseline`,
      `current`, `applied`, `previous`, `prune`, `public`, `resolve_files` (content by `(path, sha256)`,
      images from disk when the hash still matches)
- [x] T006 `[P]` `backend/tests/test_project_reimport.py` (unit half): the diff classifies added /
      changed / removed, counts the specs and ids, truncates at 500 and prunes keeping applied/previous

## Phase 3 — the import that becomes a revision (US1, US2)

- [x] T007 `backend/app/projects/reimport.py`: `plan` (the diff, no writes) and `execute` (write the
      zip, delete what left it — files and images — then the revision row), `needs_confirmation`
- [x] T008 `backend/app/projects/zip.py`: match by slug, `mode` in the answer, `dry_run`,
      `replace_draft`, and the copy path renaming artifact ids with their references
- [x] T009 `backend/app/projects/service.py`: `detail` carries the revision chip and calls
      `ensure_baseline`

## Phase 4 — apply, revert and the record (US3)

- [x] T010 `backend/app/projects/apply.py`: mark the draft `aplicada`, the previous `anterior`, the rest
      `reemplazada`; audit both numbers
- [x] T011 `backend/app/projects/revisions.py`: `revert_to` — write that revision back as a new draft and
      apply it, audited
- [x] T012 `backend/app/projects/revisions.py` + `fs.apply_ops` callers: an editor save (and an agent
      write) creates a revision with source `editor`

## Phase 5 — the API

- [x] T013 `backend/app/api/projects.py`: import gains `copy`, `dry_run`, `replace_draft`;
      `GET /{slug}/revisions`, `GET /{slug}/revisions/{number}/zip`,
      `POST /{slug}/revisions/{number}/revert`
- [x] T014 `[P]` `backend/tests/test_project_reimport.py` (HTTP half): import twice, removal of a file
      and an image, shares and grants surviving, copy, revert, retention, dry run, `needs_confirmation`

## Phase 6 — the screens

- [x] T015 `frontend/src/api/types.ts` + `frontend/src/api/projects.ts`: `ProjectImportResult` gains
      `mode`, `revision`, `diff`, `needs_confirmation`; `revisions`, `revisionZipUrl`, `revert`
- [x] T016 `frontend/src/components/projects/RevisionDiff.tsx`: the counts, the lists behind a
      disclosure, and the allowances
- [x] T017 `frontend/src/pages/projects/Projects.tsx`: **Importar como copia**, the dry run, the diff,
      the **Reemplazar borrador / Cancelar** choice and the mode in the result
- [x] T018 `frontend/src/components/projects/RevisionList.tsx` +
      `frontend/src/pages/projects/ProjectWorkspace.tsx`: the chip (`rev 3 · aplicada`), the list with
      download and revert
- [x] T019 `[P]` `frontend/tests/unit/revision-diff.test.tsx` +
      `frontend/tests/unit/revision-list.test.tsx`

## Phase 7 — words, CLI and docs

- [x] T020 `frontend/src/i18n/es.ts` + `en.ts`: every label of the diff, the chip, the list and the
      import choices
- [x] T021 `cli/bizview_cli/importer.py` + `__main__.py` + `i18n/{es,en}.py`: the mode and the diff
      against the workspace folder; `--dry-run` prints the diff only
- [x] T022 `[P]` `cli/tests/test_import_diff.py`
- [x] T023 `backend/app/guide/{es,en}/reimportar-un-proyecto.md` + `index.yaml`: the topic (033)
- [x] T024 `docs/IMPORT.md` §5 and §8; `CHANGELOG.md` under Unreleased

## Phase 8 — the flow end to end

- [x] T025 `frontend/tests/e2e/project-reimport.spec.ts`: import v1 → apply → import v2 → diff → apply →
      new layout → revert → old layout
- [x] T026 Gates: `pytest` (reimport, migrations, guide), `tsc -b`, `vitest run`, `npm run build`,
      the CLI suite
