# Tasks: Project isolation (037)

Depends on nothing new. Ordered so each step is verifiable on its own.

## Paths (US2, FR-003/FR-004)

- [x] T001 `fs.check_rel` refuses a leading `projects` segment with `path_outside_project`; absolute
      paths, `..` and symlinks keep their current codes.
- [x] T002 `fs.resolve_project_path(project_id, relative, db=None)` + `fs.project_folder(project_id)`:
      id → slug → `PROJECTS_DIR/<slug>`, raising `project_not_found` when the row is gone.
- [x] T003 Route the fix endpoint, the apply, the export, the preview and the tools through it.

## Validation published per project (US1, FR-001/FR-002)

- [x] T004 `compose.validate_project` splits own issues (`errors`/`warnings`, relative paths) from
      `other_projects` and `workspace_errors`; adds `composed_valid`.
- [x] T005 `readiness.compute` requires `composed_valid` and lists the blocking projects.
- [x] T006 i18n strings (es/en) for the new messages; the assistant's validation block reads the
      project-scoped payload unchanged.

## Fixes and tools (US2, FR-005/FR-010)

- [x] T007 `fixes.apply_fixes` resolves through `resolve_project_path`; cross-project paths are
      `422 path_outside_project`, missing files stay `409 fix_gone`; the fix must name a file of the
      project.
- [x] T008 `read_draft` rejects foreign paths; `_check_path` says «ruta fuera del proyecto»;
      `apply_fix` only matches the session's project.

## Preview and worker (US4, FR-009)

- [x] T009 Migration `0030_project_scope`: `assistant_preview_request.project_id` (backfill, NOT
      NULL, FK, index) and `orphan_scope`, counting what it quarantines.
- [x] T010 `request_preview` stores the project; `process_request` checks it, resolves the folder,
      logs the root and fails with slug + path when the folder is empty or missing.

## Page and panel (US1/US3, FR-006/FR-007/FR-008)

- [x] T011 `ProblemsPanel` renders only issues of its slug and never offers a foreign fix; the
      header shows the project the data belongs to.
- [x] T012 `_conversation()` uses the caller's own conversation; `?chat=` is validated against the
      page's conversations.
- [x] T013 Frontend types and i18n (`otherProject` removed, `blockedBy` added).

## Verification

- [x] T014 `test_project_scope.py`: `resolve_project_path` escapes, two-project validation split,
      fix refusal, preview folder error, and the two-project end-to-end regression (SC-001).
- [x] T015 `test_project_scope_guard.py`: no query on a project-scoped model without a project or
      session filter outside the allowlist.
- [x] T016 vitest: the panel ignores the other project's issue and does not render its fix.
- [x] T017 `docs/guides/proyectos/aislamiento.md` + CHANGELOG under Unreleased.
