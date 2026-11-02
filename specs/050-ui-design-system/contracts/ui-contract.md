# UI contract — what a screen must satisfy

Written so a reviewer can check a page without reading this feature's code.

## A page

1. Its root uses `APP_PAGE` (container + gutter). It declares **no** `max-w-*` of its own.
2. Its sections are separated by `PAGE_STACK`, not by ad-hoc `space-y-*`.
3. At 320 px it does not scroll horizontally; at 1440 px it is aligned to the same container as
   every other page.
4. Its first heading is an `<h1>`; sections use `<h2>`, sub-sections `<h3>`, in order.

## A card

1. `rounded-card border bg-surface` (the `Card` component), padding `CARD_PAD`.
2. Contents stacked with one of the token spacings; no empty filler to make heights match — equal
   heights come from the grid, not from padding.
3. Text wraps; a translated label never truncates a primary action.

## A page header

1. One `<h1>`; optional one-line subtitle; actions in a single wrapping row on the right at `sm`
   and above, below the title on a phone.
2. Compact on a phone: it must not take more than about a fifth of a 375 × 740 viewport.

## A segmented control

1. Options are siblings inside a container that carries `grid` and a `grid-cols-N`.
2. `role="radiogroup"` with `radio` children, or `group` with `menuitemradio` inside a menu.
3. Exactly one `aria-checked="true"`; Arrow keys move and select; only one is tabbable.
4. Every option shows an icon and/or text at 320 px; nothing clips or wraps the page.

## A split pane

1. The two panes are grid children of a container bounded by `PANEL_MAX_H`.
2. Each scrollable pane carries `PANEL_SCROLL` (`min-h-0 overflow-y-auto`).
3. Below `lg` the split collapses to one column with an explicit way back.

## Colours and focus

1. Colours come from theme tokens (`text-ink`, `bg-surface`, `border-line`, `ring-focus`, …) — the
   `no-raw-colors` unit test enforces it.
2. Every interactive element has a visible `focus-visible` ring from the shared token.
