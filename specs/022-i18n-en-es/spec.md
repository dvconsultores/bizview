# Feature Specification: Interface in Spanish and English (i18n)

**Feature Branch**: `022-i18n-en-es`

**Created**: 2026-10-08

**Status**: Implemented (closed 2026-10-12, backend + CLI + frontend + e2e suites green)

**Input**: Owner, 2026-10-08 (prompt.md): "please create i18n for all the app, English and Spanish."

**Supersedes**: the "Spanish only" interface rule (002 FR-024, `frontend/src/i18n/es.ts`).
**Constitution**: 2.0.0 constraint "every user-visible text in Spanish and English".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Each user chooses the language (Priority: P1) 🎯

A user opens Perfil → Idioma and chooses "English"; every screen changes to English at once and stays
English on any device after signing in again. Another user keeps "Español".

**Why this priority**: it is the request; per-user choice serves mixed teams.

**Independent Test**: sign in, switch to English, walk every route (e2e list of all routes and
views): no Spanish string of the catalogue remains visible; switch back to Español: no English
string remains; sign in on a new browser: the choice is kept.

**Acceptance Scenarios**:

1. **Given** Perfil, **When** the user chooses Español / English / "Idioma del navegador", **Then**
   the interface switches without a full sign-out, the choice is saved on the account, and the
   account menu offers the same switch (like the theme switch of 006).
2. **Given** no saved choice, **When** the app loads, **Then** it uses the browser language if it is
   English or Spanish, otherwise the installation default `DEFAULT_LOCALE` (default `es`).
3. **Given** the sign-in page (no session), **When** it loads, **Then** it follows the browser
   language and offers a language switch; the choice is remembered on that device and saved to the
   account after sign-in if the account has none.
4. **Given** English, **When** numbers, currency, dates, periods ("Mes en curso" → "Current month")
   and relative times are shown, **Then** they use English formatting (`en-US`); Spanish uses
   `es-ES` formatting as today.

---

### User Story 2 - Server messages, PDFs, emails and the agent follow the language (Priority: P1)

Errors from the API, validation problems, PDF exports, emails (dashboard send, scheduled
subscriptions, mail test), Telegram bot messages and the agent's replies come in the user's language.

**Independent Test**: with the account in English: trigger a validation error, a sign-in error, a
PDF export, a "send by email" and a chat message (fake provider); each output is in English; repeat
in Spanish.

**Acceptance Scenarios**:

1. **Given** an API error, **When** returned, **Then** it carries a stable `code`, parameters and a
   message in the request language (account language, else `Accept-Language`, else default).
2. **Given** a PDF export, **When** generated, **Then** headings, labels, period names, page footer
   and number/date formats follow the requesting user's language; a scheduled email PDF follows each
   recipient's language.
3. **Given** an email (dashboard send, scheduled subscription, mail test; the product sends no
   password or alert emails today), **When** sent, **Then** subject and body are in the recipient's
   language; Telegram bot messages follow the linked account's language (else the Telegram client
   language, else `DEFAULT_LOCALE`).
4. **Given** the agent (014/017/021/023), **When** it replies, **Then** it answers in the user's
   language; command prompts and the scope refusal exist in both languages; the specs it writes use
   the project's language (`project.yaml` `language`, default the creator's language — from feature
   020 on; before 020, the session owner's language).
5. **Given** the worker's run history and audit entries, **When** shown, **Then** fixed texts are
   translated by code; free-form values (database error texts, names) are shown as recorded.

---

### User Story 3 - Nothing is left untranslated (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the frontend catalogues, **When** the unit tests run, **Then** the English and Spanish
   catalogues have exactly the same keys and placeholders, no value is empty, and no component
   contains a user-visible literal outside the catalogue (lint test).
2. **Given** the backend catalogues, **When** the tests run, **Then** every message id used in code
   exists in both languages with the same placeholders.
3. **Given** the CLI (`bizview validate` messages), **When** `BIZVIEW_LANG=en` or the system locale is
   English, **Then** messages are in English; default Spanish.

### Edge Cases

- Authored workspace content (report titles, metric names, spec documents) is shown as written; it is
  not machine-translated. A report MAY declare optional English labels (`title_en`, `label_en`,
  `description_en`) used when the viewer's language is English.
- Shared links (018) without an account: browser language, with a switch.
- Missing key at runtime (should never pass the tests): falls back to Spanish and logs the key once.
- Right-to-left languages: out of scope.
- Screen readers: `<html lang>` follows the active language.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Frontend text MUST come from two catalogues (`es`, `en`) with identical structure;
  English MUST be type-checked against the Spanish shape so a missing key fails the build.
- **FR-002**: The active language MUST be resolved as: account preference → device choice (sign-in,
  shared view) → browser language (es/en) → `DEFAULT_LOCALE`; changing it re-renders the app without
  signing out.
- **FR-003**: The account MUST store `locale` (`es` | `en` | null = browser) through the existing
  preferences endpoint (`PATCH /api/me/preferences`), with a migration.
- **FR-004**: Number, currency, percent, date and time formatting MUST use the active locale
  (`es-ES` / `en-US`); period and comparison names come from the catalogues.
- **FR-005**: API errors MUST carry `code` and `params`; the backend MUST render `message` from a
  backend catalogue in the request language; the frontend MAY prefer its own text for known codes.
- **FR-006**: PDFs (ReportLab) and emails MUST be rendered from catalogues in the requesting user's
  or recipient's language; recipients without an account get `DEFAULT_LOCALE`.
- **FR-007**: The agent's system prompt, command prompts (021), scope refusal (021 FR-007) and app
  guide (023) MUST exist in both languages; replies follow the user's language.
- **FR-008**: The CLI MUST offer `es` and `en` messages (`BIZVIEW_LANG`), default `es`.
- **FR-009**: Report definitions MAY carry optional `_en` labels (title, description, metric and
  dimension labels, view titles); the schema is extended additively.
- **FR-010**: Tests MUST enforce key parity, placeholder parity, and no hard-coded user-visible
  strings in components (allow-list for brand names and technical tokens).
- **FR-011**: `<html lang>` and document titles MUST follow the active language.

### Key Entities

- **Locale preference**: user, `es` | `en` | null.
- **Message catalogue**: id → text with named placeholders, per language (frontend, backend, CLI).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The e2e language walk visits every route and view in both languages with 0 strings
  from the other language's catalogue visible.
- **SC-002**: 100% key and placeholder parity in all catalogues (unit tests).
- **SC-003**: Switching language takes under 300 ms on the reference machine and keeps the current
  page and its state (filters, open project tabs).
- **SC-004**: PDFs and emails produced in English contain 0 Spanish fixed texts (test on extracted
  PDF text and email bodies).

## Assumptions

- No i18n library is needed: typed catalogues and a small context (frontend), dict catalogues
  (backend, CLI). If the plan picks a library it is a supporting library listed in the plan.
- English is US English for formatting; Spanish keeps `es-ES` formatting as today.
- Existing Spanish texts are the reference; English texts are written by the team (no runtime
  machine translation).
