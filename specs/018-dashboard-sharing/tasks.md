---
description: "Task list for feature 018 — Dashboard sharing (email and expiring links)"
---

# Tasks: Dashboard sharing — email and expiring links

**Roles**: Claude thinks (spec, plan, tasks, briefs) and audits/converges; DeepSeek executes (writes
all code, tests and fixes). Security-sensitive (public links, SMTP secret, migration): Claude
reviews line by line. Code first, test last.

## Phase 1: Foundational
- [X] T001 Migration backend/alembic/versions/0013_dashboard_sharing.py + models (share_link, email_settings, email_send, email_delivery, email_subscription, audit kinds) + crypto AAD/rotation for the SMTP password; migration test

## Phase 2: User Story 1 — Expiring share links (P1) 🎯
- [X] T002 [US1] backend/app/sharing/links.py + authenticated routes (create/list/revoke) + public router /api/shared/{token} (definition, data, filters, pdf; throttle; headers; no narrative); tests incl. SC-002 route probe
- [X] T003 [US1] Frontend: "Compartir" view in the dashboard page (days, note, link shown once, active links, revoke) + public route /s/:token (read-only dashboard, banner, PDF, neutral expired page); unit tests

## Phase 3: User Story 4 — Email settings (P1)
- [X] T004 [US4] backend/app/mail/{settings,send}.py + /api/admin/mail (GET/PUT/test, toggles email and sharing, internet profile refuses no-TLS); tests with fake SMTP; Frontend Administración → Correo page + admin home tile; unit tests

## Phase 4: User Story 2 — Send by email (P1)
- [X] T005 [US2] Backend: POST/GET /api/dashboards/{code}/email (recipient rules, limits, selection), worker take_email_sends (claim, render PDF once, send, retries, roll-up, access re-check); tests incl. SC-003 PDF equality and SC-005 secret never leaked
- [X] T006 [US2] Frontend: "Enviar por correo" view (recipient picker, subject, message, attach PDF, include link days for admins) + "Envíos" list; unit tests

## Phase 5: User Story 3 — Scheduled delivery (P2)
- [X] T007 [US3] Backend subscriptions CRUD + worker email_subscriptions_tick (exactly once, next due computation, pause, access re-check); tests incl. SC-004
- [X] T008 [US3] Frontend "Envíos programados" list + form; unit tests

## Phase 6: Polish
- [X] T009 E2E (link → public view + PDF → revoke; email to fake SMTP via test hook), CHANGELOG, docs/INSTALL.md (SMTP, sharing, SITE_ADDRESS), .env.example if any new variable
- [X] T010 Targeted suites + `/speckit-converge`

## Phase 7: Convergence
- [X] T011 Refuse non-ASCII SMTP username/password at PUT /api/admin/mail and map UnicodeError/ValueError in smtp_transport to MailError('auth_failed', permanent) without tracebacks; tests (sanitized test-email result, no password fragment in logs, worker marks failed) per SC-005, US4/AC1 (partial)
- [X] T012 crypto.rotate re-encrypts email_send.selection['link'] ciphertexts of unfinished sends (row lock) and reports the count; rotate CLI message lists email_send, email_settings and telegram counts; test per FR-006, plan: key rotation (missing)
- [X] T013 Email-created links: interactive sends count toward the 20 active links (refuse "Incluir enlace" with a reason at the cap); each subscription reuses one active link it owns and creates a new one only when the current one expires within 1 day or was revoked; listing marks link origin; tests per FR-001, FR-008, FR-010 (contradicts)
- [X] T014 Caddyfile: /s/* responses send X-Robots-Tag "noindex, nofollow" and Cache-Control "no-store" (not overridden by the SPA no-cache rule); e2e asserts both headers per Edge: search engines (partial)
- [X] T015 Compartir view computes the cap from the server's counted total (to_json/listing flag) instead of every active item; unit test per FR-001, US1/AC1 (partial)
- [X] T016 Share-link guessing uses its own throttle key/window separate from sign-in, audited with the cause per FR-005 (unrequested)
- [X] T017 Backend test: an existing link serves a new workspace version's definition and returns the neutral 404 after the report is removed per Edge: version change (partial)
- [X] T018 Backend tests for PDFs over 10 MB (no link → failed too_large; with link → no attachment, link present) per Edge: large PDFs (partial)
- [X] T019 E2E sends to 3 recipients and compares the attachment sha256 with the dashboard PDF download for the same selection (test mail hook records sha256) per SC-003 (partial)
- [X] T020 Prefill the subject with the dashboard name in "Enviar por correo" (reset after send); unit test per US2/AC1 (partial)
- [X] T021 Email HTML includes the installation logo (LOGO_URL) with alt text when set; test per FR-008 (partial)
- [X] T022 Serialize the per-user send rate limit (advisory xact lock on the user id) with a concurrency test per FR-007 (partial)
- [X] T023 Show "Envíos programados" to admins even when email is off (panel shows the unavailable state and still allows pause/delete); unit test per FR-011, US3/AC1 (partial)
- [X] T024 Backend tests for scheduled runs with link_days (link created/reused and in the email; sharing off with/without attachment) per FR-010 (partial)
- [X] T025 E2E for "Envíos programados" on phone widths (create weekly, listed with next run, pause, delete inline, axe check) per FR-011 (missing)
- [X] T026 Show next/last run times in the installation timezone (subscriptions response carries TIMEZONE) per FR-010 (partial)
- [X] T027 Docs: INSTALL and CHANGELOG describe email links (count, reuse per subscription, revocable under Enlaces activos) per T009 (partial)

## Phase 8: Email settings from the environment (owner amendment 2026-10-07)
- [X] T028 Config: SMTP_HOST, SMTP_PORT, SMTP_SECURITY, SMTP_USER, SMTP_PASSWORD (SecretStr), SMTP_FROM, SMTP_FROM_NAME, EMAIL_ALLOWED_DOMAINS, SHARE_LINKS_ENABLED in backend/app/config.py with validation (port range, security enum + default by port, internet profile refuses none, address formats, password non-ASCII refused); mail settings/state read from config instead of the email_settings table; remove PUT/toggle routes and the SMTP password encryption/rotation path (keep the email-link ciphertext rotation); migration 0014 drops email_settings (downgrade recreates it empty); .env.example, docs/INSTALL.md, CHANGELOG; tests updated per FR-012
- [X] T029 Frontend: remove the Correo tile from Administración and the /admin/correo route/page and its unit tests; email/sharing availability in dashboard views comes from the backend status; backend CLI command `python -m app.cli mail-test <address>` (sanitized result, exit code) with a test; unit tests and e2e updated (test hooks enable email/sharing through settings overrides) per FR-013
