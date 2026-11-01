# Research — 047 themes as data

Phase 0. Each decision is what the plan implements; alternatives are recorded so a reviewer sees
what was rejected.

## R1. The authored format versus the runtime tokens

**Decision**: the published schema is the brief's — `light`/`dark` sets with `surface`, `card`,
`text`, `muted`, `grid`, `primary`, `positive`, `negative`, `neutral` and `series[]` (3–8), plus an
optional `shape` block. The runtime tokens the renderers already consume are **derived** from it:
`series1..8` come from `series[]`, `kpi_text` from `text`, `kpi_surface` from `card`, and
`kpi_delta_bg` from `positive`/`negative` mixed with `card` at a fixed ratio. The five built-ins are
rewritten in the authored format and their derived output is asserted against their current JSON.

**Rationale**: 030's rendering, its CSS-variable mapping and its PDF mirror are load-bearing and
tested. Changing the *authored* contract without touching the *consumed* one makes the feature
additive and reversible; it also means the five presets prove the derivation.

**Alternatives considered**: (a) migrate the renderers to the new names — touches every chart, every
PDF block and 030's gates for no user-visible gain; (b) keep 030's format as the authored one — it
has no `card`/`text`/`muted` and no shape tokens, so it cannot express a brand.

## R2. Where the validator lives

**Decision**: `cli/bizview_cli/theme.py` holds one function `validate_theme(data)` returning a list
of problems (path, code, message with the measured value), and `derive_tokens(theme, mode)`.
`bizview theme validate` uses it; the backend imports it (the CLI is already a path dependency of the
backend, and it is where the artifact rules live).

**Rationale**: one implementation means an author's `bizview theme validate` and the server's upload
cannot disagree — the failure mode this whole feature exists to prevent.

**Alternatives considered**: validate in the backend and re-implement in the CLI (two answers, the
one defect the project keeps paying for); validate only in TypeScript with JSON Schema (no contrast
mathematics, and the CLI is Python).

## R3. Two layers of validation, one function

**Decision**: `theme.schema.json` (through `jsonschema`, which the CLI already depends on and uses
for every artifact schema) refuses the *shape*; `validate_theme()` then runs the hand-written
*material* rules — text/surface, series/card, adjacent-series ΔE, positive/negative hue distance —
and every problem carries the pair and the measured value.

**Rationale**: the tree already ships `jsonschema` and `_schema()` for six artifact schemas, so
reusing it costs nothing and keeps the theme's shape refusals in the same words authors already
read. What a schema cannot express is the accessibility mathematics, and that is exactly where an
author needs "3.9:1, needs 4.5:1" instead of "invalid".

**Alternatives considered**: schema only — accepts a theme whose text is illegible, which is the
failure this feature exists to prevent; hand-written only — re-implements key and type checks the
repository already has.

## R4. Shape tokens

**Decision**: `radius` (`sm|md|lg`), `density` (`compact|normal`), `kpi_scale` (`md|lg|xl`), `font`
(`sans|serif|mono`), `badge` (`filled|outline`). They map to CSS custom properties
(`--t-radius`, `--t-density`, `--t-kpi-scale`, `--t-font`, `--t-badge`) consumed by the existing
components; the PDF maps the same enums to its own metrics.

**Rationale**: fixed enums mean a theme cannot ask for a font the PDF cannot embed or a radius no
component knows, and the whole block is optional so a colour-only theme stays tiny.

**Alternatives considered**: free numbers (`radius: 12px`) — invites a stylesheet by another name
and breaks the PDF's fixed geometry; custom font upload — out of scope, and it is a licence problem
before it is a technical one.

## R5. Storage: a table, not a file

**Decision**: `theme` table with `tokens` JSONB, `origin` (`builtin|upload|project`), `project_id`,
`version`, `created_by`. The migration seeds the five built-ins from the same JSON the frontend and
the PDF ship.

**Rationale**: a theme is installation data that must be uploaded, versioned, audited and listed
with its origin. Writing files into the container's filesystem is what the product deliberately does
not do for anything but project files.

**Alternatives considered**: a folder under `PROJECTS_DIR` for installation themes — mixes project
data with installation data and has no transaction with the audit row.

## R6. Built-ins: rows in the database *and* files in the tree

**Decision**: built-ins are product data in the tree (`frontend/src/theme/themes/*.json`, mirrored
byte-identically for the PDF) **and** seeded as rows so the library, the delete rule and the report
references have one lookup. The seed is idempotent and re-runs at bootstrap; a built-in cannot be
deleted or replaced, and its row is refreshed from the file when the product ships a new version.

**Rationale**: the files are what the frontend bundles (no request before first paint) and what the
PDF needs offline; the rows are what the API and the references need. Keeping both is how 030
already works, and the migration makes the second explicit.

**Alternatives considered**: only rows and a request at startup — the first paint would flash the
wrong colours, and the PDF would need a database read to render a share link.

## R7. Report theme resolution and the mode

**Decision**: resolve `report.layout.theme.id` → installation theme → `impacto`, once per page, into
CSS custom properties on the report's container (not on `<html>`), which is what lets a dark report
sit inside a light app. The report's container also carries `data-mode`, derived from
`layout.theme.mode` (`auto` follows the app, `light`/`dark` force) and overridable per session by a
toggle stored in `sessionStorage`. A share link reads the report before rendering, so it opens in
the report's mode.

**Rationale**: pushing the variables onto the report container rather than the root is the whole
mechanism; everything else is a stored preference.

**Alternatives considered**: force the whole document's mode — the brief explicitly wants the chrome
to stay as the viewer chose.

## R8. PDF

**Decision**: the PDF always renders the theme's **light** variant, and the `layout.theme.mode` is
ignored there. `backend/app/reports/palette.py` grows `resolve_theme(theme_tokens, "light")` beside
the existing `resolve()`.

**Rationale**: a printed page on a dark surface is a black rectangle; every BI product does this.
The brief says so too.

**Alternatives considered**: honour the mode — wasted ink and unreadable on paper.

## R9. Project themes and collisions

**Decision**: `themes/<id>.yaml` inside a project is validated at import with the same function; a
collision offers rename/replace/skip naming the owner. A built-in id is never replaced by an import
(rename or skip only). Export writes the theme back from the database, not from the zip.

**Rationale**: identical to 031's id collision rules, which authors already know.

**Alternatives considered**: last-wins — silently changes the look of every dashboard using that id.

## R10. `palette` → `id`

**Decision**: `layout.theme.id` is the new key; `layout.theme.palette` keeps validating and resolves
as if it were `id`, marked deprecated in the reference for one version.

**Rationale**: a project written yesterday must still apply; the brief asks for exactly this.

**Alternatives considered**: rename outright — breaks every existing project's apply.

## R11. `bizview theme preview` emits SVG, not PNG

**Decision**: the command writes an `.svg` (default `preview.svg`) with the same card the Apariencia
page draws — KPI with badge, four bars, two-series sparkline, light and dark side by side — plus the
measured contrast ratio of each mode's text on its surface printed to the console.

**Rationale**: the brief asks for `--out preview.png`, but rasterising needs either a headless
browser or an image library, and neither is a dependency of this repository; adding one to satisfy a
file extension would be a larger change than the feature. The SVG opens in any browser or viewer,
shows the identical geometry and colours the React component uses, and a colour is exactly as
verifiable in it as in a PNG. The extension the command writes decides the format it can honour: an
`--out *.png` is refused with a message naming `.svg`, instead of writing SVG bytes under a `.png`
name.

**Alternatives considered**: add Pillow — a new runtime dependency for one developer command; add a
headless browser — the heaviest possible dependency, and the very thing 045 removed from the stack.

## R12. The pack carries one worked theme, not the five built-ins

**Decision**: `THEME.md` in the authoring pack shows one complete theme inline; the pack does not
ship copies of the five built-ins. An author who wants a real one downloads it from Apariencia
(**Descargar**), which serves the row's authored file.

**Rationale**: the built-ins already exist twice (the web app and the PDF's byte-identical mirror)
and a test fails on drift between them. A third copy inside the CLI package would be a third place
to forget.

**Alternatives considered**: copy the five JSON files under `workspace_template/files/themes/` —
more to keep in sync than it buys; a `bizview theme example <id>` command — a new verb for a file
the product can already hand over.
