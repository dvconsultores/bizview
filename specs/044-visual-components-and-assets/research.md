# Phase 0 — Research

Five decisions, each stated with the alternatives that were rejected. Facts were checked against
the tree (`4b10ae7` + the 042 Batch C commits), not assumed.

## R1 — Where images live and how they are served

**Decision**: files under `PROJECTS_DIR/<slug>/assets/…`, served by a new route
`GET /api/projects/{slug}/assets/{path}` with `ETag` = SHA-256 of the bytes and
`Cache-Control: private, max-age=31536000, immutable` (the content is versioned with the project).

**Rationale**: the spec says the author ships logos inside the project zip, and everything else in a
project already lives in that folder and travels with the version (`workspace_version.projects`).
Storing images in PostgreSQL would make every apply copy megabytes of bytes through the version row;
storing them outside the folder would break "the zip is the project".

**Alternatives considered**:
- *Bytes in the database*: versioning for free, but the version row already carries the file map and
  a 25 MB project would bloat every apply and every backup.
- *Serving from the preview schema*: previews already drop schemas on apply; images must survive.
- *No route, inline base64 in the JSON payload*: 483 logos × 300 KB in one report payload is not a
  dashboard, it is a download.

**Share links and TV mode**: both render in the same origin as the app, so the same route serves
them; the route checks the same project scope as `GET /{slug}/file` and refuses `path_unsafe` /
`path_outside_project` identically. There is no directory listing.

## R2 — SVG: sanitise and serve, or refuse?

**Decision**: accept PNG, JPEG, WebP and SVG; sanitise SVG with an **allowlist** parser (elements,
attributes, no `<script>`, no `on*`, no external `href`/`xlink:href`, no `<foreignObject>`, no
external fonts) before storing, and store the sanitised text — never the original.

**Rationale**: logos are overwhelmingly SVG, and refusing them would push authors to rasterise by
hand and lose sharpness on a phone. Sanitising at write time (not at read time) means the bytes on
disk are already safe, so the PDF and the cache can trust them.

**Alternatives considered**:
- *Refuse SVG*: simplest, but the reference project's CC0 coin set mixes SVG and PNG.
- *Serve SVG in `<img>` only* (no inline `object`/`iframe`): `<img>` already blocks scripts, but the
  PDF path also has to read the file, so the file itself must be clean anyway.
- *Sanitise on read*: repeated cost per request and two code paths to keep equal.

**Content sniffing** applies to all four types: a `.png` whose first bytes are not a PNG is refused
with the existing `path_not_allowed`-style error, because a mislabelled binary is how a decompression
bomb or a polyglot gets in.

## R3 — SVG in the PDF without a new dependency

**Decision**: **PDF embeds raster only.** A project image usable in PDF must be PNG, JPEG or WebP
(the last converted to PNG bytes by the existing ReportLab imaging path); an SVG-only set renders on
screen and, in the PDF, falls back to the same initial-circle as a missing file. `bizview validate`
emits a **warning** — not an error — naming the set and saying the PDF will show the fallback.

**Rationale**: rasterising SVG server-side needs `svglib`/`cairosvg` (a new stack component under
constitution V) or a headless browser (worse). A warning keeps the author in control: ship a PNG
sibling for print fidelity, keep the SVG for the screen.

**Alternatives considered**:
- *Add `svglib`*: the cleanest visual result, but V is explicit and the plan should not be the place
  it bends.
- *Rasterise once at import and store both*: doubles storage for every icon and needs the same
  library.
- *Refuse SVG entirely* (R2's rejected option): loses the screen quality the feature is for.

## R4 — The URL cache: directory, settings, failures

**Decision**: a dedicated directory, `IMAGE_CACHE_DIR` (default `<data>/image-cache`, sibling of
`projects/`), never `attachments/`. One row per URL in a small table with `(url, sha256, ext,
fetched_at, status, bytes)`; the file is `IMAGE_CACHE_DIR/<sha256>.<ext>`. Fetches go through
`backend/app/security/netguard.py` with the same policy the sources use, 10 s timeout, 300 KB cap,
500 new images per run. A failed URL records `status='failed'` and is not retried for 24 h; a
successful load never fails because an image failed. A sweep drops files no row references and rows
older than the retention window (default 90 days).

**Rationale**: `attachments/` disappears in 043 WS-A; reusing the name would resurrect a concept the
product no longer has and the gate (`asistente|speckit-|run_contract|token_budget`) would not catch
it, so the naming is a design decision, not a leftover. Hashing by content means two rows pointing at
the same logo share one file.

**Alternatives considered**:
- *Cache inside the project folder*: the cache is derived data, not project content; it must not
  travel in the zip or count against the 25 MB.
- *Fetch at render time with a short TTL*: violates SC-003 (zero viewer requests to third parties)
  and puts a network in the report path.
- *Store images in the report cache*: the report cache is keyed by selection and expires; logos
  outlive both.

## R5 — `image:` versus the asset tile's positional `columns`

**Decision**: `image: <set>` is a **new, named** property on the components that take one (`asset`,
`kpi`, `table`); the asset tile's existing positional `columns: [imagen, título, subtítulo, valor,
delta]` keeps working, where `imagen` names a **column** whose value is a key into the set declared by
`image:`. Neither replaces the other: `image:` says *where the pictures come from*, `columns[0]` says
*which column carries the key*.

**Rationale**: `report.schema.json` already documents the positional convention for `asset` (line
961), and 042 Batch C shipped the renderer for it. Replacing it would break every report written
since; adding a second, competing way to name an image would be worse. Splitting the two concerns is
the only option that keeps both.

**Alternatives considered**:
- *`image:` as a bare string set name replacing `columns[0]`*: breaks existing reports and the
  example in the golden project.
- *A second positional slot for the set*: positional lists are already the hardest part of this
  schema to read; a named key is clearer.

## R6 — Who says which column holds image addresses

**Decision**: the **report** says it, in `images: {<set>: {column: <alias>.<column>}}`; there is no
`kind: image_url` on the integration column. After a load, `app/images/cache.py` collects the columns
the applied reports name for that integration (`columns_for`), fetches the unknown values, and
rewrites the successful ones to `<sha256>.<ext>`. The payload hands the client a report-scoped
`cached_url` prefix, and the two doors that already serve the report (`/api/reports/<id>/images/<name>`
and `/api/shared/<token>/images/<name>`) serve the bytes.

**Rationale**: an integration column in `integration.schema.json` carries a stored `type` and no
`kind`; adding one would mean a second declaration of the same fact — the schema would hold it, the
report would also hold it, and the two would drift. The report is where the picture is *used*, so it
is where "this column holds addresses" belongs, and the validator can check the alias against
`uses` while it is already checking `key` against the dimensions. It also keeps the engine's type
system untouched, which FR-004's original wording would have bent.

**Alternatives considered**:
- *`kind: image_url` on the column (the original plan)*: needs a schema change in the authoring
  contract, a validator rule pairing it with `text`, and the worker still has to find which datasets
  of which reports are affected — the report already answers that.
- *Fetch at render time*: rejected in R4 (a network in the report path).
- *Store the address in the row and let the browser fetch it*: that is what the asset tile did until
  now, and it is exactly the third-party request SC-003 forbids.
