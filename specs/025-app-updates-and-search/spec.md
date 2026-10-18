# Feature Specification: Updates notice, project search, full-screen chat and the type scale

**Feature Branch**: `025-app-updates-and-search`

**Created**: 2026-10-14

**Status**: Implemented (2026-10-15; frontend unit 592/592, `tsc` clean, build OK; Playwright
`projects.spec.ts` (incl. the collapsible menu and the panel geometry), `updates.spec.ts`,
`design.spec.ts`, `reporting.spec.ts`, `i18n.spec.ts`, `commands.spec.ts` and `assistant.spec.ts`
green; backend `ruff` clean and the three guide suites green)

**Input**: Owner, 2026-10-14 (with two screenshots, Customer A on the left and this app on the
right): "when the panel is full screen the chat does not appear, keep the chat overlay it was
beautiful but it needs to be visible even at full screen", "add a new version available when there
is a new change", "compare both font size at left cliente-a at right cliente-c", "add a input search in
proyectos".

**Builds on**: 020 (BI projects), 024 (one chat per screen, the design pass that introduced
full-screen mode and the type scale), 022 (languages).

**Constitution**: **IX (spec-driven)** — a change without a spec is a change nobody can audit, so
each of the four items below is an FR with its test. **VIII (AI private and optional)** is
untouched: none of these items sends anything to a provider. **2.1 (mobile-first)** — every control
added here is measured at 320/375 px as well as on a desktop viewport.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The chat is there in full screen too (Priority: P1)

Someone takes a project to full screen to work on the files with every pixel available, and then
wants to ask the assistant about what is on the screen. Today the docked panel disappears the
moment the chrome steps aside, so there is no chat at all: the assets and the editor are the only
thing on the screen and the conversation is unreachable without leaving full screen.

**Why this priority**: it is the reported defect; a missing control in a mode the product itself
offers makes the mode unusable for the flow it was built for (look at the report, ask for the
change).

**Independent Test**: open a project, enter full screen, open the assistant from the project's own
tool strip and send a message — the panel is visible, docked over the full-height canvas, and the
project page keeps its own controls reachable.

**Acceptance Scenarios**:

1. **Given** a project page in full screen with the panel closed, **When** the person presses
   *Asistente* in the project tool strip, **Then** the chat panel appears immediately, from the very
   top of the viewport (no 4 rem gap where the top bar used to be), with the conversation usable.
2. **Given** the panel expanded, **When** the chrome is hidden (full screen), **Then** the panel
   uses the whole width from the left edge instead of offsetting itself by the sidebar that is no
   longer there.
3. **Given** full screen and the panel open, **When** the person works in the project, **Then** the
   project's own controls are never covered by the panel, and leaving and re-entering full screen
   keeps the open/closed state the person chose.
4. **Given** a phone in full screen, **When** the person opens the chat, **Then** it is the pane as
   before (the docked panel does not exist below 1024 px) and nothing regresses.

### User Story 2 - "Hay una versión nueva" (Priority: P1)

The product is self-hosted and updated in place. A dashboard open on a wall-mounted screen, or a
person who left a tab open, keeps running the bundle it loaded hours ago; today nothing tells them a
new build is deployed, so they report bugs that were already fixed and miss the fix that was already
shipped.

**Why this priority**: it is the second explicit request, and the failure it prevents (people
working on an old build without knowing) is silent.

**Independent Test**: with the app open, replace the deployed `index.html` with one that points at a
different hashed bundle; within the check period the app shows a "new version available" notice with
a *Recargar* action, and no notice appears when the deployed bundle is the one that is running.

**Acceptance Scenarios**:

1. **Given** a page whose bundle is the one the server is serving, **When** the check runs, **Then**
   nothing is shown (no false positives in development, where the entry never changes).
2. **Given** a page whose bundle is older than the deployed one, **When** the check runs, **Then** a
   dismissible notice appears with the action *Recargar*, which reloads the app onto the new build.
3. **Given** the notice is showing, **When** the person dismisses it, **Then** it stays dismissed for
   that tab (it does not come back on every poll) and it never blocks the page or steals focus.
4. **Given** a hidden tab, **When** the person returns to it, **Then** the check runs immediately
   (returning to a wall screen is the case that matters most) and the notice is only ever rendered
   while the tab is visible.

### User Story 3 - Finding a project in the list (Priority: P2)

An installation accumulates projects — one per report request — and the list is the only way to
reach one. Scrolling a grid to find "the payroll report I asked for in March" is the slowest part of
the day, and the list has no way to narrow it.

**Why this priority**: it is the third request; it does not block anything, it removes friction from
a page that is used every day.

**Independent Test**: type part of a project's name, its identifier or its description; the grid
shows only the matches, the count of matches is stated, and a search that matches nothing says so
(with the way to clear it) instead of showing the "no projects yet" empty state.

**Acceptance Scenarios**:

1. **Given** four projects, **When** the person types `p2p`, **Then** only the matching project is
   listed and the number of matches is announced.
2. **Given** a search matching nothing, **When** the grid renders, **Then** it says no project
   matches (with the term) and offers to clear the search; the "create your first project" empty
   state is not shown while a search is active.
3. **Given** a search with an accent (`administracion`), **When** the project is named
   `Administración`, **Then** it matches (the search ignores case and accents).
4. **Given** a phone at 320 px, **When** the search is used, **Then** the field, its label and its
   clear control stay inside the viewport and meet the touch-target minimum.

### User Story 4 - The type scale is the reference app's (Priority: P3)

The owner compares this app against the reference (Customer A) side by side and asks for the same
type scale, element by element.

**Why this priority**: it is a refinement of a closed decision (024's design pass), verified from
the reference's own stylesheet rather than by eye.

**Independent Test**: read the computed root font size at 375, 768, 1024 and 1920 px and compare it
with the reference's rules (`html{font-size:13px}`, 12.5 px ≤640 px, 13.5 px ≥1536 px).

**Acceptance Scenarios**:

1. **Given** a 1024 px viewport or wider (and below 1536 px), **Then** the root is 13 px, as in the
   reference (already the case since 024).
2. **Given** a 768 px viewport, **Then** the root is 13 px — the reference has no tablet band, its
   13 px applies from 641 px up. *(This is the one deviation this feature removes: the app used
   14 px there.)*
3. **Given** a 375 px viewport, **Then** the root is 15 px; the reference's 12.5 px is too small for
   this app's dense screens beside a 16 px form control (iOS zooms into anything under 16 px). The
   deviation is deliberate, documented and asserted by a test.

### Edge Cases

- **The collapsed menu on a phone**: the side menu only exists from 1024 px, so the collapse control
  is never rendered on phones and the bottom bar is untouched.
- **Collapsed menu plus the docked chat**: the content keeps its room in both directions (rail on the
  left, panel on the right); at a narrow desktop width the rail plus the panel must not squeeze the
  content to nothing (the panel is `34rem`/`38rem`, the rail is 80 px).

- **Full screen with the chat closed**: entering and leaving full screen must not open the chat by
  itself, and must not forget that it was closed.
- **Full screen on a phone**: the panel cannot dock; the chat stays a pane and the chrome returns
  when full screen is left.
- **The version check when the server is unreachable**: it is silent (no notice, no console noise,
  no blocking), exactly like the report auto-refresh's backoff.
- **A bundle with no entry script** (an unusual base path, a stripped `index.html`): the check is
  inert, never a notice.
- **Version notice versus report auto-refresh**: they are different things (a new *build* and new
  *report data*) and must not be confused in the copy.
- **Search with a project whose name is empty**: the identifier and the description are still
  searchable.

### User Story 5 - Folding the menu away, and no wasted space (Priority: P2)
A wall dashboard or the project editor wants every pixel; a 208 px menu with six labels is width
that the screen cannot use, and the gutters around the content (a third of a rem next to the menu
and another next to the chat) read as blank space rather than breathing room.

**Why this priority**: it is the owner's "small fixes" round — small, visible, and it makes the two
previous features (the docked chat, the wide projects list) actually use their width.

**Independent Test**: collapse the menu and watch the icon rail take a quarter of the old width
with the content starting where it ends; open the chat and check that the page now touches the
panel with no gutter between them.

**Acceptance Scenarios**:

1. **Given** the menu expanded, **When** the person presses *Contraer el menú*, **Then** it becomes
   an icon rail (labels as tooltips, accessible names unchanged, targets still ≥ 24 px), the content
   moves up to the rail, and the choice survives a reload.
2. **Given** the menu collapsed, **When** the person presses *Expandir el menú*, **Then** the labels
   come back and the state is remembered.
3. **Given** the docked chat, **When** the project page renders, **Then** the page's content meets
   the panel (no canvas gutter between them) while the panel keeps its own border.
4. **Given** any screen, **When** it renders at a desktop width, **Then** the gutter next to the
   menu and the space below the top bar are visibly tighter than they were, and nothing overflows.

## Requirements *(mandatory)*

- **FR-001**: The docked assistant panel MUST be rendered in full screen exactly as it is with the
  chrome visible: same view, same conversation, same controls.
- **FR-002**: In full screen the panel MUST sit at the top of the viewport (`top: 0`) and, when
  expanded, MUST use the full width from the left edge, because there is no top bar and no sidebar
  to make room for. With the chrome visible the docked panel MUST also own the **full height of its
  column** (`inset-y-0`): the top bar spans the content column only, so starting the panel below it
  left an empty band of canvas at the top of the panel's column (owner, 2026-10-15: *"when open the
  chat the navbar reduces, and there is an empty space at top… use full full height"*).
- **FR-003**: With the chrome hidden and the panel docked, the page content MUST keep its room: the
  panel MUST NOT cover the project's own controls.
- **FR-004**: The app MUST detect that the deployed build is not the one it is running and MUST show
  a dismissible notice with a *Recargar* action; the detection MUST be based on the deployed entry
  document, so a development server (whose entry never changes) never triggers it.
- **FR-005**: The check MUST run while the tab is visible, on an interval of at most 60 s, and
  immediately when the tab becomes visible again; it MUST NOT run while hidden, MUST NOT block or
  delay any other request, and MUST fail silently.
- **FR-006**: Dismissing the notice MUST persist for the tab until it is reloaded, and the notice
  MUST never take focus or cover content when it appears (no modal).
- **FR-007**: The projects list MUST provide a search field that filters by name, identifier and
  description, case-insensitively and ignoring accents, with an accessible name, a placeholder, a
  clear control, and a stated count of matches.
- **FR-008**: A search that matches nothing MUST state that no project matches (naming the term) and
  offer to clear it; the first-run empty state MUST only appear when there are truly no projects.
- **FR-009**: The root type scale MUST equal the reference app's on desktop: 13 px from 641 px,
  13.5 px from 1536 px. No ordinary UI text MAY be hardcoded above the scale (the shell's brand and
  navigation used a fixed 15 px that did not follow the root: they are rem-sized now, so the
  sidebar renders at 13 px exactly as the reference's does). The phone base MAY deviate (the
  reference's 12.5 px is too small here) and the deviation MUST be documented in the stylesheet and
  asserted by a test.
- **FR-010**: Every string added by this feature MUST exist in Spanish and English, and both
  catalogues MUST stay in step (the existing guard test).
- **FR-011**: No new dependency, no new backend endpoint and no schema change: the notice reads the
  installed front end, not the database.
- **FR-012**: The guide MUST describe the new notice and the project search (feature 023 keeps the
  guide equal to the app).
- **FR-013**: The left menu MUST be collapsible to an icon rail (and back), from a control placed
  with the menu it acts on: the labels MUST stay the accessible names (visible label, `sr-only` when
  collapsed, `title` as a tooltip), the targets MUST keep their size, the control MUST expose
  `aria-expanded`/`aria-controls`, and the choice MUST be remembered by the browser (localStorage),
  never by the account.
- **FR-014**: The content gutters MUST be tight: no content-column gutter between the content and the
  docked panel, one spacing unit next to the menu and the top bar, and one spacing unit above the
  page content below the top bar. The menu's own band MUST NOT be stretched by a control pinned to
  the bottom of the screen; the space that remains under it is the page's, not the menu's.
- **FR-016**: The seam between the page and the docked chat MUST be the IDE's own pane divider — the
  same width and colour as the element between the file explorer and the editor (`w-1.5 bg-line`),
  with no shadow: a panel that casts a halo into the page reads as empty space. With the chat docked
  the page MUST also use the whole remaining column (no centered `max-w` cap leaving canvas in front
  of the panel on a wide screen).
- **FR-015**: Neither FR-013 nor FR-014 may introduce horizontal overflow at 320 px or break the
  phone layout (the side menu and the docked panel only exist from 1024 px).

## Success Criteria *(mandatory)*

- **SC-001**: In full screen with the chat open, the conversation is visible and one message can be
  sent and answered; measured by an e2e test at a desktop viewport.
- **SC-002**: With the chrome hidden and the panel open, the project header's tool strip is fully
  visible and clickable (nothing under the panel), verified by an e2e assertion on the control's
  bounding box versus the panel's.
- **SC-003**: A simulated deployment (the served `index.html` pointing at another bundle) produces
  the notice in less than one check period, and the same test with the unchanged document produces
  no notice.
- **SC-004**: Searching a list of projects narrows it to the matches in a single keystroke-driven
  render, announces the count, and needs no network request.
- **SC-005**: The computed root font size is 13 px at 768 px, 1024 px and 1440 px, and 13.5 px at
  1920 px; the reference's own stylesheet is cited as the evidence in the spec and the code comment.
- **SC-006**: Collapsing the menu leaves an icon rail narrower than half the menu, keeps every link's
  accessible name and target size, moves the content with it, and survives a reload; with the chat
  docked, the gap between the page and the panel is at most 1 px and there is no horizontal
  overflow at any tested width.

## Assumptions

- **"A new version" means a new front-end build.** The backend and the front end ship as separate
  images (Caddy serves the bundle), so the only signal both sides share is the deployed entry
  document; comparing the entry asset the page is running with the one the server serves is precise,
  dependency-free and works in every deployment, including a development server (which never
  changes its entry).
- **The notice is a banner, not a modal** (the product forbids modals): it appears at the top of the
  content, it is dismissible, and it does not interrupt.
- **Search is client-side** over the list the page already loaded (the endpoint returns every
  project of the installation); the filters of the reports pages are a different feature.
- **"Full screen" keeps its meaning**: the browser's own full screen plus the app's chrome stepping
  aside (024). The chat panel is a side panel, never a page.
- **Out of scope**: auto-updating the bundle in place, service workers, a version history screen,
  server-side search, and any change to the report/ETL engine.

## Decisions taken while implementing (2026-10-14/15)

- **The docked panel owns its whole column** (FR-002, owner 2026-10-15). It was `top-16`, i.e. it
  started below the top bar — but the top bar lives *inside* the content column (the shell reserves
  the panel's column with `lg:pr`), so the panel column above the panel was painted with the page's
  canvas colour: an empty band at the top of the chat. The panel is now `inset-y-0`, so it reaches
  the top and the bottom of the viewport; the only thing it covers is its own column, and an e2e
  test asserts the top bar's own controls still end before the panel's left edge.
- **The chat's edge is the IDE's divider** (owner, 2026-10-15: *"the space between chat and [the
  page] is exaggerated — use the same space between the file explorer and the result view"*). The
  docked panel used to carry a 1 px border **and** `shadow-raised`, whose 30 px blur spilled a
  ~10 px halo into the page: measured on the owner's screenshot, the separation was a 10 px gradient
  plus a 1 px line, against the reference's flat 6 px band. The panel now paints the IDE's own
  divider — a `w-1.5 bg-line` strip (0.375 rem, so it follows the type scale exactly like the pane
  separator) inside its left edge — and casts no shadow; measured on a capture, the seam is a flat
  6 px band, identical to the file-explorer/editor divider. A border was tried first and rejected:
  browsers snap `border-width` to whole device pixels (4 px for 4.875 px), so the seam no longer
  matched the divider and the e2e assertion comparing the two could not hold. The content column,
  which was capped at `max-w-screen-2xl` and centered, also stopped being centered while the panel
  is docked (on a 2560 px screen the cap left ~160 px of canvas in front of the chat; measured
  afterwards: `#main.right` equals the panel's left edge, 2047 = 2047).
- **The update check reads `index.html`, not a version endpoint.** The backend is not involved: the
  front end is served by Caddy as a static bundle whose entry script carries the build hash, so
  comparing the entry the page is running with the deployed one detects a new build exactly, needs
  no new endpoint and no schema change (FR-011), and stays inert on a development server (whose
  entry never changes). The reference check inside the report page (`/api/reports/:id/version`)
  stays what it is: a new *data version* is a different thing from a new *build*.
- **The tablet band is now the reference's.** Customer A's stylesheet has no tablet band — its 13 px
  applies from 641 px up — so the 14 px band of 024 is gone. Measured from that stylesheet: `html`
  13 px, `@media(max-width:640px)` 12.5 px, `@media(min-width:1536px)` 13.5 px. This app keeps
  **15 px on phones** (12.5 px is too small for its dense IDE screens beside a 16 px form control)
  and its own `sm` breakpoint (640 px) as the band boundary, one pixel from the reference's — the
  two deviations are deliberate and asserted by a test.
- **TV mode keeps the chat out.** The report's TV mode is meant to be looked at, so it asks the
  shell to hide the chat with the rest of the chrome (`useHideShellChrome(tv, false)`); the
  project's full screen is meant to be worked in, so the panel is rendered there (FR-001).
- **The chat column stays reserved with the chrome hidden** (FR-003): the shell keeps the panel's
  right padding in full screen, so the project's own tool strip is never under the panel.
- **Search is local and accent-folding** (`src/lib/search.ts`), and the clear control is both the
  in-field ✕ and the button of the no-match state (the e2e test targets the latter when both are on
  screen).
- **One a11y defect fixed on the way**: the hidden `.zip` file input had no accessible name (it was
  reached through the button that opens it). axe flagged it once the projects page was audited with
  a list on screen; it now carries `aria-label` (FR-007's field and this input are the two changes
  the audit surfaced).
- **The menu folds away, and the gutters shrink** (owner, 2026-10-15: *"allow collapse left menu,
  blank space between chat is too wide, and left blank space below menu too"*). Three answers to one
  complaint: the sidebar collapses to an icon rail from a control that sits right under the menu it
  acts on (labels stay as tooltips and keep their accessible names, the choice is remembered per
  browser like the theme, not on the account); the content column no longer reserves a gutter next
  to the docked panel — the page ends where the panel begins and the panel's own border is the only
  separation, measured by the e2e test as ≤ 1 px; and the padding next to the menu and the top bar
  dropped from three spacing units to one, including the space under the top bar, so the menu band
  itself is shorter (the control used to be pinned to the very bottom of the screen, which split
  the left-over space in two).
- **Nothing left at 14 px** (owner, 2026-10-15: *"14x is to much is 13px"*). The reference's
  desktop size is a flat 13 px, so no ordinary UI text stays above it: the 14 px tablet band of 024
  is gone (13 px applies from 640 px) and the shell's brand and navigation, which were hardcoded at
  15 px and therefore ignored the root scale — the two elements that made this sidebar read bigger
  than the reference's — are rem-sized now and render at 13 px. Sizes *below* 13 px are left alone
  (the dense IDE uses `text-sm`, measurable in the same audit), and headings keep their step
  (`text-lg` for the project title and card headings) because hierarchy is not body text; say the
  word and the headings come down too. The changelog's stale "14 px on tablets" sentence was
  corrected, and the e2e test asserts the sidebar's brand and links compute to 13 px.
