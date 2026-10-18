# Feature Specification: Dashboard auto-refresh and TV mode

**Feature Branch**: `015-dashboard-autorefresh`

**Created**: 2026-10-01

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: Owner, 2026-10-01: "dashboard view (autorefresh mode?)". A report can keep itself up to
date on screen, and can be shown full screen on a wall display.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The open report updates itself (Priority: P1)

A user leaves a report open. They switch on "Actualización automática"; when the integration
loads new data, the report refreshes by itself (figures, charts, freshness), keeping the
parameters and scroll position.

**Why this priority**: the core request; managers keep sales dashboards open all day.

**Independent Test**: open a report with auto-refresh on, run its integration, and see the figures
and "Datos actualizados" change within the check interval without touching the page.

**Acceptance Scenarios**:

1. **Given** auto-refresh "Al llegar datos nuevos" (default), **When** new data is loaded for any
   dataset the report uses, **Then** the report reloads once within 60 seconds and shows a short
   notice "Datos actualizados hh:mm".
2. **Given** auto-refresh with a fixed interval (1, 5, 15 or 60 minutes), **When** the interval
   passes, **Then** the report reloads (useful for relative periods like "Hoy").
3. **Given** the user has pending (unapplied) parameter edits (feature 012), **When** a refresh is due,
   **Then** it uses the applied parameters and does not discard the draft.
4. **Given** the tab is hidden, **When** refreshes are due, **Then** no requests are made until the tab is
   visible again; then it refreshes once if data changed.
5. **Given** auto-refresh is on, **When** the user reloads the page or comes back later on the same
   device, **Then** the setting is remembered (per report, per device).

---

### User Story 2 - TV mode for wall displays (Priority: P2)

From a report, the user enters "Modo TV": the report fills the screen without navigation, filters
panel or footer, with large text, the title, the period and the last update time; auto-refresh is on;
"Salir" returns to the normal view.

**Why this priority**: common for sales floors; builds on US1.

**Independent Test**: enter TV mode on a 1920 × 1080 display; check layout, legibility at distance,
auto-refresh and exit.

**Acceptance Scenarios**:

1. **Given** a report, **When** "Modo TV" is chosen, **Then** the app uses the browser's full screen when
   allowed and shows only the report content with title, period and "Datos actualizados".
2. **Given** TV mode, **When** Esc or "Salir del modo TV" is used, **Then** the normal view returns with
   the same parameters.
3. **Given** TV mode, **When** opened via its link, **Then** it opens directly in TV mode (shareable URL
   flag), still requiring sign-in and the usual access.
4. **Given** TV mode for hours, **When** the session would expire by inactivity, **Then** the screen keeps
   working within the session's absolute limit; when the session ends it shows the sign-in screen.

### Edge Cases

- The integration fails: no refresh (data unchanged); freshness shows the last successful load.
- Network down: the report keeps the last figures and shows "Sin conexión — reintentando".
- PDF and narrative are not regenerated automatically.
- Reduced motion: no animated transitions on refresh.

## Requirements *(mandatory)*

- **FR-001**: Reports MUST offer auto-refresh modes: off, "Al llegar datos nuevos" (default when
  enabled), and fixed intervals 1/5/15/60 minutes; remembered per report per device.
- **FR-002**: "Al llegar datos nuevos" MUST detect new loads through a lightweight check (no report
  recomputation) at most every 60 seconds, and reload only when the data changed.
- **FR-003**: Refresh MUST keep applied parameters and scroll position, never discard draft edits, and
  pause while the tab is hidden.
- **FR-004**: TV mode MUST hide navigation, filters and footer, enlarge content, keep title, period and
  freshness visible, enable auto-refresh, and be reachable by URL; exit returns to the normal view.
- **FR-005**: Access rules and session limits stay as today; TV mode is not a public/anonymous link.
- **FR-006**: Spanish UI, feature-010 look, no modals, WCAG AA, mobile-first (TV mode is for large
  screens but must not break on phones).

## Success Criteria *(mandatory)*

- **SC-001**: After an integration run loads new data, an open report with auto-refresh shows it within
  60 seconds in 100% of tests.
- **SC-002**: With no new data, "Al llegar datos nuevos" causes 0 report recomputations per hour.
- **SC-003**: TV mode text is readable from 3 m on a 1080p display (KPI values ≥ 48 px).

## Assumptions

- The lightweight check uses the report's existing data version (already used by the report cache).
- Fullscreen API may be refused by the browser; TV mode still works in the window.
