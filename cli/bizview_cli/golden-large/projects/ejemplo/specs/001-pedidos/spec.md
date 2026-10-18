# Pedidos de venta

**Tipo**: integracion
**Status**: Approved

**Created**: 2026-10-08

**Input**: "Cargar pedidos de venta con moneda normalizada, impuesto no nulo, fecha local y monto total calculado."

## Purpose *(mandatory)*

El equipo de finanzas consulta pedidos diarios con métricas de volumen y ticket
promedio, por moneda, sin corregir impuestos o monedas en el reporte.

## Clarifications

- Q: ¿La base origen ya da monto total? → A: No; se calcula monto_neto más impuesto en el transform.
- Q: ¿Los pedidos pueden tener impuesto nulo? → A: Sí; se normaliza a cero.
- Q: ¿Qué columna se usa para el día? → A: creado_en convertido a la fecha local de la integración.

---

## Integration *(only for Spec type: integration)*

**Data source**: origen_ventas

**Schedule**: cada hora (0 * * * *); reconstrucción completa los domingos a las 03:00
(hora de la instalación)

**Time zone for business dates**: America/Caracas

### Datasets

#### pedidos

- **What one row is**: un pedido de venta leído de la fuente.
- **Included / excluded**: incluye pedidos de cualquier moneda; excluye líneas de producto.
- **Primary key**: numero
- **Date column**: fecha
- **Incremental window**: releer los últimos 3 días en cada ejecución
- **Transform input columns** (la consulta devuelve exactamente estas):

| Column | Type | Nullable |
|---|---|---|
| numero | text | no |
| creado_en | timestamptz | sí |
| cliente_id | text | sí |
| moneda | text | sí |
| monto_neto | numeric | sí |
| impuesto | numeric | sí |

- **Transform output columns**:

| Column | Type | Nullable | Meaning / origin |
|---|---|---|---|
| numero | text | no | Número de pedido (único). |
| fecha | date | no | Fecha local derivada de creado_en. |
| creado_en | timestamptz | sí | Fecha y hora original. |
| cliente_id | text | sí | Identificador del cliente. |
| moneda | text | sí | Código de moneda en mayúsculas y sin espacios. |
| monto_neto | numeric | sí | Monto antes de impuesto. |
| impuesto | numeric | no | Impuesto; cero cuando la fuente no lo trae. |
| monto_total | numeric | sí | monto_neto más impuesto. |

- **Transform SQL**:

```sql
SELECT
  numero,
  CAST(strftime(creado_en, '%Y-%m-%d') AS DATE) AS fecha,
  creado_en,
  cliente_id,
  upper(trim(moneda)) AS moneda,
  monto_neto,
  coalesce(impuesto, 0) AS impuesto,
  monto_neto + coalesce(impuesto, 0) AS monto_total
FROM input
```

- **Why transform**: la consulta de origen no puede entregar la forma final:
  limpieza de moneda, impuesto nulo normalizado a cero y fecha local.
- **Mode**: rows (no hay GROUP BY, DISTINCT, ventanas, ORDER BY ni agregados).
- **Quality checks**: row_count con mínimo 0; not_null en numero, fecha e impuesto.

### Origin notes

Se lee la tabla de solo lectura `ventas.pedidos` con un SELECT que filtra por
`p.creado_en` usando `:window_start` y `:window_end`, devolviendo exactamente
las columnas de `transform.input`.

---

## Acceptance scenarios *(mandatory)*

1. **Given** pedidos dentro de la ventana, **When** se ejecuta la carga,
   **Then** el dataset contiene una fila por pedido con moneda normalizada y impuesto no nulo.

## Success criteria *(mandatory)*

- **SC-001**: la integración valida sin errores con `bizview validate`.
- **SC-002**: la clave primaria no tiene duplicados.

## Assumptions

- La fuente `origen_ventas` está registrada en la instalación.
