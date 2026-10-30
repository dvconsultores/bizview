# Quickstart — proving 044 works

Runnable checks, in the order a reviewer should meet them. Each one states what must be true
afterwards; none of them needs a browser open to start.

## Prerequisites

- A developer checkout with `.env` (the backend tests read `DATABASE_URL_BI` from it).
- `uv` and Node installed (see `CONTRIBUTING.md`).
- The reference project `cripto-simple-v2.zip` (report `cripto-panorama`, 483 CC0 logos).

## 1 · The contract accepts assets, and refuses bad ones

```bash
cd cli && uv run python -m bizview_cli validate ../pack/bizview-starter-pack/projects/panorama-cripto
```

- **Expected**: valid, with `assets/coins/` listed and no warnings.
- **Then** copy a text file to `assets/coins/FAKE.png` and re-run: the validator must refuse it
  naming the file and the sniffing rule.
- **Then** add a `.svg` containing `<script>`: refused, naming the element.
- **Then** add two files differing only by case: a **warning**, not an error.

## 2 · Images render on screen from the project alone

```bash
cd backend && uv run pytest tests/test_project_assets.py -q
cd ../frontend && npx vitest run tests/unit/layout-assets.test.tsx
```

- **Expected**: the tile shows the logo for a key with a file, and the initial circle for a key
  without one (`HYPE`), in both themes.

## 3 · The serving route cannot be tricked

```bash
cd backend && uv run pytest tests/test_project_assets_api.py -q
```

- **Expected**: `200` with an `ETag`; `304` on `If-None-Match`; `404` for a missing file; `422
  path_outside_project` for `../../otro/assets/x.png`; `422 path_unsafe` for `/etc/passwd`.

## 4 · The four components agree between screen and PDF

```bash
cd backend && uv run pytest tests/test_pdf_visual_components.py -q
```

- **Expected**: for a report with one gauge, one index, one share and one asset block, the figures
  read from the PDF equal the figures the renderer produced for the screen, and the embedded image
  for the asset block is the same file.
- **And** an unknown `kind` produces the named error card (026 FR-006), not a blank.

## 5 · A remote logo is fetched once and never again by a viewer

```bash
cd backend && uv run pytest tests/test_image_cache.py -q
```

- **Expected**: after a run, `IMAGE_CACHE_DIR` holds one file per distinct image; a second render
  performs **zero** outbound requests (transport spy); a failing URL leaves the row `failed`, is not
  retried within 24 h, and the data load still succeeds.

## 6 · End to end, in the browser

```bash
cd frontend && npx playwright test tests/e2e/projects.spec.ts
```

- **Expected**: import `cripto-simple-v2.zip` → validate → preview → apply → the dashboard shows
  logos, the gauge, the index bar and the share bar at 375 and 1280 px, in both themes, with no
  horizontal overflow and no axe violation of serious or critical impact.

## 7 · The gate that proves the authoring model did not regress

```bash
sh scripts/check_vocabulary.sh
```

- **Expected**: passes. This feature adds no AI surface and no authoring-in-product path, so the
  043 gate must stay green — if it fails, something in B–D smuggled a chat back in.

## What each check covers, against the spec

| Check | Spec item |
|---|---|
| 1 | FR-001, SC-002 |
| 2 | US1 acceptance 3–4, SC-001 |
| 3 | FR-006, contract §Serving |
| 4 | US2 acceptance 1–6, SC-001, SC-006 |
| 5 | US3, SC-003 |
| 6 | SC-001, SC-004 |
| 7 | constitution VIII/IX (no AI, no authoring in product) |
