# [TÍTULO]

**Tipo**: [fuente | integracion | reporte | distribucion]

**Status**: Draft

**Created**: [FECHA]

**Input**: "$ARGUMENTS"

<!--
  Vibe reporting: this spec is the only source of truth for the artifact. The Bizview engine runs
  it only when Status is Approved/Implemented, tasks.md is complete, and `bizview validate` passed.
  Keep only the section that matches your **Tipo** and delete the other three.
  English **Type**: source | integration | report | distribution is also accepted.
-->

## Purpose *(mandatory)*

[Who uses this, which business question it answers, and why now.]

## Clarifications

- Q: … → A: …

---

## Fuente *(solo Tipo: fuente)*

**Fuente**: [nombre de la fuente en Bizview, e.g. "Origen ERP"]

**Propósito de lectura**: [qué aporta esta fuente y por qué se documenta ahora]

**Tablas / endpoints de interés** *(estructura desde `bizview describe`)*:

| Tabla / endpoint | Columnas clave | Tipo | Notas |
|---|---|---|---|
| … | … | … | … |

**Decisión de acceso**: [los reportes leerán esta fuente directamente (Modo directo), o solo a través de integraciones; justificar]

**Necesidades de refresco**: [e.g. cada 30 minutos; full nightly a las 03:00]

**Seguridad**: nunca incluir credenciales, tokens ni secretos en este documento; solo estructuras y catálogo.

---

## Integration *(only for Tipo: integracion)*

**Data source**: [catalogue name in the installation, e.g. "Origen ERP"]

**Schedule**: [e.g. every 30 minutes; full rebuild nightly at 03:00]

**Time zone for business dates**: [e.g. America/Caracas]

### Datasets

For each dataset:

#### [dataset_name]

- **What one row is**: [e.g. one line of a completed sales document]
- **Included / excluded**: [e.g. only completed, non-cancelled documents; returns as negative?]
- **Primary key**: [columns]
- **Date column**: [column used for incremental windows and report periods]
- **Incremental window**: [e.g. re-read the last 7 days each run] or full reload
- **Columns**:

| Column | Type | Nullable | Meaning / origin |
|---|---|---|---|
| … | text / integer / numeric / date / timestamptz / boolean | yes/no | … |

- **Quality checks**: [row count bounds, not-null keys, reconciliation against origin totals]

### Origin notes

[Tables/endpoints read (from `bizview describe`), joins, filters. Read-only.]

---

## Report *(only for Tipo: reporte)*

**Uses**: [alias → integration.dataset, e.g. `lines → erp-ventas.sale_lines`]

*(Direct mode, replaces **Uses** above:)*

**Modo**: directo

**Fuente**: [bi o fuente PostgreSQL que permite reportes directos]

**Tablas**: [`schema.tabla` (alias `a`), ...]

**Mantenido por**: [proceso o equipo que mantiene los datos]

**Volumen esperado**: [escala e.g. ~1 M filas]

**Audience / access**: [admins; users with grant]

### Metrics

| Id | Label | Definition (exact) | Format | Better |
|---|---|---|---|---|
| net_sales | Ventas netas | sum of net amount of sale lines minus returns | currency | higher |

### Dimensions and filters

| Id | Label | Definition |
|---|---|---|

### Views

- KPI cards: […]
- Trend: [metric, grain]
- Rankings / tables: [dimension × metric, top N]

**Periods**: [default and allowed presets] · **Comparison**: [previous period / previous year]

**PDF export**: [yes/no]

**AI narrative** *(optional)*: [enabled?; the aggregated metrics it may use; instructions]. Only
these aggregates are sent to the AI provider; never rows.

---

## Distribution *(only for Tipo: distribucion)*

**Reporte**: [id del reporte a distribuir, e.g. `ventas-mensuales`]

### Schedules

| Frecuencia | Día | Hora | Periodo del reporte |
|---|---|---|---|
| diaria / semanal / mensual | L-V / lunes / 1 | 07:00 | día anterior / semana anterior / mes anterior |

**Destinatarios por rol**: [solo `admin` y/o `user`; nunca direcciones de correo individuales]

**Adjuntar PDF**: [sí / no]

**Días de enlace disponible**: [e.g. 7]

**Política de compartición**: [días máximos que el enlace puede ser compartido, e.g. 30]

---

## Acceptance scenarios *(mandatory)*

1. **Given** …, **When** …, **Then** …

## Success criteria *(mandatory)*

- **SC-001**: [measurable, e.g. figures equal the origin's totals for last month to the cent]

## Assumptions

- …
