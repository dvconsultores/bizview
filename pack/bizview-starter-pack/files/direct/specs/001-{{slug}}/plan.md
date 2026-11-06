# Plan: {{name}} — direct report / reporte directo

**Spec**: [spec.md](./spec.md)

## What will be built

- One report that reads a table another process already prepares, with no integration of our own.
- Metrics, dimensions, periods, filters and a layout for web and PDF.

## Files

| File | Purpose |
|---|---|
| `reports/{{slug}}/report.yaml` | what the reader sees, and the tables it reads |

## Constitution check

- Read-only against the source; the declaration in `direct:` is the whole truth of what is read.
- The report declares at least one filter and its personal-data decision.
- Nothing runs before the project is applied.
