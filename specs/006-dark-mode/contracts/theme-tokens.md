# UI contract: theme tokens and switcher

Tokens are CSS variables holding RGB triplets (`--c-ink: 15 23 42`) so Tailwind alpha works
(`bg-surface/95`). Declared in `frontend/src/index.css`: light on `:root`, dark on
`:root[data-theme="dark"]`. Exposed in `tailwind.config.js` under `theme.extend.colors`
(`TOKENS` list). Every light value equals the class it replaced, so the light theme is unchanged
(verified by screenshot comparison, quickstart 16). Tones of a hue follow one pattern:
`-bright` (600), base (700), `-strong` (800), `-deep` (900), `-soft` (50), `-line` (200); dark
values mirror the scale (600→400, 700→300, 800→200, 900→100, 50→950, 200→800).

## Colour tokens

| Token | Replaced | Light | Dark |
|---|---|---|---|
| `canvas` | page `bg-slate-50` (`min-h-screen`, body) | slate-50 | slate-950 |
| `surface` | `bg-white` | white | slate-900 |
| `subtle` | inset/hover `bg-slate-50` | slate-50 | slate-800 |
| `surface-2` | `bg-slate-100` | slate-100 | slate-800 |
| `fill` | `bg-slate-200` (skeletons) | slate-200 | slate-700 |
| `line-soft` / `line` / `line-strong` | slate-100 / 200 / 300 borders, rings, dividers; `bg-slate-300` | slate-100 / 200 / 300 | slate-800 / 700 / 500 |
| `ink` / `ink-2` / `ink-3` | `text-slate-900` / 800 / 700 | slate-900 / 800 / 700 | slate-50 / 100 / 200 |
| `ink-muted` / `ink-soft` / `ink-faint` | `text-slate-600` / 500 / 400 | slate-600 / 500 / 400 | slate-300 / 400 / 500 |
| `accent-bright` / `accent` / `accent-strong` / `accent-deep` | `text-brand-600` … 900 | brand-600 … 900 | brand-400 / 300 / 200 / 100 |
| `accent-soft` / `accent-soft-2` | `bg-brand-50` / 100 | brand-50 / 100 | brand-950 / 900 |
| `accent-line` / `accent-line-strong` | brand-200 / 400 rings and borders | brand-200 / 400 | brand-800 / 500 |
| `primary` / `primary-hover` / `primary-active` | `bg-brand-600` / 700 / 800 fills, brand-600 selected borders | brand-600 / 700 / 800 | same |
| `focus` | brand-500 focus rings/borders, `:focus-visible` | brand-500 | same |
| `danger-bright` / `danger` / `danger-strong` / `danger-deep` | `text-rose-600` … 900 | rose-600 … 900 | rose-400 / 300 / 200 / 100 |
| `danger-soft` / `danger-line` | `bg-rose-50`, `ring-rose-200` | rose-50 / 200 | rose-950 / 800 |
| `danger-border` / `danger-focus` | input error `border-rose-400` / `focus:border-rose-500` | rose-400 / 500 | rose-500 / 400 |
| `danger-solid` / `-hover` / `-active` | `bg-rose-600` / 700 / 800 (danger button) | rose-600 / 700 / 800 | same |
| `success-bright` / `success` / `success-strong` / `success-deep` / `success-soft` / `success-line` | emerald 600 / 700 / 800 / 900 / 50 / 200 | same steps | emerald 400 / 300 / 200 / 100 / 950 / 800 |
| `warning` / `warning-strong` / `warning-deep` / `warning-soft` / `warning-line` | amber 700 / 800 / 900 / 50 / 200 | same steps | amber 300 / 200 / 100 / 950 / 800 |
| `backdrop` | modal `bg-slate-900/50` | slate-900 | slate-950 |
| `toast` | toast `bg-slate-900` | slate-900 | slate-700 |
| `ring-ink/5`, `ring-ink/10` | `ring-slate-900/5`, `/10` (card edges) | slate-900 | slate-50 (a faint light edge) |
| `chart-1` / `chart-2` / `chart-grid` / `chart-axis` / `chart-label` | TrendChart hex colours | brand-700 / slate-500 / 200 / 400 / 600 | brand-400 / slate-400 / 700 / 500 / 400 |

Disabled solid buttons use `disabled:bg-primary/50` and `disabled:bg-danger-solid/50`.

Fixed in both themes (allowed raw utilities, listed in the guard test with reasons): the hero
gradient and its content (`text-white`, `bg-white/15`, `ring-white/30`, `hover:bg-white/10`,
`text-brand-50`, `text-brand-100`) — the logo only appears there; `text-white` on solid fills and
the toast; the switch knob `bg-white`; toast icons `text-emerald-400` / `text-amber-300`.

Other variables: `--shadow-card`, `--shadow-raised` (dark: a 1 px `line` ring + deeper shadow),
`--hero-color` (browser bar colour per theme).

## Guard rule (enforced by `frontend/tests/unit/no-raw-colors.test.ts`)

Source files under `frontend/src` MUST NOT use raw palette utilities or hex/rgb colour literals
outside the allow-list above (plus the two hero hex values in `theme/resolve.ts`, which must match
`public/theme-init.js`). The test prints each offending `file:line`. A second test checks that
every token defined for light also has a dark value (except the fixed ones).

## Document-level contract

- `<html data-theme="light|dark">` is always set before first paint (by `/theme-init.js`).
- `:root { color-scheme: light }`, `:root[data-theme=dark] { color-scheme: dark }` (native form
  controls, scrollbars, date pickers follow).
- `<meta name="color-scheme" content="light dark">`; `<meta name="theme-color">` is updated to
  the hero colour of the active theme.
- `<body class="bg-canvas text-ink">`.

## Theme switcher (`components/ThemeSwitcher.tsx`)

- `role="radiogroup"`, `aria-label="Tema"`; three `role="radio"` buttons with icon + text:
  "Sistema" (Monitor), "Claro" (Sun), "Oscuro" (Moon); `aria-checked` on the active one; arrow
  keys move focus and selection (roving tabindex); each target ≥ 44 × 44 px.
- Inside the account menu (`inMenu`), a `role="group"` of `role="menuitemradio"` items instead,
  since a menu may only contain menu items.
- Used in: Profile → card "Apariencia"; account menu in the app-shell header.
- On save failure: warning toast (new `tone` argument of `useToast`) `"Tema aplicado en este dispositivo, pero no se pudo guardar en tu
  cuenta."` (FR-013). All texts live in `src/i18n/es.ts` under `theme`.

## Hook (`theme/ThemeContext.tsx`)

```ts
type ThemePreference = "system" | "light" | "dark";
useTheme(): { preference: ThemePreference; resolved: "light" | "dark";
              setPreference(p: ThemePreference): Promise<void> }
```
