# Ventas directo

**Tipo**: reporte
**Status**: Approved

**Created**: 2026-10-01

**Input**: "Reporte directo de ventas consolidadas con KPI, tendencia, ranking y detalle."

## Purpose *(mandatory)*

El equipo comercial usa este reporte para monitorear las ventas consolidadas que ya
prepara el proceso nocturno del ERP: total, unidades, ranking por producto y detalle
por sucursal y producto.

## Clarifications

- Q: ¿Los datos ya están preparados por otro proceso? → A: Sí, el proceso nocturno
  del ERP consolida las ventas en `public.bi_ventas`; la columna `fecha` está indexada.
- Q: ¿Cómo se calcula el ticket promedio? → A: Total vendido dividido por las unidades.

---

## Report *(only for Spec type: report)*

**Modo**: directo

**Fuente**: bi

**Tablas**: `public.bi_ventas` (alias `v`)

**Mantenido por**: el proceso nocturno del ERP que consolida las ventas

**Volumen esperado**: ~1 M filas; crece ~30 mil filas por mes

**Audience / access**: Comercial y finanzas; admin y user solo lectura.

### Metrics

| Id | Label | Definition (exact) | Format | Better |
|---|---|---|---|---|
| total_vendido | Total vendido | `sum(v.monto)` | currency | higher |
| unidades_vendidas | Unidades vendidas | `sum(v.unidades)` | integer | higher |
| ticket_promedio | Ticket promedio | `total_vendido / unidades_vendidas` | currency | higher |

### Dimensions and filters

| Id | Label | Definition |
|---|---|---|
| sucursal | Sucursal | `v.sucursal` |
| producto | Producto | `v.producto` |

### Views

- KPI cards: total_vendido, unidades_vendidas y ticket_promedio.
- Trend: total_vendido por día.
- Rankings / tables: ventas por producto y detalle por sucursal y producto.

**Periods**: mtd por defecto · **Comparison**: previous_period por defecto

**PDF export**: sí, vertical, con las 4 vistas en orden

**AI narrative** *(optional)*: no

---

## Acceptance scenarios *(mandatory)*

1. **Given** ventas consolidadas del mes en curso, **When** se abre el reporte,
   **Then** las KPI muestran total, unidades y ticket promedio.
2. **Given** el reporte directo, **When** se ejecuta `bizview validate`, **Then** no
   hay errores.
3. **Given** la columna `fecha` indexada, **When** se consulta la tendencia, **Then**
   responde dentro del timeout configurado.

## Success criteria *(mandatory)*

- **SC-001**: el reporte valida sin errores con `bizview validate`.
- **SC-002**: el reporte usa modo directo con origen `bi` y cumple las cinco líneas
  obligatorias del spec.
- **SC-003**: los datos son de solo lectura y no exponen credenciales.

## Assumptions

- La tabla `public.bi_ventas` ya existe en la base BI y la mantiene el proceso
  nocturno del ERP.
- La columna `fecha` tiene un índice que la usa como columna principal.
