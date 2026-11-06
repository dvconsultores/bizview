# Prompt — 057-docs-help-starter-zip: help and README that match the product, and a ready-to-use starter zip

Paste everything below the line into the coding agent with the repository open.

---

You are working on the BizView repository (0.2.x). Read `.specify/memory/constitution.md`,
`specs/043-bizview-refactor-external-authoring/spec.md`, `specs/045-remove-authoring-agent/spec.md`,
`specs/046-release-docs-governance/spec.md`, `specs/052-source-structure-chat/spec.md`,
`backend/app/guide/README.md`, `backend/app/guide/index.yaml`, `docs/AUTHORING.md`,
`docs/IMPORT.md` and `pack/bizview-starter-pack/`. Implement **057-docs-help-starter-zip** as
`/speckit-specify` (from this text) → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.
Do not ask me questions.

## Why

Since 043/045 a project is authored **outside** Bizview with whatever AI the user prefers (ChatGPT,
Claude, DeepSeek, Gemini, Copilot…) or by hand, then imported. The in-app help, the README and
parts of `docs/` still describe the removed chat agent and "vibe reporting", and the only way to
get the authoring pack is `bizview init workspace` on a machine with the CLI. A non-technical
admin must be able to click **Descargar paquete inicial**, hand the zip to their AI with one
sentence, and import the result.

## Part 1 — Starter zip, downloadable from the app

1. **Proyectos → Nuevo proyecto → Descargar paquete inicial** (also on the empty state of Proyectos
   and in Ayuda → "Crear un proyecto con tu IA"). A dialog with:
   - **Nombre del proyecto** (→ `project.yaml.name` and slug),
   - **Fuente** (optional select of registered sources): when chosen, the zip includes that source's
     structure pack (`sources/<nombre>/structure.md` + `structure.json`, from 048/052 — generated on
     the fly if none is stored; credentials, hosts and row values never included),
   - **Idioma** of the pack text (es/en, default the viewer's),
   - **Tipo** of first spec: integración + reporte (default) or reporte directo.
   The download is `bizview-starter-<slug>.zip`, built server-side from `pack/bizview-starter-pack/`
   plus the selections; budget-checked against 049 before it is served.
2. Zip content (the pack of 043, slimmed — no example project inside, it is a template):
   ```
   PROMPT.md            ← paste-into-any-AI prompt: rules, file contract, the 9 checks, "return one zip"
   REQUEST.md           ← template the user fills: what, for whom, filters, period, visual style
   project.yaml         ← name/slug/locale filled from the dialog
   specs/001-<slug>/{spec.md,plan.md,tasks.md}   ← skeletons with the required headings and [ ] tasks
   integrations/<slug>/integration.yaml          ← skeleton with every key commented (omitted for direct reports)
   integrations/<slug>/queries/example.sql       ← ":window_start / :window_end" example
   reports/<slug>/report.yaml                    ← skeleton: metrics, dimensions, periods, views, filters, pdf, layout
   sources/<nombre>/structure.{md,json}          ← when a source was selected
   .bizview/schemas/*.json, .bizview/preset.yaml ← what the validator checks
   CLAUDE.md, AGENTS.md                          ← same text as PROMPT.md for agentic tools
   README.md                                     ← 10 lines: "1 fill REQUEST.md · 2 give the folder to your AI
                                                    (or paste PROMPT.md + REQUEST.md + structure.md) · 3 import the zip it returns"
   ```
3. `PROMPT.md` must work when **pasted into a chat** (not only given as a folder): it is
   self-contained, under 1,500 words, states that the answer is **one zip with the project files at
   the root**, that specs need `spec.md` + `plan.md` + `tasks.md` with every task `[X]`, the schema
   rules (`CAST(strftime(col, '%Y-%m-%d') AS DATE)` for dates in transforms, singular
   `dimension`/`metric` in ranking views, `x`/`series` in bar components, personal-data
   declaration, `comprobante_id`-style names instead of `document_id`…), and the import budgets.
   Keep it in sync with the validator: a unit test renders the pack with every example and runs
   `bizview validate` on it with zero errors.
4. The same zip is what `bizview init workspace` writes (one source of truth:
   `pack/bizview-starter-pack/`), and the CLI gains `bizview init project <name> [--source <s>]`.

5. **General template at the repository root.** Besides the per-project download, publish a generic
   `bizview-starter-template.zip` (no name, no source, placeholders `<slug>` / `<nombre>`) that:
   - is built by `make starter-template` from `pack/bizview-starter-pack/` and committed at the
     repository root and attached to every GitHub release (046 governance),
   - is served by the app at `GET /api/projects/starter-template` and linked from the Proyectos empty
     state as **Descargar plantilla general** next to **Descargar paquete inicial**,
   - is linked from `README.md` (top of "How it works") and `docs/AUTHORING.md`.
   A test asserts the committed zip equals the rendered one (CI fails when the pack changes and
   the zip was not regenerated).

6. **`CONTENIDO.md` / `CONTENTS.md` inside every zip** (both languages always shipped), a detailed,
   file-by-file explanation a non-technical reader can follow. For each file: what it is, who
   writes it (you / your AI / Bizview), whether it is required, what Bizview does with it on
   import, and one short example. Minimum coverage:

   | File | Required | Written by | What Bizview does with it |
   |---|---|---|---|
   | `project.yaml` | yes | you (dialog fills it) | name, slug, locale of the project; slug decides collisions |
   | `REQUEST.md` | for your AI | you | never imported; it is the brief your AI reads |
   | `PROMPT.md`, `CLAUDE.md`, `AGENTS.md` | for your AI | Bizview | rules for the AI; ignored on import |
   | `specs/NNN-slug/spec.md` | yes | your AI | purpose, clarifications, datasets or metrics, acceptance; shown in the editor; `**Datos personales**` is enforced |
   | `specs/NNN-slug/plan.md`, `tasks.md` | yes | your AI | artefacts list and `[X]` tasks; `spec_incomplete` when missing |
   | `integrations/<id>/integration.yaml` | for integración | your AI | datasets, schedule, keys, incremental window, checks; becomes a worker schedule on apply |
   | `integrations/<id>/queries/*.sql` or `requests/*.yaml` | with it | your AI | read-only extraction; validated statically; run by the worker |
   | `reports/<id>/report.yaml` | yes | your AI | metrics, dimensions, views, periods, filters, layout web/PDF; becomes a dashboard on apply |
   | `assets/**` | optional | you | images for `asset` tiles and KPI icons; budget 049 |
   | `sources/<nombre>/structure.{md,json}` | for your AI | Bizview | the source's structure; never imported |
   | `.bizview/schemas/*.json`, `.bizview/preset.yaml` | for your AI | Bizview | what the validator checks; never imported |
   | `bizview.lock` | optional | CLI | hash of a validated tree; informative |

   Also explain in that file the naming rules (`NNN-slug` folders, ids in kebab-case, one report
   id = one dashboard URL `/r/<id>`), what the import ignores, and the budgets.

7. **`QUE-HACE-BIZVIEW.md` / `WHAT-BIZVIEW-DOES.md` inside every zip** (and the same text as help
   topic `importar-y-aplicar` and in `docs/IMPORT.md`): a step-by-step, plain-language account of
   **import** and **apply**, so the author knows what to expect:

   *Import* — 1 the zip is read in memory, the top folder stripped, executables and scripts in SVG
   rejected; 2 files are mapped to the layout, unknown ones listed as `ignored`; 3 budgets checked
   (artifacts 400 files / 20 MB, assets 2000 / 25 MB); 4 slug collision → re-import as a new
   revision (055) or `-2` copy on request; 5 the whole tree is validated with the same validator
   as the CLI (schemas, SQL statically, references between files, personal data vs spec, spec
   completeness) and problems are shown per file with a fix; 6 the project is saved as a
   **draft**: nothing runs, nothing is visible to users yet.

   *Apply* — 1 the draft is composed with the other applied projects into a new installation
   **version** and checked again (duplicate ids across projects are real errors); 2 each
   integration is registered with the worker: the first run is a full load, then the schedule
   (`cron`) runs the incremental window (`:window_start`/`:window_end`) or a full reload per
   `incremental.mode`; 3 datasets land in the warehouse schema `ds_<integration>.<dataset>` with
   `_run_id` and `_loaded_at`; 4 each report becomes a dashboard at `/r/<id>`, visible to the
   roles in `access`, with filters, periods, comparison, PDF/CSV and share links; 5 the apply is
   an audit event and **Volver a la versión anterior** rolls everything back; 6 what to look at
   first: Integraciones → last run, Tableros → the new dashboard, Proyectos → Problemas.

8. **Bilingual everywhere.** Every text shipped in the zip (`README.md`, `CONTENIDO.md`,
   `QUE-HACE-BIZVIEW.md`, comments in the YAML skeletons, `PROMPT.md`) exists in Spanish and in
   English: the dialog's language picks which one is the primary file and the other is shipped
   with the `.en.md` / `.es.md` suffix; the general template at the root ships both. Help topics,
   README and docs sections from Parts 2 and 3 are written in both languages (`backend/app/guide/es`
   and `/en`; `docs/*.md` in English with `docs/es/*.md` mirrors for AUTHORING, IMPORT and REPORTS).

## Part 2 — In-app help (backend/app/guide, ES + EN)

- Remove the section **Agente y Spec Kit** and every topic that explains the chat agent. Replace with
  section **Crear con tu IA** (`crear-con-ia`), topics:
  `paquete-inicial` (what the zip is, how to download it), `escribir-la-peticion` (REQUEST.md),
  `pasarlo-a-tu-ia` (how to use it with ChatGPT, Claude, DeepSeek, Gemini or by hand; what to
  paste; what to ask back), `validar-antes-de-importar` (CLI optional; the import validates
  anyway), `corregir-problemas` (reading problems and fixes), `reimportar-cambios` (055 when
  present; until then: delete and import), `ejemplo-completo` (the Ventas por marca walkthrough:
  request → zip → import → apply → share).
- Rewrite **Primeros pasos** as the five steps: source → structure → starter zip → your AI →
  import. Update `importar-un-proyecto`, `generar-estructura-con-ia`, `estructura-de-un-proyecto`,
  `definir-una-integracion`, `definir-un-reporte`, `tipos-de-spec`, `proyectos-en-vs-code` and
  `ia` so they describe what the product does today (no chat; AI is optional and private — 052;
  images and visual components — 044; themes — 047/051; limits — 049; parameters sheet — 053;
  Google sign-in — 054).
- Every topic ends with **Relacionados** and, where a screen exists, an app link
  (`app://proyectos`, `app://fuentes`), as the guide README prescribes. Grep gate: the words
  "agente", "chat de autoría", "vibe" do not appear in `backend/app/guide/**`.

## Part 3 — README and docs

- `README.md`: "How it works" becomes the five steps above with **Descargar paquete inicial** as
  step 3 (CLI as the alternative); "What it does" table gains rows for 047, 048, 049, 050–054 (and
  055/056 when merged) and drops nothing that still exists; a "Author with your own AI" paragraph
  listing what the pack contains and that no AI key is needed in Bizview.
- `docs/AUTHORING.md`: starter zip section first, pack layout as in Part 1, the paste-into-chat
  flow, and the "9 checks" list; keep the complete worked example.
- `docs/VIBE-REPORTING.md`: rename to `docs/REPORTS.md` (keep a one-line stub with the new name),
  remove chat-era text.
- `docs/IMPORT.md`: link the starter zip; collision table per 055 when merged.
- CHANGELOG under Unreleased.

## Tests

- Download dialog produces a zip that `bizview validate` accepts with 0 errors for each
  combination (with/without source, integración+reporte / directo, es/en); budget respected.
- Every zip (per-project and general template) contains `CONTENIDO.md`+`CONTENTS.md` and
  `QUE-HACE-BIZVIEW.md`+`WHAT-BIZVIEW-DOES.md`; the contents table lists every file actually in the
  zip (test walks the zip and checks each path is documented).
- Committed `bizview-starter-template.zip` equals the rendered one; `GET /api/projects/starter-template`
  serves it with the right content type and size.
- Help topic `importar-y-aplicar` exists in es/en and matches the text shipped in the zip (single
  source rendered to both places).
- Pack rendered from `pack/bizview-starter-pack/` equals what `bizview init project` writes.
- Guide index has no `agente` section; new topics load in both languages; links resolve; search
  finds "paquete inicial".
- README/docs grep gate for the removed terms; markdown lint passes.
- e2e: Proyectos empty state → Descargar paquete inicial → zip → import that zip untouched →
  validation shows only the expected "fill me" problems (skeleton placeholders), never a schema error.

## Deliverables

Backend (starter endpoint `GET /api/projects/starter?name=&source=&lang=&kind=`,
`GET /api/projects/starter-template`, pack builder, tests), frontend (dialog, empty state with both
downloads, help link), CLI (`init project`), `make starter-template` + committed
`bizview-starter-template.zip` at the repository root and attached to releases, `backend/app/guide`
(ES/EN topics and index, new `importar-y-aplicar`), `pack/bizview-starter-pack/` refresh with
`CONTENIDO.md`/`CONTENTS.md` and `QUE-HACE-BIZVIEW.md`/`WHAT-BIZVIEW-DOES.md`, `README.md`,
`docs/*` with `docs/es/` mirrors, `es.ts`/`en.ts`, CHANGELOG. Constitution: no change (VIII — AI optional and external; IX —
spec-driven; II — nothing from the source but structure leaves the installation).
