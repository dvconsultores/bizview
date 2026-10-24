# Implementation Plan: Report page polish — width, parameters, filters, theme, impact palette

**Branch**: `030-report-page-polish` | **Date**: 2026-10-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/030-report-page-polish/spec.md`

## Summary

Five owner-visible changes to the report page and the shared view, plus the palette system that
gives them their look:

1. The report page stops drawing its own narrower column (`mx-auto max-w-7xl`) and inherits the app
   container the shell already applies to Tableros/Administración (`mx-auto max-w-screen-2xl
   sm:px-5 lg:px-4`); the public shared view gets the same container through one shared constant.
2. The "Parámetros del reporte" card (today a 20 rem sidebar) disappears. What is left is a compact
   meta line (period · compared with · updated) and an **actions row** (Filtros, Parámetros, PDF,
   Compartir, Correo, Envíos, Modo TV).
3. Filters move into a **non-blocking sheet** (`ReportSheet`): right side sheet ≥1024 px, bottom
   sheet below, state in the URL, live apply with a 250 ms debounce, applied filters as removable
   chips. Parameters were moved to a small inline panel after the owner's review (see §3b).
4. The shared view (`/s/<token>`) gets a light/dark toggle beside the language toggle; the share
   dialog gains an optional first-load theme; PDFs stay light.
5. Charts and KPIs become vivid and intentional through **palette presets** (product data, JSON),
   chosen per installation in a new Administración → Apariencia screen and overridable per report
   (`layout.theme.palette`), resolved by the web renderer, the shared view and the ReportLab PDF
   from the same data, and gated by an automated palette check.

No data, metric, report-engine or API-shape change: the same `/api/reports/*`, `/api/shared/*` and
share links. Backend work is the palette data + resolution for the PDF, the installation appearance
setting and one nullable `share_link` column.

## Technical Context

**Language/Version**: Python 3.11+ (backend, PDF, CLI checker) · TypeScript 5.9 / React 19 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic, ReportLab, jsonschema (backend/CLI);
React 19, Vite 8, Tailwind CSS 3.4, react-router 7, lucide-react (frontend). **No new dependency**:
the sheet, chips, tooltips and the palette check are product code (constitution V, the "supporting
libraries" list stays empty).

**Storage**: PostgreSQL — one new singleton table `appearance_settings` (installation default
preset) and one nullable column `share_link.theme`. Palette presets themselves are product data
(JSON files in the repo), not rows.

**Testing**: `pytest` (`backend/tests`, `cli/tests`), `vitest` (`frontend/tests/unit`), Playwright
(`frontend/tests/e2e`). The palette check and the palette-mirror check are vitest tests, so they run
with `npm test` — the repository has no `.github/workflows/` directory today, so "CI" means the
release gate that runs the three suites (see `CONTRIBUTING.md`), plus `starter.py` locally.

**Target Platform**: mobile-first web (375 px first, 1280/1440/1920 px verified), TV mode, plus the
public shared view; PDF through the backend.

**Performance Goals**: filter change → charts redrawn in under 500 ms on the demo dataset with the
sheet open (SC-003); sheet open/close animation ≤300 ms; palette resolution costs no request (read
once from `/api/config`; the per-report override already rides in the report definition).

**Constraints**: WCAG AA; every preset must pass the palette check in both themes; 0 hex codes in
report definitions; PDF always light; `prefers-reduced-motion` respected; no modal dialogs; Spanish
and English strings for everything new.

**Scale/Scope**: 5 presets × 2 themes; 1 report page, 1 shared view, 1 new admin screen; ~12 changed
or new frontend modules, 4 backend modules, 1 migration (0027).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / constraint | How this plan honours it |
|---|---|
| I. Mobile-first, Tailwind only | The sheet is a **bottom sheet** at phone widths and the first screen carries title + meta line + KPIs (SC-002); no CSS files are added beyond token blocks in `src/index.css`; touch targets reuse `min-h-tap`. |
| II / VI. No data change | Untouched: same report API, same aggregates, no ETL, no report storage change. |
| V. Fixed stack | No stack component added, no library added. ReportLab keeps rendering PDFs; the SVG charts stay hand-rolled. |
| VII. One product, many installations | Presets are product data; **which** preset an installation uses is configuration (`appearance_settings`, set by the super user). No customer hues in code. |
| IX. Spec-driven reporting | The per-report override is a declarative field, `layout.theme.palette`, validated against the preset list by the CLI schema + checker (`cli/bizview_cli/report_layout.py`, `cli/bizview_cli/schemas/report.schema.json`); 026's "colour roles, never hex" rule is unchanged and still enforced. |
| Constraints | PDF by backend only (html2canvas untouched); no modal dialogs (the sheet replaces the phone `View`); all new strings in `es.ts` + `en.ts`; branding stays configuration — a clashing brand primary never overrides series hues (research R6). |

→ **PASS**, no violations to justify. Re-checked after Phase 1 (end of this file).

## Design

### 1. One container for every page (FR-001, US1)

Facts: [AppShell.tsx:291](../../frontend/src/components/AppShell.tsx:291) already centres the shell
content with `mx-auto max-w-screen-2xl sm:px-5 lg:px-4`, but
[ReportView.tsx:505](../../frontend/src/pages/ReportView.tsx:505) adds `mx-auto max-w-7xl` inside it
— 1280 px of content in a 1536 px container, which is the "too much margin" the owner saw. The
public [SharedDashboard.tsx:250](../../frontend/src/pages/SharedDashboard.tsx:250) lives outside the
shell and repeats `max-w-7xl`.

- New `frontend/src/lib/layout.ts` exports `APP_CONTAINER` (`mx-auto w-full max-w-screen-2xl`) and
  `APP_GUTTER` (`px-4 sm:px-5 lg:px-4`); `AppShell` composes them instead of the inline string.
- New `frontend/src/components/PageContainer.tsx` (a `div`/`header`/`main` wrapper using those
  constants) is used by the shell's `<main>` and by the shared view's header and main.
- `ReportView` drops its two `mx-auto max-w-7xl` wrappers and renders inside the shell container.
  TV mode keeps working: `useHideShellChrome` already swaps the main padding for full width.
- KPI row, charts and tables simply fill the wider container; no grid change (026 spans keep their
  meaning).

### 2. Header: title, meta line, chips, actions (FR-002, FR-005, US2)

`ContextBlock` today is a card titled "Parámetros del reporte" holding period/compared/updated/
viewed-by plus the action buttons. It becomes two flat pieces under the title, no card:

- `ReportMetaLine` — `Año en curso · 1 ene – 23 oct 2026 · vs 2025 · Datos 23 oct 20:00`, one line
  on ≥640 px, two lines on phones (period first), middle truncation that never cuts the dates; it
  also holds the applied-filter chips (`Estatus: pagada ×`) and a "+N más" overflow.
- `ReportActions` — Filtros (with the active count), Parámetros, Descargar PDF, Compartir, Enviar
  por correo, Envíos programados, Modo TV. Icon+label ≥1024 px, icon+`title` tooltip on tablets,
  everything but Filtros/Parámetros inside a "⋯" menu (`aria-haspopup="menu"`, roving focus — the
  pattern `CardMenu` already implements) on phones. Entitlements are unchanged: the share/email/
  schedule buttons keep their `user.role === "admin"` / `dashCode` / `emailAvailable` conditions.
- "Consultado por" leaves the screen in both pages (the prop stops being passed); the PDF keeps it
  through the existing `pdf.viewer` meta line
  ([pdf.py:151](../../backend/app/reports/pdf.py:151)) and the audit event is already recorded.
- `ParamsPanel.tsx` and `useReportPanelCollapsed` (only referenced by `ReportView`) are deleted, with
  their strings (`reportParams.collapse`, `reportParams.expand`).

### 3. `ReportSheet`: one sheet for filters and parameters (FR-003, FR-004, US2/US3)

`frontend/src/components/report/ReportSheet.tsx`, no library, no portal to a modal dialog:

- **Desktop ≥1024 px**: right side panel, 360 px wide, fixed to the right edge, **no backdrop**; the
  dashboard stays scrollable and interactive; open/close is a 200 ms translate (suppressed by
  `motion-reduce`).
- **Phones/tablets**: bottom sheet with a drag handle, `max-height: 70vh`, swipe-down and Esc close
  it; the dashboard above stays visible and updates live.
- **A11y**: `role="dialog"` + `aria-modal="false"` + `aria-labelledby`; focus moves into the sheet on
  open, Tab is trapped inside while it is open, Esc closes it and focus returns to the opener;
  clicking outside closes it on desktop. The trap releases when the sheet closes so the page is
  reachable again.
- **Tabs**: "Filtros" (one control per declared filter, search inside long lists, "Limpiar",
  "Listo") and "Parámetros" (period, comparison, auto-refresh, export format, "Paleta").
- **State**: filters/period/comparison keep living in the query string through the existing
  `lib/reportQuery` (`parseSelection`/`serializeSelection`, `setParams(..., { replace: true })`); the
  sheet only edits the same `ReportSelection`.
- **Live apply**: `ParamsForm` gains a `live` prop that debounces `onApply` by 250 ms (the current
  submit-on-apply behaviour stays for the "Aplicar" path the e2e flow uses); its period block and
  filter block become separately renderable so the sheet's two tabs do not duplicate the form.
- Unknown filter in the URL keeps today's behaviour (ignored) and the sheet shows the one-line
  notice required by the edge cases.

### 3b. Owner change (2026-10-24): parameters are a small inline panel, not a sheet tab

The owner reviewed the shipped page and asked for the parameters to be less invasive: "make it
hidden, it's invasive, it must show the dashboard, create a small control panel to show params".
As built:

- **Parámetros** toggles a compact panel (`ParamBar`, one row: Período · Comparar · Frecuencia ·
  Paleta · export format) inserted between the meta line and the dashboard. It overlays nothing and
  is closed by default; changes still apply live (250 ms) and the URL stays the state.
- **Filtros** keeps the sheet (`ReportSheet`), because the filter list needs the room. The sheet lost
  its tab list: it is a single "Filtros" panel now.
- The shared view follows the same pattern.

### 4. Chart transitions and reduced motion (US3.4, FR-012)

Charts are hand-rolled SVG (`components/report/charts/*`). Geometry morphing is not available, so a
data change animates as a ≤300 ms fade/rise of the data layer keyed by the series signature, and
`motion-reduce:transition-none` (the class pair already used across the page) suppresses it. The
Playwright suite runs with `reducedMotion: "reduce"` (`playwright.config.ts`), so e2e never depends
on the animation.

### 5. Shared view theme toggle (FR-006, US4)

[SharedDashboard.tsx:278](../../frontend/src/pages/SharedDashboard.tsx:278) shows
`LanguageSwitcher compact` in the header and sits **inside** `ThemeProvider`
([App.tsx:53](../../frontend/src/App.tsx:53)), so `useTheme()` is already available; `setPreference`
writes `localStorage` only when nobody is signed in (`ThemeContext.tsx`: `if (!user) return`).

- `ThemeSwitcher` gains `compact` (two options: Claro/Oscuro) with the same roving-radio pattern as
  `LanguageSwitcher compact`; "system" is the initial value (resolved from the device until the
  viewer picks).
- The share dialog (`ShareLinksPanel`) gains an optional "Abrir en tema claro/oscuro" select; the
  value is stored on the share link (`share_link.theme`, nullable) and returned by
  `GET /api/shared/{token}`; the shared view applies it **once**, only when the viewer has no stored
  preference (`localStorage` miss), then the viewer's choice wins.
- PDFs from any view are rendered light: the backend renderer only ever uses the preset's `light`
  variant.

### 6. Palette presets (FR-007…FR-011, US5)

- **Data**: `frontend/src/theme/palettes/{impacto,clasico,monocromo,contraste,daltonico}.json`, one
  file per preset, `light` and `dark` objects with the roles `primary`, `series1…series8`,
  `positive`, `negative`, `neutral`, `grid`, `surface`, `kpi_text`, `kpi_delta_bg.{positive,negative}`
  and a `strategy` field (`categorical` | `sequential`) that tells the check which distinguishability
  rule applies. Contract: [contracts/palette-preset.md](./contracts/palette-preset.md).
  Byte-identical mirror in `backend/app/reports/palettes/` (the PDF renderer must not import from
  `frontend/`); a vitest test fails on drift.
- **Resolution**: effective preset = `definition.layout.theme.palette` (validated) ?? installation
  `appearance_settings.palette_preset` ?? `impacto`. The web gets the installation value from
  `/api/config` (`palette_preset`) once at boot; the per-report value rides in the report definition
  it already fetches. The PDF resolves the same order server-side.
- **Application (web)**: `frontend/src/theme/palette.ts` resolves the preset + current resolved theme
  into CSS custom properties on `<html>` (`--c-chart-1…8`, `--c-success*`, `--c-danger*`,
  `--c-chart-grid`, `--c-chart-label`, plus `--c-kpi-*`), so every existing token class
  (`fill-chart-3`, `text-success-strong`, …) keeps working and both the report page and the shared
  view re-theme without a reload. `data-palette="<id>"` on `<html>` lets `index.css` add the
  `impacto` typography/surface block (display numerals, tight tracking, filled delta badges, stronger
  dark elevation). The installation `primary` (branding) keeps feeding the interface `primary` role
  only — chart series always come from the preset (research R6).
- **Application (PDF)**: new `backend/app/reports/palette.py` loads the mirrored JSON, resolves roles
  to ReportLab colours for the **light** variant and replaces the hex constants in
  `pdf.py:21-24` and `pdf_layout.py:44-56`; `pdf.render()` and the declarative `Layout` carry the
  resolved palette (no hex in the layout, 026 FR-005 intact).
- **Presets and their verified numbers**: research R3–R5 (all five × two themes pass the check; the
  default `impacto` is fully specified there).
- **Gate**: `frontend/tests/unit/palette-presets.test.ts` — for every preset × theme: each series
  ≥3:1 against that theme's `surface` (≥7:1 for `contraste`), adjacent-series CIE76 ΔE ≥10
  (≥3.5 for the sequential `monocromo`), `positive`/`negative` distinct (ΔE ≥25) and ≥3:1,
  `kpi_text` AA (≥4.5:1), delta badge text ≥4.5:1 on its own background, `grid` subtle
  (<1.8:1 vs surface). It also asserts the backend mirror is identical and that no report-definition
  fixture in the repo carries a hex colour (SC-004).

### 7. Administración → Apariencia (FR-008)

- **Data**: `appearance_settings` singleton (id=1), `palette_preset` (check-constrained against the
  preset ids), `updated_at`/`updated_by` — the same shape as `telegram_settings`
  ([models.py:457](../../backend/app/models.py:457)). Migration `0027_appearance_palette`.
- **API**: `GET/PUT /api/admin/appearance` in new `backend/app/api/appearance.py`, guarded by
  `require_superuser`, audited (`appearance_updated`), CSRF as the other admin writes; the value is
  also exposed by `GET /api/config` as `palette_preset` for the web and the shared view.
- **Screen**: `frontend/src/pages/admin/Appearance.tsx` + a tile in `adminTiles.ts` and a route in
  `App.tsx`: preset cards with a live mini dashboard (KPI + bar + line) rendered in both themes,
  picked and saved by the super user. Strings in `es.ts`/`en.ts`.

### 8. Report definition contract (026 FR-005 holds)

`layout.theme.palette` (string, one of the preset ids) is added to
`cli/bizview_cli/schemas/report.schema.json` (`layout` object, `additionalProperties: false` stays),
to `cli/bizview_cli/report_layout.py` (`_enum` against the preset list, hex still refused by
`_LITERAL`) and to `frontend/src/api/types.ts` (`ReportDefinition.layout.theme?`). The report's
"Parámetros" tab shows the "Paleta" selector with "Usar la de la instalación" as the default; saving
goes through the existing report-definition update path (a new workspace version), so the choice
travels with the version and the PDF. Contract: [contracts/layout-theme.md](./contracts/layout-theme.md).

### Project structure (files this feature touches)

```text
frontend/
├── src/lib/layout.ts                    # NEW  app container + gutters
├── src/components/PageContainer.tsx     # NEW  shell/public container wrapper
├── src/components/AppShell.tsx          #      uses the container constants
├── src/components/ThemeSwitcher.tsx     #      + compact (Claro/Oscuro)
├── src/components/report/
│   ├── ReportSheet.tsx                  # NEW  side/bottom sheet, tabs
│   ├── ReportMetaLine.tsx               # NEW  meta line + chips (+N más)
│   ├── ReportActions.tsx                # NEW  actions row / "⋯" overflow
│   ├── ContextBlock.tsx                 #      split into meta line + chips (viewer gone)
│   ├── ParamsForm.tsx                   #      live apply + per-section render
│   ├── ParamsPanel.tsx                  # DELETED (replaced by the sheet)
│   ├── KpiGrid.tsx                      #      --c-kpi-* tokens
│   └── charts/*                         #      ≤300 ms data transition
├── src/pages/ReportView.tsx             #      container, header, sheet wiring
├── src/pages/SharedDashboard.tsx        #      container, theme toggle, filter sheet
├── src/pages/admin/Appearance.tsx       # NEW  preset picker
├── src/theme/palette.ts                 # NEW  preset resolution → CSS vars
├── src/theme/palettes/*.json            # NEW  product data (5 presets)
├── src/theme/ThemeContext.tsx           #      applies the effective palette
├── src/api/types.ts                     #      layout.theme, share theme, config
├── src/i18n/{es,en}.ts                  #      new strings
├── src/index.css                        #      impacto typography/surface block
├── tsconfig.json                        #      resolveJsonModule
└── tests/unit|e2e                       #      new tests (see below)

backend/
├── app/reports/palette.py               # NEW  preset load + role resolution (light)
├── app/reports/palettes/*.json          # NEW  byte-identical mirror
├── app/reports/pdf.py                   #      colours from the palette
├── app/reports/pdf_layout.py            #      colours from the palette
├── app/api/appearance.py                # NEW  GET/PUT /api/admin/appearance
├── app/api/health.py                    #      /api/config exposes palette_preset
├── app/api/sharing.py                   #      share theme on create
├── app/models.py                        #      AppearanceSettings, ShareLink.theme
├── alembic/versions/0027_appearance_palette.py  # NEW
└── tests/test_palette.py, test_pdf_*.py, test_share_theme.py  # NEW/extended

cli/
├── bizview_cli/schemas/report.schema.json  #    layout.theme
├── bizview_cli/report_layout.py            #    palette enum + no hex
└── tests/test_report_layout.py             #    extended
```

**Structure Decision**: web application monorepo — `frontend/` (React/Vite/Tailwind), `backend/`
(FastAPI/ReportLab, which by principle IV owns PDF code) and `cli/` (artifact schemas shared with the
backend). The palette data is duplicated `frontend/` ↔ `backend/` on purpose, kept in step by a test
rather than by a cross-package import.

### Data (migration `0027_appearance_palette`)

| Object | Change |
|---|---|
| `appearance_settings` | new singleton table: `id` (1), `palette_preset` (varchar + check against the preset ids), `updated_at`, `updated_by` FK `app_user` — same shape as `telegram_settings` |
| `share_link` | new nullable `theme` (`light`/`dark`, check constraint) |
| report definitions | no DB change; `layout.theme.palette` lives inside the versioned definition JSON |

### API

| Method | Path | Actor | Notes |
|---|---|---|---|
| GET | `/api/admin/appearance` | super user | `{palette_preset}` |
| PUT | `/api/admin/appearance` | super user | validates the preset id, audits `appearance_updated` |
| GET | `/api/config` | anyone | adds `palette_preset` (public: the shared view needs it) |
| POST | `/api/sharing/links` | admin | optional `theme` |
| GET | `/api/shared/{token}` | token holder | adds `theme` |

### Tests

- **vitest**: `palette-presets.test.ts` (the gate of FR-010 + SC-004 + mirror drift),
  `report-sheet.test.tsx` (tabs, live debounce, chips, focus/Esc/restore, reduced motion),
  `report-actions.test.tsx` (breakpoint collapse, entitlements), `shared-theme.test.tsx` (compact
  toggle persists, PDF stays light), `appearance-page.test.tsx` (picker saves), and updates to
  `params-form.test.tsx`, `layout-renderer.test.tsx`, `layout-charts.test.tsx`,
  `no-raw-colors.test.ts` (new tokens defined for both themes).
- **Playwright**: extend `report-params.spec.ts` (sheet open → change a filter → charts update with
  the sheet still open, 375 px and desktop), `sharing.spec.ts` (theme toggle in the shared view), new
  `appearance.spec.ts` (pick a preset, every report follows), plus the width assertions of SC-001 in
  `design.spec.ts`/`layout.spec.ts`.
- **pytest**: `test_palette.py` (role resolution per preset, light output, unknown preset rejected),
  extended `test_pdf_layout.py`/`test_pdf_declarative_layout.py` (colours come from the preset, no hex
  in the layout), `test_share_theme.py` (create with/without theme, shared payload),
  `test_appearance_api.py` (super user only, audit, `/api/config`).
- **CLI**: `test_report_layout.py` (accepts the 5 ids, rejects anything else, still rejects hex).

## Complexity Tracking

No constitution violations. One deliberate duplication: the five preset files exist in `frontend/`
and `backend/` (byte-identical, enforced by a test) because principle IV forbids the backend from
importing frontend assets and a shared package would be a new module for five data files.

## Post-design Constitution re-check

Re-evaluated after Phase 1 with the artifacts in place:
I (bottom sheet, phone-first, Tailwind only) ✔ · II/VI (no data change) ✔ · V (no new stack
component or library — the sheet, chips and picker are product components; ReportLab/SVG charts
unchanged) ✔ · VII (presets are product data, the installation picks one in the UI) ✔ ·
IX (`layout.theme.palette` is declarative and validated by the CLI schema + checker; hex still
refused) ✔ · Constraints (PDF by backend and always light, no modals, `es`+`en` strings, no secrets,
branding stays configuration) ✔ · Quality gates (AA, <500 ms filter update, palette check in the
suite) ✔ → **PASS**.
