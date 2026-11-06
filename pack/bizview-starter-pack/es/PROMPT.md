# Instrucciones para tu IA — proyecto BizView

Eres quien escribe un proyecto de BizView. Yo lo importaré en BizView, que lo valida, lo ejecuta,
lo convierte en tableros y lo comparte. No tienes acceso a la base de datos: solo a este documento,
a `REQUEST.md` y, si lo hay, a `sources/<fuente>/structure.md`.

## Lo que tienes que devolver

**Un solo archivo `.zip`.** Dentro, los archivos del proyecto en la raíz (sin una carpeta que los
envuelva), con esta forma exacta:

```
project.yaml
specs/001-<slug>/spec.md        obligatorio
specs/001-<slug>/plan.md        obligatorio
specs/001-<slug>/tasks.md       obligatorio, todas las tareas [X]
integrations/<id>/integration.yaml            si hay integración
integrations/<id>/queries/*.sql               una lectura de solo lectura por archivo
integrations/<id>/requests/*.yaml             REST/SOAP en lugar de SQL
reports/<id>/report.yaml                      obligatorio
assets/**                                     opcional: imágenes (PNG, JPEG, WebP, SVG)
```

`<slug>` es el `slug` de `project.yaml`: minúsculas, dígitos y guiones. La carpeta de la spec es
`001-<slug>` y el `id` de cada artefacto es el nombre de su carpeta. Un `id` de reporte es una URL:
`/r/<id>`. Si hay varias specs, numéralas 002, 003… y que cada artefacto apunte a la suya con
`spec: specs/NNN-<slug>`.

## Reglas que el validador aplica (las 9 comprobaciones)

1. **Esquema y formato.** Cada YAML cumple el esquema de `.bizview/schemas/`, y las carpetas y los
   nombres de archivo son los del formato. Nada de archivos sueltos ni de carpetas inventadas.
2. **Spec aprobada.** Cada artefacto tiene su `spec.md` en su propia carpeta `specs/NNN-…`, con
   `**Tipo**: integracion | reporte` y `**Status**: Approved`. Sin spec aprobada no hay artefacto.
3. **Referencias.** Cada `spec:` apunta a una carpeta que existe; cada métrica, dimensión, vista y
   filtro nombra algo declarado; cada `uses` nombra una integración y un dataset declarados.
4. **SQL.** Una sola instrucción `SELECT` o `WITH` por archivo, de solo lectura, sin `;` encadenados,
   sin DDL ni DML. En transformaciones, una fecha se convierte con
   `CAST(strftime(columna, '%Y-%m-%d') AS DATE)`. Toda columna que un reporte usa debe estar
   declarada en el dataset que lee.
5. **Identificadores.** El `id` de cada artefacto es único en la instalación y coincide con su
   carpeta; los números de spec son de tres dígitos, consecutivos y no se repiten.
6. **Imágenes.** Si `images:` nombra una carpeta, existe, no está vacía y sus claves coinciden con la
   columna; un bloque `chart`/`table` del PDF no puede depender de imágenes solo SVG.
7. **Datos personales.** Si un dataset lleva una columna con datos personales, la `spec.md` de la
   integración la enumera en una línea `**Datos personales**: …`. Si no hay ninguna, escribe
   `**Datos personales**: ninguna`.
8. **Filtros.** Cada reporte declara al menos un filtro en `filters:`. Sin filtros no se aplica.
9. **Presupuesto.** Artefactos: hasta 400 archivos, 2 MB por archivo, 20 MB en total. Imágenes:
   hasta 2 000 archivos, 300 KB por archivo, 25 MB en total. Lo que no es del proyecto (este
   documento, `REQUEST.md`, `sources/`, `.bizview/`) no se importa.

## Contrato de los artefactos

`project.yaml` — `name`, `slug`, `description`, `created`.

`integration.yaml` — `id`, `spec`, `source` (el nombre de la fuente en BizView), `schedule` (cron),
`timezone`, `datasets:` con `primary_key`, `date_column`, `columns:` (`type`, `nullable`,
`description`, `enum` si aplica), `extract:` (`query: queries/x.sql` o `request: requests/x.yaml`)
e `incremental:` (`window_days`, `full_rebuild_cron`, `mode`). Un dataset con ventana filtra con
`:window_start` y `:window_end` y declara los dos en `extract.params`. Checks: `row_count`, `not_null`.

`report.yaml` — `id`, `spec`, `title`, `uses:` (alias → `<integración>.<dataset>`), `date`
(`alias.columna`), `metrics:` (`sql` o `formula`), `dimensions:`, `periods:`, `compare:`,
`filters:`, `access:` (`roles: [admin, user]`), `views:`, `pdf:`, `layout:` (`web.components` y
`pdf.blocks`).

- Una métrica usa `sum`, `count`, `count(distinct …)`, `avg`, `min`, `max`, `coalesce`, `round`,
  `date_trunc`, siempre como `alias.columna`. Una `formula` solo combina métricas que tienen `sql`.
- Vistas: `kpis`, `trend`, `ranking`, `table`, `gauge`, `index`, `share`, `asset`.
  **En un ranking, `dimension` y `metric` van en singular**, nunca `dimensions`/`metrics`.
- En el layout, **un componente `bar` usa `x` y `series`**; `line` usa `x` y `series`; `kpi` usa
  `metric`; `table` usa `columns`. `span` va de 1 a 12.
- Un reporte directo (sin integración) declara `direct: {source, tables: {alias: esquema.objeto}}`
  en lugar de `uses`, más `date` y, si aplica, `joins`. La forma corta de `tables` solo vale si la
  fuente es BI-ready.

Nombres de negocio, no de motor: `comprobante_id`, nunca `document_id`; `fecha`, nunca `created_at`
en lo que lee el lector. Etiquetas en el idioma que pida `REQUEST.md`.

## Cómo trabajar

1. Lee `REQUEST.md`: la pregunta, quién lee, qué filtros, qué período, qué estilo visual.
2. Lee `sources/<fuente>/structure.md` si existe: es la estructura real. No inventes tablas ni
   columnas que no estén ahí.
3. Escribe la `spec.md` primero (el porqué y los datasets), luego `plan.md` y `tasks.md`, luego los
   artefactos.
4. Antes de responder, repasa las nueve comprobaciones una por una.
5. Devuelve **un zip** con los archivos en la raíz y una frase que diga qué contiene.

Si trabajas con la carpeta abierta en un editor o un agente de código, escribe los archivos ahí y
valida con `bizview validate`. Si trabajamos en un chat, devuelve el zip.

## Qué no hagas

- No inventes datos, ni siquiera de ejemplo, dentro del SQL: el proyecto describe la lectura.
- No escribas credenciales, hosts ni cadenas de conexión.
- No dejes tareas sin marcar en `tasks.md`: todas van `[X]`.
- No uses `**Tipo**: fuente` si no hay artefacto que lo consuma; usa `integracion` o `reporte`.
- No añadas dependencias, scripts ni ejecutables: solo texto y YAML.
