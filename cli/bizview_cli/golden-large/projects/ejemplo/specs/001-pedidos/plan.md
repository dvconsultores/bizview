# Implementation Plan: Pedidos de venta

**Spec**: [spec.md](./spec.md) | **Date**: 2026-10-08

## Summary

Creamos la integración `pedidos` sobre la fuente `origen_ventas`, con un dataset que
usa `transform` por filas para limpiar moneda, normalizar impuesto y calcular monto_total.

## Artifacts

| File | Purpose |
|---|---|
| `integrations/pedidos/integration.yaml` | Contrato de la integración, dataset y transform. |
| `integrations/pedidos/queries/pedidos.sql` | SELECT incremental de solo lectura. |

## Mapping from spec to artifact

- `Datasets.pedidos` → `datasets.pedidos`
- `Primary key: numero` → `datasets.pedidos.primary_key`
- `Transform input columns` → `datasets.pedidos.transform.input`
- `Transform output columns` → `datasets.pedidos.columns`

## Rules (checked by `bizview validate`)

- SQL de consulta: un solo SELECT/WITH de solo lectura, sin escrituras ni funciones de
  administración; solo :window_start/:window_end.
- transform: las columnas de `input` se leen desde la consulta; el SQL devuelve las
  columnas de salida; el modo es rows.

## Verification

- `bizview validate --write-lock` passes.
