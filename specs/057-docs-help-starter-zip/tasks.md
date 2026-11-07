# Tasks — 057 help, README and starter zip

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/starter-api.md](./contracts/starter-api.md)

Legend: `[P]` can run in parallel with its neighbours; `[X]` done.

## Phase 1 — The pack (foundation)

- [X] T001 Write `pack/bizview-starter-pack/es/{PROMPT,REQUEST,README,CONTENIDO,QUE-HACE-BIZVIEW}.md`
- [X] T002 Write `pack/bizview-starter-pack/en/{PROMPT,REQUEST,README,CONTENTS,WHAT-BIZVIEW-DOES}.md`
- [X] T003 Write the skeletons under `pack/bizview-starter-pack/files/` (project.yaml, bizview.yaml,
      specs, integration + example query, report, `.bizview/preset.yaml`) with bilingual comments
- [X] T004 Write `cli/bizview_cli/starter.py`: `pack_dir()`, `render()`, `zip_bytes()`,
      `TEMPLATE_NAME`, language selection and placeholders
- [X] T005 Ship the pack inside the wheel (`hatch` force-include) so an installed CLI finds it
- [X] T006 `cli/bizview_cli/init.py`: `init project <name>` + pack-based `init workspace`
- [X] T007 `cli/bizview_cli/__main__.py`: the `init project` subcommand and its `--help`
- [X] T008 i18n strings for the new CLI output (es/en)
- [X] T009 `scripts/build_starter_template.py` and the root `Makefile` target `starter-template`
- [X] T010 Generate and commit `bizview-starter-template.zip`

## Phase 2 — Server

- [X] T011 `backend/app/projects/starter.py`: `build()` (render, structure document, budget check)
- [X] T012 `GET /api/projects/starter` and `GET /api/projects/starter-template`, declared before
      `/{slug}`
- [X] T013 Expose the budget refusal from `zip.py` so both paths speak the same message
- [X] T014 Backend i18n keys (`app/i18n/es.py`, `en.py`)

## Phase 3 — Frontend

- [X] T015 `StarterDialog` component (name, source, language, kind; link to help)
- [X] T016 Proyectos: "Nuevo proyecto" button, empty state with both downloads
- [X] T017 `projectsApi.starterUrl` / `starterTemplateUrl`; `es.ts` / `en.ts` keys

## Phase 4 — Help

- [X] T018 Guide loader: accept `Relacionados`/`Related` as a closing section
- [X] T019 `index.yaml`: replace `agente` with `crear-con-ia`; add the eight new topics; move the
      artifact topics into it
- [X] T020 Write `crear-con-ia` topics in es and en
- [X] T021 Rewrite `primeros-pasos` and the topics that drifted (import, structure, integrations,
      reports, spec kinds, VS Code, AI, themes, images, limits, parameters, Google)
- [X] T022 Append `Relacionados`/`Related` with app links to every topic
- [X] T023 `labels-allow.txt` + `tests/test_guide.py` count

## Phase 5 — Documents

- [X] T024 `README.md` / `README.es.md`: five steps, capability table, author-with-your-AI paragraph
- [X] T025 `docs/AUTHORING.md`: starter zip first, pack layout, paste-into-chat, nine checks
- [X] T026 `docs/REPORTS.md` from `docs/VIBE-REPORTING.md` + stub; `docs/IMPORT.md` links
- [X] T027 `docs/es/{AUTHORING,IMPORT,REPORTS}.md` mirrors
- [X] T028 `CHANGELOG.md` under Unreleased

## Phase 6 — Proof

- [X] T029 `cli/tests/test_starter.py` (combinations, validator, contents, determinism, prompt size)
- [X] T030 `backend/tests/test_starter_api.py` (both routes, refusal, content type)
- [X] T031 Run the suites and the gates; fix what they find

## Dependencies

T001–T003 → T004 → (T006, T007, T009) → T010 → T011/T012 → T015/T016; T018 → T019 → T020/T021 → T022.

## Convergence 057b — what the product does, and every document in both languages

Found after 057 (2026-11-06), assessed against the code: nothing in the shipped documents said how
a `report.yaml` is **executed** — periods, comparison, cache, rollups, layouts — and bilingual
coverage was partial (`docs/es/` held three shortened documents; INSTALL, THEMES, DESIGN-SYSTEM,
CONTRIBUTING, SECURITY, CODE_OF_CONDUCT and DIAGNOSIS had no Spanish at all).

- [X] T032 `docs/RENDERING.md` + `docs/es/RENDERING.md`: six numbered steps, each citing the file that
      does it (`engine/report.py`, `engine/periods.py`, `api/reports.py`, `engine/rollup.py`,
      `engine/snapshot.py`, `reports/pdf.py`, `LayoutRenderer.tsx`), the "What each key controls at run
      time" table and one real generated statement quoted from the engine (partial)
- [X] T033 `docs/assets/rendering.mmd` + `docs/assets/rendering.svg` (rendered with
      `scripts/render_mermaid.js`) and a six-line block in both READMEs linking the document (missing)
- [X] T034 The two short forms of the same text: `COMO-SE-DIBUJA.md` / `HOW-IT-RENDERS.md` inside every
      starter zip (wired into `cli/bizview_cli/starter.py`, documented in CONTENIDO.md/CONTENTS.md,
      template regenerated) and the guide topic `como-se-dibuja-un-tablero` in `crear-con-ia`, both
      languages (missing)
- [X] T035 `scripts/check_docs_parity.py`: heading skeleton, fenced blocks (language and size), tables
      and resolved links per pair, for the root documents, `docs/`, the guide and the pack; `make
      check`, the gates workflow and `backend/tests/test_docs_parity.py` prove both directions (missing)
- [X] T036 Bring every Spanish document to parity and create the missing ones: `docs/es/{INSTALL,
      THEMES,DESIGN-SYSTEM}.md`, the rewritten `docs/es/{AUTHORING,IMPORT,REPORTS}.md`, and
      `{CONTRIBUTING,SECURITY,CODE_OF_CONDUCT,DIAGNOSIS}.es.md` (partial)
- [X] T037 Language switch line in every paired document; remove `docs/VIBE-REPORTING.md` and repoint
      its inbound links (partial)
- [X] T038 Record the rule in `specs/046-release-docs-governance/spec.md` (FR-020, FR-021) and in
      `CONTRIBUTING.md`; CHANGELOG under Unreleased (missing)

## Dependencies

T032 → T033/T034 → T035 → T036/T037 → T038.
