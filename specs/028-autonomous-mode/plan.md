# Implementation Plan: Autonomous mode for the Asistente

**Branch**: `028-autonomous-mode` | **Date**: 2026-10-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/028-autonomous-mode/spec.md`

## Summary

Give the Asistente a per-conversation **mode** (`ask` | `edit` | `auto`) that the tool layer enforces,
and let **Auto** run the whole pipeline on its own: one message, one step-up-confirmed **run
contract**, then discover → write specs and artifacts → validate → preview → fix → **apply** → report,
with a bounded budget and a cooperative stop. Three moving parts:

1. **Mode** as a column on `assistant_session`, changed only by the composer selector, enforced in
   `assistant/tools.py` (offer list + `run_tool`), never by prompt instructions (FR-000, FR-003).
2. **Run contract** as a row in a new `assistant_auto_run` table: allowed sources/tables, allowed
   stages, limits (tokens, previews, applies, wall clock), `modify_existing`, `auto_rollback`,
   `visible_to`, confirmed once with step-up; that confirmation authorises every apply inside the run
   (FR-001, FR-002).
3. **Stage chaining**: `run_command`, `set_current_spec`, `run_preview` and `apply_draft` become
   contract-gated tools, so an Auto run is a chain of ordinary, audited command runs and one apply
   (FR-004, FR-004b, SC-008).

The command-routing defect (FR-000c) is already on `main` (`commands/resolve.py`, `set_current_spec`,
`misrouted`/`budget` run statuses, migration 0023); this plan keeps the session-18 replay as the
regression test rather than re-implementing it.

## Technical Context

**Language/Version**: Python 3.12 (backend, CLI); TypeScript 5 / React 19 (frontend).

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic, pydantic 2, psycopg 3, APScheduler,
ReportLab; React + Tailwind + Vite; Playwright. No new dependency: the run contract is JSONB
validated with pydantic, the prompt/authoring defaults live in `cli/bizview_cli`.

**Storage**: PostgreSQL (product DB from `DATABASE_URL_BI`); the customer's project files under the
installation's `projects/` folder (the Asistente edits those, not the repository's own `specs/`).

**Testing**: pytest in `backend/` and `cli/` (fake provider + recorded transports; no live AI),
vitest in `frontend/`, Playwright e2e at 320/375 px. `AI_LIVE_TESTS=1` gates SC-001 only.

**Target Platform**: Linux server (single backend process with an in-process agent runner thread),
mobile-first web at 320 px, WCAG 2.2 AA, Spanish and English.

**Project Type**: web application (backend + frontend) plus the `cli/` authoring package.

**Performance Goals**: no extra provider round per stage (a stage switch is one tool call); the
contract status bar polls at the existing 1–2 s cadence; apply time unchanged (same
`projects.apply.apply_project`); a run stays within `AI_AUTO_RUN_MAX_SECONDS` (default 1800).

**Constraints**: AI stays off by default and no new data reaches the provider (VIII); step-up on the
`internet` profile needs password **and** TOTP; limits and stages are enforced by product code, never
by the model; the 015/017 data boundary, read-only SQL, draft path limits, workspace lock and rollback
are untouched (FR-012).

**Scale/Scope**: one installation's super users; concurrency already capped by
`AI_AGENT_MAX_CONCURRENT`; 3 modes, 6 user stories, 12 functional requirements groups, one migration.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Verdict |
|---|---|---|
| I. Mobile-first | Selector is a segmented control above the composer at 375 px, reachable by Tab and arrow keys (SC-009). | PASS |
| II. Backend as ETL | The agent only edits declarative specs/artifacts in a project; apply re-validates and the engine still builds `ds_<integration>`. | PASS |
| III. Source of truth external | Origin access keeps the read-only session + `statement_timeout`; the contract *narrows* source access, never widens it. | PASS |
| IV. Separated folders | All new code in `backend/app/assistant/`; the authoring defaults stay in `cli/bizview_cli`; no customer data in the repo. | PASS |
| V. Fixed stack | No new component or library: JSONB + pydantic + the existing scheduler and preview worker. | PASS |
| VI. Data tuning | Unchanged. | PASS |
| VII. One product | Mode, contract limits and profiles are settings/rows per installation, not a fork. | PASS |
| VIII. AI optional and private | A run adds no new provider input: it reuses the same tools and the same `sanitize()` layer. The contract's `sources`/`tables` allow-list is a *reduction*. | PASS |
| IX. Spec-driven | "No spec, no run" and the readiness gate stay; the human approval moves from per-apply to per-run, which the spec justifies and this plan records in Complexity Tracking. | PASS (see below) |
| Constraints | Credentials untouched; `internet` step-up adds the TOTP code; Alembic 0024; worker idempotent (rollback is a normal version switch). es/en strings for every new text. | PASS |

**Post-design re-check**: see the end of this plan — no new violations, one justified deviation
(014 FR-006 per-apply → per-run step-up).

## Design

### 1. Mode on the conversation (`assistant_session.mode`)

- Migration `0024_autonomous_mode` adds `assistant_session.mode TEXT NOT NULL DEFAULT 'edit'` with
  `CHECK (mode IN ('ask','edit','auto'))`. The conversation's contract is its newest
  `assistant_auto_run` row (`ix_auto_run_session`); a back-reference column would make the FK a
  table cycle and stop Alembic's `compare_metadata` from checking either table's foreign keys.
- `POST /sessions/{id}/mode` (`api/assistant.py`) validates the value, audits
  `assistant_mode_changed`, and — when the new mode is lower than the current one and a run is in
  flight — calls the existing `service.stop()` so an Auto run is braked exactly as "Detener" (FR-007,
  US2/AC1). Switching **to** `auto` only stores an intent: the mode becomes `auto` when the contract
  is confirmed (see §2).
- `service.session_json` exposes `mode` and the contract's public face (`contract`,
  `contract_status`, `stage`, `limits_used`) so the header pill, the conversation list and the status
  bar read the same payload (FR-000, FR-006).
- The mode is not a lock: `mode='auto'` without a live contract (`confirmed`/`running`) refuses
  `run_preview`/`apply_draft`, so a spent contract cannot apply anything (Q1 of the clarifications).

### 2. Run contract (`assistant_auto_run` + `assistant_run_profile`)

New table `assistant_auto_run` (one row per run, the contract **and** its outcome):

| Column | Type | Note |
|---|---|---|
| `id` | BIGINT identity | |
| `session_id` | BIGINT FK `assistant_session` CASCADE | |
| `project_id` | BIGINT FK `project` CASCADE | |
| `contract` | JSONB NOT NULL | goal, sources/tables, stages, limits, `modify_existing`, `auto_rollback`, `visible_to`, `profile_id` |
| `status` | TEXT | `confirmed` \| `running` \| `applied` \| `stopped` \| `failed` |
| `stop_reason` | TEXT NULL | `limit:tokens`, `limit:previews`, `limit:applies`, `limit:wall_clock`, `stopped:user`, `stopped:mode`, `revoked:role`, `blocked:<reason>`, `error:<code>` |
| `stage` | TEXT NULL | last stage reached (`discover`, `specify`, `plan`, `tasks`, `implement`, `preview`, `apply`) |
| `previews` / `applies` | INTEGER | counters enforced by the gate |
| `tokens` | INTEGER | charged from the existing `_count_usage` |
| `version_id` | BIGINT FK `workspace_version` NULL | the applied version |
| `summary` | JSONB NULL | version, ids, schedule, decisions, preview rows, tokens (FR-004/US1 AC4) |
| `watch_integration` | TEXT NULL, `watch_state` TEXT NULL | post-apply watch (FR-008) |
| `confirmed_by` / `confirmed_at` / `confirmed_ip` | BIGINT / timestamptz / INET | the single step-up |

`POST /sessions/{id}/contract` — body `{contract, password, code?}`; re-verifies the password exactly
like `/auth/reauth` (`passwords.verify_password` behind `throttle.check` and `users.is_locked`) and,
when `security.profile.mfa_required_for(role)` is true (`internet` + admin), the TOTP code with
`security.mfa.verify_code`. It validates the contract with pydantic (`RunContract`), writes the row
as `confirmed`, sets `session.mode='auto'`, inserts the contract as a
transcript line (chips, 014 FR-007) and audits `assistant_contract_confirmed`. Cancelling the dialog
changes nothing (no row, mode untouched).

`assistant_run_profile` (US5): `id`, `name` (unique, ≤ 60), `contract` JSONB, `created_by`,
`created_at`, `updated_at`, `deleted_at`. CRUD under `Administración → Asistente → Perfiles de
ejecución`; using a profile only prefills the dialog — the step-up is still required (FR-011).

### 3. Enforcement in the tool layer (FR-000, FR-003)

Two functions in `backend/app/assistant/tools.py` own the decision:

- `offered_tool_specs(view, settings)` — filters by mode before the model sees the tools:
  `ask` → `ASK_TOOLS` (the read set), `edit` → today's `guard.allowed_tools(...)`, `auto` with a
  live contract → the same plus `run_command`, `run_preview`, `apply_draft`, `set_current_spec`,
  clipped to the contract's stages (`stages=['draft']` hides preview/apply).
- `run_tool(...)` — after `guard.check_tool`, `mode_gate(view, name, args, contract)` raises
  `ToolError` with a localized code (`assistant.mode_ask_refused`, `assistant.contract_required`,
  `assistant.contract_source_not_allowed`, `assistant.contract_stage_not_allowed`,
  `assistant.contract_limit_reached`). Refusals are chips in the transcript (US3/AC2, US6/AC1).

`ASK_TOOLS` is the read set confirmed in the clarifications: `DISCOVERY_TOOLS` +
`get_app_guide` + `get_project_overview` + `read_draft` + `check_query` **without** `path`
(`is_discovery()` already draws that line). `update_notes`, `propose_draft`, `edit_draft`,
`run_preview`, `apply_draft`, `finish_command` and `suggest_command` are not offered in `ask`.

**Product code, not prose**: the contract's source allow-list is checked in `_dispatch` for
`list_sources`/`describe_source`/`profile_source`/`check_query` by source name (and table, when the
call names one), so injected text in source metadata cannot widen it (SC-003, US3/AC2).

### 4. The Auto loop (`assistant/service.py`)

- `_turn` reads the live contract into the turn state (`view.session.auto_run`, `autonomous=True`;
  the tools already receive the `WorkView`, which carries `session` and `command_run`) and asks
  `offered_tool_specs` for the Auto set. The system context gains a `## Modo` block (es/en):
  the mode, what it allows, the contract's stages and limits, and — in Auto — the rule "do not end
  the run asking the human; take the documented default and record it" (FR-000b, FR-004b, FR-005).
- The per-message round ceiling (`ai_chat_max_rounds`, the local `max_rounds` of `_turn`) becomes
  `AI_AUTO_MAX_ROUNDS` (default 200) while a contract is live, and `_progress()` is skipped in
  Auto: the run continues until it is done, stopped, or hits a contract limit (FR-004).
- **`run_command(spec, command, arguments?)`** performs a *stage switch*: it closes the current
  `assistant_command_run` if any, creates the next one through the same `runs.create(...)` +
  `registry` guard the composer uses (with `resolved_from` set), points `view.command_run` at it
  and returns the stage's context (the command's prompt, its tool set, the spec's stage) to the
  model. The transcript shows "Auto · /speckit-plan 002-ventas-facturacion". No nested provider
  loop, no second claim (research R5). `set_current_spec` is called in the same step.
- **`run_preview()`** is the tool that already exists: it runs
  `preview.run_draft_preview(db, session, time_limit_s=120)` inline and bumps
  `session.stats['previews']`. Auto adds only the contract gate (stage `preview`, `limits.previews`
  never above `AI_CHAT_MAX_PREVIEWS`, and a per-run counter). The human button keeps its queued
  worker path (`request_preview` / `drop_for_session`), so FR-007's "pending preview requests are
  cancelled" continues to describe that path.
- **`apply_draft()`** calls `service.apply_draft` → `projects.apply.apply_project` with
  `source="chat:<id>:auto"`: identical re-validation, readiness gate, workspace lock, version row
  and documents as the button (SC-004). It is refused unless the contract allows `apply` and
  `applies < max_applies`, and it increments the counter.
- **Ending a run** is one function, `_finish_auto_run(db, session, run, status, reason, summary)`:
  it stores the summary, the reason code, the counters and the audit entries (`assistant_run_started`,
  `assistant_run_stopped`/`applied`), and clears `session.busy_since`. A post-turn check
  (`_auto_blocked_reason`) inspects the final assistant message; if it asks the human to pick a spec
  or press "Aplicar" while the contract allowed `apply`, the run is stored as `blocked:<reason>` and
  the message is replaced by the summary (FR-004b, SC-007).
- Limits are checked at the top of every round and before every gated tool: tokens (`_count_usage`
  vs the contract's budget and `AI_CHAT_BUDGET_MAX`), previews (the contract's `limits.previews`,
  capped by `AI_CHAT_MAX_PREVIEWS`), applies,
  and wall clock (`AI_AUTO_RUN_MAX_SECONDS`, measured from `confirmed_at`). Reaching one calls
  `_finish_auto_run(..., 'stopped', 'limit:<name>')`.
- `service.stop()` and the mode switch-down clear `session.busy_since`, which `_commit_round`
  already turns into `_ClaimLost`; the Auto run also marks the contract `stopped:user` /
  `stopped:mode` and leaves the draft and working state untouched (FR-007, SC-002).
- A role downgrade is caught by the existing super-user dependency on the next HTTP call, and inside
  the loop by re-reading the actor before each gated tool: `revoked:role` (edge case).

### 5. Documented defaults and "Decisiones tomadas" (FR-005)

`cli/bizview_cli/authoring.py` gains a `DEFAULTS` table (refresh hourly, incremental window 30 days,
exclude personal data, new ids, visible to super user, one-page PDF, default layout) exposed to the
model through the existing `get_authoring_guide` topics and rendered into the agent's base prompt
(022 es/en). The agent writes each default it took into the spec's `## Decisiones tomadas` and into
the run summary; the summary is also checked by a fixture test (SC-006).

### 6. After apply (FR-008, FR-009)

- Apply sets `watch_integration` (the integration ids of the applied version) and `watch_state='pending'`.
  `worker.py`'s `run_scheduled` already records an `integration_run`; after a run whose
  `version_id` is the applied one and `kind` is `incremental` (the first scheduled run), it resolves
  the pending watch: success → `watch_state='ok'`; failure or failed `checks` → a system message in
  the conversation, and when `auto_rollback` is true, `workspace.service.rollback(...)` as the
  confirming super user, audited `assistant_run_rolled_back` (FR-008, SC-005: one scheduler cycle).
- No notification channel is built: the message plus the integration's run history in Administración
  (clarification 5). Email reuses `app/mail` only where the installation already configured SMTP.
- `visible_to` is applied as `dashboard_access` grants for the named roles' active users (audited
  `dashboard_granted` with the run id); no grant by default, so no `user`-role account sees it — staff
  (super users and administrators) do, by role, which FR-009 states explicitly (US4/AC3).

### 7. Frontend (`frontend/src/components/assistant/`)

- `ModeSelector.tsx` — **one compact button that opens a two-entry menu** (Preguntar / Auto), as the
  owner asked on 2026-10-20 ("just preguntar and auto, nothing about all form option"); each entry
  carries a name and one line; `role="menu"` + `menuitemradio`, arrow keys, Escape, AA contrast in
  both themes. Auto is the default and the mode only changes when the run is authorised.
- `RunContractDialog.tsx` — **one line, not a form**: the documented defaults in a sentence plus
  the password (+ TOTP when the installation is `internet`) and a single "Autorizar el run" button;
  the API keeps the full contract shape for profiles. It is an **inline panel above the composer**,
  not an overlay: `tests/unit/no-modals.test.ts` forbids `role="dialog"`, `aria-modal` and
  `fixed inset-0` anywhere in `src/`. The composer shows **Autorizar run** while the mode is Auto
  and no contract is live.
- `SessionIndicator.tsx`/`AssistantHistory.tsx` — the mode pill in the header and in the
  conversation list; "Auto · ejecutando" / "Auto · sin contrato" / "Auto · detenido (límite)".
- `RunStatus.tsx` grows the Auto status bar: stage, attempts, tokens used, previews/applies used,
  elapsed vs `AI_AUTO_RUN_MAX_SECONDS`, and "Detener" (existing endpoint).
- `CommandRunChip.tsx` — the "Auto · /speckit-plan NNN-…" line and the refusal chips.
- `i18n/es.ts` + `i18n/en.ts` — every new string (constitution constraint), including the mode
  labels and the "Pasar a Auto" chip offered when the user asks for autonomy in text (FR-000b).
- `api/types.ts` — `AssistantMode`, `RunContract`, `AutoRun`; `api/client.ts` gets
  `setSessionMode`, `confirmContract`, and the profile CRUD.

### 8. Run profiles (US5, P3)

Administración → IA (`admin/ia`, `pages/admin/AI.tsx`) gains **Perfiles de ejecución** at
`admin/ia/perfiles`: list/create/edit/delete with audit (`assistant_profile_created/edited/deleted`),
built on the existing admin table idiom. Selection in the contract dialog prefills every field;
step-up remains mandatory.

### Project structure (files this feature touches)

```text
backend/app/
├── assistant/
│   ├── auto.py            # NEW  RunContract (pydantic), mode_gate, _finish_auto_run helpers
│   ├── service.py         # mode/contract context, Auto rounds, stop semantics, apply tool path
│   ├── tools.py           # ASK_TOOLS, offered_tool_specs by mode, run_command/apply_draft specs
│   ├── commands/          # reused as-is (resolve, registry, guard, runs)
│   └── preview.py         # reused as-is (the button path)
├── api/
│   ├── assistant.py       # POST /sessions/{id}/mode, /contract, /contract/cancel, /run-profiles
│   └── schemas.py         # ModeIn, ContractIn, ProfileIn
├── models.py              # AssistantSession.mode, AssistantAutoRun, AssistantRunProfile, AUDIT_KINDS
├── config.py              # AI_AUTO_* settings
├── projects/apply.py      # reused (source="chat:<id>:auto")
└── worker.py              # first-run watch + auto rollback
backend/alembic/versions/0024_autonomous_mode.py

frontend/src/
├── components/assistant/  # ModeSelector, RunContractDialog, RunStatus, SessionIndicator,
│                          # AssistantHistory, CommandRunChip (chips), AssistantChat
├── api/{client,types}.ts  # setSessionMode, confirmContract, profiles, AssistantMode types
└── i18n/{es,en}.ts        # every new string, both languages

cli/bizview_cli/authoring.py  # the documented defaults of FR-005
```

### Data (migration `0024_autonomous_mode`)

- `assistant_session.mode` (+ CHECK).
- `assistant_auto_run` (§2) with indexes on `(session_id, started_at DESC)` and
  `(watch_state) WHERE watch_state = 'pending'`.
- `assistant_run_profile`.
- `audit_event.kind` CHECK extended with `assistant_mode_changed`, `assistant_contract_confirmed`,
  `assistant_run_started`, `assistant_run_applied`, `assistant_run_stopped`,
  `assistant_run_rolled_back`, `assistant_profile_created`, `assistant_profile_edited`,
  `assistant_profile_deleted`.
- Downgrade drops both tables, the columns and restores the previous CHECK list.

### Config (`backend/app/config.py`)

| Key | Default | Meaning |
|---|---|---|
| `ai_auto_max_rounds` | 200 | rounds allowed inside one Auto run |
| `ai_auto_max_applies` | 1 | applies allowed inside one contract |
| `ai_auto_run_max_seconds` | 1800 | wall clock of one contract |
| `ai_auto_max_previews` | falls back to `AI_CHAT_MAX_PREVIEWS` | previews allowed inside one contract |

All are validated with the existing `Field(ge=…, le=…)` idiom; the contract stores the numbers it
was confirmed with, so changing a setting never alters a running contract.

### API (all super user + CSRF, as the rest of `api/assistant.py`)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/sessions/{id}/mode` | set ask/edit/auto; stops a run when switching down |
| `POST` | `/sessions/{id}/contract` | confirm the contract with step-up (`password`, `code?`) |
| `POST` | `/sessions/{id}/contract/cancel` | close the dialog without authorising |
| `GET` / `POST` / `PATCH` / `DELETE` | `/run-profiles[/{id}]` | US5 profiles |

Error codes: `mode_invalid`, `contract_required`, `contract_invalid`, `step_up_required`,
`step_up_failed`, `contract_limit_reached`, `not_running`, plus the existing `assistant_busy`.

### Tests

- `backend/tests/test_assistant_auto_mode.py` — mode gate per tool (ask/edit/auto), contract
  validation, stage clip, source allow-list refusal, limit stops, stop/mode-down, `revoked:role`.
- `backend/tests/test_assistant_auto_contract.py` — step-up (password; password + TOTP on `internet`),
  audit rows, `session.mode` transitions and the newest-run lookup, spent contract refusing apply.
- `backend/tests/test_assistant_auto_apply.py` — `apply_draft` tool equals the manual apply
  (SC-004), counter ceiling, `visible_to` grants, rollback watch in `run_scheduled`.
- `backend/tests/test_assistant_auto_loop.py` — the session-18 replay under Auto (SC-008), the
  two-spec chain, `blocked:<reason>` when a stage cannot proceed, no message ending with an
  instruction to the human (SC-007).
- `frontend/tests/unit/assistant-mode.test.tsx`, `assistant-contract.test.tsx` — selector a11y/state,
  dialog validation, pill states.
- `frontend/tests/e2e/assistant-auto.spec.ts` — 320/375 px, three engines, both themes.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| 014 FR-006 "password confirmation per apply" becomes "per run" when a contract exists | The whole point of Auto is one human decision up front; per-apply step-up makes an unattended run impossible | Keeping step-up per apply was rejected: it either blocks the run mid-flight or silently pretends to be autonomous. Everything else in FR-006 (re-validation, readiness, version row, documents, audit) is unchanged, and the contract limits what the single confirmation covers (stages, sources, applies, time) |
| A new table (`assistant_auto_run`) instead of columns on `assistant_session` | Contract, counters, stop reason and summary are per run, and the conversation can start a second run later | JSONB columns on the session would overwrite the previous run's record and leave no auditable history for FR-010/SC-002 |
| No notification channel for FR-008 | There is none in the product today, and building one is a separate feature with its own consent/consent-to-email rules (018) | Reusing the 018 email pipeline was rejected: it needs a subscription model and consent this feature does not have; the conversation + run history is where the super user already looks |

## Post-design Constitution re-check

No new violation after Phase 1. The only deviation remains the per-run step-up above; the data
boundary, read-only SQL, draft limits, workspace lock and rollback are all reused unchanged, and the
contract can only *narrow* what the agent may do. Records of FR-010 are audit kinds plus
`assistant_auto_run`; every user-visible string is added in `es` and `en`.
