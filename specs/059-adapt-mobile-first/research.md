# Research — mobile-first sign-in and sheet

Feature 059. Each decision says what it replaces and what was rejected.

## R1 — Full height: `100dvh`, not `100vh`

**Decision**: the phone sheet uses `height: 100dvh` (with `100vh` as the fallback line before it).

**Rationale**: `100vh` on Android Chrome and iOS Safari is the *largest* viewport, so a `100vh` sheet
hides its footer under the URL bar — exactly the "footer covers the last control" complaint. `dvh`
tracks the visible height as the bar collapses.

**Alternatives**: `position: fixed; inset: 0` (works, but the footer then needs its own safe-area
maths and the sheet loses its transition), `calc(100vh - 56px)` with a guessed bar height (wrong on
every device).

## R2 — One label per control

**Decision**: the section title of each control becomes the control's own label; the duplicate
`<h3>` + label pair disappears. Where a group title is genuinely useful (the two tabs) it stays in
the tab strip.

**Rationale**: `PERÍODO` + `Período` costs 24 px of vertical rhythm per control and reads like a
bug. Four controls × 24 px is a quarter of the phone screen.

**Alternatives**: keep the heading and drop the label (breaks the label-control association for
screen readers), smaller section titles (still duplicated).

## R3 — Chip rows for palette and theme

**Decision**: palette (with its swatch) and light/dark become one-line horizontal chip rows with
`overflow-x-auto` and `scroll-snap`, instead of selects.

**Rationale**: the options are few and visual; a select opens a native sheet on top of ours, which on
a phone is a second modal over a full-screen one.

**Alternatives**: radio list (tall), keep selects (two nested sheets).

## R4 — History entry for the sheet

**Decision**: opening the sheet pushes a `history.pushState({ sheet: true })`; `popstate` closes it;
closing from the UI calls `history.back()` when the entry we pushed is current, otherwise closes
directly.

**Rationale**: the physical back button is the primary "close" of a full-screen surface on Android;
without an entry it navigates away from the dashboard and loses the user's place.

**Alternatives**: `beforeunload` (no), intercepting back with a sentinel route (heavier, and the
report page already owns the URL for filters).

## R5 — No drag handle on phones

**Decision**: the handle and the swipe-to-close gesture are desktop-only (≥ 640 px bottom sheet) and
absent on the full-screen phone sheet.

**Rationale**: a 40 × 6 px target on a full-screen surface is an accident waiting to happen, and the
header's `×` plus Back already close it.

**Alternatives**: keep the handle for discoverability (it implies "this is partially open", which is
false when it is the whole screen).

## R6 — Providers in one row

**Decision**: Google and Telegram share a row of two equal buttons (icon + short label) when both are
enabled; a single enabled provider takes the full width.

**Rationale**: two stacked 48 px buttons plus the divider is ~120 px the 640 px screen does not have.
Two words fit in a 160 px column at 14 px.

**Alternatives**: icon-only buttons (unclear which provider), a "more options" menu (hides the
providers behind a tap).

## R7 — Where the compact scale lives

**Decision**: utilities in the components (`min-h-tap`, `text-sm`, `gap-3`) with two new Tailwind
screens already implied by the design system (`< 640` is Tailwind's default `sm`), and no new token.

**Rationale**: 050 owns the token vocabulary; adding `--space-compact` for four components would be a
second scale to keep in step.

**Alternatives**: a new token set (drift), CSS custom properties per component (same drift, less
discoverable).
