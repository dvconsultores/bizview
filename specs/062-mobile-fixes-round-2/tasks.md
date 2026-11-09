# Tasks — 062-mobile-fixes-round-2

Feature: [spec.md](./spec.md) · Plan: [plan.md](./plan.md) · Contract:
[contracts/mobile-fixes.md](./contracts/mobile-fixes.md) · Research: [research.md](./research.md)

Each fix ships with the test that measures it: four of the five were marked done before, and only a
measurement finds them (R6).

## Phase 1 — US1: one provider per row

- [X] T001 [US1] `frontend/src/pages/SignIn.tsx`: the provider block is always `space-y-3`, one
  full-width button per provider; remove the `grid-cols-2` branch and the short-label ternaries
  (FR-001, FR-002)
- [X] T002 [US1] `frontend/src/components/GoogleSignInButton.tsx`: drop the `compact` prop and the
  `sm:hidden` label swap; the button is 48 px, icon left, full label (FR-002)
- [X] T003 [US1] `frontend/src/i18n/{es,en}.ts`: remove `google.signInShort` / `telegram.signInShort`
  if nothing else reads them (the catalogue test refuses unused keys)
- [X] T004 [P] [US1] `frontend/tests/unit/sign-in.test.tsx`: both providers are two stacked
  full-width buttons at 360 and at 1280 (no grid class, no short label)

## Phase 2 — US2: the sheet on a phone

- [X] T005 [US2] `frontend/src/components/report/ReportSheet.tsx`: the footer publishes its height
  (`data-sheet-footer`, `--sheet-footer`), the body reserves
  `calc(var(--sheet-footer) + env(safe-area-inset-bottom))`; no handle below 640 px (FR-003, FR-004)
- [X] T006 [US2] `frontend/src/components/report/ParamsForm.tsx`: verify and finish 059's density —
  one label per control, 44 px controls, 12 px gaps, Período + Comparar con in one row from 320 px
  (FR-005)
- [X] T007 [P] [US2] `frontend/tests/unit/report-sheet-params.test.tsx`: the body's padding comes from
  the footer's height variable; the panel keeps its existing label/order assertions

## Phase 3 — US3: the maximized title and header

- [X] T008 [US3] `frontend/src/pages/ReportView.tsx`: `maximizedTitle()` resolves component title →
  view title → KPI metric label → text's first words → report title; never the id (FR-006)
- [X] T009 [US3] `frontend/src/components/report/CardDialog.tsx`: two-row header grid — title +
  `shrink-0` actions, then the chips; `min-w-0 truncate` title with `title=` full text (FR-007)
- [X] T010 [P] [US3] `frontend/tests/unit/card-dialog.test.tsx`: title text, one-line assertion,
  header grid classes, 44 px actions

## Phase 4 — US4: the pie/donut on a phone

- [X] T011 [US4] `frontend/src/components/report/charts/PieChart.tsx`: size from the measured
  container (`min(240, w − 32)`; maximized `min(w − 32, 0.6 h, 520)`), legend below under 640 px;
  no `window` read (FR-008, FR-009)
- [X] T012 [US4] `frontend/src/components/report/charts/ChartCard.tsx`: keep a minimum height on the
  measured box so the ring is laid out before data arrives (FR-008)
- [X] T013 [P] [US4] `frontend/tests/unit/pie-chart.test.tsx`: svg width at 360 for card and maximized,
  legend below vs beside, single-slice circle

## Phase 5 — US5: the source form's actions

- [X] T014 [US5] `frontend/src/pages/admin/SourceForm.tsx`: static actions at the end of the form,
  **Guardar** → **Probar conexión** → **Eliminar fuente**, full width on phones, `pb-safe` (FR-010)
- [X] T015 [US5] `frontend/src/pages/admin/UserForm.tsx`, the integration settings and appearance
  screens: same treatment where they copied the bar (FR-011)
- [X] T016 [P] [US5] `frontend/tests/unit/no-floating-actions.test.ts`: a gate that refuses
  `sticky bottom-20` and `writing-mode` anywhere in `src/` (FR-012)

## Phase 6 — Sweep and evidence

- [X] T017 `tests/e2e/mobile-fixes.spec.ts`: the five contracts measured at 360 × 780 and
  393 × 851, light and dark (SC-001 … SC-004)
- [X] T018 `specs/059-adapt-mobile-first/tasks.md`: record where 062 finished 059's sheet work, and
  `specs/056-layout-polish/tasks.md`: the convergence note for the maximized title
- [X] T019 `CHANGELOG.md` under *Unreleased*; no constitution change

## Verification (2026-11-09)

- `frontend/tests/e2e/mobile-fixes.spec.ts` — **14 passed** (`chromium-375`, viewports set per test).
- `mobile-first.spec.ts` (059) and `layout-maximized.spec.ts` (056b) — **40 passed**, after the 059
  provider case was rewritten to the new decision and its password-eye geometry kept.
- `vitest` — **800 passed** (79 files), including the new `card-title`, `card-dialog-pie`,
  `source-form-actions` and `layout-guards` suites; `tsc --noEmit` and `--noUnusedLocals` clean.
- `scripts/gates/all.sh` — all pass; `scripts/check_docs_parity.py` — 90 pairs.

Two findings the measurements produced beyond the brief, both recorded in [research.md](./research.md):

- **R7**: `h-11` is a *rem* length — 41 px at the app's 15 px phone root. 056b's dialog actions were
  three pixels short of the 44 px the product promises; they now use `min-h-tap`/`min-w-tap`.
- **R8**: "the title is ≥ 60 % of the header" cannot hold at 360 px with five 44 px targets (328 px
  header, ~140 px of actions). The requirement is implemented as its measurable intent — more than
  half the header, one line, never stacked — and the arithmetic is in the contract.

## Follow-up (owner, 2026-11-09): "parameters and filter in mobile need a little bit more wide"

- [x] T020 [US2] The sheet's body gutter is 12 px on phones (16 from 640 px), and the period row's
  column floor is 130 px instead of 160, per FR-005 (partial). Two measurements caused the complaint:
  the 16 px gutter left 328 px at 360 px, and `minmax(160px,1fr)` needs 332 px for two columns plus
  the 12 px gap — so **Período and Comparar con stacked**, and every control read as narrow. Now the
  pair shares the row from 320 px (as 059 promised) and each control is ≥ 150 px wide at 360 px.
  *Verified by* `tests/e2e/mobile-fixes.spec.ts` ("uses the whole width", measuring the computed
  gutter and both boxes) and `tests/unit/report-sheet-phone.test.tsx`.

## Follow-up 2 (owner, 2026-11-09): the report's own control row

- [x] T021 [US2] The **Filtros · Parámetros · ⋯** row fills the phone's width. Below 420 px the row was
  a content-sized flex item — 203 px of a 336 px line — so the three controls hugged the left edge and
  a third of the row was empty. It is now `w-full max-[420px]:flex-nowrap` with each control `flex-1`
  (the menu trigger `w-full`), which gives three equal ~106 px targets and keeps every one ≥ 44 px
  tall. *Verified by* `tests/e2e/mobile-fixes.spec.ts` ("fills the phone's width instead of hugging the
  left edge": each control ≥ 80 px wide, ≥ 44 px tall, row reaching the page's right edge) and
  `tests/unit/app-shell-phone.test.tsx`.
