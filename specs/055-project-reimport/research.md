# Research — 055-project-reimport

What exists, what was measured, and the decisions the implementation follows.

## R1. What the import does today with a taken slug

`app/projects/zip.py:import_zip` builds the file map from the archive, then:

```python
wanted = slug or meta.get("slug")
if not (isinstance(wanted, str) and layout.ID_RE.match(wanted)):
    wanted = project_service.suggest_slug(db, title)
try:
    project = project_service.create(db, actor, title, wanted, "", ip)
except ApiError as e:
    if e.code != "slug_taken":
        raise
    project = project_service.create(db, actor, title,
                                     project_service.suggest_slug(db, wanted), "", ip)
```

`suggest_slug` returns the base when it is free and `base-2`, `base-3`… otherwise. So the second zip
of a project creates a **second project** whose folder holds the same `integrations/<id>/` and
`reports/<id>/` as the first. Composition (`workspace.service.apply_tree` → `bizview_cli.validate`)
then sees two projects owning the same artifact id, which 037 refuses — or, worse, an installation
where both were applied at different times keeps a stale dashboard.

**Confirmed**: the duplicate is created by `create()`, not by the archive being different. Nothing
about the zip is compared with what the installation already has.

## R2. What a snapshot needs, and what it must not copy

A revision has to answer three questions: *what files did it hold*, *can I download it*, *can I
restore it*. Three sources already hold that information:

| Need | Already stored | Where |
| --- | --- | --- |
| text content at a moment | `project_file_revision.content` + `sha256`, one row per change | 020 |
| image content | **only the hash** (`content` is NULL on purpose) | 020 (`history.record_asset`) |
| what the active version holds | `workspace_version.projects[slug].files` (path → sha) | 014/020 |

So a revision is a **file map of hashes**: `{path: sha256}`. Download resolves each text path with

```sql
SELECT content FROM project_file_revision
 WHERE project_id = :p AND path = :path AND sha256 = :sha
```

which is exact and immutable (a hash match cannot be a different file). Images cannot be resolved that
way — the bytes were never kept — so a download takes an image's bytes from disk **only when the
current file still has that hash**, and reports the rest as unavailable. This is the same limit 020
already documents for restoring an image (`asset_not_restorable`), now said out loud instead of
silently skipped.

Duplicating contents per revision was rejected: 20 revisions × a 45 MB project is 900 MB of copies of
data the product already keeps per change.

## R3. How the apply knows what it applied

`app/projects/apply.py:apply_project` composes, validates and activates a version, and audits
`project_applied` with the file list. The project row carries `first_applied_at`, and
`specs.applied_files()` reads `version.projects[slug].files` for the status. Nothing records "which
snapshot" — that is exactly what the new revision row adds, so the chip can say
`rev 3 · aplicada` without re-deriving it from hashes.

## R4. Where an editor save happens

`PUT /api/projects/{slug}/file` and `POST /{slug}/ops` call `fs.apply_ops(..., _user(actor, "edit"))`,
which records **one `project_file_revision` per file** under a shared `group_id` — one group per save.
A "revision per save" is therefore `group_id`-shaped: the snapshot is taken **after** the ops, from the
folder, and stored with source `editor`. The agent's writes go through the same `apply_ops`, so they
produce an editor revision too; the brief's vocabulary has two sources and this is the honest bucket
for "a person or the agent changed files between two imports".

## R5. What the CLI can see

`cli/bizview_cli/importer.py` measures a folder or a zip with the shared `budgets.tally` and never
talks to a server (`docs/IMPORT.md`: "The CLI never talks to a running Bizview"). The diff of a
re-import is therefore computed **against the workspace folder** the command is run in
(`projects/<slug>/` when the v2 layout is present, the folder itself otherwise). That keeps the CLI
useful in a Git checkout where the previous revision is on disk, and costs nothing when it is not:
with no folder the mode is `created` and the whole archive is "added".

## R6. Refusals that must not move

The codes of 043/049 are user-visible and tested: `zip_disallowed`, `zip_too_large`,
`artifacts_over_files|bytes`, `assets_over_files|bytes`, `*_file_too_large`, `spec_number_duplicate`,
`git_project`. A re-import validates its inputs **before** it writes, exactly like the import it
generalises: the archive is read and tallied first (`_entries` + `shared_budgets.tally`), the two spec
numbers are checked by `apply_ops` (which rolls the folder back), and the `git` refusal is
`service.ensure_editable`, already used by the editor.

## R7. Concurrency

`fs.apply_ops` and `fs.apply_asset` each take `pg_advisory_xact_lock(hashtextextended(lock_key(
"project", id)))` in their own transaction. A re-import does several of those calls in a row; the
project revision is written **after** the last write, so two racing imports produce two revisions in
order (the second one's diff is computed against the first one's result) and never a mixed folder.
The revision number comes from `project.revision_seq` updated under the same advisory lock's
transaction (`fs.apply_ops` bumps `last_activity_at` there), so no number is reused.

## R8. Existing projects need revision 1

An installation upgrading to this release has projects whose files predate the table. A data migration
cannot read `PROJECTS_DIR` (the folder may be on another volume at migrate time, and a migration that
touches the file system is a migration that can fail halfway). So the baseline is created **on read**:
`revisions.ensure_baseline(db, project)` writes revision 1 from the current folder when the project has
none, marking it `aplicada` when `specs.applied_files()` is not None and `borrador` otherwise. Same
shape as `importer.ensure_principal`, which the product already runs at start and retries.

## R9. Copy ids

A copy must be applicable, so its artifact ids must not collide with the original's (037). The ids are
the folder names under `integrations/`, `reports/`, `distributions/` and `themes/`, all matching
`layout.ID_RE`. The copy suffixes each with the copy's number (`panorama-cripto` → `panorama-cripto-2`)
and repoints the references it can see in its own files: a report's `uses` alias values
(`<integration>.<dataset>`), a distribution's `report`, and a report's `theme:` block (the helper
`_repoint_reports` already exists for the last one). A trimmed id keeps the 50-character ceiling by
shortening the base.
