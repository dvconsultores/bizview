# Prompt — 045: remove the in-app authoring agent and every piece of dead code it leaves behind

Paste everything below the line into the coding agent with the repository open. This is a
deletion-first task: the goal is a smaller, honest codebase, not a feature.

---

You are working on the BizView repository. Read `.specify/memory/constitution.md` and
`specs/043-bizview-refactor-external-authoring/spec.md` (workstreams A and G are the scope of this
feature). Implement **045-remove-authoring-agent** end to end: remove the in-app authoring agent and all code, data, strings, tests, docs
and dependencies that only existed for it. Do not ask me questions. Work as
`/speckit-specify` (from this text) → `/speckit-plan 045-remove-authoring-agent` → `/speckit-tasks` → `/speckit-implement`, in the commits listed at the end.

## What stays (do not touch)

- Everything that runs, renders and shares: worker, integrations, report engine, dashboards,
  PDF, share links, email delivery, TV mode, projects (files, versions, apply, rollback, export
  zip, import), CLI, sources, users/roles/audit, security profiles.
- The read-only help page and help search (033), and the provider layer's `complete()` for the
  optional help agent. The Claude connector (016) if present.
- `Tokens de acceso` (used by the CLI's `bizview describe`).

## What goes — find it, don't guess (enumerate before deleting)

1. **Routes and UI**: `/admin/asistente`, project chat pane and its routes, the sparkle/assistant
   button in the header, the composer, mode selector (Ask/Edit/Auto), run contract and profiles
   screens, "Pasar a Auto" chips, token-budget widgets, the "IA funcionando" pill, the
   "Inteligencia artificial" card in Administración, "Insertar /speckit-…" buttons, "Aplicar
   arreglo" buttons that only existed for chat-driven fixes (keep validator fixes that work
   from the project editor), the "Asistente" nav item.
2. **Backend**: `app/assistant/**` (loop, tools, tree builder for drafts, history builder,
   compression, repair), the command runner for `/speckit-*` in the app, run contracts/profiles,
   `/speckit-all` state machine, preview-from-chat requests, per-command token ceilings, tool
   groups, provider `chat()` with tool calling and its error mapping beyond what `complete()`
   needs, the authoring pack endpoints that served the agent (keep/adapt only what 043 WS-B will
   reuse: schema serving for the skeleton), `apply_fix`/`set_current_spec`/`run_command`
   tools, the AI narrative generation if nothing else uses it (check reports' `ai_narrative`:
   keep the schema key as deprecated-ignored for one version, remove the generator).
3. **Database**: tables `assistant_session`, `assistant_message`, `assistant_preview_request`,
   `command_run`, run contracts, run profiles, help-usage tables that only the chat wrote, and
   their enums/indices. Migration order: (a) for every `applied` conversation whose spec folder
   is not already in its project, copy the spec documents into the project folder (nothing a
   user applied may be lost; transcripts are not kept); (b) drop the tables; (c) remove the
   settings rows `AI_CHAT_*`, `AI_COMMAND_TOKEN_CEILING`, budgets, contract defaults.
4. **Settings and env**: `AI_CHAT_ENABLED`, token budgets/ceilings, `AI_VISION`, anything in
   `.env.example` that only the agent read; `AI_PROVIDER` stays, default `none`, documented as
   "help only".
5. **Frontend**: pages, components, hooks, stores, API clients, types and `es.ts`/`en.ts` strings
   for the above; dead CSS; icons imported only by removed components.
6. **Tests and fixtures**: backend and frontend suites, e2e specs, FakeProvider scripts,
   recorded conversation exports, session fixtures (`session18.json` etc.), the live-eval
   harness for authoring. Keep FakeProvider only if the help agent tests need it.
7. **Dependencies**: any package used only by removed code (check with the dependency graph /
   `deptry`-style tooling, and `npm ls`/bundle analysis). Remove tool-calling-specific SDK
   extras if `complete()` does not need them.
8. **Docs and specs**: `docs/` pages for the assistant; help topics about the assistant;
   README sections; move `specs/014, 015, 017, 021, 024, 028, 029, 035, 036, 039, 040` (and
   any other spec whose purpose was the in-app agent — check 023 and 033's agent parts) to
   `specs/_deprecated/<id>/` with a one-line `DEPRECATED.md` each ("removed in 0.2.0 by 045;
   authoring moved outside Bizview"). Update the constitution per 043's amendment 2.0.0 Sync
   Impact Report (principle IX redefined; folder list without `backend/app/assistant/`).
9. **Admin home (043 WS-G, included here)**: remove the AI card and pill; rewrite the "Tokens de acceso" and
   "Proyectos" descriptions as 043-G says; grid 3/2/1.

## Method (so nothing half-removed remains)

- Start by producing `specs/045-remove-authoring-agent/inventory.md`: every file,
  route, table, setting, string key, test and dependency you will remove, with the reason. Commit
  it first.
- Delete by inventory, run the suites after each commit, and finish with these gates (add them
  to CI so the agent cannot come back silently):
  - grep gate: no match in `backend/ frontend/ cli/ docs/ README*` for
    `asistente|assistant|speckit-all|speckit_all|run_contract|token_budget|AI_CHAT|tool_calls|FakeProvider`
    except an explicit allowlist file for the help agent;
  - dead-code gate: `vulture`/`ruff --select F401,F841` (backend), `knip` or `ts-prune` (frontend)
    report 0 unused exports/modules;
  - dependency gate: no unused packages (backend and frontend);
  - route gate: the API's OpenAPI document lists no `/assistant`, `/commands`, `/runs`,
    `/contracts` paths; the frontend router has no assistant routes;
  - migration gate: a seeded database with applied conversations migrates, every applied spec
    folder exists in its project afterwards, and the tables are gone.
- Measure and report in the PR: backend image size, frontend bundle size, dependency count,
  line count — before and after.

## Deliverables

- Inventory + CHANGELOG 0.2.0 "Removed" section listing every removed feature by spec number.
- Migration with the spec-folder rescue step and a dry-run flag.
- CI gates above.
- README/docs without the assistant; constitution amended (2.0.0).
- All suites green; `./deploy.sh` and `/api/health` showing the new commit.

Commits: (1) inventory, (2) frontend removal + strings, (3) backend removal + routes, (4)
migration + settings, (5) tests/fixtures/deps cleanup + CI gates, (6) docs/specs/constitution +
CHANGELOG.
