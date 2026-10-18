# Implementation Plan: BI projects — a workspace per chat with numbered specs

**Branch**: `020-bi-projects` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md) |
**Research**: [research.md](./research.md)

## Summary

Every conversation now lives in a **project**: a folder `PROJECTS_DIR/<slug>/` with the Spec Kit
layout (project.yaml, constitution, numbered `specs/NNN-*`, `integrations/`, `reports/`,
`distributions/`). The folder is the working copy that replaces 014's per-conversation draft; every
change is a database revision (history, diff, restore). The project page is a cloud editor
(explorer, tabs, CodeMirror, rendered Markdown, problems, status bar, chat; tabs on phones).
"Aplicar proyecto" validates the composition *active version with this project's subtree replaced*
and applies it as a new workspace version that records the owning project of every artifact and
spec; distributions create the email subscriptions owned by the project. The upgrade imports the
active version into project `principal`; the CLI and the Git apply accept the v2 layout
(`projects/<slug>/…`) and the legacy flat layout.

## Technical Context

Python 3.12 / FastAPI / SQLAlchemy / Alembic (migration `0018_projects`, after 019 `0015`, 005-A
`0016`, 022 `0017_user_locale`); stdlib `os`, `hashlib`, `difflib`, `zipfile` (no new backend
dependency; zip import reads a raw `application/zip` body, so no `python-multipart`). jsonschema +
sqlglot + PyYAML in `cli/bizview_cli` (CLI 0.4.0: v2 layout, lock v2, `project`/`distribution`
schemas, `bizview project new`). React 19 / Tailwind; new supporting libraries CodeMirror 6,
react-markdown + remark-gfm, react-resizable-panels (R11). i18n from 022: every new UI string in
`frontend/src/i18n/es.ts` **and** `en.ts` (`useT()`), every backend message through
`backend/app/i18n/{es,en}.py`. Tests: backend pytest on `DATABASE_URL_BI` in `app_test_*` schemas
with `PROJECTS_DIR` = a pytest `tmp_path`; fake AI provider only; code first, focused checks per
task, full suites once at the end of the queue.

## Constitution Check

- **I (mobile first)**: the project page is designed at 375 px first: three panes become tabs
  "Archivos / Editor / Chat" (`PaneTabs`, `role="tablist"`); opening a file or a problem switches to
  the Editor tab; toolbar actions are 44 px targets (`min-h-tap`); from 1024 px the panes are
  resizable. Unsaved-changes, delete and overwrite choices are inline bars, never modals. Dark mode
  through the existing tokens (CodeMirror theme uses CSS variables; `no-raw-colors` test). SC-004
  axe check at 375 px.
- **IV (separated concerns by folder)**: customer projects live only in the installation's
  `projects/` (dev default `./projects`, git-ignored); the repository keeps generic templates
  (`cli/bizview_cli/workspace_template/`), the shared layout (`cli/bizview_cli/layout.py`) and the
  schemas (`cli/bizview_cli/schemas/`), imported by the backend (single source). Backend code in
  `backend/app/projects/`, UI in `frontend/src/pages/projects/` and `frontend/src/components/ide/`.
- **V (fixed stack)**: no stack component added; the editor libraries are supporting libraries
  (listed with reasons in R11 and below). No Git binary (history in PostgreSQL).
- **VII (one product)**: templates and golden examples use generic names (`facturas`,
  `origen_ventas`, project `ejemplo`); a customer's projects never enter the repo; differences are
  folders and settings (`PROJECTS_DIR`, `PROJECT_MAX_MB`).
- **VIII (AI optional and private)**: projects, editor, history, apply, zip and CLI work with AI
  off (the chat pane shows "IA no configurada"); naming a project from the first message is
  deterministic (no provider call, R16). Project files reach the provider only through the existing
  017 tools (sanitised); credentials never live in project files (`fuente` specs name the
  catalogue source); distributions name recipients by **role only**, never people (R8; spec change
  recorded below).
- **IX (spec-driven, projects with numbered specs)**: every artifact still needs an approved,
  complete spec ("no spec, no run" unchanged); specs are per-project, sequential, never reused,
  with a mandatory kind line; the version records the owning project of every artifact and spec.
  The agent keeps changing files only through its tools (021 restricts them to commands).
- **Security**: path allow-list + symlink-free resolution + `O_NOFOLLOW` atomic writes (R2); size
  caps per file and per project; zip import with entry/size/ratio/symlink guards (R13); apply,
  withdraw, delete, convert and import need step-up (`recent_reauth`) and are audited; super user
  only (`require_superuser`), CSRF as every mutating route.
→ PASS (no amendment; no Complexity Tracking entry).

## Design

### 1. On-disk layout and safe paths (`cli/bizview_cli/layout.py`, `backend/app/projects/fs.py`)

- Layout (FR-002), project-relative, regex allow-list in `layout.PROJECT_PATTERNS`:
  `project.yaml`; `.specify/memory/constitution.md`;
  `specs/NNN-<short>/(spec|plan|tasks|research|data-model|quickstart).md`;
  `specs/NNN-<short>/checklists/<name>.md`; `integrations/<id>/integration.yaml`;
  `integrations/<id>/queries/<name>.sql`; `integrations/<id>/requests/<name>.yaml`;
  `reports/<id>/report.yaml`; `distributions/<id>.yaml`. Segments: id `^[a-z][a-z0-9-]{1,49}$`,
  file names `^[a-z0-9][a-z0-9._-]{0,63}$`, spec folder `^[0-9]{3}-[a-z0-9][a-z0-9-]{0,59}$`.
  `layout.allowed_folders(path)` says whether a folder path is a prefix of an allowed pattern (empty
  folders may be created). `layout.ALLOWED_TEXT` = human list used in errors and the authoring pack.
- Workspace v2 (Git and composition): root `bizview.yaml` (+ `bizview.lock`) and
  `projects/<slug>/<layout>`; legacy = root `bizview.yaml` + `integrations/`, `reports/`,
  `specs/(integrations|reports)/…` (project `principal`). A tree with both is an error
  (`mixed_layout`). Files outside the layout in a checkout or zip are ignored and listed.
- `fs.py`: `projects_dir()`, `project_root(slug)`, `resolve(slug, rel) -> Path` (R2 steps),
  `read_text(slug, rel)`, `list_files(slug) -> dict[path, (size, sha256)]` (walk with `os.scandir`,
  no symlinks followed, ignored paths returned separately), `write_atomic(path, text)`,
  `remove(path)` (+ prune empty parents up to the root), `move_folder(src, dst)`.
  Limits: UTF-8 text, no NUL, ≤ 512 KB per file (014), ≤ `PROJECT_MAX_MB` per project (sum of
  sizes after the write), ≤ 400 files. Errors raise `ProjectPathError(code, message)` with codes
  `path_not_allowed` (message lists `layout.ALLOWED_TEXT`), `path_unsafe`, `too_large`,
  `project_too_large`, `not_text`, `not_writable` (disk full / permissions: "No se pudo escribir
  en la carpeta del proyecto").
- `fs.apply_ops(project_id, ops, actor) -> list[Revision]` (R5, R6): ops
  `write{path, content, base_sha256|None, force?}`, `delete{path, base_sha256}`,
  `rename{from, to, base_sha256}`, `mkdir{path}`, `rmdir{path}` (deletes files below, one revision
  each). Own DB session, `pg_advisory_xact_lock(lock_key("project", id))`, external-change sync
  first (§3), base checks (`file_changed` with the current revision), new spec folder number check
  (§5), file writes, revisions, commit; restore previous bytes on failure after a replace. One
  `group_id` (uuid) per call.

### 2. Project model and migration `0018_projects`

- `project`: `id` bigint identity; `slug` text (check `^[a-z][a-z0-9-]{1,49}$`, unique among
  `deleted_at IS NULL`); `name` text 1–80; `description` text ≤ 500 default `''`; `origin`
  `app|git` default `app`; `spec_seq` int ≥ 0 default 0; `validation` jsonb NULL; `query_checks`
  jsonb NULL; `preview` jsonb NULL; `first_applied_at`, `withdrawn_at`, `imported_at`,
  `deleted_at` timestamptz NULL; `created_by` FK app_user NULL; `created_at`, `updated_at`,
  `last_activity_at` timestamptz default now(). Status (FR-001) is derived, not stored (§6):
  borrador / aplicado / cambios sin aplicar / retirado.
- `project_file_revision`: `id` bigint identity; `project_id` FK project ON DELETE CASCADE; `path`
  text; `op` `create|update|delete|rename|restore|import|external|git`; `sha256` text NULL (NULL on
  delete); `content` text NULL; `size` int; `renamed_from` text NULL; `restored_from` bigint NULL;
  `actor_kind` `user|agent|system|external|git`; `actor_id` FK app_user NULL; `command` text ≤ 60
  (`/speckit-…`, `edit`, `rename`, `delete`, `restore`, `import`, `external`, `git`, `create`);
  `session_id` FK assistant_session ON DELETE SET NULL; `group_id` uuid; `created_at`. Indexes
  `(project_id, path, id DESC)`, `(project_id, id DESC)`, `(project_id, group_id)`.
- `assistant_session`: `project_id` bigint FK project ON DELETE CASCADE (NOT NULL after backfill),
  `current_spec` text NULL (check spec-folder pattern), `read_only` bool default false.
- `workspace_version`: `projects` jsonb NOT NULL default `'{}'` (R3).
- `email_subscription`: `project_id` FK project ON DELETE SET NULL, `distribution_id` text NULL,
  `distribution_index` smallint NULL; check `(project_id IS NULL) = (distribution_id IS NULL)`;
  unique `(project_id, distribution_id, distribution_index)`.
- Audit kinds: `project_created`, `project_updated`, `project_deleted`, `project_purged`,
  `project_applied`, `project_withdrawn`, `project_imported`, `project_exported`,
  `project_converted`.
- Backfill (R10): if `assistant_session` has rows or an active `workspace_version` exists, insert
  `principal` (name "Principal", origin `git` when the active version's `commit` is not NULL,
  `created_by` = the super user, `imported_at` NULL); `UPDATE assistant_session SET project_id =
  principal, read_only = true`; then `ALTER … SET NOT NULL`. Downgrade: refuses when projects other
  than `principal` or rows of the new audit kinds exist; otherwise drops in reverse order.
- Models in `backend/app/models.py`: `Project`, `ProjectFileRevision`, new columns, constants
  `PROJECT_ORIGINS`, `REVISION_OPS`, `REVISION_ACTORS`, audit kinds.

### 3. Revisions, history, diff, restore, external changes (`backend/app/projects/history.py`)

- `record(db, project, path, op, content|None, actor, command, session_id, group_id)`.
- `latest(db, project_id, path)`; `file_map(db, project_id) -> {path: sha}` from latest non-delete
  revisions (one `DISTINCT ON (path)` query).
- External changes (spec edge case): `sync_external(db, project)` compares `fs.list_files` with
  `file_map`; differing/new files → revision `op=external`, `actor_kind=external`,
  `command=external`; missing files → `op=delete` external. Called by `apply_ops`, tree reads and
  file reads (cheap: sizes+sha of ≤ 400 small files; a per-process cache keyed by (path, mtime_ns,
  size) avoids re-hashing).
- `list_revisions(project_id, path?, spec?, before_id?, limit≤100)` — newest first, grouped by
  `group_id` in the API response, merged with audit events `project_applied` /
  `project_withdrawn` / `project_imported` of the project.
- `diff(rev_a, rev_b|current)` → `difflib.SequenceMatcher` hunks `[{a_start, b_start, lines:
  [{t: " "|"+"|"-", text}]}]`, 3 context lines, capped at 5 000 lines (`truncated: true`).
- `restore(project, revision_id, base_sha256, actor)` → `apply_ops` write with `op=restore`,
  `restored_from`, `command=restore` (a deleted file is recreated; restoring a delete revision
  deletes).
- `spec_timeline(project, folder)` (FR-012): stage events from revisions of the folder (first
  spec.md, first clarify, first plan.md, first tasks.md, first revision with no open task,
  versions whose `projects[slug].files` contained the folder: `applied_at`), plus conversations =
  distinct `session_id` of those revisions ∪ sessions with `current_spec = folder`.

### 4. Project service (`backend/app/projects/service.py`)

- `suggest_slug(name)` (NFKD → ascii, lowercase, `[^a-z0-9]+` → `-`, trim, ensure leading letter,
  ≤ 50, unique by `-2`, `-3`…); `create(db, actor, name, slug?, description?)` → row + folder with
  `project.yaml` (template `workspace_template/files/project.yaml`), `.specify/memory/
  constitution.md` (template `files/constitution.md`), empty `specs/`, `integrations/`,
  `reports/`, `distributions/` (revisions `op=create`, `command=create`), audit `project_created`.
  Folder creation failure rolls back the row and removes the partial folder.
- `rename(db, project, name?, description?, slug?)`: name/description any time (rewrites
  `project.yaml`, revision `command=rename`); slug only when `first_applied_at IS NULL` (moves the
  folder under the project lock), else 409 `slug_locked`.
- `delete(db, actor, project)`: refused while the active version contains the project (409
  `project_applied`, "Retíralo del espacio primero"); moves to `.papelera` (R15), `deleted_at`,
  audit. `purge_trash(db, now)`.
- `list(db)` → per project: name, slug, origin, status, spec count, last activity, integrations,
  reports, distributions (current folder) and applied ones, conversation count, problems count.
- `detail(db, project, viewer)` → meta, status, `changed_files` since applied (§6), validation,
  readiness (§9), last apply (version id, time, actor), specs `[{folder, number, title, kind,
  stage, converged}]`, viewer's conversations.

### 5. Specs: numbering, kind, stage (`backend/app/projects/specs.py`, `cli/bizview_cli/validate.py`)

- `parse_spec(text) -> {title, kind, status, source, clarified, open_tasks}` with the kind regex of
  R7 (shared helper `bizview_cli.validate.spec_kind()`).
- New spec folder rule in `apply_ops`: creating any file below a non-existing `specs/NNN-x/`
  requires `NNN == spec_seq + 1` (else `spec_number` error "usa el número 004"); `spec_seq` is
  bumped in the same transaction. Renaming a spec folder keeps its number.
- `stage(project, folder, files, file_map_applied, sources)` per R7; `fuente` uses
  `DataSource.last_test_ok`; the "Implementada" step of a `fuente` spec whose source is missing
  returns `source_missing` with the link target `/admin/fuentes/nueva?kind=<kind>` (kind read from
  a `**Tipo de fuente**:` line when present).
- Validator v2 (CLI): every spec folder of a project needs `spec.md` with a kind line (error
  `spec_kind_missing`), folder pattern, unique numbers (`spec_number_duplicate`); artifacts must
  point (`spec:`) to `specs/NNN-x` of their own project with the matching kind (integration →
  integracion, report → reporte, distribution → distribucion); `fuente` specs: `**Fuente**:` line
  required, unknown source is an error when `known_sources` is given. Approval and open-task rules
  (005) unchanged for specs that produce artifacts.

### 6. Distributions, subscriptions ownership (`cli/…/distribution.schema.json`, `backend/app/projects/distributions.py`)

- Schema (R8): `id`, `spec`, `report`, `subscriptions` (≤ 20) of `{frequency daily|weekly|
  monthly, hour 0–23, weekday 0–6 (weekly only, 0 = lunes), monthday 1–28 (monthly only), period
  (report period ≠ custom), recipients {roles: [admin|user], minItems 1}, attach_pdf (default
  true), link_days 1–90|null, paused (default false)}`, `share {allowed (default true), max_days
  1–90}`. Semantic checks in the validator: report exists in the composed workspace; period in the
  report's `periods.allowed`; `attach_pdf` needs `pdf.enabled`; not `attach_pdf` and no
  `link_days` → error; `link_days ≤ share.max_days`; a role not in the report's `access.roles` →
  warning. Distribution ids unique across projects.
- `distributions.sync(db, version, actor)` (FR-006): for each `artifacts.distributions[id]`
  (project P, report R → dashboard by `report_id`): upsert `email_subscription` by
  `(P.id, id, index)` with `created_by = actor`, `recipients = [{"role": r}…]`, schedule fields,
  keep `paused` set by hand unless the YAML changed `paused`; delete owned rows not in the version;
  audit `email_subscription_created|updated|deleted` with `detail.project`. Called by apply,
  withdraw, rollback and Git apply.
- `mail/subscriptions.py`: `tick` resolves `{"role": r}` entries to active users of role `r` who
  `can_open` the dashboard; `to_json` adds `managed_by {project, slug, distribution}`;
  `update`/`delete` refuse owned rows (409 `managed_by_project`); pause/resume allowed. The 20 per
  dashboard cap counts owned rows; validation warns when it would be exceeded.
- `sharing/links.py::create`: policy from the active version's distributions of the report.

### 7. Composition, validation, apply, withdraw (`backend/app/projects/compose.py`, `apply.py`)

- `version_projects(version) -> {slug: ProjectSnapshot}` (legacy reader `legacy_tree` for
  versions without `projects`: everything is `principal`, spec folders renumbered per R10).
- `write_version_project(snapshot, dest)` writes one project subtree from a version
  (project.yaml, every stored spec document, artifacts with their files, distributions).
- `compose(db, *, include: Project|None, exclude_slug: str|None, dest) -> Path`: root
  `bizview.yaml` (active manifest or template), every snapshot except the target slug, then the
  project's layout files (from `fs`, after `sync_external`); returns the root. A per-process cache
  of the "others" tree keyed by `(active version id, slug)` keeps a save under 2 s (FR-008).
- `validate_project(db, project) -> dict`: compose + `workspace.service.validate_root`; issues
  whose `file` starts with `projects/<slug>/` are mapped to project-relative paths with `line`
  (§10); issues of other projects keep `project` (e.g. "el id facturas ya lo usa el proyecto
  ventas", FR-013). Stored in `project.validation` with `base_version` and files fingerprint.
- `apply_project(db, actor, project, ip)` (FR-013, US5): idle check of the project's
  conversations; `origin.recheck_draft(view)`; readiness gate (pending empty); `lock_workspace`;
  compose with the project; validate + write lock; `service.apply_tree(origin="project:<slug>",
  projects_meta=…)`; `distributions.sync`; `first_applied_at` once, `withdrawn_at = NULL`; audit
  `project_applied {project, version, files}`; drop the preview.
- `withdraw_project` (FR-014): compose excluding the project; validation failure (e.g. another
  project's report uses this project's integration) → 409 naming the dependants; apply; sync
  (owned subscriptions removed); `withdrawn_at`; audit. `ds_*` untouched.
- `workspace.service`: `_artifacts(result)` adds `project`/`spec` per artifact, `distributions`,
  v2 spec keys; `_activate` stores `projects` (`{slug: {project_id, origin, name, project_yaml,
  files}}`, `files` = sha of every layout file of each project in the composed tree);
  `rollback` calls `distributions.sync`; `version_json` adds `projects` (FR-015) and keeps the old
  keys; `spec_document(key)` accepts v2 keys and legacy keys.
- Git apply (R9): `apply()` validates the mounted tree as today, then composes it with the app
  projects and applies; afterwards `importer.mirror_git_projects(version)`.

### 8. Version recording of the owning project (FR-015)

- Every artifact and spec in `artifacts`/`specs` carries `project` (slug). `version_json` returns
  `projects: [{slug, name, origin, integrations, reports, distributions, specs: [{key, folder,
  kind, title, status}]}]`; the Workspace page shows the spec archive grouped by project and the
  owning project per integration/report.

### 9. The 017 tools move from `session.draft` to the project folder

- `WorkView` (R4) wraps (project, session); `tools.run_tool`, `service._turn`, `state_text`,
  `readiness.compute`, `origin.recheck_draft/check_query`, `preview.*` receive it instead of the
  raw session where they read draft/validation/query_checks/preview.
- `propose_draft(files, summary)`: writes/overwrites the given files through `apply_ops`
  (actor agent, `command` = running command or `agent`, `session_id`); files not listed stay;
  probe detection only when the project has no spec yet. `edit_draft(ops)`: same ops, `write`
  with the R5 seen-sha check, `replace` content-anchored, `delete` needs the file; returns
  validation + readiness + `files`. `read_draft(paths)`: reads from disk (after `sync_external`),
  records `working_state.seen[path] = sha`. Paths are project-relative; legacy `specs/integrations/…`
  paths are refused with `layout.ALLOWED_TEXT`.
- `duplicate_integrations`/`edit_integrations` (017 T017) are removed: an id used by another
  project is a validator error; editing the project's own applied integration is normal work.
- System prompt (`SYSTEM_PREFIX`) and `authoring.DRAFT_PATHS`/`RULES` describe the project layout,
  numbering, kind line and distributions; the `## Estado` suffix lists the project files (path,
  size, sha8), the next spec number and the current spec.
- Sessions: `create_session(project_id)` required; `read_only` sessions refuse messages (409
  `read_only`); `session_json` adds `project {id, slug, name}`, `current_spec`, `read_only` and
  takes `validation/readiness/preview` from the project; `draft` is replaced by `files` (index).
  `apply_draft` and `/sessions/{id}/apply` delegate to `apply_project`. `PATCH /sessions/{id}`
  accepts `current_spec`.

### 10. Problem positions (`backend/app/projects/positions.py`)

`line_for(text, pointer)` via `yaml.compose` marks (YAML/JSON), Markdown marker lines; added to
validation problems as `line` (R14).

### 11. CLI v2 (`cli/bizview_cli/{layout,validate,init,project,__main__}.py`)

- `validate(root)` detects the layout; v2 loads entries per project (Entry gains `project`,
  `folder = projects/<slug>/<kind>s/<id>`), loads `distributions/*.yaml`, checks `project.yaml`
  (`project.schema.json`: name 1–80, slug = folder name, description ≤ 500, locale es|en optional),
  spec folders (§5), duplicate ids across projects (`duplicate_id` naming both projects).
- Lock v2: entries keep keys `integrations/<id>`, `reports/<id>`, add `distributions/<id>`, each
  with `project`; plus `projects: {slug: {project: sha(project.yaml), specs: {folder: {kind,
  sha256}}}}`; `layout: v2|legacy`. `lock_differences` compares the new parts too. CLI 0.4.0.
- `bizview init <path> --name` creates a v2 workspace (root `bizview.yaml`, README/AGENTS/CLAUDE
  rules, `projects/`); `--layout legacy` keeps the 005 behaviour.
- `bizview project new <name> [--path .] [--slug] [--agent claude] [--no-speckit]` creates
  `projects/<slug>/` with the template files and, unless `--no-speckit`, runs `specify init --here`
  + preset + extension inside the project folder (each project folder is a Spec Kit root).
- Templates: preset `spec-template.md` uses `**Tipo**: [fuente | integracion | reporte |
  distribucion]` and a section per kind (fuente: `**Fuente**:`, tables, direct-read decision);
  new `files/project.yaml`; README/AGENTS/CLAUDE rules describe the project layout.
- Golden: `golden/` becomes a v2 workspace (`projects/ejemplo/…` with specs 001 integracion,
  002 reporte, 003 distribucion); `golden-supabase/` likewise; a legacy fixture stays in
  `cli/tests/fixtures/legacy/` for the compatibility test. `authoring.guide('example')` returns
  project-relative paths.

### 12. Zip export / import (`backend/app/projects/zip.py`)

Per R13. `export(project) -> bytes` (audit `project_exported`); `import_zip(db, actor, data, name?,
slug?)` → project + revisions `command=import`, response `{project, ignored: [...], validation}`
(audit `project_imported`).

### 13. Importer and Git mirror (`backend/app/projects/importer.py`)

- Uses `compose.legacy_tree(version) -> {path: text}` (deterministic, R10), the same reader
  `compose.version_projects` uses for legacy versions.
- `ensure_principal(db)` at bootstrap; `mirror_git_projects(db, version)` after a Git apply.

### REST API (`backend/app/api/projects.py`, prefix `/api/projects`, super user, CSRF)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/projects` | list (lazy trash purge) |
| GET | `/api/projects/slug?name=` | slug suggestion |
| POST | `/api/projects` | `{name, slug?, description?}` |
| GET | `/api/projects/{slug}` | detail (§4) |
| PATCH | `/api/projects/{slug}` | `{name?, description?, slug?}` |
| DELETE | `/api/projects/{slug}` | step-up; to trash |
| GET | `/api/projects/{slug}/tree` | files `{path, size, sha256, spec?}` + folders + ignored |
| GET | `/api/projects/{slug}/file?path=` | `{path, content, sha256, revision_id}` |
| PUT | `/api/projects/{slug}/file` | `{path, content, base_sha256, force?}` → file + validation + readiness |
| POST | `/api/projects/{slug}/ops` | `{ops: [rename/delete/mkdir/rmdir]}` |
| GET | `/api/projects/{slug}/changes?after=` | revisions after id + latest id + busy |
| POST | `/api/projects/{slug}/validate` | re-run validation |
| GET | `/api/projects/{slug}/history?path=&spec=&before=&limit=` | grouped revisions + events |
| GET | `/api/projects/{slug}/history/{rid}` | revision content |
| GET | `/api/projects/{slug}/diff?from=&to=` | hunks (`to` omitted = current) |
| POST | `/api/projects/{slug}/history/{rid}/restore` | `{base_sha256}` |
| GET | `/api/projects/{slug}/specs/{folder}/timeline` | stages + conversations |
| POST | `/api/projects/{slug}/apply` | step-up |
| POST | `/api/projects/{slug}/withdraw` | step-up |
| POST | `/api/projects/{slug}/convert` | step-up; git → app |
| POST | `/api/projects/{slug}/preview` | 014 preview via the project's conversation |
| GET | `/api/projects/{slug}/preview/report/{rid}` (+`/data`, POST `/pdf`) | project-scoped preview |
| GET | `/api/projects/{slug}/export.zip` | zip |
| POST | `/api/projects/import?name=&slug=` | step-up; `application/zip` body |
| POST | `/api/assistant/project-proposal` | `{text}` → `{name, slug}` (R16) |

Assistant routes: `POST /api/assistant/sessions` requires `project_id`; `GET /api/assistant/
sessions?project=<slug>`; `PATCH` accepts `current_spec`. Workspace routes keep their paths;
`version_json` grows `projects`. Errors use the backend i18n catalogue (022).

### Frontend

- Routes (`frontend/src/App.tsx`, lazy): `/proyectos` (`pages/projects/Projects.tsx`),
  `/proyectos/:slug` (`ProjectWorkspace.tsx`, query `?chat=<id>&file=<path>&line=`),
  `/proyectos/:slug/historial` (`ProjectHistory.tsx`). `/admin/asistente` → `/proyectos`;
  `/admin/asistente/:id` → fetch the session → `/proyectos/<slug>?chat=<id>`. Navigation entry
  "Proyectos" for super users; Administración tile "Asistente" becomes "Proyectos".
- `Projects.tsx`: list cards (name, specs, status badge, last activity, integrations/reports),
  "Nuevo proyecto" inline form (name → suggested slug editable → create → opens the project with
  its first chat), "Importar proyecto" (file input → step-up → result view with ignored files and
  problems).
- `ProjectWorkspace.tsx`: header (name editable, status badge, Aplicar / Retirar / Descargar /
  Historial / Vista previa), `PaneTabs` with `Explorer`, `EditorTabs` + `CodeEditor` /
  `MarkdownView`, `ProblemsPanel`, `StatusBar`, and the chat (`AssistantChat` bound to the
  project's conversation: selector of the viewer's conversations, "Nuevo chat en este proyecto",
  current spec chip). Apply/withdraw results and the "changed files since applied" list are views.
- `components/ide/`: `Explorer.tsx` (WAI-ARIA tree, collapsible folders, lucide icons per type,
  spec folders show kind badge + stage, inline new/rename/delete rows with the allowed patterns in
  errors), `EditorTabs.tsx` (≤ 8 tabs, dirty dot, inline "Guardar / Descartar / Cancelar" on
  close and on leave via `useBlocker`), `CodeEditor.tsx` (CodeMirror wrapper: language by
  extension, line numbers, lint markers from problems, `goToLine`, read-only for `git` projects),
  `MarkdownView.tsx` (react-markdown + remark-gfm, "Ver código" toggle), `ProblemsPanel.tsx`
  (file:line, message, fix; selecting opens the file at the line), `StatusBar.tsx`
  (`role="status"`: Válido / N problemas / Listo para aplicar, last apply, save state),
  `PaneTabs.tsx` (tabs < 1024 px, resizable panels ≥ 1024 px), `useProjectChanges.ts` (R12),
  `ConflictBar.tsx` (stale save / changed-on-disk choices).
- `ProjectHistory.tsx`: revision groups (actor, command, files, time), per-file filter, two
  revisions → diff table (`components/ide/DiffView.tsx`), "Restaurar" inline confirm, spec
  timeline per spec.
- Docked assistant panel: shows the conversation's project with a link; "Nuevo chat" asks the
  first message then the inline project proposal (R16).
- 018 subscription list shows "Gestionado por el proyecto X" and hides edit/delete for owned rows.
- Strings in `i18n/es.ts` and `i18n/en.ts` under `projects.*`, `ide.*`, `history.*`.

### Supporting libraries (constitution V)

`@codemirror/state`, `@codemirror/view`, `@codemirror/commands`, `@codemirror/language`,
`@codemirror/search`, `@codemirror/lint`, `@codemirror/lang-yaml`, `@codemirror/lang-sql`,
`@codemirror/lang-markdown`, `@codemirror/lang-json` (editor), `react-markdown` + `remark-gfm`
(safe Markdown), `react-resizable-panels` (accessible desktop panes) — reasons in R11. Backend:
stdlib only.

### Settings, compose, install

- `backend/app/config.py`: `projects_dir: str = str(ROOT / "projects")` (env `PROJECTS_DIR`),
  `project_max_mb: int = Field(20, ge=1, le=500)`. Bootstrap checks the folder exists and is
  writable (log + project pages show "La carpeta de proyectos no se puede escribir").
- `docker-compose.yml`: backend `PROJECTS_DIR: /app/data/projects`, volume
  `${PROJECTS_DIR_HOST:-./projects}:/app/data/projects` (rw, backend only; the worker gets none).
- `backend/Dockerfile`: `mkdir -p /app/data/projects && chown app` before `USER app`.
- `deploy/install.sh`: creates `$DIR/projects` (`install -d -m 0750 -o 10001 -g 10001` when root,
  else a printed `sudo chown 10001:10001` hint), adds the volume to the generated compose, adds
  `PROJECT_MAX_MB=20` to `.env`, mentions `projects/` in the backup note.
- `.env.example`, `.gitignore` (`/projects/`), README/deploy docs.

## Tests (focused per task; full suites at the end of the queue)

- CLI: layout allow-list; v2 + legacy validation; mixed layout; kind line aliases; numbering;
  duplicate ids across projects; distribution schema + semantic checks; lock v2; `project new`;
  golden v2 validates.
- Backend: `fs` traversal/absolute/backslash/symlink (root, parent, final)/size/project cap/
  not-writable; `apply_ops` base checks and pairing (failure after replace restores bytes, no
  revision); external change detection; numbering rule; history/diff/restore/timeline; stage
  derivation; compose (others from version, legacy reader); apply/withdraw/rollback with two
  projects (US5 independent test); owned subscriptions sync never touches hand-made rows; role
  recipients at tick; share policy; migration 0018 backfill + downgrade guard; importer
  (renumbering, SC-005 artifact equality, status "Aplicado"); Git apply composition and conflicts;
  zip export/import guards (zip-slip, symlink, bomb, ignored files); tools on project files
  (seen-sha refusal, project-relative paths, revisions with agent actor and session).
- Frontend unit: Explorer keyboard tree, EditorTabs dirty/close bar, ProblemsPanel → open at line,
  PaneTabs at 375 px, StatusBar states, ConflictBar, DiffView, no-modals and no-raw-colors pass.
- e2e (fake provider): SC-001 flow (new project → fuente + direct reporte specs → apply →
  dashboard); SC-002 folder/explorer equality after create, edit, agent change, restore, import;
  SC-003 revisions per change; SC-004 axe at 375 px + 30-file project load < 1.5 s.

## Risks

- **Composition cost on every save** (FR-008 2 s): mitigated by the per-version cache of other
  projects' trees and validating only on saves of validated paths; measure in e2e.
- **Host folder permissions** (bind mount owned by root): install.sh sets ownership when run as
  root; otherwise creation fails with a clear message — documented.
- **Git + app on the same installation**: origin rules (R9) refuse conflicting applies; operators
  must convert `principal` before editing it in the app when it came from Git.
- **Legacy versions without spec documents**: principal imports artifacts without specs and shows
  `missing_spec_documents` until regenerated; SC-005 then holds for artifacts only.
- **Old unapplied drafts** are not migrated (read-only conversations keep them visible).
- **Disk/DB divergence** after an administrator edit or a crash between replace and commit: handled
  as an external change revision on the next read (never silent).
- **021 dependency**: per-command write limits and command names in revisions arrive with 021;
  until then agent revisions use `command = "agent"`.
- **Rollback depth**: 005 keeps one previous version; owned subscriptions follow the re-activated
  version, but hand-paused owned rows recreated after a withdraw lose their pause.

## Spec changes made while planning

1. US2 AC4 / FR-006 context: distribution recipients are roles only (people never named in
   project files, constitution VIII).
2. SC-005: "same checksum of artifacts" → same artifact definitions (apart from the rewritten
   `spec` paths) and files.
3. US6 AC3 / FR-018: the zip opens with the same commands after a one-time `specify init --here`
   documented in its README (Spec Kit's scripts are not redistributed in the image).
4. FR-002: files outside the layout in a Git checkout or an imported zip are ignored and listed.
