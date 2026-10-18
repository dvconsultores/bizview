# Feature Specification: Visual redesign (Customer A look)

**Feature Branch**: `010-visual-redesign`

**Created**: 2026-10-01

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: User description: "I do not like the design; use the design of app.example-customer.com
(Customer A, the owner's own product) as the reference." Reference screenshots (2026-10-01): Tablero
(dashboard), Configuración (section hub), Movimientos de Nómina (filter form), Maestro de
Departamentos (list with table).

## Reference look (what the owner showed)

- **Shell**: full-height left sidebar on white; at its top a block with a soft steel-teal gradient
  holding the logo tile and the product name in white; navigation items with an outline icon and
  label, the active item a filled steel-teal pill with white text and a soft shadow. A white top
  bar over the content only, with controls on the right (organisation/user pill with role badge,
  notifications, theme toggle). Page background a very light grey-blue.
- **Page header**: a white card with a large extra-bold title (tight letter spacing) and a muted
  subtitle; on detail pages a "← Volver" outlined button followed by a breadcrumb trail whose last
  item is in the accent colour.
- **Home**: a wide welcome banner with a light-to-deep steel-teal gradient, rounded corners, a small
  status chip, a large greeting and the date; then a row of KPI tiles.
- **KPI / summary tiles**: white rounded cards; an icon on a softly tinted rounded square; a small
  muted label; a large bold number; optional muted footnote ("de 24 configurados").
- **Hub cards**: grid of white cards with an icon tile, a bold title and a one-line description.
- **Cards**: white, generous radius, thin border — light grey for plain cards, steel-teal for
  emphasised ones (page header, main panels).
- **Tables**: light header row; codes in a small bordered chip; name bold with a muted second line;
  status as soft pills (green "Activo"); row actions as small icon buttons.
- **Forms**: tall inputs with a filled light grey-blue background and no visible border, rounded;
  bold labels with a red asterisk for required fields.
- **Buttons**: primary filled steel-teal with white text; secondary outlined; both rounded.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The app looks like Customer A (Priority: P1)

A user signs in and every screen shows the reference look: the sidebar with the gradient logo
block and filled active item, the white top bar, the light grey-blue background, header cards
with large bold titles, and the steel-teal accent — in light and dark themes.

**Why this priority**: the owner rejected the current look; this is the core of the request.

**Independent Test**: open home, a report, profile and every admin screen at 1920 px and 375 px in
both themes, and compare against the reference elements listed above.

**Acceptance Scenarios**:

1. **Given** a signed-in user on a desktop, **When** any screen opens, **Then** the sidebar spans the
   full height with the gradient logo block at its top, the active section is a filled steel-teal
   pill, and the top bar is white and sits only above the content.
2. **Given** any page, **When** it opens, **Then** its title and subtitle are shown in a header card
   with a large extra-bold title; detail pages (user detail, source form, report) show "← Volver"
   and a breadcrumb.
3. **Given** a phone (320–375 px), **When** any screen opens, **Then** the same visual language is
   used (header block, cards, pills, filled inputs) with the existing bottom navigation, and nothing
   scrolls horizontally.
4. **Given** the dark theme, **When** any screen opens, **Then** the same structure is shown with
   dark surfaces and the steel-teal accent, meeting WCAG AA contrast.

---

### User Story 2 - Home welcomes me and shows key figures at a glance (Priority: P2)

On the home screen the user sees a gradient welcome banner ("Bienvenido de nuevo", their name, the
date) and, below it, their dashboards as cards in the hub-card style.

**Why this priority**: home is the first impression; it depends on the shell of User Story 1.

**Independent Test**: sign in as a user with several dashboards and check the banner, the date in
Spanish and the dashboard cards at 1920 px and 375 px.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** home opens, **Then** a welcome banner shows "Bienvenido de
   nuevo", the user's first name and today's date in Spanish, over the steel-teal gradient, with
   text contrast meeting WCAG AA.
2. **Given** the user has dashboards, **When** home opens, **Then** each dashboard is a hub card
   (icon tile, bold title, one-line description) in a responsive grid.
3. **Given** an administrator, **When** the administration home opens, **Then** its sections are hub
   cards like the reference "Configuración" screen, preceded by summary tiles where counts are
   already available (users, sources, integrations).

---

### User Story 3 - Lists, forms and reports follow the same style (Priority: P2)

Lists (users, audit, sources, integrations, tokens), forms (new user, source, profile) and
reports use the reference table, form and tile styles.

**Why this priority**: consistency across screens; builds on User Story 1's tokens and components.

**Independent Test**: open the users list, the new-user form, the source form and a report; check
tables, filled inputs, chips, pills and KPI tiles against the reference.

**Acceptance Scenarios**:

1. **Given** a list screen, **When** it opens on a desktop, **Then** rows show codes/emails as chips
   where relevant, names bold with a muted second line, states as soft pills, and actions as icon
   buttons; on phones the list stays readable without horizontal scrolling.
2. **Given** a form, **When** it opens, **Then** inputs are tall, filled and borderless, labels bold,
   required fields marked, and errors still clearly visible (colour plus text).
3. **Given** a report, **When** it opens, **Then** its KPIs use the KPI tile style (tinted icon square,
   small label, large value, change indicator), and charts use the steel-teal series colours.

---

### Edge Cases

- The customer's logo must stay visible on the gradient logo block (light tile behind it when
  needed), without asking customers for a second logo.
- Sign-in and password-change screens adopt the palette (gradient panel, filled inputs) while
  keeping their two-panel layout.
- Views (feature 009) use the header-card style with their back button.
- Long names in the sidebar, chips and pills truncate with an ellipsis instead of breaking layout.
- PDF exports keep their current look.
- Reduced motion: no decorative animations.
- The Ubuntu typeface (feature 009) is kept.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The default accent of the product MUST be the reference steel-teal, with a light-to-deep
  gradient for the logo block, the home banner and the sign-in panel; customers' logos stay as
  configured.
- **FR-002**: The shell MUST have a full-height sidebar (from desktop width) with the gradient logo
  block and a filled pill for the active item, a white top bar above the content only, and a light
  grey-blue page background; phones keep the bottom navigation.
- **FR-003**: Every screen MUST show its title in a header card (large extra-bold title, muted
  subtitle); detail screens MUST also show "← Volver" and a breadcrumb.
- **FR-004**: Cards, KPI tiles, hub cards, tables, chips, status pills, filled inputs and buttons MUST
  follow the reference look described above, implemented once as shared components and reused.
- **FR-005**: Home MUST show the welcome banner with the user's first name and the date in Spanish,
  and the dashboards as hub cards; the administration home MUST show its sections as hub cards.
- **FR-006**: Light and dark themes MUST both implement the look and meet WCAG 2.1 AA contrast (4.5:1
  text, 3:1 non-text).
- **FR-007**: The layout MUST remain mobile-first: no horizontal scrolling at 320/375 px, touch
  targets ≥ 44 px.
- **FR-008**: The redesign MUST NOT change behaviour, routes, texts' meaning or data shown; all
  existing automated tests keep passing (selectors updated only where markup changed).
- **FR-009**: All visible texts MUST be in Spanish.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The owner, comparing BizView side by side with the four reference screens, recognises
  the same visual language (shell, header cards, tiles, tables, forms) on 100% of BizView's screens.
- **SC-002**: 0 serious or critical automated accessibility violations on every screen in both
  themes.
- **SC-003**: 0 screens scroll horizontally at 320 and 375 px.
- **SC-004**: 100% of the existing functional tests pass after the redesign.

## Assumptions

- Customer A is the owner's own product, so reusing its visual language is permitted; no assets
  (logos, images) are copied — only the style.
- The reference font is not adopted; Ubuntu stays (owner's earlier request).
- Language switch, organisation selector and notifications seen in the reference are not features of
  BizView and are not added; the top bar shows BizView's existing controls (theme, account menu).
- Charts keep their types; only colours and tile framing change.
