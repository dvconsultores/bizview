# Tasks — 046 release, documentation and governance

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md) ·
[data-model.md](./data-model.md) · [contracts/](./contracts) · [quickstart.md](./quickstart.md)

Six commits, as the brief asks: constitution · READMEs · security/community · version and naming ·
docs and help topics · changelog and tag. Every task leaves the tree truthful: `sh
scripts/gates/all.sh` green and the documents describing what 0.2.0 ships.

## Phase 1: Setup (no code)

- [x] T001 Read `.specify/memory/constitution.md`, `VERSION`, the two READMEs, `SECURITY.md`,
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `docs/INSTALL.md`, `docs/VIBE-REPORTING.md` and
  `backend/app/guide/index.yaml`, and list in `specs/046-release-docs-governance/inventory.md`
  every statement that is no longer true (agent, Spec Kit commands in the app, modes, budgets,
  "AI Powered"), with the file and line, before editing anything

## Phase 2: Foundational (the gates that make the rest stay true)

- [x] T002 [P] Extend `scripts/gates/01-vocabulary.sh` (via `scripts/check_vocabulary.sh`) to
  cover `README.md`, `README.es.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `docs/` and `backend/app/guide/`, and add `AI Powered` to the refused vocabulary, keeping the
  allowlist (`CHANGELOG.md`, `specs/`, `backend/alembic/versions/`) with its reasons
- [x] T003 [P] Write `scripts/gates/07-version.sh`: print every copy of the version
  (`VERSION`, `backend/pyproject.toml`, `frontend/package.json`, `cli/pyproject.toml`,
  `cli/bizview_cli/__init__.py::__version__`), fail listing the ones that disagree, and check
  `/api/health.version` against `VERSION` when a backend answers (stated skip otherwise)
- [x] T004 [P] Write `scripts/gates/08-markdown.sh`: unclosed fenced blocks, table rows whose cell
  count differs from the header, relative links/images whose target is missing, headings without a
  space or duplicated verbatim, trailing whitespace after a heading, and `README.md`/`README.es.md`
  section-count parity
- [x] T005 Wire `07-version.sh` and `08-markdown.sh` into `scripts/gates/all.sh` and confirm
  `.github/workflows/gates.yml` runs them (it runs `all.sh`)
- [x] T006 Prove each new gate fails on a deliberately reintroduced offence and passes on the tree
  (version copy edited by hand; an `# asistente` line in `docs/`; a broken relative link; a table
  row with one cell too many)

## Phase 3: User Story 1 — a newcomer installs from the README (P1)

- [x] T007 [US1] Rewrite `README.md`: hero line and one screenshot placeholder, the three actions
  (install · hosted · connect my ERP), the one-screen install (two files, four values, `chown`,
  `pull` + `up -d`, private vs public, upgrade), how it works in eight steps with the CLI commands,
  the capabilities table without the assistant and with import/export, the authoring pack, the
  structure packs and the visual components, the configuration groups with `AI_PROVIDER` as
  "help only, optional", the architecture diagram, and short Security/Contributing/Licence sections
- [x] T008 [P] [US1] Rewrite `README.es.md` with the same sections, the same commands and the same
  promises as T007
- [x] T009 [US1] Verify the install path end to end on this repository: follow the README literally
  and record in `specs/046-release-docs-governance/evidence.md` what a reader types and what they
  see (or the one line that would block them)

## Phase 4: User Story 2 — an author finds the contract (P1)

- [x] T010 [US2] Write `docs/AUTHORING.md`: folder layout, `PROMPT.md`/`REQUEST.md`, the schemas in
  `cli/` as the single source, the rules, lite specifications, `bizview validate` and its
  `problems.json`, images (`assets/`, the 300 KB / 25 MB limits, the URL-column cache), and one
  complete worked example at the end
- [x] T011 [P] [US2] Write `docs/IMPORT.md`: upload → map → collisions → validate → preview →
  apply, each with its CLI equivalent
- [x] T012 [US2] Turn `docs/VIBE-REPORTING.md` into a redirect note to `docs/AUTHORING.md`, keeping
  the parts that are still the product's (the report contract itself) as links
- [x] T013 [US2] Trim `docs/INSTALL.md`: keep install, upgrade, backup, hardening; remove the
  assistant's settings, mounts and limits; make the title and the AI section say 0.2.0 reality

## Phase 5: User Story 3 — the community documents (P2)

- [x] T014 [US3] Rewrite `SECURITY.md`: supported versions (0.2.x supported, 0.1.x for 60 days after
  0.2.0), private reporting through GitHub's Security tab, acknowledgement within 3 business days,
  fix target 30 days for high severity, in-scope (product code, CLI, images, compose, the pack
  format) and out-of-scope (customer projects' own SQL/YAML, third-party APIs, installations'
  infrastructure), the protections that are true now (AES-256-GCM write-only credentials,
  `SECURITY_PROFILE=internet`, read-only origins, SSRF rules for sources and image fetches, import
  validation with content sniffing and SVG sanitisation, no AI authoring, structure packs carry no
  data)
- [x] T015 [P] [US3] Confirm `CODE_OF_CONDUCT.md` is the Contributor Covenant 2.1 and give it the
  contact address used by `SECURITY.md`
- [x] T016 [US3] Rewrite `CONTRIBUTING.md`: how to run the dev stack (moved from the old README),
  the specification workflow for product features, tests and lints including `scripts/gates/all.sh`,
  how to add a help topic and a `## Docs` section to a specification, how to propose a schema change
  (`format_version` bump + migration note + pack regeneration), commit and pull-request conventions,
  and the AGPL-3.0-or-later terms of a contribution (no CLA)

## Phase 6: User Story 4 — one version, one name (P2)

- [x] T017 [P] [US4] Set `VERSION` to `0.2.0` and align every copy: `backend/pyproject.toml`,
  `frontend/package.json`, `cli/pyproject.toml`, `cli/bizview_cli/__init__.py::__version__`
- [x] T018 [US4] Rename the product default to `Bizview`: `backend/app/config.py` (`PRODUCT_NAME`),
  `frontend/src/config/BrandingContext.tsx`, `frontend/index.html`, `cli/pyproject.toml`'s
  description, every document, page title, manifest and alternative text that says `AI Powered`
- [x] T019 [US4] Run `sh scripts/gates/07-version.sh` and the frontend/backend suites that read the
  version or the name (`frontend/tests/unit/no-literals.test.ts`,
  `frontend/tests/e2e/flows.spec.ts`, `backend/tests/test_ai.py`-style config tests) and fix what
  they catch

## Phase 7: User Story 5 — the constitution describes the product (P3)

- [x] T020 [US5] Amend `.specify/memory/constitution.md` through `/speckit-constitution`: preamble,
  folder list without `backend/app/assistant/` and with `cli/bizview_cli/workspace_template/` as the
  pack's source (and `custom_queries/` noted as superseded), principle VIII's AI boundary,
  principle IX redefined, and the constraints (import limits; the CLI's schemas as the single
  source for CLI, backend and pack) — with a Sync Impact Report that records the numbering decision
  from research R1
- [x] T021 [US5] Verify the constitution against the tree: every folder it names exists (or is
  marked superseded) and no principle names a removed capability

## Phase 8: Polish — help topics, changelog, release

- [x] T022 Regenerate the help topics that describe authoring (`backend/app/guide/{es,en}/`): the
  eight steps, the CLI commands, import, and the removal of the in-app agent; keep every topic's
  five headings, its `roles`/`routes`/`commands` metadata and its alias parity
- [x] T023 Write the `CHANGELOG.md` 0.2.0 section: Added (authoring pack, structure packs, import as
  the front door, lite specs, visual components), Changed (README/docs/constitution, naming),
  Removed (every spec 045 removed, by number), Security (import validation, SSRF for image fetch)
- [x] T024 Run the full gate suite, `ruff`, `tsc`, `vitest`, the guide/i18n backend suites and
  `sh deploy/tests/test_install.sh`; record every command and its result in
  `specs/046-release-docs-governance/evidence.md`
- [x] T025 Tag `v0.2.0` locally and write the release notes from the changelog plus 045's
  before/after numbers; record the external dependency on `bizview-site`'s hero line with its owner

## Dependencies

- Phase 2 before Phases 3–8: the gates are what keep the rewrites honest (T002–T006).
- T001 before every edit (the inventory).
- US1 (T007–T009) and US2 (T010–T013) are independent of each other; both depend on T002.
- US4 (T017–T019) depends on nothing but T003 (the version gate).
- T022 (help topics) depends on T010–T013 (the documents they mirror).
- T023–T025 come last: they report what the tree became.

## Parallel opportunities

- T002, T003, T004 are three different scripts (three editors or three commits).
- T008 runs beside T007 once T007's section list exists; T011 beside T010.
- T015 and T017 touch different files than T014/T016.

## MVP scope

T001–T009: the gates, the inventory and the two READMEs. A reader can install 0.2.0 from the front
page and every later phase only makes the rest of the corpus match.
