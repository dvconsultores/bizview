# Research: Views instead of modals, wider layout, Ubuntu font

Facts measured in the code on 2026-10-01.

## Current state

- `frontend/src/components/Modal.tsx`: fixed overlay (`fixed inset-0 z-50`, `bg-backdrop/50`),
  bottom sheet on phones, focus trap, Esc closes, body scroll locked. 10 uses:
  `ReauthDialog.tsx` (global step-up), `UserForm.tsx` (user created), `UserDetail.tsx` ×5 (reset
  password form + result via `ResetPasswordModal`, Telegram unlink, two-step reset,
  deactivate/reactivate), `TwoFactorCard.tsx` ×2 (recovery codes, disable),
  `Workspace.tsx` (rollback), `SourceForm.tsx` (delete).
- `ReauthProvider` sits in `App.tsx` above the router; the API client calls its `ask()` when a
  request answers `reauth_required`, then retries the request once (feature 004).
- Layout: `AppShell` `<main className="mx-auto max-w-6xl px-4 … sm:px-6">` beside a 16 rem
  (256 px) sidebar from `lg`; admin pages add `mx-auto max-w-3xl` (Profile, UserForm `max-w-2xl`,
  ReportView `max-w-5xl`). At 1920 px: area beside sidebar 1664 px, content 768 px ≈ 46 %.
- Font: Tailwind `fontFamily.sans` = system stack. CSP (deploy/caddy/Caddyfile): `font-src 'self'`.
- Weights used: `font-medium` (58), `font-semibold` (58), `font-bold` (13), `font-extrabold` (1),
  `font-normal` (1); no italics.
- E2E tests that address dialogs by role: `reporting.spec.ts`, `security.spec.ts`,
  `telegram.spec.ts`, `theme.spec.ts` (step-up), `flows.spec.ts` ("Usuario creado.").

## R1. What a "view" is

**Decision**: a `View` component with the same props as `Modal` (`open`, `title`, `onClose`,
`children`, `footer`), rendered through a portal into the nearest **view host**. While a view is
open the host hides its normal content with the `hidden` attribute (kept mounted) and shows the
view in normal document flow: a header row with a back button ("Volver") and the title as `<h1>`,
the body, and the footer actions in a row (stacked full-width on phones). The view is a
`<section aria-labelledby=…>` (role `region`), never `role="dialog"`, never `fixed`, no backdrop,
no scroll lock, no focus trap.

**Rationale**: replacing the page content in place satisfies "a screen that replaces the page
content" (spec FR-002) while keeping the page mounted, so typed text, filters and component state
survive cancel and back (FR-003, FR-004) with no serialisation. Keeping the `Modal` props makes
the migration of the 10 call sites mechanical.

**Alternatives considered**: a route per view (`/admin/usuarios/:id/restablecer`…): unmounts the
page, so form state and the step-up retry need storage; one-time secrets would need to travel
through router state, which survives reload in `history.state` (violates FR-005). Rejected.
Full-screen fixed panel: still an overlay. Rejected.

## R2. View hosts

**Decision**: two hosts. (1) `AppShell` wraps `<Outlet />` in a host, so views replace the page
area and keep the top bar, sidebar and bottom tabs. (2) `App` wraps the whole route tree in a root
host, used only when no shell host is mounted (sign-in, password change). A `ViewHostContext`
keeps a stack of mounted hosts; `View` portals into the innermost one. Only one view is shown at
a time; a second view opened while one is open (step-up from a confirmation view) stacks: the
newer one is shown, the older one is hidden but kept, and it reappears when the newer one closes.

**Rationale**: the step-up provider lives above the router, so its view must find the shell
host through context instead of the React tree.

## R3. Back button and history

**Decision**: when a view opens, `navigate(current path+search+hash, { state: { ...state,
view: <id> } })` pushes one same-URL entry. A location whose `state.view` no longer contains the
id closes the view through its `onClose` (back button = cancel). Closing from the UI while the
entry is on top calls `navigate(-1)`. After a reload or forward navigation an entry with a
`view` id but no open view is ignored (the page renders normally), so secrets, which live only in
component memory, are never shown again (FR-005).

**Rationale**: React Router v7 owns `history.state`; going through `navigate` keeps its index
consistent. Same path → the route element is not remounted.

## R4. Step-up as a view

**Decision**: `ReauthProvider` keeps its promise-based `ask()` and renders a `View` titled
"Confirma tu contraseña" with the password field focused, "Confirmar" and "Cancelar". Several
`ask()` calls while open share one pending promise (all resolve together). Back = cancel →
`resolve(false)`. On 423/429 the view closes with `false`, as today.

**Rationale**: the interrupted page stays mounted under the hidden host, so its form state is
intact and the client's single retry completes the action exactly once (FR-004, SC-002).

## R5. Focus, scroll, accessibility

**Decision**: on open, remember `document.activeElement` and `window.scrollY`, scroll to top,
focus the view's first field if `autoFocus` is set (step-up, reset password) otherwise its
`<h1 tabIndex={-1}>`. On close, restore scroll and focus the remembered element if it is still
connected. Esc closes as before (keyboard parity with the back button).

## R6. Width

**Decision**: `AppShell` main `max-w-screen-2xl` (1536 px) with `px-4 sm:px-6 lg:px-8`; remove the
per-page caps (`max-w-2xl`/`max-w-3xl`) from admin pages and Profile. Forms lay out fields in two
columns from `xl` where fields are short (name + email; host + port…), and keep long fields
full width. ReportView goes from `max-w-5xl` to `max-w-7xl` (1280 px) so charts and tables keep a
readable line length on very wide screens. Sign-in and password change are unchanged.
At 1920 px: 1536 − 64 = 1472 px of 1664 px ≈ 88 % (SC-003 ≥ 85 %).

**Alternatives**: no cap at all — on 2560 px screens lines and tables get too long. Rejected.

## R7. Ubuntu font

**Decision**: vendor the Ubuntu woff2 files (latin + latin-ext subsets, weights 400, 500, 700;
no italics — none are used) under `frontend/src/assets/fonts/ubuntu/` with the Ubuntu Font
Licence 1.0 text (`LICENCE.txt`), declared with `@font-face` in `src/index.css`
(`font-display: swap`, `unicode-range` per subset); Vite fingerprints and serves them from the
installation (CSP `font-src 'self'` holds, offline works). Tailwind `fontFamily.sans` =
`["Ubuntu", <current system stack>]`; a `fontFamily.mono` stack is used by `SecretBox` and the
temporary-password field instead of the inline style. `font-semibold` (600) resolves to the 700
face (CSS font matching), `font-extrabold` to 700. Files are obtained once from the
`@fontsource/ubuntu` package tarball (`npm pack`, not a dependency).

**Rationale**: no new runtime library (constitution V), works offline, licence shipped with the
files (FR-009). `swap` shows fallback text immediately (US4 AC2).

**Alternatives**: Google Fonts CDN — blocked by CSP and offline installs. `@fontsource/ubuntu` as a
dependency — adds a package for four files. Rejected.

## R8. Guard against regressions

**Decision**: unit test `tests/unit/no-modals.test.ts` scans `src/**/*.{ts,tsx}` and fails on
`role="dialog"`, `aria-modal`, a `Modal` import, or `fixed inset-0` (allow-list: none). The
`Modal` component is deleted.
