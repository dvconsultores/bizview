# Feature Specification: Re-importing a project — the same project at a new revision

**Feature Branch**: `055-project-reimport`

**Created**: 2026-11-05

**Status**: Draft

**Input**: Owner, 2026-11-05, from production: "cada vez que corrijo algo y vuelvo a importar me crea un
proyecto nuevo `ventas-marca-2`, `-3`… y tengo que borrar el anterior a mano. Debe ser el mismo
proyecto con una revisión nueva, como Git."

**Builds on**: 020 (projects, folder layout, apply as a workspace version, per-file history),
037 (project isolation — ids of one project are validated against the others), 043 (the zip is the
only way in), 049 (two import allowances), 047 (themes carried by a project).
**Constitution**: no amendment. 037 stands (a project never writes another's files) and IX stands
(nothing is applied before it validates).

## Problem

Projects are authored outside Bizview and arrive as a zip; every correction is another zip of the same
project. The import path treats a slug that already exists as a collision: `suggest_slug` appends
`-2`, the new row is a *different* project, and the previous one keeps its folder, its integration and
its report with the same artifact ids. The result, on production:

- `ventas-marca`, `ventas-marca-2`, `ventas-marca-3` for one project;
- the ids of the three copies collide when the composition is validated (037 refuses the apply, or a
  stale dashboard keeps serving the old layout);
- shares, grants and dashboard access stay attached to the copy the operator forgot;
- the author has to delete the previous project by hand before each import, losing its history.

The expected behaviour is the one a Git user already knows: **the same project, a new revision of it**.

## Terms

- **Revision**: a numbered snapshot of the project's files (`1, 2, 3…`, one sequence per project).
  It is not the installation's workspace *version* (020/014): revisions belong to one project, versions
  to the installation.
- **Draft revision**: the newest revision, the state of the folder on disk. It may be newer than what
  is applied.
- **Applied revision**: the revision whose files produced the active version. The one before it stays
  reachable as *anterior*, for a revert.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The second zip replaces the project instead of duplicating it (Priority: P1) 🎯

The author fixes a report, zips the project folder again and imports it. Bizview recognises the same
`slug`, shows what changed, writes the new files over the project's draft revision, and leaves
everything else — id, shares, grants, dashboards, audit history, loaded data — where it was.

**Why this priority**: this is the reported defect. Until it works, every correction costs a manual
deletion and the installation accumulates duplicates.

**Independent Test**: import the same project twice; the second response says `mode: reimported`, the
project list still holds one row with that slug, the project's revision is 2 in `draft`, and the file
the zip changed appears in the diff.

**Acceptance Scenarios**:

1. **Given** a project imported from `ventas.zip`, **When** `ventas.zip` is imported again, **Then**
   there is still exactly one project with that slug, its newest revision is `2 · borrador`, and the
   response carries `mode: "reimported"`.
2. **Given** the same project applied (revision 1), **When** revision 2 is imported, **Then** the
   applied dashboard keeps serving revision 1's report until **Aplicar** is pressed.
3. **Given** a file present in revision 1 and absent from the new zip, **When** the re-import finishes,
   **Then** the file is gone from the project folder (and so is an image that the zip no longer
   carries) — a re-import replaces, it never merges.
4. **Given** a project with shares, dashboard grants and audit entries, **When** it is re-imported,
   **Then** all of them survive unchanged and the project keeps its id.
5. **Given** a zip whose `project.yaml` carries a new `name`, **When** it is re-imported, **Then** the
   project's name follows it; a zip that does not change the name leaves it as it is.
6. **Given** an author who wants a separate project (a variant), **When** the import is sent with
   `copy=true`, **Then** a new project is created with a unique slug and its own artifact ids, as a
   copy — never silently, only because it was asked for.

---

### User Story 2 - The author sees the diff before anything is written (Priority: P1)

Choosing a zip shows what the import will do: files added, changed and removed, specs added and
removed, artifact ids added and removed, and the two allowances of feature 049. Nothing is written
until the author confirms.

**Independent Test**: a dry run of the second zip returns the same diff the real import then applies,
and the folder is untouched by the dry run.

**Acceptance Scenarios**:

1. **Given** a chosen zip whose slug exists, **When** the import is previewed, **Then** the response
   lists the added, changed and removed paths, the specs and the ids, and a `revision` number of `0`
   because nothing was created.
2. **Given** the preview, **When** the author confirms, **Then** the revision is written with exactly
   the files the preview described.
3. **Given** a zip that changes nothing, **When** it is previewed, **Then** the diff is empty and the
   import still creates a revision only if the author confirms (the files are identical, so the apply
   is a no-op and says so).

---

### User Story 3 - Apply, revert and read the revision history (Priority: P1)

The project page shows which revision is the draft and which is applied (`rev 3 · aplicada`,
`rev 4 · borrador`). **Aplicar** composes the draft as today. **Volver a la revisión anterior**
restores the previous revision's files as a new draft and applies it. The history lists every
revision with its date, who imported it, its source and its counts, and each one can be downloaded as
a zip.

**Independent Test**: import v1, apply, import v2, apply, revert: the dashboard shows v1's layout
again and three audit entries (import, apply, revert) exist.

**Acceptance Scenarios**:

1. **Given** a draft revision newer than the applied one, **When** the project page loads, **Then**
   the chip reads `rev N · borrador` next to the applied revision, and **Aplicar** is offered.
2. **Given** an apply, **Then** the draft revision becomes `aplicada`, the previous applied one becomes
   `anterior`, and the audit records the apply with both revision numbers.
3. **Given** an applied project with a previous revision, **When** **Volver a la revisión anterior** is
   confirmed, **Then** the previous revision's files are written as a new draft revision which is then
   applied, the change is audited, and the dashboard serves the older layout again.
4. **Given** the revision history, **When** a row is downloaded, **Then** the zip has the same shape
   **Exportar** produces, with the files of that revision.
5. **Given** an editor save, **Then** a revision is recorded with source `editor` (one per save, never
   per keystroke) and the chip moves to it.

---

### User Story 4 - A conflict is a question, not a surprise (Priority: P2)

If the draft has editor changes the re-import would overwrite, the import asks before doing it. A zip
that collides with itself is rejected as today. An id that belongs to *another* project is reported as
today (037).

**Acceptance Scenarios**:

1. **Given** a draft whose files were saved in the editor since the last import, **When** a re-import is
   sent without the replace flag, **Then** the response asks for confirmation (`needs_confirmation`),
   writes nothing, and the page offers **Reemplazar borrador / Cancelar**.
2. **Given** the same re-import with the replace flag, **Then** the draft is replaced and the discarded
   editor revision stays in the history.
3. **Given** two spec folders with the same number inside one zip, **Then** the import is rejected with
   `422` and nothing is written, exactly as today.
4. **Given** an artifact id that another project owns, **Then** validation names that project on the
   next apply, as today (037).

---

### User Story 5 - Retention keeps the history bounded (Priority: P3)

A project that is re-imported every day must not grow without bound. The newest 20 revisions are kept
(`PROJECT_REVISIONS_KEEP`), and the applied and previous revisions are never pruned even when they
fall outside that window.

**Acceptance Scenarios**:

1. **Given** 22 imports, **When** the 22nd finishes, **Then** 20 revisions remain and the applied and
   previous ones are among them.
2. **Given** a project with the default ceiling, **When** the setting is lowered to 5, **Then** the
   next import prunes to 5 (keeping applied and previous), and nothing else changes.
3. **Given** a pruned revision, **When** the history is read, **Then** it is no longer listed and its
   download answers `404`.

---

### Edge Cases

- **A zip whose slug changes.** The zip is a different project: a new one is created and the previous
  one is untouched; the diff of the new project is its whole content.
- **Re-import of a `git` project.** Git projects are edited in their repository; a zip import for that
  slug is refused with the same `git_project` error the editor raises.
- **A project whose folder is missing** (volume lost): the re-import writes the folder back and the diff
  reports every file as added; shares and grants are untouched.
- **An image that the new zip drops.** Its bytes are on disk until removed and cannot be restored from
  history (044's decision stands: images are stored by hash, not by content). A revert that cannot
  bring an image back lists it and says so, instead of silently leaving a broken reference.
- **A very large diff.** The diff lists at most 500 paths per kind and says it was truncated; the counts
  are always exact.
- **Two re-imports racing.** The second one waits on the project lock and then applies its own diff; it
  never writes half of one and half of the other.
- **A slug that exists but is in the trash** (deleted, purge pending): it does not count as the project,
  so the import creates a new one — a deleted project is not re-imported into.

## Requirements *(mandatory)*

### Matching and modes
- **FR-001**: An import MUST match an existing project by `slug` — the zip's `project.yaml.slug`, or
  the slug derived from its name when the file does not carry one — compared case-sensitively after
  normalisation, and MUST treat a match as a re-import of that project. The `-2` suggestion MUST NOT be
  used unless the import explicitly asks for a copy.
- **FR-002**: The import MUST answer `mode: "created" | "reimported"`, and `copy=true` MUST force the
  copy path (new project, unique slug, its own artifact ids), never as a fallback of a collision.
- **FR-003**: A copy MUST get artifact ids that no other project owns: each id inside the copy is
  suffixed with the copy's number and every reference to it inside the copy's own files is repointed.

### Revisions
- **FR-004**: A project MUST keep a list of revisions numbered `1, 2, 3…` monotonically per project,
  each with `number`, `status` (`borrador` | `aplicada` | `anterior` | `reemplazada`), `source`
  (`importación` | `editor`), the actor, the time, the file map (`path → sha256`), the counts and the
  diff summary that produced it.
- **FR-005**: A re-import MUST write the zip's files as the project's new draft revision with a **full
  replacement** semantic: files and images present before and absent from the zip are removed; nothing
  is merged. The revision number MUST be the highest of the project plus one, and the previous draft
  (if it was never applied) MUST be marked `reemplazada` and kept in the history.
- **FR-006**: A re-import MUST keep the project's id, slug, shares, grants, dashboard access, audit
  history and the integration's loaded data. The name follows `project.yaml` when it changed. Datasets
  are never dropped by the import; a changed contract is handled by the existing apply rules.
- **FR-007**: A re-import MUST NOT apply anything: the previously applied revision keeps serving the
  dashboards until **Aplicar** is pressed.
- **FR-008**: A save from the editor (and an agent write through the same path) MUST create a revision
  with source `editor`, one per save.

### Diff
- **FR-009**: Before writing, the import MUST compute a diff — paths added / changed / removed, specs
  added / removed, artifact ids added / removed, and the two allowances of 049 — and MUST be able to
  return it without writing (`dry_run=true`).
- **FR-010**: The diff MUST be bounded (500 paths per kind, with a `truncated` flag) while its counts
  stay exact.

### Apply, revert and history
- **FR-011**: **Aplicar** MUST mark the draft revision `aplicada`, mark the previously applied one
  `anterior`, and audit the apply with both revision numbers.
- **FR-012**: **Volver a la revisión anterior** MUST write the `anterior` revision's files as a new
  draft revision (source `importación`, command `revert`) and apply it, with step-up, audited.
  Reverting to any other revision with content available MUST be possible through the same endpoint.
- **FR-013**: The revision history MUST be readable per project (newest first) with number, time, actor,
  source, file counts and diff summary, and each revision MUST be downloadable as a zip with the same
  shape as **Exportar**.

### Conflicts and refusals
- **FR-014**: When the current draft holds editor changes since the last import, the re-import MUST
  answer a confirmation request and write nothing unless `replace_draft=true` is sent.
- **FR-015**: A zip that collides with itself (two spec folders with the same number), an image over
  its allowance, an executable file, an over-limit project, or an unreadable archive MUST keep the
  current refusals: `422`, nothing left behind.
- **FR-016**: A re-import of a `git` project, and a project slug that is deleted, follow the existing
  rules (`git_project` / not a match).

### Retention, API and CLI
- **FR-017**: The newest `PROJECT_REVISIONS_KEEP` revisions MUST be kept (default 20), and the applied
  and previous revisions MUST never be pruned. Pruned revisions disappear from the history and answer
  `404` on download.
- **FR-018**: `POST /api/projects/import` MUST accept `copy`, `dry_run` and `replace_draft` and MUST
  answer `{project, mode, revision, diff, ignored, validation, budgets}`.
- **FR-019**: `bizview import <zip|folder>` MUST report the mode and the diff — computed against the
  project folder of the workspace it is run in — and `--dry-run` MUST print the diff without writing.

### Words and docs
- **FR-020**: Every label MUST exist in Spanish and English (022), a help topic **Reimportar un
  proyecto** MUST document the flow (033), `docs/IMPORT.md` §5 and §8 MUST carry the new collision
  table row, and the CHANGELOG MUST record the change under Unreleased.

## Key Entities

- **ProjectRevision**: project, number, status, source, actor, time, `files` (`path → sha256`), counts,
  diff summary.
- **Project**: gains `revision_seq`; its applied revision is the newest `aplicada`.
- **ImportDiff**: added / changed / removed paths, specs added / removed, ids added / removed, counts.

## Success Criteria *(mandatory)*

- **SC-001**: Importing the same zip twice leaves exactly one project, whose second revision is a
  draft; `mode` is `created` then `reimported`.
- **SC-002**: A re-import never changes the project's id, slug, shares or grants (asserted over a
  re-import that changes files, adds a spec and removes a file).
- **SC-003**: The applied dashboard serves the previous revision's report until the apply, and the new
  one afterwards, with no restart.
- **SC-004**: A revert restores the previous layout on the dashboard and is audited.
- **SC-005**: The dry run's diff equals the diff the real import reports for the same archive.
- **SC-006**: After 22 imports, exactly `PROJECT_REVISIONS_KEEP` revisions remain and the applied and
  previous ones are among them.
- **SC-007**: Copies keep working: `copy=true` creates `<slug>-<n>` whose ids collide with nothing, and
  the original project is untouched.

## Assumptions

- A project's revision is a snapshot of the *folder*: text files are recoverable from
  `project_file_revision` by `(path, sha256)`; images are stored by hash only (044), so an image that
  left the folder cannot be restored from the history — the revert reports it instead of lying.
- The workspace version (020) stays the installation's unit of apply; revisions never replace it and the
  worker keeps reading applied versions.
- Import stays the only way in: re-import is the same path with a different match rule.
- The CLI keeps never talking to a running Bizview: its diff compares the archive with the workspace's
  `projects/<slug>/` folder on disk.

## Decisiones tomadas (modo autónomo)

- [specify] decision — matching is by slug and by nothing else: a project is identified by its slug
  across the product (its folder, its ids, its audit) so the zip's slug is the only honest key. A zip
  whose slug changes is a different project, and the diff of the new one is its whole content.
- [specify] decision — the revision lives in its own table (`project_revision`) and stores a file map of
  hashes, not file contents: contents are already versioned per file by 020 (`project_file_revision`),
  and duplicating up to 20 full snapshots of a 45 MB project would be the wrong price for a list. A
  revision's zip resolves each path by `(path, sha256)`.
- [specify] decision — a revision is created on import, on an editor save and on a revert, and never by
  a read-only action, so the chip's meaning ("what the folder is") is always true.
- [specify] decision — the copy path renames artifact ids instead of duplicating them: a copy that
  cannot apply is the defect this feature fixes, and the brief's "as today" describes the intent (a
  distinct project), not the current behaviour (identical ids that collide at apply).
- [specify] decision — `PROJECT_REVISIONS_KEEP` is a deployment setting, read where it is used and
  reported with the history, not a row in `project_limits`: the brief names an environment setting, and
  giving it a UI would widen 049's screen for a number an operator changes once.
- [implement] decision — an archive without a `slug:` is identified by the slug its **name derives
  to**, and that derivation never appends a number (`project_service.plain_slug`): a suggestion that
  answers `ventas-marca-2` is exactly the duplicate this feature removes, so uniqueness is only
  applied when the project is truly new and `_copy_suffix` answers the copy.
- [implement] decision — the incoming `project.yaml` is rewritten with the project's own slug before
  the revision is planned or written (`reimport.pin_slug`). The export carries `slug: ""`, so without
  this every re-import of an exported zip showed the manifest as "changed" and the apply's schema
  refused it (`slug: '' does not match …`); the same helper serves the create path, which used to do
  it inline after `create`.
