# Quickstart: validate feature 009

Prerequisites: the app running (`python starter.py` or the e2e servers), a super user, a browser
with devtools. Automated equivalents: `cd frontend && npm test && npx playwright test`.

1. **No overlays** — `/admin/usuarios/nuevo`, create a user → "Usuario creado." replaces the page
   (sidebar and top bar still visible, nothing dimmed); copy the password; "Ver usuario" opens the
   detail. Repeat "Crear otro" → empty form.
2. **Back = cancel** — on a user's detail open "Desactivar", press the browser back button → back
   on the detail, user still active. Same with the phone back gesture at 375 px.
3. **Secret not reachable** — after step 1, press back then forward, and reload → the password is
   not shown anywhere.
4. **Step-up keeps work** — `/admin/tokens`, type a name, "Crear token" with an expired step-up →
   "Confirma tu contraseña" view; "Cancelar" → name still typed, no token; again, confirm →
   token created once with that name.
5. **Step-up from a confirmation** — source detail → "Eliminar" → (step-up) → confirm → source
   deleted; repeat cancelling the step-up → back on the delete confirmation.
6. **All views** — open each row of contracts/views.md "Call sites" in light and dark; axe has 0
   serious/critical violations; focus lands on the title (or the password field) and returns to
   the opening button on close.
7. **Width** — 1920 × 1080: `/admin/usuarios`, `/admin/auditoria`, `/admin/seguridad`,
   `/admin/usuarios/nuevo`, `/perfil` → content width ≥ 85 % of the area beside the sidebar
   (devtools: `main > *` width ÷ (viewport − 256)). 1366 × 768: no regressions.
8. **Phones** — 320 and 375 px: every screen and view, `document.documentElement.scrollWidth <=
   innerWidth`.
9. **Font** — devtools → Network: `ubuntu-*.woff2` served from the installation; computed
   `font-family` of body text starts with Ubuntu and "Rendered fonts" shows Ubuntu; block the
   font URL → text still visible in the system font. Temporary password and recovery codes render
   monospace.
10. **Guard** — `npm test` includes `no-modals.test.ts`; adding `role="dialog"` anywhere fails it.
