# Implementation Plan: Ventas directo

**Spec**: [spec.md](./spec.md) | **Date**: 2026-10-01

## Summary

Creamos el reporte `ventas-directo` en modo directo sobre la tabla
`public.bi_ventas` de la base BI, con alias `v`. Incluye cuatro vistas (KPI,
tendencia, ranking y tabla), filtros por sucursal y producto, comparación con el
período anterior y exportación PDF vertical.

## Artifacts

| File | Purpose |
|---|---|
| `reports/ventas-directo/report.yaml` | Contrato del reporte directo, métricas y vistas. |

## Mapping from spec to artifact

- `Modo: directo` → bloque `direct` en `report.yaml`
- `Fuente` → `direct.source: bi`
- `Tablas` → `direct.tables.v`
- `Metrics` → `metrics`
- `Dimensions and filters` → `dimensions` y `filters`
- `Views` → `views[0..3]`
- `Periods / Comparison` → `periods` y `compare`
- `PDF export` → `pdf`

## Rules (checked by `bizview validate`)

- El reporte usa exactamente uno de `uses` o `direct`; aquí usa `direct`.
- Las métricas y dimensiones usan solo `v.<columna>` de la tabla directa.
- `ticket_promedio` es una fórmula sobre métricas con sql.
- `date` es `v.fecha`, de tipo date.
- Sin credenciales ni valores de filas.

## Verification

- `bizview validate --write-lock` passes.
- Exportar el PDF y comprobar que incluye KPI, tendencia, ranking y tabla en el orden
  declarado.
- Confirmar que la instalación tiene DIRECT_REPORTS_BI activo y que
  `public.bi_ventas` tiene un índice por `fecha`.
