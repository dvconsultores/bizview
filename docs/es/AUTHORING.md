🇪🇸 Español · 🇬🇧 [English](../AUTHORING.md)

# Autoría de un proyecto de Bizview

Bizview ejecuta lo que escribes; no lo escribe. Este documento es el contrato completo: la carpeta,
la petición, los esquemas, las reglas, el paso de validación y un ejemplo completo al final.

Puedes seguirlo a mano, o entregarle el paquete a cualquier IA: el `PROMPT.md` del paquete dice las
mismas reglas en la forma que un agente necesita.

## 0. El paquete inicial

No tienes que escribir la carpeta desde cero. **Proyectos → Nuevo proyecto → Descargar paquete
inicial** construye `bizview-starter-<identificador>.zip` en el servidor, y ese zip es la carpeta que
describe el §2 con el nombre que escribiste, el idioma que elegiste y, cuando eliges una, la
estructura de la fuente.

```text
PROMPT.md            las reglas para tu IA, autocontenidas: funcionan pegadas en un chat
REQUEST.md           la petición que rellenas
project.yaml         nombre, identificador, fecha de creación
specs/001-<slug>/    la spec, el plan y las tareas de la integración (kind: integration)
specs/002-<slug>-reporte/   la spec propia del reporte (kind: report)
integrations/<id>/   integration.yaml + queries/example.sql (se omite en un reporte directo)
reports/<id>/        report.yaml
sources/<name>/      structure.md + structure.json, cuando se eligió una fuente
.bizview/            schemas/*.json y preset.yaml: lo que comprueba el validador
CONTENIDO.md / CONTENTS.md            para qué sirve cada archivo, en español y en inglés
QUE-HACE-BIZVIEW.md / WHAT-BIZVIEW-DOES.md   qué hacen importar y aplicar, en ambos idiomas
CLAUDE.md, AGENTS.md                 el texto de PROMPT.md para herramientas que leen una carpeta
```

El proyecto renderizado valida sin errores: lo que queda por escribir está marcado `REEMPLAZA` /
`REPLACE`. `make starter-template` publica el mismo paquete con marcadores como
[bizview-starter-template.zip](../../bizview-starter-template.zip), y
`bizview init project "<nombre>" [--source <s>]` lo escribe desde una terminal. Una sola fuente, tres
salidas.

### Pegarlo en un chat

`PROMPT.md` está escrito para sobrevivir a un copiar y pegar: pégalo, pega el `REQUEST.md` relleno,
pega `sources/<nombre>/structure.md` cuando tengas uno y pide el proyecto. La respuesta debe ser **un
zip con los archivos del proyecto en la raíz**. Con una herramienta de código, abre la carpeta en su
lugar: `CLAUDE.md` y `AGENTS.md` llevan las mismas reglas.

## 1. Los cinco pasos

| # | Paso | Pantalla o comando |
|---|---|---|
| 1 | Añadir la fuente | **Fuentes de datos → Nueva**, luego **Probar** |
| 2 | Generar su estructura | **Estructura → Generar estructura**, o `bizview describe "<fuente>" --pack --out .` |
| 3 | Descargar el paquete inicial | **Proyectos → Nuevo proyecto → Descargar paquete inicial**, o `bizview init project "<nombre>"` |
| 4 | Rellenar `REQUEST.md` y dárselo a tu IA | cualquier chat o herramienta de código |
| 5 | Importar el zip y aplicar | **Proyectos → Importar proyecto**, luego **Aplicar** |

`bizview validate` es opcional y el producto nunca se lo salta: la importación ejecuta el mismo
validador antes de escribir el borrador.

`bizview describe` imprime solo estructura — nombres de tablas, nombres de columnas, tipos, conteos
de filas. Nunca devuelve filas, y ninguna credencial aparece jamás en su salida.

Feature 052: el mismo contenido está en la página de la fuente — **Fuentes de datos → «fuente» →
Estructura** — con **Descargar estructura (.md)** y **(.json)**, o desde la terminal. Pulsa primero
**Generar estructura con IA** y el paquete lleva las tablas lógicas, los campos, las relaciones y las
notas que la IA de un autor necesita (ver [REPORTS.md](REPORTS.md)).

```bash
bizview describe "Origen ERP" --pack --out .   # escribe sources/<name>/structure.md + structure.json
```

Los dos archivos son del paquete: `structure.md` sigue la plantilla de
`pack/bizview-starter-pack/bizview-starter/sources/<nombre>/structure.md`, y `structure.json` lleva
el mismo contenido con una cabecera `pack`. Tus notas en **Observaciones** y las marcas de datos
personales viajan en los dos.

## 2. La carpeta

```text
mycompany/                          el espacio de trabajo, uno por organización
├── bizview.yaml                    manifiesto: el nombre
├── bizview.lock                    escrito por `bizview validate --write-lock`
├── REQUEST.md                      qué quieres, para quién y con qué filtros
└── projects/<slug>/                un proyecto BI por carpeta
    ├── project.yaml                nombre, identificador, descripción
    ├── specs/NNN-<nombre>/         spec.md (+ plan.md, tasks.md, checklists/)
    ├── integrations/<id>/          integration.yaml + queries/*.sql | requests/*.yaml
    ├── reports/<id>/               report.yaml
    ├── distributions/<id>.yaml     envíos programados (destinatarios solo por rol)
    └── assets/                     imágenes que muestra un reporte (PNG/JPEG/WebP/SVG)
```

Un **proyecto** es lo que Bizview importa, aplica y versiona. Su `slug` son letras minúsculas,
dígitos y guiones.

## 3. La petición

`REQUEST.md` es para ti y para tu IA; el producto nunca lo lee. Una página:

```md
# Panorama cripto

## Pregunta
¿Cómo está el mercado cripto en la última captura y cómo se movió en la ventana?

## Lector
El operador desde el móvil, a primera hora de la mañana.

## Decisiones
- Ranking por capitalización, los diez primeros.
- Miedo y codicia e índice altseason como dos tarjetas de cifras.
- Dinero en USD.

## Fuera de alcance
- Precios históricos más allá de la ventana.
- Datos personales: ninguna de estas fuentes tiene.
```

## 4. La especificación

Cada carpeta de proyecto lleva **specs ligeras**. `spec.md` es el único archivo obligatorio:

```md
# Mercado cripto

**Tipo**: integracion
**Status**: Approved

Carga cada 30 minutos la última captura del mercado: capitalización, volumen, dominancia,
miedo/codicia y el índice de altseason.

**Fuente**: CoinMarketCap
**Tablas**: assets, global_metrics, fear_greed, altcoin_season
```

- La línea de tipo es `**Tipo**: fuente | integracion | reporte | distribucion` (también se acepta
  `**Type**: source | integration | report | distribution`).
- `**Status**: Approved` es lo que permite que existan artefactos: sin spec aprobada, no hay
  artefacto.
- `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `quickstart.md` y `checklists/*.md` son
  opcionales en un proyecto importado. Úsalos cuando el trabajo sea lo bastante grande para
  planificarlo.
- Los números son de tres dígitos por proyecto, consecutivos y nunca se reutilizan.

## 5. Los artefactos

### Integración — `integrations/<id>/integration.yaml`

```yaml
id: mercado-cripto               # único en todo el espacio de trabajo
spec: specs/001-mercado-cripto   # la spec que lo posee, dentro de este proyecto
source: CoinMarketCap            # el nombre de la fuente en Bizview
schedule: "*/30 * * * *"         # cron, en la zona horaria de la instalación salvo que `timezone:` diga otra
datasets:
  assets:
    primary_key: [snapshot_at, symbol]
    date_column: snapshot_at
    columns:
      snapshot_at: {type: timestamptz, nullable: false}
      symbol: {type: text, nullable: false}
      price: {type: numeric}
    extract: {query: queries/assets.sql}
    incremental: {mode: full}
```

- Una instrucción de solo lectura por archivo en `queries/` (un único `SELECT` o `WITH`, sin cadenas
  con `;`).
- `incremental.mode: full` reemplaza la ventana; `incremental.mode: window` conserva lo que hay y
  añade.
- Una fuente REST/SOAP usa `requests/*.yaml` en lugar de SQL.
- Nunca una credencial y nunca una fila de datos reales en el repositorio.

### Reporte — `reports/<id>/report.yaml`

```yaml
id: panorama-cripto
spec: specs/002-panorama-cripto
title: Panorama cripto
uses:
  assets: mercado-cripto.assets
date: assets.snapshot_at
metrics:
  market_cap: {label: Capitalización, format: currency, better: higher, sql: sum(assets.market_cap)}
dimensions:
  symbol: {label: Moneda, sql: assets.symbol}
views:
  - {id: kpis, type: kpis, metrics: [market_cap]}
  - {id: tabla, type: table, dimensions: [symbol], metrics: [market_cap], limit: 10}
```

- `uses` asigna un alias local a `<id-de-integración>.<conjunto>`; `sql` lo lee como `alias.columna`.
- Una métrica puede ser `sql` o una `formula` sobre otras métricas.
- `views` es lo que ve el lector: `kpis`, `trend`, `ranking`, `table`, `gauge`, `index`, `share`,
  `asset`.
- `labels` imprime los números de forma permanente: `true` en un `bar`, `line` o `area` pone el valor
  al final de cada marca (se oculta cuando no cabe); `values`, `percent` o `both` en un `pie`/`donut`
  elige lo que imprime cada porción. Sin él, los valores aparecen al pasar el puntero o al tocar, en
  una ficha con el nombre, el valor y la participación.
- Un reporte sobre una tabla existente sin ETL declara `direct:` en lugar de `uses:` (ver
  [REPORTS.md](REPORTS.md) para el contrato de fuente directa). Cuando la fuente es
  **apta para BI** (el superusuario declaró lo que expone) una tabla no necesita lista de columnas:
  escribe `alias: esquema.objeto` y las columnas vienen de la estructura propia de la fuente,
  exactamente lo que te muestra el paquete de estructura.

  ```yaml
  direct:
    source: Almacén ventas
    tables:
      v: reporting.v_ventas_dia     # columnas leídas de la fuente
      p: reporting.dim_producto
  joins:
    - {left: v.producto_id, right: p.id}
  date: v.fecha
  materialize: none               # none | daily (daily: la cifra se guarda una vez al día)
  ```

  La declaración es toda la verdad: un objeto fuera de ella se rechaza al validar, y otra vez
  cuando el reporte se renderiza. Elige una integración en su lugar cuando el origen sea
  transaccional, cuando necesites historial, uniones entre fuentes o transformación pesada: una
  fuente apta para BI es para datos que otro proceso ya dio forma.

### Distribución — `distributions/<id>.yaml`

```yaml
id: envio-semanal
spec: specs/003-envio-semanal
report: panorama-cripto
subscriptions:
  - frequency: weekly
    weekday: 1
    hour: 7
    period: mtd
    recipients: {roles: [admin], lists: ["Gerencia comercial"]}
    attach_pdf: true
    link_days: 7
```

Los destinatarios son **roles** y **nombres de listas**, nunca direcciones: un proyecto vive en Git, y
una lista de clientes es dato personal de la instalación (constitución II). `lists:` nombra las listas
de correo creadas en **Listas de correo** — el mismo nombre puede existir como lista personal de
alguien y como compartida, y gana la compartida. Al aplicar, un nombre que no existe en la instalación
se rechaza y el mensaje lo nombra, así el proyecto sigue diciendo lo que necesita. El validador
rechaza cualquier `@` dentro de `recipients:`: *las direcciones no se permiten en una distribución;
nombra una lista*.

### Imágenes — `assets/`

Un reporte muestra imágenes de dos formas:

```yaml
images:
  coins: {folder: assets/coins, key: symbol, fallback: initial}
  logos: {column: assets.logo_url, key: symbol, fallback: initial}
```

- `folder:` lee el archivo llamado como la clave de la fila dentro del proyecto (`BTC.png`,
  `btc.jpg`, `BTC.webp`, `BTC.svg`), ≤ 300 KB cada uno y ≤ 25 MB por proyecto, y viaja en la
  exportación.
- `column:` nombra una columna cuyo valor es una URL: el worker la descarga una vez, la guarda en la
  caché de imágenes de la instalación (90 días por defecto) y reescribe el valor, así que el móvil
  del lector nunca llama al tercero.
- Sin archivo, o con `fallback: none`, la tarjeta dibuja la inicial y un color de la paleta.

## Filtrar haciendo clic (feature 063)

Cualquier marca que represente **un valor de una dimensión** filtra el tablero al pulsarla: barra,
porción, fila de ranking, celda de una columna de dimensión o tarjeta de `asset`. El filtro es el
mismo de la hoja Filtros (`filter.<dimension>=<valor>`), así que la URL, el PDF/CSV y el correo lo
conservan. Pulsar el mismo valor lo quita; Ctrl/Cmd-clic añade otro valor de la misma dimensión
(`IN`); un valor de otra dimensión añade un segundo filtro (AND). «Otros», los totales y la tendencia
no se pulsan.

```yaml
interactions:
  cross_filter: true          # por defecto; false apaga el clic en todo el reporte

layout:
  web:
    components:
      - {id: marcas, type: bar, view: marcas, category: marca}
      - {id: total, type: kpi, view: resumen, metric: ventas_netas, cross_filter: ignore}
      - {id: nota, type: text, text: "...", cross_filter: false}

dimensions:
  producto:
    label: Producto
    sql: products.name
    key: products.product_code   # filtra por el código, muestra el nombre
```

- `cross_filter: false` deja ese componente inerte.
- `cross_filter: ignore` lo mantiene fuera del cross-filter: sigue mostrando el total de la compañía.
- Una dimensión es filtrable aunque no esté en `filters:`; esa lista solo decide qué ofrece la hoja.
- Un id que no es una dimensión del reporte se rechaza con 422.

## 6. Validar

```bash
bizview validate --write-lock
```

El mismo validador que ejecuta el servidor, sobre los mismos JSON Schemas de
`cli/bizview_cli/schemas/`: por eso un proyecto que valida aquí se aplica allí. Estas son las nueve
comprobaciones que nombra el `PROMPT.md` del paquete, en el mismo orden:

- el YAML contra su esquema, y las carpetas contra el formato;
- que cada artefacto tenga una spec aprobada en su propio proyecto;
- que cada `spec:` apunte a una carpeta que existe, y que toda referencia resuelva;
- que el SQL sea una única instrucción de solo lectura, y que cada columna que un reporte usa esté
  declarada por el conjunto de datos que lee;
- identificadores únicos en todo el espacio de trabajo, números de spec, carpetas de imágenes y sus
  claves;
- que los conjuntos de `images:` existan, no estén vacíos y no sean solo SVG cuando un bloque del
  PDF los dibuja;
- que ningún conjunto de datos lleve una columna marcada como dato personal sin que la spec de la
  integración la enumere bajo `**Datos personales**:` (la misma puerta que aplica el servidor antes
  de aplicar un proyecto);
- que cada reporte declare al menos un filtro: un **aviso** aquí, porque un reporte que ya está
  corriendo sigue validando, pero el servidor no aplicará un proyecto cuyo reporte no ofrezca
  ninguno;
- que se cumplan los dos presupuestos de importación: artefactos (400 archivos, 2 MB cada uno,
  20 MB) e imágenes (2 000 archivos, 300 KB cada una, 25 MB), contados por separado para que un
  juego de logos nunca gaste lo que las specs necesitan.

`--write-lock` escribe `bizview.lock` con un hash por archivo, así que una aplicación puede probar
que nada cambió después de la validación. Un fallo se escribe en `problems.json`:

```json
[{"file": "projects/panorama/reports/panorama-cripto/report.yaml",
  "path": "/metrics/market_cap/sql",
  "code": "unknown_column",
  "message": "assets.market_cap no existe en el dataset assets",
  "fix": "usa una de: price, volume_24h"}]
```

`--live` ejecuta además cada consulta contra la fuente (solo estructura y conteos) cuando la
instalación deja que la CLI llegue a ella. La puerta propia del servidor, **Volver a comprobar**, es
la misma comprobación: una consulta o petición que no la ha pasado desde su último cambio impide
aplicar el proyecto.

## 7. Importar y aplicar

**Proyectos → Importar** toma el zip de la carpeta del proyecto. Mapea lo que encuentra, informa las
colisiones, valida otra vez y muestra el árbol antes de que se aplique nada. **Aplicar** crea una
versión compuesta con los demás proyectos aplicados y arranca el horario. Nada corre antes de eso.

Los detalles, incluidas las equivalencias de la CLI y las reglas de colisión: [IMPORT.md](IMPORT.md).

## 8. Un ejemplo resuelto

Las piezas de abajo son el proyecto `coinmarketcap`: una integración con cuatro conjuntos de datos
unidos por `snapshot_at`, y un reporte que muestra una fila de cifras, una tendencia, un ranking y
una tabla.

`specs/001-mercado-cripto/spec.md`

```md
# Mercado cripto

**Tipo**: integracion
**Status**: Approved
**Fuente**: CoinMarketCap
**Tablas**: assets, global_metrics, fear_greed, altcoin_season
```

`integrations/mercado-cripto/queries/assets.sql`

```sql
SELECT captured_at AS snapshot_at, symbol, price_usd AS price,
       market_cap_usd AS market_cap, volume_24h_usd AS volume_24h
FROM public.crypto_assets
```

`integrations/mercado-cripto/integration.yaml` — el conjunto de datos del §5 con cuatro entradas:
`assets`, `global_metrics`, `fear_greed`, `altcoin_season`, cada una con su `primary_key`, sus
`columns` y su `extract.query`.

`reports/panorama-cripto/report.yaml`

```yaml
id: panorama-cripto
spec: specs/002-panorama-cripto
title: Panorama cripto
description: Mercado de criptomonedas en la última captura
uses:
  assets: mercado-cripto.assets
  global_metrics: mercado-cripto.global_metrics
  fear_greed: mercado-cripto.fear_greed
  altseason: mercado-cripto.altcoin_season
joins:
  - {left: assets.snapshot_at, right: global_metrics.snapshot_at, type: left}
  - {left: global_metrics.snapshot_at, right: fear_greed.snapshot_at, type: left}
  - {left: fear_greed.snapshot_at, right: altseason.snapshot_at, type: left}
date: assets.snapshot_at
metrics:
  market_cap: {label: Capitalización, format: currency, sql: sum(assets.market_cap)}
  dominance: {label: Dominio de la cartera, format: percent,
              formula: market_cap / total_market_cap * 100}
  altseason_index: {label: Índice altseason, format: integer, sql: max(altseason.value)}
dimensions:
  symbol: {label: Moneda, sql: assets.symbol}
periods: {default: last_7_days, allowed: [last_7_days, last_30_days, mtd, ytd]}
views:
  - {id: kpis, type: kpis, metrics: [market_cap, dominance, altseason_index]}
  - {id: tendencia, type: trend, dimensions: [snapshot_at], metrics: [market_cap]}
  - {id: ranking, type: ranking, dimensions: [symbol], metrics: [market_cap], limit: 10}
  - {id: tabla, type: table, dimensions: [symbol], metrics: [market_cap, volume], limit: 50}
```

Luego:

```bash
bizview validate --write-lock     # problems.json vacío
```

y **Proyectos → Importar** con el zip, **Aplicar**, **Compartir**.

La propia suite de pruebas del producto mantiene este proyecto como fixture
(`backend/tests/fixtures/projects/coinmarketcap/`), así que el ejemplo no es ilustrativo: se
renderiza en cada ejecución.
