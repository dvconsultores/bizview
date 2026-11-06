# What BizView does with your project

This document explains, in plain language, what happens when you upload the zip (import) and
what happens when you put it to work (apply). Nothing runs and nobody sees anything until you
apply.

## Import

1. BizView reads the zip in memory, strips the folder wrapping it when there is one, and rejects
   executables and scripts hidden inside an SVG.
2. It maps each file to the project format and lists the ones that are not as ignored: they are
   not stored and the project imports anyway.
3. It checks the budgets before writing anything: artifacts (400 files, 2 MB each, 20 MB total) and
   images (2 000 files, 300 KB each, 25 MB total). A refusal names the limit that was exceeded.
4. If the `slug` already exists the zip is a new revision of that project; if you want a
   separate project, ask for a copy and BizView creates it under another slug.
5. It validates the whole tree with the same validator the CLI runs: schemas, SQL statically,
   references between files, personal data against the spec and whether the spec is complete.
   Problems are shown file by file, with a proposed fix.
6. It saves the project as a draft: nothing runs and no user sees it.

## Apply

1. The draft is composed with the other applied projects into a new installation version and
   checked again; duplicate identifiers across projects are real errors.
2. Each integration is registered with the worker: the first run is a full load, then the schedule
   (`cron`) runs the incremental window (`:window_start`/`:window_end`) or a full reload per
   `incremental.mode`.
3. Datasets land in the `ds_<integration>.<dataset>` schema with `_run_id` and `_loaded_at`.
4. Each report becomes a dashboard at `/r/<id>`, visible to the roles in `access`, with filters,
   periods, comparison, PDF/CSV and share links.
5. The apply is an audit event and Roll back to the previous version undoes all of it.
6. What to look at first: Integrations for the last run, Dashboards for the new dashboard and
   Projects for pending problems.
