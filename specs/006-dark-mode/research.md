# Research: Dark mode

**Feature**: [spec.md](./spec.md) · **Date**: 2026-09-30

Starting point (surveyed 2026-09-30): the frontend has ~660 Tailwind colour utilities across
pages and components (top: `text-slate-600` 54, `text-slate-900` 49, `text-brand-700` 38,
`bg-white` 21, `bg-brand-50` 17, `text-rose-700` 14); the only hard-coded colours are in
`src/index.css` (brand scale) and `components/report/TrendChart.tsx` (SVG hex strokes/fills).
`index.html` pins `<meta name="color-scheme" content="light">` and a fixed `theme-color`. Caddy
serves `script-src 'self'` (no inline scripts). No chart library: the trend chart is inline SVG.

## R1. How the dark theme is expressed in CSS

- **Decision**: **semantic colour tokens** backed by CSS variables (RGB triplets), declared for
  light on `:root` and for dark on `:root[data-theme="dark"]`, exposed to Tailwind as colour
  names (`bg-canvas`, `bg-surface`, `text-ink`, `text-ink-muted`, `border-line`, `text-accent`,
  `bg-primary`, `bg-danger-soft`, …; full list in [contracts/theme-tokens.md](./contracts/theme-tokens.md)).
  Existing palette classes are migrated to tokens with a mapping table (a one-off codemod script
  plus manual review of the ~30 ambiguous uses). Each light value equals the class it replaced (one
  token per used step, no collapsing), so the light theme is pixel-identical.
- **Rationale**: one class per use (no `dark:` twin to forget); a guard test can forbid raw
  palette classes so every future screen is dark-safe by construction (keeps SC-001 true over
  time); the chart, focus ring and shadows read the same variables.
- **Alternatives considered**:
  - Tailwind `dark:` variants on every element: ~660 extra classes, easy to miss one, no way to
    enforce except visual review.
  - Remapping the existing `slate`/`brand` scales per theme (so `text-slate-900` becomes light in
    dark): fewest edits, but steps are dual-use (`brand-700` is both link text and button hover
    background, `slate-900` both text and toast background) so no single dark value works, and
    `text-slate-900` rendering near-white misleads every future developer.

## R2. Theme attribute, "Sistema", and no flash on load (FR-005, FR-006, FR-007)

- **Decision**: the resolved theme (`light` | `dark`) lives in `data-theme` on `<html>`, together
  with the CSS `color-scheme` property and the `theme-color` meta. A tiny classic script
  `frontend/public/theme-init.js`, loaded **synchronously in `<head>` before the stylesheet**,
  reads the device cache (`localStorage["bizview.theme"]`, default `system`), resolves `system`
  with `matchMedia("(prefers-color-scheme: dark)")`, and sets the attribute before first paint.
  In the app, a `ThemeProvider` owns the preference, listens to the media query while the
  preference is `system`, and on `/api/me` load adopts the account value (server wins) and
  refreshes the device cache. Signing out keeps the cache (FR-007 "last theme chosen on that
  device").
- **Rationale**: the CSP forbids inline scripts, so the pre-paint code must be a same-origin
  file; a blocking ~0.5 KB script costs one cached request and is the only way to avoid a flash
  on a slow phone. `localStorage` holds only `system|light|dark` (not personal data).
- **Alternatives considered**: inline script with a CSP hash (couples the Caddyfile to a build
  artefact hash); cookie read by the backend (the API never renders HTML); relying on CSS
  `@media (prefers-color-scheme)` alone (cannot express an explicit "Claro"/"Oscuro" choice).
- Browsers without `matchMedia` or without storage (private mode throws): treated as `light` /
  `system` respectively, inside try/catch (spec edge case).

## R3. Where the preference is stored (FR-004)

- **Decision**: new column `app_user.theme text NOT NULL DEFAULT 'system'` with a CHECK
  (`system|light|dark`), Alembic migration `0005_user_theme`. Returned in `user_json` (so
  `GET /api/me` and auth responses carry it) and changed with `PATCH /api/me/preferences`.
- **Rationale**: one small, typed attribute of the user; a JSON "preferences" column is not
  justified for a single value (can be revisited when a second preference appears). The route is
  named `preferences` so a later preference does not need a new endpoint.
- **Alternatives considered**: separate `user_preference` key/value table (joins for one enum);
  device-only storage (fails FR-004).
- Not audited: a display preference is not a security event (the audit log records security and
  administration events only). Allowed for sessions with a temporary password
  (`auth_allow_temporary`) so the password-change screen can also switch theme.

## R4. Palette and contrast (FR-009, SC-001)

- **Decision**: dark values from the Tailwind slate/blue/rose/emerald/amber scales, verified with
  the WCAG 2.1 formula (script run 2026-09-30):

  | Pair (dark) | Ratio | Need |
  |---|---|---|
  | ink `slate-50` / surface `slate-900` | 17.06 | 4.5 |
  | ink-muted `slate-400` / surface-2 `slate-800` (worst text case) | 5.71 | 4.5 |
  | accent `blue-300` / accent-soft `blue-950` | 8.15 | 4.5 |
  | white / primary `blue-600` (unchanged) | 5.17 | 4.5 |
  | danger `rose-300` / danger-soft `rose-950` | 8.27 | 4.5 |
  | success `emerald-300` / `emerald-950` | 9.94 | 4.5 |
  | warning `amber-200` / `amber-950` | 12.03 | 4.5 |
  | focus ring `blue-500` / surface | 4.85 | 3 |
  | chart series `blue-400` / surface; previous `slate-400` / surface | 7.02; 6.96 | 3 |
  | input border `slate-500` / surface | 3.75 | 3 |

- `ink-faint` (`slate-500` in dark, 3.75:1) is for decorative icons and disabled text only; the
  guard test forbids it on body text. Solid fills (primary, danger buttons) keep the same colour
  in both themes: white text stays ≥ 4.5:1 and hover darkens (`blue-700`).
- Elevation in dark: shadows are nearly invisible on dark surfaces, so the `card` and `raised`
  shadows become a 1 px `line` ring + darker shadow via the `--shadow-*` variables.
- Verification: axe-core (`color-contrast` rule, already in the e2e suites) run on every screen in
  both themes (SC-001).

## R5. Branding in dark mode (FR-011)

- **Decision**: the logo is only ever shown on the deep-blue `bg-hero` surface (app-shell header,
  sign-in, change-password header), which stays the same in both themes, so a customer logo keeps
  the background it was chosen for. Brand-coloured text and fills use the accent/primary tokens,
  whose dark values are lighter steps of the same brand scale (`--brand-300`/`--brand-400`), so a
  deployment that changes the brand scale gets a matching dark accent automatically.
- **Alternatives considered**: a second "logo for dark" setting (spec: no extra customer
  configuration); CSS `filter: invert()` on logos (breaks colour logos).

## R6. Charts (FR-010)

- **Decision**: `TrendChart` strokes and fills read CSS variables (`--chart-1`, `--chart-2`,
  `--chart-grid`, `--chart-axis`, `--chart-label`) through `rgb(var(--x))` in SVG presentation
  attributes; the previous-period series stays dashed and the tooltip names both series, so the
  colour is never the only cue. Positive/negative deltas keep their arrow icon + sign.
- **Rationale**: SVG `fill`/`stroke` accept CSS variables in all target browsers (Safari ≥ 14),
  so the chart re-themes without re-rendering.

## R7. Theme switcher placement (FR-002)

- **Decision**: (a) a three-option segmented control "Sistema / Claro / Oscuro" (radio group,
  44 px targets) in a new "Apariencia" card on the Profile screen; (b) the same control inside the
  account menu of the app shell header (menu open = tap 1, option = tap 2). The sign-in screen
  gets no control (it follows the device / last choice, FR-007).
- **Rationale**: meets "≤ 2 taps from any screen" (SC-002) without adding a header icon on a
  375 px header that already holds logo, name and account button.

## R8. PDF exports (FR-012)

- **Decision**: no change. PDFs are rendered by the backend (ReportLab) from JSON payloads and
  never see the client theme; the plan adds only a regression check in quickstart. html2canvas is
  not used by the current report renderer.

## R9. Transition and reduced motion

- **Decision**: no animated colour transition on theme change (instant swap); the global
  `prefers-reduced-motion` rule already neutralises component transitions.

## Supporting libraries

None added. Everything uses React, Tailwind, and browser APIs already in the stack.
