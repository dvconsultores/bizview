# {{name}}

**Tipo**: integracion
**Status**: Approved

**Created**: {{date}}

**Input**: "REEMPLAZA: la pregunta de negocio que responde este proyecto, en una frase."
"REPLACE: the business question this project answers, in one sentence."

## Purpose *(mandatory)*

REEMPLAZA este párrafo: quién usa el tablero, qué decisión toma con él y por qué ahora.
REPLACE this paragraph: who uses the dashboard, what decision they make with it and why now.

## Clarifications

- P: ¿Qué se cuenta por fila? → R: un comprobante. Q: what is one row? A: one voucher.
- P: ¿Qué período se compara? → R: con el período anterior. Q: which period is compared? A: the
  previous one.

---

## Integration *(only for Spec type: integration)*

**Data source**: {{source}}

**Schedule**: cada hora (`0 * * * *`) · hourly

**Time zone for business dates**: UTC

### Datasets

#### {{dataset}}

- **What one row is**: REEMPLAZA: un comprobante con su fecha, estado y monto.
- **Included / excluded**: REEMPLAZA: qué entra y qué no; sé explícito.
- **Primary key**: comprobante_id
- **Date column**: fecha
- **Incremental window**: releer los últimos 7 días en cada ejecución
- **Columns**:

| Column | Type | Nullable | Meaning / origin |
|---|---|---|---|
| comprobante_id | text | no | Identificador del comprobante / voucher id |
| fecha | date | no | Fecha contable / business date |
| estado | text | no | emitido, pagado o anulado / issued, paid or voided |
| sucursal | text | yes | Sucursal que emitió / issuing branch |
| monto_total | numeric | no | Monto total / total amount |

- **Quality checks**: row_count con mínimo 0; not_null en comprobante_id, fecha, estado y
  monto_total.

### Personal data

**Datos personales**: ninguna columna de este dataset contiene datos personales.
**Personal data**: no column in this dataset holds personal data.

If that changes, list the columns here — Bizview refuses to apply a project that carries personal
data without this line. Si cambia, enumera aquí las columnas: Bizview no aplica un proyecto con
datos personales sin esta línea.

---

## Acceptance scenarios *(mandatory)*

1. **Given** comprobantes emitidos en la ventana, **When** se ejecuta la carga, **Then** el dataset
   tiene una fila por comprobante con su identificador único.
2. **Given** cualquier fila cargada, **When** se revisa, **Then** comprobante_id, fecha, estado y
   monto_total no son nulos.
3. **Given** una ejecución incremental, **When** se consulta el dataset, **Then** solo aparecen los
   comprobantes con fecha entre :window_start y :window_end.

## Success criteria *(mandatory)*

- **SC-001**: la integración valida sin errores con `bizview validate`.
- **SC-002**: la clave primaria no tiene duplicados.
- **SC-003**: el dataset puede agruparse por fecha y estado para sumar monto_total.

## Assumptions

- La fuente `{{source}}` está registrada en la instalación.
- Los estados y las fechas usan los valores declarados en la tabla de columnas.
