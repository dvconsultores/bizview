# Implementation Plan: Dark mode

**Branch**: `006-dark-mode` | **Date**: 2026-09-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-dark-mode/spec.md`

## Summary

Add a dark theme and a "Sistema / Claro / Oscuro" choice. The UI's ~660 raw Tailwind colour
utilities are migrated to a small set of **semantic colour tokens** (CSS variables with light and
dark values, exposed as Tailwind colours), guarded by a unit test so no screen can reintroduce a
theme-blind colour. The resolved theme is a `data-theme` attribute on `<html>`, set before first
paint by a blocking same-origin script (`/theme-init.js`, CSP-safe) from a device cache and the OS
preference; after sign-in the account value wins. The preference is stored in a new
`app_user.theme` column (migration `0005_user_theme`) and changed with
`PATCH /api/me/preferences`. The trend chart reads the same tokens; PDFs are untouched (research
R1–R8).

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.9 (frontend)

**Primary Dependencies**: existing only — FastAPI, SQLAlchemy, Alembic; React 19, Tailwind CSS 3.4,
Lucide React (Sun/Moon/Monitor icons). No new libraries.

**Storage**: `public.app_user.theme` (migration `0005_user_theme`) on the external BI database;
device cache in `localStorage["bizview.theme"]`

**Testing**: pytest on `DATABASE_URL_BI` (`app_test_*` schemas): migration up/down, `GET /api/me`
carries `theme`, `PATCH /api/me/preferences` (200/401/403/422, idempotent). Vitest: theme
resolver, `theme-init.js` logic, guard test against raw palette classes and hex literals.
Playwright (3 engines × 320/375 px): new `tests/e2e/theme.spec.ts` — axe `color-contrast` on
every route in both themes (Playwright `colorScheme`), cross-context persistence, no-flash with
app bundle blocked, save-failure toast.

**Target Platform**: browsers of the existing matrix (Safari/iOS ≥ 14, Android ≥ 8, last 2 versions)

**Project Type**: web application (backend + frontend)

**Performance Goals**: theme swap < 1 s (SC-002; in practice one style recalculation); zero
flash of the wrong theme (SC-004); `theme-init.js` < 1 KB

**Constraints**: CSP `script-src 'self'` (no inline script); light theme visually unchanged;
WCAG 2.1 AA in both themes; mobile-first 375 px

**Scale/Scope**: ~50 frontend files touched mechanically (token migration), 1 column, 1 endpoint,
2 new components (ThemeProvider, ThemeSwitcher), 1 static script

## Constitution Check

| Rule | Status | Evidence |
|---|---|---|
| I. Mobile-first, Tailwind only | PASS | tokens are Tailwind colours; switcher 44 px targets; e2e at 320/375 px; no custom CSS framework (only CSS variables in `index.css`) |
| II. Backend as ETL | N/A | no data path change |
| III. Source of truth external | N/A | origin untouched |
| IV. Folders | PASS | frontend code in `frontend/`, column + route in `backend/app/` |
| V. Fixed stack | PASS | no stack component added; no supporting library added |
| VI. Data tuning | N/A | — |
| VII. One product, many installations | PASS | no customer-specific colours; dark accent derived from the brand scale variables |
| VIII. AI optional/private | N/A | — |
| IX. Spec-driven reporting | PASS | report renderer only re-coloured; report specs unchanged |
| Constraint: product schema via Alembic | PASS | `0005_user_theme` |
| Constraint: JSON API, PDFs by ReportLab | PASS | new endpoint is JSON; PDFs unchanged (R8) |
| Constraint: CSRF / same origin | PASS | PATCH goes through the existing `X-Requested-With` + Origin check |
| License: source link on every page | PASS | `SourceFooter` migrated to tokens, still present |

Post-design re-check (after Phase 1): unchanged — all PASS, no Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/006-dark-mode/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md             # user_json.theme, PATCH /api/me/preferences
│   └── theme-tokens.md    # token table, guard rule, document contract, switcher
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0005_user_theme.py      new: app_user.theme + CHECK
├── app/models.py                            AppUser.theme
├── app/api/schemas.py                       user_json + ThemeIn (extra="forbid")
├── app/api/me.py                            PATCH /api/me/preferences
└── tests/test_me.py, test_migrations.py     new cases

frontend/
├── index.html                               <script src="/theme-init.js"> in <head>, color-scheme
│                                            "light dark", body bg-canvas text-ink
├── public/theme-init.js                     new: pre-paint resolver (classic script)
├── tailwind.config.js                       token colours, shadow vars
├── src/index.css                            :root / [data-theme=dark] token values
├── src/theme/ThemeContext.tsx               new: provider, useTheme, media-query listener
├── src/theme/resolve.ts                     new: pure resolver shared with tests
├── src/components/ThemeSwitcher.tsx         new: radiogroup Sistema/Claro/Oscuro
├── src/components/*.tsx, src/pages/**/*.tsx token migration (codemod + review)
├── src/components/report/TrendChart.tsx     SVG colours from --chart-* variables
├── src/components/AppShell.tsx              switcher in account menu
├── src/pages/Profile.tsx                    "Apariencia" card
├── src/auth/AuthContext.tsx                 hand user.theme to ThemeProvider
├── src/api/types.ts                         User.theme, ThemePreference
├── src/i18n/es.ts                           theme.* strings
├── scripts/codemod-tokens.mjs               one-off migration script (deleted after use)
└── tests/unit/{theme.test.ts,no-raw-colors.test.ts}, tests/e2e/theme.spec.ts
```

**Structure Decision**: existing web-application layout (features 002–005). Theme code gets its
own `src/theme/` folder next to `src/config/` (branding) so a developer finds it in one place.

## Implementation notes for tasks

1. Backend first (migration, model, schema, endpoint, tests) — independent of the UI.
2. Tokens + `index.css` + `tailwind.config.js` with light values equal to today; then the codemod
   over `src/` using the mapping in [contracts/theme-tokens.md](./contracts/theme-tokens.md);
   review the ambiguous hits by hand (`bg-white` on hero, `bg-slate-900` toast, `hover:bg-brand-700`).
   Light screenshots before/after must match (quickstart 16) before dark values are added.
3. Dark values, `theme-init.js`, ThemeProvider, TrendChart variables → US1 + US3 testable.
4. Switcher (profile + account menu), persistence, failure toast → US2.
5. Guard test + e2e theme suite + axe on all routes in both themes.

## Complexity Tracking

No constitution violations; nothing to justify.
