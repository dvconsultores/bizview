# Facturación diaria

**Tipo**: reporte
**Status**: Approved

**Created**: 2026-10-01

**Input**: "Reporte de facturación diaria con totales, ranking por estado y detalle."

## Purpose *(mandatory)*

El equipo comercial lo usa para responder cuánto se factura por día, cómo evoluciona
el total, qué estados aportan más y qué composición tienen los montos por día.

## Clarifications

- Q: ¿Qué métrica se usa para el promedio? → A: Total facturado dividido por el número
  de facturas.
- Q: ¿La comparación es con el período anterior? → A: Sí, por defecto; también se
  puede comparar con el año anterior o desactivarla.

---

## Report *(only for Spec type: report)*

**Uses**: `f → facturas.facturas`

**Audience / access**: Comercial y finanzas; admin y user solo lectura.

### Metrics

| Id | Label | Definition (exact) | Format | Better |
|---|---|---|---|---|
| total_facturado | Total facturado | `sum(f.monto_total)` | currency | higher |
| facturas | Facturas | `count(distinct f.numero)` | integer | higher |
| ticket_promedio | Ticket promedio | `total_facturado / facturas` | currency | higher |
| impuesto | Impuesto | `sum(coalesce(f.impuesto, 0))` | currency | — |

### Dimensions and filters

| Id | Label | Definition |
|---|---|---|
| estado | Estado | `f.estado` |
| moneda | Moneda | `f.moneda` |

### Views

- KPI cards: total_facturado, facturas y ticket_promedio.
- Trend: total_facturado por día.
- Rankings / tables: facturación por estado y detalle por estado y moneda.

**Periods**: last_7_days por defecto · **Comparison**: previous_period por defecto

**PDF export**: sí, vertical, con las 4 vistas en orden

**AI narrative** *(optional)*: no

---

## Acceptance scenarios *(mandatory)*

1. **Given** facturas de los últimos 7 días, **When** se abre el reporte, **Then** las
   KPI muestran total, facturas y ticket promedio.
2. **Given** datos de varios estados, **When** se consulta la vista ranking, **Then**
   cada estado aparece una vez con su total facturado.
3. **Given** un período que incluye facturas anuladas, **When** se calcula el total,
   **Then** el total incluye todas las facturas; el usuario puede filtrar por estado.
4. **Given** el período seleccionado, **When** se exporta a PDF, **Then** el PDF
   contiene las 4 vistas en orden y en vertical.

## Success criteria *(mandatory)*

- **SC-001**: el reporte valida sin errores con `bizview validate`.
- **SC-002**: el ticket promedio es numéricamente correcto para cualquier filtro de
  estado o moneda.
- **SC-003**: el ranking muestra los 10 estados con mayor facturación.
- **SC-004**: el PDF incluye KPI, tendencia, ranking y tabla en el orden declarado.

## Assumptions

- Los montos comparados están en la misma moneda; el reporte no convierte divisas.
- El detalle por moneda y estado usa topes de 100 filas.
