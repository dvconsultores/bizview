# Tasks: Updates notice, project search, full-screen chat and the type scale

**Input**: [spec.md](./spec.md) · **Feature**: `025-app-updates-and-search`

Every task names the file it touches. Research: the reference app's stylesheet
(`app.example-customer.com/assets/index--Ko3s9fK.css`) is the evidence for US4.

## Phase 1: Setup

- [x] T001 Confirm the reference type scale and the deployment topology (front end served by Caddy, backend separate) so the version check needs no backend change — `specs/025-app-updates-and-search/spec.md`

## Phase 2: Foundational

- [x] T002 Expose whether the shell chrome is hidden to the whole shell (`ShellChrome` context carries `hidden` and `setHidden`; `useHideShellChrome` keeps its API) — `frontend/src/components/ShellChrome.tsx`
- [x] T003 Add the language strings of this feature to both catalogues (`update.*`, `projects.search*`) — `frontend/src/i18n/es.ts`, `frontend/src/i18n/en.ts`

## Phase 3: User Story 1 — the chat in full screen (P1)

- [x] T004 [US1] Render the docked assistant panel while the chrome is hidden (drop the `chromeHidden` condition) — `frontend/src/components/AppShell.tsx`
- [x] T005 [US1] Reserve the docked panel's column with the chrome hidden as well, so the project's own controls are never covered — `frontend/src/components/AppShell.tsx`
- [x] T006b [US1] Give the docked panel its whole column instead of starting below the top bar (`inset-y-0`), which removes the empty canvas band above the chat — `frontend/src/components/assistant/AssistantPanel.tsx`
- [x] T006 [US1] Place the panel at `top-0` and, expanded, from the left edge when the chrome is hidden — `frontend/src/components/assistant/AssistantPanel.tsx`
- [x] T007 [US1] e2e: full screen with the chat open shows the panel at the top of the viewport, the project tool strip stays clickable, and the conversation sends a message — `frontend/tests/e2e/projects.spec.ts`
- [x] T007b [US1] e2e: with the chrome visible the docked panel starts at the top of the viewport, reaches the bottom, leaves nothing but itself in its top corner and ends after the top bar's own controls — `frontend/tests/e2e/projects.spec.ts`

## Phase 4: User Story 2 — the new-version notice (P1)

- [x] T008 [US2] Version watcher: read the entry asset the page is running, fetch the deployed entry document without cache, compare, and poll only while the tab is visible (plus immediately on return); silent on any failure — `frontend/src/lib/appVersion.ts`
- [x] T009 [US2] Dismissible notice with the *Recargar* action, no modal, no focus steal — `frontend/src/components/UpdateBanner.tsx`
- [x] T010 [US2] Render the notice at the top of the shell content (visible in full screen too) — `frontend/src/components/AppShell.tsx`
- [x] T011 [US2] Unit tests: identical entries show nothing; a changed entry shows the notice; a missing entry script is inert; a failing fetch is silent — `frontend/tests/unit/app-version.test.tsx`
- [x] T012 [US2] e2e: intercept the entry document to simulate a deployment and assert the notice, the dismissal and its absence without the interception — `frontend/tests/e2e/updates.spec.ts`

## Phase 5: User Story 3 — project search (P2)

- [x] T013 [US3] Search field with an accessible name, a placeholder, a clear control and a match count; filtering by name, identifier and description, case- and accent-insensitive — `frontend/src/pages/projects/Projects.tsx`
- [x] T014 [US3] No-match state naming the term with the way to clear it; the first-run empty state only when there are no projects at all — `frontend/src/pages/projects/Projects.tsx`
- [x] T015 [US3] Unit tests: narrows the list, counts matches, ignores accents and case, no-match message, clear control — `frontend/tests/unit/projects-page.test.tsx`
- [x] T016 [US3] e2e: type in the search at a desktop viewport, assert the filtered list and the no-match copy, then axe — `frontend/tests/e2e/projects.spec.ts`

## Phase 6: User Story 4 — the type scale (P3)

- [x] T017 [US4] Align the tablet band with the reference (13 px from 640 px) and document the two bands and the deliberate phone deviation in the stylesheet — `frontend/src/index.css`
- [x] T018 [US4] e2e: computed root font size at 768, 1024 and 1920 px, and the sidebar's brand and
  navigation at the scale (13 px) — `frontend/tests/e2e/projects.spec.ts`
- [x] T019 [US4] Remove the last hardcoded sizes above the scale: the shell's brand and navigation
  become rem-sized (owner: "14x is to much is 13px") and the stale "14 px on tablets" sentence in
  the changelog is corrected — `frontend/src/components/AppShell.tsx`, `CHANGELOG.md`

## Phase 6b: User Story 5 — a menu that folds away and tightly fitted gutters (P2)

- [x] T019b [US5] Collapsible left menu: `readNavCollapsed`/`writeNavCollapsed` (device choice) and the
  `//` control at the bottom of the sidebar with `aria-expanded`/`aria-controls`, tooltips and
  `sr-only` labels in the rail — `frontend/src/lib/navPrefs.ts`, `frontend/src/components/AppShell.tsx`, `frontend/src/i18n/{es,en}.ts`
- [x] T019c [US5] Tighten the shell: content column follows the rail width, no gutter between the
  content and the docked panel, one spacing unit next to the menu and the top bar — `frontend/src/components/AppShell.tsx`
- [x] T019d [US5] Unit tests for the remembered state (default, collapse, expand, junk, blocked storage) — `frontend/tests/unit/nav-prefs.test.ts`
- [x] T019e [US5] e2e: the rail is less than half the menu, labels still name the links, the content
  follows the rail, the choice survives a reload, axe; and the page meets the panel with ≤ 1 px of
  gutter — `frontend/tests/e2e/projects.spec.ts`
- [x] T019f [US5] Give the docked panel the IDE's own divider as its seam (a `w-1.5 bg-line` strip
  inside its left edge, no shadow) and stop capping/centering the content while it is docked; assert
  in e2e that the strip's width and colour equal the pane separator's and that a 2560 px viewport
  leaves no gap and no overflow — `frontend/src/components/assistant/AssistantPanel.tsx`,
  `frontend/src/components/AppShell.tsx`, `frontend/tests/e2e/projects.spec.ts`

## Phase 7: Polish

- [x] T020 Guide: describe the new-version notice, the project search and the collapsible menu, in both languages — `backend/app/assistant/guide/es/*`, `backend/app/assistant/guide/en/*`, `backend/app/assistant/guide/index.yaml`
- [x] T021 Changelog entry for the items of this feature — `CHANGELOG.md`
- [x] T022 Full validation: frontend unit + `tsc` + build, the touched Playwright specs, backend `ruff` and the guide tests

## Dependencies

- T002 and T003 block every user story.
- US1 (T004–T007b) is independent of US2, US3 and US4.
- US2 (T008–T012) depends on T003 only.
- US3 (T013–T016) depends on T003 only.
- US4 (T017–T019) is independent (T018 touches the same e2e file as T007/T016, so it runs after them).
- US5 (T019b–T019f) depends on T002 (the chrome state) and on T011c (the panel's column); T019e
  touches the same e2e file as T007/T016/T018, so it runs after them.
- T020–T022 close the feature.

## Implementation strategy

MVP is US1 + US2 (both P1): the reported defect and the silent failure. US3, US4 and US5 follow in
the same round because they are small, testable slices. Tests are part of the definition of done for
every user story.
