# Tasks: Report page polish — width, parameters, filters, theme, impact palette

**Input**: Design documents from `/specs/030-report-page-polish/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: included — the spec makes them part of the deliverable (FR-010 "automated palette check … runs in CI", FR-004 "validated by an automated palette test in the frontend suite", SC-001 "visual tests", SC-003 "(e2e)", SC-005).

**Organization**: by user story, in priority order (US1, US2, US3, US5 are P1; US4 is P2).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: two one-line enablers used by more than one story.

- [X] T001 Add `"resolveJsonModule": true` to `frontend/tsconfig.json` so `import preset from "./palettes/impacto.json"` type-checks
- [X] T002 [P] Add `"appearance_updated"` to the `AUDIT_EVENTS` tuple in `backend/app/models.py` (alphabetical with the other `*_updated` names)

**Checkpoint**: `npx tsc --noEmit -p .` still passes in `frontend/`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the sheet shell and the form refactor that US2 (Parámetros tab) and US3 (Filtros tab) both build on.

**⚠️ CRITICAL**: US2 and US3 start after this phase; US1, US5 and US4 do not depend on it.

- [X] T003 Create `frontend/src/components/report/ReportSheet.tsx` per [contracts/report-ui.md](./contracts/report-ui.md) §4: props `{ open, tab, onTabChange, onClose, title, children }`; ≥1024 px right side sheet 360 px with no backdrop, <1024 px bottom sheet with drag handle and `max-height:70vh`; `role="dialog"`, `aria-modal="false"`, `aria-labelledby`; focus moves in on open, Tab cycles inside, Esc closes, focus returns to the opener, outside click closes (desktop only); 200 ms slide with `motion-reduce:translate-none`; no library, no portal
- [X] T004 Refactor `frontend/src/components/report/ParamsForm.tsx`: add `live?: boolean` (debounce `onApply` by 250 ms while `draft` differs from `applied`, cancel on unmount) and `section?: "all" | "period" | "filters"` so the period block and the filter block can be rendered separately; keep the existing "Aplicar filtros" path working when `live` is false
- [X] T005 [P] Add the shared i18n strings in `frontend/src/i18n/es.ts` and `frontend/src/i18n/en.ts`: namespace `reportSheet` (`tabs.filters`, `tabs.params`, `done`, `close`, `clearFilters`, `searchFilter`, `moreChips(n)`, `unknownFilter`) and `reportActions` (`filters(n)`, `params`, `pdf`, `share`, `email`, `schedules`, `tv`, `more`)
- [X] T006 [P] Unit tests in `frontend/tests/unit/report-sheet.test.tsx`: renders as a dialog, opens on the requested tab, Esc closes and returns focus to the opener, Tab stays inside while open, bottom-sheet class below 1024 px, `prefers-reduced-motion` removes the transition; and extend `frontend/tests/unit/params-form.test.tsx` for `live` (one debounced `onApply` after 250 ms) and `section="filters"` (no period fields)

**Checkpoint**: sheet renders in isolation; `npx vitest run tests/unit/report-sheet.test.tsx tests/unit/params-form.test.tsx` passes.

---

## Phase 3: User Story 1 - The page uses the app's width (P1) 🎯 MVP

**Goal**: the report page and the shared view span the same container as Tableros/Administración.

**Independent Test**: at 1280/1440/1920 px the report content width equals the Tableros list width; 375 px gives 16 px gutters and no horizontal scroll (quickstart scenario 1).

- [X] T007 [US1] Create `frontend/src/lib/layout.ts` exporting `APP_CONTAINER = "mx-auto w-full max-w-screen-2xl"` and `APP_GUTTER = "px-4 sm:px-5 lg:px-4"`
- [X] T008 [US1] Create `frontend/src/components/PageContainer.tsx`: polymorphic (`as="div" | "main" | "header"`) wrapper composing `APP_CONTAINER` + `APP_GUTTER` + `className`, forwarding the rest of the props
- [X] T009 [US1] Use the constants in `frontend/src/components/AppShell.tsx` `<main>` (`mx-auto max-w-screen-2xl sm:px-5 lg:px-4` → `APP_CONTAINER + " " + APP_GUTTER`) keeping the `docked` and `chromeHidden` branches unchanged
- [X] T010 [US1] Remove both `mx-auto max-w-7xl` wrappers in `frontend/src/pages/ReportView.tsx` (the `!def` branch and the main return) so the page fills the shell container
- [X] T011 [P] [US1] Use `PageContainer` for the header and main of `frontend/src/pages/SharedDashboard.tsx`, replacing all three `max-w-7xl` occurrences
- [X] T012 [P] [US1] e2e width assertion in `frontend/tests/e2e/design.spec.ts`: measure the report content box vs the Tableros list at the configured widths and assert equality (±2 px) and `document.documentElement.scrollWidth <= viewport` at 320/375 px

**Checkpoint**: US1 deliverable is visually verifiable on its own (quickstart scenario 1).

---

## Phase 4: User Story 2 - Parameters out of the way, one tap away (P1)

**Goal**: title, one meta line, an actions row and the numbers; the parameters card is gone; "Parámetros" opens the sheet.

**Independent Test**: at 375×667 the first screen shows title, meta line and ≥2 KPI tiles; "Parámetros" opens the sheet on its Parámetros tab and changes apply live (quickstart scenario 2).

- [X] T013 [US2] Create `frontend/src/components/report/ReportMetaLine.tsx`: one line `Año en curso · 1 ene – 23 oct 2026 · vs 2025 · Datos 23 oct 20:00` from `t.reportParams.periodLabels`/`compareLabels`/`freshnessText`/`formatRange`; two lines below 640 px with the period first; middle truncation that never cuts a date; renders the filter chips (from T022) and the "+N más" overflow
- [X] T014 [US2] Create `frontend/src/components/report/ReportActions.tsx`: Filtros (with active count) and Parámetros as icon+label; Descargar PDF, Compartir, Enviar por correo, Envíos programados and Modo TV as icon+label ≥1024 px, icon with `title`/`aria-label` at 640–1023 px, all inside a "⋯" menu (`aria-haspopup="menu"`, roving focus, Esc closes, focus returns) below 640 px; keep the existing conditions (`def.pdf`, `user.role === "admin"`, `dashCode`, `emailAvailable`)
- [X] T015 [US2] Rewire `frontend/src/pages/ReportView.tsx`: drop `ParamsPanel`/`useReportPanelCollapsed` and the collapsed grid, render `ReportMetaLine` + `ReportActions`, open `ReportSheet` on the Parámetros tab, stop passing `viewer` to `ContextBlock`, and delete `frontend/src/components/report/ParamsPanel.tsx`
- [X] T016 [US2] Replace `frontend/src/components/report/ContextBlock.tsx` with the chips-only rendering used by `ReportMetaLine` and delete the card, its `<dl>` and the viewer cell; update the shared view call site
- [X] T017 [P] [US2] Remove `reportParams.collapse`, `reportParams.expand`, `reportParams.contextTitle` and `reportParams.contextViewer` from `frontend/src/i18n/es.ts` + `en.ts`, and every reference in `frontend/src` and `frontend/tests`
- [X] T018 [P] [US2] Unit tests `frontend/tests/unit/report-header.test.tsx`: meta line renders the four segments and truncates without breaking the dates; actions row collapses the conditional buttons at the three breakpoints; "Consultado por" is absent from the DOM

**Checkpoint**: no parameters card on the page; actions row keyboard reachable (quickstart scenario 2.1–2.4).

---

## Phase 5: User Story 3 - Filters as a side sheet with chips (P1)

**Goal**: Filtros and Parámetros share the sheet, state stays in the URL, chips reflect it, charts animate.

**Independent Test**: filter change → URL + chip + chart update in under 500 ms with the sheet open; bottom sheet on a phone; deep link restores (quickstart scenario 3).

- [X] T019 [US3] Wire `ReportSheet` into `frontend/src/pages/ReportView.tsx` for both tabs, replacing the phone-only `View` at the Filtros button; sheet open state in the component, tab defaulting to the button used
- [X] T020 [US3] Filtros tab content in `ReportSheet`: `ParamsForm section="filters" live` (one row per declared filter, `MultiSelect` search inside long lists, "Limpiar"/"Listo"), grouping under collapsible headings when the report declares 10+ filters
- [X] T021 [US3] Chips: `frontend/src/components/report/FilterChips.tsx` with removable chips (`Estatus: pagada ×`, label from `localized(def.dimensions[id],"label")`), two lines max then "+N más" that opens the Filtros tab, wired into `ReportMetaLine`
- [X] T022 [US3] Unknown-filter notice: when the URL carries a filter id the definition no longer declares, ignore it (existing `parseSelection` behaviour) and show the one-line `reportSheet.unknownFilter` notice inside the sheet
- [X] T023 [US3] ≤300 ms data transition in `frontend/src/components/report/charts/*` (fade/rise keyed by the series signature) with `motion-reduce:transition-none`, and the same for `KpiGrid`
- [X] T024 [P] [US3] Use `ReportSheet` + `ReportActions` in `frontend/src/pages/SharedDashboard.tsx` (replacing the `showFilters` card), keeping the PDF action and the read-only behaviour
- [X] T025 [P] [US3] e2e `frontend/tests/e2e/report-params.spec.ts`: open the sheet, change a filter, assert the chart updates with the sheet still open, chip appears, URL carries the state, reload restores it
- [X] T026 [P] [US3] Unit tests `frontend/tests/unit/filter-chips.test.tsx`: chip removal applies `withoutFilterValue`, "+N más" opens the Filtros tab, 10+ filters group under headings

**Checkpoint**: US3 works end to end on its own (quickstart scenario 3).

---

## Phase 6: User Story 5 - Impact palette, presets, saved (P1)

**Goal**: vivid default look, preset chosen per installation and optionally per report, PDF follows, gate in the suite.

**Independent Test**: `npx vitest run tests/unit/palette-presets.test.ts` passes for 5 presets × 2 themes; Administración → Apariencia saves a preset that every report follows (quickstart scenarios 0 and 5).

- [X] T027 [P] [US5] Add `frontend/src/theme/palettes/{impacto,clasico,monocromo,contraste,daltonico}.json` exactly as [contracts/palette-preset.md](./contracts/palette-preset.md) / research R3–R4 specify (both themes, all roles, `strategy`, `label_key`)
- [X] T028 [US5] Type the data: `PaletteId`, `PalettePreset`, `PaletteTheme` in `frontend/src/theme/palette.ts` plus `PALETTES` (id → preset) and `PRESET_IDS`, with the completeness rules of data-model §1 expressed in types
- [X] T029 [US5] `applyPalette(id, theme)` in `frontend/src/theme/palette.ts`: write the CSS custom properties of contracts/palette-preset.md ("Web token mapping") on `document.documentElement` and set `data-palette="<id>"`
- [X] T030 [US5] Wire it: `frontend/src/theme/ThemeContext.tsx` applies the palette when the resolved theme or the effective preset changes; `PublicConfig` (`frontend/src/api/types.ts` + the config fetch) carries `palette_preset`/`palette_presets`; `ReportView`/`SharedDashboard` pass their report override (`def.layout?.theme?.palette`)
- [X] T031 [US5] Add the new tokens to `frontend/src/index.css` for both themes (`--c-kpi-text`, `--c-kpi-neutral`, `--c-kpi-surface`, `--c-kpi-delta-bg-positive/negative`, `--kpi-numeral`, `--kpi-tracking`) and the `:root[data-palette="impacto"]` block (display numerals, tight tracking, filled delta badges, `--radius-card`/`--shadow-card` stronger in dark)
- [X] T032 [US5] Use them in `frontend/src/components/report/KpiGrid.tsx` (numerals via `--kpi-numeral*`/`--kpi-tracking`, delta badges filled with `--c-kpi-delta-bg-*`) so other presets keep today's typography (FR-009)
- [X] T033 [US5] Backend data + resolution: `backend/app/reports/palette.py` (`PRESET_IDS`, `load_preset`, `ReportPalette`, `resolve(definition, installation)` → light variant) and the byte-identical mirror in `backend/app/reports/palettes/*.json`
- [X] T034 [US5] Take every colour from the palette in `backend/app/reports/pdf.py` (`BLUE/INK/MUTED/LINE`) and `backend/app/reports/pdf_layout.py` (base constants + semantic + series), passing the resolved palette through `render()`/`Layout`
- [X] T035 [US5] Persistence: `AppearanceSettings` model in `backend/app/models.py` (singleton `id=1`, `palette_preset` default `impacto` with a check constraint on the five ids, `updated_at`, `updated_by`) and migration `backend/alembic/versions/0027_appearance_palette.py`
- [X] T036 [US5] API: `backend/app/api/appearance.py` with `GET`/`PUT /api/admin/appearance` ([contracts/appearance-api.md](./contracts/appearance-api.md), `require_superuser`, CSRF, `appearance_updated` audit, `422` on an unknown id) and the router registration
- [X] T037 [P] [US5] `GET /api/config` in `backend/app/api/health.py` returns `palette_preset` + `palette_presets`, defaulting to `impacto` when the row is unreadable
- [X] T038 [P] [US5] CLI contract: `theme`/`palette` in `cli/bizview_cli/schemas/report.schema.json` and the enum check in `cli/bizview_cli/report_layout.py` (hex still refused), plus `ReportDefinition.layout.theme` in `frontend/src/api/types.ts`
- [X] T039 [P] [US5] "Paleta" selector in the report's Parámetros tab (same presets, "Usar la de la instalación" default) saving `layout.theme.palette` through the existing definition update path
- [X] T040 [US5] Admin screen `frontend/src/pages/admin/Appearance.tsx` + route in `frontend/src/App.tsx` + tile in `frontend/src/pages/admin/adminTiles.ts`: preset cards with a live mini dashboard (KPI + bar + line) in both themes, save via `PUT /api/admin/appearance`
- [X] T041 [P] [US5] Palette gate `frontend/tests/unit/palette-presets.test.ts` implementing [contracts/palette-preset.md](./contracts/palette-preset.md) rules 1–9 (contrast, ΔE, sequential rule, semantic pair, badge text, subtle grid, backend mirror byte-identical) and the no-hex-in-report-definitions lint (SC-004)
- [X] T042 [P] [US5] pytest `backend/tests/test_palette.py` (resolve order, light output, unknown preset rejected) and extend `backend/tests/test_pdf_layout.py` / `test_pdf_declarative_layout.py` for palette-driven colours + `test_appearance_api.py` (super user only, audit, `/api/config`)
- [X] T043 [P] [US5] CLI test in `cli/tests/test_report_layout.py`: accepts the five ids, rejects `neon` with a `layout_range` issue on `layout/theme/palette`, still rejects hex
- [X] T044 [P] [US5] Unit tests `frontend/tests/unit/appearance-page.test.tsx` (cards preview in both themes, save calls PUT, failure toast) and extend `frontend/tests/unit/no-raw-colors.test.ts` (new tokens defined in both themes)

**Checkpoint**: gate green, preset change visible on every report and in the PDF (quickstart scenarios 0 and 5).

---

## Phase 7: User Story 4 - Shared view: light and dark (P2)

**Goal**: the public view gets a theme toggle beside the language toggle; the sharer may force the first load; PDFs stay light.

**Independent Test**: toggle re-themes without reload and persists; a link created with "oscuro" opens dark in a clean profile; the PDF is light (quickstart scenario 4).

- [X] T045 [P] [US4] `compact` variant of `frontend/src/components/ThemeSwitcher.tsx` (Claro/Oscuro only, roving radio like `LanguageSwitcher compact`)
- [X] T046 [US4] Shared header in `frontend/src/pages/SharedDashboard.tsx`: theme toggle beside the language toggle
- [X] T047 [US4] First-load theme: nullable `theme` (`light`/`dark` + check) on `ShareLink` in `backend/app/models.py`, optional `theme` on `POST /api/sharing/{code}/links`, `theme` in `GET /api/shared/{token}`, and the apply-once rule of [contracts/share-theme.md](./contracts/share-theme.md) in `frontend/src/pages/SharedDashboard.tsx`
- [X] T048 [P] [US4] "Abrir en tema claro/oscuro" select in `frontend/src/components/sharing/ShareLinksPanel.tsx` (+ strings)
- [X] T049 [P] [US4] Unit tests `frontend/tests/unit/shared-theme.test.tsx` (toggle persists to `localStorage`, forced theme applied only on a storage miss, storage failure swallowed) and pytest `backend/tests/test_share_theme.py` (create with/without theme, payload, existing links stay `NULL`)
- [X] T050 [P] [US4] e2e `frontend/tests/e2e/sharing.spec.ts`: switch theme on a shared page, reload, still chosen; PDF request returns a light PDF

**Checkpoint**: US4 complete; the PDF is light in both screen themes.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T051 a11y pass over the sheet, chips, toggles and picker: names, roles, `aria-expanded`, focus order, ≥44 px targets; run the existing axe assertions in `frontend/tests/e2e/design.spec.ts` against the report page and the shared view in both themes (SC-006)
- [X] T052 i18n parity: every new key exists in `frontend/src/i18n/es.ts` and `en.ts`; extend `frontend/tests/unit/guide-drift.test.ts` expectations if the guide mentions the report page controls
- [X] T053 Update `CHANGELOG.md` and the report-page section of `docs/` (if present) for: app container, sheet replacement, presets, shared theme
- [X] T054 Run the full gate: `cd frontend && npx tsc --noEmit -p . && npm test && npm run build`; `cd backend && uv run ruff check app tests alembic && uv run pytest`; `cd cli && uv run ruff check . && uv run pytest`
- [ ] T055 Walk [quickstart.md](./quickstart.md) scenarios 0–6 and record the SC-007 side-by-side evidence for the owner in the PR body (template `.github/pull_request_template.md`)

---

## Dependencies

```text
T001, T002 ─┬─> US1 (T007→T012)
            ├─> Foundation (T003→T006) ─┬─> US2 (T013→T018) ─> US3 (T019→T026)
            │                            └─> (T024 uses the sheet too)
            ├─> US5 (T027→T044)          (independent of Foundation)
            └─> US4 (T045→T050)          (independent; T047 needs T002)
```

- US1 is independent of everything and ships alone (MVP).
- US2 needs the sheet shell (T003) + i18n (T005); US3 needs US2's header (the chips live in the meta line).
- US5 is independent of US2/US3 (only its "Paleta" selector, T039, needs the sheet) and of US4.
- T054 (full gate) runs last; T055 is the owner review.

## Parallel execution examples

- **US1**: T011 (shared view) runs while T010 (report page) is edited; T012 (e2e) after both.
- **US5**: T027/T028/T029 (frontend data + tokens) parallel with T033/T034 (backend palette) and T038 (CLI contract); tests T041/T042/T043 in parallel once both sides exist.
- **US4**: T045/T046 (toggle) parallel with T047 (data/API) and T048 (share dialog); tests T049/T050 after.

## Implementation strategy

1. **MVP**: US1 only — the container fix is one dependency-free increment that answers the owner's first complaint.
2. **Increment 2**: Foundation + US2 + US3 — the header rewrite and the sheet (the bulk of the UX change).
3. **Increment 3**: US5 — palette presets, admin screen, PDF, gate.
4. **Increment 4**: US4 — shared view theme.
5. **Close**: polish, full gate, owner side-by-side (SC-007).

## Format validation

All tasks use `- [ ] TNNN [P?] [USn?] description with path`; setup, foundational and polish tasks carry no story label; every user-story task names the exact file(s) it touches.

---

## Implementation notes (2026-10-23)

**Verification actually run**

| Suite | Command | Result |
|---|---|---|
| Frontend types | `cd frontend && npx tsc --noEmit -p .` | clean |
| Frontend unit (67 files) | `cd frontend && npm test` | 697 passed |
| Frontend build | `cd frontend && npm run build` | ok (pre-existing chunk-size warning) |
| CLI | `cd cli && uv run pytest` | passed (incl. the new `layout.theme` cases) |
| Backend lint | `cd backend && uv run ruff check app alembic tests` | passed |
| Backend palette + PDF | `uv run pytest tests/test_palette.py tests/test_pdf_layout.py tests/test_pdf_declarative_layout.py` | 42 passed |
| Backend appearance + share theme | `uv run pytest tests/test_appearance_api.py tests/test_share_theme.py` | 11 passed (real migration `0027`) |
| Backend `/api/config` | `uv run pytest tests/test_auth.py::test_public_config_and_health` | passed |
| e2e report page (Chromium 375) | `npx playwright test tests/e2e/report-params.spec.ts --project=chromium-375` | 6 passed (live apply = one request, chips, bottom sheet, axe both themes) |
| e2e i18n (Chromium 375) | `npx playwright test tests/e2e/i18n.spec.ts --project=chromium-375` | 5 passed (every screen and in-page view in English and Spanish, the sheet included) |
| e2e palette (Chromium 375) | `npx playwright test tests/e2e/appearance.spec.ts --project=chromium-375` | 2 passed (installation preset on the report page, per-report preview) |
| e2e sharing + shared theme (Chromium 375) | `npx playwright test tests/e2e/sharing.spec.ts --project=chromium-375` | 6 passed (theme toggle, forced first-load theme, PDF from any theme, the pre-existing share/email/schedule flows) |
| e2e report/reporters (Chromium 375) | `npx playwright test tests/e2e/{design,reporting,autorefresh,direct-report,views,layout,theme}.spec.ts --project=chromium-375` | 35 passed (SC-001 width assertion, live apply, TV mode, auto-refresh, declarative layouts, theme) |

Not run: the full backend suite (the external test database is ~180 ms per statement and the suite
is long) and the Firefox/WebKit projects (the Chromium 375 project covers the phone layout); SC-007's owner side-by-side (T055) stays open until the
owner reviews `Ventas y facturación` with `impacto` versus today.

**Deviation from the spec (T039/US5.3)** — the report's "Paleta" selector previews any preset for the
viewer and hands over the exact `layout.theme.palette` snippet to copy, but it does **not** write the
report definition: there is no endpoint that edits a report definition (`POST /api/workspace/*` only
validates/applies a new version), and principle IX requires definition changes to go through the
project editor and a validated workspace version. `layout.theme.palette` itself is implemented,
validated (CLI schema + checker) and honoured by the web, the shared view and the PDF.

**Other notes**

- The modal guard (`tests/unit/no-modals.test.ts`, feature 010) forbids `role="dialog"` anywhere, so
  the sheet is a named `region` with a heading, a focus trap while open and Esc-to-close; the axe
  runs above cover it in both themes.
- `ParamsPanel`/`useReportPanelCollapsed` and `ContextBlock` were deleted with their strings; the
  guide pages that mentioned "Filtros y controles"/"Consultado por" were updated, and a new
  `apariencia` topic documents the admin screen (`guide-drift` green).
- The PDF renderer resolves the **installation** preset too: every `pdf.render()` caller passes
  `palette.resolve(definition, palette.installation_preset(db))` (report API, shared view, previews
  and scheduled email).
