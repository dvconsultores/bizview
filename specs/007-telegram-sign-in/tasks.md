---
description: "Task list for feature 007 — Sign in with Telegram"
---

# Tasks: Sign in with Telegram

**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md),
[contracts/bot.md](./contracts/bot.md), [quickstart.md](./quickstart.md)

**Tests**: included — the spec's success criteria (SC-002 refusals audited, SC-003 two-step,
SC-004 secret never shown) and the constitution's security constraints require them. No live
Telegram calls: a fake transport and an env-gated test hook (research R9).

**Roles**: DeepSeek writes each task's code from a brief; Claude audits, runs tests, converges.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Create package `backend/app/telegram/__init__.py` (docstring: bot client, conversation handler, poller, service for feature 007) and test helper module `backend/tests/fake_telegram.py` skeleton (see T006)

---

## Phase 2: Foundational (blocking)

- [X] T002 Migration `backend/alembic/versions/0006_telegram.py` (revision `0006_telegram`, down_revision `0005_user_theme`): tables `telegram_settings`, `telegram_link`, `telegram_request` exactly as data-model.md — `telegram_settings.id` smallint PK CHECK `id = 1`; `enabled` boolean NOT NULL default false; `bot_username` text NULL CHECK `bot_username ~ '^[A-Za-z][A-Za-z0-9_]{1,28}[Bb][Oo][Tt]$'`; `token_ct` bytea / `token_key_id` text with CHECK `(token_ct IS NULL) = (token_key_id IS NULL)`; `token_changed_at`, `last_check_at` timestamptz; `last_check_ok` boolean NULL; `last_check` jsonb NULL; `update_offset` bigint NOT NULL default 0; `updated_at` timestamptz default now(); `updated_by` FK app_user. `telegram_link`: `user_id` bigint PK FK app_user ON DELETE CASCADE; `telegram_id` bigint NOT NULL UNIQUE; `username` text NULL CHECK char_length ≤ 64; `display_name` text NOT NULL CHECK char_length ≤ 128; `linked_at` timestamptz NOT NULL default now(); `linked_by` FK app_user. `telegram_request`: `id` text PK (16 chars); `purpose` CHECK IN ('sign_in','link'); `token_hash` bytea NOT NULL UNIQUE; `browser_hash` bytea NULL UNIQUE; `user_id` FK app_user ON DELETE CASCADE NULL; `telegram_id` bigint NULL; `match_code` smallint NULL CHECK 10–99; `status` CHECK IN ('pending','started','approved','refused','expired','consumed'); `reason` text NULL; `chat_id`, `message_id` bigint NULL; `ip` inet NULL; `user_agent` text NULL; `created_at` default now(); `expires_at` NOT NULL; index `(status, expires_at)`; CHECK `purpose <> 'link' OR user_id IS NOT NULL`; CHECK `purpose <> 'sign_in' OR (browser_hash IS NOT NULL AND match_code IS NOT NULL)`. Extend the audit kind CHECK (same pattern as 0004: drop + recreate `ck_audit_event_ck_audit_event_kind` via `op.f`) with `telegram_settings_updated`, `telegram_checked`, `telegram_enabled`, `telegram_disabled`, `telegram_linked`, `telegram_unlinked`; downgrade reverses all
- [X] T003 Models in `backend/app/models.py`: `TelegramSettings`, `TelegramLink`, `TelegramRequest` mirroring T002 (constraint names via the naming convention so `test_models_match_migrations` passes), constants `TELEGRAM_PURPOSES`, `TELEGRAM_STATUSES`; add the six kinds to `AUDIT_KINDS`
- [X] T004 `backend/app/security/crypto.py`: `TELEGRAM_AAD = "telegram:bot"`; `_encrypted_data_exists` also checks `TelegramSettings.token_ct`; `rotate` re-encrypts it (count key `telegram_settings`)
- [X] T005 Bot API client `backend/app/telegram/client.py`: class `BotClient(token, settings, transport=None)` using `netguard.guarded_client(policy=policy_from_settings(settings), timeout=…)` (or the injected `httpx` transport for tests), base `https://api.telegram.org/bot<token>/`; methods `get_me()`, `get_webhook_info()`, `get_updates(offset, timeout=25)`, `send_message(chat_id, text, buttons=None)` (inline keyboard rows of `(text, callback_data)`), `edit_message(chat_id, message_id, text)` (removes keyboard), `answer_callback(callback_id, text=None)`; error class `TelegramError(code)` with codes `invalid_credential` (401/404), `webhook_conflict` (409), `timeout`, `unreachable`, `telegram_error`; every error string passed through `redact(…, token)` so the token never appears (reuse `app.ai.redact`)
- [X] T006 [P] Fake transport `backend/tests/fake_telegram.py`: `FakeTelegram` holding a bot `username`, a `token`, queued updates, recorded sent/edited messages and answered callbacks; returns an `httpx.MockTransport`; switches to simulate 401, 409, timeout and network error
- [X] T007 Request primitives in `backend/app/telegram/service.py`: `new_request(db, purpose, *, user_id=None, ip, user_agent) -> (TelegramRequest, start_token, browser_secret|None)` (start token = `secrets.token_urlsafe(32)` (43 chars), public id = `secrets.token_urlsafe(12)` (16 chars), browser secret = `secrets.token_urlsafe(32)`, SHA-256 stored, `match_code` random 10–99 for sign_in, `expires_at = now + 5 min`); `find_by_token`, `find_by_browser`; `expire_due(db)` (non-final past expiry → `expired`); `purge_old(db)` (older than 1 day); `deep_link(bot_username, token)`; `qr(deep_link)` via `mfa.qr_svg_data_uri`; `consume(db, req)` with `SELECT … FOR UPDATE` guaranteeing approved → consumed exactly once
- [X] T008 Poller `backend/app/telegram/poller.py`: `TelegramPoller(stop_event)` thread: when settings enabled and token present, `get_updates(offset)`; for each update call `handler.handle_update(db, client, update)` in its own transaction and persist `update_offset = update_id + 1`; on `invalid_credential` / `webhook_conflict` record `last_check_ok=false` with the reason, `enabled` unchanged, and pause 60 s; network errors back off 1 s → 60 s; never log update payloads or message text
- [X] T009 Wire into `backend/app/worker.py`: start the poller thread in `serve()`, stop it on shutdown; each loop also calls `service.expire_due` and (hourly) `service.purge_old`
- [X] T010 Env-gated test hook `backend/app/api/testhooks.py`: `POST /api/test/telegram/update` (body = Telegram Update JSON) calling `handler.handle_update` with a client built on a recording no-op transport; router included in `backend/app/main.py` ONLY when `BIZVIEW_TEST_HOOKS == "1"`; `backend/tests/test_telegram.py` asserts it is absent by default

**Checkpoint**: migration up/down, models match, poller unit-tested with FakeTelegram.

---

## Phase 3: User Story 1 — The super user turns on Telegram sign-in (P1)

**Goal**: configure bot (encrypted, write-only), check, enable/disable; nothing visible until on.

**Independent test**: quickstart 1–5.

- [X] T011 [US1] Settings service in `backend/app/telegram/service.py`: `get_settings_row(db)` (creates the singleton lazily), `public_state(row)` (dict per contracts/api.md, never the token), `update_settings(db, actor, bot_username, token|None|"")` (normalise `@`, validate the regex; any change → `last_check_ok=None`, `enabled=False`; token encrypted with `crypto.get_keyring().encrypt(token.encode(), TELEGRAM_AAD)` and `ensure_key_check`; audit `telegram_settings_updated` with `detail={"fields": [...]}`), `token_of(row)`, `check(db, actor, client_factory)` (`get_me` + `get_webhook_info`; reasons `invalid_credential` / `unreachable` / `timeout` / `name_mismatch` (case-insensitive compare) / `webhook_conflict`; stores result; audit `telegram_checked`), `set_enabled(db, actor, enabled)` (409 `telegram_check_required` unless `last_check_ok is True`; audit `telegram_enabled`/`telegram_disabled`), `is_available(db)` (enabled and last_check_ok)
- [X] T012 [US1] Routes in `backend/app/api/telegram.py` (router included in `backend/app/main.py`): `GET /api/admin/telegram` (`require_superuser`), `PUT /api/admin/telegram`, `POST /api/admin/telegram/check`, `POST /api/admin/telegram/enabled` (all `require_superuser` + step-up `recent_reauth`); pydantic bodies with `extra="forbid"`; `token` max 100 chars
- [X] T013 [US1] `backend/app/api/health.py` `/api/config`: add `telegram_sign_in` and `telegram_bot` (read with a short DB session; on DB error report false/null)
- [X] T014 [P] [US1] Backend tests in `backend/tests/test_telegram.py`: defaults off (config false, start 404); only super user + step-up; token write-only (marker token absent from every API response, audit details, and captured logs — SC-004); each check reason via FakeTelegram; enable refused before a good check and after a token change; disable keeps links
- [X] T015 [US1] Frontend types/strings: `frontend/src/api/types.ts` (`PublicConfig.telegram_sign_in`, `telegram_bot`; `TelegramAdminState`), `frontend/src/i18n/es.ts` `telegram` block (all texts of contracts/api.md and bot refusals)
- [X] T016 [US1] Super-user section in `frontend/src/pages/admin/Security.tsx`: card "Ingreso con Telegram" — bot name input, write-only token field (existing `SecretField`), Guardar, Probar (shows result/reason), switch Activar (disabled until the check is OK), all actions through the existing ReauthDialog step-up; tokens only (feature 006 guard)

**Checkpoint**: super user can configure, check, enable; sign-in screen and profile still unchanged until enabled.

---

## Phase 4: User Story 2 — A user links their Telegram account (P1)

**Goal**: link/unlink own Telegram (step-up + bot Confirmar); admin removes links.

**Independent test**: quickstart 6–8.

- [X] T017 [US2] Link conversation in `backend/app/telegram/handler.py` per contracts/bot.md: `/start <token>` for a `link` request → bind `telegram_id`/`chat_id`, status `started`, send "Vincular tu Telegram a {masked email} en {product}…" with `ok:<id>` / `x:<id>`; callback `ok` from the same Telegram id → `approved` then immediately `consume`: insert `TelegramLink` (username, display name = first + last name, ≤ limits) — on unique violation → `refused/already_linked` with generic text; audit `telegram_linked`; `x` → `refused/cancelled`; edit the message to the final state; invalid/expired/foreign callbacks → "Esta solicitud ya no es válida."
- [X] T018 [US2] Routes in `backend/app/api/telegram.py`: `GET /api/me/telegram`, `POST /api/me/telegram/link` (`recent_reauth`; 409 `telegram_already_linked_self`; 404 when not available), `DELETE /api/me/telegram` (`recent_reauth`; audit `telegram_unlinked` actor=user)
- [X] T019 [US2] `backend/app/api/admin.py`: `DELETE /api/admin/users/{id}/telegram` (`require_admin`, `users.ensure_can_manage(actor, target, "telegram")`, step-up; 404 if none; audit actor=admin target=user); `user_json` for admin reads gains `telegram_linked`
- [X] T020 [P] [US2] Backend tests (append to `backend/tests/test_telegram.py`): full link via handler with FakeTelegram updates; link of an already-linked Telegram id refused without naming the holder; foreign callback ignored; expiry; unlink own and by admin (audit actors); admin cannot unlink a user they cannot manage
- [X] T021 [US2] `frontend/src/components/TelegramCard.tsx` + `frontend/src/pages/Profile.tsx`: card shown when `telegram_sign_in`; unlinked → "Vincular Telegram" (step-up) → "Abrir Telegram" button + QR (≥ 640 px) + countdown, polls `GET /api/me/telegram` every 2 s until linked/5 min; linked → name, date, "Desvincular" (step-up)
- [X] T022 [US2] `frontend/src/pages/admin/UserDetail.tsx`: when `telegram_linked`, "Quitar vínculo de Telegram" with confirmation modal + step-up

**Checkpoint**: links created and removed; audit shows actors.

---

## Phase 5: User Story 3 — A user signs in with Telegram (P1)

**Goal**: sign in with match code; same rules as password sign-in.

**Independent test**: quickstart 9–17.

- [X] T023 [US3] Refactor `backend/app/api/auth.py`: extract `finish_sign_in(db, user, request, response, ip, *, method)` containing the shared rules after the credential is proven — locked → audit `login_failed` + throttle failure + `users.locked_error`; inactive → audit + throttle failure + generic refusal; `mfa.enabled` → `mfa_pending` session + `{"mfa_required": True}`; else `_complete_login` (audit `login_ok` with `detail={"method": method}` when method is not password). Password `login` keeps its exact behaviour (existing tests must pass unchanged)
- [X] T024 [US3] Sign-in conversation in `backend/app/telegram/handler.py`: `/start <token>` for `sign_in` → bind; Telegram id not linked → `refused/not_linked` + reply text of contracts/bot.md; else message with three shuffled distinct codes (the request's `match_code` + two random 10–99) as `c:<id>:<code>` and `x:<id>`; callback: right code → `approved` with `user_id` of the link; wrong → `refused/wrong_code`; `x` → `refused/cancelled`; edit message to the final state; refresh link `username`/`display_name`
- [X] T025 [US3] Routes in `backend/app/api/telegram.py`: `POST /api/auth/telegram/start` (404 when not available; `throttle.check`; replace any previous request of this browser; set cookie `bv_tg` HttpOnly, SameSite=Strict, Path=/api/auth/telegram, Max-Age 300, Secure per `COOKIE_SECURE`; response per contract) and `GET /api/auth/telegram/status` (by cookie; `throttle.check`; `approved` → `service.consume` then `finish_sign_in(method="telegram")`, clear `bv_tg`; `refused` → audit `login_failed` `{method: telegram, reason}` + `throttle.register_failure` once per request; messages per contract; no cookie/unknown/expired → `{"status": "expired"}`)
- [X] T026 [P] [US3] Backend tests (append to `backend/tests/test_telegram.py`): happy path signed_in + session works + audit; not_linked / wrong_code / cancelled refused and counted; inactive and locked same refusals as password; `internet` profile admin with two-step → `mfa_required` then `/api/auth/mfa` completes; temporary-password user lands with `must_change_password`; replayed `/start`, status after consumption, status without cookie or from another client, expiry → refused/expired (SC-002); 20 Telegram failures then password → 429 (shared counter); unreachable Telegram does not affect password sign-in
- [X] T027 [US3] `frontend/src/components/TelegramSignInPanel.tsx` + `frontend/src/pages/SignIn.tsx`: when `telegram_sign_in`, secondary button "Ingresar con Telegram" under the form → panel: match code (large, `aria-live`), "Abrir Telegram" link button (`deep_link`, opens app on phones), QR image (≥ 640 px), countdown, polling `GET /api/auth/telegram/status` every 2 s; `signed_in` → `setUser` + navigate to `next`; `mfa_required` → existing second-step UI; `refused` → message + "Intentar de nuevo"; `expired` → restart button; network failure → "Telegram no está disponible; ingresa con tu correo" (FR-013); tokens only, 44 px
- [X] T028 [P] [US3] Unit test `frontend/tests/unit/telegram.test.ts`: panel polling state machine with mocked `api` (pending → signed_in, refused, expired, network error, stops polling on unmount)

**Checkpoint**: all three stories complete.

---

## Phase 6: Polish & cross-cutting

- [X] T029 E2E `frontend/tests/e2e/telegram.spec.ts` (backend started with `BIZVIEW_TEST_HOOKS=1` in `frontend/tests/e2e/backend.sh`): super user configures with a fake-checked bot (test hook marks check OK), links own Telegram via `/api/test/telegram/update`, signs out, signs in with Telegram choosing the shown code; refusal path; axe on sign-in panel, profile card and security card in light and dark; reset settings in `afterEach`
- [X] T030 [P] `CHANGELOG.md` Unreleased entry; `docs/INSTALL.md` section "Ingreso con Telegram" (create bot with @BotFather, worker must reach api.telegram.org, no webhook)
- [X] T031 Run suites sequentially: backend `uv run pytest`, then frontend `npm test && npm run build && npm run check:compat && npm run e2e` — *Baseline 2026-10-08: backend (all pass after 2 test fixes and 3 network-timeout reruns), CLI, frontend unit 425, build, compat, Playwright 300 passed / 36 skipped*
- [X] T032 `/speckit-converge` and walk quickstart.md 1–19 (19 = manual with a real bot) — *automated scenarios green; quickstart 19 (real bot) stays a manual owner check*

---

## Dependencies & execution order

- T001 → T002 → T003 → T004; T005 (+T006 in parallel) → T007 → T008 → T009; T010 after T008.
- US1 (T011–T016) needs Phase 2. US2 (T017–T022) needs T011 (availability). US3 (T023–T028) needs T011 and T007; T023 is independent of US2 and can start early.
- Polish after the stories.

## Parallel examples

- T006 ‖ T005; T014 ‖ T015/T016; T020 ‖ T021/T022; T026 ‖ T027; T028 ‖ T029 prep; T030 any time.

## Implementation strategy

1. MVP = Phase 2 + US1 + US2 + US3 (all P1; sign-in needs linking needs configuration).
2. DeepSeek batches: (A) T002–T004, (B) T005–T007, (C) T008–T010, (D) US1 backend, (E) US1 UI,
   (F) US2, (G) T023 + US3 backend, (H) US3 UI, (I) tests per story. Claude audits each batch and
   runs the relevant tests before the next.

---

## Phase 7: Convergence

- [X] T033 Record poller health (`telegram_settings.last_poll_ok_at` timestamptz NULL via migration `0007_telegram_poll_health` + model; set by `TelegramPoller` after every successful `getUpdates`) and make `POST /api/auth/telegram/start` and `POST /api/me/telegram/link` answer `503 telegram_unavailable` ("Telegram no está disponible; ingresa con tu correo.") when no successful poll happened in the last 2 minutes; the sign-in panel and profile card show that message; tests in backend/tests/test_telegram.py, per FR-013 (partial)
- [X] T034 Poller tests in backend/tests/test_telegram.py using FakeTelegram and `TelegramPoller(stop).poll_once()`: offset advances and persists, a poison update is skipped with the offset advanced, `invalid_credential`/`webhook_conflict` set `last_check_ok=false` with the reason, nothing polled while unavailable, per plan: Phase 2 checkpoint / T008 (missing)
- [X] T035 Sync specs/007-telegram-sign-in/contracts/api.md, research.md R6 and data-model.md with the code: locked/inactive return the password sign-in errors (401/423), admin user detail carries `telegram_linked` at top level, test hooks `sent`/`reset`/`check-ok`, encryption AAD `bizview:v1:telegram_settings:token`, per contracts/api.md (contradicts)
