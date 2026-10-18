# Implementation Plan: Pedidos por día

**Spec**: [spec.md](./spec.md) | **Date**: 2026-10-08

## Summary

Creamos el reporte `pedidos-dia` con materialize: daily y solo métricas sum/count/avg.

## Artifacts

| File | Purpose |
|---|---|
| `reports/pedidos-dia/report.yaml` | Contrato del reporte. |

## Mapping from spec to artifact

- `Metrics` → `metrics`
- `Dimensions and filters` → `dimensions`, `filters`
- `materialize: daily` → `materialize: daily`

## Rules (checked by `bizview validate`)

- materialize: daily solo con métricas sum, count, avg, min o max.
- views, periods, compare y access deben ser válidos para el esquema.

## Verification

- `bizview validate --write-lock` passes.
