# Implementation Plan: Mobile fixes, round 2

**Branch**: `062-mobile-fixes-round-2` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

## Summary

Five independent defects on the phone, all in the frontend: the sign-in provider row (revert a 059
decision), the sheet's height and footer reservation (059's remaining gap), the maximized card's
title and header grid (056b's fallback to the component id), the pie/donut's fixed 240 px ring, and
the source form's floating action bar. Each one is fixed where it is drawn, plus the tests that measure
it, since four of the five were "done" before and only a measurement would have found them.

## Technical Context

**Stack**: React 19 + TypeScript, Tailwind with the product's tokens, `vitest` + Testing Library for
units, `Playwright` for geometry at a fixed viewport. No backend, no API, no migration.

**Key constraint — measure, don't estimate**: `useChartWidth` already exists (`charts/chartScale.ts`)
and is a `ResizeObserver` on the element; the pie ignores it. The sheet is already `h-dvh`; the body
does not reserve the footer. In both cases the code *looks* right and the geometry is wrong, so every
fix ships with a test that asserts a measurement (a px width, a scroll height, a computed position),
not a class name.

**Layout budget at 360 px**: 16 px page gutters → 328 px content; a card's `p-5` leaves 288 px for its
body; the chart ring must therefore be `min(240, 288 − 32) = 240`. In the dialog the body is `p-4`
(32 px), so a 360 px phone gives 328 px of content, and the ring takes it whole (the dialog is already
padded) — `min(width, 60vh, 520)` — which is what makes the ring at least 300 px maximized. In a card
the gutter is the card's own, so the ring is `min(240, width − 32)`.

## Constitution Check

| Principle | How it is satisfied |
|---|---|
| Mobile first | The five fixes are the principle applied at 360 px; the sweep in SC-001 is the guard. |
| No modals | `CardDialog` stays the single, named exception; the sheet stays a `region`. |
| Tokens, no literals | Only layout classes; no new colour, no new font size outside the scale. |
| i18n | One label may disappear (`google.signInShort`, `telegram.signInShort` if unreachable) — the catalogue test refuses unused keys, so they are removed with the code that used them. |
| Tests before merge | Unit tests for the classes and the title resolution, Playwright for the geometry. |
| Token discipline | 44 px is `min-h-tap`/`min-w-tap` (px), not `h-11` (rem): the root is 15 px on a phone, so a rem height measured **41 px**. `h-11` on the dialog's actions was a latent 3 px shortfall from 056b that the e2e caught. |

**Gate: PASS.**

## Files

```text
frontend/src/pages/SignIn.tsx                     # one provider per row
frontend/src/components/GoogleSignInButton.tsx    # drop the `compact` variant
frontend/src/components/report/ReportSheet.tsx    # body reserves the footer; measured
frontend/src/pages/ReportView.tsx                 # maximizedTitle(): title, view, metric label
frontend/src/components/report/CardDialog.tsx     # two-row header grid
frontend/src/components/report/charts/PieChart.tsx # container-measured ring, legend below
frontend/src/components/report/charts/ChartCard.tsx # pass the measured width/height, no min-height guess
frontend/src/pages/admin/SourceForm.tsx           # static actions
frontend/src/i18n/{es,en}.ts                      # drop the short provider labels if unused
frontend/tests/unit/*.test.tsx                    # one per defect
tests/e2e/mobile-fixes.spec.ts                    # geometry at 360 and 393, both themes
```

## Phase 0 — research

See [research.md](./research.md) R1–R6: why the sheet's footer overlaps although it is a sibling, why
the title collapses to one letter per line, what a maximized KPI can be titled from, how to measure a
chart without `window`, why the action bar must be static, and what the previous features' tests
asserted so the new ones do not repeat their blind spot.

## Phase 1 — design

[contracts/mobile-fixes.md](./contracts/mobile-fixes.md): the geometry contract each fix must satisfy,
as the numbers the Playwright suite asserts.
