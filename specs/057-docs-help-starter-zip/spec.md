# Feature Specification: Help and README that match the product, and a ready-to-use starter zip

**Feature Branch**: `main` (this repository works on `main` only; no feature branches)

**Created**: 2026-11-06

**Status**: Draft

**Input**: Owner, 2026-11-06: "Since 043/045 a project is authored outside Bizview with whatever AI
the user prefers or by hand, then imported. The in-app help, the README and parts of `docs/` still
describe the removed chat agent and 'vibe reporting', and the only way to get the authoring pack is
`bizview init workspace` on a machine with the CLI. A non-technical admin must be able to click
Descargar paquete inicial, hand the zip to their AI with one sentence, and import the result."

**Builds on**: 043 (external authoring), 045 (agent removed), 046 (release docs), 048 (BI-ready
sources), 049 (import limits and assets), 052 (source structure), 055 (re-import).

**Constitution**: no amendment. Principles VIII (AI optional and external), IX (spec-driven,
authored outside) and II (nothing but structure leaves the installation) are what this feature
makes visible to a reader.

## Why

Three surfaces still describe a product that no longer exists: the in-app guide (section "Agente y
Spec Kit"), the README ("How it works" and the capability table), and parts of `docs/`. At the same
time the authoring pack — the one artifact a customer must have to start — is only reachable from a
terminal. A non-technical administrator is therefore told to use a deleted screen and handed no
usable entry point.

This feature closes that gap: one downloadable starter zip built by the product, one generic
template published with every release, and help and documentation that describe what the reader can
actually do today.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator downloads a starter pack and hands it to their AI (Priority: P1)

A non-technical administrator opens **Proyectos**, presses **Nuevo proyecto → Descargar paquete
inicial**, types the project name, optionally picks a registered source and a language, chooses
whether the first spec is an integration plus a report or a direct report, and downloads
`bizview-starter-<slug>.zip`. They unzip it, fill `REQUEST.md` in one sentence, paste `PROMPT.md` and
`REQUEST.md` into whichever AI they use, get a zip back, and import it in Bizview.

**Why this priority**: without this the product has no reachable front door for the audience 043
defined.

**Independent Test**: download the pack for each combination of source, language and kind; each zip
validates with zero errors and imports as a draft whose only problems are the intentional "fill me"
placeholders.

**Acceptance Scenarios**:

1. **Given** the Proyectos empty state, **When** it loads, **Then** it offers **Descargar paquete
   inicial** and **Descargar plantilla general**.
2. **Given** the dialog, **When** the administrator confirms a name, a language and a kind, **Then**
   the download is `bizview-starter-<slug>.zip` and contains every file of the pack contract.
3. **Given** a chosen source, **When** the zip is built, **Then** it carries
   `sources/<name>/structure.md` and `structure.json` and nothing else from that source: no
   credentials, no host, no row values.
4. **Given** a pack whose files exceed the import allowance, **When** the download is requested,
   **Then** it is refused naming the allowance, before a byte is served.

---

### User Story 2 - The pack is self-contained enough to paste into a chat (Priority: P1)

An author uses a chat window, not a folder: they paste `PROMPT.md` and `REQUEST.md` (and the
structure file when a source was picked) into ChatGPT, Claude, Gemini, DeepSeek or Copilot and ask
for the project. The prompt states the file contract, the validation rules, the required artefacts
and that the answer is one zip with the project files at the root.

**Why this priority**: the most common tool the audience has is a chat window. A prompt that only
works from a checked-out folder excludes them.

**Independent Test**: paste `PROMPT.md` alone into a fresh chat and ask for a project; the answer can
be assembled into a zip that passes validation.

**Acceptance Scenarios**:

1. **Given** `PROMPT.md`, **When** it is read alone, **Then** it states the output shape (one zip,
   project files at the root), the required spec files, every task marked `[X]`, the schema rules
   that reject a naive answer, and the import budgets.
2. **Given** the pack's own examples, **When** the whole pack is rendered and validated, **Then**
   validation reports zero errors.
3. **Given** `CLAUDE.md` and `AGENTS.md`, **When** they are compared with `PROMPT.md`, **Then** they
   carry the same rules for tools that read a folder.

---

### User Story 3 - Every zip explains itself to a non-technical reader (Priority: P2)

Whoever opens the zip finds `CONTENIDO.md`/`CONTENTS.md` and `QUE-HACE-BIZVIEW.md`/
`WHAT-BIZVIEW-DOES.md` in both languages: what each file is, who writes it, whether it is required,
what Bizview does with it on import, and a plain-language walkthrough of import and apply.

**Why this priority**: the author may not know what a schema or a spec is, and guessing produces a
zip that fails validation.

**Independent Test**: hand the zip to a person who has never seen Bizview and ask them to explain
what to do first; the two documents answer it.

**Acceptance Scenarios**:

1. **Given** any zip this feature produces, **When** its entries are listed, **Then** both content
   documents are present in both languages.
2. **Given** `CONTENIDO.md`, **When** it is read against the zip, **Then** every file in the zip is
   documented with its requirement, author and import behaviour.
3. **Given** the help topic `importar-y-aplicar`, **When** it is compared with the zip's
   `QUE-HACE-BIZVIEW.md`, **Then** they say the same thing (one text, rendered to both places).

---

### User Story 4 - A generic template is published with each release (Priority: P2)

Someone without an installation, or the project page of a colleague, downloads
`bizview-starter-template.zip` from the repository, from the release assets or from the app's
Proyectos empty state. It has no name and no source: placeholders decide later.

**Why this priority**: the README and the release are the public front door (046); the template must
be reachable without an account.

**Independent Test**: download the template from the repository and from the app; both are byte
identical to what the pack renders.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** `make starter-template` runs, **Then** it writes
   `bizview-starter-template.zip` at the repository root deterministically.
2. **Given** the committed zip and the pack, **When** CI compares them, **Then** a pack change
   without a regenerated zip fails.
3. **Given** `GET /api/projects/starter-template`, **When** it is called by an administrator,
   **Then** it serves that zip with the zip content type and its exact size.

---

### User Story 5 - The help page teaches the real flow (Priority: P3)

A superuser presses **Ayuda**, searches "paquete inicial" and finds a section **Crear con tu IA**:
what the zip is, how to fill `REQUEST.md`, how to use it with any AI, how to validate, how to fix
problems and how to re-import changes. **Primeros pasos** is the five-step path from source to
applied dashboard.

**Why this priority**: help that documents a deleted chat is worse than no help.

**Independent Test**: search the guide for the removed vocabulary and find nothing; follow the five
steps on a clean installation and reach an applied dashboard.

**Acceptance Scenarios**:

1. **Given** the guide index, **When** it is read, **Then** there is no section about an agent and
   every topic of the new section exists in Spanish and English.
2. **Given** a topic body, **When** it ends, **Then** it has **Relacionados** and, where a screen
   exists, an app link.
3. **Given** the guide corpus, **When** it is searched for the removed vocabulary, **Then** nothing
   matches.

---

### User Story 6 - The README and docs say what the product does (Priority: P3)

A newcomer reads the README and understands the five steps with **Descargar paquete inicial** as
step three; the capability table lists what exists after 047–055; `docs/AUTHORING.md` starts with
the starter zip; `docs/REPORTS.md` replaces the chat-era name; `docs/IMPORT.md` links the zip.

**Why this priority**: the documents are the release (046) and must not lag the product.

**Independent Test**: give the README to a newcomer; they name the three download entry points and
the AI-optional rule without opening another document.

**Acceptance Scenarios**:

1. **Given** `README.md` and `README.es.md`, **When** they are compared, **Then** they have the same
   structure and the same promises.
2. **Given** the documentation corpus, **When** it is searched for the removed vocabulary, **Then**
   nothing matches, apart from the one-line compatibility stub allowed for the renamed document.
3. **Given** the markdown gate, **When** it runs over the changed documents, **Then** it passes.

### Edge Cases

- A source is selected but has no stored structure: the structure is generated on the fly from the
  same generator the structure pack uses, and the download still succeeds (or says why it cannot).
- A source belongs to another installation's credentials: the download never reads a row value.
- The project name yields an empty slug (all symbols): the dialog refuses with a message naming the
  field.
- A name that already exists: the pack is still built; identity is decided at import (055).
- The committed template is missing in a deployment: the endpoint renders the template in memory
  instead of failing.
- An author edits the pack and does not regenerate the committed zip: CI fails naming both.

## Requirements *(mandatory)*

### Functional Requirements

**Starter pack**

- **FR-001**: The product MUST offer **Descargar paquete inicial** from Proyectos → Nuevo proyecto,
  from the Proyectos empty state, and from the help topic that explains it.
- **FR-002**: The dialog MUST collect project name, optional source, pack language (es/en, default the
  viewer's) and first-spec kind (integration plus report, or direct report).
- **FR-003**: The download MUST be named `bizview-starter-<slug>.zip` and be built on the server
  from one pack source, with the selections applied.
- **FR-004**: A selected source MUST contribute `sources/<name>/structure.md` and `structure.json`
  only — never credentials, hosts, connection strings or row values.
- **FR-005**: Every zip MUST contain the pack contract: `PROMPT.md`, `REQUEST.md`, `project.yaml`,
  `specs/001-<slug>/{spec,plan,tasks}.md`, `reports/<slug>/report.yaml`, the integration skeleton
  and example query (omitted for a direct report), `.bizview/schemas/*.json`,
  `.bizview/preset.yaml`, `CLAUDE.md`, `AGENTS.md`, `README.md`, and the two bilingual explanatory
  documents.
- **FR-006**: `PROMPT.md` MUST be self-contained (works pasted into a chat), under 1,500 words, and
  MUST state the output shape, the required files, the nine checks the validator applies and the
  import budgets.
- **FR-007**: The rules in `PROMPT.md` MUST be the validator's: a unit test renders the pack and runs
  the validator over it with zero errors.
- **FR-008**: The pack MUST be shippable as one generic template with placeholders, produced by
  `make starter-template`, committed at the repository root and served by the app.
- **FR-009**: The CLI MUST write the same pack (`bizview init project <name> [--source <s>]`) so one
  source produces the download, the template and the CLI's output.
- **FR-010**: Every zip MUST ship `CONTENIDO.md`/`CONTENTS.md` and
  `QUE-HACE-BIZVIEW.md`/`WHAT-BIZVIEW-DOES.md`, in both languages, and the contents document MUST
  cover every file the zip contains.
- **FR-011**: Every text shipped inside the zip MUST exist in Spanish and English.

**Help**

- **FR-012**: The guide MUST have a section **Crear con tu IA** with topics for the starter pack, the
  request, handing it to an AI, validating, fixing problems, re-importing and one complete example.
- **FR-013**: **Primeros pasos** MUST describe the five steps: source, structure, starter pack, your
  AI, import.
- **FR-014**: Topics about importing, structure, integrations, reports, spec kinds, VS Code, AI,
  themes, images, limits, parameters and Google sign-in MUST describe the shipped product.
- **FR-015**: Every topic MUST end with **Relacionados** and, where a screen exists, an app link.
- **FR-016**: The guide MUST NOT contain the removed vocabulary (the in-app agent, its chat, "vibe").

**Documentation**

- **FR-017**: `README.md`/`README.es.md` MUST present the five steps with the starter download as
  step three, list the capabilities that exist today and state that no AI key is needed.
- **FR-018**: `docs/AUTHORING.md` MUST start with the starter zip and the pack layout.
- **FR-019**: `docs/VIBE-REPORTING.md` MUST be renamed to `docs/REPORTS.md`, keeping a stub at the old
  path.
- **FR-020**: `docs/IMPORT.md` MUST link the starter pack and describe import and apply in plain
  language.
- **FR-021**: Documentation MUST exist in English with Spanish mirrors for authoring, import and
  reports.
- **FR-022**: `CHANGELOG.md` MUST record the change under Unreleased.

**Gates**

- **FR-023**: Tests MUST prove the download, the template, the CLI output and the committed zip agree,
  that every zip documents every file it carries, and that `bizview validate` accepts the rendered
  pack.

### Key Entities

- **Starter pack**: the folder of templates a project begins as; bilingual; rendered with a name,
  slug, language, first-spec kind and optional source structure.
- **Starter template**: the same pack with placeholders, published at the repository root.
- **Structure pack**: the source's tables, columns and shapes with no credentials or values.
- **Content document**: the per-file explanation shipped in every zip.
- **Import walkthrough**: the plain-language account of import and apply, shipped in every zip and
  used as the help topic `importar-y-aplicar`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator with no terminal reaches a downloaded starter zip in under two minutes
  from opening Proyectos, on the first attempt.
- **SC-002**: Every combination of the dialog (with/without source, two kinds, two languages) produces
  a zip the validator accepts with zero errors.
- **SC-003**: The prompt fits in one chat message: under 1,500 words.
- **SC-004**: Every zip explains itself: 100 % of its entries appear in the contents document, and
  each entry names who writes it and whether it is required.
- **SC-005**: No document or help topic mentions the removed agent: a repository-wide search returns
  nothing.
- **SC-006**: A reader of the README names the starter download and the AI-optional rule after one
  screen.

## Assumptions

- The pack is rendered from one folder at the repository root, shipped inside the CLI package by the
  build, so an installed CLI and the server use the same bytes.
- A source's structure is generated with the existing generator (048/052); when generation fails the
  download still succeeds without the structure and says so.
- Both languages are always shipped; the dialog only decides which one is primary and which carries
  the `.en.md`/`.es.md` suffix.
- `docs/es/` mirrors exist for AUTHORING, IMPORT and REPORTS; other documents may remain English-only.
- The nine checks named in `PROMPT.md` are the validator's error classes, listed by name.
