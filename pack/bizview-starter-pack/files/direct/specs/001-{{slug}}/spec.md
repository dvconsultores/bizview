# {{name}}

**Tipo**: reporte
**Status**: Approved

**Created**: {{date}}

**Input**: "REEMPLAZA: qué pregunta responde el reporte, en una frase."
"REPLACE: the question the report answers, in one sentence."

## Purpose *(mandatory)*

REEMPLAZA: quién lo usa, qué decide y por qué se lee directo de una tabla ya preparada en vez de
cargarla con una integración.
REPLACE: who uses it, what they decide and why it reads a table already prepared in the source
instead of loading it with an integration.

## Clarifications

- P: ¿Por qué directo? → R: otro proceso ya prepara la tabla y no hace falta historial propio.
- Q: why direct? A: another process already prepares the table and no history of our own is needed.

---

## Report *(only for Spec type: report)*

**Modo**: directo

**Fuente**: {{source}}

**Tablas**: `reporting.v_comprobantes_dia`

**Mantenido por**: REEMPLAZA: el proceso que prepara la vista (ETL de otro sistema, procedimiento
nocturno). / REPLACE: the process that prepares the view.

**Volumen esperado**: REEMPLAZA: filas por día, p. ej. «unas 20 000 filas al día». / REPLACE: rows
per day.

**Audience / access**: REEMPLAZA: quién lo lee. Roles admin y user, solo lectura.

### Metrics

| Metric | How it is computed |
|---|---|
| total | sum of the amount column |
| comprobantes | distinct count of the voucher id |

### Dimensions

| Dimension | Column |
|---|---|
| estado | status |
| sucursal | branch |

### Personal data

**Datos personales**: la vista no expone datos personales.
**Personal data**: the view exposes no personal data.

## Acceptance scenarios *(mandatory)*

1. **Given** the view has rows in the period, **When** the report opens, **Then** the KPIs show the
   total and the number of vouchers.
2. **Given** a period with no rows, **When** the report opens, **Then** it shows zeros instead of an
   error.

## Success criteria *(mandatory)*

- **SC-001**: el reporte valida sin errores con `bizview validate`.
- **SC-002**: el tablero abre en menos de 2 s en un teléfono.

## Assumptions

- La fuente `{{source}}` admite reportes directos y la vista existe con las columnas declaradas.
