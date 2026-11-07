🇪🇸 Español · 🇬🇧 [English](../REPORTS.md)

# Referencia de reportes — el contrato de reportes e integraciones en detalle

**Cada integración y cada reporte es una spec, y Bizview ejecuta exactamente lo que dice la spec.**
El *flujo de trabajo* — los cinco pasos, el paquete inicial, la importación — está en
[AUTHORING.md](AUTHORING.md) y [IMPORT.md](IMPORT.md). Esta página es la referencia a la que
esos dos apuntan: los campos de una integración, de un reporte, de un reporte directo y las reglas
que aplica el validador.

Si estás empezando un proyecto, lee primero AUTHORING.md; vuelve aquí cuando necesites un campo.

## 1. Crear el espacio de trabajo (una vez por cliente)

El espacio de trabajo es un **repositorio Git privado del cliente**, separado del producto.

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
uv tool install "bizview-cli @ git+https://github.com/<owner>/bizview#subdirectory=cli"
bizview init workspace --name acme --path acme-bizview   # espacio de trabajo v2: una carpeta por proyecto
cd acme-bizview && git remote add origin <private repo> && git push -u origin main
bizview init project "Ventas" --source "Origen ventas"    # projects/ventas/, el paquete inicial
```

Cada proyecto empieza del mismo paquete que descarga la aplicación (**Proyectos → Nuevo proyecto →
Descargar paquete inicial**): `bizview init project` lo escribe desde una terminal. Trabaja en
`projects/<slug>/` con la herramienta que prefieras y ejecuta `bizview validate --write-lock` desde la
raíz del espacio de trabajo (informa de todos los proyectos). El árbol plano heredado de abajo
todavía se acepta (`bizview init <carpeta> --name acme --layout legacy`).

```text
acme-bizview/
├── bizview.yaml
├── bizview.lock
└── projects/ventas/
    ├── project.yaml                      nombre, identificador, descripción, fecha de creación
    ├── .specify/memory/constitution.md
    ├── specs/001-origen/                 **Tipo**: fuente — la fuente y sus tablas
    ├── specs/002-ventas-diarias/         **Tipo**: integracion
    ├── specs/003-ventas/                 **Tipo**: reporte
    ├── specs/004-envio-semanal/          **Tipo**: distribucion
    ├── integrations/<id>/integration.yaml + queries/*.sql | requests/*.yaml
    ├── reports/<id>/report.yaml
    └── distributions/<id>.yaml           envíos programados a roles, política de enlaces para compartir
```

`bizview init` instala Spec Kit con el **preset de Bizview** (plantillas de spec, plan y tareas para
integraciones y reportes) y la **extensión de Bizview** (`/speckit.bizview.validate`,
`/speckit.bizview.describe`, y un hook `after_implement` obligatorio que ejecuta `bizview validate`),
además de la constitución del espacio de trabajo y las reglas de autoría (`CLAUDE.md`, `AGENTS.md`,
`.github/copilot-instructions.md`).

```text
acme-bizview/
├── bizview.yaml                      nombre, moneda (ISO 4217), zona horaria informativa
├── specs/integrations/NNN-<id>/      spec.md plan.md tasks.md
├── specs/reports/NNN-<id>/           spec.md plan.md tasks.md
├── integrations/<id>/integration.yaml + queries/*.sql | requests/*.yaml
├── reports/<id>/report.yaml
└── bizview.lock                      sumas de verificación escritas por `bizview validate --write-lock`
```

## 2. Mirar la fuente — solo estructura

El superusuario crea un token en **Administración → Tokens de acceso** (alcance `describe`, se muestra
una sola vez). Después, en el espacio de trabajo:

```bash
export BIZVIEW_URL=https://bi.acme.com BIZVIEW_TOKEN=bzv_…
bizview describe "Origen ERP"            # PostgreSQL: tablas, columnas, claves, filas estimadas
bizview describe "API pedidos" --path /orders   # REST: forma del JSON (claves y tipos, sin valores)
```

Las descripciones nunca contienen valores de filas. Dáselas a tu IA como contexto para la spec.

Desde la feature 052 un superusuario también puede hacer esto desde la interfaz — **Fuentes de datos →
«fuente» → Estructura** —: pulsa **Generar estructura con IA** (una pasada interna: escaneo, IA,
verificación) y luego **Descargar estructura** para obtener el `sources/<nombre>/structure.md` y el
`structure.json` del propio paquete. El paquete generado es más rico que el catálogo en bruto: tablas
lógicas, semántica de los campos, claves, campos de fecha, relaciones, marcas de datos personales y
las notas que dicen qué es una fila. En el espacio de trabajo, `bizview describe "<nombre>" --pack`
escribe los mismos dos archivos; `?mode=scan` da la lectura en bruto.

## 3. Escribir una spec de integración

Pídeselo a tu IA, por ejemplo: *"Integración: líneas de venta y devoluciones de la fuente
'Origen ERP', cada 30 minutos, últimos 7 días, recarga completa diaria"*. La spec debe decir, para
cada conjunto de datos: qué es una fila, las inclusiones y exclusiones, la clave primaria, la columna
de fecha, la ventana incremental, las columnas con sus tipos y las comprobaciones de calidad. La
implementación es `integration.yaml` más un `SELECT` de solo lectura por conjunto de datos:

```yaml
id: erp-ventas
spec: specs/integrations/001-erp-ventas
source: Origen ERP                       # nombre en Administración → Fuentes de datos
schedule: "*/30 * * * *"                 # zona horaria de la instalación (TIMEZONE)
timezone: America/Caracas                # fechas de negocio
datasets:
  sale_lines:
    primary_key: [line_kind, line_id]
    date_column: local_date
    columns:
      line_kind: {type: text, nullable: false, enum: [sale, return]}
      line_id: {type: bigint, nullable: false}
      local_date: {type: date, nullable: false}
      net_amount: {type: numeric, nullable: false}
    extract: {query: queries/sale_lines.sql, params: [window_start, window_end]}
    incremental: {window_days: 7, full_rebuild_cron: "0 3 * * *"}
    checks:
      - {type: row_count, min: 1}
      - {type: reconcile, query: queries/daily_totals.sql, compare: [local_date, net_amount], tolerance: 1.0}
```

Reglas que aplica `bizview validate` y otra vez la instalación:

- exactamente un `SELECT`/`WITH` por archivo; nada de DML/DDL, `COPY`, `SELECT … INTO`, bloqueos ni
  funciones que lean archivos, duerman, envíen señales o cambien ajustes; como parámetros solo
  `:window_start` y `:window_end` (ligados, nunca concatenados);
- la consulta debe devolver exactamente las columnas del contrato; los tipos se exigen al cargar;
- los conjuntos de datos incrementales deben filtrar por los dos parámetros de la ventana.

Una ejecución carga cada conjunto de datos en una tabla de preparación, ejecuta las comprobaciones del
contrato (nulos, enumerados, mínimo y máximo, claves duplicadas) y las de la spec (conteos de filas,
no nulos, **conciliación** contra los totales del origen calculados de forma independiente), y solo
entonces reemplaza la ventana: todo o nada. Una comprobación fallida conserva los datos anteriores y
muestra el motivo en **Administración → Integraciones**.

Las fuentes REST/SOAP usan `extract: {request: requests/<nombre>.yaml}` con `method`, `path`,
`params` (`{window_start}`, `{window_start_date}`…), `pagination` (`page`, `offset`, `cursor`,
`link`), `records` (ruta JSON a la lista) y `fields` (columna → ruta JSON).

## 4. Escribir specs de reporte — muchas por integración

Un reporte usa conjuntos de datos de una o más integraciones (alias), declara las uniones, la columna
de fecha, las métricas (expresiones agregadas de SQL o fórmulas sobre otras métricas), las
dimensiones, las vistas, los filtros, el acceso, el PDF y la narrativa opcional de IA:

```yaml
id: ventas
spec: specs/reports/001-ventas
title: Ventas
uses: {lines: erp-ventas.sale_lines, products: erp-ventas.products}
joins: [{left: lines.product_id, right: products.product_id, type: left}]
date: lines.local_date
metrics:
  net_sales: {label: Ventas netas, sql: "coalesce(sum(lines.net_amount), 0)", format: currency}
  orders: {label: Pedidos, sql: "count(distinct lines.document_id)", format: integer}
  avg_ticket: {label: Ticket promedio, formula: net_sales / orders, format: currency}
dimensions:
  product: {label: Producto, sql: "coalesce(products.name, 'Sin producto')"}
views:
  - {type: kpis, metrics: [net_sales, orders, avg_ticket]}
  - {type: trend, metric: net_sales, grain: auto}
  - {type: ranking, dimension: product, metric: net_sales, limit: 10}
filters: [product]
ai_narrative: {enabled: true, inputs: [net_sales, orders], instructions: Resume en 3 frases.}
```

Cada alias de `uses` tiene que ser alcanzable desde el alias de `date` a través de `joins`: un reporte
es una sola consulta, así que un conjunto que nadie une no se puede leer y el tablero respondería
«Conjuntos sin unión». El validador lo dice antes de que el reporte se pueda aplicar, con la línea que
hay que añadir.

Las expresiones solo pueden usar las columnas de los alias declarados y funciones de la lista blanca
(`sum`, `count`, `avg`, `min`, `max`, `coalesce`, `case`, `round`, `date_trunc`, …); nada de
subconsultas. Los períodos (hoy … últimos 12 meses, personalizado), las comparaciones (período
anterior, año anterior, base cero → «Nuevo»), la frescura y el PDF los pone el producto. La narrativa
de IA recibe **solo** las métricas listadas en `inputs`, agregadas, nunca filas.

### Tema por reporte (opcional)

Cada instalación gestiona los temas de sus reportes en **Administración → Apariencia**: los cinco que
trae (`Impacto`, `Clásico`, `Monocromo`, `Contraste alto`, `Daltónico`), los que se suben allí y los que
trajo un proyecto. Un reporte puede declarar el suyo; entonces viaja con la versión del espacio de
trabajo y se aplica a la página web y al PDF:

```yaml
layout:
  theme:
    id: contraste        # cualquier tema de la instalación, incluidos los subidos
    mode: auto           # auto | light | dark
```

El valor es un id de tema, nunca un color: las definiciones de reporte llevan solo roles semánticos,
así que los validadores pueden garantizar contraste y distinción en ambos modos. `palette:` se acepta
durante una versión como alias obsoleto de `id`, para que un reporte escrito antes de que los temas
tuvieran id siga aplicándose. `mode: dark` pinta de oscuro el área propia del reporte aunque la
aplicación de quien lo ve sea clara — el marco se queda como esa persona lo eligió —, y un interruptor
de sol y luna en el reporte permite a quien lo ve imponerlo durante la sesión. El PDF usa siempre la
variante clara del tema.

`id` debe nombrar un tema que existe: el de la biblioteca de la instalación o uno que el proyecto
traiga en `themes/<id>.yaml`. Un reporte que nombra un tema que nadie tiene es un problema de
validación, no un reemplazo silencioso. Consulta [THEMES.md](THEMES.md) para el archivo del tema en
sí.

### Etiquetas en inglés (opcional)

Los reportes pueden aportar variantes en inglés mediante claves `_en`:

```yaml
title: Ventas
title_en: Sales
metrics:
  net_sales:
    label: Ventas netas
    label_en: Net sales
    sql: "coalesce(sum(lines.net_amount), 0)"
    format: currency
dimensions:
  product:
    label: Producto
    label_en: Product
    sql: "coalesce(products.name, 'Sin producto')"
views:
  - {type: ranking, dimension: product, metric: net_sales, limit: 10, title: Ranking de productos, title_en: Product ranking}
```

Claves admitidas: `title_en`, `description_en`, `metrics.<id>.label_en`,
`metrics.<id>.description_en`, `dimensions.<id>.label_en`, y `title_en` en las vistas de ranking y de
tabla.

- Los textos en inglés se muestran cuando la interfaz está en inglés; si falta una variante `_en`, se
  muestra el texto en español. El contenido de autor nunca se traduce automáticamente.
- Estas etiquetas se usan también en los PDF, en los asuntos y encabezados de correo, en las
  exportaciones CSV y en el catálogo de tableros, que se busca en los dos idiomas.
- Los marcadores de la spec también se aceptan en inglés: `**Personal data**:`
  (= `**Datos personales**:`), `**Mode**: direct` (= `**Modo**: directo`), `**Source**:`,
  `**Tables**:`, `**Maintained by**:`, `**Expected volume**:`.
- Los formatos de número y fecha siguen el idioma: `es` usa `1.234,56`; `en` usa `1,234.56`.
- El idioma de la CLI viene de la opción global colocada antes del comando (`bizview --lang en validate`); si no, de `BIZVIEW_LANG`; si no, de `LC_ALL` / `LC_MESSAGES` / `LANG` (la primera no vacía decide); si no, español.

### Imágenes (opcional)

Un proyecto puede llevar imágenes con sus archivos y usarlas en una tabla, en una tarjeta de activo o
en una cifra. Declara los conjuntos en el reporte y nombra uno desde el componente:

```yaml
images:
  coins:                        # el nombre del conjunto; los componentes lo referencian
    folder: assets/coins        # dentro del proyecto
    key: symbol                 # la dimensión o columna que nombra el archivo
    fallback: initial           # initial | none
layout:
  web:
    components:
      - {id: tabla, type: table, view: detalle, image: coins, span: 12}
```

- El archivo de una fila es `assets/coins/<clave>`: `BTC` encuentra `BTC.png`, `btc.png`, `BTC.svg`,
  `BTC.webp` o `BTC.jpg`; las mayúsculas no importan, y una clave con `/` o espacios se convierte en
  `_` en el nombre del archivo. Nunca escribes una ruta en el reporte: la instalación la resuelve.
- Una clave sin archivo dibuja el círculo con la primera letra, coloreado desde la paleta (`initial`),
  o nada en absoluto (`none`).
- Se admiten `.png`, `.jpg`, `.webp` y `.svg` bajo `assets/`, como máximo 300 KB cada uno y 25 MB por
  proyecto. Un `.png` tiene que ser realmente un PNG, y un SVG se limpia al importar: sin scripts y
  sin referencias externas.
- El PDF imprime los archivos raster; un conjunto solo con SVG imprime el círculo en su lugar, así que
  añade un PNG cuando el reporte se comparta en papel.
- Un conjunto alimentado por una columna de URL lee el valor de la fila, así que la vista que usa el
  componente debe devolver esa columna: declara una dimensión con `sql: <alias>.<columna>` y añádela a
  las dimensiones de la vista; no se muestra salvo que el componente la liste en sus propias
  `columns`. Un conjunto que nombra una `column:` y una vista que no la proyecta es un aviso
  (`image_column_not_projected`), y todas las filas mostrarían el reemplazo.
- Una tarjeta `kpi` no tiene fila, así que su conjunto se indexa por el id de la métrica
  (`images: {coins: {folder: assets/coins, key: total_facturado}}`).
- **Licencia**: incluye solo imágenes que puedas redistribuir. Los logos de las marcas de tus propios
  clientes, el arte del propio proveedor o un conjunto CC0 (por ejemplo los logos de criptomonedas
  CC0) sirven; una imagen copiada de un sitio web normalmente no, y viaja dentro del proyecto cuando
  lo exportas.

### Reportes directos ("direct reports")

Usa un reporte directo solo cuando los datos ya los prepara otro proceso — una tabla BI probada, una
vista de reporte mantenida por el ERP —; si no, escribe una integración. El autor sigue la misma
regla. No hay integración, ni ejecución del worker, ni copia; el reporte lee la fuente en vivo en cada
renderizado.

```yaml
direct:
  source: bi
  tables:
    v:
      table: public.bi_ventas
      columns:
        fecha: { type: date }
        sucursal: { type: text }
        monto: { type: numeric }
        unidades: { type: integer }
  cache_seconds: 300
date: v.fecha
metrics:
  total_vendido: { label: Total vendido, sql: "sum(v.monto)", format: currency }
dimensions:
  sucursal: { label: Sucursal, sql: v.sucursal }
```

Todo lo demás — las uniones entre alias declarados, las métricas, las dimensiones, las vistas, los
filtros, los períodos, la comparación, el acceso, el PDF y la narrativa de IA — funciona igual. Un
reporte tiene exactamente uno de `uses` o `direct`; `materialize` se rechaza porque la caché es el
mecanismo de velocidad. Ejemplo de referencia: el paquete de autoría `example-direct` (espacio de
trabajo `golden-direct`).

Las fuentes son `bi` — la base BI de esta instalación, permitida por `DIRECT_REPORTS_BI` (activo por
defecto) — o una fuente PostgreSQL del catálogo con "Permitir reportes directos" activado en
Administración → Fuentes de datos (desactivado por defecto; confirmación con contraseña; auditado).
Las fuentes SOAP, REST y Supabase (REST) no se pueden leer directamente. El nombre `bi` está
reservado.

La validación falla por cada línea de spec que falte:

```markdown
**Modo**: directo
**Fuente**: bi
**Tablas**: public.bi_ventas
**Mantenido por**: <el proceso que da forma a los datos>
**Volumen esperado**: <filas y crecimiento>
```

Añade `**Datos personales**: <columnas>` cuando una dimensión o un filtro use una columna marcada como
dato personal.

Límites:

| Ajuste | Rango / valor por defecto | Significado |
| --- | --- | --- |
| `cache_seconds` | 60–86400, por defecto 300 | resultados en caché por reporte, selección y cubo de tiempo; las peticiones concurrentes idénticas comparten una consulta |
| `timeout_seconds` | 1–60, por defecto 15 | plazo de la sentencia |
| `max_rows` | 1–5000, por defecto 500 | filas de las vistas de tabla |
| `DIRECT_REPORT_CONCURRENCY` | por defecto 2 | consultas a la vez por fuente; las demás esperan hasta el plazo y luego "La fuente está ocupada" |
| `DIRECT_REPORT_WARN_ROWS` | por defecto 5 millones (estimadas) | las tablas por encima de esto necesitan un índice cuya primera columna sea la de fecha (o particionado por ella); si no, la validación dice "Tabla grande sin índice por fecha: crea una integración con materialize: daily o indexa <columna>" |

Seguridad: las sesiones son de solo lectura y ejecutan solo el SQL que genera el motor. Las tablas del
producto de la base BI (usuarios, sesiones, auditoría, credenciales, compartición, `alembic_version`,
y los esquemas `pg_catalog`, `information_schema`, `app_test_*`, `preview_*`) se rechazan con "Tabla
del producto: no se puede leer en un reporte directo"; las tablas de conjuntos de datos `ds_*` sí se
pueden leer. Las vistas sobre tablas del producto también se rechazan; ver la §5 de INSTALL para
`DIRECT_BI_ROLE`.

Los identificadores son solo en minúsculas: `table` es `schema.table` y encaja con
`^[a-z_][a-z0-9_]{0,62}\.[a-z_][a-z0-9_]{0,62}$`; los alias y las columnas encajan con
`^[a-z][a-z0-9_]{0,40}$`. Las fuentes con nombres en mayúsculas o entrecomillados necesitan una vista
en minúsculas del lado de la fuente (por ejemplo
`CREATE VIEW reporting.ventas AS SELECT "FechaDoc" AS fecha, ... FROM "Ventas"`).

Al validar y aplicar, la instalación compara cada tabla y columna declarada con la fuente en vivo: una
tabla que falta, una columna que falta o un tipo incompatible falla. Tipos compatibles:
text ← text/varchar/char/uuid/citext/name; integer ← integer/smallint;
bigint ← bigint/integer/smallint;
numeric ← numeric/integer/bigint/smallint/real/double precision; boolean; date;
timestamptz ← timestamp with/without time zone. Que la fuente esté caída al validar es solo un aviso.
`bizview validate` sin conexión comprueba el esquema, las líneas de la spec y los nombres reservados;
añade `--describe NAME=FILE` (la salida de `bizview describe NAME --json`) o `--live` (usa
`BIZVIEW_URL` y `BIZVIEW_TOKEN`) para comprobar la estructura.

Los usuarios ven "Datos en vivo · <fuente> · consultado <hora>" en el pie de página (también en el PDF
y en la vista compartida). Cuando la fuente falla y hay un resultado en caché de hasta 24 h, el
reporte muestra "Datos de <hora>; la fuente no respondió"; si no, un error claro; no hay un bucle de
reintentos apretado (espera de 30 s). Una columna que desaparece muestra "La estructura de la fuente
cambió: falta <columna>" y la pantalla del espacio de trabajo (`/admin/espacio`) marca el reporte como
"Estructura cambiada" (cada reporte muestra su modo Dataset/Directo, la fuente y las tablas). La
actualización automática "Al llegar datos nuevos" refresca una vez por `cache_seconds`. Cada consulta
directa se registra sin valores; Administración → Seguridad cuenta las lecturas directas por fuente
en 24 h y cuántas imágenes ha traído la caché de imágenes de terceros (cantidad, tamaño, resultado;
nunca las imágenes).

## 5. Validar, bloquear, confirmar — luego aplicar

```bash
bizview validate --write-lock      # también lo ejecuta el hook after_implement
git add -A && git commit -m "Reporte ventas" && git push
```

En el servidor de la instalación: `cd /opt/bizview/workspace && git pull`, y luego **Administración →
Workspace (`/admin/espacio`) → Validar → Aplicar** (confirmación con contraseña). La instalación valida
otra vez (además: que las fuentes existan y que el bloqueo coincida con los archivos) y copia la
versión a su base de datos; los archivos que cambien después no hacen nada hasta la siguiente
aplicación. **Volver a la versión anterior** restaura la versión previa en segundos. Los reportes
aparecen en el inicio de los usuarios como tableros; el acceso sigue los permisos habituales.

Cada proyecto se valida y se aplica en su propia página: los problemas que muestra son los suyos (los
de otro proyecto solo se cuentan, nunca se ofrecen como corrección), y aplicar uno lo compone con el
resto del espacio de trabajo; si otro proyecto rompe la composición, la aplicación lo nombra. Ver
[proyectos/aislamiento.md](./guides/proyectos/aislamiento.md).

Cuando un tablero no se puede pintar (un conjunto de datos desapareció, una métrica divide por cero,
un formato está fuera del catálogo, un bloque del PDF no se puede dibujar) la tarjeta muestra una ficha
con su código y la pieza que falló, y el resto del tablero se sigue renderizando; un reporte cuyo
conjunto de datos nunca se cargó responde `dataset_missing` en lugar de un error anónimo. Ver
[tableros/errores.md](./guides/tableros/errores.md).

Un proyecto se aplica solo cuando se cumplen tres cosas más, y cada una dice cuál falta en la barra de
estado bajo **Pendiente para aplicar**:

- cada `queries/*.sql` y `requests/*.yaml` ha pasado **Volver a comprobar** desde su último cambio (la
  comprobación corre contra la fuente, solo estructura y conteos);
- ninguna columna de conjunto de datos marcada como dato personal se queda sin su línea de spec
  `**Datos personales**: <columnas>`;
- el reporte declara al menos un filtro (`filters: [<dimensión>]`).

Las dos primeras también las informa `bizview validate` — la columna personal como error, los filtros
que faltan como aviso —, así que la IA del autor puede corregirlas antes de la importación.

## "Sin spec, no hay ejecución"

Nada corre si su carpeta de spec no tiene `spec.md`, `plan.md` y `tasks.md`; si el `**Status**` de la
spec no es `Approved` o `Implemented`; si `**Spec type**` no coincide; si alguna tarea está sin
marcar; o si `bizview.lock` no coincide con los archivos.
