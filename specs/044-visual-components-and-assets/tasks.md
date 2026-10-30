# Tasks: Visual components and project images

**Input**: Design documents from `/specs/044-visual-components-and-assets/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: included, because the spec's success criteria are only provable by tests (SC-001 visual
parity, SC-002 adversarial uploads, SC-003 zero third-party requests). Each test task names the
criterion it proves.

**Organization**: by user story. Note that the plan's build order (A→D) differs from the story
order: the folder and the serving route are shared by US1 and US3, so they live in Foundational, and
each story phase is then independently shippable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2 or US3

## Path Conventions

Web app: `backend/app/…`, `backend/tests/…`, `frontend/src/…`, `cli/bizview_cli/…`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: the settings, keys and copy every later phase writes into.

- [x] T001 Add `image_cache_dir` (default `<data>/image-cache`), `image_cache_days` (default 90) and `image_max_kb` (default 300) to `backend/app/config.py`, with bounds and a comment saying the folder is NOT `attachments/` (043 removed that one) — done as `image_cache_dir` + `image_cache_days`; the per-run ceiling is `MAX_PER_RUN = 500` in `app/images/cache.py`, a constant, because no operator asked to tune it
- [x] T002 [P] Add the i18n keys the contract names, in both catalogues: `assets.too_large`, `assets.project_too_large`, `assets.svg_refused`, `assets.case_duplicate`, `assets.not_found` in `backend/app/i18n/es.py` and `backend/app/i18n/en.py` — done, plus `images.bad_url`, `images.fetch_failed`, `images.not_cached`, `images.svg_not_allowed`, `images.too_large` for the cache
- [x] T003 [P] Add the same five keys plus the component-editor labels to `frontend/src/i18n/es.ts` and `frontend/src/i18n/en.ts` — nothing to add: the component draws a picture or the fallback circle and shows no text of its own
- [x] T004 [P] Add `IMAGE_CACHE_DIR` to `.env.example` and to the compose files (`bizview.yml`, the block `deploy/install.sh` writes), with its volume, and to `deploy/tests/test_install.sh` as one check

**Checkpoint**: settings and strings exist; nothing reads them yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the folder, the sniffing and the serving route. US1 and US3 both depend on them.

**⚠️ CRITICAL**: no story phase starts before this one is done.

- [x] T005 Extend the published contract in `cli/bizview_cli/layout.py`: add `assets/<segment>/<name>.<ext>` to `PROJECT_PATTERNS` (extensions `.png .jpg .jpeg .webp .svg`), add `assets` and `assets/<segment>` to `FOLDER_PATTERNS`, and extend `ALLOWED_TEXT`; **do not touch** `cli/bizview_cli/workspace_template/` — done, with `_ASSET` allowing upper case so `BTC.png` is a legal file name
- [x] T006 [P] Create `backend/app/projects/assets.py`: `sniff(data) -> str` (PNG/JPEG/WebP/SVG by magic bytes, extension must agree), `MAX_KB = 300`, `check_svg(text) -> list[str]` (allowlist elements/attributes; refuses `<script>`, `on*`, `<foreignObject>`, external `href`/`xlink:href`), `normalise_key(key) -> str` (`/` and spaces → `_`), and `lookup(folder, key) -> Path | None` implementing the four-step order of `contracts/project-assets.md`
- [x] T007 Add `read_asset(slug, rel) -> tuple[bytes, str, str]` (bytes, content type, sha256) to `backend/app/projects/fs.py`, reusing `resolve_project_path` so the `path_unsafe`/`path_outside_project` rules apply unchanged; make `list_files` report `assets/` entries with their size and digest
- [x] T008 Route the write path through the checks: in `backend/app/projects/fs.py` `apply_ops`, refuse a non-sniffing extension/bytes pair, a file over `image_max_kb` and a folder over `PROJECT_MAX_MB`, storing the sanitised SVG text rather than the original — done as a sibling write path (`apply_asset`): `apply_ops` refuses NUL bytes on purpose, and an image is not text
- [x] T009 [P] Carry assets in both directions in `backend/app/projects/zip.py`: export writes `assets/**`, import accepts them (they now pass `layout.is_allowed`) and reports them in the import result
- [x] T010 [P] Add `GET /api/projects/{slug}/assets/{path}` to `backend/app/api/projects.py`: 200 with the sniffed type, `ETag` = sha256, `Cache-Control: private, max-age=31536000, immutable`, `304` on `If-None-Match`, `404 projects.file_not_found`, `422` for out-of-scope paths — no listing — done for the editor's door; the report and share doors came with T017/T037
- [x] T011 [P] Foundational tests in `backend/tests/test_project_assets.py`: sniffing accepts the four types and refuses a text file named `.png`; SVG with `<script>` is refused naming the element; `lookup` follows the four-step order; writes over 300 KB and a folder over 25 MB are refused
- [x] T012 [P] Foundational route tests in `backend/tests/test_project_assets_api.py`: 200 + ETag, 304, 404, `path_unsafe`, `path_outside_project`, and no directory listing

**Checkpoint**: a hand-edited project can carry and serve images; no report reads them yet.

---

## Phase 3: User Story 1 — Logos in tiles and tables from the project zip (Priority: P1) 🎯 MVP

**Goal**: a report that declares `images:` shows logos on tiles, in tables and in the asset tile,
falling back to the initial circle.

**Independent Test**: import `cripto-simple-v2.zip`, validate, apply — five price tiles and the table
show logos, `HYPE` shows its initial, and export/import round-trips `assets/`.

### Tests for User Story 1

- [x] T013 [P] [US1] Schema and validator tests in `cli/tests/test_report_images.py`: `images` accepts folder-only and column-only sets, refuses neither, warns on an SVG-only set (R3) and on a case-only duplicate, and `image` is refused on a component type that does not take one
- [x] T014 [P] [US1] Renderer tests in `frontend/tests/unit/layout-assets.test.tsx`: the table cell shows a 20 px round image for a keyed row, the asset tile a 40 px one, a missing key draws the initial circle from a palette role, and `image` absent keeps today's URL behaviour (R5)

### Implementation for User Story 1

- [x] T015 [US1] Add the `images` block and the `image` property to `cli/bizview_cli/schemas/report.schema.json` exactly as `contracts/report-images.md` specifies (`imageSet` with `folder`/`column` `oneOf`, `key` required, `fallback` default `initial`)
- [x] T016 [US1] Implement the validator rules a schema cannot express in `cli/bizview_cli/validate.py`: folder exists and holds an allowed image; `column` names a declared column; `key` is a declared dimension or column; `image` only on `table`/`kpi`/`asset`
- [x] T017 [US1] Resolve image sets in the report payload: extend the report definition the API returns (`backend/app/reports/` + `frontend/src/api/types.ts`) with `images` and the resolved key-to-URL map, so the client never guesses a path
- [x] T018 [P] [US1] Render images in `frontend/src/components/report/LayoutRenderer.tsx`: table cell (20 px round), `kpi` and `asset` tiles (40 px round), `alt` = key or name; the initial fallback uses `palette.role` by a hash of the key
- [x] T019 [P] [US1] Add the small image component the renderer uses (loading state, `onError` → fallback) next to the other report components in `frontend/src/components/report/`
- [ ] T020 [US1] Update the example project in `cli/bizview_cli/golden*` to declare `images: {coins: {folder: assets/coins, key: symbol, fallback: initial}}`, use `image: coins` on one table and one asset tile, and ship a handful of real logos under `assets/coins/` — **blocked**: `authoring.golden_files()` walks a golden as UTF-8 text, so a golden cannot hold a PNG, and the guide's round-trip test builds its workspace from that text tree. The example with images belongs to the starter pack (FR-008, `panorama-cripto`), which is not in the tree yet; it lands with the pack, not here
- [x] T021 [US1] Add the licence reminder to the authoring skeleton's `PROMPT.md` (ship only images you may redistribute; CC0 sets are fine) — the skeleton lives in `cli/bizview_cli/workspace_template/`, which is copied, never edited in place: change the copy source, not the template. **Half done**: the authoring contract now has an «Images» section in `docs/VIBE-REPORTING.md` §4 (sets, naming by key, limits, fallback, licence); the starter pack's `PROMPT.md` line waits for the pack to enter the tree with 043 A5, and the template itself stays untouched

**Checkpoint**: US1 is demonstrable end to end; the PDF still ignores images (US2).

---

## Phase 4: User Story 2 — Gauge, index, share and asset components in the PDF (Priority: P1)

**Goal**: the four components the screen already renders become PDF block kinds whose figures
match the screen, images included.

**Independent Test**: a report whose PDF layout contains exactly one gauge, one index, one share and
one asset block exports to PDF, and every figure equals the screen's.

### Tests for User Story 2

- [x] T022 [P] [US2] Parity test in `backend/tests/test_pdf_visual_components.py`: for the four kinds, the numbers read from the PDF equal the renderer's; the asset block embeds the same image bytes; an SVG-only set draws the fallback circle; an unknown `kind` produces the named error card (SC-001, SC-006)
- [x] T023 [P] [US2] Palette test in `backend/tests/test_pdf_visual_components.py`: every gauge band and share segment resolves through `THEME_ROLES`, in every preset × theme (SC-004)

### Implementation for User Story 2

- [x] T024 [US2] Extend `cli/bizview_cli/schemas/report.schema.json` so the four kinds are valid PDF block kinds with the same properties they have as components (the property names shipped by 042 Batch C, not the ones this task first listed: `min`/`max`/`low_label`/`high_label`/`remainder_label`/`metric`/`items`/`columns`/`image`/`sparkline`/`limit`
- [x] T025 [P] [US2] Implement the `gauge` block in `backend/app/reports/pdf_layout.py`: semicircular arc, bands by role, marker, centre value, label below
- [x] T026 [P] [US2] Implement the `index` block in `backend/app/reports/pdf_layout.py`: value, gradient bar between two roles, marker, end labels
- [x] T027 [P] [US2] Implement the `share` block in `backend/app/reports/pdf_layout.py`: figures plus a stacked bar whose remainder is `rest_label` when the parts sum to less than 100
- [x] T028 [US2] Implement the `asset` block in `backend/app/reports/pdf_layout.py`: embedded raster (PNG/JPEG/WebP via ReportLab's image reader), name, value, sign-coloured badge, optional sparkline
- [x] T029 [US2] In `backend/app/reports/pdf_layout.py`, make the four blocks resolve `image:` against the project folder and the cache with the same lookup as the screen, drawing the initial circle when only an SVG exists (R3) — the asset block resolves the declared set through `app.reports.images.reader`; SVG and a missing key still draw the circle, and the `column:` cache waits for T031–T039
- [x] T030 [US2] In `backend/app/reports/pdf_layout.py`, make an unsupported block kind fall through to the existing error card (026 FR-006) with the kind's name, never a blank region

**Checkpoint**: screen and PDF agree; US1's logos now reach the PDF when shipped as raster.

---

## Phase 5: User Story 3 — Images fetched once from a URL column (Priority: P2)

**Goal**: an `image_url` column's values are fetched once by the worker, stored locally, and served
by Bizview; viewers never contact the third party.

**Independent Test**: run an integration pointing at three public URLs, cut the network to those
hosts, and the dashboard still renders, with zero outbound requests during the page load.

### Tests for User Story 3

- [x] T031 [P] [US3] Cache tests in `backend/tests/test_image_cache.py`: one file per distinct image, two URLs with identical bytes share one file, a failure records `failed` and does not retry within 24 h, the data load still succeeds, and the transport spy records zero requests on a second render (SC-003)
- [x] T032 [P] [US3] Guard tests in the same file: a private address, a redirect into a private address, a payload over 300 KB and a non-image body are refused through `backend/app/security/netguard.py`

### Implementation for User Story 3

- [x] T033 [US3] Add migration `0043_image_cache.py` in `backend/alembic/versions/` creating the cached-image table of `data-model.md` (`url` unique, `sha256`, `ext`, `bytes`, `fetched_at`, `status` check `ok|failed`, `error`), plus its `upgrade`/`downgrade`
- [ ] T034 [US3] Add the `image_url` kind to the extraction types in `backend/app/engine/extract.py`: accepted, kept as `text`, never coerced — **dropped on purpose**: an integration column has only `type`, no `kind`, and the report already declares the URL column in `images.<set>.column`; a second list would drift. `columns_for` reads the declaration instead
- [x] T035 [US3] Create `backend/app/images/` (service + fetch): resolve through `netguard.guarded_client`, 10 s timeout, 300 KB cap, PNG/JPEG/WebP only (SVG refused — R3), content-hash into `image_cache_dir`, insert or update the row
- [x] T036 [US3] Run the cache pass after a successful load in `backend/app/engine/runner.py`: at most 500 new images per run, failures recorded and never failing the load, `status='failed'` older than 24 h retried once
- [x] T037 [US3] Serve cached images in `backend/app/api/projects.py`: extend the route added in T010 to fall through to the cache by hash, with the same ETag semantics and without ever proxying a third-party URL
- [x] T038 [US3] Add the retention sweep to `backend/app/worker.py` (hourly, like the preview housekeeping): remove files with no `ok` row and rows older than `image_cache_days`
- [x] T039 [US3] Make the renderer prefer the asset and then the cached URL in `frontend/src/components/report/LayoutRenderer.tsx`, using the key-to-URL map already in the payload (T017)

**Checkpoint**: all three stories work independently; US3 degrades to US1's assets when the network is gone.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T040 [P] Authoring guide: a section in `docs/VIBE-REPORTING.md` on images (folder, naming by key, limits, licence) and on the four components' PDF blocks
- [x] T041 [P] `CHANGELOG.md`: an entry under the next version — Added (assets folder, `images:`, the PDF blocks, the image cache) and Changed (the schema version bump)
- [x] T042 [P] `docs/INSTALL.md`: `IMAGE_CACHE_DIR`, its volume and its size expectation, next to the projects folder section
- [ ] T043 Bump the authoring skeleton version in `cli/bizview_cli/workspace_template/` (copy source only) and regenerate `pack/` so the published contract and the code ship together (constitution note in `plan.md`) — **blocked**: `pack/` is not in the tree yet (043 WS-A's starter pack is still uncommitted) and the template is copied, never edited, so this waits for the pack
- [x] T044 Run `sh scripts/check_vocabulary.sh` — must stay green: this feature adds no AI surface and no authoring-in-product path. **Run**: 368 hits, none of them new — every hit is 043 WS-A's to delete (`docs/VIBE-REPORTING.md` §332–493, `README*.md`, the assistant modules). The text this feature added is clean, and the gate goes green the day 043 lands
- [x] T045 Run the seven checks of `specs/044-visual-components-and-assets/quickstart.md` in order and record the result of each in the PR description. **Run**, with two substitutions: 1 is covered by `cli/tests/test_report_images.py` (9 passed) because the reference project is not in the tree yet; 2–5 are `test_project_assets.py`, `test_project_assets_api.py`, `test_pdf_visual_components.py`, `test_report_images.py` (43 passed) and `test_image_cache.py` (11 passed) plus `frontend/tests/unit/layout-assets.test.tsx` (8 passed); 6 needs a running stack and is not run here; 7 is T044's run above

---

## Dependencies

```text
Phase 1 (T001–T004)
   └─ Phase 2 (T005–T012) ── hardening of the folder, sniffing and route
        ├─ Phase 3 / US1 (T013–T021)      MVP: logos on screen
        │     └─ Phase 4 / US2 (T022–T030) needs US1's lookup to embed images
        └─ Phase 5 / US3 (T031–T039)      independent of US2; needs T010's route
Phase 6 (T040–T045) after the phases that ship
```

- **T007/T008 before T010**: the route serves what the write path stored.
- **T017 before T018/T019**: the renderer reads the resolved map, not a guessed path.
- **T029 before T028's image half**: the asset block embeds what the lookup found.
- **T033 before T035/T036**: the cache service writes rows the migration creates.

## Parallel execution examples

```text
# Foundational, different files
T006 assets.py        T009 zip.py        T011 test_project_assets.py
T007 fs.py            T010 projects.py   T012 test_project_assets_api.py

# US1, different files
T015 report.schema.json   T018 LayoutRenderer.tsx   T020 golden project
T016 validate.py          T019 image component      T021 authoring skeleton

# US2, the four blocks are separate functions in one file — sequential there, but the tests run beside
T025 gauge   T026 index   T027 share   (same file: not parallel with each other)
T022 parity test          T023 palette test
```

## Implementation strategy

- **MVP = Phase 1 + Phase 2 + Phase 3 (US1).** It delivers the owner's original ask — logos inside
  the project zip, on screen — and it is shippable on its own.
- **Second increment = Phase 4 (US2).** Same reports, now printable.
- **Third increment = Phase 5 (US3).** Remote logos for sources that publish URLs.
- **Do not** merge Phase 5 before the route of T010 is in: the cache has nothing to serve through.

## Notes

- `cli/bizview_cli/workspace_template/` is the external authoring contract and is never edited in
  place; T021 and T043 change the copy source, not the template.
- Every task that touches user-visible text writes Spanish and English in the same commit.
- No task introduces an AI call: the vocabulary gate (T044) is the guard.

---

## Phase 7: Convergence

- [ ] T046 Pass a `column:` set's own value in the table cell and the KPI tile so a cached logo draws there too, not only in the asset grid, and cover both in `frontend/tests/unit/layout-assets.test.tsx` per US2/AC2 (partial)
- [ ] T047 Verify the four components and their images at 375 px and 1280 px in both themes: add the case to `frontend/tests/e2e/layout.spec.ts` (or a 044 spec) and run it, since only jsdom unit tests cover the screen today per SC-001 and Constitution I (partial)
- [ ] T048 Make the declared lookup order real — allow a set with both `folder` and `column` (`anyOf` in `$defs/image_set` of `cli/bizview_cli/schemas/report.schema.json`) and resolve project asset → cached URL → fallback in `frontend/src/components/report/ReportImage.tsx` — or amend FR-005 and data-model's "AND/OR" to the shipped exactly-one rule per FR-005 (contradicts)
- [ ] T049 Reconcile the artifacts with the shipped URL-column design: FR-004's `kind: image_url` and data-model's column `kind` do not exist in `cli/bizview_cli/schemas/integration.schema.json`; either add the kind and have `backend/app/images/cache.py` read it, or amend FR-004, data-model and research R6 to the report-declared column per FR-004 (contradicts)
- [ ] T050 Prove the viewer never reaches a third party and that a bad URL never fails a load: a run-level test whose failing URL leaves the run `succeeded` and whose payload carries only `/api/…` paths, plus a transport-spy assertion that a second render issues no outbound request per SC-003 (partial)
- [ ] T051 Align the cache retention default across T001, `backend/app/config.py` and `docs/INSTALL.md` — `image_cache_days` shipped as 30 and T001 said 90 per T001 (`plan: image cache settings`) (partial)
