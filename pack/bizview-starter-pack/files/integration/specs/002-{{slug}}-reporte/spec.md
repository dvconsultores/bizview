# {{name}} — reporte

**Tipo**: reporte
**Status**: Approved

**Created**: {{date}}

**Input**: "REEMPLAZA: qué pregunta responde el tablero, en una frase."
"REPLACE: the question the dashboard answers, in one sentence."

## Purpose *(mandatory)*

REEMPLAZA: quién lo usa, qué decide con él y cómo se lee en un teléfono.
REPLACE: who uses it, what they decide with it and how it reads on a phone.

## Clarifications

- P: ¿Qué cifra manda en la pantalla? → R: el total del período.
- Q: which figure leads the screen? A: the period's total.

---

## Report *(only for Spec type: report)*

**Uses**: `d → {{slug}}.{{dataset}}`

**Audience / access**: REEMPLAZA: quién lo lee. Roles admin y user, solo lectura.

### Metrics

| Metric | How it is computed |
|---|---|
| total | suma de los montos del período / sum of the period's amounts |
| comprobantes | número de comprobantes distintos / distinct vouchers |
| promedio | total dividido entre comprobantes / total divided by vouchers |

### Dimensions

| Dimension | Column |
|---|---|
| estado | el estado del comprobante / the voucher status |
| sucursal | la sucursal que lo emitió / the issuing branch |

### Periods and filters

- Período por defecto: últimos 7 días. También mes en curso, trimestre y año.
- Filtros: estado y sucursal. El reporte no se aplica sin al menos un filtro.

### Personal data

**Datos personales**: el reporte no muestra datos personales.
**Personal data**: the report shows no personal data.

## Acceptance scenarios *(mandatory)*

1. **Given** un período con datos, **When** el tablero abre, **Then** las cifras principales suman
   lo mismo que el detalle.
2. **Given** un período sin datos, **When** el tablero abre, **Then** muestra ceros, no un error.
3. **Given** el botón de PDF, **When** se pulsa, **Then** descarga una página con cabecera, cifras y
   tabla.

## Success criteria *(mandatory)*

- **SC-001**: el reporte valida sin errores con `bizview validate`.
- **SC-002**: el tablero abre en menos de 2 s en un teléfono con 4G.

## Assumptions

- La integración `{{slug}}` carga el dataset `{{dataset}}` con la fecha, el estado y el monto.
