# Implementation Plan: Sign in with Telegram

**Branch**: `007-telegram-sign-in` | **Date**: 2026-09-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-telegram-sign-in/spec.md`

## Summary

Optional, per-installation "Ingresar con Telegram". Each installation registers its own bot
(super user: name + encrypted, write-only token, check, enable). Sign-in uses a **bot
confirmation flow**: the API creates a single-use, 5-minute request bound to the browser by an
HttpOnly cookie and returns a deep link (`t.me/<bot>?start=<token>`, QR on desktop) plus a
2-digit match code; the user taps *Start* in Telegram and picks the matching code; the browser
polls and receives a normal session through the same rules as password sign-in (throttle, lock,
inactive, two-step for administrators, temporary password). Users link/unlink their own Telegram
from the profile (step-up); administrators can remove links. Bot updates are read by a long-poll
thread in the existing worker (outbound HTTPS only), so CSP and private installations are
unaffected (research R1–R9).

## Technical Context

**Language/Version**: Python 3.12+ (backend, worker), TypeScript 5.9 (frontend)

**Primary Dependencies**: existing only — FastAPI, SQLAlchemy, Alembic, httpx (Telegram Bot API
via `netguard.guarded_client`), cryptography (token at rest), segno (QR), APScheduler worker
loop; React 19, Tailwind (feature-006 tokens), Lucide

**Storage**: `public` — new tables `telegram_settings`, `telegram_link`, `telegram_request`;
extended `audit_event` kinds (migration `0006_telegram`)

**Testing**: pytest on `DATABASE_URL_BI` (`app_test_*`) with a fake Telegram transport
(`httpx.MockTransport`): settings/check/enable, link/unlink, sign-in state machine, replay,
binding, throttling, two-step, secret leak marker. Vitest for the sign-in panel polling logic.
Playwright (3 engines × 320/375): sign-in and link flows driven through the test hook, axe in
light and dark. No live Telegram calls (opt-in manual check only).

**Target Platform**: existing installations (caddy, backend, worker); outbound HTTPS to
`api.telegram.org` when enabled

**Project Type**: web application + worker

**Performance Goals**: approval visible in the browser ≤ 3 s after the tap (2 s polling + update
latency); sign-in < 20 s end to end on a phone (SC-001)

**Constraints**: CSP unchanged (`script-src 'self'`); token write-only and encrypted; no new
libraries; requests single-use ≤ 5 min; works on `private` (IP) and `internet` profiles

**Scale/Scope**: tens to hundreds of users per installation; 3 tables, ~10 endpoints, 1 worker
thread, 4 screens touched

## Constitution Check

| Rule | Status | Evidence |
|---|---|---|
| I. Mobile-first, Tailwind | PASS | "Abrir Telegram" button first on phones, QR only ≥ 640 px; 44 px targets; e2e 320/375 |
| II–III. ETL / external origin | N/A | no data path change |
| IV. Folders | PASS | `backend/app/telegram/` (bot client, poller handler, service), API routes in `backend/app/api/`, UI in `frontend/` |
| V. Fixed stack | PASS | no new library; Telegram is an optional external service, like AI providers; worker hosts the poller (no broker) |
| VII. One product, many installations | PASS | bot per installation, configured at runtime; no customer data in repo |
| VIII. AI optional/private | N/A | — |
| Constraint: credentials encrypted, write-only | PASS | token AES-256-GCM with the keyring, never returned/logged; included in key rotation |
| Constraint: security profiles | PASS | two-step for admins on `internet` unchanged; Telegram never satisfies it; throttling shared |
| Constraint: JSON API, CSRF | PASS | all JSON; `X-Requested-With` + Origin check; `bv_tg` SameSite=Strict |
| Constraint: Alembic | PASS | `0006_telegram` |
| License footer | PASS | screens keep `SourceFooter` |

Post-design re-check: unchanged — all PASS; no Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/007-telegram-sign-in/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md     # HTTP endpoints
│   └── bot.md     # Telegram conversation and polling
└── tasks.md       # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0006_telegram.py
├── app/models.py                         TelegramSettings, TelegramLink, TelegramRequest, audit kinds
├── app/telegram/
│   ├── client.py                         Bot API calls (getMe, getWebhookInfo, getUpdates,
│   │                                     sendMessage, editMessageText, answerCallbackQuery), redaction
│   ├── service.py                        settings, check, enable, requests (create/consume/expire),
│   │                                     link/unlink, purge
│   ├── handler.py                        handle_update(db, update): /start + callbacks (contracts/bot.md)
│   └── poller.py                         TelegramPoller thread (long poll, offset, backoff)
├── app/api/telegram.py                   /api/auth/telegram/*, /api/me/telegram, /api/admin/telegram*
├── app/api/auth.py                       shared sign-in rules helper (password + Telegram)
├── app/api/admin.py                      DELETE /api/admin/users/{id}/telegram; telegram_linked in user_json
├── app/api/health.py                     /api/config adds telegram_sign_in, telegram_bot
├── app/security/crypto.py                rotate + existence check include the bot token
├── app/worker.py                         start/stop TelegramPoller; purge old requests
└── tests/test_telegram.py, tests/fake_telegram.py

frontend/src/
├── pages/SignIn.tsx                      "Ingresar con Telegram" + TelegramSignInPanel
├── components/TelegramSignInPanel.tsx    code, deep link, QR, countdown, polling
├── components/TelegramCard.tsx           profile link/unlink
├── pages/Profile.tsx, pages/admin/UserDetail.tsx, pages/admin/Security.tsx
├── api/types.ts, i18n/es.ts              types and Spanish strings
└── tests/unit/telegram.test.ts, tests/e2e/telegram.spec.ts
```

**Structure Decision**: a `backend/app/telegram/` package keeps the bot client, conversation
handler and poller together (constitution IV: a developer finds the Telegram code in one place);
the worker imports the poller like it imports the integration runner.

## Implementation notes for tasks

1. Migration + models + crypto rotation first (blocking).
2. `client.py` + fake transport, then `service.py` (settings/check/enable) → US1.
3. `handler.py` + `poller.py` + request lifecycle → shared by US2 and US3.
4. Link/unlink endpoints and profile card → US2.
5. Extract the shared sign-in rules from `api/auth.py`, then `/api/auth/telegram/*` and the
   sign-in panel → US3.
6. Test hook (env-gated), e2e, axe, secret-leak marker test.

## Complexity Tracking

No constitution violations; nothing to justify.
