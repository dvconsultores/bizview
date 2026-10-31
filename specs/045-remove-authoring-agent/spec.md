# Feature Specification: Remove the in-app authoring agent

**Feature Branch**: `045-remove-authoring-agent`

**Created**: 2026-10-31

**Status**: Draft

**Input**: Owner, 2026-10-31: remove the in-app authoring agent and every piece of dead code it
leaves behind. Authoring happens outside Bizview, with any agent, against the published contract.
This is a deletion-first feature: the goal is a smaller, honest product, not a feature.

**Builds on**: 043 (external authoring; workstreams A and G are this feature's scope).
**Removed by**: 0.2.0.

## Why

The product grew a second way to author dashboards: a chat inside the app that ran Spec Kit
commands, edited project files through tools, kept run contracts and token budgets, previewed
drafts and applied them. Feature 043 replaced that model: an author works in their own Git
workspace with any agent, validates there, and brings the finished project in through
**Proyectos → Importar**. Two doors for one job means double the surface, double the bugs (044's
browser run alone found three silent ones on the shared paths), and a product that still promises
something it no longer recommends.

What remains is what runs, renders and shares: the worker, the integrations, the report engine,
dashboards, the PDF, share links, email, TV mode, projects, the CLI, sources, users and audit, and
the read-only help page. Those must not change behaviour.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator sees a product without the agent (Priority: P1)

An administrator opens **Administración** and the product no longer offers to build dashboards
inside Bizview: there is no assistant entry, no AI card, no "IA funcionando" pill, no run profiles,
no "Spec actual", no composer and no mode switch. What is left describes what the installation
actually does.

**Why this priority**: it is the visible half of the change, and leaving one door open teaches
users a path the product will not support.

**Independent Test**: sign in as superuser, walk every menu and page; no screen offers to author a
dashboard in the app, and every remaining page works as before.

**Acceptance Scenarios**:

1. **Given** an administrator's home, **When** it loads, **Then** it shows the remaining cards,
   with no AI card and no status pill, on a 3/2/1 grid at desktop/tablet/phone widths.
2. **Given** the main navigation, **When** it renders, **Then** there is no "Asistente" item and no
   sparkle button in the header.
3. **Given** a project page, **When** it opens, **Then** it shows files, problems and history —
   no chat pane, no spec selector, no mode selector, no run contract, no token widget.
4. **Given** any URL of the removed area, **When** it is opened, **Then** the product answers a
   clear "not here any more" page instead of a broken screen.

### User Story 2 - Nothing a user applied is lost (Priority: P1)

A customer upgraded from an installation where conversations were applied. After the upgrade every
applied specification still exists inside its project, so its dashboards keep running and its
history still explains itself. The conversations themselves are gone, and the product says so.

**Why this priority**: a deletion that loses applied work is unacceptable, whatever the feature.

**Independent Test**: a database seeded with applied and unapplied conversations is upgraded; every
applied specification folder exists in its project afterwards, every unapplied draft is gone, and
the report pages still render.

**Acceptance Scenarios**:

1. **Given** a conversation whose draft was applied, **When** the upgrade runs, **Then** its
   specification documents exist in the project folder, unchanged in content.
2. **Given** a conversation that was never applied, **When** the upgrade runs, **Then** nothing is
   rescued and nothing is left half-written.
3. **Given** the upgrade, **When** it finishes, **Then** the assistant's stored data is gone and the
   installation starts normally.
4. **Given** the upgrade is run twice, **When** the second run finishes, **Then** it changes nothing.

### User Story 3 - The help page still answers (Priority: P2)

A user presses **Ayuda**, searches and reads. The help page and its search work exactly as before,
and the topics that described the removed assistant are gone rather than describing a screen that
no longer exists.

**Why this priority**: help that documents a deleted feature is worse than no help.

**Independent Test**: open Ayuda, search for a topic that exists, read it; search for an assistant
topic and find nothing.

**Acceptance Scenarios**:

1. **Given** the help page, **When** it loads, **Then** it lists its topics and search returns
   matches.
2. **Given** a search for a removed topic, **When** it runs, **Then** no result sends the reader to
   the assistant.

### User Story 4 - The repository cannot grow the agent back (Priority: P2)

A contributor adds code that reintroduces the removed vocabulary or an unused dependency. The
pipeline refuses the change, naming the offending line.

**Why this priority**: without a gate the deletion decays; every later feature would be free to
re-add a chat.

**Independent Test**: introduce one forbidden word and one unused dependency on purpose; the gates
fail and name them.

**Acceptance Scenarios**:

1. **Given** a source file that mentions the removed vocabulary outside the allowlist, **When** the
   gate runs, **Then** it fails and prints the file and line.
2. **Given** dead code or an unused package, **When** the gates run, **Then** they fail.
3. **Given** the running product, **When** its published interface is inspected, **Then** no route,
   screen or setting of the removed area remains.

### Edge Cases

- A conversation applied but whose project was later deleted: nothing to rescue, nothing to fail.
- Two conversations applying the same specification folder: rescued once, never duplicated.
- A conversation whose draft documents are malformed: rescued as-is; the product does not edit
  user content.
- An installation with the AI features disabled: the upgrade behaves identically.
- A share link whose report came from an assistant preview: the link keeps working from the applied
  version, as every share link does.
- An installation that never used the agent: the upgrade is a no-op on its data.

## Requirements *(mandatory)*

- **FR-001**: Every screen, route, navigation item and control that exists only to author a
  dashboard inside Bizview MUST be absent from the shipped product.
- **FR-002**: Every stored thing that exists only for that flow MUST be removed after its applied
  content has been rescued into the owning project, and the rescue MUST preserve the documents
  byte for byte.
- **FR-003**: Every setting and environment variable read only by the removed flow MUST be gone;
  the AI provider setting MUST remain, defaulting to off, described as help-only.
- **FR-004**: The deleted surface MUST leave no dead code: no unused module, export, route, string
  key, test, fixture or dependency.
- **FR-005**: The help page and its search MUST keep working, and MUST stop describing the removed
  flow.
- **FR-006**: The specifications whose purpose was the removed flow MUST be marked deprecated in
  the repository, each with a one-line note naming this feature and the version.
- **FR-007**: The project constitution MUST describe the product as it is after this change.
- **FR-008**: The release notes MUST list every removed feature by its specification number.
- **FR-009**: Everything that runs, renders and shares MUST behave exactly as before: worker,
  integrations, report engine, dashboards, PDF, share links, email, TV mode, projects (files,
  versions, apply, rollback, export, import), CLI, sources, users, roles, audit, security profiles.
- **FR-010**: The published interface MUST expose no route, screen or setting of the removed area.
- **FR-011**: A repeatable gate MUST fail the build when the removed vocabulary, dead code or an
  unused dependency reappears, naming what it found and allowing only an explicit, documented
  exception list.
- **FR-012**: The change MUST be reproducible and reversible by running one upgrade step, and
  running it twice MUST change nothing.

### Key Entities

- **Applied specification**: the documents of a conversation's draft that were applied into a
  project. They are project content and outlive the conversation.
- **Conversation and its messages**: the record of an in-app authoring session. They belong to the
  removed flow and do not survive the upgrade.
- **Removal inventory**: the list of every file, route, table, setting, string key, test and
  dependency this feature removes, with the reason — produced before anything is deleted, and
  committed first.

## Success Criteria *(mandatory)*

- **SC-001**: 100% of the removed screens, routes and settings are unreachable in a running
  installation, verified by walking the product and by inspecting its published interface.
- **SC-002**: 100% of applied specifications exist in their projects after the upgrade, verified on
  a database seeded with applied conversations; no applied dashboard stops rendering.
- **SC-003**: The gates fail on a deliberately reintroduced forbidden word, dead export and unused
  package, and pass on the shipped tree.
- **SC-004**: Every existing automated suite passes, and the browser suite covering report
  rendering, sharing and projects passes unchanged.
- **SC-005**: The product measures smaller afterwards: backend image size, frontend bundle size,
  dependency count and line count are each reported before and after, and none grows.
- **SC-006**: An administrator completing the main tasks (sign in, open a dashboard, browse
  projects, import a project, share a link, read help) succeeds without meeting a dead end.

## Constitution check

- I (mobile-first): no new UI; removed screens reduce the surface. PASS
- II (backend as ETL, direct reads by exception): untouched. PASS
- III (no origin queries at render): untouched; the removed flow was the only place that ran
  ad-hoc SQL on behalf of a model, so the invariant gets stronger. PASS
- IV/V (stack): no new component; dependencies are removed, not added. PASS
- VI (data minimisation): conversations and messages are deleted; applied specifications are
  rescued rather than lost. PASS
- VII (project configuration): projects gain no new concept; the flow that edited them from inside
  the app disappears. PASS
- VIII (AI): the product keeps an optional, read-only help function and no authoring AI. PASS
- IX (authoring): redefined by this feature — authoring happens outside Bizview, against the
  published contract. The constitution is amended accordingly (FR-007). PASS

## Assumptions

- The read-only help page and its optional AI assistance stay; they author nothing.
- Access tokens stay, because the CLI uses them.
- Both existing ways of reporting a validation problem stay; only the chat-driven "apply this fix"
  path disappears.
- The upgrade rescues applied drafts and discards everything else; conversation transcripts are not
  kept, as the owner's brief says.
- Specs are moved to a deprecated folder rather than deleted, so their reasoning survives.
