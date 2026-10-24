# Feature Specification: Report page polish — width, parameters, filters, theme, impact palette

**Feature Branch**: `030-report-page-polish`

**Created**: 2026-10-23

**Status**: Draft

**Input**: Owner, 2026-10-23, after reviewing the live report `Ventas y facturación` on
`bi.getbizview.com` (desktop and the shared mobile view): (1) the web page has too much left/right
margin — use the app standard; (2) the parameters block is invasive — hide it behind a button;
(3) decide the best modern option for filters (modal, new view, inline); (4) the shared view should
let the viewer switch to light theme too; (5) the dashboard needs more impactful colours, with a few
palette options the super user can set and save, defaulting to a modern high-impact look like the
Claude-generated dashboard shown as reference.

**Builds on**: 010 (visual system), 005/011 (report definition), 026 (declarative layouts), the shared
view (`/s/<token>`), PDF export. Does not change data, metrics or the report engine.

**Decisions taken here** (so the plan does not reopen them):

- **Filters UX (item 3)**: not a modal (feature-010 rule, constitution "views not modals"), not a
  separate page (loses the numbers while you filter). A **non-blocking side sheet** on desktop (slides
  from the right, 360px, the dashboard stays visible and updates live) and a **bottom sheet** on
  phones (drag handle, 70% height, dashboard visible above). Applied filters appear as removable
  chips under the title. This is what the reference dashboards from Claude, Linear and Vercel do and
  is the most direct answer to "modern".
- **Parameters (item 2)**: collapsed by default into a single compact **meta line** under the title
  (period · compared with · updated · viewed by) plus one **"Parámetros"** button that opens the same
  side/bottom sheet on its "Parámetros" tab. Actions (PDF, share, email, scheduled sends, TV mode)
  move to an **actions row** aligned right of the title: icon buttons with labels on desktop, an
  overflow "⋯" on phones. The big "Parámetros del reporte" card disappears.
- **Palette (item 5)**: semantic roles only (026 FR-005), resolved from a named **palette preset**
  chosen per installation with per-report override. Presets ship with the product; the super user
  picks and saves, never types hex codes. Default preset is the new high-impact one.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The page uses the app's width (Priority: P1) 🎯

On desktop the report content spans the same container as the rest of the app (Tableros,
Administración), not a narrower centred column with wide empty margins.

**Independent Test**: at 1920px, 1440px and 1280px the report content width equals the width of
the Tableros list on the same viewport; at 375px the gutter is 16px on each side.

**Acceptance Scenarios**:

1. **Given** the report page, **When** opened at any desktop width, **Then** its content container is
   the app standard container (same max-width and gutters as other pages), and KPI tiles fill the
   row (4 across ≥1280px, 2 across tablets, 1–2 on phones per 026).
2. **Given** TV mode, **Then** the content uses the full width with the TV gutters already defined.
3. **Given** the shared view, **Then** it uses the same container rules.

---

### User Story 2 - Parameters out of the way, one tap away (Priority: P1)

The reader sees title, one meta line and the numbers. "Parámetros" opens the sheet; the sheet shows
period, comparison, refresh time and the report's own options; changes apply live and close with
"Listo".

**Acceptance Scenarios**:

1. **Given** the report opens, **Then** no parameters card is shown; under the title there is one meta
   line: `Año en curso · 1 ene – 23 oct 2026 · vs 2025 · Datos 23 oct 20:00`, truncating gracefully on
   phones (period first, the rest in a second line).
2. **Given** "Parámetros" is pressed, **Then** the sheet opens on the "Parámetros" tab with period,
   comparison and report options; the dashboard remains visible and updates as values change.
3. **Given** the actions row, **Then** Descargar PDF, Compartir, Enviar por correo, Envíos programados
   and Modo TV are icon+label buttons on desktop and collapse into "⋯" on phones; keyboard reachable,
   WCAG AA.
4. **Given** the "Consultado por" field, **Then** it moves out of the page into the PDF footer and the
   audit; it is not shown on screen.

---

### User Story 3 - Filters as a side sheet with chips (Priority: P1)

**Acceptance Scenarios**:

1. **Given** "Filtros" is pressed (actions row or the meta line), **Then** the sheet opens on its
   "Filtros" tab: one control per declared filter, search inside long lists, "Limpiar" and "Listo".
2. **Given** filters are applied, **Then** removable chips appear under the meta line
   (`Estatus: pagada ×`), and the URL carries the state so it can be shared and restored.
3. **Given** a phone, **Then** the sheet is a bottom sheet with a drag handle; the dashboard stays
   visible above it and updates live.
4. **Given** a filter change, **Then** charts animate the transition (≤300 ms) and respect
   `prefers-reduced-motion`.

---

### User Story 4 - Shared view: light and dark (Priority: P2)

The shared page (`/s/<token>`) gets a theme toggle next to the language toggle; default follows the
viewer's system; the choice persists in the viewer's browser.

**Acceptance Scenarios**:

1. **Given** the shared view, **Then** the header shows `Español | English` and a sun/moon toggle;
   switching re-themes instantly with no reload.
2. **Given** the sharer chose a theme when creating the link (optional), **Then** the link opens in
   that theme the first time; the viewer can still switch.
3. **Given** a PDF download from the shared view, **Then** the PDF uses the light theme always
   (print-friendly) regardless of screen theme.

---

### User Story 5 - Impact palette, presets, saved (Priority: P1)

Dashboards look vivid and intentional out of the box. The super user can pick a preset per
installation in Administración → Apariencia, override it per report in the report's "Parámetros"
sheet (saved on the report, not the viewer), and the PDF follows the same preset.

**Acceptance Scenarios**:

1. **Given** a fresh installation, **Then** the default preset is **"Impacto"**: saturated primary
   for the main series, a distinct accent per secondary series, bold KPI numerals (display size,
   tight tracking), delta badges in strong positive/negative colours, subtle neutral grid, cards with
   stronger surface contrast in dark mode — in the spirit of the reference dashboard.
2. **Given** Administración → Apariencia, **Then** the super user sees preset cards with a live mini
   dashboard preview (KPI + bar + line) in both themes and picks one: `Impacto` (default), `Clásico`
   (today's look), `Monocromo` (brand primary shades), `Contraste alto` (AA+ for TV/projectors),
   `Daltónico` (Okabe–Ito-based categorical set). Saving applies to every report without override.
3. **Given** a report's Parámetros sheet, **Then** a "Paleta" selector (same presets, "Usar la de la
   instalación" default) lets the super user override for that report; saved on the report
   definition as `layout.theme.palette`, so it travels with the workspace version and the PDF.
4. **Given** any preset, **Then** categorical series stay distinguishable in both themes
   (contrast ≥3:1 against the card surface, adjacent series ΔE sufficient), text stays AA, and the
   semantic roles `positive`/`negative`/`neutral` keep their meaning; validated by an automated
   palette test in the frontend suite (the dataviz palette check), run for every preset × theme.
5. **Given** the PDF export, **Then** it renders with the report's effective preset in light theme.

### Edge Cases

- A report with many filters (10+): the sheet groups them under collapsible headings; chips wrap
  to two lines, then "+N más" opens the sheet.
- Deep link with filters for a filter that no longer exists: ignored with a one-line notice.
- Very long period labels in English/Spanish: the meta line truncates the middle, never the dates.
- TV mode: filters and parameters sheets are disabled; actions row hidden; palette applies.
- Installation branding with a primary colour that clashes with a preset: presets derive series
  colours from fixed hues, only `primary` role follows branding; the automated check flags a clash
  and falls back to the preset's own primary for charts.
- Shared view theme toggle with the sharer's forced theme: viewer's choice wins after the first
  load; stored per browser only (localStorage, try/catch).
- Reduced motion: no sheet slide animation, no chart transitions.

## Requirements *(mandatory)*

### Layout
- **FR-001**: The report page and the shared view use the app standard container (`max-w` and gutters
  shared with Tableros/Administración via one layout component); no page-specific margins. Phones:
  16px gutters, no horizontal scroll.
- **FR-002**: Header = title, description, meta line, applied-filter chips, actions row. The
  "Parámetros del reporte" card is removed.

### Sheet (filters + parameters)
- **FR-003**: One `ReportSheet` component with tabs "Filtros" and "Parámetros": right side sheet
  ≥1024px (360px, non-modal, dashboard interactive behind), bottom sheet below (drag handle, 70%
  height, swipe to close). No modal dialogs. Focus trap only while open; Esc closes; returns focus to
  the opener.
- **FR-004**: Filter and parameter state live in the URL (query string) and apply live with debounce
  (250 ms) through the existing report data API; chips reflect the URL.

### Actions
- **FR-005**: Actions row: Filtros, Parámetros, Descargar PDF, Compartir, Enviar por correo, Envíos
  programados, Modo TV — icon+label ≥1024px, icons with tooltips on tablets, "⋯" overflow on phones.
  "Consultado por" removed from the page (kept in PDF footer and audit).

### Shared view theme
- **FR-006**: Shared view gains a theme toggle (system default, persisted per browser) beside the
  language toggle; the share dialog gains an optional "Abrir en tema claro/oscuro" for the first load.
  PDFs from any view render light.

### Palette presets
- **FR-007**: Presets are product data (`frontend/src/theme/palettes/*.json`, mirrored for the
  backend PDF renderer in `backend/app/reports/palettes/`), each defining semantic roles for light
  and dark: `primary`, `series[1..8]`, `positive`, `negative`, `neutral`, `grid`, `surface`,
  `kpi_text`, `kpi_delta_bg`. No hex codes in report definitions (026 FR-005 holds).
- **FR-008**: Installation default preset in Administración → Apariencia (setting `palette_preset`,
  default `impacto`); per-report override `layout.theme.palette` in the report definition (validated
  by the 026 schemas against the preset list); effective preset = report override or installation.
- **FR-009**: Preset `impacto` also sets typography and surfaces for KPI tiles: display-size numerals,
  tight tracking, delta badges with filled backgrounds, stronger card elevation in dark. Other
  presets keep current typography.
- **FR-010**: An automated palette check (contrast of series vs surface ≥3:1, text AA, adjacent
  series distinguishable, positive/negative not confusable) runs in CI for every preset × theme; a
  failing preset cannot ship.
- **FR-011**: The PDF renderer resolves the same effective preset (light variant).

### Quality
- **FR-012**: WCAG AA, keyboard and screen-reader support for sheet, chips, toggles and presets
  picker; `prefers-reduced-motion` respected; Spanish strings in `es.ts` (English in the shared view
  where it already exists).

## Success Criteria *(mandatory)*

- **SC-001**: Report content width equals the Tableros container at 1280/1440/1920px; 16px gutters at
  375px (visual tests).
- **SC-002**: First screen of a report at 375×667 shows title, meta line and at least two KPI tiles
  without scrolling (today it shows the parameters card only).
- **SC-003**: Filter change → charts updated in under 500 ms on the demo dataset, sheet open the whole
  time (e2e).
- **SC-004**: Every preset × theme passes the palette check; 0 hex codes in any report definition in
  the repo (lint).
- **SC-005**: Shared view theme toggle works with no reload and persists across reloads in the same
  browser; PDF always light.
- **SC-006**: Lighthouse accessibility ≥95 on the report page and the shared view, both themes.
- **SC-007**: Side-by-side review of `Ventas y facturación` with preset `impacto` vs today, in both
  themes, approved by the owner once (recorded in the PR).

## Constitution check

- I (mobile-first): bottom sheet, 16px gutters, first screen shows numbers; Tailwind only.
- II/VI: no data changes; same report API.
- V: no new stack component (sheet, chips and presets are product components; Recharts/ReportLab
  unchanged). If a headless sheet primitive is wanted, it is a supporting library listed in the plan.
- VII: presets are product data; branding stays configuration.
- IX: palette override is a declarative field validated by schema.
- Constraints: PDF by backend; html2canvas untouched; no modals.

→ PASS.

## Assumptions

- The app already has a standard container component or utility used by Tableros/Administración;
  if not, the plan introduces one and migrates those pages too (small).
- The reference dashboard's look (large numerals, saturated bars, dark surfaces with strong contrast)
  is the target for `impacto`; exact hues are chosen in the plan against the palette check, not
  copied from the reference.
- Shared view already has the language toggle and token expiry; this spec only adds theme.
