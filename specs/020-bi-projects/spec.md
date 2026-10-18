# Feature Specification: BI projects — a workspace per chat with numbered specs

**Feature Branch**: `020-bi-projects`

**Created**: 2026-10-08

**Status**: Implemented (closed 2026-10-12, backend + CLI + frontend + e2e suites green)

**Input**: Owner, 2026-10-08 (prompt.md): "for each chat create a new espacio de trabajo (physical
folders and structure) where all specs for this report project will live, like VS Code manages the
spec.md, plan, tasks, implement etc., to add any spec for the project: spec 001, spec 002, etc. This
way I can see and view the evolution and track, because any report project can have a datasource,
ETL, integration, report schedule, share etc., or just simply generate a report of an existing
source. The app must work as an agent, only for BI, and use specs … the app must work as an
in-cloud VS Code and app, in espacio de trabajo: project name, and specs. Remember ETL uses Rust
(Python lib Polars)."

**Builds on**: 005 (workspace, validate/apply/versions), 011 (spec archive), 014/017 (chat, tools,
preview, readiness), 018 (sharing and subscriptions), 019 (direct reports).
**Supersedes**: 014's "one draft per conversation" — the working copy is now the project folder; a
conversation belongs to a project. 017's tools keep their contracts but read and write project files.
**Constitution**: 2.0.0 principles IV (projects folder) and IX (projects, numbered specs).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A new chat creates a project with its own folder (Priority: P1) 🎯

The super user opens "Proyectos", presses "Nuevo proyecto", types a name ("Facturación Cliente C")
and lands in the project workspace: an explorer with the project folder on the left, an editor in
the middle and the chat on the right. The folder already holds the project's structure
(`project.yaml`, constitution, empty `specs/`).

**Why this priority**: every other story needs a project to live in.

**Independent Test**: create a project through the UI; the folder `projects/facturacion-cliente-c/`
exists on disk with the documented layout; the explorer shows the same tree; reloading the page shows
the same files.

**Acceptance Scenarios**:

1. **Given** the Proyectos page, **When** the super user creates a project with a name, **Then** a
   slug is derived (lowercase, digits, hyphens; unique; editable before creation), the folder is
   created with `project.yaml`, `.specify/memory/constitution.md` (from the installation template)
   and `specs/`, the creation is audited, and the first chat of the project opens.
2. **Given** the global "Nuevo chat" button, **When** the super user starts a chat outside a project,
   **Then** the agent asks for (or proposes from the first message) the project name and creates a
   new project for that chat; a chat never exists without a project.
3. **Given** an existing project, **When** the super user presses "Nuevo chat en este proyecto",
   **Then** a new conversation is attached to the same project and sees the same files.
4. **Given** the Proyectos page, **When** it loads, **Then** each project shows name, number of
   specs, status (Borrador / Aplicado / Cambios sin aplicar), last activity and its integrations and
   reports.

---

### User Story 2 - Numbered specs inside the project, like Spec Kit in VS Code (Priority: P1)

Every piece of work in the project is a numbered spec folder: `specs/001-fuente-erp/`,
`specs/002-etl-facturas/`, `specs/003-reporte-facturacion/`, `specs/004-envio-semanal/`. Each folder
has the Spec Kit documents (`spec.md`, `plan.md`, `tasks.md`, `research.md`, `checklists/…`) and the
artifacts it produces live in the project's `integrations/`, `reports/` and `distributions/`
folders, exactly as Spec Kit does in VS Code.

**Independent Test**: in a project, create four specs of the four kinds; the explorer shows
`specs/001…004` with their documents, each spec shows its kind and stage, and the artifacts appear
in their folders linked to their spec.

**Acceptance Scenarios**:

1. **Given** a project, **When** a new spec is created (021 `/speckit-specify`), **Then** it takes the
   next free number of the project (001, 002, …), a short name, and a kind line `**Tipo**:` with one
   of: `fuente` (documents a catalogue source), `integracion` (ETL into a BI table), `reporte`
   (dataset or direct, 019), `distribucion` (schedules and sharing).
2. **Given** a spec, **When** it advances, **Then** its stage is shown in the explorer and on the spec
   header: Especificada → Aclarada → Planificada → Tareas → Implementada → Aplicada (with
   "Convergida" when converge added work), derived from the documents present and the apply history.
3. **Given** a `fuente` spec, **When** implemented, **Then** it never contains credentials: it names
   the catalogue source, its purpose, tables of interest and the direct-read decision (019); if the
   source does not exist yet the implementation step links to Administración → Fuentes → Nueva with
   the kind preselected, and the spec stays "Implementada" only when the source exists and its last
   connection test passed.
4. **Given** a `distribucion` spec, **When** implemented, **Then** `distributions/<id>.yaml` declares
   email subscriptions (018 FR-010: report, frequency, hour, period, recipients by role, PDF,
   link days) and share-link policy (max days); people are never named in project files
   (constitution VIII: the agent reads them), individual recipients stay hand-made subscriptions on
   the dashboard; applying creates or updates the subscriptions owned by the project and never
   touches subscriptions created by hand.
5. **Given** a project that only needs a report over an existing table, **When** built, **Then** it
   may contain a single `reporte` spec in direct mode (019) and nothing else.

---

### User Story 3 - The cloud editor: browse, read and edit like VS Code (Priority: P1)

The project page works like VS Code in the browser: explorer tree (folders collapsible, file icons
by type), tabs with the open files, Markdown files rendered with a "Ver código" toggle, YAML and SQL
with syntax colouring and line numbers, editing with save, a status bar with validation and
readiness, and a problems list that opens the file at the line.

**Independent Test**: open `specs/003…/spec.md` (rendered), switch to code, edit a line, save; the
file on disk changes, the history records the edit by the user, validation re-runs and the problems
list updates; a YAML error points to file and line.

**Acceptance Scenarios**:

1. **Given** the explorer, **When** the super user opens a file, **Then** it opens in a tab; up to 8
   tabs; unsaved tabs show a dot; leaving with unsaved changes shows the choice inline in the view
   (no modal).
2. **Given** a saved file, **When** it is part of the validated set (artifacts, specs), **Then**
   validation runs on the whole project and the status bar shows "Válido" / "N problemas" /
   "Listo para aplicar" (017 readiness).
3. **Given** the problems list, **When** a problem is selected, **Then** the file opens at the line or
   JSON path of the problem (017 FR-003 fields).
4. **Given** a phone (375 px), **When** the project page is open, **Then** the three panes become
   tabs "Archivos / Editor / Chat" and every action stays reachable (constitution I).
5. **Given** the explorer, **When** the super user creates, renames or deletes a file or folder,
   **Then** only paths allowed by the project layout are accepted (with the allowed patterns in the
   error), and every change is recorded in the history.

---

### User Story 4 - Evolution and traceability (Priority: P2)

The owner wants to see how the project evolved: which spec was added when, which command changed
which files, who applied what.

**Independent Test**: after creating, planning, implementing and applying two specs, the history
lists each step in order with actor (user or agent + command), files changed, and a diff per file
between any two revisions.

**Acceptance Scenarios**:

1. **Given** any change to a project file (by the agent through a command, or by a person in the
   editor), **When** it is saved, **Then** a revision is stored with path, content hash, actor
   (user id or "agente"), command (`/speckit-plan`, "edición manual", "aplicar", …), conversation and
   time.
2. **Given** the history view, **When** two revisions of a file are chosen, **Then** a line diff is
   shown; any revision can be restored as a new revision.
3. **Given** a spec, **When** its timeline is opened, **Then** it shows its stages with dates and the
   conversations that worked on it.

---

### User Story 5 - Apply a project (Priority: P1)

When the project is "Listo para aplicar", the super user applies it; the project's integrations,
reports and distributions join the installation's active workspace as a new version.

**Independent Test**: two projects applied one after the other each create a new workspace version
containing both projects; rolling back the second restores the first only; ids clashing with another
project are rejected at validation.

**Acceptance Scenarios**:

1. **Given** a ready project, **When** "Aplicar proyecto" is pressed, **Then** after step-up the
   active version plus this project's current files is validated as one workspace and applied as a
   new version (014 FR-006 unchanged: audit, rollback), and the project status becomes "Aplicado".
2. **Given** an integration or report id already used by another project or by the Git workspace,
   **When** validated, **Then** it fails naming the project that owns the id.
3. **Given** an applied project edited later, **When** opened, **Then** it shows "Cambios sin
   aplicar" with the list of changed files since the applied revision.
4. **Given** a project, **When** "Retirar del espacio" is pressed (step-up), **Then** a new version
   without its integrations, reports and project-owned subscriptions is applied; the folder and
   history stay; `ds_*` data is kept until the engine's normal cleanup rules apply.

---

### User Story 6 - Existing work and Git workspaces keep working (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an installation upgraded with an active version and existing conversations, **When** the
   upgrade runs, **Then** the active version's integrations, reports and specs are imported once into
   project `principal` (specs renumbered 001… in their existing order, artifact `spec` paths
   rewritten), existing conversations are attached to `principal` as read-only history, and the
   active version is not changed.
2. **Given** a customer workspace managed in Git (`workspace/`), **When** it uses the v2 layout
   (`projects/<slug>/…`) or the legacy flat layout, **Then** `bizview validate` and the apply from Git
   accept both; the legacy layout is treated as project `principal`.
3. **Given** a project, **When** "Descargar" is pressed, **Then** a zip of the folder (with
   `.specify/` and the Spec Kit preset so it opens in VS Code with the same commands after a one-time
   `specify init --here` documented in its README) downloads;
   "Importar proyecto" accepts such a zip after validation.

### Edge Cases

- Two conversations of the same project edit the same file: last save wins per file, the history
  keeps both revisions, and the second conversation is told the file changed since it read it
  (revision check on `edit_draft` / editor save).
- Disk full or folder not writable: creation and saves fail with a clear message; the database
  history never records a revision whose file write failed.
- A file edited on disk outside the app (administrator shell): detected by hash on next read,
  recorded as revision "cambio externo".
- Project slug renamed: not allowed after the first apply (ids and history depend on it); the display
  name can change any time.
- Deleting a project: only when not applied (or after "Retirar"), with step-up; the folder is moved
  to `projects/.papelera/` and purged after 30 days.
- Very large files: the 014 size limits apply per file; total project size limit
  `PROJECT_MAX_MB` (default 20).
- Path traversal (`..`, absolute paths, symlinks): rejected; the backend resolves every path inside
  the project folder.

## Requirements *(mandatory)*

### Functional Requirements

#### Project and folder
- **FR-001**: A project MUST have id, name (1–80 chars), slug (unique, `^[a-z][a-z0-9-]{1,49}$`),
  description, creator, created/updated times, status (borrador / aplicado / cambios sin aplicar /
  retirado) and the applied revision set; projects are visible and editable by super users only.
- **FR-002**: Each project MUST be a folder `PROJECTS_DIR/<slug>/` (installation folder `projects/`,
  mounted read-write into the backend only) with this layout: `project.yaml`,
  `.specify/memory/constitution.md`, `specs/NNN-<short-name>/{spec.md, plan.md, tasks.md,
  research.md, data-model.md, quickstart.md, checklists/*.md}`, `integrations/<id>/{integration.yaml,
  queries/*.sql, requests/*.yaml}`, `reports/<id>/report.yaml`, `distributions/<id>.yaml`. Any other
  path is rejected (files outside the layout in a Git checkout or an imported zip, such as Spec Kit's
  own scripts, are ignored and listed, never imported).
- **FR-003**: Every conversation MUST belong to exactly one project; starting a conversation without
  a project creates one (name asked or proposed by the agent from the first message, confirmed by the
  user).
- **FR-004**: Spec numbers MUST be per project, sequential, three digits, never reused; the kind
  line `**Tipo**:` (fuente / integracion / reporte / distribucion) is mandatory in `spec.md`.

#### Artifacts per kind
- **FR-005**: `integracion` specs produce integrations as in 005/017, including the optional Polars
  transform stage (005 amendment 2026-10-08); `reporte` specs produce `report.yaml` (dataset or
  direct, 019); `fuente` specs produce no artifact and are satisfied by an existing, tested catalogue
  source; `distribucion` specs produce `distributions/<id>.yaml` validated by a new
  `distribution.schema.json` in `cli/`.
- **FR-006**: Applying MUST create, update or remove only the email subscriptions owned by the
  project (marked with project and distribution id); hand-made subscriptions are never touched.

#### Editor
- **FR-007**: The project page MUST provide explorer, tabbed editor (Markdown rendered/code, YAML,
  SQL, JSON with syntax colouring and line numbers), save, create/rename/delete within allowed paths,
  problems list linked to file positions, and a status bar (validation, readiness, last apply).
- **FR-008**: Saving a file MUST re-run project validation and readiness (017) and update the status
  bar and problems within 2 s for a typical project.
- **FR-009**: The chat panel MUST be part of the project page and show which spec is current; the
  agent's file changes appear in the explorer and open tabs live (refresh on change).
- **FR-010**: On phones the page MUST use tabs for the three panes; on desktop the panes are
  resizable.

#### History
- **FR-011**: Every file change MUST be stored as a revision (path, content, sha256, actor, command,
  conversation, time) in the database; the folder holds the current content. A restore creates a new
  revision.
- **FR-012**: The history view MUST list revisions per project and per file, show line diffs between
  two revisions, and per spec a timeline of stages.

#### Apply and versions
- **FR-013**: "Aplicar proyecto" MUST validate the composition (active version with this project's
  subtree replaced by the current folder) as one workspace, require step-up, apply as a new version,
  audit, and allow rollback (005). Integration and report ids MUST be unique across projects.
- **FR-014**: "Retirar del espacio" MUST apply a new version without the project's artifacts.
- **FR-015**: The workspace version MUST record, per artifact and spec, the owning project; the
  spec archive (011) shows specs grouped by project.

#### Compatibility
- **FR-016**: A one-time upgrade step MUST import the active version into project `principal` and
  attach existing conversations to it (read-only), without changing the active version; a
  conversation holding an unapplied draft becomes its own project («<título> (borrador)») with the
  draft files and stays editable.
- **FR-017**: The CLI (`bizview validate`, `init`, new `bizview project new <name>`) and the apply
  from Git MUST accept the v2 layout and the legacy flat layout (as `principal`).
- **FR-018**: Projects MUST be downloadable as a zip that opens in VS Code with Spec Kit (preset and
  extension included; Spec Kit's own scripts come from a one-time `specify init --here` explained in
  the zip's README) and importable from such a zip after validation and path checks.

### Key Entities

- **Project**: id, name, slug, description, status, creator, times, applied revision set.
- **Project folder**: the on-disk working copy (FR-002 layout).
- **Project spec**: number, short name, kind, stage, documents, produced artifacts.
- **File revision**: project, path, sha256, content, actor, command, conversation, time.
- **Conversation**: as in 014/017, now with a mandatory project and an optional current spec.
- **Distribution**: id, report, subscriptions (frequency, hour, period, recipient roles, PDF, link days),
  share-link policy; owned by a project.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From "Nuevo proyecto" to an applied dashboard over an existing table (one `fuente` and
  one direct `reporte` spec) in one session, with every file visible in the explorer (e2e).
- **SC-002**: The on-disk folder and the explorer tree match in 100% of e2e checks after create,
  edit, agent change, restore and import.
- **SC-003**: Every file change in the e2e suite appears in the history with the right actor and
  command (0 missing revisions).
- **SC-004**: The project page is usable at 375 px (axe: no serious violations; all actions reachable)
  and opens a 30-file project in under 1.5 s on the reference machine.
- **SC-005**: An upgraded installation keeps serving every existing dashboard unchanged, and project
  `principal` validates as the same workspace (same artifact definitions, apart from the `spec`
  paths rewritten by the import, and the same artifact files).

## Assumptions

- Projects are a super-user tool (same as the 014 assistant); other roles only see the dashboards.
- The editor uses a supporting code-editor library (CodeMirror 6) listed in the plan; no new stack
  component.
- History is stored in the database (no Git binary in the image); the folder is the working copy and
  the database is the record of changes. The installation backup must include `projects/`.
- The worker does not read `projects/`: it keeps running from applied workspace versions.
- Credentials never live in project files; sources stay in the encrypted catalogue (004).
