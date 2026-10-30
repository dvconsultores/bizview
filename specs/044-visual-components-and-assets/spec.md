# Feature Specification: Visual components and project images

**Feature Branch**: `044-visual-components-and-assets`

**Created**: 2026-10-30

**Status**: Draft

**Input**: Owner, 2026-10-29: «Enable logos and gauges in dashboards; I can add all logos inside
the project zip.» Reports need tiles with a logo (coins, products, vendors), a semicircular gauge
(fear & greed), a two-ended index bar (Bitcoin ↔ Altcoin season) and a share bar (dominance), on
screen and in the PDF. Images come, in this order, from the project's own `assets/` folder, from a
cached URL column, or from a generated fallback.

**Builds on**: 026 (declarative layouts), 030 (palette roles as the only source of colour), 042
(tile catalogue: gauge, share, index and asset tiles already render on screen), 043 (import is the
front door; the in-app authoring agent is gone, so the declarative surface is the whole contract).
**Reference project**: `cripto-simple-v2.zip` (report `cripto-panorama`, `assets/coins/<SYMBOL>.png`,
483 CC0 logos).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Logos in tiles and tables from the project zip (Priority: P1) 🎯

The author ships `assets/coins/BTC.png …` inside the project and declares an image set keyed by a
column. Price tiles and the coins table show the logo next to the symbol; the PDF shows the same
images.

**Why this priority**: it is the reason the feature exists — a crypto or product dashboard without
logos is unreadable at a glance — and it delivers value on its own, with no other story built.

**Independent Test**: import `cripto-simple-v2.zip`, validate, apply; the price tiles and the table
rows show logos; a symbol without a file (for example `HYPE`) shows a circle with its initial; the
downloaded PDF embeds the same images.

**Acceptance Scenarios**:

1. **Given** a project folder with files under `assets/`, **When** it is saved or imported, **Then**
   `.png`, `.svg`, `.webp` and `.jpg` files under `assets/` are accepted (each ≤ 300 KB, whole folder
   ≤ 25 MB, content-sniffed: a file named `.png` must really be a PNG; an SVG with scripts or
   external references is refused) and are served with the project.
2. **Given** a `report.yaml` that declares

   ```yaml
   images:
     coins: {folder: assets/coins, key: symbol, fallback: initial}
   ```

   **Then** validation confirms the folder exists in the project and that `key` is a declared
   dimension (or a dataset column of a dataset the report uses); a component may then say
   `image: coins`.
3. **Given** a row whose key is `BTC`, **Then** the image is `assets/coins/BTC.png`
   (case-insensitive on the file name, `.svg`/`.webp`/`.jpg` also tried); when no file matches,
   `fallback` decides: `initial` draws a circle with the first letter and a palette colour derived
   from the key, `none` leaves the space empty.
4. **Given** a table component with `image: coins`, **Then** each key cell carries the image (20 px,
   round); given a `kpi` or `asset` tile, 40 px round beside the label.
5. **Given** a project with `assets/`, **When** it is downloaded, **Then** the zip carries the same
   files, and importing it into an older installation fails with the existing clear message rather
   than dropping them silently.

---

### User Story 2 - Gauge, index, share and asset components (Priority: P1)

The same four visual components the tiles already render on screen become part of the declarative
language: authors place them in a dashboard layout and in a PDF layout, and the numbers match.

**Why this priority**: the components are the visible half of the feature and the part a reader
compares across screen and PDF; without them the logos have nowhere to live.

**Independent Test**: build a report whose layout uses one `gauge`, one `index`, one `share` and one
`asset` block, with no other component type; it renders on screen, exports to PDF, and both agree
digit by digit.

**Acceptance Scenarios**:

1. **Given** a `gauge` bound to a metric (`min`, `max`, `bands: [{to: 25, role: negative}, …]`,
   optional `label_metric`), **Then** a semicircular arc shows the bands, a marker at the value, the
   value large in the centre and the label below (for example «40 · Neutral»).
2. **Given** an `index` component (`metric`, `min`, `max`, `left_label`, `right_label`, optional
   `label_metric`), **Then** it shows the value («43 /100»), a horizontal gradient bar from the left
   role to the right role with a marker, and the two end labels.
3. **Given** a `share` component (`parts: [{metric: btc_dominance, label: BTC}, …]`, optional
   `rest_label`), **Then** it shows the figures and a stacked bar whose remainder is «Otros» when the
   parts sum to less than 100.
4. **Given** an `asset` component (`metric` for the figure, `change_metric` for the badge, `image`,
   optional `name_dimension`, `sparkline`), **Then** it shows logo plus name, the value at display
   size, a filled ▲/▼ badge coloured by sign, and the optional sparkline.
5. **Given** any of the four in a PDF layout, **Then** the PDF draws the equivalent vector shapes
   with the embedded images, and every figure equals the screen.
6. **Given** a component type the running installation does not have, **Then** the existing error
   card names the piece (026 FR-006) — never a blank tile.

---

### User Story 3 - Images fetched once from a URL column and served locally (Priority: P2)

An integration column of kind `image_url` is fetched once per new value, stored locally and served
by Bizview; viewers never call the third party, and the PDF embeds the stored file.

**Why this priority**: it covers the sources that publish logos as URLs instead of files. It is P2
because a project that ships its own `assets/` never needs it.

**Independent Test**: run an integration whose column points at three public image URLs; the
dashboard renders them with the network to those hosts cut off afterwards, and the PDF embeds them.

**Acceptance Scenarios**:

1. **Given** a dataset column `logo_url: {type: text, kind: image_url}`, **When** the integration
   runs, **Then** the worker downloads new or changed URLs (public hosts only, same rules as data
   sources; ≤ 300 KB; PNG/SVG/WEBP/JPG; 10 s timeout; at most 500 new images per run), stores them
   under Bizview's own image cache, and records url, hash, fetch time and status.
2. **Given** an image set `images: {coins: {column: l.logo_url, key: symbol}}`, **Then** the lookup
   order is project asset by key → cached URL → fallback.
3. **Given** a URL that fails, **Then** the row shows the fallback and the run log names the URL;
   the same URL is not retried more than once a day, and image failures never fail the data load.

---

### Edge Cases

- Keys with characters a file name cannot hold (`/`, spaces): normalised to `_` for lookup, and the
  normalisation is documented in the authoring guide.
- Two files differing only by case (`btc.png`, `BTC.png`): validation warns; the exact-case match
  wins.
- An SVG with an embedded raster or fonts: allowed after sanitisation; external `<image href>` is
  removed.
- A project exported after this feature carries `assets/`; an older product importing it refuses the
  files with the existing message (no silent drop) — and the project still applies without them.
- Share links and the report's TV mode serve images through the same path as the report data; the
  folder has no public listing.
- Accessibility: every image carries `alt` = its key or name; gauge, index and share expose a text
  summary of their value.
- An installation upgrading from before 043 no longer has an `attachments/` folder: the image cache
  is a new location, never the retired one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Import and the editor MUST accept files under `assets/` with the limits and checks of
  US1; assets are versioned with the project, served by the product, and exported back in the zip.
- **FR-002**: A report MUST be able to declare `images: {<set>: {folder | column, key, fallback}}`,
  validated against the project's files and its declared dimensions or dataset columns; layouts MUST
  be able to reference a set with `image: <set>`.
- **FR-003**: The four components — `asset`, `gauge`, `index`, `share` — MUST exist in the
  declarative schema (the CLI's `report.schema.json` as the single source), in the screen renderer
  and in the PDF renderer, and MUST take their colours only from palette roles.
- **FR-004**: A report MUST be able to name a column that holds image addresses
  (`images: {<set>: {column: <alias>.<column>, key: <key>}}`), and the worker MUST cache the values
  of the columns the applied reports name, as described in US3, without ever blocking a data load on
  an image failure. *(Amended 2026-10-29 — this first asked for an integration column `kind:
  `image_url``: an integration column carries only a stored `type`, and the report already declares
  which column holds the addresses, so a second declaration could only drift from it. See research
  R6.)*
- **FR-005**: The image lookup order MUST be project asset → cached URL → fallback; `initial` MUST
  draw a circle with the first letter in a palette-derived colour, `none` MUST leave the space empty.
- **FR-006**: Served images MUST carry per-version caching headers and MUST NOT exceed 300 KB each;
  no image is served from a path outside the project's `assets/` or the image cache.
- **FR-007**: The authoring guide MUST explain how to add images, how keys map to file names, the
  limits, and the licence reminder (ship only images you may redistribute; the CC0 set is fine).
- **FR-008**: The example project shipped with the authoring pack MUST use the four components and
  `assets/coins/`, so an author has a working reference.
- **FR-009**: A report that references a component the installation cannot render MUST fall back to
  the existing error card, which names the piece — never an empty space.

### Key Entities

- **Asset**: a file shipped inside a project under `assets/`, identified by a set name and a key;
  versioned with the project and exported with it.
- **Image set**: the declaration in a report that maps a key column to files (or to a URL column),
  with its fallback policy.
- **Cached image**: one downloaded URL, stored once by content hash with its fetch status and time,
  shared by every row that points at the same URL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `cripto-simple-v2.zip` imports, validates, applies and renders logos on tiles and table,
  plus the gauge, the index bar and the share bar, at 375 and 1280 px, in both themes, and in the
  PDF — with screen and PDF figures identical.
- **SC-002**: 100 % of adversarial uploads are refused: a script inside an SVG, a binary mislabelled
  as `.png`, a file over the size limit, and a path that escapes `assets/`.
- **SC-003**: With the network to the image hosts cut off after a run, 100 % of logos still render —
  which also means zero viewer requests to third-party hosts during page loads.
- **SC-004**: Every gauge band and share colour passes the palette check in every preset × theme
  combination.
- **SC-005**: An author who has only the guide and the example project builds a report that uses
  `images` and `gauge` without asking for help; the shipped example is that proof.
- **SC-006**: A report using an unsupported component shows the named error card in 100 % of cases,
  never a blank or a broken layout.

## Constitution check

Checked against the constitution as amended by 043 (IX redefined, VIII explicit that Bizview does
not author with AI).

- **I (mobile-first)** — the components must work at 320 px and pass WCAG 2.2 AA, which is why
  accessibility is an edge case with an `alt` for every image and a text summary for gauge, index
  and share. PASS.
- **II / VI (backend as ETL, data tuning)** — images are static files shipped in the project, never
  origin queries; the optional URL cache fetches once per new value and never blocks a data load.
  PASS.
- **III (source of truth is external)** — `image_url` downloads are read-only HTTP GETs under the
  same public-host rules as data sources. PASS.
- **IV (separated concerns by folder)** — assets live under the project folder, next to the specs
  that declare them; the cache is its own directory inside the data volume, not the project. PASS.
- **V (fixed technology stack)** — no new stack component: the screen draws SVG with product code,
  the PDF keeps ReportLab, and any supporting imaging library is declared in the plan. PASS.
- **VII (one product, many installations)** — assets are project configuration, versioned with the
  project, so an apply reproduces a dashboard exactly on any installation. PASS.
- **VIII (AI optional and private)** — no AI anywhere in this feature; an author may be a person or
  an external agent, and the product only validates and renders. PASS.
- **IX (spec-driven reporting)** — `images` and the four components are declarative and validated
  against the project files and the declared columns; nothing about them is authored by Bizview.
  PASS.

Two consequences the plan must carry, recorded here rather than discovered later:

- The published contract changes (the CLI's report schema and the layout allowlist learning
  `assets/`), so the authoring skeleton and the example project ship in the same release; otherwise
  an author following the guide writes a project the validator refuses.
- `cli/bizview_cli/workspace_template/` stays untouched: it is the external authoring contract, not
  product code.

## Assumptions

- **Assets are project configuration, not origin data**: they travel with the project version, so an
  apply reproduces a dashboard exactly. No origin query is involved in serving them.
- **300 KB per image and 25 MB per project** are enough for the reference case (483 CC0 logos fit
  comfortably); a project that needs more is a signal to use the URL cache instead.
- **The image cache is a new directory of its own**, not `attachments/`: 043 removes that folder
  with the chat, and reusing its name would resurrect a concept the product no longer has.
- **The four components are already on screen** (042 Batch C); this feature makes them declarative
  and adds the PDF half, rather than inventing new visuals.
- **Colour comes from palette roles only** (030): the feature adds no hex values and no theme
  exceptions.
- **No AI is involved** in any part of it: the image sets and components are declarative, and the
  author may be a person or an external agent.
