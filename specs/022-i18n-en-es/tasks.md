---
description: "Task list for feature 022 — Interface in Spanish and English (i18n)"
---

# Tasks: Interface in Spanish and English (i18n)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md) (design D1–D13 referenced below)

**Roles**: Claude thinks (spec, plan, tasks, briefs) and audits/converges; DeepSeek executes (writes
all code, translations, tests and fixes). Migration and the request-locale/auth hook: Claude
reviews line by line. Code first, test last: each task runs only its focused cheap checks; full
suites run once at the end of the queue (T046).

**Rules for every task**: every new or moved string goes into BOTH `frontend/src/i18n/es.ts` and
`frontend/src/i18n/en.ts` (frontend) or BOTH `backend/app/i18n/es.py` and `en.py` (backend);
Spanish text is the reference and stays as it is today; authored workspace content is never
translated; no modal dialogs; no customer names; backend tests in `app_test_*` schemas; no live AI
calls (fake providers).

**Frontend batch recipe (T011–T026)** per file: replace `import { t } from "…/i18n/es"` with
`import { useT } from "…/i18n"`; add `const t = useT();` as the first statement of every component
function that reads `t.`; turn module-level values that read `t` into functions or move them into
the component; add `locale` (from `useLocale()`) to `useMemo`/`useCallback` deps whose result holds
catalogue text; move every hard-coded user-visible literal to the catalogue; replace `"es"` passed
to `Intl`/`toLocale*` with the `lib/numbers.ts`/`lib/format.ts` helpers (D2, D4). Check: `npx tsc -b`
and the Vitest files that cover the batch.

## Phase 1: Foundational (blocks every story)

- [X] T001 Migration backend/alembic/versions/0017_user_locale.py (down_revision = current head: 0016_run_transform if present, else 0015_direct_reports): `app_user.locale text NULL` + CHECK `locale IN ('es','en')`, `integration_run.message_key text NULL`, `integration_run.message_params jsonb NULL`; downgrade drops them; backend/app/models.py `LOCALES`, `AppUser.locale`, `IntegrationRun.message_key/message_params`; up/down test in backend/tests/test_migrations.py per FR-003, US2 AC5
- [X] T002 [P] Setting `DEFAULT_LOCALE` (`es`|`en`, default `es`, validated) in backend/app/config.py; `default_locale` in `GET /api/config` (backend/app/api/health.py); .env.example and docs/INSTALL.md (setting, resolution order, NULL-locale recipients get DEFAULT_LOCALE); test in backend/tests/test_bootstrap.py or a new backend/tests/test_i18n_api.py per FR-002, FR-006
- [X] T003 [P] Backend i18n core backend/app/i18n/__init__.py (SUPPORTED, normalize, from_accept_language with q-values, per-request mutable box in a contextvar, current(), use_locale() context manager, t(key, **params) with es→key fallback logging a missing id once, tn() plural `.one/.other`, lazy class M(key, **params), localized(obj, field, locale) for `_en` labels) + backend/app/i18n/es.py and en.py with `MESSAGES: dict[str, str]` holding the generic ids (common.unexpected, auth.session_ended, common.forbidden, common.not_found, common.validation, http.*) ; pure unit tests in backend/tests/test_i18n_core.py per FR-005, D6
- [X] T004 Request locale + error envelope: pure ASGI middleware in backend/app/main.py opens the box (Accept-Language → DEFAULT_LOCALE); backend/app/auth/deps.py `_lookup` sets the box to `user.locale` when not NULL; `request_locale()` dependency in backend/app/i18n/__init__.py; backend/app/errors.py: `ApiError(status, code, msg: M | str, …)`, helpers default to catalogue ids, handlers render `message` in `current()` and add `key`/`params` when `msg` is `M`; RequestValidationError/404/500 messages from the catalogue; tests in backend/tests/test_i18n_api.py (same error in es and en by account, by Accept-Language, account wins over header, default) per FR-005, US2 AC1
- [X] T005 `PATCH /api/me/preferences` partial update in backend/app/api/me.py + backend/app/api/schemas.py (`theme` and `locale` optional, `locale: null` = browser, only fields present are written, empty body 422, `extra="forbid"`), `user_json` carries `locale`; tests in backend/tests/test_me.py (200 / 401 / 422, theme-only body still works, null, idempotent, allowed with temporary password) per FR-003
- [X] T006 Frontend catalogue split: frontend/src/i18n/es.ts exports `es` and `type Catalogue = typeof es` (content unchanged); frontend/src/i18n/en.ts `export const en: Catalogue` with sections `common` … `audit` translated to US English and the remaining sections temporarily spread from `es`; frontend/src/i18n/resolve.ts (pure: account → device cache `bizview.locale` → navigator.languages es/en → default_locale → es; intlTag es-ES/en-US); frontend/src/api/types.ts `User.locale`, `PublicConfig.default_locale`, `Locale`, `LocalePreference` per FR-001, FR-002
- [x] T007 frontend/src/i18n/en.ts second half: translate sections `ai` … `sharing` (all remaining), no section left spread from `es` per FR-001
- [x] T008 frontend/src/i18n/index.tsx: live binding `export let t`, `LocaleContext` (default `es`), `LocaleProvider` (mirror of frontend/src/theme/ThemeContext.tsx: device cache, account wins after /api/me and is written to the device cache, serialized PATCH queue, last response wins, toast on failure keeps the applied language, one-time PATCH of the device choice after sign-in when the account locale is NULL), `useT()`, `useLocale()`, sets `document.documentElement.lang`; mount in frontend/src/App.tsx beside ThemeProvider; frontend/public/theme-init.js also sets `<html lang>` pre-paint from the cache/browser; frontend/index.html noscript text in both languages; unit tests frontend/tests/unit/locale-provider.test.ts and resolve cases per FR-002, FR-011, US1 AC2
- [x] T009 frontend/src/api/client.ts: send `Accept-Language` with the active locale on every request; network / non-JSON fallbacks from the live `t` (`t.errors.*`); frontend/src/lib/numbers.ts, frontend/src/lib/format.ts, frontend/src/lib/autoRefresh.ts: replace `LOCALE` constants and module-level `Intl` formatters with `intlTag()` + a formatter cache, `formatChange` "Nuevo" → `t.common.new`; English cases in frontend/tests/unit/numbers.test.ts and frontend/tests/unit/auto-refresh.test.ts per FR-004, US1 AC4

**Checkpoint**: backend speaks both languages for generic errors; frontend switches language
for every component that already calls `useT()`.

## Phase 2: User Story 1 — Each user chooses the language (P1) 🎯 MVP

**Goal**: Perfil → Idioma and the account menu switch every screen at once; sign-in and shared
view offer a device switch. **Independent test**: switch in Perfil, walk routes, sign in elsewhere.

- [x] T010 [US1] frontend/src/components/LanguageSwitcher.tsx (radiogroup Español / English / Idioma del navegador, 44 px targets, compact variant Español / English for public pages); "Idioma" card in frontend/src/pages/Profile.tsx; entry in the account menu of frontend/src/components/AppShell.tsx; compact switch on frontend/src/pages/SignIn.tsx and frontend/src/pages/SharedDashboard.tsx; unit test frontend/tests/unit/language-switcher.test.tsx per US1 AC1, AC3, edge "shared links"
- [x] T011 [P] [US1] Batch shell & primitives (recipe): frontend/src/components/{AppShell,BackLink,Breadcrumbs,CopyButton,View,Spinner,SecretField,SourceFooter}.tsx per FR-001, FR-010
- [x] T012 [P] [US1] Batch account primitives (recipe): frontend/src/components/{PasswordField,PasswordRules,ReauthDialog,ThemeSwitcher,TwoFactorCard,UserBadges,RoleTiles,MultiSelect}.tsx per FR-001, FR-010
- [x] T013 [P] [US1] Batch home & Telegram (recipe): frontend/src/components/{DashboardCatalog,DashboardShortcuts,OverviewTiles,WelcomeBanner,StatTile,TelegramAdminCard,TelegramCard,TelegramSignInPanel}.tsx (soonBadge and errorText become render-time) per FR-001, FR-004
- [x] T014 [P] [US1] Batch report controls (recipe): frontend/src/components/report/{AutoRefreshControl,CardMenu,ContextBlock,ExportSection,ParamsForm,ParamsPanel}.tsx per FR-001, FR-004
- [x] T015 [P] [US1] Batch report display (recipe): frontend/src/components/report/{TvLayout,Narrative,TrendChart,RankingTable,KpiGrid}.tsx (literals "Resumen con IA", "Ver datos", "Desde", "Anterior", "Sin datos en el período.", "Indicadores") per FR-001, FR-004
- [x] T016 [P] [US1] Batch sharing (recipe): frontend/src/components/sharing/{EmailSendPanel,RecipientPicker,ShareLinksPanel,SubscriptionsPanel}.tsx + frontend/src/lib/sharing.ts (live `t` import) per FR-001
- [x] T017 [P] [US1] Batch assistant 1 (recipe): frontend/src/components/assistant/{AgentMap,AssistantChat,AssistantHistory,AssistantPanel,AssistantToggle,BudgetNotice}.tsx (AgentMap and AssistantHistory dates via format helpers) per FR-001, FR-004
- [x] T018 [P] [US1] Batch assistant 2 (recipe): frontend/src/components/assistant/{EditableTitle,ProblemList,Readiness,RunStatus,SessionIndicator,WorkingNotes}.tsx per FR-001
- [x] T019 [P] [US1] Batch user pages (recipe): frontend/src/pages/{ChangePassword,DashboardGate,Dashboards,Forbidden,Home,NotFound,Profile,TwoFactorSetup}.tsx per FR-001
- [x] T020 [P] [US1] Batch report & public pages (recipe): frontend/src/pages/{ReportView,SharedDashboard,SignIn}.tsx + frontend/src/lib/{reportQuery,schedule,csv}.ts (live `t` import) + frontend/src/theme/ThemeContext.tsx per FR-001
- [x] T021 [P] [US1] Batch admin 1 (recipe): frontend/src/pages/admin/{AdminHome,Users,UserForm,UserDetail,AI}.tsx (AdminHome ENTRIES → function of `t`, tile texts to the catalogue) per FR-001
- [x] T022 [P] [US1] Batch Audit (recipe): frontend/src/pages/admin/Audit.tsx + labels for all 62 `AUDIT_KINDS` of backend/app/models.py in `audit` of both catalogues; structured mail detail label (`detail.subject`); frontend/tests/unit/audit-labels.test.ts parses models.py per US2 AC5, FR-010
- [x] T023 [P] [US1] Batch sources (recipe): frontend/src/pages/admin/{SourceForm,Sources}.tsx (~55 literals) per FR-001
- [x] T024 [P] [US1] Batch workspace & security (recipe): frontend/src/pages/admin/{Workspace,Security,Tokens}.tsx (~70 literals; SPEC_TAB_LABELS → render-time) per FR-001
- [x] T025 [P] [US1] Batch integrations & assistant pages (recipe): frontend/src/pages/admin/{Integrations,AssistantPage,AssistantSession}.tsx (run status badges, DRAFT_GROUPS labels) per FR-001
- [x] T026 [US1] Sweep: every remaining importer of `i18n/es` or hard-coded literal, including files added by features 019 and 005-A (`grep -rl "i18n/es" frontend/src`), converted with the recipe; only frontend/src/i18n/index.tsx imports es.ts/en.ts per FR-001, FR-010

**Checkpoint**: whole UI switchable; e2e walk (T043) can run.

## Phase 3: User Story 2 — Server messages, PDFs, emails and the agent (P1)

**Goal**: everything the server produces follows the requester's/recipient's language.
**Independent test**: account in English → validation error, sign-in error, PDF, email to fake
SMTP, chat message with the fake provider are English; repeat in Spanish.

- [x] T027 [P] [US2] Backend batch auth/me/security: backend/app/errors.py helpers, backend/app/auth/deps.py, backend/app/api/auth.py, backend/app/api/me.py, backend/app/security/{throttle,netguard,middleware}.py, backend/app/services/users.py → `M` ids in both catalogues; extend backend/tests/test_i18n_api.py (sign-in error, locked, MFA conflict in en) per FR-005
- [X] T028 [P] [US2] Backend batch dashboards/reports/sharing: backend/app/services/dashboards.py, backend/app/sharing/links.py, backend/app/api/{reports,shared,sharing,dashboards}.py, backend/app/engine/report.py (`ReportError(M, status, code)`, 14 sites), backend/app/engine/periods.py (`PeriodError` codes → ids) per FR-005
- [X] T029 [P] [US2] Backend batch sources: backend/app/sources/{schemas,service,describe}.py, backend/app/sources/connectors/{__init__,base,postgresql,rest}.py, backend/app/api/sources.py (type field labels from `/api/sources/types` rendered per request locale) per FR-005
- [X] T030 [P] [US2] Backend batch workspace/admin/AI: backend/app/workspace/service.py, backend/app/api/{workspace,admin,tokens,security,assistant}.py, backend/app/engine/schedule.py (`ScheduleError` codes → ids), backend/app/ai/{__init__,service,openai_compatible}.py (provider error table) per FR-005
- [X] T031 [US2] Worker run messages: backend/app/engine/{runner,extract,datasets}.py, backend/app/worker.py and, when present, backend/app/engine/direct.py (019) and backend/app/engine/transform.py (005-A) write `message_key`/`message_params` and `checks[].key/params` (keep `message` rendered in DEFAULT_LOCALE); run JSON renders from the key in the request locale, legacy rows and free-form errors as recorded; tests in backend/tests/test_runner.py per US2 AC5
- [X] T032 [US2] PDF: backend/app/reports/pdf.py `render(…, locale)`, `fmt/fmt_change/fmt_date` per locale (en: `1,234.56 USD`, `12.3%`, `Sep 29, 2026`), period labels, months, headings and footer from the catalogue, report labels via `i18n.localized`; backend/app/api/reports.py and backend/app/api/shared.py pass `request_locale()`; tests in backend/tests/test_pdf_layout.py and backend/tests/test_reports_params.py (English PDF text contains no Spanish fixed text) per FR-004, FR-006, US2 AC2, SC-004
- [X] T033 [US2] Mail: backend/app/mail/send.py `build_message(…, locale)` and error-code texts from the catalogue; backend/app/mail/settings.py test email in the requester's locale; backend/app/mail/sends.py worker groups deliveries by recipient locale (user.locale, else DEFAULT_LOCALE; externals DEFAULT_LOCALE), renders the PDF once per locale, audit detail `subject` structured; backend/app/mail/subscriptions.py `selection["auto_subject"]` rendered per locale; tests with the fake SMTP in backend/tests/{test_mail_send,test_mail_subscriptions,test_mail_settings}.py (mixed es/en recipients, SC-004 on bodies) per FR-006, US2 AC3
- [X] T034 [P] [US2] Telegram: backend/app/telegram/{handler,service}.py, backend/app/api/telegram.py — language = linked account locale → Telegram `from.language_code` → DEFAULT_LOCALE; tests with backend/tests/fake_telegram.py in backend/tests/test_telegram.py per US2 AC3
- [X] T035 [US2] Agent core: backend/app/assistant/service.py `system_prefix(locale)` (es/en bodies, reply-language line, specs written in the user's language until 020) and fixed chat texts (`_BUDGET_TEXT`, `_BUDGET_HINT`, `_CUT_TEXT`, `_EMPTY_TEXT`, `_INVALID_ARGS_TEXT`, `BUDGET_WARNING_LINE`, `BUSY_TEXT`, `CAPACITY_TEXT`, `_INTERRUPTED_TEXT`, `_STOPPED_TEXT`, `_UNEXPECTED_TEXT`, `_READY_TEXT`, `_REPEATED_TEXT`, 14 ApiError sites) from the catalogue in the session owner's locale; backend/app/engine/narrative.py SYSTEM and fixed lines per locale; tests with the fake provider in backend/tests/{test_assistant_loop,test_ai}.py (prompt variant per locale) per FR-007, US2 AC4
- [X] T036 [US2] Agent user-visible messages: backend/app/assistant/{readiness,activity,preview,tree,origin}.py messages shown in the UI → catalogue in the session owner's locale (model-facing tool descriptions and tool-result hints stay as they are, plan D9); readiness confirmation words accept English (yes/confirm/include/ok; no/exclude/without/remove/omit); tests in backend/tests/{test_assistant_readiness,test_assistant_preview,test_assistant_activity}.py per FR-007
- [X] T037 [US2] Backend guard backend/tests/test_i18n_catalogue.py (no DB): es/en key parity, placeholder parity, no empty value, every literal id in `M(`/`t(`/`tn(` calls under backend/app exists (AST), no string-literal message passed to `ApiError`, `ReportError` or `forbidden/not_found/validation/unauthenticated`; then remove the transitional `str` branch from backend/app/errors.py per FR-010, US3 AC2, SC-002 — *done 2026-10-11: the guard bans literal messages; `ApiError` keeps `M | str` only for runtime texts that are already rendered with `t()` or come from external systems (redacted source errors, AI provider errors), see backend/tests/test_i18n_catalogue.py*

## Phase 4: User Story 3 — Nothing is left untranslated (P2)

**Goal**: guards make a missing translation fail the build or the tests.
**Independent test**: delete one `en` key, add a JSX literal, add a backend raw message → tests fail.

- [X] T038 [P] [US3] CLI i18n: cli/bizview_cli/i18n/{__init__,es,en}.py (explicit lang → BIZVIEW_LANG → LC_ALL/LC_MESSAGES/LANG → es; `use_lang()`); messages of cli/bizview_cli/{validate,sqlsafety,authoring,init,__main__}.py through it; tests cli/tests/test_i18n.py (parity, env cases, default es) and existing cli/tests stay green in Spanish per FR-008, US3 AC3
- [X] T039 [US3] Backend passes the request locale to the CLI validator and SQL checks: backend/app/workspace/service.py, backend/app/api/workspace.py, backend/app/assistant/tree.py, backend/app/engine/report.py, backend/app/engine/extract.py, backend/app/assistant/origin.py; test that a workspace validation problem comes back in English for an English account (backend/tests/test_vibe_reporting.py) per FR-005, FR-008
- [X] T040 [US3] Optional English report labels: cli/bizview_cli/schemas/report.schema.json (`title_en`, `description_en`, `metrics.*.label_en`, `metrics.*.description_en`, `dimensions.*.label_en`, views `title_en`, Spanish descriptions like siblings), cli/bizview_cli/authoring.py summary mentions them, cli/tests/test_validate.py + cli/tests/test_schema_descriptions.py cases; frontend/src/lib/labels.ts `localized(obj, field)` used by the report components, dashboard catalogue and shared view; backend `i18n.localized` in PDF and email subjects (T032/T033 call sites) per FR-009, edge "authored content"
- [x] T041 [P] [US3] frontend/tests/unit/i18n-parity.test.ts: recursive key parity incl. `Record` maps, leaf-kind parity, function arity + marker-argument placeholder parity, non-empty values, no `en` value object-identical to `es` per FR-010, SC-002
- [x] T042 [US3] frontend/tests/unit/no-literals.test.ts (modelled on no-raw-colors.test.ts): JSX text, user-visible attributes, Spanish-letter literals outside src/i18n, allow-list (brand and technical tokens) with reasons, no import of i18n/es|en outside src/i18n, `t.` ⇒ `useT()` in .tsx, no top-level eager `t.` capture, document titles carry no catalogue text; fix any hit it finds per FR-010, FR-011, US3 AC1
- [X] T043 [US3] frontend/tests/e2e/i18n.spec.ts: other-language-only string sets from es.ts/en.ts (≥ 4 chars, allow-list); English walk over every route of frontend/src/App.tsx (shared list with frontend/tests/e2e/theme.spec.ts + /tableros, /admin/asistente, /ingresar, /s/:token of a created link) and the in-page views (params panel, Compartir, Enviar por correo, Envíos programados, assistant panel) asserting `html[lang]` and no Spanish-only string; same walk in Spanish; switch < 300 ms keeping report filters; persistence in a fresh context; sign-in page device switch saved to the account after sign-in; afterEach resets account locale to NULL per SC-001, SC-003, US1 AC1–AC3

## Phase 5: Polish

- [X] T044 [P] Translation review: read frontend/src/i18n/en.ts, backend/app/i18n/en.py and cli/bizview_cli/i18n/en.py end to end for consistent US English terminology (Dashboard, Report, Integration, Source, Workspace, Share link, Scheduled send) and fix; glossary as a comment at the top of each en file per Assumptions
- [X] T045 [P] Docs: CHANGELOG.md (i18n, DEFAULT_LOCALE, `_en` labels, Accept-Language), docs/INSTALL.md (language resolution, emails for NULL-locale users), docs/VIBE-REPORTING.md (`*_en` labels), CLI help text for BIZVIEW_LANG in cli/bizview_cli/__main__.py per FR-008, FR-009
- [X] T046 Full suites deferred to the end of the queue (backend pytest on DATABASE_URL_BI, CLI pytest, Vitest, `npm run build`, Playwright all projects) + `/speckit-converge`

## Dependencies & Execution Order

- T001 → T005, T031. T003 → T004 → T027–T037, T039. T002 → T008 (default_locale).
- T006 → T007 → T008 → T009 → T010–T026 (frontend batches are mutually parallel [P]; each edits
  different component files but appends to the same catalogues — merge catalogue hunks by
  section, run them sequentially when executed by one agent).
- T026 after T011–T025. T041 after T007. T042 after T026 (fails until all batches are done).
- T043 after T010, T026, T032 (shared view PDF) and T040.
- T032, T033 after T028 (period ids) and T040 for `localized` (or add the helper call later).
- T037 after T027–T036. T038 → T039. T046 last.

## Parallel Opportunities

- Phase 1: T002 ∥ T003 ∥ T006 (backend vs frontend).
- US1: T011–T025 in parallel by file group once T008/T009 exist.
- US2: T027 ∥ T028 ∥ T029 ∥ T030 ∥ T034; agent tasks T035 → T036.
- US3: T038 ∥ T041; backend and frontend tracks fully independent until T043.

## Implementation Strategy

MVP = Phase 1 + US1 (whole UI switchable, account preference, sign-in/shared switch). Then US2
(server texts follow the language), then US3 guards and the e2e walk, which close the feature.
Features 020/021/023 start only after T037/T042 so their strings are bilingual from the start.

## Phase 6: Convergence

- [X] T047 Move the remaining user-visible fixed chat texts of backend/app/assistant/service.py to backend/app/i18n/{es,en}.py and render them in the session owner's locale: `_composed_progress` labels ("Hecho:", "Siguiente:", "seguir con el borrador", "nada todavía"), the `_budget_stop` headline "Progreso hasta ahora:", the `_progress` fallback "Llegué al límite de {max_rounds} rondas en este mensaje.", the invalid-arguments turn summary "Argumentos no válidos en {name}." (it reaches the progress message), the `_READY_TEXT` summary fallback "el borrador"; make `_progress_prompt` ask for the Done/Next labels in the reply language and the "continúa" check accept the English hint; fake-provider test in backend/tests/test_assistant_loop.py for an English account per FR-007, US2 AC4 (partial)
- [X] T048 Show the default conversation title in the viewer's language: `DEFAULT_TITLE = "Nueva conversación"` (backend/app/assistant/service.py) is stored and returned as the title of a new chat and appears in the conversation picker of frontend/src/pages/projects/ProjectWorkspace.tsx for English users; render it per request locale where titles are serialized (`display_title`, project/session JSON) or let the frontend use `t.assistant.newConversation`, keeping the sentinel comparison working; test in backend/tests per FR-007, US2 AC4 (partial)
- [X] T049 Localize `period_label` of the subscription JSON (backend/app/mail/subscriptions.py `pdf.PERIOD_LABELS.get(...)`, always Spanish) in the request locale via the `pdf.period.*` catalogue ids, or render it in frontend/src/components/sharing/SubscriptionsPanel.tsx from the frontend period labels; English case in backend/tests/test_mail_subscriptions.py per FR-004, US1 AC4 (partial)
- [X] T050 Render the automatic subject of subscription sends in the request locale in the send-history JSON (backend/app/mail/sends.py list/detail return the stored Spanish `send.subject`, frozen in backend/app/mail/subscriptions.py as "{dashboard} · {Spanish period}") using `_subject()`/`selection.auto_subject`, so frontend/src/components/sharing/EmailSendPanel.tsx history is not Spanish for English users; test in backend/tests/test_mail_subscriptions.py per FR-006, US2 AC3, plan D7 (partial)
- [X] T051 Replace the hard-coded "ahora" of `relativeTime` in frontend/src/components/assistant/AssistantHistory.tsx (shown in the assistant history and in frontend/src/components/DashboardShortcuts.tsx on Home) with a catalogue text in both es.ts and en.ts; update frontend/tests/unit/assistant-history.test.tsx with an English case and extend frontend/tests/unit/no-literals.test.ts so returned/ternary Spanish word literals without accents are caught per FR-004, FR-010, US1 AC4 (partial)

## Closure 2026-10-12

The five convergence tasks above are implemented and covered by the tests they name
(`backend/tests/test_i18n_assistant.py` T047/T048, `test_assistant_loop.py::
test_round_limit_progress_follows_an_english_account` T047 — its continue-hint regression fixed on
2026-10-12 —, `test_mail_subscriptions.py` T049/T050, `frontend/tests/unit/assistant-history.test.tsx`
T051). Feature closed: backend, CLI, frontend and e2e suites green.
