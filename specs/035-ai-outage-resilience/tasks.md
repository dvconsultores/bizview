# Tasks: Surviving an AI outage

**Input**: Design documents from `/specs/035-ai-outage-resilience/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)
**Tests**: required by the owner's brief (mapping table, health, refusal/stop, fixes, UI).

**Organization**: one phase per user story. Delivery in the four commits the owner asked for:
commit 1 = Phase 2 + US1 + US4, commit 2 = US2, commit 3 = US3, commit 4 = US1/US2/US3 UI + docs.

## Phase 1: Setup

- [X] T001 Confirm the working tree is clean and `d598afc` is the base (`git log --oneline -1`); no branch is created (owner rule).

## Phase 2: Foundational (blocking)

**Purpose**: the code vocabulary, the status row and the redaction helper that every story uses.

- [X] T002 [P] Write the closed code set and `transient()`/`action_for()`/`BLOCKING` in `backend/app/ai/errors.py` per `contracts/provider-errors.md`; replace the code list in `backend/app/ai/__init__.py` and give `AIError` a `retry_after: float | None = None`.
- [X] T003 [P] Add `redact_detail(text, key)` (keys/ids stripped, max 300 chars + ellipsis) in `backend/app/ai/errors.py`.
- [X] T004 Add the `AIStatus` model (single row, `CheckConstraint("id = 1")`, `last_error_detail` varchar-ish ≤300) in `backend/app/models.py`.
- [X] T005 Add migration `backend/alembic/versions/0028_ai_status.py` (`down_revision = "0027_appearance_palette"`) creating `ai_status` with `id`, `last_ok_at`, `last_error_code`, `last_error_at`, `last_error_detail`, `last_model`, `updated_at`.
- [X] T006 Implement `backend/app/ai/state.py`: `record_ok(model)`, `record_error(code, detail, model)`, `read()` (dict or nulls), `blocked_reason(db)` — each write in its own short session; never raises.
- [X] T007 [P] Add every new i18n key to `backend/app/i18n/es.py` and `en.py`: `ai.error.<code>` for the whole set, `ai.action.admin_ai`, `ai.action.retry`, `ai.details.*`, `ai.test.*`, `assistant.ai_blocked`, `projects.fix_applied`, `projects.fix_stale`, `projects.fix_not_applicable`; mirror the code texts in `app/ai/__init__.py::MESSAGES`.
- [X] T008 [P] Backend unit tests `backend/tests/test_ai_status.py`: ok/error/none transitions, blocking rule (`last_error_at > last_ok_at`), detail cap and redaction, write survives a broken outer transaction.

**Checkpoint**: vocabulary, storage and texts exist; every story can now proceed.

## Phase 3: US1 — The error says what happened and what to do (P1) 🎯

**Goal**: a bubble with code, provider text, provider/model, one action and a details block.
**Independent Test**: `python -m pytest tests/test_ai.py tests/test_health_ai.py` + vitest
`tests/unit/provider-error.test.tsx`.

- [X] T009 [P] [US1] Test the full mapping table with recorded bodies (Anthropic classes, 402/400/429+`retry-after`/500, DeepSeek bodies) in `backend/tests/test_ai.py`, asserting code, redacted ≤300 detail and action.
- [X] T010 [US1] Map every exception/status/body to the new codes in `backend/app/ai/anthropic_provider.py` and `backend/app/ai/openai_compatible.py` (context markers before model markers; 402 → `no_credit`; 5xx/timeout/transport → `provider_down`; `retry_after` kept).
- [X] T011 [US1] Record the outcome: `state.record_ok`/`record_error` on every provider call in `backend/app/assistant/service.py::_turn` and in `backend/app/ai/service.py::test_connection`.
- [X] T012 [US1] Parse malformed tool-call JSON once and fail with `invalid_tool_call` in `backend/app/assistant/service.py` (after the existing repair round).
- [X] T013 [US1] Put the payload on the message: `tool_payload["error"] = {code, detail, provider, model, at, request_id, action}` in `_turn`, forward `error` in `message_json`, and log `assistant provider failure <id>: <code> <detail>` with the same `uuid4().hex[:8]` id.
- [X] T014 [P] [US1] `GET /api/health` `ai` block in `backend/app/api/health.py` per `contracts/health-ai.md`; tests in `backend/tests/test_ai_status.py` (configured/ok/error/missing-row).
- [X] T015 [US1] Probar: `test_connection` runs a completion **and** a one-round tool call, returns both outcomes plus `models` from `Provider.list_models()` (`GET /models`, `client.models.list()`), records the status; endpoint `backend/app/api/ai.py`; tests in `backend/tests/test_ai.py`.
- [X] T016 [P] [US1] `frontend/src/components/assistant/ProviderError.tsx`: code + translated text + detail + provider/model + action link/button + `<details>` Detalles técnicos (timestamp, request id, log command).
- [X] T017 [US1] Render it in `frontend/src/components/assistant/AssistantChat.tsx`/`AssistantPanel.tsx` when a message carries `error`; add `error` to the message type in `frontend/src/api/types.ts`; strings in `es.ts`/`en.ts`; test `frontend/tests/unit/provider-error.test.tsx` (code, action, details collapsed, keyboard).
- [X] T018 [US1] Administración → IA (`frontend/src/pages/admin/AI.tsx`): show code, detail, action, details block, both test outcomes and the models list with the configured one marked; test `frontend/tests/unit/admin-ai.test.tsx`.

**Checkpoint**: any provider failure is named and actionable in the chat and in the admin page.

## Phase 4: US2 — Auto does not spend on a dead provider (P1)

**Goal**: refuse before the call, stop after two strikes, keep the work.
**Independent Test**: `python -m pytest tests/test_assistant_ai_outage.py` (transport spy).

- [X] T019 [P] [US2] Tests `backend/tests/test_assistant_ai_outage.py`: refusal on contract/command (0 calls), refusal on «continua» (0 calls), two consecutive same-code errors → `stop_reason == "blocked:ai_<code>"` with `working_state` and draft intact, one bounded retry for `rate_limited`/`provider_down` (2 calls), retry-after honoured and capped at 60 s.
- [X] T020 [US2] Refuse before the provider: `state.blocked_reason(db)` in `ensure_auto_contract`, in `_command_turn` before starting a `/speckit-*` run, and in `_turn` for a bare «continua|continúa|corrige|sigue» message — answering `assistant.ai_blocked` (code + action) without creating the run.
- [X] T021 [US2] Consecutive-failure accounting and stop in `_turn`: per-code counter, transient retry once, else `end("error", "blocked:ai_<code>")`; `finish_auto_run` stores `stop_reason = "blocked:ai_<code>"` and the summary says what was kept (015 US5).
- [X] T022 [P] [US2] Composer pill: fetch `/api/health` in `frontend/src/components/assistant/AssistantChat.tsx` (shared hook `useAIHealth` in `frontend/src/api/ai.ts`), show the state inline while unhealthy; test with the pill states of `contracts/health-ai.md`.
- [X] T023 [P] [US2] Administración home pill (`frontend/src/pages/admin/AdminHome.tsx` + `adminTiles.ts`): IA tile reading `/api/health`; test `frontend/tests/unit/ai-pill.test.tsx` (pill states + home).

**Checkpoint**: an outage costs zero provider calls to detect and never costs the draft.

## Phase 5: US3 — Deterministic fixes need no AI (P2)

**Goal**: `fix_data` on the problems, one endpoint, one tool, one button.
**Independent Test**: `cd cli && uv run pytest tests/test_validate.py -q -k fix` and
`python -m pytest tests/test_project_fixes.py`.

- [X] T024 [P] [US3] CLI: add `fix_data: dict | None` to `Issue` (`cli/bizview_cli/validate.py`) and serialise it in `as_dict()`; add the pure helpers `set_pointer/append_pointer/insert_pointer` used by both sides in `cli/bizview_cli/fixops.py`.
- [X] T025 [US3] Rule `unjoined_sets` publishes an `append` fix to `/joins` (one problem per missing alias) — `cli/bizview_cli/validate.py::_check_joined`.
- [X] T026 [P] [US3] Rule missing/invalid `date` publishes `set /date` with a date column of the date alias — `cli/bizview_cli/validate.py::_check_report`.
- [X] T027 [P] [US3] Pre-schema rules in `_load_entries` (run right after `_read_yaml`, before the schema gate): `label_missing` (`set /…/label` + `label_en`, humanised id), `view_type_unknown` (nearest known type), `schedule_missing` (`set /schedule` `"0 * * * *"`).
- [X] T028 [P] [US3] Layout rules: `layout_filter_undeclared` (set the reference to null) and `palette_missing` (warning, set `/layout/theme/palette` to the installation preset) in `cli/bizview_cli/report_layout.py`.
- [X] T029 [P] [US3] CLI tests for all seven rules, before/after YAML, in `cli/tests/test_validate.py` (and `tests/test_report_layout.py` for the layout ones).
- [X] T030 [US3] `backend/app/projects/fixes.py`: validate `fix_data`, enforce `base_sha256`, apply pointer ops to the current text via `fs.apply_ops` (one revision per file), audit `project_fix_applied`, revalidate, return diffs; errors `fix_stale`/`fix_not_applicable`.
- [X] T031 [US3] `POST /api/projects/{slug}/fix` in `backend/app/api/projects.py` per `contracts/project-fixes.md` (super user + recent re-auth).
- [X] T032 [US3] Tool `apply_fix(problem_id)` in `backend/app/assistant/tools.py` (resolves the current validation of the conversation's project), plus the rule in the command prompt: prefer it over `edit_draft` when a problem publishes `fix_data`.
- [X] T033 [US3] Publish `problem_id` next to `fix_data` in the validation payload (`backend/app/projects/compose.py::validate_project` and the workspace validation), and add both to `frontend/src/api/types.ts`.
- [X] T034 [P] [US3] Backend tests `backend/tests/test_project_fixes.py`: session-23 fixture (report without `joins`) 1 → 0 problems and applies; stale hash → `fix_stale` and no write; two fixes in one file; AI stubbed down (asserts 0 provider calls); assistant uses `apply_fix` and not `edit_draft` for that file.
- [X] T035 [US3] `frontend/src/components/ide/ProblemsPanel.tsx`: **Aplicar arreglo** per problem with `fix_data`, **Aplicar todos los arreglos** when ≥2, pending state, diff display; `frontend/src/api/projects.ts::applyFixes`; strings; test `frontend/tests/unit/problems-fix.test.tsx` (AI down, keyboard, one click 1 → 0).

**Checkpoint**: the session-23 report is fixed and applied with one click and no provider.

## Phase 6: Polish — docs, changelog, verification

- [X] T036 [P] `backend/app/assistant/guide/es/ia.md` and `en/ia.md`: «Problemas frecuentes» with every code, meaning and fix (and how to read the backend log); keep the guide-drift test green.
- [X] T037 [P] `CHANGELOG.md` under Unreleased: the four parts of the feature with the outage as the reason.
- [X] T038 Run the gates: `ruff` (backend+cli), `pytest` targeted suites of every phase, `cd cli && uv run pytest -q`, `npx tsc --noEmit`, `npm run build`, `npx vitest run`.
- [X] T039 Commit in the four commits the owner asked for and push them; run `./deploy.sh`; confirm `/api/health` shows the new commit and the `ai` block.

## Dependencies

- Phase 2 blocks everything (codes, status, texts).
- US1 (Phase 3) → US2 (Phase 4): the refusal reads the status US1 records.
- US3 (Phase 5) is independent of US1/US2 (validator + project paths) but ships after them to keep
  the commits in the owner's order.
- Phase 6 last.

## Parallel examples

- T002/T003/T007 (errors module, redaction, i18n) — different files.
- T009/T014/T016 — tests and the admin API/bubble can be written while T010/T011 land.
- T026/T027/T028/T029 — one rule each, different functions.
- T036/T037 — docs and changelog.

## Implementation strategy

MVP = Phase 2 + US1: after it, a failing provider is named, actionable and visible in
`/api/health`. Then US2 (spend protection), then US3 (the case that cost the day: a fix that needs
no AI), then the polish commit with the docs.
