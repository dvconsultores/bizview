# Research — 057 helper pack, template and serving

## R1 — Where the pack lives and how the installed CLI finds it

**Decision**: the canonical pack is `pack/bizview-starter-pack/` at the repository root. The CLI
resolves it in this order: `BIZVIEW_STARTER_PACK` (a path), the packaged copy
`bizview_cli/starter_pack` (shipped in the wheel), then a walk up from `bizview_cli/__init__.py`
looking for `pack/bizview-starter-pack`.

**Rationale**: the repository must have one visible folder an author can edit, and an installed CLI
must work without a checkout. `hatch`'s `force-include` copies the root folder into the wheel at
build time, so both readers see the same bytes.

**Alternatives considered**: (a) keep the templates inside `bizview_cli/workspace_template/` — the
prompt's deliverable says `pack/`, and a folder named "workspace template" would hold a project
template; (b) download the pack from GitHub at runtime — the product must work offline.

## R2 — How the rendered zip stays identical between builds

**Decision**: `zipfile.ZipInfo` with a fixed timestamp (`1980-01-01 00:00:00`), sorted entry names
and `ZIP_DEFLATED`. One function returns the bytes for both the server and `make starter-template`.

**Rationale**: the test that compares the committed template with the rendered one is only meaningful
if the bytes are reproducible; a timestamp and a set iteration would make it flaky.

## R3 — Layout of the rendered skeleton, and how it validates

**Decision**: the zip root is the project root (`project.yaml`, `specs/`, `integrations/`,
`reports/`). To validate, the pack is written as a v2 workspace — `bizview.yaml` plus
`projects/<slug>/…` — because the validator's v1 layout requires `specs/integrations/…`.

**Rationale**: the import contract wants the project files at the root, and the validator wants
`spec: specs/001-…` to resolve inside a project folder. Writing the two layouts from one render is a
function call, not a second pack.

**Alternatives considered**: adding `bizview.yaml` to the zip and validating it as v1 — the v1 `spec:`
convention (`specs/integrations/<name>`) contradicts the v2 numbering the product uses.

## R4 — The skeleton must validate with zero errors

**Decision**: the skeleton is a valid, minimal project with a fictional dataset and placeholder
prose (marked `REEMPLAZA …` / `REPLACE …`), not a broken one. Every required key is present, the
spec is `Approved`, every task is `[X]`.

**Rationale**: an author who starts from a tree that already fails cannot tell their mistakes from
ours. The "fill me" markers are the readiness problems the UI shows, never schema errors.

## R5 — Source structure on the fly

**Decision**: when the dialog names a source, the endpoint calls `sources.structure.build` (the
generator of 048/052) and renders `structure.md`/`structure.json` with `enriched_markdown`/
`enriched_json`. A failure (source unreachable) does not fail the download: the zip is served without
the structure and the response carries a header naming the reason.

**Rationale**: the structure is what the external AI reads instead of connecting (constitution VIII),
and it is the same document the source screen downloads.

## R6 — Serving the committed template

**Decision**: `GET /api/projects/starter-template` reads `bizview-starter-template.zip` from
`STARTER_TEMPLATE_PATH` when set, else from the repository root resolved from the backend package,
and renders it in memory when neither exists.

**Rationale**: a deployment built from the image has the file at the image root; a developer does not
need to run `make` before opening the page. The fallback keeps the button working and the CI test
still proves the committed file is current.

## R7 — Language selection

**Decision**: `CONTENIDO.md`+`CONTENTS.md` and `QUE-HACE-BIZVIEW.md`+`WHAT-BIZVIEW-DOES.md` always
ship, in their own language. The other documents ship in the chosen language under their canonical
name and in the other language with `.en.md`/`.es.md`. YAML comments carry both languages on
consecutive lines (`# ES:`/`# EN:`).

**Rationale**: two names for the same document are how the dialog can be bilingual without a folder
tree that confuses a chat-based AI.

## R8 — Guide structure for the new section

**Decision**: the `agente` section becomes `crear-con-ia`; `tipos-de-spec`, `definir-una-integracion`,
`definir-un-reporte`, `distribuciones`, `recorrido-integracion-a-distribucion` and
`recorrido-reporte-directo` move into it unchanged in id. New ids: `paquete-inicial`,
`escribir-la-peticion`, `pasarlo-a-tu-ia`, `validar-antes-de-importar`, `corregir-problemas`,
`reimportar-cambios`, `ejemplo-completo`, `importar-y-aplicar`. Every topic gains a
`## Relacionados`/`## Related` closing section rendered from its `related` metadata.

**Rationale**: ids survive, so links and searches keep working; a new heading is the guide loader's
only change.

**Alternatives considered**: a completely new id set — it would break every existing `related` entry
and the drift tests for no reader benefit.
