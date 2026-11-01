# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
