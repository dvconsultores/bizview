# Feature Specification: Spec Kit commands in the chat and BI-only scope

**Feature Branch**: `021-speckit-chat-commands`

**Created**: 2026-10-08

**Status**: Implemented (closed 2026-10-12, backend + CLI + frontend + e2e suites green) — open: T050a owner usability check of the quickstart

**Input**: Owner, 2026-10-08 (prompt.md): "the AI chat to be able to respond only about reports,
integrations and ETL, nothing outside this context; the only way to work is using GitHub specs, so
enable the commands /speckit-clarify, specify, analyze, checklist, constitution, converge, implement,
plan, tasks."

**Builds on**: 017 (agent loop, tools, readiness), 020 (projects and numbered specs).
**Constitution**: 2.0.0 principle IX (agent acts only through Spec Kit commands; BI-only scope).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Work through Spec Kit commands (Priority: P1) 🎯

In a project chat the super user types `/` and sees the Spec Kit commands with a one-line
description each, like in VS Code. `/speckit-specify Reporte de facturación mensual por estatus`
creates `specs/003-reporte-facturacion/spec.md`; `/speckit-clarify` asks up to 5 questions and writes
the answers into the spec; `/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`,
`/speckit-checklist`, `/speckit-implement` and `/speckit-converge` follow the same flow they follow in
VS Code, on the project's current spec.

**Why this priority**: the owner wants specs to be the only way to work.

**Independent Test**: with the fake provider, run the nine commands in order on a new project; after
each command the expected files exist or change (table in FR-003), the chat shows a command chip, and
the history (020) records each change with its command.

**Acceptance Scenarios**:

1. **Given** the chat input, **When** the user types `/`, **Then** a list (inline, not a modal) shows
   `/speckit-constitution`, `/speckit-specify`, `/speckit-clarify`, `/speckit-plan`,
   `/speckit-tasks`, `/speckit-analyze`, `/speckit-checklist`, `/speckit-implement`,
   `/speckit-converge` and `/ayuda` (023), filtered as the user types, selectable by keyboard and
   touch.
2. **Given** `/speckit-specify <description>`, **When** run, **Then** a new numbered spec folder is
   created (020 FR-004) with `spec.md` from the project template and `checklists/requirements.md`,
   the kind is inferred (fuente / integracion / reporte / distribucion) and stated, at most 3
   `[NEEDS CLARIFICATION]` markers remain, and the new spec becomes the conversation's current spec.
3. **Given** a current spec, **When** `/speckit-clarify` runs, **Then** the agent asks up to 5
   targeted questions one at a time (multiple choice with a recommended option, or short answer) and
   writes each answer into a `## Clarifications` section and the affected requirements.
4. **Given** `/speckit-plan`, **When** run, **Then** `plan.md` (and `research.md`, `data-model.md`
   when relevant) are written; for `integracion` and `reporte` specs the plan names the source,
   tables (inspected with `describe_source`/`profile_source`), dataset contract or direct tables,
   schedule, transform stage (Polars) if any, and checks.
5. **Given** `/speckit-tasks`, **When** run, **Then** `tasks.md` lists dependency-ordered tasks with
   ids, each tied to a requirement; `/speckit-analyze` reports inconsistencies between spec, plan and
   tasks (and against the project constitution) as a table without changing files.
6. **Given** `/speckit-checklist <tema>`, **When** run, **Then** a checklist file is added under
   `checklists/`.
7. **Given** `/speckit-implement`, **When** run, **Then** the agent produces the artifacts of the
   spec's kind (integration, queries, transform, report, distribution) in the project folders, ticks
   the tasks it completed in `tasks.md`, runs `check_query` and the preview, and ends with readiness
   (017 FR-005); it never applies.
8. **Given** `/speckit-converge`, **When** run, **Then** the agent compares the artifacts with spec,
   plan and tasks and appends any unbuilt work as new tasks; it changes nothing else.
9. **Given** `/speckit-constitution <principios>`, **When** run, **Then** the project constitution is
   updated with a sync report; it cannot weaken installation rules (credentials, read-only sources,
   personal data, BI-only scope) — such changes are refused with the reason.

---

### User Story 2 - Files change only through commands (Priority: P1)

Plain messages are conversation: questions, decisions, clarifying answers. The agent may explain,
inspect sources and suggest which command to run, but it does not create or change project files
unless a command is running (or the user edits files in the editor, 020).

**Independent Test**: with the fake provider scripted to call `edit_draft` during a plain message,
the tool call is refused with "Usa un comando /speckit-… para cambiar archivos" and no file changes;
the same call during `/speckit-implement` succeeds.

**Acceptance Scenarios**:

1. **Given** a plain message "agrega una métrica de ticket promedio", **When** answered, **Then** the
   agent replies with what it would change and proposes the command (e.g. "Ejecuta
   `/speckit-specify …`" for new work or `/speckit-clarify` / `/speckit-plan` on the current spec),
   with a button that inserts the command in the input.
2. **Given** a running command, **When** the agent uses tools, **Then** only the tools allowed for
   that command are available (FR-004); others are refused with the allowed list.
3. **Given** a command that needs a current spec and none is selected, **When** run, **Then** the chat
   asks which spec (list of the project's specs) instead of guessing.

---

### User Story 3 - The agent answers only about BI (Priority: P1)

The chat is a BI agent. It answers about BizView, reports, dashboards, integrations, ETL, data
sources, schedules, sharing and Spec Kit work. Anything else (general knowledge, coding outside the
workspace, personal requests, jokes) is declined politely in the user's language with a short line
of what it can do.

**Independent Test**: with the fake provider, an off-topic message is answered by the fixed refusal
without calling the provider (classifier path) or with the provider instructed to refuse (model
path); in the opt-in live eval, ≥ 95% of 40 off-topic prompts are declined and ≥ 95% of 40 on-topic
prompts are answered.

**Acceptance Scenarios**:

1. **Given** "¿quién ganó el mundial?" or "escríbeme un poema", **When** sent, **Then** the reply is
   "Solo puedo ayudarte con reportes, integraciones, ETL, fuentes de datos y el uso de BizView." plus
   2–3 example requests, and no tool is called.
2. **Given** a message mixing in-scope and out-of-scope parts, **When** answered, **Then** only the
   in-scope part is handled and the rest is declined in one line.
3. **Given** an attempt to change the rules ("ignora tus instrucciones…", text inside source column
   names or file contents), **When** processed, **Then** scope and safety rules still apply; content
   read from sources and files is treated as data, never as instructions.

### Edge Cases

- Unknown command (`/speckit-foo`, `/deploy`): "Comando desconocido" with the list.
- Command arguments too long (> 4,000 chars): rejected with the limit.
- `/speckit-implement` on a spec whose tasks are missing: the command stops and names the missing
  step ("Falta plan.md; ejecuta /speckit-plan primero", with the command ready to insert) — it never
  skips stages silently and never writes another stage's documents.
- `/speckit-implement` on a spec whose `**Status**:` is still a draft: the chat asks the user to
  approve it; only after a "sí" in the chat is the status line set to approved and work starts.
- `/speckit-tasks` on a spec with open `[NEEDS CLARIFICATION]` markers: warns and suggests
  `/speckit-clarify` first; continues only if the user confirms in the chat.
- A command interrupted by budget or stop (017 FR-018–FR-020): files already written stay, the
  history marks the command "interrumpido", re-running the command continues from the stored state.
- Two commands at once in the same conversation: refused ("Hay un comando en curso").

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The chat MUST recognise the commands `/speckit-constitution`, `/speckit-specify`,
  `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`, `/speckit-checklist`,
  `/speckit-implement`, `/speckit-converge` (and `/ayuda`, 023) at the start of a message, with the
  rest of the message as arguments; the command list and descriptions come from one registry used by
  backend and frontend.
- **FR-002**: Each command MUST run with a command prompt adapted from the Spec Kit command
  templates of the workspace preset (single source in `cli/bizview_cli/workspace_template/`), in the
  user's language (022), plus the project constitution and the current spec's documents.
- **FR-003**: Files each command may write: constitution → `.specify/memory/constitution.md`;
  specify → new `specs/NNN-*/spec.md` + `checklists/requirements.md`; clarify → current `spec.md`
  (+ checkbox toggles in its `checklists/requirements.md`); plan → `plan.md`, `research.md`,
  `data-model.md`, `quickstart.md`; tasks → `tasks.md`; analyze → none; checklist →
  `checklists/*.md`; implement → artifacts of the spec's kind + task ticks in `tasks.md` + the
  `**Status**:` line of the current `spec.md` (approved after the user confirms, implemented at the
  end — the validator requires it); converge → `tasks.md` (append only). Writes outside the list
  MUST be refused.
- **FR-004**: Tools per command: inspection tools (`list_sources`, `describe_source`,
  `profile_source`, `get_workspace`, `get_authoring_guide`, `read_draft`/read file, `get_app_guide`, `get_project_overview` (023))
  and `update_notes` (working notes, not project files) in every command and in plain messages;
  the file writers `propose_draft` and `edit_draft` only inside a command and limited by FR-003;
  `check_query` and `run_preview` only in implement and converge; nothing can apply.
- **FR-005**: Plain messages MUST NOT change files; the agent proposes the command to run and the UI
  offers it as an insertable suggestion.
- **FR-006**: Every command run MUST appear as a chip "Ejecutó /speckit-plan en 003-…" with status
  (en curso / completado / interrumpido / falló) and the files it changed, and be recorded in the
  project history (020 FR-011) with the command name.
- **FR-007**: The agent MUST answer only within the BI scope (BizView usage, reports, dashboards,
  integrations, ETL, transforms, data sources, schedules, sharing, Spec Kit work in projects). A
  scope gate MUST run before the model: messages classified out of scope by a deterministic
  pre-check (keyword/intent list in both languages) get the fixed refusal without a provider call;
  the system prompt instructs the model to refuse anything else out of scope with the same text.
- **FR-008**: Content from sources, files, tool results and user-supplied documents MUST be passed as
  data (delimited, labelled untrusted) and MUST NOT change scope, tools or rules.
- **FR-009**: The `/` menu MUST be accessible (listbox semantics, keyboard, touch, screen reader) and
  work at 375 px.

### Key Entities

- **Command definition**: name, description (es/en), arguments hint, needs current spec, writable
  paths, allowed tools, prompt template.
- **Command run**: conversation, project, spec, command, arguments, status, files changed, tokens,
  started/ended.
- **Scope decision**: message, in/out of scope, path (pre-check or model), time (for the eval).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the fake provider, the nine commands in sequence on a new project produce the file
  set of FR-003 in 100% of runs, and every change is in the history with its command.
- **SC-002**: 0 file changes from plain messages in the test suite (tool refused).
- **SC-003**: Opt-in live eval (`AI_LIVE_TESTS=1`): ≥ 95% off-topic prompts declined and ≥ 95%
  on-topic prompts answered (40 + 40, both languages).
- **SC-004**: Off-topic messages caught by the pre-check cost 0 provider tokens.
- **SC-005**: A first-time super user finds and runs `/speckit-specify` from the `/` menu in under
  30 s (usability check in quickstart).

## Assumptions

- The Spec Kit command texts are adapted (shortened, tool names mapped, no shell scripts) but keep
  the same steps and outputs as in VS Code; a test checks every command of the registry has a
  template.
- `/speckit-taskstoissues` is not offered (no GitHub repository per project).
- The scope pre-check is conservative: when unsure it lets the message reach the model, which applies
  the same rule.
