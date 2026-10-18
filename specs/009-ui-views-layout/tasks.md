---
description: "Task list for feature 009 — Views instead of modals, wider layout, Ubuntu font"
---

# Tasks: Views instead of modals, wider layout, Ubuntu font

**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/views.md](./contracts/views.md),
[quickstart.md](./quickstart.md)

**Tests**: included — SC-001…SC-006 require automated proof (guard, unit, e2e).

**Roles**: DeepSeek writes the code from briefs; Claude audits, fixes via DeepSeek, converges.
Frontend only: no backend, API or migration change.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Vendor the Ubuntu font: `npm pack @fontsource/ubuntu` in the scratchpad (not a dependency), copy `ubuntu-latin-{400,500,700}-normal.woff2` and `ubuntu-latin-ext-{400,500,700}-normal.woff2` into frontend/src/assets/fonts/ubuntu/ and the package's licence text as frontend/src/assets/fonts/ubuntu/LICENCE.txt (Ubuntu Font Licence 1.0); record the source version in a one-line frontend/src/assets/fonts/ubuntu/README.md

---

## Phase 2: Foundational (blocking)

**Purpose**: the view primitives every story uses (contracts/views.md).

- [X] T002 New frontend/src/components/ViewHost.tsx: `ViewHostContext` with a stack of mounted hosts (innermost wins); `ViewHost({children})` renders `<div hidden={viewOpen}>{children}</div>` plus a slot `<div>` for views; exposes `register/unregister` of open views so the host knows when to hide its content; several open views → only the most recently opened is visible, closing it reveals the previous (research R2)
- [X] T003 New frontend/src/components/View.tsx with props `open, title, onClose, children, footer?, autoFocus?`: portal into the innermost host slot; markup per contracts/views.md (`<section aria-labelledby>`, back button `aria-label="Volver"` with Lucide `ArrowLeft`, `<h1 tabIndex={-1}>`, footer `flex flex-col-reverse gap-3 sm:flex-row sm:justify-end`); NEVER `role="dialog"`, `aria-modal`, `fixed`, backdrop, scroll lock or focus trap; tokens only; Esc → `onClose`
- [X] T004 In View.tsx implement history (research R3): on open `navigate({pathname, search, hash}, { state: { ...location.state, view: [...ids, id] } })`; when the location's `state.view` no longer contains the id while open → `onClose()`; UI close while its entry is on top → `navigate(-1)`; entries with ids not open (reload/forward) are ignored
- [X] T005 In View.tsx implement focus and scroll (research R5): on open save `document.activeElement` and `scrollY`, `scrollTo(0, 0)`, focus the first input when `autoFocus` else the `<h1>`; on close restore `scrollY` and focus the saved element if still connected
- [X] T006 Mount hosts: frontend/src/components/AppShell.tsx wraps `<Outlet />` in `<ViewHost>`; frontend/src/App.tsx wraps `<Routes>` in a root `<ViewHost>` inside the router and inside `ReauthProvider`'s children (the step-up view must find a host through context)
- [X] T007 [P] Unit tests frontend/tests/unit/views.test.tsx (MemoryRouter): open view hides host content but keeps it mounted (an input keeps its typed value after close); view renders inside the innermost host; stacking two views shows the newer and reveals the older on close; browser back (`navigate(-1)`) calls `onClose` once; UI close pops the history entry; Esc closes; focus goes to `<h1>` (or first input with `autoFocus`) and returns to the opener; no element has `role="dialog"`

**Checkpoint**: `npm test` green; `Modal` still in use (nothing migrated yet).

---

## Phase 3: User Story 1 — Confirmations and results are screens (P1) 🎯 MVP

**Goal**: every confirmation/result in FR-002 except the step-up is a `View`.

**Independent test**: quickstart 1–3 and 6.

- [X] T008 [US1] frontend/src/pages/admin/UserForm.tsx: "Usuario creado." → `View` with email, `SecretBox`, `CopyButton`, hint, footer "Crear otro" / "Ver usuario"; `onClose` = "Ver usuario" behaviour as today; the password lives only in `created` state and is cleared on close (FR-005)
- [X] T009 [US1] frontend/src/pages/admin/UserDetail.tsx: `ResetPasswordModal` → `ResetPasswordView` (form with `autoFocus`, then result with secret and "Cerrar"; secret cleared on close); Telegram unlink, two-step reset and deactivate/reactivate confirmations → `View` with "Cancelar" + action; errors stay on the view (`actionError`) and the action can be retried
- [X] T010 [P] [US1] frontend/src/components/TwoFactorCard.tsx: recovery codes → `View` (codes, copy, "Listo"; codes cleared on close); disable two-step → `View` with password field (`autoFocus`), "Cancelar" + "Desactivar"
- [X] T011 [P] [US1] frontend/src/pages/admin/Workspace.tsx: "¿Volver a la versión anterior?" → `View` with "Cancelar" + today's action label
- [X] T012 [P] [US1] frontend/src/pages/admin/SourceForm.tsx: delete confirmation → `View` with "Cancelar" + "Eliminar"
- [X] T013 [US1] Update frontend/tests/e2e/flows.spec.ts: "Usuario creado." is located as `page.getByRole("region", { name: "Usuario creado." })` (or its `h1`), not a dialog

**Checkpoint**: all admin confirmations are views; only the step-up still uses `Modal`.

---

## Phase 4: User Story 2 — Confirming my password does not lose my work (P1)

**Goal**: step-up as a view that preserves the interrupted page and resumes the action once.

**Independent test**: quickstart 4–5.

- [X] T014 [US2] frontend/src/components/ReauthDialog.tsx: render `<View title={t.reauth.title} autoFocus>` instead of `Modal`; concurrent `ask()` calls share one pending promise (resolve all together); back/Cancelar → `false`; wrong password keeps the view, shows the error, clears the field; 423/429 closes with `false` (as today); keep `setReauthHandler` wiring
- [X] T015 [US2] Delete frontend/src/components/Modal.tsx; no file imports it
- [X] T016 [P] [US2] Unit tests in frontend/tests/unit/views.test.tsx: `ReauthProvider` — two concurrent `ask()` resolve together on confirm; cancel resolves `false`; an input on the page behind keeps its value through confirm and cancel (mock `api.post`)
- [X] T017 [US2] Update e2e specs that confirm the password: frontend/tests/e2e/reporting.spec.ts, security.spec.ts, telegram.spec.ts (`confirmPasswordIfAsked`), theme.spec.ts (axe on the open step-up) — `getByRole("dialog", { name: "Confirma tu contraseña" })` → `getByRole("region", { name: "Confirma tu contraseña" })`, keep the same steps

**Checkpoint**: zero `Modal` uses; e2e that rely on the step-up pass.

---

## Phase 5: User Story 3 — Pages use the width of large screens (P2)

**Goal**: ≥ 85 % of the area beside the sidebar at 1920 px; phones unchanged.

**Independent test**: quickstart 7–8.

- [X] T018 [US3] frontend/src/components/AppShell.tsx: `<main>` classes → `mx-auto max-w-screen-2xl px-4 pb-10 pt-5 sm:px-6 sm:pt-8 lg:px-8 lg:pb-12`
- [X] T019 [P] [US3] Remove page-wrapper width caps (`mx-auto max-w-2xl` / `max-w-3xl`) in frontend/src/pages/Profile.tsx and frontend/src/pages/admin/{AdminHome,Audit,Integrations,AI,Security,Sources,SourceForm,Tokens,UserDetail,UserForm,Workspace}.tsx (keep their `space-y-*`); in frontend/src/pages/ReportView.tsx `max-w-5xl` → `max-w-7xl`; SignIn and ChangePassword unchanged
- [X] T020 [US3] Two-column short fields from `xl` (`xl:grid xl:grid-cols-2 xl:gap-5`, long fields `xl:col-span-2`): frontend/src/pages/admin/UserForm.tsx (name + email), frontend/src/pages/admin/SourceForm.tsx (paired short fields such as host + port, database + user); lists and cards keep one column
- [X] T021 [US3] Check frontend/src/pages/admin/Users.tsx and Home.tsx grids still read well at 1536 px (cards `xl:grid-cols-3` where a grid already exists); no horizontal scroll at 320/375 px

---

## Phase 6: User Story 4 — The app uses the Ubuntu typeface (P3)

**Goal**: Ubuntu everywhere, served by the installation; secrets monospace.

**Independent test**: quickstart 9.

- [X] T022 [US4] frontend/src/index.css: six `@font-face` rules (family "Ubuntu", weights 400/500/700, style normal, `font-display: swap`, `src: url("./assets/fonts/ubuntu/ubuntu-<subset>-<weight>-normal.woff2") format("woff2")`, `unicode-range` of the latin and latin-ext subsets as published by Fontsource)
- [X] T023 [US4] frontend/tailwind.config.js: `fontFamily.sans` = `["Ubuntu", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "Noto Sans", "sans-serif"]`; add `fontFamily.mono` = `["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"]`
- [X] T024 [P] [US4] Secrets monospace via `font-mono`: `SecretBox` in frontend/src/components/CopyButton.tsx and the temporary-password input in UserForm.tsx and UserDetail.tsx (remove the inline `MONO` style objects)

---

## Phase 7: Polish & cross-cutting

- [X] T025 [P] Guard test frontend/tests/unit/no-modals.test.ts: scan frontend/src/**/*.{ts,tsx}; fail with file:line on `role="dialog"`, `aria-modal`, an import of `components/Modal`, or `fixed inset-0`; no allow-list
- [X] T026 New frontend/tests/e2e/views.spec.ts: for each call site in contracts/views.md the view is a region with its title, no element matches `[role=dialog], [aria-modal]`, and the page beside it is hidden; back button on the deactivate confirmation leaves the user active; after "Usuario creado." → back → forward → reload the password text is absent from the page; step-up from `/admin/tokens` keeps the typed name on cancel and creates exactly one token on confirm (count via `/api/admin/tokens` before/after); axe 0 serious/critical on the reset-password and recovery-codes views in light and dark; at viewport 1920 × 1080 `main` content width ≥ 0.85 × (1920 − 256) on `/admin/usuarios` and `/admin/usuarios/nuevo`; `document.documentElement.scrollWidth <= innerWidth` on those screens at the project widths; computed `font-family` of `body` starts with `Ubuntu` and a request to a `ubuntu-*.woff2` URL on the same origin succeeds
- [X] T027 [P] CHANGELOG.md Unreleased: confirmations and results are screens instead of pop-ups (back button cancels), wider pages on large screens, Ubuntu typeface (vendored, Ubuntu Font Licence)
- [X] T028 Run frontend suites (detached): `npm test && npm run build && npm run check:compat && npx playwright test`; then `/speckit-converge`

---

## Dependencies & execution order

- T001 → T022 (font files before `@font-face`).
- T002 → T003 → T004 → T005 → T006 → T007 → **blocks US1/US2**.
- US1 (T008–T013) and US2 (T014, T016, T017) after T006; T015 after T008–T014.
- US3 (T018–T021) and US4 (T022–T024) independent of US1/US2.
- T025 after T015; T026 after all stories; T028 last.

```text
T001 ───────────────────────────────→ T022 → T023 → T024
T002 → T003 → T004 → T005 → T006 → T007
                              ├→ T008 / T009 / T010 / T011 / T012 → T013
                              └→ T014 → T016 → T017
                 T008–T014 → T015 → T025
T018 → T019 → T020 → T021
all → T026 → T027 → T028
```

## Parallel examples

- US1: T010 (TwoFactorCard) ‖ T011 (Workspace) ‖ T012 (SourceForm) after T006.
- US3 ‖ US4 ‖ US1 — different files (except UserForm.tsx: T008 before T020 and T024).
- T025 ‖ T027.

## Implementation strategy

1. **MVP** = Setup + Foundational + US1: no admin pop-ups left (the owner's main complaint).
2. US2: step-up as a view — `Modal` deleted, guard on.
3. US3 + US4: width and font.
4. Views e2e, full frontend suites, converge.

---

## Phase 8: Convergence

- [X] T029 In frontend/src/pages/admin/SourceForm.tsx `remove()`: on failure (including a cancelled step-up) keep the "Eliminar fuente" view open and show the error inside it (as UserDetail.tsx and Workspace.tsx do), per spec Edge Cases / FR-004 / quickstart 5 (contradicts)
- [X] T030 E2E in frontend/tests/e2e/views.spec.ts: step-up started from inside a confirmation view (delete source with an expired step-up) — confirm → deleted once; cancel → back on the confirmation, source intact, per spec Edge Cases / SC-002 (missing)
- [X] T031 Remove the `mx-auto max-w-lg` page caps in frontend/src/pages/TwoFactorSetup.tsx (keep a readable max width only on the inner form card), per FR-007 / plan R6 (partial)
- [X] T032 E2E: Telegram-unlink and reactivate confirmation views (region, no dialog, page hidden, back cancels), per T026 / SC-001 (missing)
- [X] T033 E2E: axe in light and dark on deactivate/reactivate, Telegram unlink, two-step reset, disable two-step, delete source, rollback and "Usuario creado." views, per SC-006 / FR-006 (partial)
- [X] T034 E2E: extend the 1920 px width ≥ 85 % check to every administration screen and /perfil, per SC-003 (partial)
- [X] T035 Unit test in frontend/tests/unit/views.test.tsx: scroll position restored after a view closes, per FR-003 / plan R5 (partial)
