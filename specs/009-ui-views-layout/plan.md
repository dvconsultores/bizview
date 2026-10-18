# Implementation Plan: Views instead of modals, wider layout, Ubuntu font

**Branch**: `009-ui-views-layout` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-ui-views-layout/spec.md`

## Summary

Replace the overlay `Modal` with an in-place `View`: a portal into the nearest view host
(`AppShell` page area, or the app root outside the shell) that hides the page content (kept
mounted) and shows a titled screen with a back button. Same-URL history entries make the browser
back button cancel a view; secrets stay in memory only. The global step-up becomes a view and
keeps the interrupted page mounted, so its form state survives and the API client's single retry
completes the action. The shell's main area widens to 1536 px and per-page caps go; Ubuntu is
vendored as woff2 with its licence (research R1–R8).

## Technical Context

**Language/Version**: TypeScript 5.9 (frontend only)

**Primary Dependencies**: existing only — React 19, React Router 7, Tailwind CSS 3.4, Lucide React.
No new libraries (font files are vendored assets).

**Storage**: none (no backend, API or migration change)

**Testing**: Vitest — `View`/`ViewHost` (portal, hidden host content kept mounted, stacking,
back = cancel, focus/scroll restore), `ReauthProvider` (shared promise, cancel/confirm), guard
`no-modals.test.ts`. Playwright (3 engines × 320/375 px, plus a 1920 px width check): e2e specs
that addressed `role="dialog"` move to the view's region/heading; new `tests/e2e/views.spec.ts`
(each call site, back button, secret not reachable after back/forward/reload, step-up keeps typed
text and runs once, width ≥ 85 % at 1920 px, no horizontal scroll at 320/375, Ubuntu served
locally).

**Target Platform**: browsers of the existing matrix (Safari/iOS ≥ 14, Android ≥ 8, last 2 versions)

**Project Type**: web application (frontend part)

**Performance Goals**: view open/close is a re-render (no network); font adds ≤ ~120 KB woff2,
cached, `font-display: swap`

**Constraints**: CSP `font-src 'self'`, `script-src 'self'`; WCAG 2.1 AA in both themes;
mobile-first 320/375 px; feature-006 token guard (no raw colours)

**Scale/Scope**: 2 new components (`View`, `ViewHost`), 1 deleted (`Modal`), 7 call-site files,
~15 page wrappers (width), 1 Tailwind config, 1 CSS file, 5 e2e specs touched, 1 new e2e spec,
2 new unit tests

## Constitution Check

| Rule | Status | Evidence |
|---|---|---|
| I. Mobile-first, Tailwind only | PASS | views stack actions full-width on phones; `@font-face` lives in `index.css` like the theme tokens; no CSS framework |
| II. Backend as ETL | N/A | no backend change |
| III. Source of truth external | N/A | — |
| IV. Folders | PASS | all code in `frontend/`; fonts under `frontend/src/assets/fonts/` |
| V. Fixed stack | PASS | no library added; font files are assets |
| VI. Data tuning | N/A | — |
| VII. One product, many installations | PASS | font and layout are product-wide; branding colours/logo untouched |
| VIII. AI optional/private | N/A | — |
| IX. Spec-driven reporting | PASS | report renderer only widened; report specs unchanged |
| Constraint: JSON API, PDFs by ReportLab | PASS | PDFs unchanged |
| Constraint: CSP / same origin | PASS | fonts served by the installation (`font-src 'self'`) |
| License: source link on every page | PASS | `SourceFooter` untouched; Ubuntu Font Licence shipped with the files |

Post-design re-check: unchanged — all PASS, no Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/009-ui-views-layout/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/views.md     # View/ViewHost API, history, step-up, call sites, layout, font
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
frontend/
├── src/components/View.tsx            new: in-place view (replaces Modal)
├── src/components/ViewHost.tsx        new: host + context (stack), history marker
├── src/components/Modal.tsx           deleted
├── src/components/ReauthDialog.tsx    step-up as a View, shared promise
├── src/components/TwoFactorCard.tsx   recovery codes + disable → View
├── src/components/CopyButton.tsx      SecretBox → font-mono
├── src/components/AppShell.tsx        ViewHost around Outlet; main max-w-screen-2xl, lg:px-8
├── src/App.tsx                        root ViewHost around Routes
├── src/pages/admin/UserForm.tsx       created → View; xl two-column fields; font-mono
├── src/pages/admin/UserDetail.tsx     4 confirmations + reset password → View
├── src/pages/admin/Workspace.tsx      rollback → View
├── src/pages/admin/SourceForm.tsx     delete → View; xl two-column fields
├── src/pages/**/*.tsx                 drop max-w-2xl/3xl page caps; ReportView max-w-7xl
├── src/index.css                      @font-face Ubuntu (latin, latin-ext × 400/500/700)
├── src/assets/fonts/ubuntu/           woff2 files + LICENCE.txt
├── tailwind.config.js                 fontFamily.sans Ubuntu-first, fontFamily.mono
└── tests/
    ├── unit/{views.test.tsx,no-modals.test.ts}
    └── e2e/views.spec.ts; reporting/security/telegram/theme/flows specs: dialog → region
```

**Structure Decision**: existing web-application layout; view primitives sit with the other
shared components in `src/components/`.

## Implementation notes for tasks

1. `View` + `ViewHost` + unit tests first (contract in contracts/views.md); mount hosts.
2. Step-up (`ReauthProvider`) on `View`; update the 4 e2e specs that confirm the password.
3. Migrate the 9 other call sites; delete `Modal`; guard test.
4. Width (shell + page wrappers + two-column forms), then font (assets, `@font-face`, Tailwind).
5. `views.spec.ts`, then the full frontend suites; CHANGELOG.

## Complexity Tracking

No constitution violations; nothing to justify.
