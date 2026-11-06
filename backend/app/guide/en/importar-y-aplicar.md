# What happens on import and apply

## What it is for

It explains, in plain language, what BizView does when you upload the zip (import) and when you put it to work (apply). Nothing runs and nobody sees anything until you apply.

## Who can use it

Only the Superuser to import and apply. After applying, every role in `access` sees the dashboard.

## How to

### Import

1. BizView reads the zip in memory, strips the folder wrapping it when there is one, and rejects
   executables and scripts hidden inside an SVG.
2. It maps each file to the project format and lists the ones that are not as ignored: they are
   not stored and the project imports anyway.

### Apply

1. The draft is composed with the other applied projects into a new installation version and
   checked again; duplicate identifiers across projects are real errors.
2. Each integration is registered with the worker: the first run is a full load, then the schedule
   (`cron`) runs the incremental window (`:window_start`/`:window_end`) or a full reload per
   `incremental.mode`.

## Options

- Importing a project that already exists proposes a revision, not a duplicate.
- The same text ships inside every pack, in `QUE-HACE-BIZVIEW.md` and `WHAT-BIZVIEW-DOES.md`.

## Related

- Import a project
- Apply a project
- Re-import changes
