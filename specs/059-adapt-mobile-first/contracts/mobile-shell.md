# UI contract — the numbers a reviewer measures

Feature 059. Everything below is measured with `getBoundingClientRect()` / `window.innerHeight` in a
real browser; jsdom cannot lay out, so the unit tests assert classes and roles while Playwright
asserts geometry.

## Breakpoints

| Width | Sign-in | Sheet | Top bar |
|---|---|---|---|
| < 640 px | one screen, compact | full screen (`100dvh`), no handle | logo + organisation + theme + avatar, no breadcrumb < 480 |
| 640–1023 px | two columns (unchanged) | bottom sheet at 85 %, compact density | breadcrumb back |
| ≥ 1024 px | two columns (unchanged) | right side sheet 360 px | unchanged |

## Sign-in (`/ingresar`, < 640 px)

| Element | Value |
|---|---|
| Header logo | 40 × 40 px |
| Product name | 18 px, one line, `truncate` |
| Organisation | 12 px, one line, `truncate` |
| Language toggle | below the header, right-aligned, 44 px tall targets, must not intersect the header text |
| Tagline | 14 px, one line; hidden when the viewport is < 600 px tall |
| Card | full width minus 16 px gutters, no overlap with the header, `rounded-2xl` |
| Heading | 20 px; helper text 14 px |
| Inputs | 44 px high; email `autocomplete="email"`, password `current-password` |
| Password toggle | 44 × 44 px |
| Primary button | 48 px, full width |
| Providers | two buttons in one row (icon + short label) when both are enabled; one button full width otherwise |
| Messages | inline, under the card's heading, never pushing the form out of the viewport |

## Sheet (`/r/<id>`, < 640 px)

| Element | Value |
|---|---|
| Panel | `height: 100dvh`, `width: 100%`, no drag handle, `rounded-t-none` |
| Header | 56 px row: tab strip left (`role="tablist"`), `×` right, 44 × 44 px |
| Body | `overflow-y: auto`, `scroll-padding-bottom: 5rem`, footer padded by the safe-area inset |
| Footer | sticky, `Limpiar` (ghost) + `Listo` (primary), 44 px controls |
| Control label | one per control, 14 px, 6 px above the control |
| Control | 44 px high, 12 px between controls |
| Period + comparison | one row when each column ≥ 160 px; custom dates open in that row |
| Palette / theme | one-line chip rows, horizontal scroll, 44 px targets |
| Filters | search box when a filter has > 8 options; selected values as chips above the list |
| Behaviour | live apply 250 ms after the last change; `Listo` only closes; Back closes |

## Shell

| Element | Value |
|---|---|
| Top bar | logo, organisation, theme toggle, avatar; breadcrumb hidden < 480 px, **Volver** kept |
| Dashboard title | 22 px; description 14 px clamped to two lines; meta line wraps |
| Actions | icons with labels underneath < 420 px |
| Horizontal scrolling | none at 360 px on `/`, `/ingresar`, `/r/<id>`, `/proyectos` |

## Accessibility

- Sheet stays `role="region"` with `aria-labelledby`, focus trapped, Esc and Back closing, focus
  returned to the opener (the app's no-modals rule forbids `role="dialog"` here).
- Tabs are `role="tablist"` + `role="tab"` with arrow-key navigation.
- Every control has a programmatic label; icon-only buttons have `aria-label`.
- Axe (wcag2a, wcag2aa, wcag21aa, wcag22aa) reports no serious or critical violation on either screen,
  in both themes and both languages.
- `prefers-reduced-motion: reduce` removes the sheet's transform transition.
