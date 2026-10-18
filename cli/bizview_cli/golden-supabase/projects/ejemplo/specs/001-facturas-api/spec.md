# Facturas de venta (Supabase)

**Tipo**: integracion
**Status**: Approved

**Created**: 2026-10-01

**Input**: "Cargar facturas de venta desde la API REST de Supabase (PostgREST)."

## Purpose *(mandatory)*

El equipo de finanzas lo usa para responder cuánto se factura por día, por estado y
por moneda, consumiendo la tabla `facturas` expuesta por PostgREST en Supabase.

## Clarifications

- Q: ¿Qué estados de factura se cargan? → A: Todos: emitida, pagada y anulada.
- Q: ¿Cómo se pagina? → A: Por offset, de 1000 filas por página, ordenadas por número
  de factura.

---

## Integration *(only for Spec type: integration)*

**Data source**: origen_supabase

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
| emitida_en | timestamptz | no | Momento exacto en que se emitió. |
| cliente_id | text | yes | Identificador del cliente. |
| estado | text | no | emitida, pagada o anulada. |
| moneda | text | yes | Código de moneda (ej. USD). |
| monto_neto | numeric | yes | Monto sin impuesto. |
| impuesto | numeric | yes | Impuesto aplicado. |
| monto_total | numeric | no | Monto total de la factura. |

- **Quality checks**: row_count con mínimo 0; not_null en numero, fecha_emision,
  emitida_en, estado y monto_total.

### Origin notes

Se lee la vista/tabla `facturas` de Supabase a través de PostgREST. La petición es
GET con path relativo `facturas`, paginación por offset y filtro incremental en
`params.and` usando `emitida_en`. La clave de API vive en la fuente de la instalación;
nunca se escribe aquí. No se usa `reconcile` porque la fuente no es una base
PostgreSQL directa de Bizview.

---

## Acceptance scenarios *(mandatory)*

1. **Given** facturas accesibles por PostgREST, **When** se ejecuta la petición,
   **Then** el dataset recibe una fila por factura.
2. **Given** una carga incremental, **When** se evalúa `params.and`, **Then** solo se
   traen facturas con `emitida_en` entre :window_start y :window_end.
3. **Given** que hay más de 1000 filas, **When** se pagina por offset, **Then** se
   recuperan todas las páginas sin duplicados.
4. **Given** una fila cargada, **When** se revisa, **Then** numero, fecha_emision,
   emitida_en, estado y monto_total no son nulos.

## Success criteria *(mandatory)*

- **SC-001**: la integración valida sin errores con `bizview validate`.
- **SC-002**: `fields` mapea cada columna declarada a su ruta JSON.
- **SC-003**: el filtro incremental no trae filas fuera de la ventana.

## Assumptions

- La fuente `origen_supabase` está registrada en la instalación con su clave de API.
- PostgREST mantiene los nombres de columna declarados.
- `path` se resuelve relativo a la URL de la fuente.
