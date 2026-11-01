# Feature Specification: Release, documentation and governance for 0.2.0

**Feature Branch**: `main` (this repository works on `main` only; no feature branches)

**Created**: 2026-10-31

**Status**: Draft

**Input**: User description: "046-release-docs-governance — README, SECURITY, constitution, code of conduct, contributing, version 0.2.0. Make every document that describes the product true again after the refactor: Bizview is a runtime that describes sources, validates, imports, runs and shares projects authored outside it. Ship as 0.2.0 under the plain name Bizview."

## Context

Features 043 and 045 changed what the product *is*: projects are authored outside Bizview and
enter through validation and import, and the in-app authoring agent is gone. The documents that
describe the product — the constitution, both READMEs, the security policy, the contributing
guide, the install and authoring guides, the in-app help topics — still describe the product the
agent needed. A reader who meets 0.2.0 today is told about a chat that does not exist and about a
name ("AI Powered") the product no longer uses.

This feature is the release wrapper: it makes the written product match the shipped product and
publishes it as **0.2.0** under the name **Bizview**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A newcomer understands the product in one screen and installs it (Priority: P1)

Someone who has never seen Bizview lands on the repository README. Within one screen they learn
what the product does (their business data on their phone, reports built with any AI, Bizview
validates, runs and shares them), and they can install it: two files, four values, one `chown`
line, `pull` and `up -d`.

**Why this priority**: the README is the front door of a public repository; if it lies, nothing
else in this feature matters. Everything else in the release assumes a reader who got this far.

**Independent Test**: give the README to a person who has never run Bizview and ask them to install
it on a fresh server without asking questions. They either succeed or name the one line that
blocked them; both outcomes are readable from the document alone.

**Acceptance Scenarios**:

1. **Given** the public repository, **When** a reader opens the README, **Then** the first screen
   states what the product does, shows one screenshot, and offers three actions (install, hosted
   product, connect my ERP).
2. **Given** the README's install section, **When** the reader follows it on a fresh server,
   **Then** they never have to open another document to reach a running installation.
3. **Given** the README in Spanish, **When** the reader compares it with the English one, **Then**
   both have the same structure, the same commands and the same promises.
4. **Given** the README, **When** a reader searches for the assistant, the app's slash commands,
   the modes, the budgets or "AI Powered", **Then** nothing is found.

---

### User Story 2 - An author finds the contract and the eight steps (Priority: P1)

Someone who has a data source wants a dashboard. They need one document that says: add a source,
download the authoring pack, fill `REQUEST.md`, build with any AI (or by hand), validate with the
CLI, import, apply, share — with the commands they type at each step.

**Why this priority**: authoring moved outside the product (043). If the contract is not written
down and reachable, the product has no way in.

**Independent Test**: a reader with a data source and no prior knowledge follows the eight steps to
an applied dashboard, using only the authoring document and the CLI's own `--help`.

**Acceptance Scenarios**:

1. **Given** the repository, **When** the reader opens the authoring guide, **Then** it lists the
   folder layout, `PROMPT.md`/`REQUEST.md`, the schemas, the rules, lite specifications, the
   validation step, `problems.json` and images, and ends with one complete worked example.
2. **Given** the import path, **When** the reader opens the import guide, **Then** upload → map →
   collisions → validate → preview → apply are described with their CLI equivalents.
3. **Given** an author who wrote a project with an external AI, **When** they validate it, **Then**
   the document tells them what the validator checks and how to read its report.

---

### User Story 3 - A security reporter and a contributor know where to go (Priority: P2)

Someone who found a vulnerability, and someone who wants to send a change, each open one file and
find the process, the expectations and the boundaries — without reading the code.

**Why this priority**: a public AGPL product without a truthful security policy and contribution
guide collects reports in public issues and pull requests nobody can merge.

**Independent Test**: hand SECURITY.md to a person who believes they found a vulnerability and ask
them where to report it and what happens next; hand CONTRIBUTING.md to a person who wants to fix a
typo and ask them how.

**Acceptance Scenarios**:

1. **Given** SECURITY.md, **When** a reporter reads it, **Then** they know the private channel, the
   acknowledgement time, the fix target, what is in scope and what is not, and what the product
   protects by itself.
2. **Given** SECURITY.md, **When** a reader looks for the assistant's data boundary, **Then** it is
   not there, and the structure-pack statement (structure, counts and shapes only) is.
3. **Given** CONTRIBUTING.md, **When** a contributor reads it, **Then** they find the dev stack, the
   spec workflow for product features, the tests and lints, how to add a help topic and how to
   propose a schema change, plus the commit and pull-request conventions.
4. **Given** CODE_OF_CONDUCT.md, **When** a contributor reads it, **Then** it is the Contributor
   Covenant 2.1 with a reachable contact address.

---

### User Story 4 - The version and the name are one truth (Priority: P2)

An operator asks "what version is this?" and gets the same answer from the footer, from
`/api/health`, from the image tag and from the repository — and the product is called Bizview, not
"Bizview AI Powered".

**Why this priority**: the release cannot be tagged while four files disagree about the number, and
the rename is what makes the release notes honest.

**Independent Test**: change the version in one place and run the project's own check; it either
propagates or fails loudly listing the copies that disagree.

**Acceptance Scenarios**:

1. **Given** a fresh 0.2.0 installation, **When** an operator reads the footer and `/api/health`,
   **Then** both say 0.2.0.
2. **Given** the repository, **When** someone bumps the version in the single source of truth,
   **Then** the check that compares every copy passes, and when a copy is edited by hand it fails
   naming that copy.
3. **Given** any shipped string, page title, manifest, image alternative text or document,
   **When** a reader looks for "AI Powered", **Then** it is not there; an installation may still
   choose its own product name.
4. **Given** the changelog, **When** a reader opens the 0.2.0 section, **Then** it lists what was
   added, what changed, what was removed by spec number, and what was hardened.

---

### User Story 5 - The rules of the project describe the project (Priority: P3)

A maintainer reads the constitution and finds the product 0.2.0 actually ships: no authoring agent
in the folder list, the authoring pack as the source of the contract, the AI boundary stated, and
the import limits written down.

**Why this priority**: the constitution is what future features are checked against; a stale one
re-introduces what 045 deleted.

**Independent Test**: read principle IX and the folder list, then try to find the folder or the
capability they describe in the tree; every one exists (or is explicitly superseded).

**Acceptance Scenarios**:

1. **Given** the constitution, **When** a reader looks for the authoring agent's folder or its
   commands, **Then** it is absent from the folder list and from principle IX.
2. **Given** the constitution, **When** a reader looks for the contract's source of truth, **Then**
   the schemas in the CLI are named as the single source used by CLI, backend and pack.
3. **Given** the constitution, **When** a reader looks for import limits and the AI boundary,
   **Then** both are stated as constraints.

---

### Edge Cases

- **A link that points at something that no longer exists**: a document that links to the
  deprecated specs folder, to a removed help topic or to a site page still using the old name. The
  repository's own checks must fail rather than a reader discovering it.
- **An installation that renamed the product**: `PRODUCT_NAME` is an installation setting, so no
  check may assume the literal name in a running installation's screens.
- **A version bump in one place only**: the release must not be taggable while copies disagree.
- **A translated document that drifts**: the Spanish README losing a step the English one has.
- **Help topics that still describe the agent**: the in-app help is generated from the same
  source as the docs, so it drifts the moment a document changes.
- **A security report about a customer's own project**: the policy must say clearly that a
  customer's SQL and YAML are theirs, not the product's.
- **The site repository** (`bizview-site`) carrying the old hero line: the release must not depend
  on a change that lives in another repository without recording it as an external dependency.

## Requirements *(mandatory)*

### Functional Requirements

**Governance**

- **FR-001**: The project constitution MUST describe the product 0.2.0 ships: authoring outside
  the product, the folder list without the removed module and with the authoring pack as the
  contract's source, the AI boundary (read-only help and connectors only; structure packs contain
  structure, counts and shapes — never credentials, hosts or row values), the redefined
  spec-driven principle, and the import limits.
- **FR-002**: The constitution MUST name the CLI's schemas as the single source of the contract
  used by the CLI, the backend and the authoring pack.
- **FR-003**: Every change to the constitution MUST carry a Sync Impact Report that states the
  version change, the principles modified and the deprecated specifications.

**Front door**

- **FR-004**: `README.md` and `README.es.md` MUST describe the product as a runtime that
  describes sources, validates, imports, runs and shares projects authored outside it, with the
  same structure in both languages and no reference to the removed authoring surface.
- **FR-005**: Both READMEs MUST let a reader install the product without opening another document,
  and MUST link to the hosted product and to the authoring path.
- **FR-006**: Both READMEs MUST present the eight authoring steps with the commands a reader types.

**Security and community**

- **FR-007**: `SECURITY.md` MUST state the private reporting channel, the acknowledgement and fix
  targets, the supported versions, the in-scope and out-of-scope surface, and the protections the
  product provides by itself.
- **FR-008**: `CODE_OF_CONDUCT.md` MUST be the Contributor Covenant 2.1 with a reachable contact
  address.
- **FR-009**: `CONTRIBUTING.md` MUST state how to run the development stack, the specification
  workflow for product features, the tests and lints, how to add a help topic and a documentation
  section to a specification, how to propose a schema change, and the commit and pull-request
  conventions including the licence terms of a contribution.

**Version and naming**

- **FR-010**: The product version MUST have one source of truth, and every other copy MUST be
  derived from it or verified against it by an automated check.
- **FR-011**: The product name MUST be `Bizview`, with no marketing suffix in any shipped string,
  page title, manifest, alternative text, document or package description; an installation MUST
  still be able to choose its own name.
- **FR-012**: `CHANGELOG.md` MUST carry a 0.2.0 section listing what was added, changed, removed
  (by specification number) and hardened.

**Authoring and documentation**

- **FR-013**: A reader MUST find the authoring contract in one document: folder layout, the
  request and prompt files, the schemas, the rules, lite specifications, validation and its
  report, images, and one complete worked example.
- **FR-014**: A reader MUST find the import path in one document, with the CLI equivalents of each
  step.
- **FR-015**: The install guide MUST keep what an operator needs and MUST NOT describe the removed
  authoring surface.
- **FR-016**: The in-app help topics MUST match the documents that describe the same behaviour.

**Gates (what makes the above stay true)**

- **FR-017**: An automated check MUST fail when any of the removed vocabulary appears in the
  READMEs, the security policy, the contributing guide, the documentation folder or the help
  topics, with an explicit allowlist for the changelog and the deprecated specifications.
- **FR-018**: An automated check MUST fail when the version copies disagree, and when
  `/api/health` does not report the repository's version.
- **FR-019**: Markdown lint and link checking MUST run over the top-level documents and fail on a
  broken link or a malformed table.

### Key Entities

- **Constitution amendment**: the version, the Sync Impact Report, the principles modified, the
  deprecated specifications listed.
- **Version source of truth**: one value that the backend, the frontend, the CLI and the
  deployment read or are checked against.
- **Authoring contract document**: the folder layout, the request and prompt files, the schemas,
  the rules, the validation report and the worked example.
- **Help topic**: a reader-facing page in two languages, generated from the same knowledge as the
  documents.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person who has never used the product can install it from the README alone on a
  fresh server, without opening another document and without asking a question.
- **SC-002**: The two READMEs have the same number of sections and the same commands: 100 % parity
  in a comparison a maintainer can run.
- **SC-003**: Zero occurrences of removed vocabulary or of the old product name in the READMEs, the
  security policy, the contributing guide, the documentation folder and the help topics — enforced
  by a check that fails, not by a review.
- **SC-004**: Every version copy agrees with the single source, verified automatically; the running
  product reports the same number in its footer and in its health answer.
- **SC-005**: The 0.2.0 changelog names every removed feature by specification number, so a reader
  can trace each removal to the feature that owned it.
- **SC-006**: A reader reaches the authoring contract and its worked example from the repository's
  front page in one click.
- **SC-007**: Reporters and contributors reach their process in one file each, and a broken link in
  the top-level documents fails a check instead of a reader.

## Assumptions

- **The release is 0.2.0 under the name `Bizview`.** The brief's decision; the marketing suffix is
  dropped from shipped strings and documents while `PRODUCT_NAME` stays an installation setting.
- **The constitution's substance already moved.** Features 043/045 applied principle IX, the folder
  list and the AI boundary, and the file records that the number written in 043 as "2.0.0" was
  taken against an older copy, so a MAJOR bump from 2.1.0 is 3.0.0. This feature keeps the substance,
  finishes the preamble and the constraints the brief lists, and records the numbering decision in
  the Sync Impact Report instead of downgrading the number.
- **`VERSION` at the repository root is the single source of truth**; the backend already reads it,
  and the remaining copies (frontend, CLI, image tags, documentation) are verified against it.
- **The site repository is external.** Changing its hero line is recorded as an external dependency
  with an owner; the release does not block on it.
- **No new reader-facing product surface is created**: this feature writes, edits and checks
  documents, plus the small amount of code the version check and the gates need.
- **The removed vocabulary list** is the one 045's gate already enforces, extended to the documents
  this feature touches.
