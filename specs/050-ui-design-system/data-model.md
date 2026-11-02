# Data model — tokens and the segmented control

## Layout tokens (`frontend/src/lib/layout.ts`)

| Token | Value | Rule it encodes |
|---|---|---|
| `APP_CONTAINER` | `mx-auto w-full max-w-screen-2xl` | one content width, 96 rem |
| `APP_GUTTER` | `px-4 sm:px-5 lg:px-4` | 16 → 20 → 16 px |
| `APP_PAGE` | container + gutter | what a page root uses; **never** a `max-w-*` of its own |
| `PAGE_STACK` | `space-y-4 sm:space-y-5` | vertical rhythm between page sections |
| `CARD_PAD` | `p-4 sm:p-5` | one padding for a card's content |
| `PANEL_MAX_H` | `lg:max-h-[calc(100dvh-var(--app-chrome,15rem))]` | a split pane's bound |
| `PANEL_SCROLL` | `min-h-0 overflow-y-auto` | what makes a pane scroll instead of the page |
| `SPLIT_COLS` | `lg:grid-cols-[minmax(18rem,24rem)_minmax(0,1fr)]` | navigation + reading pane |

Adding a token is cheap; a page-level exception is what needs justifying in review.

## SegmentedControl

| Prop | Type | Meaning |
|---|---|---|
| `options` | `{ value: string; label: string; icon?: ComponentType }[]` | the choices, in order |
| `value` | `string` | the single selected value |
| `onChange` | `(value: string) => void` | selection |
| `inMenu` | `boolean` | render `menuitemradio` inside a menu, `radio` otherwise |
| `label` | `string` | the group's accessible name |
| `columns` | `number` (default `options.length`) | the row count; the container is always a `grid` |

**Invariants**: exactly one option is `aria-checked`; only the checked option (or the first, when
none is) is tabbable; Arrow keys move and select; the container always carries `grid` and a
`grid-cols-N`; each button is at least 24 × 24 CSS px (44 px where it is the primary action).

**States**: unselected (muted ink), selected (surface + accent ink + ring), hover, focus-visible
(the shared focus ring), disabled (not used today).

## Panel (Help, and any split)

A panel is a grid child with `min-h-0` and `overflow-y-auto` inside a parent bounded by
`PANEL_MAX_H`. The bound is a `max-height` on purpose: content that does not fit scrolls inside the
panel, and a short viewport never clips.
