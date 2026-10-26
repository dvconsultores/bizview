# Implementation Plan: Project isolation (037)

**Feature**: `037-project-isolation` · [spec.md](./spec.md) · [tasks.md](./tasks.md)

## Technical context

| | |
|---|---|
| Backend | FastAPI + SQLAlchemy + Alembic (constitution V, unchanged) |
| Storage | `assistant_preview_request` gains `project_id` (backfilled, counted) |
| File layer | `app/projects/fs.py` becomes the only project → disk mapping |
| Frontend | React 19 + Tailwind; problems panel and workspace page only |
| Tests | pytest (DB + fake provider), vitest |

## Constitution check

- **III (projects are separate configuration)** — the reason of the feature: a project's page,
  validation payload and fixes speak only of that project's files. **PASS**.
- **VII (one product, many installations)** — nothing installation-specific is added; the composed
  validation keeps guarding the workspace, and the new `workspace_errors` count is per project.
  **PASS**.
- **VIII (AI optional and private)** — the whole fix works with the AI off: the problems panel and
  «Aplicar arreglo» are deterministic. No new data leaves the installation. **PASS**, no amendment.
- **IX (validation and apply per project)** — validation still composes (that is how a cross-project
  collision is found), but what a project *publishes* and *can fix* is its own. Apply keeps its
  composition guard. **PASS**.
- **IV (separated concerns)** — the changes stay in `projects/`, `assistant/` and `api/`; the frontend
  change is one component and one page.
- **V (fixed stack)** — no new dependency; Alembic owns the schema change.

Verdict: **PASS**, no amendment.

## Decisions

1. **One choke point for paths** (`fs.check_rel`): a first segment `projects` is refused with the new
   `path_outside_project` code, and so are absolute paths, `..` and symlinks leaving the root. This is
   enforced where every read, write, list, restore and delete already passes, so the rule cannot be
   forgotten by a new call site.
2. **`resolve_project_path(project_id, relative)`** is the sanctioned mapping, used by the fix
   endpoint, the tools, the apply, the export and the preview. It accepts an optional `db` to avoid a
   second session on hot paths and otherwise opens a short one.
3. **Validation publishes its own findings.** `validate_project` keeps composing the whole tree, then
   splits the issues: `errors`/`warnings` for this project (relative paths, own `fix_data`),
   `other_projects` (slug → count) and `workspace_errors` (count) for the rest. `valid` is "this
   project", `composed_valid` is "the composition"; readiness requires both. A foreign problem is
   never a fixable entry, so the panel cannot offer it.
4. **Apply is unchanged in behaviour** (it still refuses an invalid composition), but it logs the
   project root it composes from and names the owners of a dependant error, as it already did.
5. **Preview carries its project.** `assistant_preview_request.project_id` is backfilled from the
   session (unattributable queue rows are removed and counted), and the worker checks it against the
   session and resolves the folder from it — logging slug + absolute root. An empty or missing
   folder fails with a message that names both, so a mount problem is recognisable at a glance.
6. **The page owns its chat.** `/api/projects/<slug>/preview` uses the caller's newest conversation
   of that project, and `?chat=` is honoured only when the id is one of the page's conversations.
7. **A guard test protects the invariant**: queries on project-scoped models must filter by
   `project_id`/`session_id`, with an explicit, commented allowlist for the installation-wide call
   sites (the worker's queues, the cleanup job, the user's own conversation list, run profiles).

## Out of scope

- `assistant_run_profile` stays installation-wide (a contract of stages, limits and source names; no
  project file). Documented in the guide.
- The pending specs referenced by the incident prompt (`029`, `031`, `032`, `033`) do not exist in
  this tree, so there is no import row set to scope.

## Risks

- Splitting `valid` from `composed_valid` changes what the status bar says for a project that is
  itself fine while another one is broken. Mitigated by the readiness gate (it lists the blocking
  project) and by the apply's own refusal.
- The migration adds a NOT NULL column to a live table: it is backfilled from the session before the
  constraint is created, and a queue row that cannot be attributed is removed (and counted) rather
  than left behind as a work order nobody can run.
