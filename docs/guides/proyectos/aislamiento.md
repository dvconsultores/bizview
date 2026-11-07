🇬🇧 English · 🇪🇸 [Español](../../es/guides/proyectos/aislamiento.md)

# Isolation per project

This document explains how BizView guarantees that one project never shows, fixes or previews
another project's files. It came from a real incident (2026-10-26): the `artemisa` page showed a
problem from `coinmarketcap`, its **Apply fix** button answered "The file
projects/coinmarketcap/… no longer exists" and the preview said it saw no file of the project.

## The rule

**A project is a separate configuration: its page, its validation, its fixes and its preview talk
only about the files in its folder.** Nobody reads or writes another project's files.

Validation *composes* the workspace (this project + the applied copy of the others) because a
duplicated id or a reference to another integration are real problems. What changes is **where the
finding is published**: each project publishes only its own.

## Where each thing lives

| Data | Where | Scope |
|---|---|---|
| Project files | `PROJECTS_DIR/<slug>/…` | the folder, resolved from `project_id` |
| Draft | the folder (read) | the project |
| Validation and "problems" | `project.validation` | the project |
| Preview | `project.preview` | the project |
| Conversations | `assistant_session.project_id` | the project (and its author) |
| File history | `project_file_revision.project_id` | the project |
| Run contracts | `assistant_auto_run.project_id` | the project |
| Preview requests | `assistant_preview_request.project_id` | the project |
| Run profiles | `assistant_run_profile` | the installation (a form: stages, limits and source names; they are not a project's files) |

## Paths

- Files are named **relative to the project's folder**: `reports/panorama-cripto/report.yaml`.
- `projects/<slug>/…` is the prefix of the *composition* (what the validator sees). It is never a
  project path: it is refused with `path_outside_project` ("path outside the project").
- Absolute paths, `..` and symlinks that leave the folder are refused too.
- The only way from a project to disk is `fs.resolve_project_path(project_id, relative)`: it
  resolves the folder from the project row (`project_id → PROJECTS_DIR/<slug>`) and applies the
  rules above.

## What the reader sees

- **Problems panel**: only this project's problems, with their relative file and their **Apply fix**
  button. If the workspace has problems in other projects, a note appears with their names — and no
  button, because they are not fixed from here.
- **Status**: `Valid` means "the files of this project are valid". Applying also requires the whole
  composition to be valid (`composed_valid`): if another project breaks it, "Ready to apply" stays
  pending and names that project.
- **Chat**: the panel shows the conversation's project; a conversation from another project is not
  opened from this page (the `?chat=` link is checked).
- **Preview**: the request carries its `project_id`; the worker resolves the folder from it and, if
  it is empty or does not exist, fails naming the slug and the mounted path, to tell a missing
  volume from a scoping error. The log records the resolved folder when validation, the preview and
  apply start.

## What to do when "path outside the project" appears

1. Re-check the project's problems (the panel is recomputed on the current folder).
2. If the problem persists, look at which project it belongs to: the panel's note says so.
3. Another project's problem is fixed on **its** page.

## Implementation notes

- `compose.validate_project` publishes `errors`/`warnings` (its own), `other_projects`
  (`{slug: {errors, warnings}}`), `workspace_errors`/`workspace_warnings` and `composed_valid`.
- `POST /api/projects/{slug}/fix` resolves each file with `resolve_project_path`; another project's
  path is `422 path_outside_project` and a valid file that is gone is still `409 fix_gone`. A
  `problem_id` must name the same file as the fix.
- `PUT /api/projects/{slug}/apply` composes from the project's folder and refuses when that folder
  does not exist (a version without its files would be data loss).
- `backend/tests/test_project_scope.py` and `test_project_scope_guard.py` are the regression: two
  projects, one user, and no query over a table with `project_id` without filtering by project.
