# Implementation Plan: Facturas de venta

**Spec**: [spec.md](./spec.md) | **Date**: 2026-10-01

## Summary

Creamos la integración `facturas` sobre la fuente `origen_ventas`. Expone un dataset
con encabezado, montos y estado de factura. La carga es incremental por hora con
ventana de 7 días y reconstrucción completa los domingos a las 03:00.

## Artifacts

| File | Purpose |
|---|---|
| `integrations/facturas/integration.yaml` | Contrato de la integración y del dataset. |
| `integrations/facturas/queries/facturas.sql` | SELECT incremental de solo lectura. |

## Mapping from spec to artifact

- `Datasets.facturas` → `datasets.facturas`
- `Primary key: numero` → `datasets.facturas.primary_key`
- `Date column: fecha_emision` → `datasets.facturas.date_column`
- `Incremental window: 7 días` → `datasets.facturas.incremental.window_days`
- Columnas del spec → `datasets.facturas.columns.<columna>`
- `Quality checks` → `datasets.facturas.checks`

## Rules (checked by `bizview validate`)

- SQL: un solo SELECT/WITH de solo lectura, sin escrituras ni funciones de
  administración; solo :window_start/:window_end.
- El dataset declara exactamente las columnas que devuelve la consulta; primary_key,
  date_column y checks solo usan columnas declaradas.
- Sin credenciales, sin valores de filas, sin secretos en ningún archivo.

## Verification

- `bizview validate --write-lock` passes.
- Sumar `monto_total` desde el dataset y compararlo contra el total de facturas de la
  ventana en `ventas.facturas`, permitiendo diferencias explicables por conversión de
  precisión.
