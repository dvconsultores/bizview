# Implementation Plan: One mobile-first design system

**Branch**: `050-ui-design-system` (worked on `main`) · **Date**: 2026-11-02 ·
**Spec**: [spec.md](./spec.md)

## Summary

Three of the four defects are one-line causes in three files; the fourth (mobile-first) is absent by
construction because nothing wrote the rules down. This plan puts the rules in **one place** —
`frontend/src/lib/layout.ts` for the class strings, `docs/DESIGN-SYSTEM.md` for the reasoning — and
makes the two repeated controls (theme, language) a single component so they cannot answer
differently again. Then it corrects the screens and adds the guard tests that keep them corrected.

No new styling system, no component library, no backend change.

## Technical Context

**Language/Version**: TypeScript 5, React 19, Vite, Tailwind CSS (existing)
**Primary dependencies**: none added
**Testing**: Vitest + Testing Library-style DOM assertions (unit), Playwright (e2e, real stack)
**Target Platform**: mobile-first web client, 320 px → 1920 px
**Constraints**: theme tokens only (no literal colours), WCAG 2.2 AA, safe-area insets, 200 % zoom
**Scope**: the six screens, plus any page that repeats the same mistakes

## Constitution Check

| Principle | Effect |
|---|---|
| I. Mobile-first, always | **This feature is that principle, made concrete** |
| IV. Folder separation | `lib/` tokens, `components/` shared UI, `pages/` composition — no new folder |
| V. Fixed stack | No dependency added |
| VII. Many installations | Themes imported and built-in keep working: every surface reads tokens |
| VIII / IX | Untouched |
| Constraints | No literal colour (checked by the existing `no-raw-colors` test); two languages for every string |

**Gate: PASS.** No amendment: nothing here changes a principle, it applies one.

## Phase 0 — Research

See [research.md](./research.md): R1 tokens over per-page classes, R2 one segmented component,
R3 a documented height for split panes instead of a magic number, R4 guards that are greps not pixel
diffs, R5 what the audit deliberately leaves alone.

## Phase 1 — Design

- **[data-model.md](./data-model.md)**: the token set and the segmented-control contract.
- **[contracts/ui-contract.md](./contracts/ui-contract.md)**: what a page, a card, a header and a
  split pane must satisfy, written so a reviewer can check them.
- **[quickstart.md](./quickstart.md)**: how to see the fix and how to prove it.

## Work breakdown

1. Tokens + docs: `lib/layout.ts` (page stack, card padding, split height), `docs/DESIGN-SYSTEM.md`.
2. `SegmentedControl`; `ThemeSwitcher` and `LanguageSwitcher` rebuilt on it (fixes evidence 3, 4).
3. `PageHeader` mobile-first; applied consistently.
4. Appearance: container, 1/2/3 grid, equal heights, compact preview (fixes 1, 2).
5. Help: bounded independently scrolling panes; mobile list ⇄ article (fixes 5, 6).
6. Account menu: grouped sections, bounded scroll, focus restoration.
7. Guards: unit tests for the segmented control, the grids, the Help panes, and a source scan for
   narrow `max-w` on page roots.
8. e2e: `design-system.spec.ts` with screenshots at 375 / 768 / 1440, light and dark.
9. CHANGELOG.

## Risks

- **Moving `PageHeader` changes every page.** Mitigated: it keeps its props and its accessible
  heading; only its box and type scale change, and the existing page tests plus axe cover it.
- **A bounded height can clip.** Mitigated: heights are `max-height` with `overflow: auto`, so a
  short viewport scrolls inside the panel instead of cutting content, and the e2e checks the end of
  a long article is reachable.
- **Guards can be brittle.** Mitigated: they assert properties (no `max-w-*` on a page root, a
  segmented group has `grid`), not markup snapshots.
