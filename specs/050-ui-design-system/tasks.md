---
description: "Task list — 050 design system"
---

# Tasks: One mobile-first design system

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md) ·
[data-model.md](./data-model.md) · [contracts/ui-contract.md](./contracts/ui-contract.md) ·
[quickstart.md](./quickstart.md)

## Phase 1 — Tokens and the written rules

- [X] T001 Add `PAGE_STACK`, `CARD_PAD`, `PANEL_MAX_H`, `PANEL_SCROLL`, `SPLIT_COLS` to `frontend/src/lib/layout.ts`, each with the rule it encodes
- [X] T002 Write `docs/DESIGN-SYSTEM.md`: the tokens table, the page/card/header/segmented/split contract, the viewport matrix, and why the guards exist

## Phase 2 — One segmented control (evidence 3, 4)

- [X] T003 Create `frontend/src/components/SegmentedControl.tsx`: radiogroup/menuitemradio, roving tabindex, arrow keys, always a grid
- [X] T004 Rebuild `ThemeSwitcher` on it, keeping its props, `compact` and the account-menu mode
- [X] T005 Rebuild `LanguageSwitcher` on it, keeping its options, `compact` and persistence
- [X] T006 Add `frontend/tests/unit/segmented.test.tsx`: one row, one checked, keyboard, in-menu variant
- [X] T007 Keep `frontend/tests/unit/language-switcher.test.tsx` and `theme.test.ts` green

## Phase 3 — Page header and the appearance library (evidence 1, 2)

- [X] T008 Make `PageHeader` mobile-first: compact heading, subtitle, wrapping action row, no oversized box
- [X] T009 Correct `frontend/src/pages/admin/Appearance.tsx`: drop `max-w-4xl`, use `APP_PAGE`, 1/2/3 column grid, equal heights, compact preview, actions in a fixed place
- [X] T010 Update `frontend/tests/unit/appearance-page.test.tsx` for the new structure and add the column/selection assertions

## Phase 4 — Ayuda (evidence 5, 6)

- [X] T011 Rework `frontend/src/pages/Help.tsx`: bounded independently scrolling panes at `lg`, list ⇄ article below it, Back preserving search and position
- [X] T012 Extend `frontend/tests/unit/help-page.test.tsx`: pane tokens, mobile flow, Back restores

## Phase 5 — Account menu and the app-wide audit

- [X] T013 Group and bound the account menu in `frontend/src/components/AppShell.tsx`; restore focus to the trigger on close
- [X] T014 Audit pages for the same three mistakes (narrow root, hand-rolled options, unbounded split) and correct what repeats them

## Phase 6 — Guards and evidence

- [X] T015 Add `frontend/tests/unit/design-guards.test.ts`: no `max-w-*` on a page root; every segmented container has `grid`; every scrolling pane has `min-h-0 overflow-y-auto`
- [X] T016 Add `frontend/tests/e2e/design-system.spec.ts`: the six screens at 375 and 1440, light and dark, no horizontal overflow, long article reachable, screenshots to `docs/assets/design-system/`
- [X] T017 Run the full suites: `npx tsc --noEmit`, `npx vitest run`, `scripts/gates/all.sh`
- [X] T018 CHANGELOG under Unreleased
