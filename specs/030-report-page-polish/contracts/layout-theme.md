# Contract — `layout.theme` in the report definition

The per-report palette override (FR-008). It is a declarative field inside the existing `layout`
object of the report definition, so it travels with the workspace version, with the shared view and
with the PDF — and 026's "semantic roles only, never hex" rule is untouched.

## Shape

```yaml
layout:
  web:
    components: [ ... ]
  pdf:
    blocks: [ ... ]
  theme:
    palette: impacto        # optional; one of the five preset ids
```

- `layout.theme` is optional and accepts **only** `palette` (`additionalProperties: false`).
- `layout.theme.palette` is optional: absent means "use the installation's preset".
- No colour, font, size or URL may appear here — 026 FR-005 still holds, and the checker's `_LITERAL`
  guard keeps refusing hex anywhere in the layout.

## Schema and checker

| Artifact | Change |
|---|---|
| `cli/bizview_cli/schemas/report.schema.json` | add `theme` under `layout` (`additionalProperties: false`, `palette` enum of the five ids) + a `palette_id` `$def` |
| `cli/bizview_cli/report_layout.py` | validate `layout/theme/palette` with `_enum(...)`, so an unknown id yields a `layout_range` issue with the Spanish fix message used by every other enum field |
| `backend/app/engine/report.py` | unchanged — it already runs the checker and exposes `layout_problems` |
| `frontend/src/api/types.ts` | `layout?: { ...; theme?: { palette?: PaletteId } }` |

Error example (the CLI issue, not an API error):

```text
layout_range  reports/ventas.yml  layout/theme/palette
"palette 'neon' no es un valor admitido"
expected: ["impacto","clasico","monocromo","contraste","daltonico"]
```

## Consumers

| Consumer | Reads | Effect |
|---|---|---|
| Report page | `def.layout.theme.palette` | effective preset (see data-model §4) |
| Shared view | same (the shared payload returns the definition) | same |
| PDF (`pdf.render`, `pdf_layout`) | `definition["layout"]["theme"]["palette"]` | `light` variant of that preset |
| Apariencia admin | nothing | installation default only |

## Write path

The "Paleta" selector in the report's "Parámetros" sheet edits the definition and saves through the
existing report-definition update (new workspace version). "Usar la de la instalación" removes the
key. Restricted to the roles that can already edit the definition today — no new permission.
