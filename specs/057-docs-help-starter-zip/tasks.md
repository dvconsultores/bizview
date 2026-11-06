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
