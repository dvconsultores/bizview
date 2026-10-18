# Facturas de venta

**Tipo**: integracion
**Status**: Approved

**Created**: 2026-10-01

**Input**: "Cargar facturas de venta con su estado, montos y fecha de emisión."

## Purpose *(mandatory)*

El equipo de finanzas lo usa para responder cuánto se factura por día, por estado y
por moneda, y para vigilar que las facturas críticas no tengan campos nulos.

## Clarifications

- Q: ¿Qué estados de factura se cargan? → A: Todos: emitida, pagada y anulada.
- Q: ¿Incluye líneas o productos? → A: No, solo totales por factura.

---

## Integration *(only for Spec type: integration)*

**Data source**: origen_ventas

**Schedule**: cada hora (0 * * * *); reconstrucción completa los domingos a las 03:00
(hora de la instalación)

**Time zone for business dates**: America/Caracas

### Datasets

#### facturas

- **What one row is**: una factura emitida (documento contable con totales).
- **Included / excluded**: incluye facturas en cualquier estado; excluye líneas de
  producto y notas de crédito.
- **Primary key**: numero
- **Date column**: fecha_emision
- **Incremental window**: releer los últimos 7 días en cada ejecución
- **Columns**:

| Column | Type | Nullable | Meaning / origin |
|---|---|---|---|
| numero | text | no | Número de factura (único). |
| fecha_emision | date | no | Fecha contable de emisión. |
| emitida_en | timestamptz | yes | Momento exacto en que se emitió. |
| cliente_id | text | yes | Identificador del cliente. |
| estado | text | no | emitida, pagada o anulada. |
| moneda | text | yes | Código de moneda (ej. USD). |
| monto_neto | numeric | yes | Monto sin impuesto. |
| impuesto | numeric | yes | Impuesto aplicado. |
| monto_total | numeric | no | Monto total de la factura. |

- **Quality checks**: row_count con mínimo 0; not_null en numero, fecha_emision,
  estado y monto_total.

### Origin notes

Se lee la tabla de solo lectura `ventas.facturas` con un SELECT que filtra por
`f.creada_en` usando `:window_start` y `:window_end`.

---

## Acceptance scenarios *(mandatory)*

1. **Given** facturas emitidas dentro de la ventana, **When** se ejecuta la carga,
   **Then** el dataset contiene una fila por factura con su número único.
2. **Given** cualquier fila cargada, **When** se revisa, **Then** numero,
   fecha_emision, estado y monto_total no son nulos.
3. **Given** una ejecución incremental, **When** se consulta el dataset, **Then** solo
   aparecen facturas emitidas entre :window_start y :window_end.

## Success criteria *(mandatory)*

- **SC-001**: la integración valida sin errores con `bizview validate`.
- **SC-002**: la clave primaria no tiene duplicados.
- **SC-003**: el dataset puede agruparse por fecha_emision y estado para sumar
  monto_total.

## Assumptions

- La fuente `origen_ventas` está registrada en la instalación.
- Los códigos de moneda y los estados usan los valores declarados.
- `cliente_id` no resuelve datos personales.
