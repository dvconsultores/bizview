# Implementation plan: [TÍTULO]

**Spec**: [spec.md](./spec.md)

## Summary

[One paragraph: what the artifact does and which spec sections it implements.]

## Artifacts

| Path (relative to project) | Purpose | Schema |
|---|---|---|
| `integrations/<id>/integration.yaml` | datasets, schedule, checks | `.bizview/schemas/integration.schema.json` |
| `integrations/<id>/queries/<dataset>.sql` | one read-only SELECT per dataset using `:window_start` / `:window_end` | — |
| `integrations/<id>/requests/<request>.yaml` | declarative request definitions (API-origin integrations) | `.bizview/schemas/request.schema.json` |
| `reports/<id>/report.yaml` | uses, metrics, dimensions, views | `.bizview/schemas/report.schema.json` |
| `distributions/<id>.yaml` | scheduled sends of one report, recipients by role only | `.bizview/schemas/distribution.schema.json` |

> **Note**: `<id>` = the spec folder's short name without the number, e.g. spec `specs/003-ventas-mensuales/` → report id `ventas-mensuales`. Integration/report/distribution ids must be unique across the whole workspace.

## Mapping from spec to artifact

- Each dataset in the spec becomes a SQL file in `integrations/<id>/queries/` + an entry in `integration.yaml`.
- Each metric / dimension / view in the spec becomes the matching declaration in `reports/<id>/report.yaml`.
- Each schedule row in a distribution spec becomes an entry in `distributions/<id>.yaml` with recipients by role only.

## Rules

- SQL: one read-only SELECT (or WITH) per dataset file; never INSERT/UPDATE/DELETE.
- Reports reference only declared datasets and columns from their own spec.
- No credentials, row values, or secrets in any artifact file.
- A `fuente` spec documents a source but produces no artifact files.

## Verification

- `bizview validate --write-lock` passes with no errors.
- Figures are checked against the origin: [how, e.g. totals equal origin totals for last month to the cent].
