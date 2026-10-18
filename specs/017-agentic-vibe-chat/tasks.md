---
description: "Task list for feature 017 — Agentic vibe-reporting chat"
---

# Tasks: Agentic vibe-reporting chat

**Roles**: Claude thinks (spec, plan, tasks, briefs) and audits/converges; DeepSeek executes (writes
all code, tests and fixes). Security-sensitive (AI data boundary, origin tools, budget step-up,
migration): Claude reviews line by line. No live AI in tests (fake provider, recorded transports).
Code first, test last: full suites run once at the end.

## Phase 1: Foundational
- [X] T001 cli/bizview_cli: exhaustive validation in validate.py (Issue file/path/expected/fix, no 20 cap, oneOf branch selection, spec check despite schema errors) + report.schema.json `pdf.orientation`/`pdf.views` + CLI version 0.2.0; cli/tests
- [X] T002 cli/bizview_cli/authoring.py (summary generated from schemas, guide topics, fragments) + golden/ and golden-supabase/ workspaces; cli/tests (golden validates, summary covers required keys)
- [X] T003 Migration backend/alembic/versions/0011_agentic_assistant.py + models (working_state, query_checks, stats, audit kind assistant_budget_extended) + config (AI_CHAT_MAX_ROUNDS, AI_CHAT_BUDGET_STEP, AI_CHAT_BUDGET_MAX, AI_CHAT_MAX_PREVIEWS, AI_TOOL_TIMEOUT_SECONDS); migration test
- [X] T004 Provider: ChatMessage/ChatReply reasoning, ToolCall args_error, context_too_long code, rate-limit retry in backend/app/ai/{__init__,openai_compatible,anthropic_provider,fake}.py; recorded DeepSeek transports in backend/tests/fixtures/deepseek/; tests

## Phase 2: User Story 1 — Contract and valid draft (P1) 🎯
- [X] T005 [US1] tools: get_authoring_guide, edit_draft, read_draft, probe detection in propose_draft, problems with file/path/expected/fix (backend/app/assistant/tools.py, tree.py); tests

## Phase 3: User Story 2 — Origin safely (P1)
- [X] T006 [US2] backend/app/assistant/origin.py: personal-data flags in describe_source, profile_source, check_query (SQL + request), working-state cache; tools wiring; tests incl. SC-002 extension (seeded values never in payloads), timeout

## Phase 4: User Story 3 — Start from nothing (P1)
- [X] T007 [US3] tree.py bootstrap from workspace template (bizview.yaml allowed in drafts) + missing pre-011 spec documents as fixable problems; tests

## Phase 5: User Story 4 — Finish the job (P1)
- [X] T008 [US4] backend/app/assistant/readiness.py (FR-005/FR-009 rules incl. personal columns) + run_preview tool (in-process, max previews) + apply re-runs check_query; tests
- [X] T009 [US4] PDF: pdf.render preview flag, orientation, views; preview PDF route; engine definition_json passes pdf layout; tests

## Phase 6: User Story 5 + 6 — Budget, loop, provider (P2)
- [X] T010 [US5] service.py loop: stable system prefix + state suffix, update_notes + working state, history compaction (old results → summaries, old draft args → index), configurable rounds + progress message, 80% warning, invalid-JSON repair round, context_too_long compaction retry, stats; tests
- [X] T011 [US5] API: POST budget (recent re-auth, audit, cap), session_json additions (working_state, readiness, stats, budget_warning); tests

## Phase 7: UI
- [X] T012 frontend: types, es.ts strings, tool chips for new tools, problems list, readiness checklist + "Listo para aplicar", PDF de vista previa, 80% warning, "Ampliar presupuesto" with step-up view, "Notas de trabajo" view, Aplicar only when ready; unit tests

## Phase 8: Polish
- [X] T013 e2e frontend/tests/e2e/assistant-agent.spec.ts with the fake provider: empty installation → agent flow → ready → apply → ds_<integration> + dashboard + PDF; opt-in live eval backend/tests/live/test_agent_eval.py (SC-001); CHANGELOG, README/deploy env docs
- [X] T014 Full backend, CLI and frontend suites (detached); `/speckit-converge`

## Phase 9: Convergence
- [X] T015 Strip host/IP/port and connection details from preview outcomes sent to the AI (map connection failures to a fixed text like origin._error_text) and extend the SC-002 payload audit with run_preview incl. a failed-connection preview per SC-002 (partial)
- [X] T016 Resolve integration definition and source from the merged tree (active version + draft) in recheck_draft, draft_items and run_draft_preview so a query-only edit of an existing integration can be checked, previewed and applied; turn unexpected run_preview errors into ToolError; tests per FR-005 (partial)
- [X] T017 Reject (or report as a validation/readiness problem) a draft that creates an integration id already in the active version without an explicit edit of it, re-checked at apply time; tests per Edge: same integration id (missing)
- [X] T018 Require a real personal-data confirmation (agent asks; a later user message affirms, or a confirmed-columns decision in working_state) so a negative mention ("excluye <col>") never counts; tests per Edge: personal-data confirmation / FR-007 (partial)
- [X] T019 On a budget stop (pre-turn and mid-turn), write a product-composed progress summary to working_state.progress and append it to the budget message without an extra provider call; tests for both branches per US5/AC4, FR-015 (partial)
- [X] T020 Add a bounded "Archivos recientes" block to the state suffix with the size-capped content of files touched in the last rounds (tracked in working_state); test per FR-013 (partial)
- [X] T021 Add field descriptions to every property of cli/bizview_cli/schemas/*.schema.json (incl. oneOf branches) served by get_authoring_guide, with a CLI test that fails on a missing description per FR-001 (partial)
- [X] T022 Add readiness pending items (with a proposed default) for a draft report without dimensions or filters; test per FR-009 (partial)
- [X] T023 In the agent e2e, sign in as a normal user after apply and check the dashboard renders and its PDF downloads per SC-003 (partial)
- [X] T024 Report a schema-invalid integration as "tiene errores de esquema" instead of "no existe" in dependent reports, and run _check_spec on id/folder mismatch; CLI tests per FR-003/US1 AC2 (partial)
- [X] T025 Add fix hints listing valid names (known sources, dataset columns, metric and dimension ids) to semantic validation problems; CLI tests per FR-003 (partial)
- [X] T026 Map REST/Supabase httpx timeouts and connect timeouts to "tiempo agotado" and bound the connect timeout by AI_TOOL_TIMEOUT_SECONDS; timeout tests for check_query (PostgreSQL, REST) per Edge: slow origin (partial)
- [X] T027 Take the per-session preview lock (or mark preview pending) before dropping schemas in run_draft_preview and refuse request_preview while an agent preview runs; concurrency test per FR-010 (partial)
- [X] T028 Tests: profile_source, check_query and run_preview refuse non-TLS sources under SECURITY_PROFILE=internet; budget exhausted mid-turn → POST budget → "continúa" without a second describe_source; backend apply with no active version and no bizview.yaml uses the template manifest per Edge: internet profile, SC-005, SC-004 (partial)
- [X] T029 Map Anthropic 400 "prompt is too long" to AIError context_too_long with a recorded-transport test per US6/AC2 (partial)

## Phase 10: Convergence
- [X] T030 Migration backend/alembic/versions/0012_assistant_busy.py (assistant_session.busy_since timestamptz NULL) + model + config AI_CHAT_BUSY_STALE_SECONDS (default 900); migration test per US5/AC4 (missing)
- [X] T031 service.send: claim the conversation with a conditional UPDATE committed in its own transaction (busy_since NULL or stale), commit the user message before the first provider call and commit after every round (messages, tool results, draft, working state, tokens), release busy_since in a finally block through a separate session; a stale claim posts "La respuesta anterior se interrumpió; lo hecho hasta la última ronda se guardó. Escribe «continúa»." per US5/AC4, FR-015 (partial)
- [X] T032 Busy guard: messages, preview, apply, archive and budget return 409 assistant_busy ("El asistente sigue trabajando en esta conversación; espera a que termine.") while busy and not stale; session_json and the session list expose busy per FR-015, Edge: concurrent apply (missing)
- [X] T033 Frontend: busy state on open and on 409 assistant_busy — composer and actions disabled with "El asistente sigue trabajando…", poll the session until not busy then refresh; unit tests per US5/AC4 (missing)
- [X] T034 Tests: a second connection sees round N committed while round N+1 runs; an unexpected exception mid-turn keeps earlier rounds and releases busy; a concurrent send gets 409; a stale busy_since is reclaimed with the interruption notice; tokens of committed rounds count against the budget per US5/AC4, FR-015 (missing)

## Phase 11: Convergence
- [X] T035 Weight cached input in the budget: ChatUsage gains cached (DeepSeek prompt_cache_hit_tokens, OpenAI prompt_tokens_details.cached_tokens, Anthropic cache_read_input_tokens); budget usage = uncached input + output + AI_CHAT_CACHED_TOKEN_WEIGHT (default 0.1) × cached; stats keep raw input/cached/output totals; AI_CHAT_TOKEN_BUDGET default 400000; docs per SC-001, FR-015 (partial)
- [X] T036 Bound the "## Estado" suffix: compact inspected-table notes (≤ 600 chars each, last 8 tables, columns only of tables used by the draft in full), last 10 decisions, recent files ≤ 6000 chars; test that a large working state yields a suffix ≤ 12000 chars per FR-012, FR-013, SC-001 (partial)
- [X] T037 check_query on a request whose window returns no records retries once without the window filter (limit 1, shape only) and says so; system prompt forbids temporary/probe files in drafts; tests per US2/AC3, US1/AC4 (partial)
- [X] T038 Session indicator in the assistant header (panel and page): status dot + label (Trabajando, pulsing / Lista / Sin presupuesto), model name, budget used %; session_json adds model; unit tests per FR-015, FR-016 (missing)

## Phase 12: Convergence
- [X] T039 Move the dynamic "## Estado" block out of the system prompt to the tail of the request (providers get a `context` text appended after the last history message: OpenAI-compatible as a final user message, Anthropic as a text block appended to the last user/tool_result message); system = stable prefix only, so tools + system + history form a cacheable prefix across rounds; tests that the system prompt and the history prefix are byte-identical between two rounds per FR-001, FR-012, SC-001 (partial)
- [X] T040 Anthropic provider: cache_control ephemeral breakpoints on the tools/system prefix and on the last history message before the context block; usage parsing unchanged; recorded-transport test per SC-001 (missing)
- [X] T041 Larger chat text: transcript messages, tool chips, problems list, notes and composer one step larger (text-base / text-sm) in the docked panel and the page, phones included; unit/visual checks per owner request 2026-10-05 (missing)

## Phase 13: Autonomous runs (owner amendment 2026-10-05)
- [X] T042 Backend: 202 + background run (service.run_turn in a thread with its own DB session, injectable inline runner for tests, AI_AGENT_MAX_CONCURRENT semaphore), per-run round limit default 60 and stop conditions, automatic budget extension up to AI_CHAT_BUDGET_MAX (audited auto), budget route without recent_reauth, POST /stop releasing the claim + "Detenido por el usuario."; tests per FR-018, FR-019, FR-020
- [X] T043 Frontend: send returns immediately → busy/polling state; "Detener" button while busy; "Ampliar presupuesto" without step-up; unit tests; e2e assistant specs updated for the async flow per FR-018, FR-020

## Phase 14: Convergence (real-run findings 2026-10-05, owner request: custom chat names)
- [X] T044 Discovery loop guard: normalise targets (source name case, leading "/", "public." prefix); a repeated describe_source/profile_source/get_authoring_guide/check_query with the same normalised target returns the stored result marked "ya consultado" without calling the origin; `refresh` honoured once per target per run; after AI_AGENT_DISCOVERY_LIMIT (default 15) discovery calls without a draft, the next rounds offer only draft tools (propose_draft, edit_draft, read_draft, update_notes) and the context says to propose the complete draft now; tests per US1/AC1, SC-001, SC-005 (partial)
- [X] T045 Source-kind guidance: check_query with `sql` on a non-PostgreSQL source answers how to check a request file instead (write requests/<x>.yaml in the draft, then check_query with path); profile_source on Supabase/REST states once that only the row count exists and not to retry; describe_source/profile_source accept "tabla", "/tabla" and "esquema.tabla" for REST sources; tests per US2/AC2, US2/AC3 (partial)
- [X] T046 Chat provider timeout: AI_CHAT_TIMEOUT_SECONDS (default 180, 10–600) for chat() calls, separate from AI_TIMEOUT_SECONDS; one retry on timeout within the run before stopping with the progress summary; tests per US6/AC2 (partial)
- [X] T047 Custom conversation names: PATCH /api/assistant/sessions/{id} {title} (1–120 chars, trimmed; super user, own session, allowed while busy); inline rename in the panel header, the page header and the history list (pencil → text field, Enter saves, Esc cancels; no modal); unit tests (owner request 2026-10-05) (missing)

## Phase 15: Agent map (owner request 2026-10-05)
- [X] T048 Backend run activity: working_state["run"] = {id, started_at, status running|done|stopped|error|budget|limit|ready, round, tokens, current: {tool, label, since} | null}; `current` written in a separate short transaction before each tool runs (visible to pollers mid-round) and cleared after; finished runs appended to stats["runs"] (last 10: started_at, finished_at, status, rounds, tokens, tools count); GET /api/assistant/sessions/{id}/activity → {busy, model, run, rounds: [{n, tools: [{name, label, status running|ok|error, started_at, ms}]}] for the current/last run, background: [{kind: "preview", status, since}]}; light enough to poll every 2 s; tests
- [X] T049 Frontend "Mapa del agente" view (a view, no modal): entry from the session indicator and a header button in panel and page; agent node (status dot, model, elapsed, tokens), child nodes per tool call of the current run (running pulse / ok / error, label, duration), "Tareas en segundo plano" (preview), last runs list; polls /activity every 2 s while busy, stops when idle/unmounted; phones stack vertically; unit tests

## Phase 16: Agent map overlay (owner request 2026-10-07)
- [X] T050 Show the "Mapa del agente" as a floating, non-modal card over the chat (panel and page), like the owner's VS Code example: header "Mapa del agente" + close (×, Esc), subtitle "N herramientas · pulsa un nodo para ver detalles"; tree with the agent node on the left (status dot, conversation title, model · tokens) joined by connector lines to one node per tool call of the current run on the right (status dot running/ok/error, label, duration · round); clicking a node expands its details inline; "N tareas en segundo plano" section below (preview) with its own nodes; entry from the session indicator, a header button, and a new "● N herramientas" pill in the composer footer; no backdrop, no focus trap, not role=dialog/aria-modal (no-modals rule), anchored over the transcript, scrolls inside, phones: full-width card with the tree stacked; polls /activity every 2 s while open and busy; unit tests and an e2e check in assistant-agent.spec.ts

## Phase 17: Convergence
- [X] T051 Remove the manual "Ampliar presupuesto" button (BudgetNotice): below the max show nothing extra; at the max show "Se alcanzó el máximo de esta conversación; continúa en una nueva o sube AI_CHAT_BUDGET_MAX" consistent with the backend budget-stop text; unit tests per FR-019, SC-005 (partial)
- [X] T052 Session indicator state and % computed against budget_max (as BudgetNotice/budget_warning do); "Sin presupuesto" only at the max; unit tests per FR-019, T038 (contradicts)
- [X] T053 A stopped run's late unexpected error never writes into a newer run (post the error only while the claim/run id still belongs to this thread); threaded test per FR-020 (partial)
- [X] T054 Anthropic provider retries one RateLimitError honouring retry-after (capped like openai_compatible._retry_after); timeouts stay unretried; mocked-transport test per US6/AC2 (partial)
- [X] T055 check_query memo hit re-syncs session.query_checks[path] with the current file sha (or re-runs) so A→B→A edits reach readiness; test per FR-005 (partial)
- [X] T056 CLI semantic check: every pdf.views index < len(views), problem with file, path /pdf/views/<i> and a fix listing valid indexes; CLI test per FR-003, FR-009 (partial)
- [X] T057 Docs: AI_CHAT_MAX_TOKENS in .env.example, docs/INSTALL.md and CHANGELOG; CHANGELOG entry for the activity endpoint and the agent map card (phases 15-16) (missing)
- [X] T058 Unit test (and e2e step after "Ver borrador y aplicar") for the agent map on the draft-review page: open from header button and indicator, non-modal region, nodes, Esc/× close with focus return per T050 (partial)
