# Inventory — statements that are no longer true

Produced before editing (T001), from `grep -inE 'asistente|assistant|speckit-|AI Powered|token
budget|run contract|presupuesto|chat'` over the corpus, plus a read of each document. Every row is
a statement 0.2.0 makes false; the task that fixes it is named.

| # | File:line | Statement today | Why it is false | Task |
|---|---|---|---|---|
| 1 | `README.md:1` | `# Bizview AI Powered` | the product is **Bizview**; the suffix belonged to the agent's positioning | T018, T007 |
| 2 | `README.es.md:1` | `# Bizview AI Powered` | same | T018, T008 |
| 3 | `CONTRIBUTING.md:1` | `# Contributing to Bizview AI Powered` | same | T016 |
| 4 | `CONTRIBUTING.md:19` | "(`/speckit-specify` → `/speckit-plan` → …)" | those are the repository's own Spec Kit skills, not the product's; as written it reads as an in-app workflow | T016 |
| 5 | `docs/INSTALL.md:1` | `# Installing Bizview AI Powered for a customer` | same as 1 | T013 |
| 6 | `docs/VIBE-REPORTING.md:370-386` | "No in-app assistant" section explaining the removed chat | true but redundant: it belongs in `docs/AUTHORING.md`'s introduction | T010, T012 |
| 7 | `backend/app/config.py:151` | `product_name: str = "Bizview AI Powered"` | the shipped default name | T018 |
| 8 | `frontend/src/config/BrandingContext.tsx:6` | `product_name: "Bizview AI Powered"` | same | T018 |
| 9 | `frontend/index.html:12` | `<title>Bizview AI Powered</title>` | same | T018 |
| 10 | `frontend/dist/index.html:12` | same (a build artefact, not tracked as source) | rebuilt by the release build | T018 |
| 11 | `cli/pyproject.toml:4` | `description = "Vibe reporting toolkit for Bizview AI Powered workspaces"` | same | T018 |
| 12 | `frontend/tests/e2e/flows.spec.ts:42` | `toHaveTitle(/Bizview AI Powered · Cliente Demo/)` | the title assertion follows the rename | T019 |
| 13 | `frontend/tests/unit/google-sign-in.test.tsx:30`, `no-literals.test.ts:17` | a `Bizview AI Powered` fixture and its "brand name" allowlist entry | follow the rename | T019 |
| 14 | `backend/tests/test_pdf_preview.py:95` | `product="Bizview AI Powered"` as an assertion fixture | follow the rename | T019 |
| 15 | `VERSION` = `0.1.0`; `backend/pyproject.toml` 0.1.0; `frontend/package.json` 0.1.0; `cli/pyproject.toml` 0.3.0; `cli/bizview_cli/__init__.py` 0.4.0 | four different numbers for one release | the release is 0.2.0 and there is one truth | T017 |
| 16 | `backend/app/guide/index.yaml:19-20` | section `agente` ("Agente y Spec Kit") | the in-app agent is gone; the section has no topics that earn it | T022 |
| 17 | `backend/app/guide/{es,en}/aplicar-proyecto.md`, `editor-de-proyecto.md`, `historial-de-proyecto.md`, `recorrido-*.md`, `definir-*.md`, `distribuciones.md`, `privacidad-y-ia.md`, `instalacion-y-ajustes.md`, `proyectos-en-vs-code.md` | authoring described as something the app does with you | authoring is outside the product; the CLI and the pack are the path | T022 |
| 18 | `docs/INSTALL.md` §7 "AI (optional)" | describes the provider as authoring AI | it is help-only since 045 | T013 |
| 19 | `SECURITY.md` "Built-in protections" | lists what the product protects but not the structure-pack boundary or the import validation | the release's security story is import + SSRF + no AI authoring | T014 |
| 20 | `.specify/memory/constitution.md` preamble and constraints | written for the product that authored in-app | 043/045 changed what the product is | T020 |
| 21 | `CHANGELOG.md` | has an `[Unreleased]` block and no 0.2.0 section | the release needs its own section, with every removal by spec number | T023 |

Gaps found while reading (not false statements, but missing):

- No document tells an author the eight steps in one place, and none carries a worked example
  (`docs/AUTHORING.md`, T010).
- No document explains the import path and its collision rules (`docs/IMPORT.md`, T011).
- `README.md` names no hosted product and no "connect my ERP" action (T007).
- Nothing checks that the READMEs stay in step, that the version copies agree, or that a link in
  the top-level documents resolves (T002–T004).
