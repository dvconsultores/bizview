# Phase 0 — Research: Google branding and role mapping

**Feature**: 054-google-signin-rbac · **Date**: 2026-11-04

## What exists today

| Piece | Path | State |
| --- | --- | --- |
| Sign-in screen | `frontend/src/pages/SignIn.tsx` | outline `Button` for Google (text only), Telegram with `Send` icon, both rendered only when the provider is on; `googleErrorMessage()` maps codes to specific sentences |
| Google exchange | `backend/app/auth/google.py` | authorization code + PKCE, claims validated, `Identity(sub, email, hd)` |
| Callback | `backend/app/api/oauth.py` | `_check_domain` (env list) → link by subject → user by email → link; otherwise `unknown_identity`; audits `google_sign_in`, `google_sign_in_refused`, `google_linked` |
| Settings precedents | `app/api/appearance.py`, `app/api/telegram.py`, models `AppearanceSettings`, `TelegramSettings` | singleton row + `GET/PUT` + audit; the security page mounts `TelegramAdminCard` |
| Users | `app/models.py#AppUser`, `app/services/users.py` | `password_hash` NOT NULL; `create()` needs a temporary password; `reset_password()`; `role ∈ (admin,user)`; superuser is a single admin row with `is_superuser` |
| Access | `DashboardAccess`, `app/api/admin.py#set_grants` | explicit rows per user and dashboard; admins see everything by role |
| Audit | `AUDIT_KINDS` + a check constraint recreated per migration | adding a kind is a migration + the tuple |
| Test hooks | `app/api/testhooks.py`, mounted with `BIZVIEW_TEST_HOOKS=1` | settings override, fake mail, fake Telegram transport |

## Decisions researched

### 1. The brand mark

Google's button guidelines give two colour variants: white surface with a `#747775` outline and the
`#1F1F1F` label for light, and `#131314` surface with a `#8E918F` outline and a white label for dark,
with the mark kept in its four brand colours (`#4285F4`, `#34A853`, `#FBBC05`, `#EA4335`) in both.
The mark is drawn as one inline `<svg>` with four `<path>`s; the component picks the variant from the
resolved theme (`useTheme().resolved`), so no CSS media query is needed inside a themed page.

`no-raw-colors.test.ts` refuses colour literals except per file; the logo component joins
`LITERALS_BY_FILE` with the reason ("Google's mark, never recoloured"), which is the gate's own
mechanism for a justified exception.

### 2. Where the password assumption lives

- `AppUser.password_hash` is `NOT NULL` → migration makes it nullable; the model's type becomes
  `str | None`.
- `api/auth.py#login` calls `passwords.verify_password(user.password_hash, ...)`. `verify_password`
  expects a hash string; the login path will refuse an account with no hash **before** verifying,
  through the same `INVALID` + throttle + audit path as a wrong password (never a different message,
  never a different timing shape).
- `services/users.reset_password()` writes a hash, so an admin can give the account a password; the
  `auth_provider` stays `google` (it records how the account was created, not what it may use).
- `must_change_password=false` for provisioned accounts: there is nothing to change until a password
  exists, and `finish_sign_in` would otherwise route them to `/cambiar-clave`.

### 3. Policy storage

Singleton `google_settings` mirrors `appearance_settings`: `id = 1`, check constraint, `updated_by`.
`allowed_domains` is `jsonb` (a list) rather than text so the normalisation is explicit and the card
reads exactly what the callback reads. `default_access` is one JSON object shared with the rules:

```json
{"mode": "list", "codes": ["ventas", "finanzas"]}
```

`google_rule.position` is a plain integer kept contiguous by the service (insert at index, move,
compact on delete) — the same approach the workspace uses for ordering, without a float rank.

### 4. The callback's new order

```
cookie+state?  (unchanged)
exchange → Identity(sub, email, hd, name)
settings = policy.settings(db)            # row or env seed
domain allowed?                           # empty list = any domain
link by sub            → existing user
by email               → link + existing user
auto_provision?        → create user (rule outcome | defaults) + grants
else                   → no_user
inactive/locked?       → refuse (unchanged)
rules for existing users when the toggle is on and the outcome differs
finish_sign_in()       → unchanged, second factor intact
```

Every refusal raises `GoogleError(code)`; the page maps **every** code except `denied` to the generic
sentence, and the audit records the code.

### 5. Audit additions

`google_settings_updated`, `google_rule_created`, `google_rule_updated`, `google_rule_deleted`,
`google_user_provisioned`, `google_rule_applied`. Existing kinds keep their meaning;
`google_sign_in_refused.detail.reason` gains `domain_not_allowed`, `no_user`, `provisioned`,
`rule:<id>`. `audit.record` refuses secret-like keys (`password`, `token`, …) — rule values are
emails and domains, never secrets.

### 6. The e2e Google

The suite has no network to Google. `testhooks` gains `POST /api/testing/google-identity {email,
name?, sub?}` that installs a module-level override used by `google.exchange` (only when
`BIZVIEW_TEST_HOOKS=1`), so the browser can complete `/api/auth/google/callback?code=fake&state=…`
with the state cookie the start endpoint set. The flow stays the real one — only the token exchange
is replaced.

## Open questions

None; the ambiguities are recorded in the spec's *Decisiones tomadas*.
