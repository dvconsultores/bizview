# Research — 050 design system

## R1 — Rules live in `lib/layout.ts`, not in pages

**Decision**: every repeated class string becomes a named export in `frontend/src/lib/layout.ts`
(`APP_PAGE`, `PAGE_STACK`, `CARD_PAD`, `PANEL_MAX_H`, `SPLIT_COLS`, …) and pages import them.

**Why**: feature 030 already did this for the container and it is the only rule that never drifted.
The other three defects are all "a page answered a shared question locally". A token is reviewable
and testable; a Tailwind class repeated in six files is neither.

**Rejected**: a CSS-in-JS layer or a component library (a second styling system — the brief forbids
it); leaving classes inline and relying on review (that is what produced the current state).

## R2 — One `SegmentedControl`, two thin wrappers

**Decision**: a new `components/SegmentedControl.tsx` owns the group role, the roving tabindex, the
`aria-checked` state, the icon slot and — crucially — the `grid` that makes the options share a row.
`ThemeSwitcher` and `LanguageSwitcher` keep their public props and their persistence and become
adapters that pass options to it.

**Why**: the defect is that the two components emitted different class lists, and one of them had
lost `grid`. Making the layout the component's property removes the possibility, not just the bug.

**Rejected**: adding `grid` to `ThemeSwitcher` alone (fixes today's screenshot, leaves the next
divergence); a `display: contents` trick (obscures the intent).

## R3 — Split panes are bounded by `max-height`, never by a fixed height

**Decision**: the Help grid gets `PANEL_MAX_H` — `lg:max-h-[calc(100dvh-var(--app-chrome,15rem))]` —
and each pane `overflow-y-auto min-h-0`. `--app-chrome` has a documented default; a page may set it if
its chrome differs.

**Why**: the brief forbids arbitrary fixed pixel heights, and it is right: 15 rem is a *bound*, and a
bound that is too small scrolls inside the panel rather than clipping, while one that is too large
lets the page scroll a little. `dvh` follows mobile browser chrome. `min-h-0` is what actually allows
a grid child to scroll — its absence is why the current page scrolls instead of the article.

**Rejected**: a ResizeObserver measuring the header (a runtime dependency on layout order for a
visual bound); `100vh` (wrong on mobile with a collapsing toolbars).

## R4 — Guards are properties, not screenshots

**Decision**: unit tests assert properties — a page root declares no `max-w-*`; a segmented group's
container includes `grid`; the Help panes carry `overflow-y-auto` and `min-h-0` — and Playwright only
captures evidence.

**Why**: the brief warns against brittle pixel comparisons. A pixel diff fails on a font upgrade and
passes on a structural regression; a property test does the opposite.

**Rejected**: `toHaveScreenshot()` baselines (maintenance cost, false failures across engines).

## R5 — The audit is bounded

**Decision**: the audit corrects pages that repeat the same three mistakes (a narrow page root, a
hand-rolled option list, an unbounded split). It does not restyle tables, reports or the IDE, and it
does not touch behaviour.

**Why**: the brief says "find and correct inconsistent layouts", and equally "do not introduce broad
refactors". The line is: same cause, fix; different cause, report.

**Rejected**: a page-by-page redesign (risk without a demonstrated defect).
