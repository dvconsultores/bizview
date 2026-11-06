# Plan: {{name}}

**Spec**: [spec.md](./spec.md)

## What will be built

- One integration that reads the source and lands one dataset.
- One report over that dataset: metrics, dimensions, periods, filters and a layout for web and PDF.

## Files

| File | Purpose |
|---|---|
| `integrations/{{slug}}/integration.yaml` | what is read, when and how |
| `integrations/{{slug}}/queries/example.sql` | the read-only query |
| `reports/{{slug}}/report.yaml` | what the reader sees |
| `specs/001-{{slug}}/spec.md` | the decision this all implements |

## Constitution check

- Read-only against the source; no credential and no row value in the repository.
- The report declares its personal-data decision.
- Nothing runs before the project is applied.
