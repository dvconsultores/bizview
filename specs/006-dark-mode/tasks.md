---
description: "Task list for feature 006 — Dark mode"
---

# Tasks: Dark mode

**Input**: Design documents from `/specs/006-dark-mode/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md),
[contracts/theme-tokens.md](./contracts/theme-tokens.md), [quickstart.md](./quickstart.md)

**Tests**: included — the spec's success criteria (SC-001 contrast on every screen, SC-003
cross-device, SC-004 no flash) and the plan's testing section require them.

**Organization**: by user story, in priority order US1 (P1) → US3 (P1) → US2 (P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, US3 from spec.md

---

## Phase 1: Setup

**Purpose**: baseline for "light theme unchanged" (quickstart 16).

- [X] T001 Capture light-theme baseline screenshots (home, a report, profile, admin users, sign-in) at 375 px with a throwaway Playwright script in the scratchpad (not committed); keep them for T008 comparison

---

## Phase 2: Foundational (blocking)

**Purpose**: semantic tokens with **light values only** and every component migrated to them.
After this phase the app looks as today; dark values come in US1.

- [X] T002 Define light token variables (RGB triplets) on `:root` in frontend/src/index.css per the "Light" column of contracts/theme-tokens.md: `--c-canvas, --c-surface, --c-surface-2, --c-line, --c-line-strong, --c-ink, --c-ink-2, --c-ink-muted, --c-ink-faint, --c-accent, --c-accent-soft, --c-accent-line, --c-primary, --c-primary-hover, --c-on-primary, --c-danger, --c-danger-soft, --c-danger-line, --c-danger-solid, --c-success, --c-success-soft, --c-success-line, --c-warning, --c-warning-soft, --c-warning-line, --c-backdrop, --c-toast, --c-chart-1, --c-chart-2, --c-chart-grid, --c-chart-axis, --c-chart-label`, plus `--shadow-card`, `--shadow-raised`, `--focus`; brand-derived tokens reference the `--brand-*` variables; `:root { color-scheme: light }`; `:focus-visible` uses `--focus`
- [X] T003 Expose tokens in frontend/tailwind.config.js `theme.extend.colors` (kebab names as in the contract, `rgb(var(--c-x) / <alpha-value>)`) and point `boxShadow.card`/`raised` to `var(--shadow-card)`/`var(--shadow-raised)`
- [X] T004 Write the one-off codemod frontend/scripts/codemod-tokens.mjs: maps raw palette utilities (with any variant prefix such as `hover:`, `focus:`, `disabled:`, `sm:`) to tokens per the "Replaces today" column of contracts/theme-tokens.md; skips hero contexts (lines containing `bg-hero`, `Logo` inverted branch, `text-white`/`bg-white/NN`/`ring-white/NN`/`text-brand-100` used on the hero); prints every unmapped or ambiguous hit as file:line
- [X] T005 Run the codemod over frontend/src/components/**/*.tsx and frontend/src/pages/**/*.tsx and hand-fix the ambiguous hits it reports (toast `bg-slate-900` → `bg-toast`, modal `bg-slate-900/50` → `bg-backdrop/50`, `text-white` on solid fills → `text-on-primary`, `hover:bg-brand-700` → `hover:bg-primary-hover`, `bg-rose-600/700/800` → `bg-danger-solid` + hover opacity)
- [X] T006 Update frontend/index.html: `<meta name="color-scheme" content="light dark">`, `<body class="bg-canvas text-ink antialiased">`
- [X] T007 [P] Guard test frontend/tests/unit/no-raw-colors.test.ts: scan frontend/src/**/*.{ts,tsx} for raw palette utilities `(bg|text|border|ring|divide|fill|stroke|placeholder|from|via|to|outline|shadow)-(white|black|slate|gray|zinc|brand|rose|emerald|amber|red|green|blue|sky|indigo|yellow|orange)(-\d+)?` and for `#[0-9a-fA-F]{3,8}`/`rgb(` literals; explicit allow-list with reasons (AppShell header block, `Logo` inverted branch, SignIn and ChangePassword hero blocks); failure message lists file:line; also forbid `text-ink-faint` on `<p>`/body text (warn-level list)
- [X] T008 Build and compare against the T001 baseline; differences allowed only for the collapsed steps listed in contracts/theme-tokens.md; delete frontend/scripts/codemod-tokens.mjs once the guard test (T007) passes

**Checkpoint**: `npm test` green (guard included), app visually unchanged in light.

---

## Phase 3: User Story 1 — The app follows my device's theme (P1) 🎯 MVP

**Goal**: complete dark theme selected automatically from the device appearance, with no flash.

**Independent test**: device/emulation dark → sign-in and every screen dark; flip appearance live
→ swaps without reload (quickstart 1–3, 10).

- [X] T009 [US1] Add the dark token values on `:root[data-theme="dark"]` in frontend/src/index.css per the "Dark" column of contracts/theme-tokens.md (incl. `color-scheme: dark`, `--shadow-card`/`--shadow-raised` with a 1 px `--c-line` ring), leaving `.bg-hero` unchanged
- [X] T010 [P] [US1] Pure resolver frontend/src/theme/resolve.ts: `type ThemePreference = "system" | "light" | "dark"`, `isPreference(v)`, `resolveTheme(pref, prefersDark: boolean): "light" | "dark"`, `applyTheme(resolved)` (sets `document.documentElement.dataset.theme`, updates `<meta name="theme-color">` to the hero colour `#1e3a8a` light / `#172554` dark), `readCachedPreference()`/`writeCachedPreference()` on `localStorage["bizview.theme"]` wrapped in try/catch (fallback `system`), `systemPrefersDark()` guarded for missing `matchMedia` (→ false)
- [X] T011 [P] [US1] Pre-paint script frontend/public/theme-init.js (classic script, no modules, < 1 KB, ES2017-safe for Safari 14): same logic as resolve.ts (read cache → resolve with matchMedia → set `data-theme` and theme-color), every access in try/catch, default light
- [X] T012 [US1] Load it in frontend/index.html `<head>` as `<script src="/theme-init.js"></script>` before any stylesheet/module script (blocking, same origin — CSP `script-src 'self'`)
- [X] T013 [US1] ThemeProvider + `useTheme()` in frontend/src/theme/ThemeContext.tsx: state `preference` (initial = cached), `resolved`; subscribes to `matchMedia("(prefers-color-scheme: dark)")` change events only while preference is `system` (use `addEventListener` with `addListener` fallback for Safari 14); calls `applyTheme` on every change; exposes `setPreference` (local apply + cache only in this phase) and `adoptAccountPreference(p)`
- [X] T014 [US1] Wrap the app with `ThemeProvider` in frontend/src/App.tsx (outside the router outlet, alongside BrandingProvider) so sign-in screens are covered
- [X] T015 [P] [US1] Unit tests frontend/tests/unit/theme.test.ts: resolver matrix (3 prefs × prefersDark), invalid cache value → `system`, storage throwing → `system`, missing matchMedia → light, `applyTheme` sets attribute + meta; load public/theme-init.js source in jsdom and assert it sets `data-theme` for cached `dark` and for `system` + dark media
- [X] T016 [US1] Walk every route in dark (sign-in, cambiar-clave, seguridad/doble-factor, home, d/:code, r/:id, perfil, all admin/*, no-autorizado, 404, open Modal, ReauthDialog, Toast, Alert variants, Badge, Input error state, Switch, EmptyState, Spinner, SourceFooter) and fix residual contrast issues in the owning component under frontend/src/components or frontend/src/pages
- [X] T017 [US1] E2E frontend/tests/e2e/theme.spec.ts (part 1): with `colorScheme: "dark"` — axe (`wcag2a, wcag2aa, wcag21aa, wcag22aa`) on every route listed in T016 for both `colorScheme` dark and light with 0 violations (SC-001); live swap via `page.emulateMedia({ colorScheme })` keeps typed text in an input (FR-005); no-flash: `page.route("**/assets/*.js", r => r.abort())`, load `/ingresar`, assert `html[data-theme=dark]` (FR-006, SC-004)

**Checkpoint**: MVP — dark mode automatic and accessible everywhere.

---

## Phase 4: User Story 3 — Reports stay readable in the dark (P1)

**Goal**: every report component legible in dark with meaningful, non-colour-only encodings.

**Independent test**: report with KPIs, trend with previous period, ranking, data table,
narrative at 375 px in dark; axe clean; PDF unchanged (quickstart 11, 12).

- [X] T018 [US3] frontend/src/components/report/TrendChart.tsx: replace hex colours with `rgb(var(--c-chart-grid))`, `rgb(var(--c-chart-axis))` (zero line), `rgb(var(--c-chart-label))` (tick text), `rgb(var(--c-chart-1))` (current series, points), `rgb(var(--c-chart-2))` dashed `4 3` (previous series), hover guide `--c-chart-axis`; tooltip uses surface/ink tokens and names both series in text
- [X] T019 [P] [US3] frontend/src/components/report/KpiGrid.tsx and RankingTable.tsx: deltas keep arrow icon + sign + text next to success/danger token colours (FR-010), verify tokens came through the codemod
- [X] T020 [P] [US3] frontend/src/components/report/DataTable.tsx, Narrative.tsx, PeriodPicker.tsx: header, row separators (`divide-line`), sticky header background (`bg-surface`), selected period (`bg-accent-soft text-accent`) — verify and fix
- [X] T021 [US3] E2E in frontend/tests/e2e/theme.spec.ts (part 2): in dark at the project widths open the seeded report used by tests/e2e/reporting.spec.ts, assert no horizontal scroll, axe clean, previous-period path has `stroke-dasharray`; download the PDF in dark and in light and assert equal bytes after removing `/CreationDate` and `/ModDate` (FR-012, SC-006)

**Checkpoint**: US1 + US3 = dark mode shippable without the manual choice.

---

## Phase 5: User Story 2 — I choose my theme and it follows me (P2)

**Goal**: "Sistema / Claro / Oscuro" choice, applied instantly, stored on the account.

**Independent test**: choose "Oscuro" in one browser context, sign in with the same user in a
fresh light context → dark after sign-in (quickstart 4–9, 15).

- [X] T022 [US2] Migration backend/alembic/versions/0005_user_theme.py (revision `0005_user_theme`, down_revision `0004_vibe_reporting`): add `app_user.theme text NOT NULL DEFAULT 'system'` with CHECK `theme IN ('system','light','dark')` named `ck_app_user_theme` (follow the naming convention used in 0003/0004); downgrade drops constraint and column
- [X] T023 [US2] backend/app/models.py: `AppUser.theme: Mapped[str] = mapped_column(Text, server_default=text("'system'"))` and the CHECK in `__table_args__` (`_in("theme", THEMES)` with `THEMES = ("system", "light", "dark")`)
- [X] T024 [US2] backend/app/api/schemas.py: add `"theme": u.theme` to `user_json`; add `PreferencesIn` (pydantic, `extra="forbid"`, `theme: Literal["system","light","dark"]`)
- [X] T025 [US2] backend/app/api/me.py: `@router.patch("/preferences")` with `auth_allow_temporary`; sets `auth.user.theme`, commits following the module's commit-before-response pattern, returns `{"theme": ...}`; no audit record; invalid value → 422 with `fields.theme = "invalid"` in the common validation body
- [X] T026 [P] [US2] Backend tests in backend/tests/test_me.py: `GET /api/me` has `theme == "system"` for a new user; PATCH `dark` → 200 and persisted (re-GET); same value twice → 200; `{"theme":"sepia"}` → 422 `fields.theme`; extra field → 422; no session → 401; missing `X-Requested-With` → 403 `csrf_failed`; allowed for a temporary-password session
- [X] T027 [P] [US2] backend/tests/test_migrations.py: upgrade adds the column with default `system` on existing rows, rejects `'sepia'`; downgrade removes it
- [X] T028 [P] [US2] frontend/src/api/types.ts: `export type ThemePreference = "system" | "light" | "dark"`; `User.theme: ThemePreference` (import/re-export the type from src/theme/resolve.ts or vice versa, single definition)
- [X] T029 [P] [US2] frontend/src/i18n/es.ts: `theme` block — `title: "Apariencia"`, `label: "Tema"`, `system: "Sistema"`, `light: "Claro"`, `dark: "Oscuro"`, `hint: "«Sistema» sigue la configuración de tu dispositivo."`, `saveFailed: "Tema aplicado en este dispositivo, pero no se pudo guardar en tu cuenta."`
- [X] T030 [US2] frontend/src/theme/ThemeContext.tsx: `setPreference(p)` applies + caches immediately, then `api.patch("/api/me/preferences", { theme: p })` when signed in; on failure shows the `saveFailed` toast (existing Toast mechanism) and keeps the applied theme (FR-013)
- [X] T031 [US2] (implemented in frontend/src/theme/ThemeContext.tsx, which reads `useAuth().user`; AuthContext unchanged) when the user is loaded (sign-in response and `/api/me`), call `adoptAccountPreference(user.theme)` (server wins, cache refreshed); on sign-out leave the cache untouched (FR-007)
- [X] T032 [US2] New frontend/src/components/ThemeSwitcher.tsx per contracts/theme-tokens.md: `role="radiogroup"` `aria-label={t.theme.label}`, three `role="radio"` buttons (Lucide `Monitor`, `Sun`, `Moon` + text), `aria-checked`, roving tabindex with arrow keys, each ≥ 44 × 44 px (`min-h-tap min-w-tap`), tokens only; props `compact?: boolean` for the menu variant
- [X] T033 [US2] frontend/src/pages/Profile.tsx: new `Card` "Apariencia" with `ThemeSwitcher` and the hint text, placed before the security card
- [X] T034 [US2] frontend/src/components/AppShell.tsx: `ThemeSwitcher compact` inside the account menu between the user header and "Perfil" (menu open = tap 1, option = tap 2); choosing does not close the menu
- [X] T035 [US2] E2E in frontend/tests/e2e/theme.spec.ts (part 3): Profile → "Oscuro" applies without navigation (FR-003); account menu → "Claro" in ≤ 2 taps from a report (SC-002); context A picks "Oscuro", fresh context B (`colorScheme: "light"`) signs in → dark (SC-003); "Claro" + `emulateMedia dark` stays light; `page.route("**/api/me/preferences", r => r.fulfill({ status: 500 }))` → theme applied + toast text (FR-013); sign out after "Oscuro" and reload `/ingresar` → dark (FR-007)

**Checkpoint**: all three stories complete and independently verified.

---

## Phase 6: Polish & cross-cutting

- [X] T036 [P] Unit test for ThemeSwitcher keyboard behaviour and aria in frontend/tests/unit/theme.test.ts (arrow keys move and select, `aria-checked` follows)
- [X] T037 [P] Update CHANGELOG.md (Unreleased: dark mode, `PATCH /api/me/preferences`, migration `0005_user_theme`) (docs/ has no end-user guide — INSTALL.md and VIBE-REPORTING.md only — so no docs note)
- [X] T038 Run the full suites: `cd backend && uv run pytest`; `cd frontend && npm test && npm run build && npm run check:compat && npm run e2e`; fix regressions — results 2026-09-30: frontend unit 39/39, build + check:compat OK, e2e 96/96 (3 engines × 320/375); backend tests 1–288 passed in the full run (2 skipped), 289–296 (test_vibe_reporting) passed when rerun alone — the full run hung at #289 because it ran concurrently with e2e on the same database (advisory locks are database-wide): run the two suites sequentially
- [X] T039 Walk quickstart.md scenarios 1–16 and tick them in the PR description; confirm the checklist in checklists/requirements.md still holds — *scenarios covered by theme.spec.ts e2e on 3 engines; Baseline 2026-10-08: backend (all pass after 2 test fixes and 3 network-timeout reruns), CLI, frontend unit 425, build, compat, Playwright 300 passed / 36 skipped*

---

## Dependencies & execution order

- Setup (T001) → Foundational (T002–T008) → **blocks all stories**.
- US1 (T009–T017) needs Foundational. US3 (T018–T021) needs T009 (dark values) and T014; can run
  in parallel with T016–T017. US2 backend (T022–T027) is independent of the UI phases and can
  start right after Setup; US2 frontend (T028–T035) needs T013.
- Polish after all stories.

```text
T001 → T002 → T003 → T004 → T005 → T006 → T008
                               └──→ T007 ┘
T008 → T009 → T010/T011 → T012 → T013 → T014 → T015/T016 → T017
                                          └→ T018 → T019/T020 → T021
T022 → T023 → T024 → T025 → T026/T027          (any time after T001)
T013 + T025 → T028/T029 → T030 → T031 → T032 → T033/T034 → T035
all → T036–T039
```

## Parallel examples

- Foundational: T007 (guard test) while T005 (codemod review) proceeds.
- US1: T010 (resolve.ts) ‖ T011 (theme-init.js); later T015 ‖ T016.
- US3: T019 (KPI/Ranking) ‖ T020 (DataTable/Narrative/PeriodPicker).
- US2: backend T022–T027 ‖ frontend phases US1/US3; T026 ‖ T027; T028 ‖ T029.

## Implementation strategy

1. **MVP** = Setup + Foundational + US1: dark mode follows the device, all screens accessible.
2. Add US3 (report polish + PDF regression) → shippable dark mode.
3. Add US2 (explicit choice, account persistence) → full feature.
4. Each checkpoint runs `npm test` and the relevant Playwright part before moving on.

---

## Phase 7: Convergence

- [X] T040 Make `setPreference` in frontend/src/theme/ThemeContext.tsx ignore out-of-order `PATCH /api/me/preferences` responses (only the latest request may update `user.theme`), with a unit test in frontend/tests/unit/theme.test.ts, per FR-004 / US2/AC1 (partial) — executed by DeepSeek, audited (save queue + latest-only guard; new tests/unit/theme-provider.test.ts, mutation-checked)
- [X] T041 Extend the axe sweep in frontend/tests/e2e/theme.spec.ts to an open dialog (e.g. Workspace "¿Volver a la versión anterior?" or TwoFactorCard disable dialog) and `/admin/usuarios/:id`, in both themes, per SC-001 / FR-008 (partial)
- [X] T042 Repeat the no-flash check in frontend/tests/e2e/theme.spec.ts over 10 consecutive loads, per SC-004 (partial)

---

## Phase 8: Convergence

- [X] T043 E2E in frontend/tests/e2e/theme.spec.ts, `colorScheme: "dark"` device: Profile → "Claro" applies light at once and `aria-checked` follows; `emulateMedia` light→dark keeps light; a fresh `colorScheme: "dark"` context signing in with the same user shows light; sign out + reload `/ingresar` → light — the explicit light choice is proven like "Oscuro" already is, per US2/AC1, US2/AC2, US2/AC3, FR-001, FR-007 (partial) — *present in frontend/tests/e2e/theme.spec.ts, passing on chromium/firefox/webkit; Baseline 2026-10-08: backend (all pass after 2 test fixes and 3 network-timeout reruns), CLI, frontend unit 425, build, compat, Playwright 300 passed / 36 skipped*
- [X] T044 E2E in frontend/tests/e2e/theme.spec.ts: in one session switch through the account menu Oscuro → Claro → Sistema → Oscuro → Claro, asserting `data-theme` after each tap, that each PATCH /api/me/preferences returns the chosen value, and that after "Sistema" the screen follows `emulateMedia` again; reload → last choice ("Claro") kept, per FR-002, FR-003, FR-004, FR-005, SC-002 (partial) — *present in frontend/tests/e2e/theme.spec.ts, passing on chromium/firefox/webkit; Baseline 2026-10-08: backend (all pass after 2 test fixes and 3 network-timeout reruns), CLI, frontend unit 425, build, compat, Playwright 300 passed / 36 skipped*
