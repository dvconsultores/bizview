# Quickstart — 054-google-signin-rbac

**Feature**: Google button branding and role mapping · **Date**: 2026-11-04

## Automated gates

```bash
cd backend
uv run pytest tests/test_google_rbac.py tests/test_google_sign_in.py tests/test_auth.py \
              tests/test_migrations.py -q

cd ../frontend
npx tsc -b
npx vitest run                    # includes the colour/i18n gates and the button tests
npm run build
```

## Manual checks

1. **The button.** With `GOOGLE_AUTH_ENABLED=true`, open `/ingresar` in light mode: the Google
   control shows the four-colour G on a white surface with Google's outline; switch the device to
   dark: the dark variant. The Telegram button has the same height, its icon at the left. Disable
   Google: the control disappears and the divider still looks right.
2. **Domains.** Administration → Seguridad → **Ingreso con Google**: the domains field shows
   `GOOGLE_ALLOWED_DOMAINS` the first time. Save `example.org`, then sign in with an account on
   `example.com` (refused, generic message) and one on `example.org` (accepted). The audit shows one
   `google_settings_updated` with both values.
3. **Alta automática.** Turn it on with role **usuario** and access **ventas**. A new Google account
   on an allowed domain signs in: the user list gains exactly one person with provider Google, the
   dashboard **ventas** is granted, and a second sign-in creates nothing. The password form refuses
   that account until an admin sets a password.
4. **Rules.** Add `dominio == example.org → admin, todos los tableros públicos`, then
   `email en [cfo@example.org] → usuario, ninguno`; move the email rule above the domain rule. The
   first sign-in of a new account gets the email rule's outcome; swap the order and a new account
   gets admin. Remove the rules when done.
5. **Existing users.** With the toggle off, a rule matching an existing user changes nothing. Turn it
   on and sign in again: the role changes and the audit has one `google_rule_applied` naming the rule.
6. **Superusers.** A rule whose email matches the superuser changes nothing, and the API refuses a rule
   with role `superusuarios`/any value outside `usuario|admin`.
7. **Quiet failures.** An unknown domain, an unknown identity and an inactive account all show
   **No se pudo iniciar sesión con Google**; cancelling at Google says the sign-in was cancelled.

## Test hook (e2e)

With `BIZVIEW_TEST_HOOKS=1`:

```bash
curl -X POST localhost:8001/api/testing/google-identity \
     -H 'content-type: application/json' \
     -d '{"email": "nueva@example.org", "name": "Nueva Persona"}'
```

then complete `/api/auth/google/callback?code=fake&state=<state>` in the browser that started the
flow. The state cookie is the real one; only the token exchange is faked.
