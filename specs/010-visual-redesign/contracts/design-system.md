# Design contract: Customer A look (feature 010)

All colours go through the feature-006 tokens (`src/index.css`, `tailwind.config.js`); the guard
test forbids raw palette classes and hex literals in `src/`. Ubuntu stays (feature 009).

## Brand scale (replaces the blue `--brand-*` values in `:root`)

| Step | Hex | RGB triplet | White text | Use |
|---|---|---|---|---|
| 50 | #f1f7fa | 241 247 250 | — | tinted icon squares (light), hover rows |
| 100 | #dfedf4 | 223 237 244 | — | accent-soft, chips background |
| 200 | #c2dce9 | 194 220 233 | — | accent-line |
| 300 | #98c3d8 | 152 195 216 | — | dark-theme gradient highlight |
| 400 | #6aa6c3 | 106 166 195 | 2.67 (no) | dark-theme accent text (7.0:1 on #0b1220) |
| 500 | #4b8bab | 75 139 171 | 3.76 (large/bold ≥ 19 px only) | decorative, chart series 1 (dark) |
| 600 | #3a7393 | 58 115 147 | 5.18 | primary, accent text (light), active pill start, gradients start |
| 700 | #305e78 | 48 94 120 | 7.00 | primary-hover, active pill end |
| 800 | #2b4f63 | 43 79 99 | 8.75 | gradients end |
| 900 | #284354 | 40 67 84 | 10.39 | — |
| 950 | #172b37 | 23 43 55 | 14.61 | — |

Gradients carrying text: `--grad-from: var(--brand-600)`, `--grad-to: var(--brand-800)` (light and
dark). A non-text decorative highlight (radial, white at ≤ 15 % alpha) may sit on top.

## New / changed tokens

- `--c-canvas` light `244 247 250` (#f4f7fa); dark unchanged from 006.
- `--c-field` (filled input background): light `233 239 244` (#e9eff4); dark `30 41 59`.
- `--c-field-focus` ring: `--brand-600` light / `--brand-400` dark.
- `--c-accent` light → `--brand-600`; dark → `--brand-400`.
- `--c-accent-soft` light → `--brand-50`; dark → brand-900 at 40 % (as today's mechanism).
- `--c-line-accent`: light `--brand-200`, dark `--brand-700` — border of emphasised cards.
- `--radius-card` 1.25 rem; tiles/inputs 0.875 rem.
- Chart: `--c-chart-1` → brand-600 (light) / brand-400 (dark); `--c-chart-2` → brand-300 (light) /
  brand-600 (dark).

## Components (new or restyled, `src/components/`)

| Component | Contract |
|---|---|
| `AppShell` | ≥ lg: fixed full-height sidebar `w-64` `bg-surface` `border-r border-line`; top block `h-[5.5rem]` gradient (`--grad-from`→`--grad-to`) with `Logo` on a `bg-white/15` rounded tile + product name (white, bold) + organisation (white/80, text-sm — on 600+ only); nav items `min-h-tap rounded-xl px-4` icon `h-5 w-5` + label `font-medium text-ink-2`; active `bg-gradient-to-r from-primary to-primary-hover text-on-primary shadow-card`. Top bar `h-16 bg-surface border-b border-line` over content only, right side: theme switcher button + account menu. Content `bg-canvas`. < lg: top bar keeps a compact gradient strip with logo; bottom nav unchanged. |
| `PageHeader` | white card (`rounded-[var(--radius-card)] border border-line-accent bg-surface p-6 sm:p-8`), `h1` `text-3xl sm:text-4xl font-bold tracking-tight text-ink`, subtitle `text-ink-muted`, optional right slot (badge/actions). |
| `Breadcrumbs` (new) | row: outlined "← Volver" button (`BackLink` restyled) + trail `text-sm text-ink-muted`, last item `text-accent font-medium`, separators `ChevronRight h-3.5`. |
| `Card` | `rounded-[var(--radius-card)] border bg-surface`; `tone="plain"` → `border-line`, `tone="accent"` → `border-line-accent`. |
| `StatTile` (new) | card plain, `p-5`; icon on `h-10 w-10 rounded-xl bg-accent-soft text-accent`; label `text-xs font-medium text-ink-muted`; value `text-3xl font-bold text-ink`; optional footnote `text-xs text-ink-muted`; optional delta (arrow + sign + text, success/danger tokens). |
| `HubCard` (new) | link card plain `p-6 hover:border-line-accent hover:shadow-raised`; icon tile as StatTile; title `font-semibold text-ink`; description `text-sm text-ink-muted line-clamp-2`. |
| `WelcomeBanner` (new) | `rounded-3xl` gradient `p-8 sm:p-10 text-on-primary`; chip `rounded-full bg-white/15 px-3 py-1 text-xs font-semibold tracking-wide`; title `text-3xl sm:text-5xl font-bold tracking-tight`; subtitle `text-white/85` (only on 600+); date via `Intl.DateTimeFormat("es", {dateStyle:"full"})`. |
| `Input`/`Select`/`PasswordField` | `min-h-[3.25rem] rounded-xl bg-field border-transparent px-4`; focus `ring-2 ring-field-focus`; error keeps danger border + text; labels `text-sm font-semibold text-ink-2`; required mark `text-danger` "*". |
| `Button` | primary `bg-primary hover:bg-primary-hover text-on-primary rounded-xl`; secondary `bg-surface border border-line text-ink-2 hover:bg-subtle`; danger unchanged. |
| `Badge`/status pill | `rounded-full px-2.5 py-0.5 text-xs font-semibold` soft tones: success `bg-success-soft text-success`, neutral, accent `bg-accent-soft text-accent border border-accent-line`. |
| `CodeChip` (new) | `rounded-lg border border-line bg-subtle px-2 py-0.5 font-mono text-xs font-semibold text-ink-2`. |
| `DataTable`/admin tables | header row `bg-subtle text-xs font-semibold text-ink-muted`; rows `divide-y divide-line`; name cell bold + muted second line; actions `IconButton` (44 px target). On < sm, rows become stacked cards (existing pattern). |
| `ViewHost` views (009) | header uses `PageHeader` style with the back button inside. |

## Screens

- Home: `WelcomeBanner` (first name = first word of `user.full_name`) → dashboards as `HubCard` grid
  `sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4`.
- AdminHome: `PageHeader` "Administración" → `StatTile` row (users, sources, integrations counts
  from existing endpoints only) → sections as `HubCard` grid.
- Lists (Users, Audit, Sources, Integrations, Tokens): `PageHeader` with count badge → toolbar card
  (search filled input, filter selects, primary action right) → table card.
- Forms/details (UserForm, UserDetail, SourceForm, Profile, Security, AI, Workspace): `Breadcrumbs`
  → `PageHeader` → section cards (`tone="accent"` for the main one).
- ReportView: `Breadcrumbs` → `PageHeader` → filters toolbar → KPIs as `StatTile` → charts/tables in
  plain cards.
- SignIn/ChangePassword: hero panel uses the gradient; inputs filled; layout unchanged.
