# Implementation Plan: Mobile-first sign-in and filter sheet

**Branch**: `059-adapt-mobile-first` | **Date**: 2026-11-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/059-adapt-mobile-first/spec.md`

## Summary

Redesign two screens at 360 px first and let them widen: `/ingresar` becomes one screen with the
language toggle under the header, a compact hero that does not overlap the card, 44 px inputs and the
providers in a row; the **Filtros | Parámetros** sheet becomes a full-height sheet on phones with a
single compact control scale, no drag handle, no repeated section titles, a sticky footer and a
history entry. The same compact scale fixes the top bar and the dashboard title block.

## Technical Context

**Language/Version**: TypeScript 5, React 18, Vite, Tailwind 3 (existing).

**Primary Dependencies**: none new. `lucide-react` icons, `react-router` history, the existing
`ReportSheet`, `Input`, `PasswordField`, `Button`, `Card`, `LanguageSwitcher` components.

**Storage**: none — presentation only.

**Testing**: `vitest` + Testing Library (jsdom, no layout engine: geometry is asserted in Playwright),
`@axe-core/playwright`, the existing `tests/e2e` browser matrix (320/375) and `scripts/gates/all.sh`.

**Target Platform**: mobile-first web, 320 px up; iOS/Safari 14+ and Android Chrome.

**Project Type**: frontend only, inside the existing web application (`frontend/src`).

**Performance Goals**: no layout shift on open, sheet animation ≤ 200 ms, no extra network request.

**Constraints**:
- the design system of 050 owns colours, spacing tokens and radii; this feature adds utilities and
  a compact scale, never a new token vocabulary;
- `tests/unit/no-modals.test.ts` forbids dialogs outside `CardDialog.tsx`: the sheet stays a labelled
  `region` (FR-019), which is also why it keeps focus trapping by hand;
- layouts from 640 px up must not change (SC-007).

**Scale/Scope**: 2 screens, 2 components (top bar, title block), ~8 files, no API change.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | This plan |
|---|---|---|
| I. Mobile-first, always | 320 px, WCAG 2.2 AA | the whole feature: verified at 320/360/393/414 px with geometry assertions and axe |
| II–IV, VI–IX | data/engine/stack/structure | untouched (no request, no table, no dependency) |
| V. Fixed stack | no new component | Tailwind utilities and existing components only |
| 050 design system | tokens, not ad-hoc values | the compact scale is expressed with the existing tokens (`min-h-tap`, `text-sm`, `gap-*`); no new colour |

**Result**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/059-adapt-mobile-first/
├── spec.md
├── plan.md
├── research.md          # decisions: dvh, history entry, one label per control, chips vs selects
├── contracts/
│   └── mobile-shell.md  # the measurable UI contract (sizes, breakpoints, behaviours)
├── quickstart.md        # how to reproduce and measure
└── checklists/requirements.md
```

### Source Code (repository root)

```text
frontend/src/
├── pages/SignIn.tsx                       # compact hero, toggle under the header, provider row
├── components/report/ReportSheet.tsx      # full height < 640 px, sticky footer, no handle, history
├── components/report/ReportSheetTabs.tsx  # (extracted) the tab strip of the header
├── components/report/ReportParamsPanel.tsx# one label per control, period/comparison row, chips
├── components/report/ParamsForm.tsx       # density, labels, search box for long filter lists
├── components/LanguageSwitcher.tsx        # segmented control, 44 px targets
├── components/Input.tsx, PasswordField.tsx# 44 px on phones, helper 14 px
├── components/AppShell.tsx                # top bar: logo + organisation + theme + avatar
├── pages/ReportView.tsx                   # title block 22/14 px, actions as icon buttons < 420 px
├── i18n/{es,en}.ts                        # only if a string changes
└── tests/unit/{sign-in,report-sheet-params}.test.tsx
frontend/tests/e2e/mobile-first.spec.ts    # geometry + axe at 360/393/414/768/1280, both themes
```

## Phase 0 — Research

See [research.md](./research.md): `100dvh` over `100vh` (mobile URL bar), a history entry via
`history.pushState` + `popstate`, one label per control by removing the section wrapper titles,
palette/theme as chip rows instead of selects, and no drag handle on phones (an accidental drag would
close a full-screen sheet).

## Phase 1 — Design

- [contracts/mobile-shell.md](./contracts/mobile-shell.md) — the numbers a reviewer measures.
- [quickstart.md](./quickstart.md) — how to reproduce the two screens and run the proofs.

## Phase 2 — Tasks

See [tasks.md](./tasks.md).

## Re-evaluated Constitution Check (post-design)

PASS. Nothing structural moves: the sheet keeps its `region` role and focus trap, the sign-in page
keeps its form semantics, and the compact scale reuses the tokens of 050.

## Complexity Tracking

| Decision | Why | Simpler alternative rejected |
|---|---|---|
| A history entry for the sheet | a phone user reaches for Back; on a full-screen sheet there is nothing else to reach for | a close button only: the phone's Back would leave the dashboard |
| Chip rows for palette and theme | a select hides the options a phone user came to see | keeping the selects: one more tap and a native sheet on top of ours |
| Full height instead of 85 % on phones | a quarter of the screen showing a greyed dashboard is not information | 85 %: still a wasted strip, still a drag handle over it |
