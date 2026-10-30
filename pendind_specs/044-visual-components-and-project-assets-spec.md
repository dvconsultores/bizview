# Feature Specification: Visual components (asset, gauge, index, share) and project images

**Product**: Bizview · **Feature Branch**: `044-visual-components-assets`

**Created**: 2026-10-29

**Status**: Draft

**Input**: Owner, 2026-10-29: "Enable logos and gauges in dashboards; I can add all logos inside the
project zip." Reports need tiles with a logo (coins, products, vendors), a semicircular gauge
(fear & greed), a two-ended index bar (Bitcoin ↔ Altcoin season) and a share bar (dominance),
on screen and in the PDF. Images come, in this order, from the project's own `assets/` folder,
from a cached URL column, or from a generated fallback.

**Builds on**: 026 (declarative layouts), 031/043 (import as the front door), 030 (palette roles).
**Reference project**: `cripto-simple-v2.zip` (report `cripto-panorama`, `assets/coins/<SYMBOL>.png`,
483 CC0 logos).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Logos in tiles and tables from the project zip (Priority: P1) 🎯

The author ships `assets/coins/BTC.png …` inside the project and declares an image set keyed by
a column. Price tiles and the coins table show the logo next to the symbol; the PDF too.

**Independent Test**: import `cripto-simple-v2.zip`, apply; the five price tiles and the table rows
show logos; a symbol without a file (HYPE) shows a circle with its initial; the PDF embeds the
same images.

**Acceptance Scenarios**:

1. **Given** a project zip with `assets/**` files, **When** imported, **Then** files with
   extensions `.png .svg .webp .jpg` under `assets/` are accepted (≤ 300 KB each, ≤ 25 MB total,
   content-sniffed: a `.png` must be a PNG; SVG is sanitized — no scripts, no external refs), stored
   with the project version, and served at `/api/projects/<slug>/assets/<path>` with cache headers.
   Any other file type or location is still rejected with the existing message.
2. **Given** `report.yaml` declares

   ```yaml
   images:
     coins: {folder: assets/coins, key: symbol, fallback: initial}
   ```

   **Then** validation checks the folder exists in the project and `key` is a declared dimension
   (or a dataset column of a used alias); a component may reference `image: coins`.
3. **Given** a row whose key is `BTC`, **Then** the image is `assets/coins/BTC.png` (case-insensitive
   match on the file name, `.svg`/`.webp`/`.jpg` also tried); if none exists, the `fallback`
   applies: `initial` (circle with the first letter, colour from the palette by hash of the key)
   or `none`.
4. **Given** the table component has `image: coins`, **Then** the image appears in the key column's
   cell (20 px, round); given a `kpi`/`asset` tile, 40 px round beside the label.

---

### User Story 2 - Cached images from a URL column (Priority: P2)

An integration column of kind `image_url` is fetched by the worker once per new value, stored
locally and served by Bizview; viewers never call the third party; the PDF embeds the cached file.

**Acceptance Scenarios**:

1. **Given** a dataset column `logo_url: {type: text, kind: image_url}`, **When** the integration
   runs, **Then** the worker downloads new/changed URLs (same SSRF rules as sources: public hosts
   only; ≤ 300 KB; PNG/SVG/WEBP/JPG; timeout 10 s; max 500 new images per run), stores them under
   `attachments/images/<sha256>.<ext>`, records `(url, hash, fetched_at, status)` and never blocks
   the data load on image failures.
2. **Given** an image set `images: {coins: {column: l.logo_url, key: symbol}}`, **Then** the
   lookup order is project asset by key → cached URL → fallback.
3. **Given** a URL that fails, **Then** the row shows the fallback and the run log lists the URL
   (no retries more often than once a day).

---

### User Story 3 - Gauge, index and share components (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a `gauge` component bound to a metric (`min`, `max`, `bands: [{to: 25, role:
   negative}, {to: 45, role: series3}, {to: 55, role: neutral}, {to: 75, role: series4}, {to: 100,
   role: positive}]`, optional `label_metric`), **Then** it renders a semicircular arc with the bands,
   a needle/marker at the value, the value large in the centre and the label text below (e.g. 40 ·
   Neutral).
2. **Given** an `index` component (`metric`, `min`, `max`, `left_label`, `right_label`, optional
   `label_metric`), **Then** it renders the value (`43 /100`), a horizontal gradient bar from the
   left role to the right role with a marker, and the two end labels.
3. **Given** a `share` component (`parts: [{metric: btc_dominance, label: BTC}, {metric:
   eth_dominance, label: ETH}]`, optional `rest_label: Otros`), **Then** it renders the figures and
   a stacked bar whose remainder is `Otros` when the parts sum to < 100.
4. **Given** an `asset` component (`metric` for the big figure, `change_metric` for the badge,
   `image`, `name_dimension` optional, `sparkline`), **Then** it renders logo + name/symbol, the
   value display-size, a filled ▲/▼ badge coloured by sign, and the optional sparkline.
5. **Given** any of the four in `layout.pdf` (`kind: gauge|index|share|asset` blocks), **Then**
   ReportLab draws the equivalent vector shapes and embedded images; figures identical to the
   screen.
6. **Given** a component type the renderer lacks (older installation), **Then** the existing
   error card appears (026 FR-006), never a blank.

### Edge Cases

- Keys with characters not allowed in file names (`/`, spaces): normalised to `_` for lookup;
  documented.
- Duplicate files differing only by case (`btc.png`, `BTC.png`): validation warning; first match
  by exact case wins.
- SVG with embedded raster or fonts: allowed after sanitization; external `<image href>` removed.
- A project exported after this feature includes `assets/`; an older Bizview importing it rejects
  the files with the clear existing message (no silent drop).
- Share links and TV mode serve assets through the same signed path as the report data; no
  public listing of the folder.
- Accessibility: every image has `alt` = key or name; gauge/index/share carry a text summary.

## Requirements *(mandatory)*

- **FR-001**: Import accepts `assets/**` with the limits and checks above; assets are versioned
  with the project and exported back in the zip.
- **FR-002**: `report.yaml` gains `images: {<set>: {folder | column, key, fallback}}` validated
  against the project files and declared dimensions/columns; components gain `image: <set>`.
- **FR-003**: New web components `asset`, `gauge`, `index`, `share` and PDF block kinds of the
  same names, in `report.schema.json` (cli, single source), the LayoutRenderer and the PDF
  renderer; colours by palette roles only.
- **FR-004**: Integration column `kind: image_url` and the worker image cache (US2).
- **FR-005**: Lookup order asset → cached URL → fallback; fallback `initial` draws a circle with
  the first letter and a palette colour; `none` leaves the space empty.
- **FR-006**: Assets served with ETag/immutable caching per version; ≤ 300 KB each.
- **FR-007**: Authoring pack and `PROMPT.md` updated: how to add images, naming by key, limits,
  licence reminder (ship only images you may redistribute; the CC0 set is fine).
- **FR-008**: Example project `panorama-cripto` in the pack updated to use the four components
  and `assets/coins/`.

## Success Criteria *(mandatory)*

- **SC-001**: `cripto-simple-v2.zip` imports, applies and renders logos on tiles and table, the
  gauge, the index bar and the share bar at 375/1280 px, both themes, and in the PDF (visual tests).
- **SC-002**: 100 % of adversarial asset uploads (script in SVG, mislabeled binary, oversize, path
  escape) are rejected.
- **SC-003**: Worker image cache: 0 viewer requests to third-party hosts (transport spy); failed
  URLs never fail a data load.
- **SC-004**: Palette check passes for gauge bands and share colours in every preset × theme.
- **SC-005**: Authoring pack regenerated; the live eval builds a report using `images` and `gauge`
  from `PROMPT.md` alone.

## Constitution check

- II/VI unchanged (images are static files; no origin queries). III: `image_url` fetches are
  read-only HTTP GETs under source SSRF rules. V: no new stack component (SVG drawn by product
  code; ReportLab for PDF; Pillow if needed is a supporting library listed in the plan). VII:
  assets are project configuration. VIII: no AI. IX: `images` is declarative and validated.
→ PASS.
