# Data model — 049 import limits and assets

Two persisted concepts (one table, one pair of settings) and three transient ones shared by the
backend, the CLI and the browser.

---

## ProjectLimits (persisted, singleton)

`project_limits` — one row, `id = 1`, mirroring `appearance_settings` (030/047). Every allowance column
is **nullable**: NULL means "inherit the deployment default from `Settings`", so an operator who set an
environment variable keeps it, and a super user who edits the form stores an explicit number.

| Column | Type | NULL means | Default when NULL |
|---|---|---|---|
| `id` | `smallint` PK, `CHECK (id = 1)` | — | 1 |
| `artifact_max_files` | `integer` | inherit | `PROJECT_MAX_FILES` = 400 |
| `artifact_max_kb` | `integer` | inherit | `PROJECT_MAX_KB` = 2048 |
| `artifact_max_mb` | `integer` | inherit | `PROJECT_MAX_MB` = 20 |
| `asset_max_files` | `integer` | inherit | `PROJECT_ASSET_MAX_FILES` = 2000 |
| `asset_max_kb` | `integer` | inherit | `PROJECT_ASSET_MAX_KB` = 300 |
| `asset_max_mb` | `integer` | inherit | `PROJECT_ASSET_MAX_MB` = 25 |
| `updated_at` | `timestamptz` | — | `now()` |
| `updated_by` | `bigint` FK → `app_user.id` | nobody yet | NULL |

**Check constraints**: each column `> 0` when not null; `artifact_max_kb <= artifact_max_mb * 1024` and
`asset_max_kb <= asset_max_mb * 1024` (a per-file limit larger than the total is a configuration
mistake, not a preference). API validation mirrors them so the user reads a field error, not a 500.

**Audit**: `project_limits_changed`, detail `{before: {…}, after: {…}}` — the six numbers only, never a
path or an upload.

**Migration**: `0047_project_limits`, down_revision `0046_no_default_dashboards`. It creates the table and
inserts the single all-NULL row, so `GET` works before anyone edits. Downgrade drops the table.

---

## Budget (transient, shared)

One allowance, identified by name. Produced by the effective-limits resolution; consumed by the tally.

| Field | Type | Meaning |
|---|---|---|
| `name` | `"artifacts" \| "assets"` | which class of file this budget pays for |
| `max_files` | int | how many files of this class a project may carry |
| `max_kb` | int | the largest single file of this class |
| `max_mb` | int | the total of this class |
| `label` | str | the folders, as the author sees them: `specs/, integrations/, reports/…` / `assets/` |

**Validation**: `max_files ≥ 1`, `max_kb ≥ 1`, `max_mb ≥ 1`, `max_kb ≤ max_mb * 1024`.

**Where it comes from**: `backend/app/projects/budgets.py::effective(db)` (DB row over `Settings`), and
`cli/bizview_cli/budgets.py::defaults()` for the CLI, which has no database. The CLI's numbers are the
deployment defaults by definition; when the server publishes its effective limits, they travel in the
`GET /api/projects/limits` response so the browser never guesses.

---

## Tally (transient, shared)

What a project (a folder, a zip, or an archive index) actually costs. One per budget, plus the ignored
list.

| Field | Type | Meaning |
|---|---|---|
| `budget` | `Budget` | what is being measured against |
| `files` | int | files of this class found |
| `bytes` | int | their total, uncompressed |
| `largest` | `(path, bytes) \| None` | the biggest single file, for a size refusal |
| `fatal` | `(path, reason) \| None` | a disallowed-content refusal (R5), which fails the import |

**Derived**: `over_files(budget)`, `over_bytes(budget)`, `over_file(budget)` → an `OverLimit` with the
message the user reads, or `None`. Artifacts are checked first: when both budgets are exceeded, the
artifact message wins, because artifacts are what the project *is* (spec, Edge Cases).

**IgnoredFile**: a path no budget owns and that is not disallowed — reported as text, never written.

**Rules, in order** (each refusal names its budget, the measured value and the limit — FR-003):

1. A path with an unsafe shape (`..`, absolute, drive letter, backslash, NUL) → refused (031, unchanged).
2. A path with disallowed content (extension or magic bytes, R5) → refused, whichever budget owns it.
3. A path whose `budget_of()` is `None` → ignored.
4. A path over its budget's `max_kb` → refused, naming the file.
5. `files > max_files` for a budget → refused, naming the folder and the count.
6. `bytes > max_mb` for a budget → refused, naming the folder and the total.

---

## State transitions of an import

```text
chosen (browser)
   └─ index read ──▶ tallied
        ├─ over a limit ──▶ refused in the browser; nothing uploaded
        └─ within ──▶ uploaded ──▶ server tallies the real bytes
                       ├─ over a limit ──▶ 413/422, nothing written, nothing half-imported
                       ├─ disallowed content ──▶ 422 naming the path
                       └─ within ──▶ project created ──▶ files written ──▶ validated ──▶ applied?
```

**Invariant**: no row, no folder and no file survives a refusal. `import_zip` already deletes the project
and its folder inside its `except`; the new refusals happen **before** the first write, so that path is
only a backstop.
