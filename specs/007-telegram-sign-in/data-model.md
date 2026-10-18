# Data Model: Sign in with Telegram

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md) ·
Migrations `backend/alembic/versions/0006_telegram.py` (revises `0005_user_theme`) and `0007_telegram_poll_health.py`, schema `public`.

## telegram_settings (singleton)

| Column | Type | Rules |
|---|---|---|
| `id` | smallint PK | CHECK `id = 1` |
| `enabled` | boolean NOT NULL default false | may be true only when `last_check_ok` (enforced in service) |
| `bot_username` | text NULL | 5–32 chars `^[A-Za-z][A-Za-z0-9_]{1,28}[Bb][Oo][Tt]$` (Telegram bot rule), stored without `@` |
| `token_ct` | bytea NULL | AES-GCM ciphertext, AAD `bizview:v1:telegram_settings:token` |
| `token_key_id` | text NULL | CHECK `(token_ct IS NULL) = (token_key_id IS NULL)` |
| `token_changed_at` | timestamptz NULL | |
| `last_check_at` | timestamptz NULL | |
| `last_check_ok` | boolean NULL | reset to NULL when token or name changes (and `enabled` → false) |
| `last_check` | jsonb NULL | `{reason?, bot_name?}` — never the token |
| `update_offset` | bigint NOT NULL default 0 | next `getUpdates` offset |
| `last_poll_ok_at` | timestamptz NULL | last successful `getUpdates` (migration `0007_telegram_poll_health`); older than 2 min → sign-in answers 503 |
| `updated_at`, `updated_by` | timestamptz, FK app_user | |

## telegram_link

| Column | Type | Rules |
|---|---|---|
| `user_id` | bigint PK, FK app_user ON DELETE CASCADE | one link per user |
| `telegram_id` | bigint NOT NULL UNIQUE | permanent Telegram user id (FR-005/006) |
| `username` | text NULL | ≤ 64 chars, refreshed on each Telegram sign-in |
| `display_name` | text NOT NULL | ≤ 128 chars (first + last name), refreshed likewise |
| `linked_at` | timestamptz NOT NULL default now() | |
| `linked_by` | bigint FK app_user | the user themself (only users create links) |

## telegram_request

| Column | Type | Rules |
|---|---|---|
| `id` | text PK | public id, 16 base64url chars (callback data) |
| `purpose` | text | CHECK IN (`sign_in`, `link`) |
| `token_hash` | bytea NOT NULL UNIQUE | SHA-256 of the start token |
| `browser_hash` | bytea NULL UNIQUE | SHA-256 of the `bv_tg` cookie secret; required for `sign_in` |
| `user_id` | bigint NULL FK app_user ON DELETE CASCADE | required for `link`; set on approval for `sign_in` |
| `telegram_id` | bigint NULL | bound at `/start`; only this Telegram user may answer |
| `match_code` | smallint NULL | 10–99, `sign_in` only |
| `status` | text | CHECK IN (`pending`,`started`,`approved`,`refused`,`expired`,`consumed`) |
| `reason` | text NULL | `not_linked`, `wrong_code`, `cancelled`, `inactive`, `locked`, `already_linked`, `expired` |
| `chat_id`, `message_id` | bigint NULL | to edit the bot message to its final state |
| `ip` | inet NULL; `user_agent` text NULL | shown in the Telegram message, audit |
| `created_at` | timestamptz default now(); `expires_at` timestamptz NOT NULL (= created + 5 min) | |

Index on `(status, expires_at)` for the purge. Rows older than 1 day are deleted by the worker.

### State transitions

```text
pending ──/start (bot)──► started ──correct code / Confirmar──► approved ──status/profile poll──► consumed
   │                         ├──wrong code / Cancelar / not linked / inactive / locked──► refused
   └──────────── now > expires_at (any non-final) ─────────────────────────────────────► expired
```

`approved → consumed` happens exactly once (row lock `FOR UPDATE`), issuing the session (sign-in)
or inserting `telegram_link` (link).

## audit_event kinds (CHECK list extended)

`telegram_settings_updated`, `telegram_checked`, `telegram_enabled`, `telegram_disabled`,
`telegram_linked`, `telegram_unlinked`; sign-ins reuse `login_ok` / `login_failed` with
`detail.method = "telegram"` (+ `reason`). Details never include the token or message text.

## Crypto

`crypto.rotate` re-encrypts `telegram_settings.token_ct`; `_encrypted_data_exists` counts it.
