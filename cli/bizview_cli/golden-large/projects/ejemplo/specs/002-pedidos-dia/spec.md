# Pedidos por día

**Tipo**: reporte
**Status**: Approved

**Created**: 2026-10-08

**Input**: "Mostrar pedidos por día y por moneda, con total, conteo y ticket promedio."

## Purpose *(mandatory)*

El equipo de finanzas consulta el volumen diario de pedidos y el ticket promedio por
moneda. **Volumen esperado**: unos 20 millones de filas en pedidos (3 años); por eso usa
materialize: daily.

## Clarifications

- Q: ¿Se admiten métricas sum, count, avg, min o max? → A: Sí; el rollup diario solo soporta esas.
- Q: ¿El reporte usa transform? → A: No; consume el dataset transformado pedidos.

---

## Report *(only for Spec type: report)*

**Uses**: `p → pedidos.pedidos`

**Audience / access**: Comercial y finanzas; admin y user solo lectura.

### Metrics

| Id | Label | Definition (exact) | Format | Better |
|---|---|---|---|---|
| total_pedidos | Total pedidos | `sum(p.monto_total)` | currency | higher |
| pedidos | Pedidos | `count(p.numero)` | integer | higher |
| ticket_promedio | Ticket promedio | `total_pedidos / pedidos` | currency | higher |
| impuesto_promedio | Impuesto promedio | `avg(p.impuesto)` | currency | higher |

### Dimensions and filters

| Id | Label | Definition |
|---|---|---|
| moneda | Moneda | `p.moneda` |

### Views

- KPI cards: total_pedidos, pedidos, ticket_promedio
- Trend: total_pedidos por día
- Rankings / tables: por moneda, con pedidos, total_pedidos e impuesto_promedio

**Periods**: last_7_days por defecto · **Comparison**: previous_period por defecto

**PDF export**: no

**AI narrative** *(optional)*: no

---

## Acceptance scenarios *(mandatory)*

1. **Given** pedidos publicados, **When** se abre el reporte,
   **Then** se ven totales diarios por moneda con ticket promedio.

## Success criteria *(mandatory)*

- **SC-001**: el reporte valida sin errores con `bizview validate`.

## Assumptions

- El dataset `pedidos` está publicado con la fecha local `fecha`.
