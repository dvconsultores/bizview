# Quickstart & Validation: Sign in with Telegram

**Feature**: [spec.md](./spec.md) | **Contracts**: [api](./contracts/api.md), [bot](./contracts/bot.md) |
**Data**: [data-model.md](./data-model.md)

## Set up a real bot (manual check only)

1. In Telegram, talk to @BotFather → `/newbot` → note the username (ends in `bot`) and token.
2. Super user → Seguridad → Telegram: bot name + token → confirm password → **Probar** →
   **Activar**.
3. The `worker` service must be running (it polls Telegram) and reach `https://api.telegram.org`.

## Run the suites (no live Telegram)

```bash
cd backend && uv run alembic upgrade head && uv run pytest tests/test_telegram.py
cd frontend && npm test && npm run build && npm run e2e -- telegram
```
Backend tests use a fake Telegram transport; e2e feeds bot updates through the test hook
(`BIZVIEW_TEST_HOOKS=1`, set only by `tests/e2e/backend.sh`). Run backend and e2e suites one
after the other (they share the database; integration advisory locks are database-wide).

## Validation scenarios

| # | Scenario | Expected | Covers |
|---|---|---|---|
| 1 | Fresh installation: sign-in screen, profile, `/api/config` | no Telegram option; `telegram_sign_in=false`; start → 404 | US1 AS1, FR-001 |
| 2 | Save bot without step-up / as admin (not super user) | 403 / 403 | FR-002 |
| 3 | Save token, read `GET /api/admin/telegram`, audit, logs | only `token_configured`; marker token absent everywhere | FR-003, SC-004 |
| 4 | Check with fake 401 / timeout / wrong name / webhook set | `invalid_credential` / `timeout` / `name_mismatch` / `webhook_conflict` | US1 AS3 |
| 5 | Enable before a successful check; after changing the token | 409 `telegram_check_required`; feature turned off | FR-004 |
| 6 | Link: step-up → `/start` → Confirmar | profile shows name; audit `telegram_linked` | US2 AS1, FR-005 |
| 7 | Link a Telegram id already linked to another user | refused `already_linked`, no user named | FR-006 |
| 8 | Unlink own (step-up) / admin removes another user's link | removed, audited with correct actor | FR-007 |
| 9 | Sign in: start → `/start` → correct code → status | `signed_in`, session works, audit `login_ok` method telegram | US3 AS1, FR-008 |
| 10 | Unlinked Telegram user / wrong code / Cancelar | refused with reason; failure counted for the address | US3 AS2, FR-009 |
| 11 | Deactivated / locked linked user | same refusals as password sign-in | US3 AS3 |
| 12 | `internet` profile, admin with two-step | `mfa_required`; code completes sign-in; without enrolment → setup screen | US3 AS4, SC-003 |
| 13 | Temporary-password user signs in with Telegram | sent to change password | US3 AS5 |
| 14 | Replay `/start` token; answer callback from another Telegram id; status after consumption; wait > 5 min | refused / ignored / expired / expired | US3 AS6, FR-010, SC-002 |
| 15 | Status polled from another browser (no `bv_tg` cookie) | `expired` (cannot collect the session) | R3 binding |
| 16 | 20 Telegram failures from one address, then password sign-in | address limited (shared counter) | FR-009 |
| 17 | Telegram unreachable (fake network error) | sign-in panel shows "Telegram no está disponible…"; password sign-in unaffected | FR-013, SC-006 |
| 18 | Screens at 375 px, light and dark, axe | no violations; 44 px targets | FR-015 |
| 19 | Real bot on a phone (manual) | sign-in < 20 s without typing | SC-001 |
