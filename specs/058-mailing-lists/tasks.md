# Tasks — 058-mailing-lists

Feature: [spec.md](./spec.md) · Plan: [plan.md](./plan.md) · Data: [data-model.md](./data-model.md) ·
Contract: [contracts/mail-api.md](./contracts/mail-api.md)

Tests are part of the work: the repo ships suites for every package and this feature changes delivery
semantics, so each phase ends with the tests that prove it.

## Phase 1 — Setup

- [x] T001 `backend/app/config.py`: add `EMAIL_BATCH_SIZE` (1..500, default 50), `EMAIL_SEND_RATE`
  (0..100, default 10), `EMAIL_INDIVIDUAL_MESSAGES` (default false), `EMAIL_SENDING_PAUSED`
  (default false), `EMAIL_FROM_MODE` (`installation|user`), `EMAIL_FREE_ADDRESSES_ROLE`
  (`user|admin`); keep `EMAIL_ALLOWED_DOMAINS` but document that empty means any domain
- [x] T002 `backend/app/mail/addresses.py`: `parse_recipients(text)` → `(valid: [(address, name)],
  invalid: [raw])` splitting on `,;\s`, accepting `Nombre <correo>`, normalising and de-duplicating;
  `mask(address)` → `a***@dominio`
- [x] T003 `backend/app/models.py`: `MailList`, `MailListMember`, `EmailSend.kinds`,
  `EmailDelivery.list_id`, `EmailSubscription.paused_reason`; audit kinds `mail_list_created`,
  `mail_list_updated`, `mail_list_deleted`, `mail_send_resent`
- [x] T004 `backend/alembic/versions/0054_mail_lists.py` with the two tables, the three columns, the
  partial unique index on `(owner_id, lower(name))` and the audit-kind allowlist update

## Phase 2 — Foundational (blocks every story)

- [x] T005 `backend/app/mail/lists.py`: CRUD with ownership/visibility rules, 1,000-member cap, role
  lists, `resolve(db, ids, *, free_role)` returning addresses (skipping paused members and the
  sender), `by_name(db, name)`, `export_csv(list)`, `import_csv(list, text)` with per-line errors
- [x] T006 `backend/app/mail/sends.py`: delete `MAX_RECIPIENTS` and `SENDS_PER_HOUR` and the hourly
  lock/refusal; accept `lists` and parse `emails` with `parse_recipients`; apply the domain filter
  only to free addresses and members; drop the sender's own address; record `kinds`
- [x] T007 `backend/app/mail/send.py`: `build_message` accepts BCC batches; `From`/`Reply-To` per
  `EMAIL_FROM_MODE`; `deliver_batch`
- [x] T008 `backend/app/mail/sends.py`: `_process_send` groups pending deliveries into
  `EMAIL_BATCH_SIZE` chunks (BCC + sender in To) or one message per address when
  `EMAIL_INDIVIDUAL_MESSAGES`, pacing with a token bucket at `EMAIL_SEND_RATE`, one status per
  address; `process_due` returns early when `EMAIL_SENDING_PAUSED`

## Phase 3 — User Story 1 (P1): send to any address

- [x] T009 [US1] `backend/app/api/sharing.py`: `EmailIn` gains `lists` and `save_as_list`; the options
  endpoint answers `max_recipients: null`, `sending_paused`, `batch_size`, `send_rate`,
  `individual_messages`, `from_mode`, `free_addresses_role` and the usable lists
- [x] T010 [US1] `backend/tests/test_mail_send_batches.py`: addresses parse, duplicates collapse, the
  sender is dropped, the send has no ceiling, 1,500 recipients become ⌈1500/size⌉ messages paced, the
  domain filter empty vs set, `EMAIL_SENDING_PAUSED`, `EMAIL_FROM_MODE=user`
- [x] T011 [P] [US1] `frontend/src/components/sharing/EmailPanel.tsx`: recipient chips for users,
  lists and free addresses, bulk paste, live counter, save-as-list
- [x] T012 [P] [US1] `frontend/src/api/mail.ts` + `frontend/tests/unit/mail-lists.test.tsx`:
  client and the dialog's parse/counter behaviour

## Phase 4 — User Story 2 (P1): lists

- [x] T013 [US2] `backend/app/api/mail_lists.py` + router registration: the contract's endpoints
- [x] T014 [US2] `backend/app/mail/lists.py` + `subscriptions.py`: deleting a list pauses the
  subscriptions that use it with `paused_reason = list_deleted`
- [x] T015 [US2] `backend/tests/test_mail_lists.py`: CRUD, ownership, shared visibility, CSV
  import/export, paused member skipped, role list resolves at send time, delete pauses
- [x] T016 [P] [US2] `frontend/src/pages/mail/Lists.tsx` + `ListEditor.tsx` and the route/entry:
  Mis listas, Listas de correo (admin), paste, CSV import/export, pause
- [x] T017 [P] [US2] `frontend/src/i18n/{es,en}.ts`: every new label

## Phase 5 — User Story 3 (P2): subscriptions

- [x] T018 [US3] `backend/app/mail/subscriptions.py` + `api/sharing.py`: `lists` in create/update/
  to_json; `paused_reason` exposed and cleared; tick resolves lists at send time
- [x] T019 [US3] `backend/tests/test_mail_subscriptions.py`: a subscription with a list delivers once
  per member on the tick; a deleted list pauses it
- [x] T020 [P] [US3] `frontend/src/components/sharing/SubscriptionsPanel.tsx`: the same recipient
  kinds as the dialog, plus the paused reason

## Phase 6 — User Story 4 (P2): authored distributions

- [x] T021 [US4] `cli/bizview_cli/schemas/distribution.schema.json` + validation: `recipients.lists`
  by name, an `@` refused with a message saying addresses are not allowed
- [x] T022 [US4] `backend/app/projects/{compose,apply}.py`: resolve `lists:` names on apply, refuse
  `distribution_list_missing` naming the list; `cli/tests/test_distributions.py` +
  `backend/tests/test_distributions_lists.py`

## Phase 7 — User Story 5 (P3): history and re-send

- [x] T023 [US5] `backend/app/mail/sends.py` + `api/sharing.py`: `GET …/email/sends` (masked
  addresses) and `POST …/email/sends/{id}/resend-failed`
- [x] T024 [P] [US5] `frontend/src/components/sharing/SendHistory.tsx`: per-recipient status, reason,
  Reenviar los fallidos

## Phase 8 — Docs, help, configuration

- [x] T025 `.env.example`, `docs/INSTALL.md` (email section with SES / Workspace / 365 examples),
  `docs/AUTHORING.md` § Distribution (`lists:`), `specs/018-dashboard-sharing/spec.md` amendment
- [x] T026 Help topics `listas-de-correo` (new) and `corregir-envio-de-correo` (new) plus the update
  of `enviar-por-correo`, ES/EN, index + `Relacionados`; `docs/es/*` parity for INSTALL/AUTHORING
- [x] T027 `CHANGELOG.md` under Unreleased; grep gate for `MAX_RECIPIENTS` / `SENDS_PER_HOUR` in
  `scripts/gates/01-vocabulary.sh`

## Phase 9 — Proof

- [x] T028 Run `pytest` (backend + CLI), `vitest`, `tsc`, `scripts/gates/all.sh`,
  `scripts/check_docs_parity.py`; fix what they find

## Dependencies

T001–T004 → T005/T006/T007 → T008 → (T009→T010, T011/T012) → T013→T015→T016 →
T018→T019→T020 → T021→T022 → T023→T024 → T025/T026/T027 → T028.

## MVP

US1 + US2 (T001–T017): a sender can mail any addresses and keep them in a list. Subscriptions,
authored distributions and the history follow.
