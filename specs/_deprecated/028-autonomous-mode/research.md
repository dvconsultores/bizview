# Phase 0 — Research: Autonomous mode for the Asistente

All decisions below were taken while reading the code this feature extends: `assistant/service.py`
(turn lifecycle, claim, stop, budget, `_command_turn`), `assistant/tools.py` (`TOOL_SPECS`,
`run_tool`, `offered_tool_specs`, `is_discovery`), `assistant/commands/` (`registry`, `guard`,
`resolve`, `runs`), `assistant/preview.py`, `projects/apply.py`, `workspace/service.py`,
`worker.py`, `security/{mfa,profile}.py`, `api/assistant.py`, `api/auth.py`, and the frontend
`components/assistant/`. There are no `NEEDS CLARIFICATION` items left: the five open questions were
closed in `spec.md` § Clarifications (2026-10-20).

## R1 — Where the mode lives

**Decision**: a `mode` column on `assistant_session` (`ask`|`edit`|`auto`, default `edit`),
changed only by `POST /sessions/{id}/mode`.

**Rationale**: the mode is per conversation, exactly like `current_spec`, `token_budget` and
`read_only` — all columns on that table. The gate needs it on every tool call, i.e. inside a turn
that already holds the session row; a join or a settings lookup would add nothing.

**Alternatives considered**: a separate `assistant_session_mode` table (a 1:1 table for one enum is
noise); deriving the mode from the last message (fragile, and the spec requires it to survive
reloads and to be listed on the conversation list).

## R2 — Where the run contract lives

**Decision**: a new table `assistant_auto_run`, one row per contract, with `contract` JSONB,
counters, `status`/`stop_reason`, `version_id` and `summary`; the conversation's current
contract is its newest row (no back-reference column: it would be a FK table cycle, which makes
Alembic's metadata comparison skip the foreign keys of both tables).

**Rationale**: a contract covers exactly one run (spec, "How an Auto run works" 3), and FR-010 wants
the run summary stored plus audit entries per apply/stop. A row per run gives history for free, lets
SC-002 assert stored state after a stop, and gives FR-008 a place to keep the post-apply watch.

**Alternatives considered**: JSONB columns on `assistant_session` (a second run would overwrite the
first — no history, no `version_id` linkage, and the summary of a stopped run would be lost);
reusing `assistant_command_run` (that table is per `/speckit-*` run with a command CHECK, and an Auto
run spans several commands plus a preview and an apply).

## R3 — Where the mode is enforced

**Decision**: `tools.offered_tool_specs()` filters what the model is offered and `tools.run_tool()`
refuses what it still tries; both consult one `mode_gate()` helper. The system prompt only explains
the mode (FR-000b).

**Rationale**: `run_tool` is the single choke point through which every tool call already passes
(`guard.check_tool` runs there today), and `offered_tool_specs` already filters by command guard.
Refusing in one place keeps Ask/Edit/Auto exhaustive and testable, and satisfies FR-003 (limits in
product code, not prose) including against injected instructions in source metadata.

**Alternatives considered**: per-tool `if mode == …` inside each `_dispatch` branch (easy to miss
one; the 028 spec needs "0 write tools succeed", which is a chokepoint property); prompt-only
enforcement (explicitly rejected by FR-003).

## R4 — Step-up for the contract

**Decision**: `POST /sessions/{id}/contract` re-verifies the password with the same helpers as
`/auth/reauth` (`passwords.verify_password`, `throttle.check`, `users.is_locked`, audit
`reauth_failed`/`reauth_ok`) and, when `security.profile.mfa_required_for(role)` is true, a TOTP
code through `security.mfa.verify_code`. Success also stamps `session.reauth_at`, so the existing
`recent_reauth` dependency keeps working for other actions of the same session.

**Rationale**: 014 FR-006 already proves "password confirmation" this way, and the `internet`
profile requires a second factor for admins (`mfa_required_for` = `profile == "internet"` and
`role == "admin"`); the Asistente is super-user only.

**Alternatives considered**: a new step-up endpoint (duplicates throttling and lockout logic);
trusting `recent_reauth` alone (the spec wants the contract confirmation itself to be the
authorisation, with its own audit entry).

## R5 — How the agent chains Spec Kit stages (`run_command`)

**Decision**: `run_command(spec, command, arguments?)` is a **stage switch**, not a nested run: it
closes the current `assistant_command_run`, creates the next one with the same
`commands.runs.create(...)` + `registry` definition the composer uses (so `resolved_from`, guard,
tool set, token ceiling and audit are identical), points `session.command_run` at it, and returns the
stage context to the model, which keeps working in the same provider loop.

**Rationale**: the composer path is "parse → `_command_turn` → `runs.create` → one provider loop with
that command's tools". Re-entering `run_turn` from inside a tool call would nest claims
(`_claim`/`_TurnClaim`), duplicate the semaphore slot and make "Detener" ambiguous. A stage switch
gives the same audited outcome (each stage is a real command run row) with one tool call per stage,
and the transcript can render "Auto · /speckit-plan 002-…" from the run row.

**Alternatives considered**: calling `service.start()` recursively (nested claim, transcript
duplication); a scheduler of separate turns (loses the single authorised run, needs a new
orchestrator and a new claim model); letting the model just write files without stage rows (loses
FR-010 records and `misrouted` detection).

## R6 — `run_preview` inside the loop

**Decision**: reuse the tool that already exists: `run_preview` in `tools.py` runs the draft preview
**inline** through `preview.run_draft_preview(db, session, time_limit_s=120)` and bumps
`session.stats['previews']`. Auto only adds the contract gate (stage `preview`, `limits.previews`,
never above `AI_CHAT_MAX_PREVIEWS`) and the per-run counter. No queueing, no polling.

**Rationale**: the agent path and the human button already use different mechanisms — the button
queues `preview.request_preview` in the worker (cancellable with `drop_for_session`), the tool runs
inline with a 120 s ceiling. Keeping the tool inline preserves the existing behaviour and the
existing per-conversation cap, and `time_limit_s` already bounds a hung preview inside the turn.

**Alternatives considered**: switching the tool to the worker queue and polling `session.preview`
(would need a new wait setting and an in-tool sleep; the inline call is already bounded and tested);
letting the button's preview satisfy the run (the agent could not diagnose and fix in the same run).

## R7 — Limits, wall clock and "Detener"

**Decision**: limits are checked at the top of every round and again inside each gated tool.
Tokens use the existing budget accounting (`_count_usage`, `budget_limit`), previews/applies the
contract counters, wall clock `now - confirmed_at` against `AI_AUTO_RUN_MAX_SECONDS`. Any breach
calls `_finish_auto_run(status='stopped', reason='limit:<name>')`. "Detener" and switching the mode
down both clear `busy_since`, which `_commit_round` already turns into `_ClaimLost` — the existing
cooperative stop, unchanged.

**Rationale**: reusing the claim mechanism means a stopped run cannot apply afterwards (the claim is
lost, the next `_commit_round` raises), which is exactly SC-002, and the draft/working state are
already committed each round.

**Alternatives considered**: a separate cancellation flag (a second source of truth next to
`busy_since`); `threading.Event` per run (does not survive the multi-worker HTTP/runner split).

## R8 — Post-apply watch and rollback

**Decision**: apply records `watch_integration` (the applied version's integration ids) and
`watch_state='pending'`. `worker.py`'s `run_scheduled` — which already records an `IntegrationRun`
with `checks` and calls `workspace.service.rollback` on demand — resolves the pending watch after
the first scheduled run on that version: failure or failed checks → a system message in the
conversation, and with `auto_rollback`, `workspace.service.rollback(db, actor=confirming_user, ip)`
plus audit `assistant_run_rolled_back`.

**Rationale**: the run record already carries everything needed to judge success (`status`,
`checks`), and rollback is already "a normal version switch" (constitution, worker idempotent), so
no new mechanism is required.

**Alternatives considered**: a new watcher thread (duplicates the scheduler); no watch (the spec's
SC-005 requires the restore within one scheduler cycle).

## R9 — `visible_to`

**Decision**: after an apply, the new dashboards get **no** `dashboard_access` rows unless the
contract names roles; a named `user` role grants access to that role's currently active accounts,
audited as `dashboard_granted` with the run id.

**Rationale**: `dashboard_access` is the only per-user visibility mechanism in the product (018).
`dashboards.visible_for` shows every non-hidden dashboard to `admin` and hides it from `user`
without a grant, so "no grants" is the closest achievable reading of the spec's "super user only":
non-super administrators still see it by role, and the only way to hide it from them is
`status='hidden'`, which hides it from the super user too. The spec records this limit in FR-009.
Granting to users created later would silently widen visibility, which the spec forbids.

**Alternatives considered**: `status='hidden'` until a human publishes (nobody could see the
dashboard the run just reported, defeating US1); a report-level permission table (new model, new
admin UI, no precedent); reusing share links (public links, not roles).

## R10 — Modes × tools matrix (grounded in today's sets)

**Decision**:

| Mode | Offered tools |
|---|---|
| `ask` | `list_sources`, `describe_source`, `profile_source`, `get_authoring_guide`, `get_workspace`, `get_app_guide`, `get_project_overview`, `read_draft`, `check_query` (no `path`) |
| `edit` | today's `guard.allowed_tools(definition)` (inspection set + the command's tools + `finish_command`) |
| `auto` (live contract) | the `edit` set **plus** `run_command`, `set_current_spec`, `run_preview`, `apply_draft`, clipped by the contract stages and source allow-list |

`ASK_TOOLS` reuses `DISCOVERY_TOOLS` and the existing `is_discovery()` split of `check_query`
(without `path` = read a source; with `path` = check the draft's queries, so it needs a draft).

**Rationale**: the product already classifies tools this way for discovery and for the command guard,
so the mode matrix does not invent a taxonomy; `check_query` is the only tool with two natures and
`is_discovery()` already encodes the distinction.

**Alternatives considered**: a `read_only` flag per tool spec (a parallel taxonomy that would drift
from `INSPECTION_TOOLS`/`DISCOVERY_TOOLS`).

## R11 — Selector, dialog and a11y

**Decision**: `ModeSelector.tsx` as a segmented control rendered above the composer (feature-010
look, no modals), the contract in `RunContractDialog.tsx` (the one place a modal-like panel is
acceptable because it is an authorisation, and it is dismissible), the status bar in the existing
`RunStatus.tsx`. All strings in `i18n/es.ts` + `i18n/en.ts`.

**Rationale**: the composer already owns the send button and the command menu; a radix-free
segmented control with `role="radiogroup"` meets SC-009 (Tab + arrows, AA contrast) and works at
320 px without a new dependency (no modal library is installed).

**Alternatives considered**: a `<select>` (the spec explicitly rejects a dropdown on phones); a
route for authorisation (loses the conversation context and the chips).

## R12 — Run profiles

**Decision**: `assistant_run_profile` (installation-wide, `name` unique, `contract` JSONB,
`created_by`, soft delete) with CRUD under the existing admin routes and audit kinds.

**Rationale**: profiles are an installation setting (VII) that any super user may reuse; the
contract still needs its own step-up, so a profile is only a form prefill.

**Alternatives considered**: storing profiles per user (the spec says per installation); storing them
in `app_setting` JSONB (no per-row audit, no unique name).

## R13 — Prompt and language

**Decision**: the mode and contract notice is appended to the turn context (`## Modo`, es/en) built
in `service.state_text`/`_context`, not to the static base prefix, because it changes per turn; the
defaults of FR-005 go to the authoring guide (`cli/bizview_cli/authoring.py`) and are summarised in
the same block.

**Rationale**: the base prefix is cached (`system_prefix` with `lru_cache`), and the mode/contract
must not leak between conversations; the authoring pack is the single source the validator and the
agent already share (017 §1).

**Alternatives considered**: a per-mode system prefix (four cached prefixes, easy to mix up); putting
the defaults only in the prompt (they would drift from the validator).

## R14 — Tests without a live model

**Decision**: the fake provider replays recorded runs; the session-18 fixture (integration 001 +
report 002 from one request) becomes a replay under Auto (SC-008). SC-001 stays opt-in
(`AI_LIVE_TESTS=1`, DeepSeek). The adversarial suite seeds source metadata containing injection text
(SC-003). Product-DB tests keep the `app_test_*` schema convention.

**Rationale**: this matches 017/021 and the contributing guide's "tests never call a live AI"; the
fixture already exists as the misrouting regression for the routing fix that shipped.

**Alternatives considered**: asserting on prompt text (brittle); live-only verification (not runnable
in CI, and `AI_PROVIDER=none` installations must still pass).

## R15 — Why no notification channel

**Decision**: FR-008 reports through the conversation (system message) and the integration's run
history; email only where the installation already configured SMTP.

**Rationale**: the product has no notification inbox, no push and no per-user preference store for
one; 018's email pipeline is subscription/consent based. Building one here would be a second feature
and would widen the data boundary (decided in spec.md § Clarifications 2026-10-20).
