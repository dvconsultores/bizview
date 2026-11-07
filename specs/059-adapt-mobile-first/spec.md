# Feature Specification: Mobile-first sign-in and filter sheet

**Feature Branch**: `059-adapt-mobile-first`

**Created**: 2026-11-07

**Status**: Draft

**Input**: User description: "Sign-in page and the Filtros/Parámetros sheet on phones — the language toggle covers the product name, the hero takes a third of the screen and the form overlaps it, the form does not fit one screen; the sheet opens at 72 % with a drag handle and greys out a quarter of the screen, every control repeats its section title, and the footer covers the last control."

## Context

Mobile first is the first principle of the product, and two screens on an Android phone (393 × 851 CSS
px, dark theme) do not meet it: the sign-in page needs scrolling to reach the providers, and a
quarter of the filter sheet is wasted on a greyed-out dashboard nobody can read at that size. Both
screens were designed at desktop widths and adapted with a breakpoint, instead of being designed at
360 px and widened.

This feature fixes the two screens and applies the same compact scale to the parts of the shell they
sit in: the top bar and the dashboard title block.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign in from a phone in one screen (Priority: P1)

A salesperson opens Bizview on their phone, picks their language, types their email and password and
presses **Ingresar** — or **Google** — without scrolling, with the product name and the organisation
visible at the top.

**Why this priority**: it is the first screen; a form the user has to hunt for is a product that does
not work on the device the product is for.

**Independent Test**: open `/ingresar` at 393 × 640 and confirm every control is reachable without a
scroll and the language toggle does not touch the header text.

**Acceptance Scenarios**:

1. **Given** a 393 × 640 viewport in dark theme, **When** `/ingresar` loads, **Then** the email,
   password, **Ingresar**, **Google** and **Telegram** controls are all visible without scrolling.
2. **Given** the same viewport, **When** the page renders, **Then** the language toggle sits below the
   header on the right and its bounding box does not intersect the product name or organisation.
3. **Given** a focused password field with the keyboard open, **When** the user types, **Then** the
   field and the **Ingresar** button remain visible (the page pans, it does not hide them).
4. **Given** only Google enabled, **When** the providers render, **Then** the button is full width;
   with both enabled they sit side by side.
5. **Given** a 1280 px viewport, **When** `/ingresar` loads, **Then** the layout is the two-column one
   of today.

---

### User Story 2 - Read and change the filters of a dashboard on a phone (Priority: P1)

A manager opens a dashboard on their phone, presses **Parámetros**, and sees a full-screen sheet with
the two tabs, four controls and a footer that never hides them.

**Why this priority**: the sheet is the only way to change what the numbers mean; a quarter of the
screen showing a greyed dashboard and two screens of scrolling for four controls make it unusable.

**Independent Test**: at 393 px open the sheet, confirm it is the full height of the window, the last
control is reachable, and the phone's back button closes it.

**Acceptance Scenarios**:

1. **Given** a 393 × 851 viewport, **When** the sheet opens, **Then** it covers the whole height
   (`100dvh`), has no drag handle, and its footer is visible with the last control focused.
2. **Given** the Parámetros tab, **When** it renders, **Then** each control has exactly one label
   (no section title repeated as a field label) and the four controls fit without scrolling at 393 ×
   851.
3. **Given** a change in any control, **When** 250 ms pass, **Then** the dashboard behind refreshes
   with the new value and **Listo** only closes.
4. **Given** the phone's back button, **When** it is pressed with the sheet open, **Then** the sheet
   closes and the dashboard keeps its state.
5. **Given** **Limpiar**, **When** pressed, **Then** every control returns to the report's defaults.

---

### User Story 3 - The shell fits a phone (Priority: P2)

The top bar shows the logo, the organisation, the theme toggle and the avatar; the dashboard title and
its actions fit without horizontal scrolling at 360 px.

**Why this priority**: the two screens above sit inside a shell that also wastes space and forces
scrolling.

**Independent Test**: at 360 px open `/`, `/r/<id>` and `/proyectos` and confirm no element is wider
than the viewport.

**Acceptance Scenarios**:

1. **Given** a 360 px viewport, **When** any main route renders, **Then** no element exceeds the
   viewport width.
2. **Given** the dashboard title block, **When** the description is long, **Then** it shows at most
   two lines with an ellipsis and the meta line wraps.
3. **Given** an actions row narrower than 420 px, **When** it renders, **Then** the buttons are icons
   with labels underneath.

---

### Edge Cases

- A 320 px viewport: the sign-in form still fits without horizontal scrolling; the language toggle
  wraps under the organisation instead of overlapping it.
- A tablet (640–1023 px): the sheet is a bottom sheet at 85 % height with the compact density; the
  sign-in page is the two-column layout.
- A very short viewport (568 px tall, landscape phone): the tagline is hidden, the header shrinks, and
  the form stays usable.
- A filter with more than eight values: a search box appears inside the sheet.
- `prefers-reduced-motion`: the sheet does not slide, it appears.

## Requirements *(mandatory)*

### Functional Requirements

**Sign-in**

- **FR-001**: On viewports below 640 px the sign-in page MUST fit one screen at 393 × 640: compact
  header (logo 40 px, product name, organisation on one line), form card edge to edge with 16 px
  gutters, inputs 44 px high, **Ingresar** 48 px full width, and the providers reachable without
  scrolling.
- **FR-002**: The language toggle MUST sit below the header on the right, never over the product name
  or the organisation, and MUST NOT intersect them.
- **FR-003**: The hero banner MUST NOT overlap the form card: the heading is fully readable.
- **FR-004**: The tagline MUST be one line, and MUST be hidden below 600 px of height.
- **FR-005**: Typography MUST be compact on phones: heading 20 px, labels and helper text 14 px.
- **FR-006**: The providers MUST sit side by side (icon + short label) when both are enabled and take
  the full width when only one is.
- **FR-007**: The email and password inputs MUST declare `autocomplete="email"` and
  `autocomplete="current-password"` (the browser's sign-in autofill contract), and the password
  toggle MUST have a 44 px target.
- **FR-008**: Errors and status messages MUST appear inline, near the field they belong to, without
  pushing the form off the screen.
- **FR-009**: From 640 px up the page MUST keep today's centred/two-column layout, unchanged.

**Sheet**

- **FR-010**: Below 640 px the sheet MUST be full screen (`100dvh`), with no drag handle, a header row
  (tabs left, `×` right, 44 px), a scrollable body and a sticky footer (`Limpiar` ghost, `Listo`
  primary) that never covers content.
- **FR-011**: The footer MUST NOT overlay the body — the body ends where the footer starts — and the
  footer MUST respect the safe-area inset, so a control scrolled into view stops above it
  (`scroll-padding-bottom`).
- **FR-012**: Each control MUST carry exactly one label, 14 px, 6 px above the control; controls
  44 px high with 12 px between them; the duplicated section titles MUST go.
- **FR-013**: Period and comparison MUST share one row when each column has at least 160 px, and the
  custom range MUST open its two dates in that same row.
- **FR-014**: The Parámetros tab MUST order the controls Período · Comparar con · Frecuencia de
  actualización · Paleta · Tema, with palette and theme as one-line horizontal chip rows.
- **FR-015**: On the Filtros tab, a filter with more than eight options MUST offer a search box, and
  the selected values MUST appear as chips above the list.
- **FR-016**: Changes MUST keep applying live (250 ms debounce) with the dashboard refreshing behind,
  and **Listo** MUST only close the sheet.
- **FR-017**: Opening the sheet MUST push a history entry so the back button closes it.
- **FR-018**: From 640 to 1023 px the sheet MUST be a bottom sheet at 85 % height with the same
  compact density; from 1024 px it MUST stay the side sheet it has today (360 px).
- **FR-019**: The sheet MUST stay a labelled `region` with focus trapped inside, Esc and back closing
  it, `role="tablist"` tabs, an axe-clean tree and respect for `prefers-reduced-motion`.

**Shell**

- **FR-020**: On phones the top bar MUST show logo, organisation, theme toggle and avatar, and MUST
  hide the breadcrumb below 480 px while keeping **Volver**.
- **FR-021**: The dashboard title MUST be 22 px with a 14 px description clamped to two lines, and a
  wrapping meta line.
- **FR-022**: Below 420 px the dashboard actions (`Filtros`, `Parámetros`, `⋯`) MUST become icon
  buttons with labels underneath.
- **FR-023**: No route MUST scroll horizontally at 360 px.

### Key Entities

Not applicable: this feature changes presentation only, and no stored data, permission or API shape.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a 393 × 640 viewport, 100 % of the sign-in controls are reachable without scrolling.
- **SC-002**: The language toggle's bounding box does not intersect the header's text at 320, 360, 393
  and 414 px.
- **SC-003**: On a 393 × 851 viewport the sheet is exactly the window height, and the four Parámetros
  controls fit in one screen without scrolling.
- **SC-004**: The footer never covers the last control: with the last control focused, its box is
  above the footer's top edge.
- **SC-005**: Zero elements wider than the viewport on `/`, `/ingresar`, `/r/<id>` and `/proyectos` at
  360 px.
- **SC-006**: No axe violation on either screen, in both themes and both languages.
- **SC-007**: Layouts from 640 px up are unchanged (the existing snapshot and unit suites stay green).

## Assumptions

- The compact scale is expressed in the design system's existing tokens plus utilities; no new colour
  or font is introduced (050 owns those).
- Snapshots are geometry and accessibility assertions in the existing Playwright idiom: the repository
  keeps no image baselines.
- The keyboard of a real phone cannot be measured; the requirement is expressed as page behaviour
  (`scroll-padding-bottom`) and verified with a focused field at a reduced viewport height.
