/** The app's layout rules in one place (features 030 and 050).
 *
 * A page composes these; it never answers a shared question locally. Three of the four defects 050
 * corrected were one page answering "how wide am I?" or "how does a choice look?" on its own, so the
 * vocabulary lives here and `docs/DESIGN-SYSTEM.md` says why. */

/** The app's content container (feature 030 FR-001): one definition shared by the authenticated
 * shell and the public pages, so the report page and the shared view span the same width as
 * Tableros and Administración instead of a narrower centred column. */
export const APP_CONTAINER = "mx-auto w-full max-w-screen-2xl";

/** Phone-first gutters: 16 px at 375 px, the reference app's 20 px from 640 px, 16 px on desktop. */
export const APP_GUTTER = "px-4 sm:px-5 lg:px-4";

/** What a page root uses. A page adds `PAGE_STACK`, never a `max-w-*` of its own (050 FR-001). */
export const APP_PAGE = `${APP_CONTAINER} ${APP_GUTTER}`;

/** Vertical rhythm between the sections of a page. */
export const PAGE_STACK = "space-y-4 sm:space-y-5";

/** One padding for the content of a card or panel. */
export const CARD_PAD = "p-4 sm:p-5";

/** A split pane's bound: `max-height`, never a fixed height, so a short viewport scrolls inside the
 * panel instead of clipping it. `--app-chrome` is the header + page title above the panes; a page
 * whose chrome is taller sets it. */
export const PANEL_MAX_H = "lg:max-h-[calc(100dvh-var(--app-chrome,15rem))] lg:overflow-hidden";

/** What actually makes a grid child scroll instead of stretching the page: `min-h-0` plus `auto`. */
export const PANEL_SCROLL = "min-h-0 overflow-y-auto";

/** Navigation pane + reading pane. The second column is `minmax(0,1fr)` so a long word wraps
 * instead of widening the grid; the row is `minmax(0,1fr)` and the container clips, which is what
 * makes a pane scroll *inside* a `max-height` instead of growing past it (measured in a browser:
 * without the row rule the pane overflowed its container and never scrolled). */
export const SPLIT_COLS =
  "lg:grid lg:grid-cols-[minmax(18rem,24rem)_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)] lg:gap-6";

/** Reading pane + an aside on the right (052: the structure, then its chat). The content keeps the
 * wide column, because it is the part that has to be readable. */
export const SPLIT_ASIDE =
  "lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(20rem,26rem)] lg:items-start lg:gap-6";

/** Card grids: one column on a phone, more only where the content is comfortable (050 FR-004). */
export const CARD_GRID_2 = "grid grid-cols-1 gap-4 sm:grid-cols-2";
export const CARD_GRID_3 = "grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3";
