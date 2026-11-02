# The BizView design system

One place for the rules every screen follows. It exists because four screens did not: the theme
library sat in a 56 rem column on a 96 rem screen, the appearance choices stacked because a class
list had lost `grid`, and Ayuda had no bounded panel, so the page scrolled instead of the article.

The rules live in code as tokens (`frontend/src/lib/layout.ts`) and in prose here. A page composes
them; it does not answer a shared question locally.

**Mobile first.** Base styles are the phone's. Enhancements come from `min-width` variants
(`sm:`, `md:`, `lg:`, `xl:`) only — never a desktop layout squeezed down.

## Tokens

| Token | Value | What it decides |
|---|---|---|
| `APP_CONTAINER` | `mx-auto w-full max-w-screen-2xl` | the one content width (96 rem) |
| `APP_GUTTER` | `px-4 sm:px-5 lg:px-4` | 16 → 20 → 16 px of side padding |
| `APP_PAGE` | container + gutter | a page root uses this and nothing else |
| `PAGE_STACK` | `space-y-4 sm:space-y-5` | rhythm between a page's sections |
| `CARD_PAD` | `p-4 sm:p-5` | a card's inner padding |
| `PANEL_MAX_H` | `lg:max-h-[calc(100dvh-var(--app-chrome,15rem))]` | a split pane's bound — a `max-height`, never a fixed height |
| `PANEL_SCROLL` | `min-h-0 overflow-y-auto` | what makes a grid child scroll instead of stretching the page |
| `SPLIT_COLS` | `lg:grid lg:grid-cols-[minmax(18rem,24rem)_minmax(0,1fr)] lg:gap-6` | navigation + reading pane |
| `CARD_GRID_2` / `CARD_GRID_3` | 1 column → 2 → 3 | the only column progressions in the product |

Colours are theme tokens (`text-ink`, `bg-surface`, `border-line`, `ring-focus`, `text-accent`, …),
never literals: `tests/unit/no-raw-colors.test.ts` fails a screen that hard-codes one, and an
imported theme (047) must keep working.

## The rules

### A page
- Root class: `APP_PAGE` plus `PAGE_STACK`. **No `max-w-*` of its own** — a narrow column inside the
  container is the defect this document exists for.
- One `<h1>`; sections `<h2>`, sub-sections `<h3>`, in order.
- No horizontal overflow at 320 px; aligned to the same container at 1920 px.

### A card
- `Card` + `CARD_PAD`. Contents stacked; equal heights come from the grid (`h-full`), not from
  padding. No filler to make a row match.

### A page header
- `PageHeader`: one `<h1>` (compact), an optional one-line subtitle, actions in one wrapping row —
  beside the title from `sm`, below it on a phone. It must not eat a fifth of a 375 × 740 viewport.

### A choice (segmented control)
- `SegmentedControl`. Its container is **always** a grid with `grid-cols-N`; options are siblings.
- `radiogroup` + `radio` outside a menu, `group` + `menuitemradio` inside one.
- Exactly one `aria-checked`; one tab stop; arrows move and select.
- At 320 px the options still share the row: shrink, never wrap the page.

### A split pane (Ayuda)
- Parent: `SPLIT_COLS` + `PANEL_MAX_H`. Children: `PANEL_SCROLL`.
- Below `lg`: one column, list first, an explicit Back (`aria-label` names the destination).
- Preserve search and scroll position across the trip.

### Feedback
- Loading: `Spinner` with an `sr-only` label. Empty: `EmptyState`. Error: `Alert tone="error"` with a
  retry where the retry is meaningful. Disabled: the shared `disabled:` styles, never a bare `opacity`.

## Viewports we design for and test

| Width | What it is | What must hold |
|---|---|---|
| 320 px | narrowest supported | no horizontal overflow, controls share their row |
| 375 px | reference phone | one column, bottom bar never covers content |
| 768 px | tablet | two columns where the content allows |
| 1024 px | laptop | the split panes appear |
| 1440 px | desktop | three columns; the container is used |
| 1920 px | wide | the container is centred, not stretched |

200 % browser zoom is a width of half the window: everything above must hold at that effective size.

## Guards

`frontend/tests/unit/design-guards.test.ts` reads the source and asserts properties, not screenshots:

- no page root declares a narrow `max-w-*`;
- the theme and language switches contain no `grid-cols-*` of their own (they delegate);
- the segmented control always renders a grid;
- Ayuda uses the bounded split tokens;
- the token module exports the vocabulary and is phone-first.

`tests/unit/no-raw-colors.test.ts` (006) keeps colours on tokens.

A screenshot diff would fail on a font upgrade and pass on a structural regression; a property
check does the opposite, which is why the guards are written this way.
