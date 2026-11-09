# Research — Mobile fixes, round 2 (062)

Four of these five defects were marked done by an earlier feature. That is the interesting part: what
was asserted, and why the screen still looked wrong.

## R1 — The sheet's footer covers the last control although it is a sibling

`ReportSheet` is `flex h-dvh flex-col` with a `min-h-0 flex-1 overflow-y-auto` body and a
`shrink-0` footer. Structurally the footer cannot overlap: it is not inside the scroll container.

What the owner sees is the *end of the scroll*: the body has `pb-6` (24 px) and the footer is
~70 px tall (button + padding + safe area). When the last control is a `min-h-tap` (44 px) element,
scrolling to the end puts its bottom edge 24 px above the body's end — which is above the footer, so
it is visible. Except that the footer is `sticky bottom-0` **inside the same flex column**: a sticky
element inside a column whose siblings scroll does not reserve space, and with `max-h-dvh` plus the
iOS/Android URL bar changing `dvh`, the body's height is recomputed while the footer stays pinned;
24 px is simply less than the footer's height, so a control that ends exactly at the scroll end sits
under it.

So the fix is not "more padding by eye": the footer must publish its height and the body must reserve
`calc(var(--sheet-footer) + env(safe-area-inset-bottom))`. That is exactly what 059's T003 said to do
("a sticky footer that reports its height through a CSS variable") and what shipped as a constant.

## R2 — Why the title prints one letter per line

`CardDialog`'s header is `flex flex-wrap items-center gap-2` with a `min-w-0 flex-1` first child
holding the `<h2>` and the chip list. The action buttons are `h-11 w-11` (arrows, close) and
`min-h-tap px-3` (CSV, PNG) with default `flex-shrink: 1`, but their *content* — an icon plus a
two-word label — sets a min-content width they cannot go below. At 360 px:

```text
available 360 − 32 (px-4) − 32 (five gaps of 8) = 296 px
actions: 44 + 44 + ~100 + ~84 + 44 = 316 px
```

The actions alone exceed the row. `flex-wrap` then moves them to a second line, but the `<h2>` in a
`min-w-0 flex-1` box keeps only what is left of the *first* line, and `[overflow-wrap:anywhere]`
turns that sliver into one character per line. 059's sweep looked for `writing-mode` and rotated text,
which this is not.

The fix is a two-row grid — title + actions on row one with the title `min-w-0 flex-1 truncate` and
the actions `shrink-0`, chips on row two — plus icons-only buttons under 480 px so the actions fit in
44 × 3 + a CSV/PNG icon pair.

## R3 — What a maximized card can be titled from

`maximizedTitle()` today:

```ts
const component = (def.layout?.web?.components ?? []).find((e) => e.id === id);
return (component ? localized(component, "title") : undefined) ?? t.layout.maximize(id);
```

`t.layout.maximize(id)` is the *button's* label (`Ampliar «{id}»`) reused as a title. The data to do
better is in the same object the dashboard already renders from:

- `component.title` — a layout component may carry its own localised title;
- `component.view` → `data.views[]` → `view.title` — a view always has one;
- for `type: "kpi"`, `component.metric` → `def.metrics[]` → `label` (a metric may be declared inline
  in the view, so both places are searched);
- for `type: "text"`, the first words of the text, which is what the card shows;
- last resort: the report's own title.

The id is a developer's handle and never appears in a reader's header. The button keeps
`Ampliar «{label}»` as its accessible name, which is where the verb belongs.

## R4 — Measuring a chart without `window`

`PieChart` hard-codes `const SIZE = 240` for the card and uses `window.innerHeight * 0.6` when
maximized. Two consequences: a card narrower than 240 px overflows (and `Card` clips it, so the ring
disappears — "no ring at all"), and a maximized ring ignores the dialog's actual width, so on a phone
it is 468 px wide inside 328 px and is clipped into nothing visible.

`ChartCard` already measures its own box with `useChartWidth`/`useChartHeight` and passes both to
`children`. The pie must use the width it is given, and only the *maximized* case needs the second
measurement — which it gets because `ChartCard`'s measured div is inside the dialog body. So: no new
hook, use the argument. `min(240, width − 32)` in a card, `min(width − 32, 0.6 × height, 520)` when
maximized, with `height` = the measured height of that same box (which is `60vh`-ish inside the
dialog because the body is `flex-1`).

## R5 — The action bar must be static, and the reason it was sticky

Before 059 the shell had no bottom tab bar on phones, and a long form needed its save button within
reach; `sticky bottom-20` (80 px = the tab bar's height) was the answer. With 44 px fields and a
card-per-section layout, an 80 px floating bar covers a third of the visible form area, and it is
translucent (`bg-surface/95 backdrop-blur`), so the fields under it look broken rather than hidden.

The owner's decision reverses it: the actions scroll with the form. `pb-safe` (a utility this repo
already has) keeps them 16 px above the tab bar, and the same treatment is applied to the other admin
forms that copied the pattern — `UserForm`, the integration settings and appearance — because a grep
gate (`sticky bottom-20`) is the only way they stay fixed.

## R6 — Why the earlier tests missed all of this

- 059's sign-in test asserted "both providers are in one row with the short labels" — the very
  behaviour the owner now rejects. The test was not wrong; the decision changed.
- 059's sheet test asserted `h-dvh` and a sticky footer by class name, never that the last control
  clears the footer.
- 056b's dialog test asserted that a title was present, not that it was the reader's title, and never
  measured its width.
- The pie had no test at all at a phone width.

So 062's tests assert **measurements and reader-facing text**: computed heights, `scrollHeight`, an
`svg` width in px, the header's `<h2>` width as a fraction of the header. A class-name assertion would
have passed on every one of the five defects.

## R7 — 44 px is a pixel token in this app, not a rem length

`h-11` is `2.75rem`. The app's root font-size is 15 px on phones (`frontend/src/index.css`, chosen so
the type scale matches the reference app while keeping the user's browser setting in percentages), so
`h-11` measured **41 px** in the browser — under the 44 px minimum the product promises, and 3 px short
of what 056b believed it had shipped on every dialog action. `tailwind.config.js` already carries the
right token: `minHeight.tap: "44px"` / `minWidth.tap: "44px"`. Feature 062 moved every dialog action to
`min-h-tap`/`min-w-tap` and the Google button to `min-h-[48px]` (the owner asked for 48, in px).

The general rule this leaves behind: a size that a finger has to hit is expressed in px, because it
must not scale with a root font-size that changes at 640 px.

## R8 — Why the "title ≥ 60 % of the header" target could not be met literally

At 360 px the dialog header is 328 px wide (`px-4`). Three actions (previous, next, close) at the tap
token are 132 px, plus the PNG/CSV icons-only buttons at 44 px each and 4 px gaps: with a KPI (arrows,
PNG, close) the actions take ~140 px, leaving 188 px — 57 %. With CSV as well it is worse. Making the
title 60 % would need 44 px targets of 30 px, which is the defect this feature is fixing.

So the requirement was implemented as its measurable intent — the title keeps more than half the header,
stays on one line, and never stacks — and the arithmetic is recorded here and in the contract rather
than left as a passing assertion that cannot hold.
