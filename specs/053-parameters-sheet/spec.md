# Feature Specification: Parámetros into the same sheet as Filtros

**Feature Branch**: `053-parameters-sheet`

**Created**: 2026-11-04

**Status**: Draft

**Input**: Owner, 2026-11-04, after using `/r/cripto-impacto` on `bi.getbizview.com`: **Filtros** opens
a right side sheet with a header, its sections and a sticky **Listo** — consistent and cheap.
**Parámetros** opens an inline card under the meta line that pushes the dashboard down: a large empty
area, **EXPORTAR** (PDF/CSV radio + "Generar reporte") on the right, and the four selects (Período,
Comparar con, Frecuencia, Paleta) along the bottom. Feature 030 FR-003 asked for **one** `ReportSheet`
with tabs *Filtros* and *Parámetros*; only the filters half of that decision was built.

**Builds on**: 030 (report page polish, FR-003/FR-004/FR-005), 047 (themes as data), 015/auto-refresh,
018 (sharing panels, untouched), 033 (help topics). Changes the report page and the shared report page
only: no data, metrics, report engine or backend contract change.

**Decisions taken here** (so the plan does not reopen them):

- **One sheet, two tabs.** `ReportSheet` grows a header tab strip (`role="tablist"`) and both actions
  in the row open it on their tab. Pressing the opener of the tab already shown closes the sheet
  (today's toggle), pressing the other switches without closing. The sheet keeps being a landmark
  `region` — never a dialog (constitution: views, not modals).
- **Parámetros tab is a column, not a row.** One control per row with the label above, in the order a
  reader thinks of them: Período (preset + custom range), Comparar con, Frecuencia de actualización,
  Paleta, Tema del reporte. The compact row of fields along the bottom is what made the panel
  unreadable and is removed.
- **Export leaves the sheet.** Downloading is an action, not a parameter: `Descargar PDF` and
  `Descargar CSV` join the actions row's `⋯` menu, whose caption keeps the one line that explained
  that the *applied* selection is exported. `Generar reporte` and the format radio disappear with
  `ExportSection`.
- **Paleta and Tema del reporte stay viewer-side and session-scoped, but in the URL** (`theme`,
  `mode`) so a reload, a shared tab and a chip keep the same view. They never write the report
  definition: declaring a palette is still an authoring action (047, IX).
- **The shared report page gets the same sheet.** A viewer sees the same two tabs; its Parámetros tab
  offers what that page already allowed (period, comparison) — no palette, refresh or mode, which a
  share link never offered.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Parámetros opens where Filtros opens (Priority: P1) 🎯

A reader on a laptop presses **Parámetros** and gets the same right-hand sheet as **Filtros**, with
**Parámetros** selected: the dashboard stays beside it and keeps updating as values change. Pressing
**Filtros** while it is open switches tab instead of stacking a second panel.

**Why this priority**: it is the reported defect — the inline card costs a screen of height, mixes
export with parameters and looks nothing like the panel next to it.

**Independent Test**: open `/r/<id>`, press both openers in any order; the same
`data-testid="report-sheet"` element is shown each time, with the pressed tab selected, and no
`data-testid="param-bar"` exists anywhere in the source.

**Acceptance Scenarios**:

1. **Given** the report page, **When** **Parámetros** is pressed, **Then** the sheet opens on the
   Parámetros tab, the numbers stay visible behind it, and the tab strip shows both tabs with
   `aria-selected` on Parámetros.
2. **Given** the sheet open on Parámetros, **When** **Filtros** is pressed, **Then** the same sheet
   shows the Filtros tab (no second sheet, no close-and-reopen flicker).
3. **Given** the sheet open on either tab, **When** that same opener is pressed again, **Then** the
   sheet closes and focus returns to the opener.
4. **Given** the inline parameters card of the current build, **Then** it no longer exists: no
   `ParamBar` component, no `param-bar` test id, no `EXPORTAR` / `Generar reporte` strings.

---

### User Story 2 - Every parameter has its own row and applies live (Priority: P1)

The Parámetros tab lists Período, Comparar con, Frecuencia de actualización, Paleta and Tema del
reporte, one per row with the label above; changing any of them updates the dashboard behind the
sheet after a 250 ms pause. **Limpiar** restores the report's defaults and **Listo** closes.

**Why this priority**: the same defect from the content side — four selects crammed in one row and an
export block competing for attention.

**Independent Test**: open the tab at 1280 px and at 375 px, change each control in turn; exactly one
data request per change, the URL carries the value, and the sheet stays open until **Listo**.

**Acceptance Scenarios**:

1. **Given** the Parámetros tab, **Then** the controls appear in the order Período, Comparar con,
   Frecuencia de actualización, Paleta, Tema del reporte, each with its label above and full width.
2. **Given** Período set to Personalizado, **Then** Desde/Hasta appear under it and an incomplete
   range is never requested.
3. **Given** Paleta, **Then** a swatch row shows the colours of the selected theme and the first
   option is **Usar la de la instalación**.
4. **Given** **Limpiar**, **Then** period, comparison and filters return to the report's defaults, the
   palette returns to the declared one, the theme mode returns to automatic, the chips disappear and
   the dashboard reloads once.
5. **Given** the report declares no theme (047 absent), **Then** the Tema del reporte row is not
   rendered.

---

### User Story 3 - Export is one menu away (Priority: P2)

Downloading leaves the sheet: `Descargar PDF` and `Descargar CSV` live in the actions row's `⋯`
menu, with one caption that says the applied selection is exported — or that it must finish loading.

**Acceptance Scenarios**:

1. **Given** the report is loaded, **When** `⋯` is opened, **Then** it lists `Descargar PDF` (when the
   report has a PDF) and `Descargar CSV` (when a table or ranking view has rows) plus the caption.
2. **Given** CSV is pressed, **Then** the downloaded file is that of the applied selection, as the
   card menu's CSV already is.
3. **Given** the report is still loading, **Then** the caption says so and the CSV item is absent.

---

### User Story 4 - The applied state is readable as chips (Priority: P2)

Under the meta line, next to the filter chips, one chip per non-default parameter:
`Período: Mes en curso`, `vs: período anterior`, `Paleta: contraste`, `Tema: oscuro`. Removing a chip
restores that parameter's default; the URL follows and a reload keeps the view.

**Acceptance Scenarios**:

1. **Given** a non-default period, **Then** its chip appears and the meta line's period text stays.
2. **Given** the chip is removed, **Then** the parameter returns to the report's default, the URL is
   rewritten and the dashboard reloads once.
3. **Given** the URL carries `period`, `compare`, `theme` or `mode`, **Then** the chips match it on the
   first paint and after a reload.
4. **Given** default values, **Then** no parameter chips are shown.

---

### User Story 5 - Phones and assistive technology (Priority: P1)

At 375 px the same sheet is a bottom sheet (≤72 % of the viewport, drag handle) with the tab strip at
the top; the two tabs are reachable, announce their state and their panel, Esc closes and focus
returns to the opener, and `prefers-reduced-motion` removes the transition.

**Acceptance Scenarios**:

1. **Given** 375 px, **When** either opener is pressed, **Then** the sheet occupies at most the bottom
   72 % with the tabs visible and the dashboard visible above.
2. **Given** the sheet, **Then** axe reports no serious or critical violation in either theme.
3. **Given** keyboard only, **Then** ArrowLeft/ArrowRight move between the tabs, Tab enters the panel,
   Esc closes and focus returns to the opener.
4. **Given** `prefers-reduced-motion: reduce`, **Then** the sheet opens without animation.

---

### Edge Cases

- The report declares a single comparison option: the row shows it read-only (today's behaviour) and
  no `vs` chip appears for it.
- `theme` or `mode` in the URL names a value the installation/report no longer has: it is ignored, no
  chip appears, and the declared/installed value applies.
- A filter id in the URL that the report no longer declares keeps its notice inside the Filtros tab.
- A share link opened on a phone with a period in the URL: the Parámetros tab shows it, the chip is
  under the title, and the sheet is closed on first paint.
- The sheet open while the data request fails: the tab stays open, the alert is visible behind it and
  the last good numbers keep their place.
- TV mode (`tv=1`) has no actions row and therefore no sheet.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `ReportSheet` MUST render an optional tab strip in its header (`role="tablist"`, one
  `role="tab"` per tab with `aria-selected` and `aria-controls`, one `role="tabpanel"` with
  `aria-labelledby`), keep its heading for assistive technology, and remain a `region` — never a
  dialog.
- **FR-002**: The report page MUST have exactly one sheet; **Filtros** and **Parámetros** open it on
  their tab, pressing the open opener closes it and pressing the other switches tab.
- **FR-003**: The inline parameters card MUST be removed from the source tree (component, test id and
  its strings), in both the private and the shared report page.
- **FR-004**: The Parámetros tab MUST list, in this order and one per row: Período, Comparar con,
  Frecuencia de actualización, Paleta, Tema del reporte; the last is shown only when the report
  declares a theme.
- **FR-005**: Parameter changes MUST apply live with the existing 250 ms debounce and one request per
  change, and MUST be reflected in the URL.
- **FR-006**: **Limpiar** MUST restore the report's defaults for period, comparison, filters, palette
  and theme mode, and **Listo** MUST close the sheet.
- **FR-007**: The Paleta control MUST preview a preset live for this view, show a swatch row of the
  selected theme, offer **Usar la de la instalación** as the default option, and MUST NOT modify the
  report definition.
- **FR-008**: The actions row's `⋯` menu MUST offer **Descargar PDF** and **Descargar CSV** for the
  applied selection, with one caption line; **Generar reporte** and the format radio MUST be gone.
- **FR-009**: Under the meta line, chips MUST represent each non-default parameter (period,
  comparison, palette, theme mode) next to the filter chips, removable, with the same URL and reload
  behaviour as filters.
- **FR-010**: On phones the sheet MUST remain a bottom sheet of at most 72 % height with the tab strip
  at the top and the drag handle, and the dashboard MUST stay visible above it.
- **FR-011**: Keyboard: ArrowLeft/ArrowRight move between tabs, Esc closes, focus returns to the
  opener, and `prefers-reduced-motion` disables the transition.
- **FR-012**: The palette (`theme`) and theme mode (`mode`) MUST be read from and written to the URL,
  validated against what the installation/report offers, and never persisted to the report.
- **FR-013**: The shared report page MUST use the same sheet with the same two tabs, offering only the
  parameters that page already allows.
- **FR-014**: A help topic **Parámetros y filtros del reporte** (033) MUST describe the two tabs, the
  chips and where export lives, in Spanish and English.

### Key Entities

- **Report sheet tab**: `id` (`filters` | `params`), label, panel content, selected state.
- **Report selection**: period, custom range, comparison — already in the URL (`period`, `from`, `to`,
  `compare`) and unchanged.
- **Viewer view state**: palette preset (`theme`) and light/dark (`mode`), URL-only, validated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: One sheet element in the report DOM at any moment; zero `param-bar` elements.
- **SC-002**: Changing any parameter issues exactly one data request (debounced), verified by the
  existing request counter.
- **SC-003**: At 375, 768, 1280 and 1920 px in both themes the report page has no horizontal scroll,
  the sheet fits its viewport share, and axe reports no serious or critical violation.
- **SC-004**: A reader goes from opening Parámetros to a changed period and a closed sheet in three
  interactions (open, choose, Listo), with the chip visible after closing.
- **SC-005**: Reload after a change keeps period, comparison, palette and mode.

## Assumptions

- 030's filter sheet, its focus handling and its live-apply debounce are correct and are reused, not
  rewritten.
- 047's `viewerMode`/`readViewerMode`/`writeViewerMode` stay the storage for the session choice; the
  URL is added as the source of truth for this view.
- The actions row keeps its current rule: Filtros and Parámetros visible, everything else in `⋯`.
- No backend change: the data, filter-options and PDF endpoints already answer for the applied
  selection.

## Decisiones tomadas (modo autónomo)

- [specify] decision — pressing the opener of the tab already shown closes the sheet, because that is
  today's behaviour for Parámetros and the e2e already asserts the toggle; the alternative (never
  close from the opener) would remove the only close control next to the tabs.
- [specify] decision — `theme` and `mode` go in the URL, because the brief asks chips and reload
  behaviour "as for filters" and a chip that cannot be reloaded is a lie; they remain view-only.
- [specify] decision — the shared page gets the two tabs but not palette/refresh/mode, which that page
  never offered; adding them would widen a share link's power without a request.
- [specify] decision — `Tema del reporte` is hidden when the report declares no theme: there is
  nothing to override, and an always-present control would need a fourth state ("default").
- [clarify] decision — **Listo never loses a change**: a pending valid draft is applied when the sheet
  closes or unmounts, because the debounce timer dies with the panel and a reader that changes a
  select and closes immediately would otherwise see the old numbers.
- [clarify] decision — the Parámetros footer holds **Limpiar** (secondary) and **Listo** (primary);
  the Filtros tab keeps **Limpiar todo** inside its panel, as it is today, so the two tabs do not
  rearrange a control readers already know.
- [clarify] decision — parameter chips are shown all at once (at most four: period, comparison,
  palette, mode) and the filter chips keep their "+N más" overflow into the Filtros tab; one overflow
  rule per kind avoids a second "more" path with a different target.
- [clarify] decision — removing the `Tema` chip clears the stored viewer mode for that report as well
  (`writeViewerMode(id, null)`), so "default" means default on the next visit too, not just now.
- [clarify] decision — `Frecuencia de actualización` keeps its existing per-report storage
  (`useAutoRefreshMode`), not the URL: a refresh cadence is a device/reader preference, not part of a
  shared link, and the brief lists chips for period, comparison and palette only.
- [analyze] decision — `ParamsForm` loses `variant="bar"` entirely instead of keeping an unused
  option: it existed only for the inline card that goes away, and a dead prop would be a second way
  to lay the panel out.
- [analyze] decision — the `⋯` caption is one line chosen from the applied-selection state
  (`exportCaptionApplied` / `exportCaptionLoading`), not a per-item caption: the sentence describes
  the pair of downloads, and repeating it twice in the menu would be noise.
- [converge] decision — the brief asked for "snapshots at 375/768/1280/1920 in both themes"; this
  repository has no visual-snapshot baseline (no `toHaveScreenshot` anywhere), so the same claim is
  asserted in `report-params.spec.ts` with the tooling it does have: the sheet inside the viewport,
  the dashboard visible behind it, no horizontal scroll, and axe clean at each width and theme.
- [converge] decision — the e2e suite needs a live backend that rebuilds a throwaway schema (minutes
  over the external database), so this run verifies with `tsc`, the full unit suite, `npm run build`
  and the guide tests; the updated Playwright specs are part of the deliverable but were not executed
  here.
