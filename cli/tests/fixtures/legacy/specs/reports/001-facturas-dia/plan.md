# Implementation Plan: Facturación diaria

**Spec**: [spec.md](./spec.md) | **Date**: 2026-10-01

## Summary

Creamos el reporte `facturas-dia` sobre el alias `f` de `facturas.facturas`. Incluye
cuatro vistas (KPI, tendencia, ranking y tabla), filtros por estado y moneda,
comparación con el período anterior y exportación PDF vertical con las cuatro vistas.

## Artifacts

| File | Purpose |
|---|---|
| `reports/facturas-dia/report.yaml` | Contrato del reporte, métricas y vistas. |

## Mapping from spec to artifact

- `Metrics` → `metrics`
- `Dimensions and filters` → `dimensions` y `filters`
- `Views` → `views[0..3]`
- `Periods / Comparison` → `periods` y `compare`
- `PDF export` → `pdf`

## Rules (checked by `bizview validate`)

- Las métricas y dimensiones usan solo `f.<columna>` de conjuntos declarados en uses.
- `ticket_promedio` es una fórmula sobre métricas con sql.
- Sin credenciales ni valores de filas.

## Verification

- `bizview validate --write-lock` passes.
- Exportar el PDF y comprobar que incluye KPI, tendencia, ranking y tabla en el orden
  declarado.
- Comparar total_facturado contra el total facturado real del período y confirmar que
  coincide.
