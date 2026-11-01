# Implementation Plan: Release, documentation and governance for 0.2.0

**Branch**: `main` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/046-release-docs-governance/spec.md`

**Note**: This feature writes documents, not product surface. The only code it adds is the version
check and the documentation gates, because the requirements that matter (SC-003, SC-004) only stay
true if a check enforces them.

## Summary

Rewrite the documents that describe the product so they match what 0.2.0 ships, publish the
release under the name **Bizview**, and make the version a single truth. Concretely: finish the
constitution's amendment (preamble, folder list, AI boundary, constraints, Sync Impact Report);
rewrite both READMEs around the eight-step authoring loop; rewrite SECURITY, CONTRIBUTING and
confirm CODE_OF_CONDUCT; add `docs/AUTHORING.md` and `docs/IMPORT.md` and retire the parts of
`docs/VIBE-REPORTING.md` they supersede; regenerate the help topics; set `VERSION` to `0.2.0` with
one source of truth and a check that every copy agrees; extend 045's gates to the documents and add
markdown/link checks; and write the 0.2.0 changelog.

## Technical Context

**Language/Version**: Markdown for the documents; the checks are POSIX `sh` (as 045's gates are),
with a small Python step for the version comparison, run by the repository's own `uv`-managed venv.

**Primary Dependencies**: none new. `scripts/gates/*.sh` (045) and `ruff`/`python` from the dev
venv; `node` for the frontend type check the existing gates already run. Markdown lint is done by a
small `sh` + `awk`/`grep` check over the same files rather than by adding a Node or Python
markdown-lint dependency.

**Storage**: none. The version lives in `VERSION` at the repository root; the backend already reads
it (`app/config.py::_file_version`), `deploy.sh` already tags images from it.

**Testing**: the gates themselves are the tests (`scripts/gates/0{1..6}-*.sh`), each proved to fail
on a deliberately reintroduced offence; `sh scripts/gates/all.sh` is the entry point and
`.github/workflows/gates.yml` runs it. `backend/tests/` and `frontend/tests/` cover the two code
changes (version read, product name default).

**Target Platform**: the repository (documents) and any installation (version/health).

**Project Type**: documentation and repository governance for a self-hosted web product.

**Performance Goals**: `sh scripts/gates/all.sh` stays under two minutes on CI; the version check is
a file read.

**Constraints**: no new runtime dependency; no change to product behaviour; every command a
document tells a reader to type must exist in the tree; the Spanish and English documents keep
their structure in step.

**Scale/Scope**: 2 READMEs, 4 top-level policy/community documents, the constitution, 3 documents
under `docs/`, 48 help topics in two languages, 1 version file and ~6 copies of the number.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Specification before code | This feature has a spec, a plan and tasks; the documents it writes are the implementation | PASS |
| II. Nothing runs unvalidated | No product code path changes; the version check adds no execution path | PASS |
| IV. Separated concerns by folder | `docs/` holds reader documents, `scripts/gates/` the checks, `cli/` the contract; no cross-folder shortcut is introduced | PASS |
| V. Fixed technology stack | No dependency added; the gates use `sh` and the existing venv | PASS |
| VIII. AI optional and private | The rewrite *states* the boundary (no AI authoring, structure packs carry no data) and removes the assistant's data-boundary claims | PASS |
| IX. Spec-driven reporting (redefined) | The documents describe authoring outside the product and import as the way in; the constitution's folder list and principle text are corrected to match | PASS |
| X. Migration and release discipline | 0.2.0 is a MAJOR release with a changelog that names every removal; the version check prevents an untagged mismatch | PASS |

No violation needs justification. The one recorded tension — the brief says the constitution
becomes 2.0.0 while the file already records that from 2.1.0 the correct MAJOR bump is 3.0.0 — is
resolved in research R1 and written into the Sync Impact Report rather than silently renumbering.

## Project Structure

### Documentation (this feature)

```text
specs/046-release-docs-governance/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── version-contract.md
│   └── docs-gates.md
└── tasks.md             # /speckit-tasks output
```

### Source Code (repository root)

```text
VERSION                                  # single source of truth → 0.2.0
README.md  README.es.md                  # rewritten around the eight-step loop
SECURITY.md  CODE_OF_CONDUCT.md  CONTRIBUTING.md
.specify/memory/constitution.md          # amendment: preamble, folders, AI, constraints, report
docs/
├── INSTALL.md                           # trimmed for operators
├── AUTHORING.md                         # NEW: the contract and the worked example
├── IMPORT.md                            # NEW: upload → … → apply, with CLI equivalents
└── VIBE-REPORTING.md                    # superseded parts folded into AUTHORING.md
backend/app/config.py                    # PRODUCT_NAME default → Bizview
backend/app/guide/{es,en}/*.md           # help topics regenerated to match
backend/app/guide/index.yaml             # sections and topic metadata
frontend/index.html  frontend/src/config/BrandingContext.tsx
cli/pyproject.toml  backend/pyproject.toml  frontend/package.json
scripts/gates/
├── 01-vocabulary.sh                     # extended to the documents
├── 07-version.sh                        # NEW: one source of truth, /api/health agrees
└── 08-markdown.sh                       # NEW: markdown lint + link check on top-level docs
CHANGELOG.md                             # 0.2.0 section
```

**Structure Decision**: documents live where a reader expects them (`README*` and the policy files
at the root, guides in `docs/`, in-app help in `backend/app/guide/`), and the checks that keep them
honest live with 045's gates in `scripts/gates/` so there is exactly one command to run and one CI
job to wire.

## Complexity Tracking

No constitution violation. Deliberate simplifications, recorded so a reviewer does not ask:

- **No markdown-lint dependency.** A full linter would add a Node or Python package for a
  repository whose documents are hand-written and reviewed; the gate checks what actually breaks
  (unclosed fenced blocks, tables whose column count disagrees with the header, relative links that
  do not resolve, trailing whitespace in headings).
- **The Spanish README is not a translation of the English one at build time.** Both are written by
  hand; a gate compares their section headings so they cannot drift silently.
