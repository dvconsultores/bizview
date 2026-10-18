# Feature Specification: Views instead of modals, wider layout, Ubuntu font

**Feature Branch**: `009-ui-views-layout`

**Created**: 2026-10-01

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: User description: "UI polish requested by the owner on 2026-10-01. (1) No modals anywhere:
every modal/overlay dialog in the web app becomes a view (a page-level screen that replaces the page
content, with a back action), never an overlay — including the global step-up 'Confirma tu
contraseña' prompt, which must keep the user's in-progress work and resume the action. Browser/phone
back closes the view. (2) Wider content on large screens. (3) App font: Ubuntu, self-hosted, with a
system fallback; monospace secrets keep a monospace font."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Confirmations and results are screens, not pop-ups (Priority: P1)

An administrator creates a user, resets a password, deactivates an account, unlinks Telegram,
resets two-step sign-in, deletes a source or rolls back the workspace. Instead of a box floating
over a dimmed page, the app shows a full screen for that step, with a clear title, the
information or question, the actions, and a way back. The same applies to every user who sees
their recovery codes, turns off two-step sign-in, or is asked to confirm their password before a
sensitive change.

**Why this priority**: it is the owner's explicit rule for the product ("never modals, always a
view"); pop-ups are hard to use on phones, hide content, and are the part of the UI the owner
rejected.

**Independent Test**: walk every flow listed in FR-002 on a phone width and on a desktop width,
and confirm that no overlay ever appears, each step is a screen with a back action, and the phone
or browser back button returns to the previous screen.

**Acceptance Scenarios**:

1. **Given** an administrator submits the new-user form, **When** the user is created, **Then** a
   "Usuario creado" screen shows the email, the temporary password once with a copy action, the
   hint to hand it over, and the actions "Crear otro" and "Ver usuario"; nothing is overlaid on
   the form.
2. **Given** a destructive or sensitive action (deactivate or reactivate a user, unlink Telegram,
   reset two-step sign-in, delete a source, roll back the workspace, turn off own two-step
   sign-in), **When** the administrator or user starts it, **Then** a confirmation screen names
   what will happen and offers the action and "Cancelar"; cancelling returns to the screen they
   came from, unchanged.
3. **Given** a confirmation or result screen is open, **When** the user presses the browser or
   phone back button, **Then** the app returns to the previous screen as if they had cancelled,
   without performing the action.
4. **Given** a one-time secret is shown (temporary password, recovery codes), **When** the user
   leaves the screen by any means, **Then** the secret is no longer shown anywhere and cannot be
   reached again with the forward button.

---

### User Story 2 - Confirming my password does not lose my work (Priority: P1)

A user is filling a form that needs a recent password confirmation (for example, creating an API
token or changing a source's credentials). When they save, the app asks them to confirm their
password on its own screen. After they confirm, the app returns to their form with everything they
typed and completes the save; if they cancel, they return to the form unchanged.

**Why this priority**: the step-up prompt appears in the middle of many admin flows; turning it
into a screen must not cost the user what they typed, or the change makes the product worse.

**Independent Test**: start a token creation with a name typed, let the session require a step-up,
confirm the password on the screen, and check the token is created with the typed name; repeat
with "Cancelar" and check the form still holds the typed name and nothing was created.

**Acceptance Scenarios**:

1. **Given** a user saving a form that requires a recent password confirmation, **When** the app
   asks for it, **Then** a "Confirma tu contraseña" screen replaces the page, with the password
   field focused.
2. **Given** the confirmation screen, **When** the user enters the correct password, **Then** the
   app returns to the previous screen with every field as they left it and the pending action
   completes once.
3. **Given** the confirmation screen, **When** the user cancels or presses back, **Then** the app
   returns to the previous screen with every field as they left it and the action is not
   performed.
4. **Given** a wrong password, **When** submitted, **Then** the screen stays, shows the error and
   clears the password field; if the account becomes locked or throttled, the screen closes and
   the action is reported as not performed, as today.

---

### User Story 3 - Pages use the width of large screens (Priority: P2)

On a large desktop screen, administration and report pages use most of the available width instead
of a narrow column with large empty margins on both sides. On phones and tablets the layout is the
same mobile-first layout as today.

**Why this priority**: the owner finds the current narrow column wasteful on 1920-pixel screens;
it does not block any task, so it follows the P1 stories.

**Independent Test**: open every main screen at 1920 × 1080 and at 1366 × 768, measure the width
used by the page content, and open the same screens at 320 and 375 pixels to check nothing
overflows.

**Acceptance Scenarios**:

1. **Given** a 1920-pixel-wide window with the sidebar shown, **When** an administration list or
   detail page opens (users, audit, security, sources, integrations, workspace, tokens, AI), **Then**
   its content spans at least 85% of the area to the right of the sidebar.
2. **Given** the same window, **When** a form page opens (new user, source form, profile), **Then**
   its content spans at least 85% of that area as well, arranging fields in more than one column
   where that keeps each field readable.
3. **Given** a 320- or 375-pixel-wide phone, **When** any screen opens, **Then** there is no
   horizontal scrolling and the layout matches today's mobile layout.

---

### User Story 4 - The app uses the Ubuntu typeface (Priority: P3)

Every screen of the app, including sign-in, renders text in the Ubuntu typeface, also on
installations without internet access. Passwords, recovery codes and other secrets that are shown
to be copied keep a fixed-width typeface so similar characters stay distinguishable.

**Why this priority**: brand consistency requested by the owner; purely visual.

**Independent Test**: open sign-in, home, a report and an admin screen on a machine without the
Ubuntu font installed and with the internet blocked, and check that the text renders in Ubuntu
and that the temporary-password and recovery-code boxes use a fixed-width face.

**Acceptance Scenarios**:

1. **Given** a device without Ubuntu installed and no internet access, **When** any screen loads,
   **Then** its text renders in Ubuntu, served by the installation itself.
2. **Given** the font files cannot be loaded, **When** a screen loads, **Then** text renders
   immediately in the system's sans-serif font and nothing is invisible while waiting.
3. **Given** a secret shown for copying, **When** it renders, **Then** it uses a fixed-width
   typeface.

---

### Edge Cases

- A confirmation screen is opened directly by URL or after a reload: the app shows the screen it
  belongs to (for example the user's detail) instead of a confirmation with no context; a one-time
  secret is never shown again after a reload.
- The step-up prompt is triggered while another step-up is pending (two requests at once): one
  screen is shown and both actions continue or stop together.
- The step-up prompt is triggered from a screen that is itself a confirmation screen (e.g. confirm
  delete, then step-up): after confirming the password the delete completes; after cancelling,
  the user is back on the confirmation screen.
- An action on a confirmation screen fails (network, server error): the screen stays, shows the
  error, and the action can be retried or cancelled.
- The sign-in screen and the password-change screen keep their own layout (hero panel); they are
  not widened.
- Reports keep a readable layout on very wide screens (charts and tables do not stretch beyond the
  point where they become hard to read).
- The account menu in the top bar is a menu, not a modal, and stays as it is; short notices
  (toasts) also stay.
- PDF exports keep their current fonts and layout.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The web app MUST NOT show any modal or overlay dialog (an element that dims or
  blocks the page behind it). Menus and transient notices that do not block the page are not
  dialogs.
- **FR-002**: Each of these flows MUST be a view (a screen that replaces the page content and has a
  title and a back action): new user created; reset a user's password (form and result);
  deactivate or reactivate a user; unlink a user's Telegram; reset a user's two-step sign-in;
  show own recovery codes; turn off own two-step sign-in; roll back the workspace; delete a
  source; confirm password before a sensitive action (step-up).
- **FR-003**: Cancelling a view, using its back action, or using the browser/phone back button
  MUST return to the screen it was opened from without performing its action and without losing
  that screen's state (typed text, filters, scroll position).
- **FR-004**: The step-up view MUST resume the interrupted action exactly once after a correct
  password and MUST NOT perform it after cancel or back; the interrupted screen's typed content
  MUST be preserved in both cases.
- **FR-005**: One-time secrets (temporary passwords, recovery codes) MUST be shown only on their
  result view and MUST NOT be reachable again through reload, back/forward navigation or the URL.
- **FR-006**: Views MUST keep focus management and accessibility: focus moves to the view's title
  or first field when it opens and returns to the control that opened it when it closes; each view
  passes the same automated accessibility checks as other screens in both themes.
- **FR-007**: On screens wider than 1280 pixels, page content MUST use at least 85% of the width
  available beside the navigation; on phones (320–375 px) the layout MUST NOT scroll
  horizontally.
- **FR-008**: The app's text MUST use the Ubuntu typeface served by the installation itself (no
  third-party font service), with a system sans-serif fallback shown immediately while the font
  loads or if it fails; secrets shown for copying MUST use a fixed-width typeface.
- **FR-009**: The font files MUST be distributed with their licence, consistent with the product's
  open-source distribution.
- **FR-010**: All texts MUST be in Spanish; colour contrast MUST meet WCAG 2.1 AA in light and dark
  themes, as today.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 overlay dialogs remain: walking every flow in FR-002, no screen shows content
  dimmed or blocked behind another element, in 100% of flows.
- **SC-002**: In 100% of step-up tests, typed form content is intact after both confirm and cancel,
  and the interrupted action runs exactly once after confirm and never after cancel.
- **SC-003**: At 1920 × 1080 every administration screen's content spans at least 85% of the area
  beside the navigation (today about 45%).
- **SC-004**: At 320 and 375 pixels, 0 screens scroll horizontally.
- **SC-005**: With the internet blocked, 100% of screens render their text in Ubuntu.
- **SC-006**: Automated accessibility checks report 0 serious or critical violations on every
  screen and view, in both themes.

## Assumptions

- "View" means a screen inside the app shell that replaces the page content; whether it has its
  own URL is a design decision for the plan, as long as back-button behaviour (FR-003) and secret
  handling (FR-005) hold.
- The Ubuntu font is redistributable under the Ubuntu Font Licence; only the weights the UI uses
  (regular, medium, bold, and their italics only if used) are shipped.
- The sign-in and password-change screens keep their two-panel design; only their font changes.
- Report specs, PDF exports and the backend are unchanged.
- The account menu and toasts are not modals and are kept.
