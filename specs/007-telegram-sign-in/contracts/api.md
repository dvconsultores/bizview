# API contract: Sign in with Telegram

Conventions as features 002–006: JSON, same-origin session cookie, mutating requests need
`X-Requested-With: fetch` (CSRF), common error body, Spanish messages.

## Public config

`GET /api/config` adds `"telegram_sign_in": bool` (enabled and last check OK) and
`"telegram_bot": string | null` (username, only when enabled).

## Sign-in (no session)

### `POST /api/auth/telegram/start`

Throttled like `/api/auth/login` (429 when the address is limited). 404 `not_found` when the
feature is off; 503 `telegram_unavailable` when the worker has not reached Telegram in the last
2 minutes (FR-013, `telegram_settings.last_poll_ok_at`).

200:
```json
{ "match_code": 47, "deep_link": "https://t.me/MiEmpresaBot?start=<token>",
  "qr_svg": "data:image/svg+xml;base64,…", "expires_at": "2026-09-30T18:05:00Z" }
```
Sets `bv_tg` cookie (HttpOnly, SameSite=Strict, Path=/api/auth/telegram, Max-Age 300,
Secure per `COOKIE_SECURE`). A new start replaces the previous request of this browser.

### `GET /api/auth/telegram/status`

Reads the request from the `bv_tg` cookie. Throttle-checked.

| Request state | Response |
|---|---|
| pending / started | 200 `{ "status": "pending" }` |
| approved, user without two-step | 200 `{ "status": "signed_in", "user": {…user_json} }` + session cookie; request → consumed; `bv_tg` cleared; audit `login_ok` (method telegram) |
| approved, two-step enabled | 200 `{ "status": "mfa_required" }` + `mfa_pending` session (finish with `POST /api/auth/mfa`) |
| refused | 200 `{ "status": "refused", "reason": "not_linked" \| "wrong_code" \| "cancelled", "message": "…" }` — reported (and counted) once |
| approved, user inactive / locked | 401 `invalid_credentials` / 423 `locked` — the same errors as password sign-in |
| expired / no cookie / unknown | 200 `{ "status": "expired" }` |

Inactive and locked accounts are only detected when the session would be issued, so they answer
with the password sign-in errors instead of a `refused` status.

## Profile (session required)

### `GET /api/me/telegram`
200 `{ "available": bool, "linked": bool, "username": str|null, "display_name": str|null,
"linked_at": iso|null, "pending": bool }`.

### `POST /api/me/telegram/link` — step-up (`recent_reauth`)
200 `{ "deep_link": "…", "qr_svg": "…", "expires_at": "…" }`. 503 `telegram_unavailable` as for
sign-in. 409 `telegram_already_linked_self`
if the user already has a link. Bot then asks Confirmar/Cancelar; on confirm the link is created
(409-equivalent refusal `already_linked` when that Telegram account belongs to another user,
without naming it).

### `DELETE /api/me/telegram` — step-up
204; audit `telegram_unlinked` (actor = user).

## Administration

### `DELETE /api/admin/users/{id}/telegram` — admin who `can_manage`, step-up
204; audit `telegram_unlinked` (actor = admin, target = user). 404 when not linked.
`GET /api/admin/users/{id}` adds `"telegram_linked": bool` next to `user` and `dashboards`.

### Super user: `GET /api/admin/telegram`
200 `{ "enabled", "bot_username", "token_configured", "token_changed_at", "last_check_at",
"last_check_ok", "last_check": {"reason"?, "bot_name"?} }` — never the token.

### `PUT /api/admin/telegram` — super user, step-up
Body `{ "bot_username": str, "token"?: str }` (`token` omitted = keep; `""` = clear).
Changing either resets the check and sets `enabled=false`. Audit `telegram_settings_updated`
(detail: which fields changed, never values).

### `POST /api/admin/telegram/check` — super user, step-up
200 `{ "ok": bool, "reason"?: "invalid_credential" | "unreachable" | "timeout" | "name_mismatch" |
"webhook_conflict", "bot_name"?: str }`; audit `telegram_checked`.

### `POST /api/admin/telegram/enabled` — super user, step-up
Body `{ "enabled": bool }`. 409 `telegram_check_required` when enabling without a successful
check of the current settings. Audit `telegram_enabled` / `telegram_disabled`.

## Test hooks (tests only)

Mounted only when `BIZVIEW_TEST_HOOKS=1` (set by `frontend/tests/e2e/backend.sh`); never in
images; no network (a local transport records what the bot would send).

| Route | Purpose |
|---|---|
| `POST /api/test/telegram/update` | feed a Telegram `Update` JSON to the real conversation handler |
| `GET /api/test/telegram/sent` | last 10 messages the bot would have sent (to read button data) |
| `POST /api/test/telegram/check-ok` | mark the bot check OK and Telegram reachable (no real bot in e2e) |
| `POST /api/test/telegram/reset` | remove links and requests, turn the feature off |
