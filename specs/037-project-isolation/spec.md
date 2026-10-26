# Feature Specification: Project isolation — one project never shows, fixes or previews another's data

**Feature Branch**: `037-project-isolation`

**Created**: 2026-10-26

**Status**: Draft

**Input**: Owner, 2026-10-26, from production (`/proyectos/artemisa`): the page header says
**artemisa**, the file tree is artemisa's, and yet

- the problems panel shows `projects/coinmarketcap/reports/panorama-cripto/report.yaml#/uses ·
  Conjuntos sin unión: altseason` with an **Aplicar arreglo** button (a *coinmarketcap* problem);
- pressing that button answers `No se pudo aplicar: El archivo
  projects/coinmarketcap/reports/panorama-cripto/report.yaml ya no existe.`;
- the chat lists the same problem (it is the same validation payload);
- four consecutive `La vista previa falló: La vista previa no ve ningún archivo del proyecto…`.

Both projects were used from the same super-user account within a few hours.

**Builds on**: 020 (projects, composed validation, per-project draft), 014 (previews, worker),
021/028 (commands, auto runs), 035 (validation problems and their deterministic fixes), 022 (i18n).

## Verified root causes

Each of these was reproduced in the code; the ones that do **not** apply are listed too, because the
point of the feature is that the answer is evidence, not a guess.

### R1. The project's validation publishes the whole composition's problems (applies)

`compose.validate_project` validates the *composed* workspace tree (this project + the applied
snapshot of the others) and then keeps **every** issue: the ones under `projects/<this slug>/` are
rewritten to project-relative paths, the ones under `projects/<other slug>/` are stored verbatim
with `project: <other>`. That object is `project.validation`, so it reaches the page, the problems
panel, the chat (`session_json`) and `apply_fix`.

Consequences: the panel and the chat list coinmarketcap's problem on artemisa's page; the session of
artemisa is told to fix a file it cannot write; `valid` is false for a project whose own files are
fine.

### R2. The panel offers the fix of a foreign problem (applies)

`ProblemsPanel` renders `fix_data` of **any** issue in the payload. For another project's issue the
path is still `projects/coinmarketcap/…`, which is not a path of artemisa, so
`POST /api/projects/artemisa/fix` answers `409 fix_gone` — literally «El archivo … ya no existe»,
the sentence of the report. The write never happened (the layout whitelist rejected the path), but
the interface claimed the file was gone and the user was told nothing about scope.

### R3. The file layer accepts `projects/<other>/…` as a *nested* folder (applies, latent)

`fs.check_rel` accepts any relative path; only `layout.is_allowed` (an exact whitelist of the
project's own files) rejects `projects/…`. Every read that does not pass through the whitelist — a
revision restore, an export, a `list_files` walk — would resolve `PROJECTS_DIR/<this slug>/projects/
<other slug>/…`, and today the only reason it cannot is that the folder does not exist.

### R4. The project page opens a conversation of another project by deep link (applies)

`ProjectWorkspace` reads `?chat=<id>` and asks for that session directly. Nothing checks that the
session belongs to the page's project, so the docked chat (and its preview, its problems and its
Aplicar) can be another project's conversation while the header says artemisa.

### R5. The project-level preview picks the newest conversation, whoever owns it (applies)

`_conversation()` in `api/projects.py` takes the project's latest `assistant_session` filtered only
by project, so `/api/projects/<slug>/preview` writes its request, its outcome message and its
`preview` state into another user's conversation.

### R6. A preview request does not carry its project, and an empty folder is nameless (applies)

`assistant_preview_request` has `session_id` only. The worker resolves the folder through the
session's project and, when it is missing or empty, fails with a message that names neither the
project nor the mounted path — so the reader cannot tell a missing volume from a wrong scope
(reported 2026-10-22, and again in this incident).

### R7. `read_draft` treats a foreign path as "missing" (applies)

`read_draft` looks the path up in `session.files()` and reports `missing`; a `projects/<x>/…` or an
absolute path is neither rejected nor explained, so the model believes the file simply is not there.

### Checked and not a defect

- `assistant_session`, `project_file_revision`, `assistant_command_run`, `assistant_auto_run` already
  carry `project_id` (NOT NULL, FK, indexed); drafts, validation and preview live on the project
  row (`WorkView`), not on the conversation. There is no workspace-level draft store to leak.
- `assistant_run_profile` stores a run contract (stages, limits, **source names** — installation
  level, no project paths) as a form prefill; it is not project data. Out of scope, documented.
- `validate_project` must keep composing the whole workspace: an id collision or a cross-project
  reference is real and the apply must still refuse it. What changes is *where the finding is
  published*, not that it is found.

## User scenarios

**US1 — a page never shows another project's problems.** Open A after validating B: the problems
panel, the chat's validation block and the status bar show A's problems only. (P1)

**US2 — a fix is applied to the page's project or refused.** «Aplicar arreglo» on A writes a file of
A. A path outside A is refused with «ruta fuera del proyecto», never with «ya no existe». (P1)

**US3 — the chat of a page is that page's chat.** `?chat=` with a conversation of another project
does not open it; the page opens its own conversation. (P1)

**US4 — a preview says which project and which folder it read.** The worker resolves the folder from
the request's project, names it and the mounted path when it is empty or missing, and logs the root
it used. (P2)

**US5 — the workspace still guards the composition.** Applying A when the composition is invalid
because of B is refused by the apply with the owners named, and the A page explains that the other
project blocks it, without offering a fix it cannot write. (P2)

## Functional requirements

- **FR-001** A validation result published on a project lists only issues about **that project's**
  files, with project-relative paths (`reports/<id>/report.yaml`), each with its `fix_data` and
  `problem_id`. Issues about other projects are summarised (`other_projects: {slug: count}`) and
  their counts are exposed, never as fixable entries. Workspace-level issues (`bizview.yaml`) are
  reported separately (`workspace_errors`), never as a project problem.
- **FR-002** `valid` means "this project's files are valid". `composed_valid` means "the whole
  composition is valid". Readiness requires `composed_valid`; the panel and the chat use `errors`,
  `warnings` and `valid`.
- **FR-003** There is exactly one way from a project to disk:
  `fs.resolve_project_path(project_id, relative)` (plus the slug-based primitives it delegates to).
  It resolves `project_id → PROJECTS_DIR/<slug>`, rejects absolute paths, `..`, symlinks leaving the
  root, and any path whose first segment is `projects` (the composition prefix), with the code
  `path_outside_project`.
- **FR-004** `fs.check_rel` (the choke point of every read, write, list and delete) refuses a leading
  `projects` segment, so no code path — present or future — can address another project's folder as
  a nested folder.
- **FR-005** The fix endpoint resolves the file through `resolve_project_path`; a cross-project or
  absolute path is `422 path_outside_project`; a valid path whose file is gone stays `409 fix_gone`.
- **FR-006** `ProblemsPanel` renders only issues of its `slug`; a `fix_data` whose `file` is not a
  project-relative path of that project is never offered.
- **FR-007** `/api/projects/<slug>/preview` uses the caller's newest conversation of that project,
  creating one when the caller has none.
- **FR-008** A project page never opens a conversation of another project: `?chat=<id>` is honoured
  only when the id is one of the page's conversations.
- **FR-009** `assistant_preview_request` carries `project_id` (FK, indexed, NOT NULL after the
  backfill). The worker checks it against the session, resolves the folder from it, logs the
  resolved root, and fails with a message that names the project slug and the absolute folder when
  that folder is missing or has no project files.
- **FR-010** The assistant's tools accept only project-relative paths: `read_draft` rejects
  `projects/…` and absolute paths with «ruta fuera del proyecto» instead of reporting them missing;
  `apply_fix(problem_id)` only matches problems of the session's project.
- **FR-011** Rows that cannot be attributed to a project are quarantined so that no query can see
  them, and the migration logs the counts per table. In this tree the only project-scoped table that
  could not answer "which project?" was `assistant_preview_request` (it carried the conversation
  only): `0030_project_scope` backfills it from the session and removes the queue rows whose
  conversation is gone — they are work orders, not data, and they cannot run. No speculative
  `orphan_scope` column is added: the session and project foreign keys make an orphan impossible
  afterwards, and a dead flag would age into a lie.
- **FR-012** Every repository function that lists or acts on project-scoped rows takes the project
  (or its id) as a required argument; a test fails when a query on a project-scoped model is written
  without a `project_id`/`session_id` filter outside the documented installation-wide call sites.

## Success criteria

- **SC-001** Two projects A and B, one user: validating B with a known problem and then opening A
  shows an empty problems panel for A, A's preview reads A's files, A's apply succeeds; and the
  reverse. No payload served to A's pages contains a `projects/B/` path.
- **SC-002** «Aplicar arreglo» on a foreign path answers `path_outside_project`, and no revision is
  written (audit shows no `project_fix_applied`).
- **SC-003** A preview request whose folder is empty fails with slug + path in the message; with the
  right `project_id` and folder it succeeds.
- **SC-004** `resolve_project_path` rejects `../x`, `/abs/x`, `projects/b/x` and a symlink out of the
  root for both projects.
- **SC-005** The existing suites keep passing: nothing that worked before (composed validation,
  apply, fixes, preview, chat) changes behaviour for a single-project installation.
