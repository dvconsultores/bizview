# Phase 1 — Data model

Three entities, plus the one table the URL cache needs. Nothing here changes an existing table:
assets are files, `images:` is report content, and only the cache adds a row type.

## Asset (file, no table)

A binary or SVG file that belongs to one project and one project version.

| Field | Where | Rules |
|---|---|---|
| path | `PROJECTS_DIR/<slug>/assets/…` | must match the `assets/` pattern: `assets/<segment>/<name>.<ext>`; no `..`, no absolute, no symlink (the existing `fs.resolve_project_path` rules apply unchanged) |
| bytes | the same file | ≤ 300 KB each; the whole `assets/` folder ≤ 25 MB (the existing `PROJECT_MAX_MB` stays the outer cap) |
| type | sniffed on write | PNG, JPEG, WebP or SVG; the extension must agree with the bytes |
| svg content | the same file | allowlisted elements/attributes, stored already sanitised |
| revision | `project_file_revision` | one row per write, `op='create'|'update'|'delete'`, `actor_kind` as today; assets are versioned exactly like text files |

**Validation rules** (all enforced at the write boundary, so import and the editor behave alike):

- extension ∈ {`.png`, `.jpg`, `.jpeg`, `.webp`, `.svg`} and the bytes agree with it;
- SVG passes the allowlist sanitiser; a refusal names the offending element;
- the cumulative size of `assets/` stays under the cap, checked before the write is committed;
- a file that differs only by case from an existing one is accepted but raises a validation **warning**.

## Image set (declaration inside `report.yaml`)

Not a row: a key in the report document.

```yaml
images:
  coins:
    folder: assets/coins     # AND/OR
    column: l.logo_url       # the cached-URL source
    key: symbol              # dimension or dataset column that names the file
    fallback: initial        # initial | none
```

| Field | Required | Rules |
|---|---|---|
| folder | `folder` and/or `column` | must exist in the project and start with `assets/` |
| column | one of `folder`/`column` | must be a declared column of a dataset the report uses |
| key | yes | a declared dimension, or a column of a dataset the report uses |
| fallback | no (default `initial`) | `initial` draws the circle; `none` leaves the space empty |

Lookup order at render time: **project asset by key → cached URL → fallback** (R1/R4). Keys are
normalised for lookup (`/` and spaces → `_`), and the match is case-insensitive on the file name
with the exact case winning (R2's duplicate rule).

## Cached image (row + file)

| Column | Type | Notes |
|---|---|---|
| url | text | unique per installation; the fetch key |
| sha256 | text | content hash; also the file name |
| ext | text | png/jpg/webp (SVG is refused from a URL: it would need sanitising per fetch and the PDF cannot embed it — R3) |
| bytes | integer | size on disk, ≤ 300 KB |
| fetched_at | timestamptz | last attempt |
| status | text | `ok` or `failed` (check constraint) |
| error | text null | the redacted reason, for the run log |

File: `IMAGE_CACHE_DIR/<sha256>.<ext>`. Two URLs with identical bytes share one file; a sweep removes
files with no `status='ok'` row and rows older than the retention window.

**State transitions**: `missing → ok` on a first successful fetch; `missing → failed` on an error;
`failed → ok` only after the 24 h retry window; `ok` never re-fetches unless the URL's row is older
than the retention window or the file is gone.

## Relationships

- One **project** has 0..n **assets** (files) and 0..n **reports** that may declare 0..n **image sets**.
- One **image set** resolves to one **project asset** per row key, or to one **cached image** per URL.
- A **cached image** belongs to the installation, not to a project: two projects using the same logo
  URL share the file. Deleting a project never deletes a cached image; the sweep does.

## What deliberately does not exist

- **No table for assets.** They are project files, and a table would duplicate what the folder and
  `project_file_revision` already say.
- **No per-project cache.** Sharing by content hash is the point; per-project caches would multiply
  the same 483 logos per project.
- **No image column type in the database, and no `kind: image_url` on the column either.** The
  report's `images.<set>.column` is the declaration: the worker reads it, and the column stays `text`
  in the dataset, which keeps the engine's type system unchanged (R6).
