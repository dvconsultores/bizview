# Feature Specification: Mobile fixes, round 2

**Feature Branch**: `062-mobile-fixes-round-2`

**Created**: 2026-11-09

**Status**: Draft

**Input**: Owner, 2026-11-09, from an Android phone (360 × 780 CSS px, light theme): five defects left
over after 056b and 059 — the two sign-in providers share a row, the Filtros | Parámetros sheet is
still not full screen and its footer covers the last control, a maximized KPI is titled with the
component id (`k_ventas`) and its header wraps to three lines, a maximized donut prints its title one
letter per line while the card shows no ring at all on the phone, and the source form's action block
floats over the fields.

## Context

059 fixed the sign-in page and the sheet against measurements at 393 px; 056b gave every card a
maximized view. Both were verified with the tools of their time, and both left defects that only a
360 px screen with a long title exposes:

- the provider row was a deliberate 059 decision (two providers side by side, short labels) that the
  owner now wants reversed: one provider per row, always;
- the sheet is `h-dvh` in code, but the *content* it hosts still uses the desktop card rhythm, and the
  sticky footer is laid out as a sibling of a `flex-1` body without reserving its height, so on a
  short screen the last control ends under it;
- `maximizedTitle()` falls back to `t.layout.maximize(id)` — a developer's identifier shown to a
  reader — and the dialog header is a single `flex-wrap` row, so a long title pushes the actions to a
  second and third line;
- `PieChart` hard-codes a 240 px ring and ignores the width `ChartCard` measures, and the dialog
  header's `min-w-0 flex-1` child is squeezed to zero by non-shrinking buttons plus
  `[overflow-wrap:anywhere]`, which is what turns a title into one letter per line;
- the source form kept `sticky bottom-20` from before the shell had a bottom tab bar, so on the phone
  the bar floats over the fields it is meant to save.

This feature fixes the five defects, and adds the measurements that would have caught them: a sweep of
the main routes at 360 × 780 and 393 × 851 in both themes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Two providers, two rows, on every screen (Priority: P1)

A person who signs in with Google or Telegram sees both options stacked, each as a full-width button
48 px high with its icon on the left, at phone and desktop widths alike.

**Independent Test**: render `/ingresar` at 360 px and at 1280 px with both providers enabled; the two
buttons are one per row, the same width as the form, and the label is the full sentence.

**Acceptance Scenarios**:

1. **Given** both providers are enabled and a 360 × 780 viewport, **When** `/ingresar` renders, **Then**
   `Continuar con Google` and `Ingresar con Telegram` are two full-width buttons stacked, each at least
   44 px high, with no shared row.
2. **Given** the same page at 1280 px, **Then** the two buttons are still stacked and full width of the
   form column.
3. **Given** only one provider is enabled, **Then** that button is full width with the full label.

### User Story 2 - The sheet on a phone is the whole screen, and its last control is reachable (Priority: P1)

A reader opens **Filtros** on a phone: the sheet covers the viewport, the header carries the two tabs
and **×**, the body scrolls, and the footer sits at the bottom with the safe-area filled in. The last
control can be scrolled into view above the footer.

**Independent Test**: at 360 × 780, open the sheet and measure: panel height equals the viewport, the
footer is visible, the body's scroll can reach the last control without it being covered.

**Acceptance Scenarios**:

1. **Given** a 360 × 780 viewport, **When** the sheet opens, **Then** its height equals
   `window.innerHeight` (100 dvh), there is no drag handle, and the footer is on screen.
2. **Given** the sheet is scrolled to its end, **Then** the last control's bottom edge is above the
   footer's top edge (the body reserves the footer's height).
3. **Given** the phone's back button, **When** it is pressed, **Then** the sheet closes and focus
   returns to the control that opened it.
4. **Given** the Parámetros tab, **Then** each control has exactly one label (no repeated section
   title), controls are at least 44 px high and 12 px apart, **Período** and **Comparar con** share one
   two-column row from 320 px, and **Paleta** and **Tema** are chip rows.

### User Story 3 - A maximized card is titled with what the reader sees (Priority: P1)

A reader presses **Ampliar** on a KPI or a chart and the dialog's header shows the card's own title on
one line, with the arrows, CSV, PNG and close buttons on the same row, and the period and filter chips
on a second row.

**Independent Test**: maximize a KPI whose metric has the label "Ventas" and a chart component with a
title; the header shows those, never `k_ventas`.

**Acceptance Scenarios**:

1. **Given** a KPI component bound to a metric, **When** maximized, **Then** the title is the metric's
   label.
2. **Given** a chart component with a localised `title`, **Then** the title is that text.
3. **Given** a component with no title of its own but a bound view with one, **Then** the view's title
   is used; given neither, the metric label; given neither of those, a text component's first words.
   The component id is never shown.
4. **Given** a 360 px viewport and a long title, **Then** the title occupies at least half the
   header's width, stays on one line (`scrollHeight === clientHeight`) and the actions keep their
   44 px targets. The brief asked for 60 %; that is arithmetically impossible at 360 px once three
   44 px actions and their gaps are subtracted (the header is 328 px, the actions ~140 px), so the
   measurable form of the requirement is "half the header, one line, never stacked".

### User Story 4 - A pie or donut is readable on a phone (Priority: P1)

A reader sees the donut on the dashboard at 360 px: the ring is drawn at the card's width, the legend
is below it, and nothing is clipped. Maximized, the ring grows but still leaves room for the legend.

**Independent Test**: at 360 px, the dashboard's donut card contains an `<svg>` at least 200 px wide and
the maximized one at least 300 px, in light and dark themes.

**Acceptance Scenarios**:

1. **Given** a 360 px viewport, **When** the dashboard renders a pie or donut, **Then** the ring's
   width is `min(240, containerWidth − 32)` and the legend is below it (`flex-col`), each row showing
   the full name, the value and the share.
2. **Given** the same card maximized, **Then** the ring is `min(containerWidth − 32, 60 vh, 520 px)` and
   the legend is below it on a phone.
3. **Given** a card whose data has not arrived, **Then** the card keeps a minimum height so the ring is
   not laid out at zero and does not jump when the data lands.

### User Story 5 - The source form's actions scroll with the form (Priority: P1)

A super user edits a source on a phone: the fields are not covered by anything, and at the end of the
form there are **Guardar**, **Probar conexión** and, separated, **Eliminar fuente**.

**Independent Test**: open `/admin/fuentes/nueva` at 360 × 780 and assert no stickily or fixed
positioned element inside the form, and that the actions follow the last field.

**Acceptance Scenarios**:

1. **Given** the source form on a phone, **Then** no element inside the form is `position: sticky` or
   `fixed`, and the actions block comes after the last field in document order.
2. **Given** the actions, **Then** they are ordered **Guardar**, **Probar conexión**, **Eliminar
   fuente** (destructive, ghost, 24 px separated), each full width on phones, with 16 px of clearance
   above the bottom tab bar (`pb-safe`).
3. **Given** any other admin form that copied the floating bar, **Then** it has the same static
   treatment; a test refuses `sticky bottom-20` anywhere in `src/`.

### Edge Cases

- A viewport narrower than 320 px: the period row falls back to one column, nothing overflows.
- A maximized card with no title of any kind: the dialog shows the report's own title, never the id.
- A pie with a single slice: still the circle path, sized by the same measurement.
- A very long metric label: truncated with `title=` carrying the full text.
- The on-screen keyboard open on the sheet: the body still scrolls and the footer stays reachable.
- Dark theme: the ring's slice colours and the legend text keep their contrast (existing tokens).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `/ingresar` MUST render enabled providers as one full-width button per row at every
  width, 48 px high, icon left, with the full labels `Continuar con Google` / `Ingresar con Telegram`.
- **FR-002**: the provider column MUST be spaced `space-y-3` and MUST NOT use a two-column grid; the
  short labels and the `compact` variant MUST no longer be reachable.
- **FR-003**: below 640 px the sheet MUST be `100dvh` with no drag handle, a header with the tab strip
  and the close button, a scrollable body and a sticky footer.
- **FR-004**: the sheet body MUST reserve the footer's height, so the last control can be scrolled
  fully above it; the footer MUST pad with `env(safe-area-inset-bottom)`.
- **FR-005**: the sheet's controls MUST follow 059's density: one label per control, 44 px controls,
  12 px gaps, **Período** + **Comparar con** in one row from 320 px, **Paleta** and **Tema** as chip
  rows.
- **FR-006**: `maximizedTitle()` MUST resolve, in order, the component's localised `title`, the bound
  view's `title`, for `kpi` the metric's `label`, for `text` its first words — and MUST never return
  the component id or `Ampliar «…»`.
- **FR-007**: the dialog header MUST be a two-row grid: title (truncated, `title=` full text, 18 px)
  plus actions on row one, the chips on row two; the title MUST NOT wrap and the chips MUST NOT
  displace the actions.
- **FR-008**: the pie/donut MUST size itself from its container (`min(240, width − 32)` in a card,
  `min(width − 32, 60 vh, 520)` maximized), measured with a `ResizeObserver` on that container, never
  from `window`.
- **FR-009**: below 640 px the pie/donut legend MUST sit below the ring; above it, beside it.
- **FR-010**: the source form's actions MUST be static (no `sticky`, no `fixed`, no blur bar), ordered
  **Guardar**, **Probar conexión**, **Eliminar fuente**, full width on phones, with `pb-safe`.
- **FR-011**: every other admin form that carried the floating action bar MUST get the same treatment.
- **FR-012**: no `<h1>`/`<h2>` inside a flex row may rely on `writing-mode` or wrap without `min-w-0`;
  a unit test MUST refuse `sticky bottom-20` in `src/` and any `writing-mode` use.

### Key Entities

Not applicable: no data model changes. The composition of a maximized card's title is the only new
rule, and it reads `layout.web.components[].title`, the bound view's `title` and the metric catalogue.

## Success Criteria *(mandatory)*

- **SC-001**: at 360 × 780 and 393 × 851, in light and dark themes, no main route scrolls horizontally
  and no element is wider than the viewport.
- **SC-002**: the five defects are each covered by an automated test that fails on the previous code.
- **SC-003**: the maximized header's title is at least 60 % of the header's width at 360 px and is one
  line high.
- **SC-004**: the dashboard's donut renders an `<svg>` ≥ 200 px at 360 px, and ≥ 300 px maximized.
- **SC-005**: no `sticky bottom-20` remains in `frontend/src`.

## Assumptions

- The phone viewport is 360 × 780 CSS px (the owner's device) and 393 × 851 (059's); both are checked.
- The report's own `title` is a safe last resort before any id, since every reachable report has one.
- Fixing the sheet's footer reservation is a CSS/layout change inside `ReportSheet`, not a redesign of
  the tabs.
