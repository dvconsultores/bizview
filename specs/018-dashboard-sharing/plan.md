# Implementation Plan: Dashboard sharing — email and expiring links

**Branch**: `018-dashboard-sharing` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

## Summary

Expiring read-only share links for one dashboard (hash-only tokens, throttled public routes that
reuse the report engine), email delivery of the dashboard PDF through an installation SMTP server
configured by the super user (encrypted password), queued and sent by the worker with per-recipient
status and retries, and scheduled subscriptions run by the worker's APScheduler.

## Technical Context

Python 3.12 / FastAPI / SQLAlchemy / Alembic (migration `0013_dashboard_sharing`); stdlib `smtplib`
+ `email` (supporting library, no new stack component); ReportLab PDF via `backend/app/reports/pdf.py`
(same code as the dashboard download); AES-256-GCM secrets via `app.security.crypto` keyring;
APScheduler in the worker. React 19 / Tailwind frontend. Tests use an in-process fake SMTP server
(`aiosmtpd` is NOT added: a tiny `smtpd`-like stub on a socket or a monkeypatched `smtplib.SMTP`).

## Constitution Check

- **V (fixed stack)**: no new component; stdlib SMTP is a supporting library (listed here); the
  mail server is installation configuration, like the Telegram bot.
- **VII**: no customer data in the repo; sender/branding from installation settings.
- **VIII**: no AI involved; share links never trigger AI narrative generation.
- **IX**: links and emails show only applied, spec-validated reports (engine unchanged).
- **Security**: tokens 256-bit, hash-only (like `api_token`), throttled public access, `noindex`,
  `no-store`, links off by default and toggled by the super user (audited), SMTP password encrypted
  and write-only, "ninguna" TLS refused in the internet profile, external recipients only in allowed
  domains, rate limits per user. → PASS.

## Design

### Data (migration `0013_dashboard_sharing`)
- `share_link(id, dashboard_id FK dashboard ON DELETE CASCADE, token_hash bytea unique, note text
  ≤200, created_by FK app_user, created_at, expires_at, revoked_at NULL, revoked_by NULL, visits int
  default 0, last_visit_at NULL)`; index (dashboard_id) and partial index on active links.
- `email_settings(id=1 singleton, enabled bool, sharing_enabled bool, host, port int, security
  starttls|ssl|none, username, password_ct bytea, password_key_id text, sender_name, sender_address,
  allowed_domains text[], last_test_at, last_test_ok, last_test jsonb, updated_at, updated_by)` —
  pair check like `telegram_settings`.
- `email_send(id, dashboard_id FK, requested_by FK NULL, subscription_id FK NULL, subject, message,
  selection jsonb (period/compare/filters params), attach_pdf bool, link_days int NULL, status
  queued|sending|sent|partial|failed, created_at, finished_at)`;
  `email_delivery(id, send_id FK cascade, recipient text, user_id NULL, status
  queued|sent|failed|skipped, attempts int, next_attempt_at, error text NULL, sent_at)`.
- `email_subscription(id, dashboard_id FK cascade, created_by, recipients jsonb [{user_id}|{email}],
  frequency daily|weekly|monthly, hour 0–23, weekday 0–6 NULL, monthday 1–28 NULL, period preset,
  attach_pdf, link_days NULL, paused bool, last_due_at NULL, next_due_at, created_at, updated_at)`.
- Audit kinds: `share_link_created`, `share_link_revoked`, `sharing_toggled`,
  `email_settings_updated`, `email_test_sent`, `email_sent`, `email_subscription_created`,
  `email_subscription_updated`, `email_subscription_deleted`.

### Backend modules
- `app/sharing/links.py`: create (admin/super user, dashboard visible to them, active ≤20,
  days 1–90), `resolve(db, raw_token)` → dashboard or None (hash compare, not expired/revoked,
  sharing enabled, dashboard available), visit counting (single UPDATE), revoke.
- `app/api/shared.py` public router `/api/shared/{token}`: `GET` (dashboard + report definition),
  `GET /data`, `GET /filters/{dimension}`, `POST /pdf` — all reuse `api/reports.py` helpers with a
  context resolved from the link instead of a user; no narrative; throttle per address
  (`app.security.throttle`); headers `X-Robots-Tag: noindex, nofollow`, `Cache-Control: no-store`,
  `Referrer-Policy: no-referrer`. Unknown/expired/revoked → 404 with one neutral message.
- `app/api/sharing.py` (authenticated): `GET/POST /api/dashboards/{code}/links`, `DELETE
  /api/dashboards/{code}/links/{id}`; `POST /api/dashboards/{code}/email` (queue a send);
  `GET /api/dashboards/{code}/email` (my sends; admins see all for the dashboard);
  subscriptions CRUD `/api/dashboards/{code}/subscriptions` (admins).
- `app/mail/settings.py` + `app/api/mail.py` (super user): GET (no password), PUT (password
  write-only, encrypted with the keyring, AAD `email_settings`), POST `/test`, toggles; `crypto.rotate`
  re-encrypts this secret too.
- `app/mail/send.py`: build the message (HTML + text, organization name, optional link, PDF
  attachment ≤ 10 MB else link-only/failed), `smtplib.SMTP`/`SMTP_SSL` with timeout, STARTTLS with
  certificate verification, login; errors sanitized (no password, host only as configured label).
- Recipients: installation users by id (active, with access to the dashboard re-checked at send
  time) and external addresses whose domain is in `allowed_domains`; ≤20 per send; rate limit 30
  sends/user/hour.
- Worker: `take_email_sends()` every 15 s claims queued deliveries with `FOR UPDATE SKIP LOCKED`,
  renders the PDF once per send (same `pdf.render` + `_data` path, user context of the requester or
  admin context for subscriptions), sends, retries with backoff 1/5/15 min, max 3 attempts, rolls
  up the send status. `email_subscriptions_tick()` every minute: due subscriptions
  (`next_due_at <= now`, not paused) are claimed with `FOR UPDATE SKIP LOCKED`, a send is created
  with `subscription_id` and the period preset, `last_due_at`/`next_due_at` advanced in the same
  transaction (exactly once).
- Links in emails: created as share links owned by the sender (admins) with `link_days`.
- Public URL: `https://<SITE_ADDRESS>` when it is a domain, else the request origin for interactive
  sends and `SITE_ADDRESS` fallback for subscriptions (documented).

### Frontend
- Dashboard view header: "Compartir" (admins) and "Enviar por correo" (when enabled) open views
  inside the dashboard page (no modal): Compartir = days (1–90, chips 1/7/30/90), note, create →
  link shown once with copy; "Enlaces activos" list with revoke. Enviar por correo = recipients
  picker (users search + external address input with domain validation), subject, message, attach
  PDF, include link days (admins), uses the current period/filters; "Envíos" list with statuses;
  "Envíos programados" (admins) list + form.
- Public route `/s/:token` outside the authenticated shell: read-only dashboard (reuses report
  components) with a "Vista compartida · vence el …" banner, PDF button, no navigation; neutral
  expired page.
- Administración → Correo (`/admin/correo`, super user): SMTP form, password write-only field,
  allowed domains, enable email, enable shared links, test email.

## Tests
- Backend: link lifecycle (create limits, hash-only storage, expiry, revoke, sharing toggle,
  dashboard unavailable); SC-002 probe — a link token reaches only `/api/shared/{token}/*` of its
  dashboard (every other route 401/404, other dashboards 404); throttling; headers; settings
  (password encrypted, never returned, rotate); recipient rules (domains, limits, inactive users,
  access re-check); worker send with a fake SMTP (PDF attached and equal to the download bytes for
  the same selection, retries, sanitized errors); subscription exactly-once across two workers
  (SKIP LOCKED) and next-due computation; audit entries; migration 0013.
- Frontend unit: share view, email view validation, public page states, settings page.
- E2E: create link → open in a fresh context → dashboard + PDF; revoke → neutral page; send email
  to a fake SMTP (test hook exposing received messages) → delivered.
