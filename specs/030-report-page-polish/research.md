# Phase 0 — Research: Report page polish

Each decision below is grounded in the code that exists today (file:line) or in numbers computed for
this plan (palette contrast/ΔE). Nothing here reopens the spec's four owner decisions.

## R1 — Where the "too much margin" comes from

**Decision**: standardise the container in one place and delete the page-level `max-w-7xl`.

**Facts**: the shell already caps and centres the content —
[AppShell.tsx:291](../../frontend/src/components/AppShell.tsx:291) uses `mx-auto max-w-screen-2xl
sm:px-5 lg:px-4` for `<main>` (and drops the cap when the assistant is docked or the chrome hidden);
[ReportView.tsx:451](../../frontend/src/pages/ReportView.tsx:451) and
[ReportView.tsx:505](../../frontend/src/pages/ReportView.tsx:505) wrap the page in `mx-auto
max-w-7xl`. At 1920 px that is 1280 px of content inside a 1536 px container — exactly the wide
empty margins the owner reported. The public shared view is outside the shell and repeats
`max-w-7xl` in three places ([SharedDashboard.tsx:250](../../frontend/src/pages/SharedDashboard.tsx:250),
[:278](../../frontend/src/pages/SharedDashboard.tsx:278), [:287](../../frontend/src/pages/SharedDashboard.tsx:287)).

**Rationale**: the app standard already exists; the report page is the outlier. One constant plus a
thin `PageContainer` component gives FR-001's "one layout component" without touching Tableros or
Administración (they already inherit the shell's `<main>`).

**Alternatives considered**: (a) raise `max-w-7xl` to `max-w-screen-2xl` locally — leaves two
definitions that can drift again; (b) change the shell cap — would move every page, out of scope.

## R2 — Sheet primitive: hand-rolled, non-modal

**Decision**: a new `ReportSheet` component; no library, no `<dialog>`/modal, no portal.

**Facts**: there is no drawer/sheet/dialog primitive; `View.tsx` is the app's "full-page replacement
for modal dialogs" with portal, focus capture, focus restore, Escape and history integration
([View.tsx:1-20](../../frontend/src/components/View.tsx:1)). It replaces the page, which is the
opposite of what a non-blocking sheet needs (the numbers must stay visible). The phone flow today
opens `View` for filters ([ReportView.tsx:658](../../frontend/src/pages/ReportView.tsx:658)) and
shares the page for the shared view's filter card.

**Rationale**: constitution V — a headless dialog library would be a new supporting library for
behaviour we need in ~150 lines (positions ×2, tabs, focus trap, Esc, swipe). The keyboard/focus
patterns already exist in `CardMenu.tsx` (menu) and `ThemeSwitcher`/`LanguageSwitcher` (roving radio),
so no new idiom is introduced.

**Alternatives considered**: (a) Radix/Headless UI sheet — new dependency, new a11y contract to
learn, constitution-cost for little gain; (b) reuse `View` — it is a page replacement, so the
numbers disappear while filtering (spec US3 rejects that); (c) native `<dialog>` — modal by design,
needs `show()` juggling and still no non-modal side-sheet semantics across browsers.

**Focus model**: `aria-modal="false"`; entering the sheet moves focus inside, Tab cycles inside while
open, Esc closes and focus returns to the opener, a pointer click outside closes it on desktop. The
dashboard behind stays scrollable and clickable (non-modal), but the keyboard stays on the sheet until
it closes — the least surprising compromise for both pointer and keyboard users, and it satisfies
FR-003's "focus trap only while open".

## R3 — The `impacto` preset, with measured numbers

**Decision**: ship `impacto` as the default, with these exact values (verified against the gate of
FR-010 with a contrast/ΔE script run for this plan; CIE76 ΔE on Lab, WCAG 2.1 contrast).

Light (surface `#FFFFFF`, `kpi_text` `#0F172A` at 17.85:1):

| role | value | contrast vs surface |
|---|---|---|
| primary | `#0B63F6` | 5.09:1 |
| series1…8 | `#0B63F6` `#00897B` `#B45309` `#DB2777` `#7C3AED` `#15803D` `#C2410C` `#0E7490` | 5.09 · 4.23 · 5.02 · 4.60 · 5.70 · 5.02 · 5.18 · 5.36 |
| positive | `#15803D` | 5.02:1 |
| negative | `#B91C1C` | 6.47:1 |
| neutral | `#334155` | 10.4:1 |
| grid | `#E2E8F0` | 1.23:1 (subtle by design) |
| kpi_delta_bg.positive / .negative | `#DCFCE7` / `#FEE2E2` | text `#15803D` 4.57:1 · `#B91C1C` 5.30:1 |

Dark (surface `#0F172A`, `kpi_text` `#F8FAFC` at 17.06:1):

| role | value | contrast vs surface |
|---|---|---|
| primary | `#60A5FA` | 7.02:1 |
| series1…8 | `#60A5FA` `#2DD4BF` `#FBBF24` `#F472B6` `#A78BFA` `#4ADE80` `#FB923C` `#22D3EE` | 7.02 · 9.59 · 10.69 · 6.74 · 6.56 · 10.25 · 7.89 · 9.88 |
| positive | `#4ADE80` | 10.25:1 |
| negative | `#FB7185` | 6.63:1 |
| neutral | `#CBD5E1` | 9.85:1 |
| grid | `#1E293B` | 1.72:1 |
| kpi_delta_bg.positive / .negative | `#052E22` / `#450A0A` | text `#4ADE80` 8.48:1 · `#FB7185` 6.00:1 |

Adjacent-series ΔE is ≥45 in light and ≥45 in dark; `positive`/`negative` ΔE is ≥104 in both.

**Rationale**: the spec asks for "saturated primary, a distinct accent per secondary, bold numerals,
strong delta colours, subtle grid" in the spirit of the reference dashboard, and delegates the exact
hues to the plan against the palette check. Amber `#F59E0B` and teal `#00A99D` were the first
candidates and both fail 3:1 on white (2.15 and 2.93) — they were replaced by `#B45309` and
`#00897B`, which keep the hue family and pass.

**Alternatives considered**: copy the reference dashboard's hues — it has no light variant and its
pale accents fail 3:1, so it cannot pass the gate; use a generated 8-hue harmonic ramp — harder to
review and no better on the check.

## R4 — The other four presets

**Decision**: `clasico` (today's look), `monocromo` (brand shades, sequential), `contraste` (AA+,
≥7:1), `daltonico` (Okabe–Ito based). Verified values (all pass; failure modes are named because
they are the interesting part):

| preset | light series1…8 | dark series1…8 |
|---|---|---|
| `clasico` | `#3A7393` `#5098B8` `#7C3AED` `#0D9488` `#B45309` `#BE123C` `#4338CA` `#4D7C0F` | `#6AA6C3` `#98C3D8` `#A78BFA` `#2DD4BF` `#FBBF24` `#FB7185` `#818CF8` `#A3E635` |
| `monocromo` | `#12232C` `#1B3541` `#234655` `#2B5768` `#336A7E` `#3C7D93` `#4790A6` `#4E9CB1` | `#DDEAF1` `#C4D9E5` `#AAC7D9` `#90B5CD` `#76A3C1` `#5C91B5` `#427FA9` `#2B6D9D` |
| `contraste` | `#0B1220` `#1E3A8A` `#7F1D1D` `#14532D` `#7C2D12` `#4C1D95` `#134E4A` `#78350F` | `#F8FAFC` `#93C5FD` `#FCA5A5` `#86EFAC` `#FDE68A` `#C4B5FD` `#5EEAD4` `#FDBA74` |
| `daltonico` | `#0072B2` `#D55E00` `#009E73` `#CC79A7` `#4B2E83` `#8C6D00` `#1B7F79` `#8B4513` | `#56B4E9` `#E69F00` `#009E73` `#CC79A7` `#C7A9E8` `#F0E442` `#5FD3C4` `#F4A261` |

**Findings that shaped them**:

- **`clasico` cannot ship as-is.** Today's `chart-2` is `brand-300` `#98C3D8`
  ([index.css:96](../../frontend/src/index.css:96)), 1.89:1 on white — under the 3:1 floor. It
  becomes `#5098B8` (3.22:1), the same hue one step darker. This is the only visual change to the
  "today" preset and it is required by FR-010; it is called out for the owner in SC-007's
  side-by-side.
- **`monocromo` is a sequential preset by nature**: eight shades of one hue cannot reach adjacent
  ΔE ≥10 (the whole usable lightness range is ~40 L*). It declares `"strategy": "sequential"` and the
  check then requires monotonic lightness with ΔL* ≥5 steps (all pairs land at ΔE 4.6–5.4) instead of
  the categorical ΔE rule; contrast ≥3:1 still applies to every shade. Series legends stay visible
  for this preset.
- **`daltonico` starts from Okabe–Ito** and substitutes the two pale members (`#F0E442` yellow,
  `#56B4E9` sky) plus black in light mode (1.5 / 2.2 / 21:1) with darker members of the same hues;
  the dark variant keeps them because they pass there.
- `contraste` clears ≥7:1 for every series on both surfaces (measured 9.07–18.72 light,
  7.3–16.9 dark).

**Rationale**: the presets have to exist as product data before the picker can be built, and the
gate must pass before shipping, so the hues are chosen against the numbers rather than in CSS later.

## R5 — Where the palette lives and how it is applied

**Decision**: JSON product data per preset (`frontend/src/theme/palettes/*.json`), mirrored
byte-identically in `backend/app/reports/palettes/*.json`; the web resolves roles to CSS custom
properties at runtime, the PDF resolves the same roles to ReportLab colours.

**Facts**: every chart and KPI colour in the web renderer goes through semantic role classes
(`fill-chart-1…8`, `text-success-strong`, …) resolved by
[layoutRoles.ts:8-82](../../frontend/src/components/report/layoutRoles.ts:8), and those classes read
the CSS variables declared in [index.css](../../frontend/src/index.css) (light `:root` + dark
`:root[data-theme="dark"]`). The colour guard
([no-raw-colors.test.ts](../../frontend/tests/unit/no-raw-colors.test.ts)) forbids raw colours and
hex literals in `src/**/*.ts(x)` — JSON is outside its scan, and the runtime `setProperty` calls use
values read from that data, so the guard keeps working unchanged.

**Rationale**: writing the variables keeps the entire existing class vocabulary (`fill-chart-3`) and
both themes' machinery intact, and the preset only has to say "which hue is series 3 in dark". No
rebuild, no new Tailwind variant, no component churn. Alternatively compiling one CSS block per
preset into `index.css` would be 5 × 2 × 15 declarations of duplicated data with no JSON to check.

**Adding JSON imports**: `tsconfig.json` has `"include": ["src"]` and no `resolveJsonModule`; the flag
is added (one line) so `import impacto from "./palettes/impacto.json"` type-checks. Vitest already
imports JSON through esbuild.

**Typing**: `ReportDefinition.layout.theme` in `src/api/types.ts` and `PalettePreset` in
`src/theme/palette.ts` (role record + `strategy`), so a preset missing a role fails `tsc -b`.

## R6 — Effective preset resolution and branding clash

**Decision**: `layout.theme.palette` ?? `appearance_settings.palette_preset` ?? `"impacto"`, resolved
in the same order by web, shared view and PDF. A clashing brand primary never reaches chart series:
series hues come from the preset, only the interface `primary` role follows branding.

**Facts**: the installation's colours reach the browser as CSS variables `--brand-*`
([index.css:26-37](../../frontend/src/index.css:26)) that the interface tokens derive from
(`--c-primary: var(--brand-600)`), while chart series 1–2 derive from brand too
(`--c-chart-1: var(--brand-600)`). The PDF has no branding today (fixed hex constants,
[pdf.py:21-24](../../backend/app/reports/pdf.py:21)). There is **no installation settings store** —
only env config (`app/config.py`) and per-user theme/locale (`app/models.py:113-154`).

**Rationale**: resolving in one documented order keeps the spec's "effective preset = report override
or installation" and makes the PDF match the screen by construction. Keeping branding out of series
colours is the spec's own rule (edge case "presets derive series colours from fixed hues, only
`primary` follows branding"); the palette check enforces it because series are checked on the
preset's own surface, not on a branded one.

## R7 — Installation appearance setting

**Decision**: new singleton table `appearance_settings` + `GET/PUT /api/admin/appearance` +
`palette_preset` on `GET /api/config`.

**Facts**: the precedent for an admin-editable singleton is `telegram_settings`
([models.py:457](../../backend/app/models.py:457)) with `GET/PUT /api/admin/telegram` guarded by
`require_superuser` and audited ([telegram.py:34-69](../../backend/app/api/telegram.py:34)).
`GET /api/config` is the public, unauthenticated configuration surface
([health.py:30-41](../../backend/app/api/health.py:30)) already used for branding and Telegram
availability; the shared view is unauthenticated and needs the palette, so this is where it belongs.

**Alternatives considered**: (a) `PALETTE_PRESET` env var only — the spec puts the choice in
Administración → Apariencia and says the super user "picks and saves"; an env var would need a
redeploy per change and break VII's "difference is configuration set in the product"; (b) a JSON
settings blob on `dashboard` — wrong scope (installation-wide).

**Audit**: a new event name in the `AUDIT_EVENTS` tuple (`app/models.py:42-53`) so the trail stays
typed.

## R8 — Report definition key `layout.theme.palette`

**Decision**: `layout.theme = { palette?: <preset id> }`, validated by schema + CLI checker.

**Facts**: `layout` is validated by `cli/bizview_cli/report_layout.py`, which closes accepted keys per
block and refuses colour literals (`_LITERAL`, [_roles] at
[report_layout.py:518-535](../../cli/bizview_cli/report_layout.py:518)); the authoritative JSON Schema
is `cli/bizview_cli/schemas/report.schema.json` (026 contracts name it as the owner). There is **no
`layout.theme` today**; the backend never builds a pydantic model for the layout — it keeps the
definition and runs the CLI checker (`app/engine/report.py:867-879`).

**Rationale**: the override must travel with the workspace version and reach the PDF, so it belongs
inside the versioned definition. Reusing the CLI checker means the "unknown preset" error surfaces at
validation time, with the same `layout_range` issue type and Spanish message the other enum fields
use.

**Alternatives considered**: a column on the report row — invisible to the definition version and to
the PDF renderer, and it would break the declarative contract of 026.

## R9 — Filters and parameters live, in the URL

**Decision**: the sheet edits the same `ReportSelection` the page already parses from the query
string; `ParamsForm` gains `live` (250 ms debounce) and per-section rendering.

**Facts**: `parseSelection`/`serializeSelection`/`selectionQuery`
([lib/reportQuery.ts](../../frontend/src/lib/reportQuery.ts)) already make the URL the state, and the
data request is keyed by `selectionQuery(applied, def)`
([ReportView.tsx:263-286](../../frontend/src/pages/ReportView.tsx:263)). `ParamsForm` keeps a local
`draft` and only calls `onApply` on submit
([ParamsForm.tsx:30-54](../../frontend/src/components/report/ParamsForm.tsx:30)); its period block and
filter block are already `<section>`s inside one form.

**Rationale**: FR-004 wants URL state (already true) and live apply. Adding a debounced `onApply`
plus a `section` prop is a smaller change than a second form component, and it keeps one place that
knows how to build a selection. The 250 ms debounce bounds the number of `/data` requests while a
multi-select is being edited; the existing `loading`/`inert` handling keeps the page honest while a
request is in flight.

**Alternatives considered**: `useDeferredValue` on the query — does not give a time bound or cancel
the in-flight request; a WebSocket/push update — out of scope (II).

## R10 — Actions row and overflow

**Decision**: `ReportActions` with three breakpoint behaviours (icon+label ≥1024 px, icon + tooltip
on tablets, "⋯" menu on phones). Reuse `Button`/`IconButton` and the `CardMenu` keyboard pattern.

**Facts**: today the actions are plain `Button`s inside `ContextBlock`'s card header
([ReportView.tsx:551-628](../../frontend/src/pages/ReportView.tsx:551)) and a phone-only "Filtros"
button opens the `View`. `CardMenu.tsx` already implements the overflow menu with roving focus and
Escape; `IconButton` exists for icon-only affordances.

**Rationale**: one component owns the "which actions exist and how they collapse" question, so the
report page and the shared view cannot drift. The tablet tooltip uses `title` + `aria-label` rather
than a custom tooltip layer (no new primitive, acceptable for pointer users; keyboard users read the
label from the accessible name).

## R11 — "Consultado por" leaves the screen

**Decision**: stop passing `viewer` in both pages; keep the PDF meta line and the audit.

**Facts**: `ContextBlock` renders the viewer as a fourth `dl` cell
([ContextBlock.tsx:121-127](../../frontend/src/components/report/ContextBlock.tsx:121)); the PDF emits it
through the localized `pdf.viewer` string ([pdf.py:151-165](../../backend/app/reports/pdf.py:151));
the shared view already passes `viewer={null}`.

**Rationale**: FR-005's removal is about screen clutter; the PDF footer is the documented place for
it and the audit event already records who read what. Keeping the PDF string means nothing is lost.

## R12 — Shared view theme toggle and first-load theme

**Decision**: `ThemeSwitcher compact` in the shared header; optional `theme` on the share link,
applied once when the viewer has no stored preference.

**Facts**: the shared view is inside `ThemeProvider`/`LocaleProvider`
([App.tsx:53-60](../../frontend/src/App.tsx:53)) and already shows `LanguageSwitcher compact`;
`ThemeContext.setPreference` writes `localStorage` and only saves to the account when a user is signed
in — so an anonymous viewer's choice is device-local by construction
([ThemeContext.tsx:70-88](../../frontend/src/theme/ThemeContext.tsx:70)). `theme-init.js` already
resolves the device preference before first paint. `ShareLink` has no theme column
([models.py:737-770](../../backend/app/models.py:737)).

**Rationale**: reuse beats a bespoke toggle, and because the resolution happens before paint there is
no flash when the shared link forces a theme: the shared page writes the stored preference (if the
viewer has none) as soon as `GET /api/shared/{token}` answers, then re-applies. On a `localStorage`
miss we honour the link; on a hit we honour the viewer (spec edge case "viewer's choice wins after
the first load"). `try/catch` around storage is already the pattern in `theme/resolve.ts`.

**Alternatives considered**: a query parameter (`?theme=dark`) — nice for links but easy to leak into
copied URLs and it would fight the stored preference; the column keeps the sharer's intent on the
record with the token's other properties.

## R13 — Chart transitions

**Decision**: animate the data layer (opacity/translate, ≤300 ms) on data change; no geometry morph.

**Facts**: charts are SVG components drawing from `ChartFrame`/series data
(`components/report/charts/*`); there is no animation library, and the repo's motion convention is
Tailwind `transition-*` + `motion-reduce:transition-none` (already used on the report content,
[ReportView.tsx:490](../../frontend/src/pages/ReportView.tsx:490)). Playwright runs with
`reducedMotion: "reduce"` globally.

**Rationale**: SVG path/bar interpolation would mean writing an interpolator and re-testing every
chart kind for a 300 ms effect. A cross-fade keyed by the series signature reads as "the numbers
changed" and costs a class. `prefers-reduced-motion` removes it.

## R14 — The palette gate, mirror drift and the no-hex lint

**Decision**: one vitest file checks all presets × themes and the backend mirror; the no-hex rule
extends to report-definition fixtures.

**Facts**: `frontend/tests/unit/brand-contrast.test.ts` already parses `index.css` variables and
computes WCAG contrast in the test suite — the maths is there to reuse.
`guide-drift.test.ts` already reads `../backend/...` from the frontend suite, so a cross-package
assertion is an established pattern. `no-raw-colors.test.ts` guards `src/**`, not JSON fixtures. The
repository has **no `.github/workflows/`**, so "in CI" = the release gate that runs `npm test`,
`pytest` and `playwright` (documented in `CONTRIBUTING.md`); adding a workflow is out of scope for
this feature.

**Rationale**: the check must be impossible to skip locally, and reusing the existing suite means no
new tooling. The mirror is compared byte-for-byte so the PDF and the screen cannot diverge silently.

**Alternatives considered**: a Python copy of the checker — two implementations of the same maths
that can disagree; a build step that copies `frontend/` JSON into `backend/` — hidden magic, and the
backend image would then need the frontend sources (principle IV).

## Carried from the spec (not re-decided)

Sheet over modal (I + "views not modals"), chips under the title, URL-carried filter state, PDF always
light, presets as product data, no hex in report definitions, "Consultado por" off-screen — all taken
as given by the owner's decision list in [spec.md](./spec.md).
