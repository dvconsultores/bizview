# Feature Specification: Dark mode

**Feature Branch**: `006-dark-mode`

**Created**: 2026-09-30

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: User description: "Dark mode: users can switch the BizView web UI between light and
dark themes (plus follow the operating-system preference by default). The choice persists per
user across sessions and devices, applies to all screens including reports, charts and tables,
and keeps contrast accessible (WCAG AA) in both themes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The app follows my device's theme (Priority: P1)

A user whose phone or computer is set to dark appearance opens BizView and sees it in dark
colours, with no extra step. A user on light appearance sees the current light look. If the
device switches appearance (for example, automatically at sunset) while BizView is open, the app
follows.

**Why this priority**: it delivers dark mode to every user with zero effort and is the default
behaviour; the rest of the feature builds on having a complete dark theme.

**Independent Test**: set the device to dark appearance, sign in, and walk every screen (home,
a report, profile, each admin screen); then switch the device to light while a screen is open.

**Acceptance Scenarios**:

1. **Given** the device is set to dark appearance and the user has never chosen a theme,
   **When** they open the sign-in screen and then any screen after signing in, **Then** every
   screen shows the dark theme.
2. **Given** a screen is open and the user's theme is "system", **When** the device switches
   between light and dark appearance, **Then** the screen changes theme within a second, without
   reloading and without losing what the user was doing (filters, open dialogs, typed text).
3. **Given** the device is set to dark appearance, **When** a screen loads, **Then** it never
   briefly shows the light theme first.

---

### User Story 2 - I choose my theme and it follows me (Priority: P2)

A user who prefers dark (or light) regardless of their device's setting picks "Oscuro", "Claro"
or "Sistema" once. The choice applies immediately and is remembered on their account, so it is
the same on their phone and their computer and after signing out and back in.

**Why this priority**: an explicit choice is what users ask for when the automatic default is not
what they want; it depends on the dark theme from User Story 1.

**Independent Test**: choose "Oscuro" on one device with light appearance, sign in on a second
device (or a fresh browser), and confirm the dark theme is shown there too.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they choose "Oscuro", "Claro" or "Sistema", **Then** the
   whole app changes to that theme immediately, without reloading.
2. **Given** a user chose "Oscuro", **When** they sign in on another device or browser, **Then**
   the app is dark as soon as it opens after sign-in, whatever that device's appearance.
3. **Given** a user chose "Claro" on a device set to dark appearance, **When** the device
   appearance changes, **Then** the app stays light.
4. **Given** the choice cannot be saved (for example, connection lost), **When** the user picks
   a theme, **Then** the theme still changes on the current screen and the user is told that the
   choice was not saved to their account.

---

### User Story 3 - Reports stay readable in the dark (Priority: P1)

A user reading sales figures at night opens a report in dark mode. KPIs, trend charts, ranking
and data tables, narratives, period pickers and badges are all legible; positive/negative values
and chart series keep distinct, meaningful colours; nothing is left as a bright white box.

**Why this priority**: reports are the product's core; a dark theme that breaks charts or tables
is worse than no dark theme. It is part of the MVP together with User Story 1.

**Independent Test**: open a report with every component type (KPI grid, trend chart, ranking
table, data table, narrative, period picker) in dark mode, at 375px width and on desktop, and
run an automated contrast check.

**Acceptance Scenarios**:

1. **Given** dark mode, **When** a report with a trend chart is shown, **Then** axes, grid lines,
   labels, legends and tooltips are legible and each series stays distinguishable.
2. **Given** dark mode, **When** a table with many rows is shown, **Then** header, row
   separation, highlighted rows and numbers are legible and the table remains readable at 375px.
3. **Given** dark mode, **When** a value is shown as positive/negative or good/bad, **Then** it
   keeps an equivalent colour meaning to light mode and never relies on colour alone.
4. **Given** dark mode, **When** the user exports a report to PDF, **Then** the PDF has the same
   light, print-friendly look as today.

---

### Edge Cases

- A customer's branding (logo, primary colour) was designed for a light background: the logo
  and brand-coloured elements must stay visible on the dark theme (for example, shown on a
  surface that keeps enough contrast), without asking the customer for a second logo.
- The browser or device cannot report an appearance preference: "Sistema" behaves as light.
- The sign-in screen is shown before the app knows who the user is: it follows the device
  appearance, or the last theme chosen on that same device if there is one.
- Two devices change the theme at the same time: the last saved choice wins; an already open
  device picks it up at the next sign-in or reload (no live sync is required).
- Content not rendered by the app itself (the browser's own date pickers, scrollbars, form
  autofill) should match the active theme where the browser allows it.
- The browser's top bar colour on phones matches the active theme.
- The user has enabled reduced motion: the theme change happens without animated transitions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST offer three theme options to every signed-in user: "Sistema"
  (follow the device appearance), "Claro" and "Oscuro". "Sistema" MUST be the default for every
  user, including existing users.
- **FR-002**: Users MUST be able to change the theme from their profile screen and from a control
  reachable from every screen of the app shell in at most two taps.
- **FR-003**: A theme change MUST apply to the whole app immediately, without reloading and
  without losing the current screen's state.
- **FR-004**: The system MUST store the user's theme choice on their account, so it applies on
  every device and browser and survives signing out and back in.
- **FR-005**: With "Sistema", the app MUST follow changes of the device appearance while open.
- **FR-006**: Screens MUST render in the correct theme from the first paint; a flash of the
  other theme on load is a defect.
- **FR-007**: Before sign-in (sign-in and related screens), the app MUST follow the device
  appearance, or the last theme chosen on that device when one is known.
- **FR-008**: The dark theme MUST cover every screen and component: sign-in, password change,
  two-step setup, home, reports (KPIs, charts, ranking and data tables, narrative, period
  picker), profile, all admin screens, dialogs, toasts, alerts, badges, forms, empty and error
  states.
- **FR-009**: In both themes, text and meaningful non-text elements (icons, chart lines, focus
  indicators, form borders) MUST meet WCAG 2.1 AA contrast: 4.5:1 for normal text, 3:1 for
  large text and non-text elements.
- **FR-010**: Chart series and status colours (positive/negative, success/warning/error) MUST
  keep the same meaning in both themes and MUST NOT rely on colour alone.
- **FR-011**: The customer's branding (primary colour and logo) MUST remain visible and
  recognisable in the dark theme without extra configuration by the customer.
- **FR-012**: PDF exports MUST keep the current light, print-friendly appearance regardless of
  the user's theme.
- **FR-013**: If saving the choice fails, the theme MUST still change for the current session
  and the user MUST see a message that it was not saved to the account.
- **FR-014**: All new labels and messages MUST be in Spanish, like the rest of the interface.

### Key Entities

- **Theme preference**: a user's chosen theme — one of "system", "light", "dark" — belonging to
  exactly one user account; defaults to "system".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the app's screens and dialogs pass an automated accessibility contrast
  check with zero contrast violations in both light and dark themes.
- **SC-002**: A user can change the theme from any screen in 2 taps or fewer, and the change is
  visible in under 1 second.
- **SC-003**: After choosing a theme on one device, the same user sees that theme on a second
  device on the first screen after sign-in, in 100% of test runs.
- **SC-004**: No screen shows a flash of the wrong theme on load, in any of 10 consecutive
  loads of each screen under the dark theme.
- **SC-005**: Every report component remains readable at 375px width in dark mode, verified on
  every component type.
- **SC-006**: PDF exports produced by a user in dark mode are identical in appearance to those
  produced in light mode.

## Assumptions

- Only the web app is in scope; PDF exports and emails keep their current look.
- The current light look is kept as the light theme; this feature only adds the dark theme and
  the choice between them (no redesign of the light theme).
- Customers' deployments do not need to configure anything for dark mode; the dark variant of
  the brand colour is derived automatically from the configured brand colour.
- No per-installation option to disable dark mode or to force one theme for all users is needed
  in this version.
- Existing users start with "Sistema"; no data migration beyond adding the preference with that
  default.
- A change made on one device does not need to reach other devices that are already open in
  real time; it applies at their next sign-in or reload.
