# Referencia de reportes — el contrato de integraciones y reportes en detalle

**Cada integración y cada reporte es una spec, y Bizview ejecuta exactamente lo que dice la spec.** El
*flujo de trabajo* — los cinco pasos, el paquete inicial, la importación — está en
[AUTHORING.md](./AUTHORING.md) y [IMPORT.md](./IMPORT.md). Esta página es la referencia a la que esos
dos apuntan: los campos de una integración, de un reporte, de un reporte directo y las reglas que
aplica el validador.

La versión completa, con todos los campos y ejemplos, está en [../REPORTS.md](../REPORTS.md).

## 1. El espacio de trabajo

Un repositorio Git privado del cliente, separado del producto. Se crea una vez:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
uv tool install "bizview-cli @ git+https://github.com/<owner>/bizview#subdirectory=cli"
bizview init workspace --name acme --path acme-bizview
bizview init project "Ventas" --source "Origen ventas"
```

Cada proyecto empieza del mismo paquete que descarga la app (**Proyectos → Nuevo proyecto →
Descargar paquete inicial**); `bizview init project` lo escribe desde la terminal. Valida desde la raíz
con `bizview validate --write-lock`: informa de todos los proyectos.

## 2. La fuente — solo estructura

`bizview describe "<fuente>" --pack --out .` escribe `sources/<nombre>/structure.md` y
`structure.json`: tablas, columnas, tipos, conteos y formas. Nunca filas, nunca credenciales. Es lo que
una IA externa lee en lugar de conectarse.

## 3. La integración

```yaml
id: ventas
spec: specs/001-ventas
source: Origen ventas
schedule: "0 * * * *"
datasets:
  ventas:
    primary_key: [comprobante_id]
    date_column: fecha
    columns:
      comprobante_id: {type: text, nullable: false}
      fecha: {type: date, nullable: false}
      monto_total: {type: numeric, nullable: false}
    extract: {query: queries/ventas.sql, params: [window_start, window_end]}
    incremental: {window_days: 7, mode: window}
```

Una sola instrucción `SELECT` o `WITH` por archivo. Las columnas con datos personales se enumeran en la
spec bajo `**Datos personales**`.

## 4. El reporte

```yaml
id: ventas-por-marca
spec: specs/002-ventas-por-marca-reporte
title: Ventas por marca
uses: {v: ventas.ventas}
date: v.fecha
metrics:
  total: {label: Total, sql: "sum(v.monto_total)", format: currency}
dimensions:
  marca: {label: Marca, sql: v.marca}
views:
  - {id: kpis, type: kpis, metrics: [total]}
  - {id: marcas, type: ranking, dimension: marca, metric: total, limit: 10}
filters: [marca]
periods: {default: last_7_days, allowed: [today, yesterday, last_7_days, mtd, qtd, ytd]}
```

Reglas que el validador aplica: una métrica usa `sum`, `count`, `count(distinct …)`, `avg`, `min`,
`max`, `coalesce`, `round` o `date_trunc`, siempre como `alias.columna`; una `formula` solo combina
métricas con `sql`; en un ranking, `dimension` y `metric` van en singular; un componente `bar` usa `x` y
`series`; cada reporte declara al menos un filtro.

### Reporte directo

Sin integración, sobre una tabla que otro proceso ya prepara:

```yaml
direct:
  source: Almacén ventas
  tables:
    v: reporting.v_ventas_dia
date: v.fecha
materialize: none
```

La declaración es toda la verdad: un objeto fuera de ella se rechaza al validar y otra vez al
renderizar. La spec lleva `**Modo**: directo`, `**Fuente**`, `**Tablas**`, `**Mantenido por**` y
`**Volumen esperado**`.

## 5. Validar, bloquear, aplicar

```bash
bizview validate --write-lock
```

Después, **Proyectos → Importar proyecto** con el zip y **Aplicar**. La importación valida otra vez con
el mismo validador; **Aplicar** compone una versión nueva y arranca el horario. **Volver a la versión
anterior** revierte todo y queda en la auditoría.
