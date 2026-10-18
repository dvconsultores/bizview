# Research: BI projects — a workspace per chat with numbered specs

**Feature**: 020-bi-projects | **Date**: 2026-10-08 | **Plan**: [plan.md](./plan.md)

Decisions taken while planning. Each one names what was chosen, why, and what was rejected.

## R1 Working copy on disk, history in the database

- **Decision**: the project folder `PROJECTS_DIR/<slug>/` holds the current content only; every
  change is a row of `project_file_revision` with the full text of the file (≤ 512 KB per file,
  `PROJECT_MAX_MB` per project). No Git binary, no `.git` folder in projects.
- **Rationale**: the spec Assumptions forbid a Git binary in the image; full-content rows make
  restore and diff trivial (`difflib`) and survive a lost folder (the folder can be rebuilt from
  the latest revisions). Size is bounded by the per-file and per-project caps.
- **Alternatives**: libgit2/pygit2 (new native dependency, a stack question, and a second source
  of truth); storing deltas (smaller, but restore/diff need replays and the files are small).

## R2 Safe path resolution

- **Decision**: one allow-list of the FR-002 layout as regular expressions in
  `cli/bizview_cli/layout.py` (shared by the CLI validator, the zip importer and the backend).
  The backend resolves a project path in `backend/app/projects/fs.py`:
  1. reject empty, absolute, backslash, NUL, `.`/`..` segments, segments starting with `.` other
     than the literal `.specify/memory/constitution.md`, length > 240;
  2. require a match against the layout allow-list (error lists the allowed patterns);
  3. walk every component from the project root with `os.lstat` and refuse any symlink (also the
     project root itself and `PROJECTS_DIR`);
  4. confirm `os.path.commonpath([root, realpath(target)]) == root`;
  5. write through a temporary file in the same directory opened with
     `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW` (mode 0640), `fsync`, then `os.replace`; directories are
     created one component at a time with `mkdir(mode=0o750)` and re-checked with `lstat`.
  Reads use `O_RDONLY|O_NOFOLLOW` and refuse non-regular files.
- **Rationale**: a regex allow-list alone does not stop a symlink planted by an administrator or
  by a crafted zip; component-wise `lstat` plus `O_NOFOLLOW` closes the TOCTOU window for the
  final component, and `commonpath` is the last guard.
- **Alternatives**: `Path.resolve()` + prefix check only (follows symlinks, racy); chroot/openat2
  `RESOLVE_BENEATH` (Linux ≥ 5.6 only and not exposed by the Python stdlib).

## R3 The applied workspace is a set of project subtrees

- **Decision**: a workspace version stays one `workspace_version` row; it gains a `projects`
  JSON map `{slug: {project_id, origin, name, project_yaml, files: {path: sha256}}}` and every
  artifact entry (`artifacts.integrations[id]`, `artifacts.reports[id]`, new
  `artifacts.distributions[id]`) carries `project` and `spec`. Spec entries move to keys
  `<slug>/specs/<NNN-name>` with `project`, `kind`, `documents` (all Spec Kit documents of the
  folder). Versions applied before 020 have no `projects` map and are read as one project
  `principal` (legacy reader in `backend/app/projects/compose.py`).
- **Composition** (`compose.py`): to validate or apply project P, write a temporary v2 tree:
  root `bizview.yaml` (active manifest or the template), every other project of the active version
  rebuilt from the version under `projects/<slug>/`, and P's current folder (layout files only)
  under `projects/<P>/`; then run the same `bizview_cli.validate` and `workspace.service.apply_tree`.
  "Retirar" composes without P.
- **Rationale**: the engine keeps reading artifacts by id (unchanged worker, unchanged report
  engine); ownership is metadata; rollback (005) stays a state swap.
- **Alternatives**: one version per project (the engine would need to merge versions on every
  read; rollback semantics unclear); flattening projects into the legacy layout (spec folders
  would collide between projects).

## R4 Project-level working state (validation, query checks, preview)

- **Decision**: `project.validation`, `project.query_checks` and `project.preview` (jsonb) replace
  the per-conversation `assistant_session.validation/query_checks/preview` for new work. A small
  adapter `backend/app/projects/workview.py` (`WorkView`) exposes the attributes that
  `readiness.py`, `origin.py`, `preview.py` and `tools.py` already read (`draft`, `validation`,
  `query_checks`, `preview`, `working_state`, `id`, `status`, `stats`) so those modules change only
  at their call sites. `draft` is read-only and returns `{"files": <project files>, "summary":
  <project name>}`. The preview still runs in the conversation's schemas (`preview_<session id>`,
  existing lock and runner); its outcome is stored on the project with `session_id` and the files
  fingerprint, and a new preview from another conversation drops the previous session's schemas.
- **Rationale**: the editor's status bar (FR-007/FR-008) and every conversation of the project
  must show the same readiness; the adapter keeps the 017 readiness rules untouched.
- **Alternatives**: merging per-session states at read time (ambiguous which preview counts);
  moving preview schemas to project ids (touches `engine/datasets.py`, `engine/report.py`,
  `engine/runner.py` for no user-visible gain).

## R5 Revision checks for concurrent writers

- **Decision**: every write names the sha256 the writer last saw (`base_sha256`, `null` for a new
  file). Editor save with a stale base → 409 `file_changed` with the current revision (author,
  time); the editor shows the choice inline (Ver diferencias / Sobrescribir / Descartar mis
  cambios); "Sobrescribir" resends with `force: true` (last save wins, both revisions kept).
  Agent: the session remembers the sha it read or wrote per path (`working_state.seen`);
  `edit_draft` `write` on a file whose current sha differs is refused ("cambió desde que lo leíste
  — edición manual de Ana, 10:42; léelo con read_draft"); `replace` ops are anchored on content
  and allowed while `old` still occurs exactly once; `delete` needs the seen sha.
- **Rationale**: matches the spec edge case (both revisions kept, the second writer is told) without
  silently overwriting a person's edit with an agent's stale copy.

## R6 File writes commit on their own

- **Decision**: `projects.fs.apply_ops()` opens its own DB session, takes
  `pg_advisory_xact_lock(lock_key("project", id))`, checks bases, writes the files, inserts the
  revisions and commits; on an exception after a file was replaced it restores the previous bytes
  before re-raising. Callers (API request, agent round) never hold that transaction.
- **Rationale**: an agent round can be rolled back (017 stop/claim lost); files and their revisions
  must stay paired (spec edge case: "the database history never records a revision whose file
  write failed", and SC-003: 0 missing revisions). Files written by an interrupted command stay
  (021 edge case).

## R7 Spec numbering, kind and stage

- **Decision**:
  - Folder `specs/NNN-<short>` (`^[0-9]{3}-[a-z0-9][a-z0-9-]{0,59}$`). A write that creates a new
    spec folder must use `project.spec_seq + 1` (bumped in the same transaction); numbers are never
    reused because `spec_seq` only grows (FR-004).
  - Kind line regex accepts `**Tipo**:`, `**Type**:` and the legacy `**Spec type**:`, with values
    `fuente|integracion|reporte|distribucion` and the aliases `source|integration|report|
    distribution` (accents tolerated); canonical value is the Spanish one. A missing kind line is a
    validation error on every spec of a v2 project.
  - Stage (computed in `backend/app/projects/specs.py`): Especificada (spec.md) → Aclarada
    (a `## Clarifications` bullet `- Q:` that is not the template placeholder, or a spec.md
    revision by `/speckit-clarify`) → Planificada (plan.md) → Tareas (tasks.md) → Implementada
    (Status Approved/Implemented, no open task, and the kind condition: ≥ 1 linked integration /
    report / distribution, or for `fuente` the `**Fuente**:` source exists with `last_test_ok`) →
    Aplicada (Implementada and the spec folder plus linked artifacts have the same sha256 in the
    active version's `projects[slug].files`). "Convergida" badge: the latest tasks.md revision by
    `/speckit-converge` added open tasks.
- **Rationale**: derivable from files + history, no extra state to drift (spec US2 AC2).

## R8 Distributions and owned subscriptions

- **Decision**: `cli/bizview_cli/schemas/distribution.schema.json` (`id`, `spec`, `report`,
  `subscriptions[≤20]` with `frequency/hour/weekday/monthday/period/recipients.roles/attach_pdf/
  link_days/paused`, `share {allowed, max_days}`). Recipients are **roles only** (`admin`, `user`):
  the resolved people are the active users of those roles who can open the dashboard, resolved at
  send time. Project files are read by the agent, so names or emails of people never go into them
  (constitution VIII); individual recipients stay hand-made subscriptions on the dashboard (018).
- `email_subscription` gains `project_id`, `distribution_id`, `distribution_index` (unique
  together). `projects/distributions.py::sync(db, version, actor)` upserts the owned rows of every
  distribution in the version (keeps `paused`, recomputes `next_due_at` when the schedule changes)
  and deletes owned rows no longer present; hand-made rows (`project_id IS NULL`) are never read.
  `sync` runs after apply, withdraw and rollback. The 018 API refuses edit/delete of owned rows
  (409 `managed_by_project`) but allows pause/resume; the subscription list shows the project.
- Share policy: `sharing/links.py` reads `share` of the distributions for the dashboard's report
  in the active version (`allowed: false` → 409; `days > max_days` → 422).
- **Alternatives**: user ids in YAML (not portable across installations, opaque for review);
  emails in YAML (personal data reaches the AI provider).

## R9 Git workspaces and project origin

- **Decision**: `project.origin` is `app` or `git`. A Git apply (`/api/workspace/apply`) validates
  the mounted checkout alone first (committed lock check as today), then composes it with the
  `app` projects of the active version: Git projects replace their slugs; an `app` project with
  the same slug as a Git project refuses the apply naming it. After a Git apply the backend mirrors
  each Git project into `PROJECTS_DIR` as a read-only `git` project (revisions actor `git`,
  command `git`). "Convertir en proyecto de la aplicación" (step-up) flips `origin` to `app`; from
  then on a Git apply that contains that slug is refused. The legacy flat layout is project
  `principal`.
- **Rationale**: a Git apply must not silently withdraw projects built in the app, and an app edit
  must not be silently overwritten by Git.

## R10 Upgrade: project `principal`

- **Decision**: migration `0018_projects` inserts project `principal` (origin `git` when the active
  version has a commit, else `app`; `imported_at NULL`) when any conversation or an active version
  exists, sets every existing `assistant_session.project_id` to it with `read_only = true`, then
  makes `project_id` NOT NULL. Files are written by `projects.importer.ensure_principal()` at
  `python -m app.cli bootstrap` (idempotent; retried at next start when the folder is not writable)
  using the deterministic legacy reader of R3: specs renumbered 001… ordered by the old folder
  number, then integrations before reports, then name; artifact `spec` rewritten; a
  `**Tipo**:` line inserted after the legacy `**Spec type**:` line. The active version is not
  changed; principal's status compares its folder with the same deterministic tree, so it shows
  "Aplicado" right after the upgrade (SC-005 compares artifact definitions without `spec` and
  artifact files).
- Versions whose spec documents were never stored (pre-011) import the artifacts and leave the
  spec folder missing → the 017 `missing_spec_documents` problem tells the user what to regenerate.
- Unapplied drafts of old conversations stay visible (read-only) in their conversation; they are
  not written into `principal`.

## R11 Editor libraries (supporting libraries, constitution V)

- **CodeMirror 6** (`@codemirror/state`, `view`, `commands`, `language`, `search`, `lint`,
  `lang-yaml`, `lang-sql`, `lang-markdown`, `lang-json`): modular (~150 KB gz for what we load),
  works with touch and mobile keyboards, accessible contenteditable, theming through CSS
  variables (dark mode tokens, `no-raw-colors` test), lint gutter for problems. Rejected: Monaco
  (≈ 2 MB, web workers, poor mobile support), a plain `<textarea>` (no highlighting/line numbers,
  FR-007).
- **react-markdown + remark-gfm**: renders Markdown to React elements without
  `dangerouslySetInnerHTML` (agent-written content is untrusted), GFM tables and task-list
  checkboxes for `tasks.md`. Rejected: `marked` + DOMPurify (HTML string + sanitiser to maintain).
- **react-resizable-panels**: accessible separators (keyboard, ARIA `separator`), small, used only
  from 1024 px (FR-010). Rejected: hand-written drag handles (keyboard and touch work to redo).
- The project pages are lazy-loaded routes so the editor never loads on dashboard pages.

## R12 Live refresh

- **Decision**: polling `GET /api/projects/{slug}/changes?after=<revision id>` every 2 s while a
  conversation of the project is busy, every 15 s otherwise and on window focus. Open tabs without
  local edits reload; tabs with local edits show an inline banner (Ver diferencias / Recargar /
  Mantener lo mío).
- **Rationale**: same pattern as the 017 busy polling; no SSE/WebSocket plumbing through Caddy and
  the threaded run.

## R13 Zip export and import

- **Export**: the project's layout files under `<slug>/`, plus `.specify/templates/` (the preset
  templates), `.bizview/preset/`, `.bizview/extension/`, `.bizview/schemas/*.json`, `AGENTS.md`,
  `CLAUDE.md` and a `README.md` with the one-time `specify init --here` + `preset add` +
  `extension add` steps (Spec Kit's own scripts are generated by its CLI and are not shipped in
  the image).
- **Import** (`POST /api/projects/import`, raw `application/zip` body, no multipart dependency):
  compressed ≤ `PROJECT_MAX_MB`, ≤ 1 000 entries, uncompressed total ≤ `PROJECT_MAX_MB`, ratio
  ≤ 100 per entry, names checked like R2, symlink entries (mode `S_IFLNK` in `external_attr`)
  refused, one optional top folder stripped. Layout files are imported (revisions command
  `import`); other files are ignored and listed. Path, size and layout errors block; validation
  problems do not (the project is created as Borrador and shows them).

## R14 Problem positions

- **Decision**: the backend adds `line` (1-based) to every problem with a YAML `file` and JSON
  `path`, using `yaml.compose` node marks (`backend/app/projects/positions.py`); Markdown problems
  point at the line of the offending marker (`**Status**`, `**Tipo**`, first open task) when known.
  The frontend never parses YAML.

## R15 Trash

- **Decision**: delete moves the folder to `PROJECTS_DIR/.papelera/<slug>--<UTC yyyymmddHHMMSS>`
  and sets `project.deleted_at`; a lazy purge runs at bootstrap and on `GET /api/projects` and
  removes folders and rows older than 30 days (revisions and conversations cascade). The worker
  never reads `projects/` (spec Assumptions).

## R16 A chat outside a project

- **Decision**: the global "Nuevo chat" shows an inline step in the chat panel: the first message is
  typed first; `POST /api/assistant/project-proposal {text}` returns a name (deterministic
  `title_from`) and a free slug; the user confirms, edits or picks an existing project; then the
  project and the session are created and the message is sent. No provider call (works without
  AI for the naming step; constitution VIII).

## R17 Visibility

- **Decision**: every super user sees and edits every project (FR-001); conversations stay owned
  by their creator (014); the project page lists the viewer's conversations and counts the others.
