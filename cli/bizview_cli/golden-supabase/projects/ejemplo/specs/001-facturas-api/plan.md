# Implementation Plan: Facturas de venta (Supabase)

**Spec**: [spec.md](./spec.md) | **Date**: 2026-10-01

## Summary

Creamos la integración `facturas-api` sobre la fuente `origen_supabase`. Consume la
tabla `facturas` por la API REST de Supabase (PostgREST). La carga es incremental por
hora con ventana de 7 días y reconstrucción completa los domingos a las 03:00.

## Artifacts

| File | Purpose |
|---|---|
| `integrations/facturas-api/integration.yaml` | Contrato de la integración y del dataset. |
| `integrations/facturas-api/requests/facturas.yaml` | Petición GET con paginación y filtro incremental. |

## Mapping from spec to artifact

- `Datasets.facturas` → `datasets.facturas`
- `Primary key: numero` → `datasets.facturas.primary_key`
- `Date column: fecha_emision` → `datasets.facturas.date_column`
- `Incremental window: 7 días` → `datasets.facturas.incremental.window_days`
- Columnas del spec → `datasets.facturas.columns.<columna>` y `requests.facturas.fields`
- `Quality checks` → `datasets.facturas.checks`

## Rules (checked by `bizview validate`)

- La petición es GET con path relativo a la fuente (tabla o vista), sin URL absoluta.
- fields mapea cada columna declarada a una ruta JSON.
- Sin credenciales (la clave vive en la fuente de la instalación), sin valores de
  filas.

## Verification

- `bizview validate --write-lock` passes.
- Comparar el total de `monto_total` recuperado contra el total de la tabla `facturas`
  en Supabase para la ventana, abriendo la API con las mismas fechas.
- Confirmar que no aparece ninguna clave de API ni secreto en los archivos del
  workspace.
