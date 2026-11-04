# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Each source shows its structure, and one button generates the pack an author's AI reads
  (feature 052)**. The source page gains a second tab, **Estructura**: the catalogue as it is
  (schemas, tables, columns, types, keys, estimated rows, date ranges) and, for REST/Supabase, the
  saved **sample requests** with the shape of their responses. On top of that, **Generar estructura
  con IA** runs one internal pass with no input from anybody — Bizview scans the source (describe,
  the samples, the OpenAPI document when the source publishes one), the provider identifies the
  logical tables, fields and semantics, keys, dates, relations, personal data, pagination and the
  notes that say what one row is, and product code verifies every name against the scan before it
  saves the pack. What the model invents is dropped and listed, so a hallucinated table cannot reach
  a spec. **Descargar estructura** produces `structure.md` + `structure.json` from that pack (or from
  the plain scan when no run exists), through one generator shared by the button, the API and
  `bizview describe --pack`; `structure.json` validates against `structure.schema.json`, which also
  ships in the authoring pack.
  A structure *chat* was the first design of this feature and the owner replaced it on production:
  one button, no conversation, nothing typed. Nothing but metadata ever leaves a source — no row
  values, hosts or credentials — and the personal-data flags are heuristics a super user can
  override, carried in the pack. Constitution VIII is amended (3.2.2 → 3.2.3) to name AI-assisted
  structure generation as the second read-only AI surface.

### Changed

- **The installation theme now repaints the whole application (feature 051)**: applying a theme used
  to change the charts and nothing else. The application's own chrome — header band, sidebar, page
  background, cards, buttons, inputs, tables, dialogs, bottom navigation — was one set of literals per
  light/dark mode in `index.css`, and the theme contract could not reach it. Two defects, one cause:
  - a theme is now **data for the chrome too**. Seven optional tokens (`canvas`, `chrome`,
    `chrome_text`, `field`, `line`, `accent`, `warning`) join the published contract, the six new
    `shape` enums (`elevation`, `button`, `nav`, `divider`, `heading`, `card_border`) finally drive
    geometry that was previously inert, and `frontend/src/theme/derive.ts` turns a theme into every
    semantic token the screens already paint with. An uploaded theme authored before this feature
    keeps working and is derived from its palette;
  - **Usar en la instalación applies at once**: the page re-reads `/api/config` and the application
    repaints, with no reload and no sign-out. The confirmation is shown only after the server stored
    the choice, and the theme is cached on the device so a reload never flashes the previous one.
- **Four official identities, and three of them are new**: **Clásico** keeps the appearance the
  installation has today — its whole chrome token set is pinned in the theme file and a test compares
  it token for token against the literals `index.css` carried, so it cannot drift. **Impacto** is the
  modern executive identity (royal blue and cyan, pale canvas, large KPIs, strong elevation, pill
  buttons, solid navigation), **Elegante** the premium one (warm cream canvas, graphite band, bronze
  accent, flat elevation, hairline cards, left-bar navigation) and **Contraste** the high-contrast one
  (white canvas, near-black band, gold accent, 2 px borders, no shadows, outlined navigation).
  Daltónico and Monocromo remain valid and renderable and move to a **Compatibilidad** group.
- **`elegante` is registered everywhere a theme id is**: the schema, the CLI validator, the backend
  registry, the report/PDF renderer and the frontend, with migration `0048_official_themes` seeding
  the six built-ins and widening the `appearance_settings` check.
- **One design system, and the screens that had drifted from it (feature 050)**: the rules for page
  width, gutters, card padding, page headers, split panes and mutually-exclusive choices now live in
  `frontend/src/lib/layout.ts` and [docs/DESIGN-SYSTEM.md](./docs/DESIGN-SYSTEM.md). Four screens had
  each answered one of them differently:
  - **Administración → Apariencia** sat in a 56 rem column inside a 96 rem container with a fixed
    two-column grid, so a wide screen showed a narrow library with an unexplained empty half and
    over-tall previews. It now fills the container with one, two or three columns and equal-height
    cards, and the selected theme is marked with a word as well as a colour.
  - **Perfil and the account menu** stacked *Sistema / Claro / Oscuro* vertically because the theme
    switcher emitted `grid-cols-3` without `grid`, while the language options sat in a row. Both are
    now the same `SegmentedControl`, so they cannot answer differently again.
  - **Ayuda** had no bounded panel: the page scrolled instead of the article, and the topic list ran
    the full page length. Two panes now scroll on their own from `lg` up, and on a phone a topic
    replaces the list with a Back that keeps the search.
  - **The account menu** mixed identity, appearance, language and links without grouping; it is now
    four labelled groups in a viewport-bounded, scrollable popup that returns focus to its trigger.
- **The page header is a title line, not a hero block**: one compact `<h1>`, an optional subtitle and
  the actions in one wrapping row. On a 375 px phone the old card took a fifth of the viewport before
  any content.

### Added

- **Two readability guarantees in the derivation**: an accent is moved along its own lightness until
  it reads at 4.5:1 on the surface and on its own tint, and `ink-soft` is the lightest shade of the
  theme's muted ink that reaches 4.5:1 on the surface and the canvas. Both are checked for all six
  themes × two modes, in the unit suite and by axe in a real browser.
- **`tests/e2e/theme-application.spec.ts`**: apply-without-reload, persistence across a reload and a
  new session, independence from the user's light/dark preference, the four identities differing
  without labels, no sideways scroll at 320/375/768/1440, and the reference screen captured in all
  eight variants (`docs/assets/theme-application/`).
- **[docs/THEMES.md](./docs/THEMES.md)** documents the widened contract, the derivation and how the
  four identities differ.

- **Import limits that account for project images (feature 049)**: the import is charged to two
  allowances counted apart — **artifacts** (`project.yaml`, `specs/`, `integrations/`, `reports/`,
  `themes/`, `distributions/`: 400 files, 2 MB each, 20 MB total) and **assets** (`assets/`: 2 000
  files, 300 KB each, 25 MB total). Before this, images spent the room the specs needed, so a
  project that shipped a logo set was refused with a message about a budget the author could not
  act on: 483 logos and 40 artifacts could never be imported. Every refusal now names the allowance
  that was exceeded, the folders it counted and the numbers, never a combined figure. All six
  numbers are settings a super user edits in **Administración → Proyectos → Límites de
  importación**; an empty field keeps the deployment default, so an operator's
  `PROJECT_MAX_MB` still applies.
- **The import screen reads the zip before uploading it (049)**: the browser reads the archive's
  table of contents — no decompression, no library — and shows both tallies against their limits.
  Over a limit, the import action is disabled and the reason names which; the server re-checks.
- **`bizview import --dry-run <zip|folder>` (049)**: the same two tallies, the ignored files and the
  verdict from the command line, from the code the server uses (`--json` for a machine). `bizview
  validate` now reports the two allowances too.
- **A project folder that still carries the authoring pack imports (049)**: `PROMPT.md`,
  `REQUEST.md`, `request/`, `sources/`, `.bizview/`, `README.md`, `.DS_Store` and `__MACOSX/` are
  listed as ignored and the project imports. Executable content — by extension or by its first
  bytes — refuses the whole import and names the path.
- **The guide topic *Importar un proyecto* (049)** in both languages.
- **A source can be declared BI-ready (feature 048)**: instead of one installation-wide switch, each
  PostgreSQL source carries its own declaration — the schemas and objects reports may read, the query
  timeout, the cache lifetime, the row cap, the concurrency and the timezone its dates are read in.
  Bizview proves the credential read-only when it is saved and once a day (a write attempted and
  refused, inside a transaction that is rolled back), the source page shows the declaration, the
  limits in force and the last 24 hours of direct reads, and an object outside the declaration is
  refused by the validator and again by the engine.
- **A direct report needs no column list (048)**: for a BI-ready source, `direct.tables` accepts
  `alias: schema.object` and the columns come from the source's structure; the 019 shape and
  `source: bi` keep working untouched.
- **A direct report can keep its figures for a day (048)**: `materialize: daily` makes the worker run
  the report once and store the payload it already produces, so every viewer reads that with the
  notice that it is yesterday's. Figures only — no rows, no `ds_` schema.

### Removed

- **Manual project creation (feature 049)**: the "Nuevo proyecto" button, its form and
  `GET /api/projects/slug` are gone, and `POST /api/projects` answers `410`
  (`project_creation_removed`) instead of creating anything. Projects are authored outside Bizview
  and arrive only by import — which is what the constitution already said, and what the empty state
  now offers. Existing projects, their files, reports and history are untouched.

### Fixed

- The 512 KB per-file check in the CLI and the 2 MB budget the specification states were two
  different answers to the same question; one shared number now, so `bizview validate` and the
  server cannot disagree about a file.
- **`GET /api/projects/<slug>/tree` answered 500 for any project with a spec folder** since 045:
  the route still read the `converged` flag the in-app agent used, and 045 removed its producer
  while the frontend type had already stopped asking for it. The project editor, the e2e flows and
  the tree the import screen reads were all affected.
- **A project with a flagged personal column could never be applied** since 045: readiness demanded
  an explicit confirmation in the conversation's working state, which 045 removed, so declaring the
  column under `**Datos personales**:` in the integration spec was not enough and "Aplicar
  proyecto" stayed disabled with no way out. The spec declaration is the record again, and the same
  column is no longer reported twice when two datasets share it.
- **The project editor said nothing while it validated**, and dropped the result when the request
  failed: Apply stayed greyed out under "Sin problemas de validación" with no visible reason. The
  status bar now says **Comprobando el proyecto…** and, when the check cannot run, says so.
- **A column named `name` was treated as personal data everywhere** — a coin, product or category
  name included — so `panorama-cripto`-style reports could not be applied and the only way out was
  to declare a falsehood in the spec. A bare `name`/`nombre` is personal only when its dataset is
  about people (customers, users, patients…); `customer_name`, `full_name` or `email` are unchanged.
- **The two rules that block an apply were invisible to the author's AI**: `bizview validate` said
  "ok" while the server refused the project for a personal column, and said nothing about a report
  with no filters. Both are reported now — the personal column as an error, the missing filters as a
  warning — and the pack's agent instructions state them.
- **«Volver a comprobar» never answered** since 045: `POST /projects/<slug>/validate` stored the
  validation on the project row, and the origin checks store their result on that same row through
  `WorkView._persist`, in a separate transaction — while the write also left the mapped attribute
  dirty, so the caller's session flushed it again. The second write waited on the lock the first
  one held, for as long as the HTTP client stayed connected: the button spun forever, every click
  parked a database connection and the rest of the installation slowed down with it (it was already
  holding two connections and the project row for twenty minutes on the owner's server). The
  checks now run before anything is written, the value they store is taken in memory as committed
  instead of dirty, and their own write waits at most 5 s. The editor also refreshes problems and
  readiness with `check_origin=false`: re-checking every query against its source belongs to the
  button, not to every file change the poller notices.

### Changed

- `DIRECT_REPORT_CONCURRENCY`, `DIRECT_REPORT_WARN_ROWS` and the rest of the `DIRECT_*` variables are
  now the defaults a source inherits, not the whole truth of what may be read.


- **Themes are data an author writes outside Bizview (feature 047)**: the five looks the product
  shipped are now themes in a published format
  ([`cli/bizview_cli/schemas/theme.schema.json`](./cli/bizview_cli/schemas/theme.schema.json)) — a
  file of colour tokens and shape choices, never CSS — that a person or any AI can write, validate
  and preview without a server (`bizview theme validate`, `bizview theme preview`). The validator
  refuses a shape and a look alike: contrast of text, accents and every series against its own
  surface, series separation, polarity, a grid that stays out of the way, each refusal naming the
  tokens and the measurement.
- **A theme library (047)**: Administración → Apariencia lists the product's themes, the ones
  uploaded there and the ones a project brought, each with a light and a dark preview, its origin
  and its version; upload, download, duplicate, delete and apply, with the upload printing every
  problem it found and a collision asking before replacing. A theme a report uses cannot be deleted.
- **A report chooses its theme and its own mode (047)**: `layout.theme.id` names any theme of the
  installation and `layout.theme.mode` (`auto|light|dark`) decides the report's area, so a dashboard
  can be dark inside a light application while the chrome stays as the viewer chose; a sun/moon
  action overrides it for the session and a share link opens in the report's mode. The PDF always
  uses the theme's light variant. A report naming a theme that exists nowhere is a validation
  problem instead of a silent fallback.
- **A project carries its themes (047)**: `themes/<id>.yaml` inside a zip is validated and enters
  the library with the project as origin; a collision offers skip, replace or rename (the project's
  own references follow the rename), and the themes leave with the project when it is deleted.
- `THEME.md` in the authoring pack and [docs/THEMES.md](./docs/THEMES.md), plus the guide topic
  *Escribir un tema* in both languages.

### Removed

- **The placeholder "Ventas" dashboard**: a new installation used to open on a board marked
  *coming soon* that led nowhere, and the catalogue showed it to every user. The product ships no
  dashboard — one appears when a project is applied or when an administrator creates it, and the
  home screen says so — so migration `0002` no longer seeds it and `0046` removes the row from the
  installations that already ran it. Only the seeded row is deleted (`managed_by = 'product'`, no
  report behind it): a board a workspace or a person owns is never touched.

### Changed

- `layout.theme.palette` is the deprecated alias of `layout.theme.id`, accepted for one version so
  every project written before this release keeps applying.
- An installation's choice is stored as a theme (`appearance_settings.theme_id`), with the old
  `palette_preset` read as the fallback: the five ids are unchanged, so nobody's look moves.

## [0.2.0] - 2026-10-31

Bizview stops authoring. The in-app agent never worked well enough to trust (owner, 2026-10-29:
"the in-app agent never worked; better to use a powerful AI dedicated to this, externally"), so
authoring moved outside the product (features 043 and 045) and everything that existed only to
serve it is gone. Reading, running and sharing are untouched. This release is also the one that
makes the written product match the shipped one (feature 046).

### Added

- **Images travel inside the project (feature 044)**: the project's `assets/` folder accepts
  `.png`, `.jpg`, `.webp` and `.svg` (≤ 300 KB each, ≤ 25 MB per project), with the bytes checked
  against the extension and the SVG cleaned on import (no scripts, no external references). A
  report declares `images: {coins: {folder: assets/coins, key: symbol}}` and a component uses it
  with `image: coins`: the row's key finds `BTC.png`, `btc.png` or `BTC.svg` without anyone writing
  a path, and the image is served at `/api/reports/<id>/assets/…` with `ETag` and immutable. With
  no file, or with `fallback: none`, the tile draws the initial on a palette colour. `assets/`
  travels in the project's export and back through import.
- **Four visual blocks in the PDF (feature 044)**: `gauge`, `index`, `share` and `asset` are no
  longer screen-only. The PDF draws the arc with its bands and needle, the index bar with both
  ends, the share as its parts and the tile with the logo, the figure and the signed badge, and
  the numbers match the screen. Images are embedded from the project itself; a set with only SVG
  prints the initial circle, as the validation already warns.
- **Images from a URL column are cached once (feature 044)**: after a successful load, the worker
  downloads the new addresses of the column the report declares (under the sources' address guard,
  10 s, 300 KB, PNG/JPEG/WebP only) and stores them named by their hash. The row is rewritten to
  point at Bizview, so whoever opens the dashboard never calls the third party, two URLs with the
  same bytes share one file, and a failure is recorded without breaking the load (retried at most
  once a day).
- **The authoring pack (feature 043)**: `bizview init` writes the presets, the rules, the schemas,
  `PROMPT.md`, `REQUEST.md` and a golden example into a workspace, so a customer can build a
  project with any AI — or by hand — against the published contract.
- **Structure packs (feature 043)**: `bizview describe` and the workspace rules hand an external AI
  a source's structure, counts and shapes — never credentials, hosts or row values.
- **Import as the front door (features 020 and 046)**: **Proyectos → Importar** takes a zip, maps
  the folders, reports collisions, validates and shows the tree before anything is applied. The
  path is documented in [`docs/IMPORT.md`](docs/IMPORT.md).
- **`docs/AUTHORING.md` (feature 046)**: the contract in one document — folder layout,
  `PROMPT.md`/`REQUEST.md`, the schemas, the rules, lite specifications, validation and its
  `problems.json`, images, and a complete worked example.

### Changed

- **Principle IX of the constitution, and its preamble, folders and constraints (amendment
  3.0.0 → 3.1.0)**: projects are authored outside Bizview against the published contract and enter
  only through validation and import; the AI boundary names the structure-pack rule; the CLI's
  schemas are the single source of the contract; the import limits are written down.
- **The product is called `Bizview`** (0.2.0): `PRODUCT_NAME`'s default, the page title, the
  manifest, the package descriptions and every document drop the "AI Powered" suffix. An
  installation still chooses its own name.
- **`VERSION` is the single source of the version**, and `scripts/gates/07-version.sh` proves the
  backend, the frontend, the CLI package and `bizview version` agree with it — the four copies had
  drifted to 0.1.0, 0.2.0, 0.3.0 and 0.4.0 before this release.
- **Both READMEs are rewritten around the loop** (feature 046): what the product does, a one-screen
  install, the eight authoring steps with the commands a reader types, the capabilities table, the
  configuration groups and the architecture — with the same structure in Spanish and English, which
  `scripts/gates/08-markdown.sh` checks.
- **`SECURITY.md`, `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`** (feature 046): the reporting
  channel, the supported versions, the in-scope and out-of-scope surface, the protections that are
  true now; the development stack, the specification workflow, how to add a help topic and how to
  propose a schema change; the Contributor Covenant's contact address.
- **The authoring contract (feature 044)**: `report.yaml` gains `images:`; the `table`, `kpi` and
  `asset` components accept `image:`; `layout.pdf.blocks` accepts the four visual types, and the
  validation rejects a block bound to a view it cannot draw. [`docs/VIBE-REPORTING.md`](docs/VIBE-REPORTING.md)
  is now the field-by-field reference the authoring guide links to.
- **Administración**: the AI card and the "IA funcionando" pill are gone; the access-tokens and
  projects cards say what they now do; the grid is 3/2/1.
- **Upgrading from 0.1.x**: migration `0041_drop_authoring_agent` copies every draft spec document
  into its project folder and verifies each copy by SHA-256 **before** dropping a single table. A
  copy that fails aborts the upgrade with the tables intact. The downgrade refuses on purpose:
  recreating the tables empty would pretend the rows came back. Recovering them means restoring the
  database backup taken before the upgrade.

### Removed

- **Feature 014 — vibe chat**: the conversation, its composer, the "Asistente" panel and its
  routes, the draft preview and its temporary schemas, the tables `assistant_session`,
  `assistant_message` and `assistant_preview_request`.
- **Feature 015 is NOT removed**: the brief that listed it among the agent's specs was wrong — the
  folder is dashboard auto-refresh and TV mode, which this release still ships.
- **Feature 017 — the agentic loop**: `app/assistant/**` (loop, tools, tree and history builders,
  context compression, repair), the run activity map and the token-budget widgets.
- **Feature 021 — Spec Kit commands in the app**: the in-app `/speckit-…` and `/ayuda` commands, the
  command registry, its guards and the `assistant_command_run` table. The Spec Kit flow itself
  lives in the author's repository, driven by the CLI.
- **Feature 024 — image briefs**: `ATTACHMENTS_DIR`, `ATTACHMENTS_MAX_MB`,
  `ATTACHMENTS_MAX_PER_MESSAGE`, `AI_VISION` and the attachment sweep in the worker.
- **Feature 028 — Auto mode**: the mode selector, run contracts and profiles, "Pasar a Auto", the
  post-apply watch with its automatic rollback, and the tables `assistant_auto_run` and
  `assistant_run_profile`.
- **Features 039 and 040 — `/speckit-all`**: the state machine, its stage bounds and tool groups,
  its stage token ceiling, the run report as a product output and the `--only` task guard. Feature
  029 was a numbering gap and never existed.
- **Features 035 and 036 — the chat's AI status and history**: the narrative generator and the
  repair of conversation history. `report.yaml`'s `ai_narrative` key stays accepted and ignored
  (deprecated since 0.2.0) so a project written for an older installation still validates.
- **Feature 037 — the project preview work order**: `POST /api/projects/{slug}/preview` and its
  report, data and PDF endpoints. Published report rendering, PDF, sharing and email remain.
- **Settings and dependencies**: `AI_CHAT_*`, `AI_COMMAND_TOKEN_CEILING`, `AI_CONTEXT_COMPACT_CHARS`,
  `AI_STAGE_TOKEN_BUDGET`, `AI_AGENT_*`, `AI_AUTO_*` and `AI_TOOL_TIMEOUT_SECONDS` (replaced by
  `ORIGIN_CHECK_TIMEOUT_SECONDS`). `AI_PROVIDER` stays, defaults to `none` and is documented as
  help only. Provider tool-calling code, `app/ai/fake.py` and `app/ai/history_rules.py` are gone.
- **Specifications**: 014, 017, 021, 024, 028, 035, 036, 039 and 040 moved to `specs/_deprecated/`,
  each with a `DEPRECATED.md`.
- **The draft preview's readiness gate**: a project is ready on validation, query checks and the
  composition of the other applied projects; it no longer needs a preview before applying.

### Security

- **Import validates before anything runs** (features 044 and 046): file types, per-file and
  per-project sizes, path traversal, byte sniffing for images, SVG sanitisation and the same JSON
  Schemas the CLI validated against. A rejected import leaves nothing half-imported.
- **The image fetch follows the sources' address rules**: loopback, link-local, cloud-metadata and
  internal addresses are refused, redirects are not followed, the size is capped and the bytes are
  content-sniffed.
- **No AI authors inside the product**: the optional provider serves the read-only help page, and
  the structure packs a customer hands to an external AI carry no data.

## [0.1.0] - 2026-09-29

### Added

- Sign-in with email and password, server-side sessions, lockout after 5 failed attempts.
- Super user created from `SUPER_USER_EMAIL` / `SUPER_USER_PASSWORD` on first start, with a
  recovery command.
- Administration: create users, edit, activate/deactivate, reset passwords, grant dashboards;
  audit log for the super user.
- Home page with the dashboards available to each user; mobile-first blue interface in Spanish,
  tested on Chromium, Firefox, and WebKit at 320 and 375 px.
- Optional AI provider layer: Claude (Anthropic) or any OpenAI-compatible endpoint, off by
  default, with a status page and connection test for the super user.
- Distribution: `deploy/install.sh` creates a customer installation that runs published images;
  multi-arch images on GHCR; CI checks and tagged releases on GitHub Actions.
- Open source under AGPL-3.0-or-later, with version and source-code link on every page.
