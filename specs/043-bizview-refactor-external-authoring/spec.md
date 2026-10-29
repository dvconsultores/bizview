# Feature Specification: Bizview 0.2 — projects are authored outside, Bizview describes, validates, imports and runs

**Product**: Bizview · **Feature Branch**: `043-bizview-refactor-external-authoring`

**Created**: 2026-10-29

**Status**: Draft (master spec; each workstream below becomes its own `/speckit-plan` + tasks)

**Input**: Owner, 2026-10-29: "Complete app refactor. Remove 100 % the chat to build. Keep the
Parámetros panel as it is and make Filtros the same. Refactor Help (last). Refactor Profile
(theme and language side by side). Appearance is terrible and none of the presets apply. Remove
AI from the Administración grid. Create a skeleton so any AI can build a project in the export
format; I must provide the data structure because the external AI cannot connect to the origin;
Bizview reads the origin and provides the structure. The project is built externally with any
AI and imported into Bizview. Full refactor, README, public repo. Why: the in-app agent never
worked; better to use a powerful AI dedicated to this, externally."

**Decision**: Bizview stops being an authoring tool with an agent and becomes a **runtime with
a contract**: it describes data sources, publishes an authoring skeleton, validates and imports
projects, runs integrations, renders dashboards and PDFs, and shares them. Authoring happens
anywhere (Claude, ChatGPT, DeepSeek, a person) against that contract. The export format already
is the contract (`.bizview/schemas`, preset, templates, `CLAUDE.md`/`AGENTS.md`, `project.yaml`,
`specs/`, `integrations/`, `reports/`); this feature makes it the front door and removes
everything built to avoid it.

**Builds on**: 005 (declarative artifacts, CLI, schemas), 020 (projects), 031 (export/import),
026/030 (layouts, palette), 033 (help), 016 (Claude connector, kept optional).
**Removes / deprecates**: 014, 015, 017, 021, 024, 028, 029, 035, 036, 039, 040 (every feature
whose purpose was the in-app authoring agent). 003's AI provider layer is kept only for the
read-only help agent (033) and off by default.

**Constitution impact**: amendment **3.0.0** (MAJOR — principle IX is redefined; the draft said
2.0.0 against a stale copy, but the constitution was already at 2.1.0). See "Constitution
amendment" at the end.

## Workstreams (each one is a plan)

| WS | Name | Priority | Depends on |
|---|---|---|---|
| A | Remove the authoring agent | P1 | — |
| B | Authoring skeleton + source structure pack | P1 | — |
| C | Import as the front door (031 convergence) | P1 | B |
| D | Report page: Parámetros and Filtros as one inline panel pattern | P1 | — |
| E | Apariencia: presets that apply + standard page | P1 | — |
| F | Profile page | P2 | — |
| G | Administración home without AI | P1 | A |
| H | Help page redesign | P3 (last) | A, D, E, F, G |
| I | README, docs, version 0.2.0, naming | P1 | all |

---

## WS-A — Remove the authoring agent

**User story**: a super user opens Bizview and finds no chat, no Asistente, no `/speckit-*`
commands, no Auto mode, no token budgets; Proyectos shows projects, their files, versions, import
and export. AI settings exist only for the help agent and the Claude connector, both optional.

**Acceptance**:
1. Routes `/admin/asistente`, `/proyectos/<slug>/chat` (and any chat route) return 404; nav items,
   header sparkle button and composer are gone from every page.
2. Backend: the assistant loop, tools, command runner, run contracts, profiles, preview-from-chat,
   compression, provider tool-calling and their tables are removed. Alembic migration drops
   `assistant_*`, `command_run`, run-contract/profile tables **after** exporting each applied
   conversation's spec folder into the project (nothing a user applied is lost; transcripts are
   not kept).
3. The provider layer keeps `complete()` for the help agent only; `chat()` with tools is deleted;
   `AI_PROVIDER` defaults to `none`; "IA funcionando" pill removed.
4. Tests, fixtures, e2e suites and docs for the removed features are deleted; CI green;
   dependency list pruned (no unused SDKs).
5. `CHANGELOG` 0.2.0 "Removed" section lists every removed feature by spec number.

---

## WS-B — Authoring skeleton and source structure pack

**User story 1 — the skeleton**: in Proyectos, "Nuevo proyecto externo" downloads
`bizview-skeleton-<version>.zip`:

```
PROMPT.md                 one page: what to produce, in what order, how it will be validated,
                          how to use the user's request and attachments
REQUEST.md                template the user fills: what they want, metrics in words, how it looks,
                          expected values; attachments (images, Excel, PDFs) go in request/
request/                  empty folder for the user's attachments
README.md                 how to work with Claude Code / Codex / DeepSeek / ChatGPT, and how to import
.bizview/schemas/*.json   the exact validator schemas (same objects the CLI/backend use)
.bizview/preset/…         spec/plan/tasks templates, speckit.specify rules
.bizview/extension/…      speckit.bizview.validate
CLAUDE.md, AGENTS.md      hard rules
project.yaml              name/slug placeholders
examples/ventas-basico/   a golden project (integration + report + layouts) that validates
specs/.gitkeep integrations/.gitkeep reports/.gitkeep
```

**User story 2 — the structure pack**: in Fuentes de datos → `<source>` → "Descargar
estructura", Bizview generates `sources/<name>/structure.md` + `structure.json`:
- PostgreSQL: schemas, tables, columns with types/nullable, primary and foreign keys, row counts
  per table (counts only), min/max of date columns; personal-data flags by name heuristics.
- REST: for each **saved sample request** (new: the super user defines sample requests on the
  source page — method, path, params; Bizview runs them with the stored key), the **response
  shape** (keys, types, array lengths, one scrubbed example value for enums/dates only),
  pagination hints, and the suggested `fields` JSONPath map.
- SOAP: operations, input/output types.
- Never: credentials, hosts, row values, personal data. The pack is what the external AI reads
  instead of connecting.
- "Descargar paquete de autoría" on the project screen bundles skeleton + the structure packs of
  the sources the project will use, so the user hands one zip to the AI.

**Acceptance**:
1. A skeleton generated from the product validates with `bizview validate` (the example project
   passes) and `PROMPT.md` references only files in the zip.
2. The structure pack for the demo PostgreSQL source and for the CoinMarketCap REST source is
   produced in under 30 s and contains 0 row values (seeded distinctive values absent — 014
   SC-002 test reused).
3. Given the skeleton + structure pack, a run of Claude Code (opt-in live eval) produces a
   project that imports with ≤ 2 validation rounds for the `Ventas y facturación` request on the
   demo source, and for `Panorama cripto` on CoinMarketCap.

---

## WS-C — Import is the front door (031 convergence)

**User story**: Proyectos → "Importar proyecto" → upload zip → map sources → resolve ids →
validate → preview → apply, as 031 specifies. The validator's output is the external AI's
feedback loop, so it must be complete and machine-readable.

**Acceptance**:
1. 031 US1–US6 pass as written.
2. Validation returns **all** problems in one pass with `file`, `json_path`, `message`,
   `expected` (schema fragment), `actual` (keys/values found) and, for request `fields`, the
   actual response keys from the stored sample; the import page offers "Descargar problemas
   (problems.json + .md)" so the user pastes it back to the AI.
3. Lite specs: for imported projects `spec.md` is mandatory (with `**Tipo**` and `**Status**:
   Approved`); `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `quickstart.md`,
   `run-report.md` are optional. "No spec, no run" is enforced on `spec.md` only.
4. Import of the attached CoinMarketCap export (`coi.zip`) succeeds on a fresh installation with
   the source mapped, previews, and applies.
5. CLI: `bizview validate` and `bizview check-request <request.yaml> --sample <structure.json>`
   validate `fields` offline against the structure pack, so the AI can iterate without the
   server.

---

## WS-D — Report page: one inline panel for Parámetros and for Filtros

**Decision (owner)**: keep the Parámetros panel pattern (image 2): an inline card that opens
under the meta line, with "Limpiar todo" and × top-right, selects in a row with labels above.
Filtros uses the **same component**, replacing the right sheet (image 1).

**Acceptance**:
1. `Filtros` opens the inline panel with one control per declared filter (select, multi-select
   with search, date range, numeric range), in rows of 4 ≥ 1280 px, 2 on tablets, 1 on phones;
   "Limpiar todo" and ×; values apply live (250 ms) and the dashboard updates below.
2. `Parámetros` keeps its fields; the panel's height is its content (no empty area); Exportar
   (PDF/CSV, "Generar reporte") moves to the right block of the same panel as today or to the
   "⋯" menu — keep today's position.
3. Only one panel open at a time; the opener button shows the active state; applied filters and
   non-default parameters appear as removable chips under the meta line; state in the URL.
4. Keyboard and screen-reader accessible; AA; snapshot tests at 375/768/1280/1920.

---

## WS-E — Apariencia

**Acceptance**:
1. **Presets apply**: the effective preset (report `layout.theme.palette` → installation
   `palette_preset` → `impacto`) resolves once per page into CSS custom properties on the report
   root (`--series-1…8`, `--positive`, `--negative`, `--neutral`, `--grid`, `--surface`,
   `--kpi-text`, `--kpi-delta-bg`); every chart, KPI, badge, sparkline and the PDF palette read
   them; no literal colours remain in chart components (lint rule).
2. Choosing a preset applies on select (toast "Paleta aplicada") and a report open in another tab
   picks it up on next render; no reload required in the same tab.
3. Page uses the standard admin template: title card full width, grid of preset cards 2/row ≥ 768
   px and 3/row ≥ 1280 px, selected card with accent border and "en uso".
4. Each card previews a real mini dashboard rendered by the same components (KPI + delta badge,
   4-bar chart, 2-series sparkline) on a light and a dark surface **side by side**, with the
   preset's colours — never blank boxes.
5. Palette check in CI for every preset × theme (contrast ≥ 3:1, AA text, distinguishable
   series).

---

## WS-F — Profile

**Acceptance**:
1. One "Preferencias" card with two segmented controls **side by side** on desktop (stacked on
   phones): **Tema** (Sistema · Claro · Oscuro, icons + labels) and **Idioma** (Español · English ·
   Idioma del navegador); the same segmented component the user menu uses; helper text in one
   line under each.
2. Account card (avatar, name, email, role) and a "Seguridad" card (contraseña, doble factor,
   sesiones, Telegram) follow, each with the standard card layout; no card wider than the
   standard container.
3. The user menu (top-right) and the profile page share state; changing one updates the other.

---

## WS-G — Administración home

**Acceptance**:
1. The "Inteligencia artificial" card is removed from the Secciones grid; the "IA funcionando"
   pill is removed; "Tokens de acceso" description becomes "Para la CLI y las herramientas
   externas"; "Proyectos" becomes "Specs, integraciones, reportes y distribuciones: importar,
   validar y aplicar".
2. A new card "Paquete de autoría" (download skeleton + structure packs) and the existing
   "Fuentes de datos" card gains "Descargar estructura" mention.
3. Grid stays 3/row ≥ 1280 px, 2 on tablets, 1 on phones; help topics updated.

---

## WS-H — Help page (last)

**Acceptance**:
1. Standard page template: title card, search, then a **two-column** layout on desktop (topic
   tree left, 280 px; topic content right) — not a single narrow column of links; on phones the
   tree collapses to a dropdown.
2. Topics regenerated per 033 for the new product (no assistant topics; new: "Crear un proyecto
   con una IA externa", "Descargar la estructura de una fuente", "Importar un proyecto",
   "Parámetros y filtros", "Apariencia").
3. The read-only help agent (033) is optional and hidden when `AI_PROVIDER=none`.

---

## WS-I — README, docs, version, naming

**Acceptance**:
1. README (EN + ES) rewritten around the loop: **1. Install (Docker Compose) → 2. Add a source →
   3. Download the authoring pack → 4. Build the project with any AI (or by hand) → 5. Validate
   with the CLI → 6. Import → 7. Apply → 8. Share.** Hero line: "Your business data on your phone.
   Build the reports with any AI; Bizview validates, runs and shares them."
2. Version `0.2.0`; product name shown in the app header and footer becomes **Bizview** (the "AI
   Powered" suffix is removed from `PRODUCT_NAME` default, README and site copy; installations
   may keep any name via `PRODUCT_NAME`).
3. `docs/AUTHORING.md` (the contract: formats, schemas, rules, validation, examples) and
   `docs/IMPORT.md`; `docs/VIBE-REPORTING.md` updated; deprecated specs moved to
   `specs/_deprecated/` with a one-line reason each.
4. CHANGELOG 0.2.0: Added / Changed / Removed.

---

## Sequencing

1. **WS-A** (remove) and **WS-G** (admin grid) first — one PR, big deletion, CI green.
2. **WS-B** (skeleton + structure pack) and **WS-C** (import convergence, lite specs, CLI
   `check-request`) — the product's new core; include the CoinMarketCap `coi.zip` and the demo
   source as fixtures.
3. **WS-D**, **WS-E**, **WS-F** — UI, can run in parallel with 2.
4. **WS-I** — README/docs/version with the release.
5. **WS-H** — help, after everything else is stable.

## Success Criteria (release gate for 0.2.0)

- **SC-001**: On a fresh installation, a person with the authoring pack and Claude Code produces
  `Ventas y facturación` on the demo source and imports it successfully in ≤ 2 validation rounds
  and under 20 minutes (guided test); the same for `Panorama cripto` with CoinMarketCap.
- **SC-002**: 0 references to the assistant remain in routes, nav, strings, docs or tests (grep
  gate in CI for `asistente|speckit-|run_contract|token_budget`).
- **SC-003**: Structure packs contain 0 row values, credentials or hosts (automated).
- **SC-004**: Import validation problems include `expected` and `actual` for 100 % of schema and
  field errors (test over the fixture of bad projects).
- **SC-005**: Presets change report colours in 100 % of e2e runs; palette check green for every
  preset × theme.
- **SC-006**: Filtros and Parámetros panels pass the snapshot and accessibility suites at four
  widths; profile and admin pages likewise.
- **SC-007**: Backend and frontend suites green; image size and dependency count lower than
  0.1.x (reported in the release notes).

## Constitution amendment (3.0.0, MAJOR)

- **VIII. AI Is Optional and Private** → unchanged in substance; add: "Bizview does not author
  artifacts with AI. AI inside the product is limited to read-only help and to connectors that
  consume approved reports."
- **IX. Spec-Driven Reporting** → redefined: "Every integration and report is defined by a spec
  (`spec.md`, kind and Approved status) and declarative artifacts in a project folder. Projects
  are authored outside Bizview — by people or by any AI — against the published contract
  (schemas, preset, rules, structure packs) and enter Bizview only through validation and import.
  The engine refuses to load, run or show anything whose spec is missing or changed after
  validation." Plan/tasks become optional for imported projects.
- **IV. Folders**: `backend/app/assistant/` removed; `cli/` gains `check-request`; the skeleton
  lives in `cli/bizview_cli/workspace_template/` (already) plus `examples/`.
- **V. Stack**: no component added; the `anthropic`/OpenAI-compatible client remains for help
  only; tool-calling code removed.
- Sync Impact Report lists the deprecated specs.

## Assumptions

- The export format in `coi.zip` is the authoring contract; schema changes from now on are
  versioned (`format_version`) and the skeleton carries the version.
- Owner provides the structure packs to the external AI by hand (download → attach); no
  automated channel between Bizview and external AIs is needed in 0.2.
- The Claude connector (016) stays on the roadmap as an optional consumer; it is not part of
  this refactor.
