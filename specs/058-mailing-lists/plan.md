# Implementation Plan: Mailing lists — send a dashboard to any address

**Branch**: `058-mailing-lists` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/058-mailing-lists/spec.md`

## Summary

Remove the two volume guards of feature 018 (per-send recipient ceiling, per-user hourly ceiling) and
make `EMAIL_ALLOWED_DOMAINS` an optional restriction, then add what the guards were standing in for:
**mailing lists** — reusable, owned, optionally shared, optionally dynamic by role — usable as
recipients of an on-demand send, of a scheduled delivery and of a project's
`distributions/<id>.yaml` (by name only). Delivery becomes batched (`EMAIL_BATCH_SIZE` recipients per
BCC message) and paced (`EMAIL_SEND_RATE`), with a per-recipient status kept as today, plus a send
history per dashboard and a "re-send the failed ones" action.

## Technical Context

**Language/Version**: Python 3.12 (FastAPI, SQLAlchemy 2, Alembic), TypeScript 5 + React 18 + Vite,
Tailwind; JSON Schema for artifacts (CLI validator shared by backend and `bizview` CLI).

**Primary Dependencies**: existing only — `smtplib`/`email` (mail), FastAPI, SQLAlchemy, Alembic,
React Router, lucide icons. **No new dependency**: CSV is the standard-library `csv` on the server and
`Blob` in the browser, and batching uses the existing worker queue.

**Storage**: PostgreSQL — two new tables (`mail_list`, `mail_list_member`) plus columns on
`email_send` (recipient kinds) and one nullable `paused_reason` on `email_subscription`.

**Testing**: `pytest` (backend, real PostgreSQL schema per session), `vitest` + Testing Library
(frontend), Playwright e2e (external BI database, CI), CLI `pytest`.

**Target Platform**: self-hosted Docker Compose installation; mobile-first web (320 px up).

**Project Type**: web application with three packages — `backend/`, `frontend/`, `cli/` — plus the
pack at `pack/`.

**Performance Goals**: a 1,500-recipient send is one job; the list pages answer under 300 ms for
1,000 members; the worker never exceeds `EMAIL_SEND_RATE` messages per second.

**Constraints**:
- addresses never reach project files, the log in clear, or an audit event (constitution II/VII,
  spec FR-014, FR-018);
- no volume limits in the product (FR-004), proved by a grep gate;
- mobile first, WCAG 2.2 AA, ES/EN (constitution I);
- the CLI validator and the import must refuse addresses inside `distributions/*.yaml`.

**Scale/Scope**: lists of up to 1,000 members; 1,500 recipients per send in the tests; existing
installations keep their subscriptions untouched.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | This plan |
|---|---|---|
| I. Mobile-first | 320 px, WCAG 2.2 AA, bilingual | lists and dialog reuse the inline card/sheet patterns; no new modal (the `no-modals` guard stays); ES/EN in `es.ts`/`en.ts` |
| II. Backend as ETL | personal data never in project artifacts | `distributions/*.yaml` accepts **list names only**; the validator refuses an `@`; addresses live in the product database |
| III. Source of truth external | — | not touched |
| IV. Separated concerns by folder | no logic in routers | list logic in `app/mail/lists.py`, delivery in `app/mail/sends.py`, routers thin |
| V. Fixed stack | no new stack component | standard-library `csv`/`smtplib`, existing queue — nothing added |
| VII. One product, many installations | no customer data in the repository | tests use `example.com`; the domain allowlist stays installation configuration |
| VIII. AI optional | — | not touched |
| IX. Spec-driven reporting | authored YAML stays the contract | `distribution.schema.json` gains `lists:`; no authored file breaks |

**Result**: PASS. No amendment: the feature removes product limits (a configuration/behaviour change),
adds tables, and keeps the constitution's personal-data bound.

## Project Structure

### Documentation (this feature)

```text
specs/058-mailing-lists/
├── spec.md              # what and why
├── plan.md              # this file
├── research.md          # decisions and alternatives (Phase 0)
├── data-model.md        # tables, fields, invariants (Phase 1)
├── quickstart.md        # how to prove it end to end (Phase 1)
├── contracts/
│   └── mail-api.md      # list, send and subscription endpoints
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0054_mail_lists.py     # new tables + columns
├── app/
│   ├── models.py                            # MailList, MailListMember, EmailSend kinds, paused_reason
│   ├── config.py                            # EMAIL_BATCH_SIZE, EMAIL_SEND_RATE, EMAIL_INDIVIDUAL_MESSAGES,
│   │                                        # EMAIL_SENDING_PAUSED, EMAIL_FROM_MODE, EMAIL_FREE_ADDRESSES_ROLE
│   ├── mail/
│   │   ├── addresses.py                     # "Nombre <correo>", bulk paste, masking
│   │   ├── lists.py                         # NEW: list CRUD, CSV, resolution, delete → pause subscriptions
│   │   ├── sends.py                         # recipient kinds, no ceilings, batching + pacing, resend
│   │   ├── subscriptions.py                 # list recipients, paused reason, project resolution by name
│   │   └── send.py                          # BCC batch message, From/Reply-To per EMAIL_FROM_MODE
│   ├── api/sharing.py                       # bodies accept `lists`; history + resend
│   └── api/mail_lists.py                    # NEW: /api/mail/lists
├── app/projects/compose.py|apply.py         # distribution `lists:` resolved on apply
└── tests/                                   # test_mail_lists.py, test_mail_send_batches.py, additions

cli/
├── bizview_cli/schemas/distribution.schema.json   # `lists:` accepted, addresses refused
└── bizview_cli/validate.py                        # list names are names, not addresses

frontend/src/
├── pages/mail/Lists.tsx, ListEditor.tsx     # NEW: Mis listas / Listas de correo
├── components/sharing/EmailPanel.tsx        # recipient chips, paste, counter, save-as-list
├── components/sharing/SendHistory.tsx       # per-recipient status + resend failed
├── components/sharing/SubscriptionsPanel.tsx# lists in the subscription form
├── api/mail.ts                              # NEW client
└── i18n/{es,en}.ts

docs/AUTHORING.md § Distribution, docs/INSTALL.md email section; help topics
backend/app/guide/{es,en}/listas-de-correo.md and corregir-envio-de-correo.md
```

## Phase 0 — Research

See [research.md](./research.md). Decisions: keep `role` recipients as they are (no synthetic list
rows); a real `mail_list` table for member lists; batch by BCC unless `EMAIL_INDIVIDUAL_MESSAGES`;
pace with a token bucket inside the send job; one `EmailDelivery` row per address in both modes, so
history and resend keep their shape.

## Phase 1 — Design

- [data-model.md](./data-model.md) — tables, invariants, deletion semantics.
- [contracts/mail-api.md](./contracts/mail-api.md) — the endpoints the frontend calls.
- [quickstart.md](./quickstart.md) — the commands that prove it.

## Phase 2 — Tasks

See [tasks.md](./tasks.md).

## Re-evaluated Constitution Check (post-design)

PASS. The design adds no stack component, keeps addresses out of project files (list **names** in
YAML, resolved at apply), writes list and send events to the audit log, and reuses the existing worker
queue — the one place in the product that already talks to SMTP.

## Complexity Tracking

| Decision | Why | Simpler alternative rejected |
|---|---|---|
| A real `mail_list` table instead of reusing `email_subscription.recipients` | lists are edited, shared and reused by many sends; a JSON blob inside a subscription cannot be owned or shared | JSON in a config row: no ownership, no sharing, no CSV |
| Batch by BCC by default, per-recipient messages opt-in | 1,500 SMTP messages for a 1,500-person send stalls the worker and trips provider limits | always per-recipient: simpler status, 30× the messages |
| Pace inside the job with a sleep | the queue already serialises a send's deliveries, so a token bucket per process is enough | `scheduled_at` per batch: more moving parts for the same result |
