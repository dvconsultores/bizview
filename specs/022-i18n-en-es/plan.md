# Implementation Plan: Interface in Spanish and English (i18n)

**Branch**: `022-i18n-en-es` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

## Summary

Every user-visible text exists in Spanish and English. Frontend: the existing typed catalogue
`frontend/src/i18n/es.ts` gets an English twin `en.ts` typed against it; a small `LocaleProvider`
(`frontend/src/i18n/index.tsx`) switches language without reload while components keep the
`t.section.key` access pattern (`const t = useT()` replaces the import, so the 73 importing files
change mechanically). The choice is stored on the account (`app_user.locale`, migration
`0017_user_locale`) through `PATCH /api/me/preferences`, exactly like the theme of feature 006.
Backend: a dict catalogue `backend/app/i18n/{es,en}.py`, a per-request locale (account → `Accept-Language`
→ `DEFAULT_LOCALE`), and `ApiError` carrying a message id + params rendered in the request
language. PDFs, emails and Telegram messages render per requester/recipient; the agent's system
prompt and the AI narrative exist in both languages; the CLI reads `BIZVIEW_LANG`. Reports may
carry optional `_en` labels. Guard tests enforce key/placeholder parity and no hard-coded
user-visible literals; an e2e walk visits every route in both languages. No i18n library.

## Technical Context

**Language/Version**: Python 3.12 (backend, CLI), TypeScript 5.9 / React 19 (frontend)

**Primary Dependencies**: existing only. Frontend formatting via the built-in `Intl` API; backend
and CLI catalogues are plain dicts with `str.format` placeholders. No new supporting library
(spec assumption holds: no `i18next`, `babel`, `gettext` catalogs).

**Storage**: `public.app_user.locale text NULL CHECK (locale IN ('es','en'))` (NULL = follow the
browser); `public.integration_run.message_key text NULL`, `message_params jsonb NULL` (fixed run
messages translated by code, US2 AC5) — both in migration `0017_user_locale` (down_revision = the
head at implementation time: `0016_run_transform` if 005-A added it, else `0015_direct_reports`).
Device cache `localStorage["bizview.locale"]`.

**Settings**: `DEFAULT_LOCALE=es` (`es` | `en`) in `backend/app/config.py`, `.env.example`,
`docs/INSTALL.md`; exposed read-only in `GET /api/config` as `default_locale`.

**Testing**: pytest on `DATABASE_URL_BI` in `app_test_*` schemas (migration, preferences, request
locale, error envelope, PDF text in English, emails per recipient with the fake SMTP, Telegram
with the fake bot, agent system prompt with the fake provider — never live AI); backend catalogue
parity/usage test (pure, no DB); CLI tests (`cli/tests/test_i18n.py`); Vitest parity, no-literal
and audit-kind coverage guards; Playwright `tests/e2e/i18n.spec.ts` (language walk). Existing
suites keep running in Spanish (Playwright `locale: "es-ES"`, backend default `es`), so their
Spanish assertions stay valid.

**Performance Goals**: language switch < 300 ms with state kept (SC-003) — one context update
re-renders the subscribed tree, no data refetch, no remount.

**Constraints**: CSP `script-src 'self'` (pre-paint `lang` set from the existing
`public/theme-init.js`, no inline script); mobile-first 375 px; WCAG AA (`<html lang>`); no modal
dialogs; authored workspace content never machine-translated.

**Scale/Scope (measured 2026-10-08)**:

| Area | Measured today | Work |
|---|---|---|
| Frontend catalogue | `es.ts` 869 lines: ~710 string leaves, 44 function leaves, 18 `Record` maps, 26 top-level sections | `en.ts` ≈ 1,100 lines (existing + ~250 new keys); es.ts grows to ≈ 1,100 |
| Frontend importers | 73 files import `t` (70 `.tsx`, `lib/{sharing,reportQuery,schedule}.ts`), ~912 `t.` references, ~103 component functions | mechanical: import swap + `const t = useT()` per component |
| Hard-coded literals | ~170 user-visible Spanish literals in ~25 files bypassing `t` (SourceForm ≈45, Workspace ≈35, Security ≈17, Tokens ≈17, Sources ≈10, AdminHome ≈10, Integrations 6, Narrative/TrendChart/RankingTable/KpiGrid/Spinner/SecretField/OverviewTiles/UserForm/UserDetail/AppShell/PasswordRules/Forbidden/ThemeSwitcher/AssistantSession ≈30), `api/client.ts` 2, `lib/csv.ts` 3, `lib/numbers.ts` 1, `index.html` noscript | extract to catalogue (both languages) |
| Audit labels | 16 of 62 `AUDIT_KINDS` labelled in `es.ts`, rest shown raw | 46 new labels × 2 |
| Eager module-level captures | `AdminHome` ENTRIES, `Workspace` SPEC_TAB_LABELS, `DashboardCatalog` soonBadge, `TelegramCard`/`UserDetail` error helpers | turn into functions / move into components |
| Locale formatting | `lib/numbers.ts`, `lib/format.ts` (`LOCALE = "es"`, module-level `Intl` formatters), 11 inline `"es"` sites in `autoRefresh.ts`, `WelcomeBanner`, `TelegramCard`, `StatTile`, `AssistantHistory`, `AgentMap` ×2 | active-locale formatter cache |
| Backend errors | 76 `ApiError(` + 82 helper calls (`forbidden/not_found/validation/unauthenticated`) + 14 `ReportError(`; coded message dicts in `mail/send.py` (15), `ai/__init__.py` (10), `api/telegram.py`, `engine/schedule.py` (9), `engine/periods.py` (5) | ≈ 400–450 backend message ids per language |
| Backend other texts | ~690 Spanish literal hits in 56 modules; top: `assistant/tools.py` 116 (model-facing, see D9), `assistant/service.py` 69, `assistant/origin.py` 58, `assistant/readiness.py` 40, `mail/send.py` 31, `engine/extract.py` 31, `sources/schemas.py` 26, `engine/runner.py` 22 | user-visible ones to catalogue |
| PDF | `reports/pdf.py`: 9 period labels, 12 month abbreviations, ~8 headings, Spanish-only `fmt` | locale parameter + English number/date rules |
| Email / Telegram | `mail/send.py` body/period/link lines, `mail/settings.py` test note, `mail/subscriptions.py` auto subject; `telegram/handler.py` ~14, `telegram/service.py` 5, `api/telegram.py` 3 | per recipient / per linked account |
| Agent | `SYSTEM_PREFIX` ≈ 60 lines Spanish ("responde siempre en español"), ~15 fixed chat texts, `engine/narrative.py` SYSTEM + 3 lines, readiness yes/no words Spanish-only | es/en variants |
| CLI | ~76 messages: `validate.py` 49, `sqlsafety.py` 7, `authoring.py` 8, `__main__.py` 6, `init.py` 6; also called by the backend (`workspace/service.py`, `api/workspace.py`, `assistant/tree.py`, `engine/report.py`, `engine/extract.py`, `assistant/origin.py`) | `bizview_cli/i18n/` + `lang` parameter |
| Report schema | `title`, `description`, `metrics.*.label/description`, `dimensions.*.label`, views `title` (2 view kinds), all `additionalProperties: false` | add optional `*_en` |

Rough effort: frontend ≈ 55 %, backend ≈ 35 %, CLI + schema + docs ≈ 10 %; ≈ 46 tasks.

## Constitution Check

| Rule | Status | Evidence |
|---|---|---|
| I. Mobile-first, Tailwind only | PASS | language switch is a 44 px radiogroup like `ThemeSwitcher`; e2e walk at 320/375 px |
| II. Backend as ETL / direct reads | N/A | data paths unchanged |
| III. Source of truth external | N/A | — |
| IV. Folders | PASS | `frontend/src/i18n/`, `backend/app/i18n/`, `cli/bizview_cli/i18n/`; PDF texts stay in `backend/app/reports/` |
| V. Fixed stack | PASS | no stack component, no supporting library (Intl, stdlib `str.format`) |
| VI. Data tuning | N/A | — |
| VII. One product, many installations | PASS | `DEFAULT_LOCALE` is installation configuration; no customer names in catalogues or fixtures |
| VIII. AI optional/private | PASS | only the instruction language of the system prompt / narrative changes; inputs (aggregates, metadata) unchanged and documented; tests use fake providers |
| IX. Spec-driven reporting | PASS | `_en` labels are an additive, validated schema change; nothing is shown that the validator did not accept |
| Constraint: every user-visible text in Spanish and English | PASS (this feature) | parity + no-literal guards; e2e walk |
| Constraint: product schema via Alembic | PASS | `0017_user_locale` |
| Constraint: JSON API, PDFs by ReportLab | PASS | envelope stays JSON; PDF still ReportLab |
| CSRF / same origin | PASS | PATCH through the existing `X-Requested-With` + Origin check |
| No modals (owner rule) | PASS | switches are inline controls |
| License footer | PASS | `SourceFooter` text from the catalogue |

Post-design re-check: unchanged, no Complexity Tracking entries.

## Design

### D1 — Frontend catalogues and typing (FR-001)
- `es.ts`: `export const es = { … }` (today `export const t`), keeps the current structure, plain
  string leaves, function leaves for interpolation, `as Record<string, string>` maps for code →
  label tables. `export type Catalogue = typeof es;` (object-literal property types are already
  widened to `string`, so no `DeepWiden` helper is needed).
- `en.ts`: `export const en: Catalogue = { … }`. A missing key, an extra key (excess-property check
  on the literal) or a function with a different parameter type fails `tsc -b` → the build.
- Interpolation stays as functions (`locked: (min: number) => …`); no template mini-language.
- Bundle: both catalogues are static imports (≈ 9 KB gzip each); lazy-loading `en` was rejected
  (async switch, typing and test complexity for a few KB).
- Missing-at-runtime fallback (edge case): `useT()` returns a `Proxy`-free object, so a missing key
  cannot pass `tsc`; for `Record` maps (`t.audit[kind] ?? kind`) the existing `??` fallbacks stay.

### D2 — LocaleProvider and switching without reload (FR-002, SC-003)
`frontend/src/i18n/index.tsx` exports:
- `type Locale = "es" | "en"`, `type LocalePreference = Locale | "browser"`.
- `export let t: Catalogue` — a **live ES-module binding** reassigned by the provider before it
  re-renders; non-component code (`lib/schedule.ts`, `lib/sharing.ts`, `lib/reportQuery.ts`,
  `api/client.ts`) imports it and reads it **at call time**, so helpers called during render see the
  current language without a hook.
- `useT(): Catalogue` — `useContext(LocaleContext)`; the context default value is `es`, so unit
  tests that render components without the provider keep working unchanged.
- `useLocale(): { locale, preference, setPreference, intlTag }` (`intlTag` = `es-ES` | `en-US`).
- `LocaleProvider` sits inside `AuthProvider`/`ToastProvider`, next to `ThemeProvider` in
  `App.tsx`; it mirrors `ThemeContext.tsx` (device cache, account wins, serialized PATCH queue, only
  the last response updates the user, toast on save failure keeps the applied language).
- Why components must call `useT()`: a provider state change re-renders only context consumers
  (children passed as props bail out), so every component that renders catalogue text subscribes.
  Re-keying the tree was rejected (remounts everything, loses filters and open tabs — SC-003).

Mechanical migration of each importing file:
1. `import { t } from "../i18n/es"` → `import { useT } from "../i18n"` (`.ts` helpers:
   `import { t } from "../i18n"`).
2. First statement of every component function that references `t.`: `const t = useT();`
   (shadows nothing else; the rest of the file is untouched).
3. Module-level values that read `t` eagerly (ENTRIES, SPEC_TAB_LABELS, soonBadge, `errorText`,
   `message` helpers) become functions called during render, or move into the component.
4. `useMemo`/`useCallback` whose result contains catalogue text add `locale` to their deps
   (12 files use `useMemo`; reviewed per batch).
5. Hard-coded literals in the file move to the catalogue (both languages, same task).
6. Text kept in component state from an earlier event (e.g. an error message set on submit) keeps
   the language it was produced in until the next event — accepted; navigation renders afresh.

### D3 — Locale resolution (FR-002, US1 AC2–3)
Pure function `frontend/src/i18n/resolve.ts` (shared by tests):
`account.locale` (when signed in and not null) → device choice `localStorage["bizview.locale"]`
(`es`|`en`, set on the sign-in page, the shared view or by any explicit switch) → browser
(`navigator.languages`, first entry whose primary subtag is `es` or `en`) → `default_locale` from
`GET /api/config` → `es`.
- Pre-paint: `public/theme-init.js` also sets `<html lang>` from the device cache / browser (same
  rules, classic script, CSP-safe) so screen readers and the first render agree; the account value
  replaces it after `/api/me`. When signed in, the resolved account value is written to the device
  cache so the next cold load starts in the right language (no flash of the other language).
- Sign-in page / shared view (`/s/:token`): compact switch (Español / English); the choice goes to
  the device cache; after sign-in, if the account `locale` is NULL and the device has an explicit
  choice, the provider PATCHes it once (US1 AC3).
- `<html lang>` follows the resolved locale (FR-011). Document titles are brand / dashboard names
  only (BrandingContext, SharedDashboard), so they contain no catalogue text; a unit test pins that.

### D4 — Formatting (FR-004)
- `lib/numbers.ts`, `lib/format.ts`, `lib/autoRefresh.ts`: `LOCALE` constants and module-level
  `Intl` formatters are replaced by `intlTag()` (reads the live locale) and a small
  `Map<tag+options, Intl.*Format>` cache; signatures unchanged, so callers do not change.
  `formatChange` "Nuevo" → `t.common.new`. Percent keeps the language convention
  (`12,3 %` / `12.3%`).
- Inline `"es"` sites (WelcomeBanner, TelegramCard, StatTile, AssistantHistory, AgentMap ×2)
  call the same helpers.
- Periods and comparisons already come from `t.reportParams.*`; schedule texts from
  `t.integrations.words` / `t.sharing.schedules` (functions) — only their callers move to `useT`.
- `numbers.test.ts` gains English cases (`1,234.56 USD`, `Sep 29, 2026`, `1.2K`).

### D5 — Account preference (FR-003)
- Migration `0017_user_locale`: `app_user.locale` NULL + CHECK; `integration_run.message_key`,
  `message_params` (D8). Downgrade drops them. Test in `backend/tests/test_migrations.py`.
- `models.py`: `LOCALES = ("es", "en")`, `AppUser.locale: Mapped[str | None]`.
- `schemas.py`: `PreferencesIn` becomes a partial update — `theme: Theme | None = None`,
  `locale: Literal["es","en"] | None = None`, `extra="forbid"`; a field counts only when present
  (`model_fields_set`), `locale: null` means "browser"; an empty body → 422. `user_json` adds
  `locale`. `PATCH /api/me/preferences` returns `{"theme", "locale"}`; allowed with a temporary
  password (same dependency as today); not audited (display preference, like 006).
- Frontend `api/types.ts`: `User.locale: Locale | null`, `PublicConfig.default_locale: Locale`.

### D6 — Backend catalogue, request locale and errors (FR-005)
- `backend/app/i18n/__init__.py`: `SUPPORTED = ("es","en")`; `normalize(tag) -> Locale | None`;
  `from_accept_language(header) -> Locale | None` (q-values, primary subtag); a contextvar holding a
  **mutable box** (`_Box(locale)`) so a value set inside a sync dependency (threadpool, copied
  context) is still visible to the exception handler and later dependencies of the same request;
  `current() -> Locale`; `use_locale(loc)` context manager (worker, mail, Telegram, tests);
  `t(key, **params) -> str` (falls back to `es`, then to the key, logging a missing key once);
  `class M` — lazy message `M(key, **params)` rendered by the handler; plural helper
  `tn(key, n, **params)` picking `key.one` / `key.other`.
- `es.py` / `en.py`: `MESSAGES: dict[str, str]`, ids namespaced by area (`auth.session_ended`,
  `report.period_not_allowed`, `mail.err.timeout`, `pdf.heading.metric`, …), named
  `{placeholders}` only.
- Request locale: a pure ASGI middleware in `main.py` opens the box per request with
  `Accept-Language` → `DEFAULT_LOCALE`; `auth/deps.py::_lookup` sets the box to `user.locale`
  when the account has one (account wins, spec FR-005 order); `request_locale()` dependency
  returns `current()` for endpoints that pass the locale explicitly (PDF).
- The frontend `api/client.ts` sends `Accept-Language: <active locale>` on every request, so for
  anonymous pages (sign-in, `/s/:token`) and accounts with `locale = NULL` the server language
  equals the screen language.
- `ApiError(status, code, msg: M | str, fields=None, extra=None)`: `code` unchanged (stable, already
  used by the frontend); `M` carries `key` + `params`. Envelope:
  `{"error": {"code", "message", "key"?, "params"?, "fields"?, …extra}}` — `message` rendered in
  `current()` at handler time. `str` is accepted only during the migration; a guard test
  (`backend/tests/test_i18n_catalogue.py`) fails on any string-literal message left in
  `ApiError`/`ReportError`/helper calls. Helpers `forbidden/not_found/validation/unauthenticated`
  default to catalogue ids. Validation `fields` stay codes (`too_long`), mapped by the frontend
  catalogue as today.
- Frontend: shows `error.message` (already in the right language); `api/client.ts` network and
  non-JSON fallbacks come from `t.errors.*`. Mapping by `key` is optional (FR-005 "MAY").
- Domain errors with their own code tables (`MailError`, AI provider errors, `ScheduleError`,
  `PeriodError`, `ExtractError`, Telegram) map code → catalogue id; messages built with free values
  (database error text, names) keep those values as params, never translated.

### D7 — PDFs and emails per recipient (FR-006, SC-004)
- `reports/pdf.py`: `render(…, locale)`; `fmt`, `fmt_change`, `fmt_date` take the locale
  (English: `1,234.56 USD`, `12.3%`, `Sep 29, 2026`); `PERIOD_LABELS`, `MONTHS` and headings
  ("Período", "Comparado con", "Indicador", "Valor", "Anterior", "Variación", footer) from the
  catalogue; report labels through `localized()` (D11). `api/reports.py` and `api/shared.py` pass
  `request_locale()`.
- `mail/send.py::build_message(…, locale)` renders subject defaults, body lines (period, link,
  expiry, footer) and error texts from the catalogue; `mail/settings.py` test email uses the
  requesting super user's locale.
- Worker `mail/sends.py`: recipient locale = `user.locale` for installation users, else
  `DEFAULT_LOCALE` (external addresses and users with NULL). Deliveries of one send are grouped by
  locale; the PDF is rendered **once per locale** (018 SC-003 becomes "equal to the download for
  the same selection and language"). User-typed subject/message are sent as written.
- Subscriptions (`mail/subscriptions.py`): the automatic subject (dashboard name · period label)
  is marked `selection["auto_subject"] = true` (jsonb, no schema change) and rendered per locale
  at send time instead of being frozen in Spanish.
- Audit note `"Correo: {subject}"` becomes structured detail (`detail.subject`) labelled by the
  frontend.

### D8 — Worker messages, audit and Telegram (US2 AC5)
- `engine/runner.py`, `engine/extract.py` (and 019 `engine/direct.py`, 005-A `engine/transform.py`):
  fixed run messages are written as `message_key` + `message_params`; `message` keeps a
  `DEFAULT_LOCALE` rendering for logs/CLI. Each `checks[]` item gains `key` + `params` beside
  `detail`. Run JSON (API) renders `message`/check details from the key in the request locale;
  legacy rows (no key) and free-form errors (`_safe_message`) are shown as recorded.
- Audit: the frontend catalogue labels all 62 `AUDIT_KINDS` (guard test parses
  `backend/app/models.py`); free-form detail values shown as recorded.
- Telegram (`telegram/handler.py`, `service.py`, `api/telegram.py`): message language = linked
  account `locale` → Telegram `from.language_code` (es/en) → `DEFAULT_LOCALE`.

### D9 — Agent and narrative (FR-007)
- `assistant/service.py`: `SYSTEM_PREFIX` becomes `system_prefix(locale)` with `es`/`en` bodies
  (the authoring summary and workspace templates appended unchanged); the reply-language line says
  "always reply in English/español" and, until feature 020, "write specs in the user's language".
  Locale = session owner's `locale` (request locale for interactive turns, stored account value or
  `DEFAULT_LOCALE` for autonomous continuations). Prompt caching gets one cache key per language.
- Fixed chat texts (`_BUDGET_TEXT`, `_CUT_TEXT`, `BUSY_TEXT`, `_READY_TEXT`, …) and user-visible
  readiness/activity/preview messages come from the backend catalogue in that locale; texts already
  stored in a conversation stay as recorded.
- `assistant/readiness.py` personal-data confirmation words gain English (`yes`, `confirm`,
  `include`, `ok`; negations `no`, `exclude`, `without`, `remove`, `omit`) — accepted in both
  languages regardless of locale.
- Model-facing texts that the user never sees (tool descriptions and tool-result texts in
  `assistant/tools.py`, `origin.py` hints, authoring pack, JSON-schema `description`s checked by
  `cli/tests/test_schema_descriptions.py`) stay single-language in 022 — they are not user-visible
  (constitution constraint scope); 020/021/023 decide their own prompt files per language.
- `engine/narrative.py`: `SYSTEM` and fixed prompt lines per locale; inputs unchanged (VIII).
- 021 command prompts / scope refusal and 023 guide ship `es` + `en` files themselves; 022
  provides `i18n.current()` and the system-prompt hook they extend.

### D10 — CLI (FR-008)
- `cli/bizview_cli/i18n/{__init__,es,en}.py` (same shape as the backend, no backend import).
  Resolution: explicit `lang` argument → `BIZVIEW_LANG` → `LC_ALL` / `LC_MESSAGES` / `LANG`
  primary subtag `en` → `es`.
- `validate.py`, `sqlsafety.py`, `authoring.py` (user-facing problems/fixes only), `init.py`,
  `__main__.py` render through it; public functions gain an optional `lang` (or a
  `use_lang()` context manager) so the backend passes the request locale when it validates a
  workspace or checks SQL (`workspace/service.py`, `api/workspace.py`, `assistant/tree.py`,
  `engine/report.py`, `engine/extract.py`, `assistant/origin.py`).

### D11 — Optional English labels in reports (FR-009)
- `report.schema.json`: optional `title_en`, `description_en`, `metrics.*.label_en`,
  `metrics.*.description_en`, `dimensions.*.label_en`, views `title_en` (each `"type": "string"`,
  same length limits, Spanish `description` text like the siblings). Additive: existing workspaces
  stay valid.
- Backend serves the definition unchanged (both fields); frontend helper
  `lib/labels.ts::localized(obj, "title")` returns `obj.title_en` when the locale is `en` and it is
  non-empty, else `obj.title` — so a switch needs no refetch. Backend `i18n.localized()` does the
  same for PDFs and email subjects.
- Authoring pack (`authoring.py` summary) mentions the optional fields.

### D12 — Tests (FR-010, SC-001, SC-002, SC-004)
- `frontend/tests/unit/i18n-parity.test.ts`: recursive key sets of `es`/`en` equal (including
  `Record` maps); leaf kinds equal; function leaves: same arity, and calling both with marker
  arguments (`"⟦0⟧"`, `7`) shows every string marker in both outputs; no empty string; no `en`
  value object-identical to the `es` one (catches spread placeholders); `resolve.ts` cases.
- `frontend/tests/unit/no-literals.test.ts` (model: `no-raw-colors.test.ts`): scans `src/**/*.tsx?`
  outside `src/i18n/`: JSX text nodes with letters, user-visible attributes (`aria-label`,
  `placeholder`, `title`, `alt`, `label`, `text`, `description`, `hint`) with string literals,
  string literals containing Spanish letters/`¿¡`; allow-list for brand names (`BizView`,
  `Bizview AI Powered`, `Telegram`, `PostgreSQL`, `Supabase`, `SOAP`, `REST`, `CSV`, `PDF`), technical
  tokens and code identifiers, per-file exceptions with a reason. Also: no import of `i18n/es`/`en`
  outside `src/i18n/`; every `.tsx` that references `t.` calls `useT()`; no top-level `const` that
  reads `t.` eagerly.
- `frontend/tests/unit/audit-labels.test.ts`: every kind in `backend/app/models.py` `AUDIT_KINDS`
  has a label in both catalogues.
- `backend/tests/test_i18n_catalogue.py` (no DB): key parity, placeholder parity
  (`string.Formatter().parse`), non-empty, every literal id in `M("…")`/`t("…")`/`tn("…")` calls
  under `backend/app` exists (AST scan), no string-literal message passed to `ApiError`,
  `ReportError` or the helpers; Accept-Language parsing.
- Backend behaviour tests: `test_me.py` (locale PATCH 200/422, partial body, null), `test_i18n_api.py`
  (same error in es/en by account and by `Accept-Language`, account wins, default), `test_pdf_layout.py`
  (English PDF: extracted text has no Spanish fixed text — SC-004), `test_mail_send.py` /
  `test_mail_subscriptions.py` (mixed-locale recipients, one PDF per locale, auto subject per
  locale), `test_telegram.py`, `test_runner.py` (message_key rendering), assistant tests with the
  fake provider (system prompt variant, fixed texts, English confirmation words).
- `cli/tests/test_i18n.py`: parity, `BIZVIEW_LANG=en`, `LANG=en_US.UTF-8`, default `es`, explicit
  `lang` wins.
- `frontend/tests/e2e/i18n.spec.ts`: builds the "other-language-only" string sets from `es.ts` and
  `en.ts` (string leaves ≥ 4 chars that are not values of the other catalogue, plus allow-list);
  signs in, switches to English in Perfil, walks every route of `App.tsx` (list shared with
  `theme.spec.ts`, plus `/tableros`, `/admin/asistente`, `/ingresar`, `/s/:token` of a created link)
  and the in-page views (params panel, Compartir, Enviar por correo, Envíos programados, assistant
  panel), asserting `html[lang]` and that `document.body.innerText` contains no Spanish-only
  catalogue string; repeats in Spanish; switch timing < 300 ms with report filters kept
  (SC-003); persistence in a fresh context; sign-in page switch; `afterEach` resets the account
  locale to NULL.

### D13 — Migration strategy (batches)
1. Foundations (backend i18n core, migration, preferences, frontend provider, formatting) land
   first; `ApiError` accepts `str` and `M`, `t` live binding exists, so nothing breaks mid-way.
2. `en.ts` for the existing catalogue in two halves (sections `common…audit`, then `ai…sharing`);
   until the second half lands, the not-yet-translated sections are spread from `es` and the parity
   test's identity check is the reminder.
3. Frontend files in batches of 3–11 files by area (heavy admin pages alone); each batch swaps to
   `useT`, extracts literals into **both** catalogues, and fixes Intl calls.
4. Backend in module groups (auth/me/security, dashboards/reports/sharing, sources, workspace/AI,
   worker, PDF, mail, Telegram, agent ×2); each converts its raises to `M` ids in both catalogues.
5. Guards last (they fail until every batch is done): no-literal test, backend string-literal
   guard, then the e2e walk.
6. Features 020/021/023 (after 022) add every new string to both catalogues from the start.

## Risks

- **Component forgets `useT()`** → its text switches only on the next unrelated re-render. Guard:
  "uses `t.` ⇒ calls `useT()`" in the no-literal test + e2e walk.
- **Eager captures** (module-level constants, memoized values) → stale language. Guard heuristic +
  per-batch review of `useMemo` deps.
- **Contextvars in the threadpool**: values set in sync dependencies are lost in copied contexts →
  mutable per-request box (D6).
- **Existing tests assert Spanish** (backend, Vitest, Playwright): defaults stay Spanish (no
  `Accept-Language` in TestClient → `DEFAULT_LOCALE=es`; Playwright `locale: "es-ES"`).
- **018 PDF-equality test** compares attachment and download; now valid per language.
- **False positives in the e2e walk** (words equal in both languages, authored names like "Ventas"
  matching a catalogue value): only strings unique to one catalogue, ≥ 4 chars, with an allow-list.
- **Translation quality**: English written by the team; one review task reads `en.ts` and
  `backend/app/i18n/en.py` end to end.
- **Scope edge**: model-facing tool texts and schema descriptions stay Spanish (D9); revisit if
  020's editor shows schema descriptions as hover hints.
- **Recipients with `locale = NULL`** get `DEFAULT_LOCALE` emails even if their browser is English
  (no browser exists at send time) — documented in INSTALL.

## Complexity Tracking

No constitution violations; nothing to justify.
