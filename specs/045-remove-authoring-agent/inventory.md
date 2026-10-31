# Removal inventory — 045

Every item this feature removes, with why. Produced before deleting anything; the commits that
follow delete by this list. Enumerated from the tree (`git ls-files`, `grep`, `ls`), never from
memory.

Legend: **R** = removed, **K** = kept (out of scope, with the reason), **A** = adapted (the shell
stays, the agent inside it goes).

## 1. Backend modules — R

| Path | Why |
|---|---|
| `backend/app/assistant/` (23 files: `activity`, `attachments`, `auto`, `ayuda`, `history`, `origin`, `overview`, `personal`, `preview`, `readiness`, `repair`, `service`, `tools`, `tree`, `commands/{guard,pipeline,prompt,registry,resolve,runs,scope}`) | the agent itself: loop, tools, draft tree, history builder, repair, command runner, `/speckit-all` state machine, preview-from-chat, readiness, origin checks |
| `backend/app/api/assistant.py` | the `/api/assistant` surface (sessions, messages, commands, previews, apply) |
| `backend/app/engine/narrative.py` | the report narrative generator (owner: keep the schema key, drop the generator) |

## 2. Backend modules — A

| Path | Change |
|---|---|
| `backend/app/ai/*` | keep `complete()` and the provider/client plumbing for the help function; drop tool calling, chat rounds, the Auto error mapping beyond `complete()`, the vision path and the stage budgets |
| `backend/app/api/reports.py` | keep every report route; drop `POST /{id}/narrative` |
| `backend/app/api/projects.py` | keep files, versions, apply, rollback, zip, import; drop the chat-driven fix/preview hooks |
| `backend/app/api/security.py` | keep audit and the security card; drop the assistant-attachment counters |
| `backend/app/models.py` | drop the seven assistant models, keep `integration_run`, `project*`, `share*`, `email*`, `report_cache`, `direct_read_log`, `app_user`, `audit_event` |
| `backend/app/worker.py` | keep integration runs; drop the preview/chat housekeeping passes |
| `backend/app/config.py` | drop the chat/vision/budget settings (see §5) |

## 3. Database — R (after the rescue)

Tables: `assistant_session`, `assistant_message`, `assistant_attachment`,
`assistant_preview_request`, `assistant_command_run`, `assistant_auto_run`, `assistant_run_profile`.
Their check constraints and indexes go with them. `app_user.attachments_notice_at` goes.

Migrations that exist only to shape those tables stay in history (a migration file is a record of
what ran, not live code) — the new migration drops the result. Files involved, for the record:
`0009`, `0011`, `0012`, `0019`, `0020`, `0021`, `0022`, `0023`, `0024`, `0025`, `0026`, `0029`,
`0030`, `0031`, `0040`; `0013`, `0015`, `0018`, `0027`, `0028` also touch other tables and stay.

**Rescue step (FR-002)**: for every conversation whose draft was applied, copy its spec documents
into the owning project folder before the tables are dropped. Applied content is project content.

## 4. API routes — R

`/api/assistant/*` in full (sessions, messages, stream, commands, runs, previews, apply, readiness,
profiles, contracts, attachments, origin checks). No other module gains a route.

## 5. Settings and environment — R

`AI_CHAT_*` (`timeout`, `cached_token_weight`, `max_tokens`, `max_rounds`, `max_previews`,
`busy_stale_seconds`, `token_budget`, `budget_step`, `budget_max`), `AI_COMMAND_TOKEN_CEILING`,
`AI_CONTEXT_COMPACT_CHARS`, `AI_STAGE_TOKEN_BUDGET`, `AI_VISION`, the assistant entries in
`.env.example`, and the cross-field validator that compares the chat timeouts.

**K**: `AI_PROVIDER` (default `none`), `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`,
`AI_TIMEOUT_SECONDS` — the optional help function reads them. `/api/health` keeps answering; its
AI line describes help-only.

## 6. Frontend — R

`src/components/assistant/` (28 files: `AgentMap`, `AIPill`, `AssistantChat`, `AssistantHistory`,
`AssistantPanelContext`, `AssistantPanel`, `AssistantToggle`, `ChatText`, `CommandMenu`,
`CommandRunChip`, `CommandSuggestion`, `EditableTitle`, `ModeSelector`, `PanelResizer`,
`PreviewReports`, `ProblemList`, `ProjectProposal`, `ProviderError`, `Readiness`, `RunReportCard`,
`RunStatus`, `SessionIndicator`, `SpecPicker`, `SpecSelect`, `useAssistantBusy`, `useCommands`,
`useOpenAssistant`, `WorkingNotes`),
`src/pages/admin/AssistantSession.tsx`, `src/pages/admin/RunProfiles.tsx`, the assistant routes in
`App.tsx`, the assistant entries in `routeAccess.ts`, the AI card and pill in `AdminHome.tsx` and
`adminTiles.ts`, the assistant strings in `i18n/es.ts` and `i18n/en.ts`, the assistant types in
`api/types.ts`, the narrative component and its call site.

**K**: `Help.tsx` (the read-only help page), `Security.tsx` minus its chat-image clause, `AI.tsx`
(provider settings for the help function), everything else.

## 7. Tests and fixtures — R

Backend (43 files): `test_ai_chat`, `test_ai_deepseek`, `test_ai_status`, `test_assistant_*` (39),
`test_history_repair`, `test_i18n_assistant`, `test_lock_scope`, `test_pdf_preview`,
`test_preview_after_apply`, `test_project_scope`, `test_project_scope_guard`.

Frontend (14 files): `agent-map`, `ai-pill`, `assistant-*` (11), `chat-links`, `command-menu`,
`command-run-chip`; e2e `assistant*.spec.ts` (4) and `commands.spec.ts`.

**K**: `tests/test_pdf_visual_components.py` (044), the report/project/share/worker suites,
`FakeProvider` **only** if the help tests need it — checked while deleting; otherwise it goes too.

## 8. Dependencies — R (pending the dependency gate)

Any package reached only from the deleted modules. Established by the gate (§9), not asserted here.

## 9. Gates to add (FR-011)

1. **vocabulary**: `asistente|assistant|speckit-all|speckit_all|run_contract|token_budget|AI_CHAT|tool_calls|FakeProvider`
   over `backend/ frontend/ cli/ docs/ README*`, excluding `specs/` (history), `CHANGELOG.md`
   (names what was removed), `alembic/versions/` (records what ran) and an explicit allowlist.
2. **dead code**: `ruff --select F401,F841` (backend), a frontend unused-export pass.
3. **dependencies**: no unused package, backend and frontend.
4. **routes**: the published interface lists none of the removed paths; the router has none of the
   removed screens.
5. **migration**: a seeded database with applied conversations upgrades, every applied spec folder
   survives, the tables are gone, and a second run changes nothing.

## 10. Docs, specs, constitution — A

`docs/VIBE-REPORTING.md` (the in-app assistant section goes; the external-authoring half stays),
`README.md` / `README.es.md` (the Asistente rows), the help topics that describe the assistant,
`specs/014, 015, 017, 021, 024, 028, 029, 035, 036, 039, 040` → `specs/_deprecated/<id>/` with a
one-line `DEPRECATED.md`, the constitution (principle IX redefined; the folder list without
`backend/app/assistant/`), `CHANGELOG.md` (0.2.0 **Removed**, by spec number).

## 11. Explicitly kept (K)

Worker, integrations, report engine, dashboards, PDF, share links, email delivery, TV mode, projects
(files, versions, apply, rollback, export, import), CLI, sources, users/roles/audit, security
profiles, the help page and its optional AI assistance, the Claude connector if present, access
tokens (the CLI's `bizview describe` uses them), validator fixes driven from the project editor.
