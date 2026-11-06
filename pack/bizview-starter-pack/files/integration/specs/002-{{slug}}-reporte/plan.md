# Plan: {{name}} — report / reporte

**Spec**: [spec.md](./spec.md)

## What will be built

- One report over the integration's dataset: metrics, dimensions, periods, filters and a layout for
  web and PDF.

## Files

| File | Purpose |
|---|---|
| `reports/{{slug}}/report.yaml` | what the reader sees |

## Constitution check

- Every column read is declared by the dataset.
- The report declares at least one filter and its personal-data decision.
