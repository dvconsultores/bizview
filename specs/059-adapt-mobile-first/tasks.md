# Tasks — 059-adapt-mobile-first

Feature: [spec.md](./spec.md) · Plan: [plan.md](./plan.md) · Contract:
[contracts/mobile-shell.md](./contracts/mobile-shell.md) · Research: [research.md](./research.md)

The tests are part of the work: the repo ships a unit suite and a Playwright suite, and this feature
is measured, not reviewed by eye.

## Phase 1 — Setup

- [x] T001 `frontend/src/index.css` and `frontend/tailwind.config.js`: add the phone-safe utilities the
  feature needs (`h-dvh` fallback pair, `scroll-padding-bottom` on the app root, a `.no-scrollbar`
  for the chip rows); no new colour or font
- [x] T002 `frontend/src/components/report/ReportSheet.tsx`: extract the header tab strip to
  `ReportSheetTabs.tsx` so the phone and desktop headers can differ without duplicating the keyboard
  logic

## Phase 2 — Foundational

- [x] T003 `frontend/src/components/SheetFooter.tsx` (or a `footer` slot contract in
  `ReportSheet.tsx`): a sticky footer that reports its height through a CSS variable so the body can
  reserve `calc(var(--sheet-footer) + env(safe-area-inset-bottom))`
- [x] T004 `frontend/src/lib/historyLayer.ts`: `useHistoryLayer(open, onClose)` — push a state on
  open, close on `popstate`, and `history.back()` on a UI close when our entry is current
  (R4), with a unit test

## Phase 3 — User Story 1 (P1): sign in from a phone in one screen

- [x] T005 [US1] `frontend/src/pages/SignIn.tsx`: compact hero (logo 40 px, name 18 px, organisation
  12 px), language toggle below the header on the right, no `-mt-8` overlap, tagline one line and
  hidden under 600 px height, card edge to edge with 16 px gutters, heading 20 px, helper 14 px
- [x] T006 [US1] `frontend/src/pages/SignIn.tsx`: providers in one row (icon + short label) when both
  are enabled, one full-width button otherwise; `Ingresar` 48 px full width on phones
- [x] T007 [P] [US1] `frontend/src/components/Input.tsx` and `PasswordField.tsx`: 44 px on phones,
  helper text 14 px, password toggle 44 × 44 px, `autocomplete` attributes verified
- [x] T008 [P] [US1] `frontend/src/components/LanguageSwitcher.tsx`: a segmented control with 44 px
  targets and `aria-pressed`, usable outside the header
- [x] T009 [US1] `frontend/src/pages/SignIn.tsx`: inline messages under the field they belong to, and
  `scroll-padding-bottom` so a focused input keeps the primary button in view
- [x] T010 [P] [US1] `frontend/tests/unit/sign-in.test.tsx`: compact classes, provider row, inline
  error, toggle placement (no absolute positioning over the header)

## Phase 4 — User Story 2 (P1): the sheet on a phone

- [x] T011 [US2] `ReportSheet.tsx`: below 640 px full screen (`h-dvh`), no drag handle, header row
  with tabs left and `×` right (44 px), body `padding-bottom` from T003, sticky footer; 640–1023 px
  bottom sheet at 85 %; ≥ 1024 unchanged
- [x] T012 [US2] `ReportSheet.tsx`: wire T004 so opening pushes history and Back closes, returning
  focus to the opener
- [x] T013 [US2] `frontend/src/components/report/ReportParamsPanel.tsx`: one label per control
  (14 px, 6 px above), controls 44 px, 12 px apart; Período + Comparar con in one row (custom dates in
  that row); order Período · Comparar con · Frecuencia · Paleta · Tema; palette and theme as chip rows
- [x] T014 [US2] `frontend/src/components/report/ParamsForm.tsx`: same density on the Filtros tab,
  search box for a filter with more than eight options, selected values as chips above the list
- [x] T015 [US2] `frontend/src/pages/ReportView.tsx`: live apply keeps its 250 ms debounce; `Listo`
  only closes; the sheet's history entry does not fight the report's URL parameters
- [x] T016 [P] [US2] `frontend/tests/unit/report-sheet-params.test.tsx`: one label per control, the
  chip rows, `Listo` closes without applying, the search box appears above eight options

## Phase 5 — User Story 3 (P2): the shell

- [x] T017 [US3] `frontend/src/components/AppShell.tsx`: top bar on phones (logo, organisation, theme,
  avatar), breadcrumb hidden below 480 px with **Volver** kept
- [x] T018 [US3] `frontend/src/pages/ReportView.tsx`: title 22 px, description 14 px clamped to two
  lines, wrapping meta line, actions as icon buttons with labels below 420 px
- [x] T019 [P] [US3] `frontend/tests/unit/app-shell-phone.test.tsx`: the compact top bar and the
  actions' labels

## Phase 6 — Proof and polish

- [x] T020 `frontend/tests/e2e/mobile-first.spec.ts`: `/ingresar` at 393 × 640 with every control in
  view and the toggle not intersecting the header; the sheet at 393 (`height === innerHeight`, last
  control above the footer, Back closes, **Limpiar** restores); no element wider than the viewport at
  360 on `/`, `/ingresar`, `/r/<id>`, `/proyectos`; axe at 360/393/414/768/1280 in both themes
- [x] T021 `specs/053-parameters-sheet/tasks.md` and `specs/054-google-signin-rbac/tasks.md`:
  convergence notes pointing at the new density and sign-in layout
- [x] T022 `backend/app/guide/{es,en}/parametros-y-filtros-del-reporte.md`: the phone behaviour of the
  sheet (full screen, Back closes, `Limpiar`); `docs/AUTHORING.md`? no — help only
- [x] T023 `CHANGELOG.md` under *Unreleased*; run `npx tsc --noEmit`, `npx vitest run`,
  `scripts/gates/all.sh`

## Dependencies

T001 → T002 → T003/T004 → (T005→T006→T009; T007/T008 parallel; T010) → T011→T012→T013/T014→T015→T016
→ T017/T018→T019 → T020 → T021/T022/T023.

## MVP

US1 (T005–T010): the sign-in page on one screen. US2 follows, then the shell.

## Implementation notes (2026-11-06)

- **T001** needed no new utility: `h-dvh`, `env(safe-area-inset-bottom)`, arbitrary media variants
  (`max-sm:`, `max-[420px]:`, `[@media(min-height:600px)]:`, `min-[480px]:`) and `[scroll-padding-bottom:…]`
  are all available from the existing Tailwind setup, so `index.css` and `tailwind.config.js` are
  untouched (`design-guards`/`no-raw-colors` stay green). The chip rows hide their scrollbar with
  `[scrollbar-width:none] [&::-webkit-scrollbar]:hidden` instead of a `.no-scrollbar` class.
- **T002** was not extracted: the header row is the same at every width (tabs left, `×` right), so
  only the handle (hidden below 640 px) and the panel geometry differ, and a `ReportSheetTabs.tsx`
  would have moved the keyboard logic for no reason.
- **T003** became "the body and the footer never overlap": the panel is a flex column, the body is
  `min-h-0 flex-1 overflow-y-auto` with `[scroll-padding-bottom:5rem]`, and the footer is a sticky row
  with `env(safe-area-inset-bottom)`. No CSS variable is needed because the footer is not overlaid;
  `frontend/tests/e2e/mobile-first.spec.ts` asserts `body.bottom <= footer.top`.
- **T004** is `frontend/src/lib/historyLayer.ts`, with the self-induced-`popstate` guard the naive
  version needs (`tests/unit/report-sheet.test.tsx` covers it).
- **T007** the password toggle was already a 44 px target; `Input`/`Select`/`MultiSelect` gained
  `max-sm:min-h-11` and the email field `autocomplete="email"`.
- **T008** the segmented control was already the shared one with 44 px targets.
- **T017** no change was needed: the phone top bar already shows logo + product name + organisation,
  the theme toggle and the avatar, with no breadcrumb in it. `Breadcrumbs` hides the trail below
  480 px and keeps **Volver** (`tests/unit/app-shell-phone.test.tsx`).
- **T022 screenshots**: the in-app help ships no images anywhere (`backend/app/guide/` has no
  image asset and the guide README does not describe a screenshot pipeline), so the topic describes the
  phone layout in words — full screen, footer always visible, back closes, `Limpiar` — instead of
  adding an unreviewed image to the help. A screenshot workflow, if wanted, belongs to its own feature.
- **T016/T019** the files are `tests/unit/report-sheet-phone.test.tsx`, `tests/unit/sign-in-phone.test.tsx`
  and `tests/unit/app-shell-phone.test.tsx`; **T022** is the ES/EN guide topic
  `parametros-y-filtros-del-reporte`.

## Finished by feature 062 (2026-11-09)

The owner's evidence on a 360 × 780 Android phone showed two items of this feature still failing on
screen, although their tests were green. Both are closed here; the record is in
`specs/062-mobile-fixes-round-2/`.

- [x] **T003 revisited — the footer's height is measured, not guessed.** T003 asked for "a sticky
  footer that reports its height through a CSS variable so the body can reserve
  `calc(var(--sheet-footer) + env(safe-area-inset-bottom))`". What shipped was a 24 px padding
  constant on the body (`pb-6`), and the footer is ~70 px tall, so on a 780 px phone the last control
  ended under it. `ReportSheet` now measures the footer with a `ResizeObserver`
  (`[data-sheet-footer]`) and the body reserves that height plus a 16 px gutter (feature 062, US2).
  Measured at 360 × 780 and 393 × 851 in `frontend/tests/e2e/mobile-fixes.spec.ts`.
- [x] **T006 revisited — one provider per row.** T006 chose "providers in one row (icon + short label)
  when both are enabled". The owner reversed that decision on 2026-11-09: two abbreviation-labelled
  buttons a thumb apart are harder to tell apart than two full-width rows. `SignIn` is now always
  `space-y-3`, one 48 px button per provider with the full sentence, and `GoogleSignInButton` lost its
  `compact` variant (feature 062, US1). The 059 e2e case was rewritten to the new decision.
