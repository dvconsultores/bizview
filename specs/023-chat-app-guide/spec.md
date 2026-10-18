# Feature Specification: The agent explains the app, Spec Kit and projects

**Feature Branch**: `023-chat-app-guide`

**Created**: 2026-10-08

**Status**: Implemented (closed 2026-10-12, backend + CLI + frontend + e2e suites green)

**Input**: Owner, 2026-10-08 (prompt.md): "train the chat to explain all app options, how to work with
specs and how every project is defined and developed."

**Builds on**: 017 (agent tools), 020 (projects), 021 (commands, BI-only scope), 022 (languages).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask the agent how the app works (Priority: P1) 🎯

A new super user asks "¿cómo comparto un tablero por correo cada lunes?" or "what is the difference
between a direct report and an integration?" and gets a short, correct answer with the steps, the
screen names as they appear in the app, and a link to the screen.

**Why this priority**: the owner wants the agent to be the guide to the whole product.

**Independent Test**: for each topic of the guide index, a scripted question (fake provider replaying
the tool call) returns an answer built from `get_app_guide(topic)`; links in the answer open the
named screens; in the opt-in live eval, ≥ 90% of 50 reference questions (both languages) are judged
correct against the guide.

**Acceptance Scenarios**:

1. **Given** a question about any app option (dashboards, filters, periods, auto-refresh/TV mode,
   PDF, favourites, sharing links, email and subscriptions, profile, theme, language, two-step,
   Telegram sign-in, users and roles, audit, sources, direct reads, integrations and their controls,
   workspace versions and rollback, projects, AI settings, tokens, security profile), **When** asked,
   **Then** the agent calls `get_app_guide` for the topic and answers from it, naming screens and
   buttons exactly as the interface shows them in the user's language.
2. **Given** an answer that refers to a screen, **When** shown, **Then** it includes an in-app link
   (e.g. "Abrir Administración → Fuentes") that navigates there; links respect the user's role (no
   link to a screen the user cannot open; the answer says who can do it instead).
3. **Given** a question the guide does not cover, **When** asked, **Then** the agent says it does not
   know rather than inventing, and suggests the closest topic.

---

### User Story 2 - Learn the Spec Kit way of working (Priority: P1)

The super user types `/ayuda` or "¿cómo trabajo con specs?" and gets the method: a project holds
numbered specs; each spec goes specify → clarify → plan → tasks → analyze/checklist → implement →
converge → apply; what each command produces; which spec kind to use for a source, an ETL, a
report (dataset or direct), a schedule or a share.

**Acceptance Scenarios**:

1. **Given** `/ayuda` with no arguments, **When** run, **Then** the agent shows the short method, the
   command list (021 registry) and 3 example requests, without calling the provider for the fixed
   part.
2. **Given** `/ayuda <tema>` (e.g. `/ayuda reporte directo`), **When** run, **Then** the agent answers
   that topic from the guide.
3. **Given** a project, **When** the user asks "¿qué falta en este proyecto?", **Then** the agent
   reads the project's specs and stages (020) and answers with the next command to run per spec.

---

### User Story 3 - Explain how a concrete project is defined and built (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a project, **When** the user asks "explícame este proyecto", **Then** the agent
   summarises it from its files: purpose, specs with kind and stage, sources, integrations (schedule,
   transform, checks), reports (mode, metrics, views), distributions, applied state and pending
   changes — without reading source rows.
2. **Given** a spec, **When** the user asks "¿por qué este reporte es directo?", **Then** the agent
   cites the spec's lines that record the decision (019 FR-003).

### Edge Cases

- A guide topic changed in a new release: the guide ships with the product version, so answers match
  the installed version.
- A user who is not super user cannot open the chat (014); the guide content is also readable as the
  "Ayuda" page by every role, filtered to what that role can do.
- Questions about security internals (keys, how to bypass two-step): answered only at the level the
  guide documents for administrators; never secrets.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product MUST ship an app guide: one Markdown document per topic in Spanish and
  English, versioned with the code, covering every screen and option of the app, the roles that can
  use it, the Spec Kit method, spec kinds, project layout, and the end-to-end paths (source →
  integration → report → distribution; source → direct report).
- **FR-002**: A tool `get_app_guide(topic?)` MUST return the topic index (no topic) or one topic in
  the user's language; available in plain messages and every command (021 FR-004).
- **FR-003**: The system prompt MUST include the guide index (stable prefix) and the rule to answer
  app questions from the guide only, with screen names as in the catalogues (022).
- **FR-004**: Answers MAY contain in-app links in the form `[texto](app:/ruta)`; the chat renders them
  as navigation links and drops links to routes the user's role cannot open or that do not exist
  (the text stays, without link); links with any other scheme are shown as plain text.
- **FR-005**: `/ayuda` MUST be in the command registry (021 FR-001); its fixed part (method, commands,
  examples) is rendered without a provider call.
- **FR-006**: A test MUST fail when a route of the app, an Administración tile or a command of the
  registry has no guide topic, or when a guide topic links to a route that does not exist (drift
  check).
- **FR-007**: The guide MUST also be readable as a page "Ayuda" (`/ayuda`) for every role, showing only
  topics relevant to that role, with search by title.
- **FR-008**: A tool `get_project_overview()` MUST return a summary of the conversation's project
  built from its files and the 020 status: specs (number, kind, mode, stage, open clarifications,
  task progress, next command, and the spec lines that record kind/mode/source decisions with file
  and line), sources referenced (name, kind, exists, last test result, direct reads allowed),
  integrations (schedule, transform, checks), reports (mode, metrics, views), distributions
  (frequency, period, recipient counts and roles — never addresses or names), applied state and
  pending changes; never source rows or credentials. It is an inspection tool added to the list of
  021 FR-004 (plain messages and every command).

### Key Entities

- **Guide topic**: id, title (es/en), roles, routes it documents, body (es/en), related topics.
- **Guide index**: ordered list of topics with one-line summaries.
- **Project overview**: metadata-only summary of one project (FR-008), recomputed on each call.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of routes, Administración tiles and commands are covered by a guide topic (drift
  test).
- **SC-002**: Opt-in live eval: ≥ 90% of 50 reference questions (25 per language) answered correctly
  and with a valid in-app link where one applies.
- **SC-003**: `/ayuda` without arguments costs 0 provider tokens and renders in under 200 ms.
- **SC-004**: In usability checks, a first-time super user completes "crear un reporte directo sobre
  una tabla existente" guided only by the chat in under 10 minutes.

## Assumptions

- "Training" means grounding the agent on a maintained guide and tool, not fine-tuning a model; it
  works with any configured provider, including local models.
- The guide is written by the team (Claude drafts, owner reviews) from the specs and the interface
  catalogues; it is part of each release.
