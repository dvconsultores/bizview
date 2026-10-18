# Research: Sign in with Telegram

**Feature**: [spec.md](./spec.md) · **Date**: 2026-09-30

Starting point: password sign-in in `backend/app/api/auth.py` (`login` → `_complete_login`,
`mfa_pending` sessions for two-step sign-in), per-address throttling (`app/services/throttle`),
per-user lock (`users.register_failure`), audit (`app/services/audit`), AES-256-GCM secrets with
associated data (`app/security/crypto`), outbound HTTP through `netguard.guarded_client`,
QR codes with `segno` (`mfa.qr_svg_data_uri`), and the `worker` service (APScheduler loop,
`python -m app.worker`). Caddy CSP: `script-src 'self'; connect-src 'self'; frame-ancestors 'none'`.

## R1. Mechanism: bot confirmation (deep link) — not the Login Widget

- **Decision**: **bot confirmation flow**. The browser asks the API for a sign-in request; the
  API returns a one-time deep link `https://t.me/<bot>?start=<token>` (button on phones, QR on
  desktop) and a 2-digit **match code** shown on screen. The user opens Telegram, taps *Start*;
  the bot replies with the request details and three code buttons; the user taps the code shown
  in the browser. The browser polls the request status and receives the session when approved.
- **Rationale**:
  - CSP and the frontend stay first-party (`script-src 'self'`, no Telegram iframe/script).
  - Works on installations reached by IP or private names (`private` profile): the Login Widget
    only works on the single domain registered for the bot with BotFather.
  - The approval is bound to one request created by one browser (FR-010), single-use, expiring.
  - The match code defeats "forwarded link" login CSRF: an attacker who starts a request and
    sends the link to a victim cannot make the victim pick a code only the attacker's screen
    shows (an unprompted victim sees three codes and no reason to pick one; a wrong pick cancels).
- **Alternatives considered**:
  - Telegram Login Widget (HMAC-signed data with `SHA256(bot_token)`): no server→Telegram traffic
    needed, but requires `script-src https://telegram.org` + `frame-src https://oauth.telegram.org`,
    one registered domain per bot, and gives no request binding (replay only bounded by
    `auth_date`).
  - Telegram OpenID/OAuth: not available for arbitrary bots at the time of writing.

## R2. Receiving bot updates: long polling from the worker

- **Decision**: a `TelegramPoller` thread in the existing **worker** service calls
  `getUpdates` (long poll, `timeout=25`, `allowed_updates=["message","callback_query"]`) with
  the stored `update_offset`, only while Telegram sign-in is enabled and a token is configured.
  Outbound calls use `netguard.guarded_client` to `https://api.telegram.org` (TLS verified).
- **Rationale**: works behind NAT/firewalls with only outbound HTTPS — no public webhook URL,
  so the same design serves `private` and `internet` installations. One bot per installation
  (spec assumption) means one consumer per bot, which `getUpdates` requires. The offset is
  persisted so a restart never reprocesses an update.
- **Alternatives considered**: webhook (needs a public HTTPS endpoint and a secret path; not
  available on private installations); polling from the API process (several Uvicorn workers
  would compete for updates → `409 Conflict`).
- Bot check also calls `getWebhookInfo`: a bot with a webhook set cannot be polled →
  reason `webhook_conflict`.

## R3. Request lifecycle and binding

- **Decision**: table `telegram_request` (data-model.md). Three secrets per request:
  1. **start token** (32 random bytes, base64url, 43 chars — fits Telegram's 64-char
     `[A-Za-z0-9_-]` start parameter); only its SHA-256 is stored.
  2. **browser secret** in an HttpOnly, SameSite=Strict cookie `bv_tg` (sign-in only); the
     status endpoint finds the request by this cookie's hash, so whoever has the link cannot
     collect the session.
  3. **public id** (16 base64url chars) used in callback data `c:<public_id>:<code>`
     (≤ 64 bytes).
  States: `pending` → `started` (bot saw `/start`, Telegram user bound) → `approved` |
  `refused` → `consumed` (session issued / link created); any non-final state → `expired` after
  5 minutes (FR-010). Only the Telegram user that sent `/start` may answer the buttons.
- **Rationale**: single-use and request-bound by construction; nothing secret is stored in
  clear; the session cookie is issued only to the browser that created the request.

## R4. Linking

- **Decision**: link requests are created by a signed-in user after step-up (`recent_reauth`,
  FR-005); the bot shows "Vincular tu Telegram a <correo enmascarado> en <producto>" with
  **Confirmar / Cancelar** (no match code: the request is already tied to an authenticated
  browser session, and the worst forwarded-link case links the victim's Telegram to the
  attacker's own account, which grants the victim, not the attacker, access). The profile
  polls `GET /api/me/telegram` until linked. Uniqueness of `telegram_link.telegram_id` enforces
  FR-006; a conflict returns the generic `telegram_already_linked`.
- Unlinking: own (`recent_reauth`) or by an administrator who `can_manage` the user (step-up),
  both audited (FR-007).

## R5. Sign-in rules reuse (FR-009)

- **Decision**: the approved request goes through the same checks as password sign-in, in a
  shared helper extracted from `api/auth.py`: throttle check (start and status), inactive →
  `invalid_credentials`-equivalent refusal, locked → `locked_error`, then
  `mfa.enabled(user)` → `mfa_pending` session + `{"mfa_required": true}` (the existing
  `/api/auth/mfa` step finishes it), else `_complete_login`. Temporary password and forced
  two-step enrolment are already enforced after sign-in by `RequireAuth` (frontend) and
  `current_auth` (API). Failures (`not_linked`, `wrong_code`, `inactive`, `locked`) call
  `throttle.register_failure` (count with password failures) and audit `login_failed` with
  `detail.method = "telegram"`. Telegram never sets `reauth_at` (FR-012).

## R6. Bot credential and settings

- **Decision**: singleton table `telegram_settings` (id = 1) with the token encrypted by the
  existing keyring (`crypto`, AES-256-GCM, associated data `bizview:v1:telegram_settings:token`, key id stored for
  rotation; `crypto.rotate` extended to re-encrypt it). Write-only: the API returns
  `token_configured` and `token_changed_at` only (FR-003). Enabling requires
  `last_check_ok = true` for the current token (FR-004); changing the token resets the check
  and disables the feature until checked again.
- Bot check (`getMe` + `getWebhookInfo`): reasons `invalid_credential` (401/404), `unreachable`,
  `timeout`, `name_mismatch` (configured name ≠ `getMe.username`, case-insensitive),
  `webhook_conflict`. The token never appears in errors: `redact()` like the AI provider.

- Reachability (FR-013): the poller records `last_poll_ok_at` after every successful
  `getUpdates`; sign-in and link requests answer 503 `telegram_unavailable` when it is older than
  2 minutes, so users are sent back to email and password instead of waiting for an approval that
  cannot arrive. Added by convergence (T033).

## R7. Telegram messages and privacy

- **Decision**: messages are in Spanish and contain only: product/organization name, purpose,
  approximate request info (browser family from User-Agent, IP address), expiry time, buttons.
  Stored per user: Telegram id, username, display name, link date (FR-014). Message texts and
  update payloads are never logged or audited (FR-011). After approval/refusal/expiry the bot
  edits its message to the final state and removes the buttons.

## R8. Frontend

- **Decision**: `/api/config` gains `telegram_sign_in: boolean` and `telegram_bot: string|null`.
  Sign-in screen: secondary button "Ingresar con Telegram" → panel with the match code (large),
  "Abrir Telegram" link button (phones) and QR (≥ 640 px, `segno` SVG data URI from the API),
  countdown, polling `GET /api/auth/telegram/status` every 2 s (stop on final state or after
  5 min). Profile: "Telegram" card (link/unlink, ReauthDialog). User detail (admin): "Quitar
  vínculo de Telegram". Security page (super user): Telegram section (bot name, token field,
  check, enable switch). All with feature-006 tokens, 44 px targets, Spanish.

## R9. Testing without Telegram

- **Decision**: a `FakeTelegram` transport (`httpx.MockTransport`) for backend tests and a
  test-only hook to feed updates into the poller's handler; no live Telegram calls in the suite
  (same rule as AI: live tests opt-in). E2E drives the flow by calling the update handler through
  a test-only endpoint enabled only when `BIZVIEW_TEST_HOOKS=1` (never in images).

## Supporting libraries

None added: `httpx` (bot API), `segno` (QR), `cryptography` (token), APScheduler worker loop —
all already in the stack.
