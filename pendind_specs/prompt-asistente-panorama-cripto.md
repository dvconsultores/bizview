# Prompt para el Asistente de BizView — proyecto «CoinMarketCap» desde cero

Antes de pegar: crea el proyecto `coinmarketcap` en Proyectos, abre su conversación, pon el modo
en **Auto** (si 028 ya está desplegado; si no, usa Editar y lanza los comandos uno por uno en el
orden del final). Comprueba en Administración → Fuentes de datos que la fuente REST
`coinmarketcap` existe con base `https://pro-api.coinmarketcap.com` y la cabecera
`X-CMC_PRO_API_KEY` guardada.

---

/speckit-specify Panorama cripto: un tablero de mercado sobre la fuente REST `coinmarketcap`.
Modo autónomo: decide lo que falte, anótalo en la spec bajo «Decisiones tomadas» y no me preguntes.

## Resultado esperado

Dos specs en este proyecto, en este orden, y nada más:

1. `001-mercado-cripto` — **integración** que toma instantáneas de la API cada 30 minutos.
2. `002-panorama-cripto` — **reporte** sobre esa integración.

Al terminar la 001 continúa con la 002 sin detenerte (cambia la spec actual tú mismo). Termina
cuando el proyecto esté «Listo para aplicar» con vista previa correcta; no me pidas que
seleccione specs ni que pulse botones intermedios.

## Integración 001-mercado-cripto

Fuente: `coinmarketcap` (REST). Comprueba cada petición con `check_request`/`describe_source`
antes de escribirla; usa los nombres de campo reales que devuelva la API, no los supongas.

Peticiones (GET, rutas relativas a la base de la fuente):

- `listings`: `/v1/cryptocurrency/listings/latest?limit=100&convert=USD`
- `global`: `/v1/global-metrics/quotes/latest?convert=USD`
- `fear_greed`: `/v3/fear-and-greed/latest`

Datasets (todos con la columna `snapshot_at` = hora de la toma, misma para los tres en cada
corrida; es la clave de unión):

- `assets`: una fila por activo de `listings` — `cmc_id` (el `id` numérico de la API), `rank`,
  `symbol`, `name`, `price_usd`, `percent_change_24h`, `percent_change_7d`,
  `percent_change_90d`, `market_cap_usd`, `tags` (lista), `logo_url` =
  `https://s2.coinmarketcap.com/static/img/coins/64x64/<cmc_id>.png` (URL pública, sin clave) y
  `snapshot_at`.
- `global_metrics`: una fila por toma — `btc_dominance`, `eth_dominance`, `total_market_cap_usd`,
  `total_volume_24h_usd`, y si la API los trae en este plan, `open_interest_usd`,
  `open_interest_perpetuals_usd`, `open_interest_futures_usd`; `snapshot_at`.
- `fear_greed`: una fila por toma — `value` (0–100), `classification`, `snapshot_at`.
- `altcoin_season`: una fila por toma, **calculada** en la integración a partir de `assets`:
  excluye activos con tags `stablecoin` o `wrapped-tokens`, toma los 100 primeros por
  capitalización, y `index` = porcentaje de ellos cuyo `percent_change_90d` supera al de BTC;
  `label` = «Altcoin season» si ≥ 75, «Bitcoin season» si ≤ 25, «Neutral» entre medias;
  `snapshot_at`.

Carga: completa en cada corrida (sin ventana incremental), **se conservan las tomas** (no se
borran), clave de idempotencia `snapshot_at` + clave natural de cada dataset; retención 30 días.
Horario: cada 30 minutos (`*/30 * * * *`). Presupuesto: 3 peticiones por corrida ≈ 4.300 llamadas
al mes; no subas la frecuencia. Checks: `assets` ≥ 50 filas por toma; `fear_greed.value` entre 0
y 100; `btc_dominance` entre 0 y 100. Sin datos personales en ningún dataset.

## Reporte 002-panorama-cripto

`uses` los cuatro datasets de 001 **con joins explícitos** por `snapshot_at` (declara los
`joins` desde el principio; la validación falla si faltan). Fecha del reporte: `snapshot_at`.
Período por defecto: última toma («ahora»); comparación: toma de hace 24 h. **Sin tablas de
ningún tipo y sin gráficos de serie**: el tablero es solo una cuadrícula de mosaicos grandes,
pensada para mirarse de un vistazo (y en Modo TV).

Métricas y dimensiones mínimas: `price_usd`, `percent_change_24h`, `market_cap_usd` por `symbol`;
`fear_greed_value`, `fear_greed_label`; `altcoin_index`, `altcoin_label`; `btc_dominance`,
`eth_dominance`, `others_dominance` (= 100 − btc − eth); `open_interest_usd` y sus dos
componentes (ocultos si el dataset no los trae).

Layout web (`layout.web`), en este orden:

1. **Cuadrícula de 8 mosaicos de activo** (componente `asset`), 4 por fila en escritorio y 2 por
   fila en teléfono, mosaicos cuadrados o casi (relación 4:3), sin encabezados de columna ni
   filas: los 8 primeros de `assets` por `market_cap_usd` excluyendo `stablecoin` y
   `wrapped-tokens`. Cada mosaico, de arriba abajo: **logo de la moneda** (`logo_url`, 40 px,
   redondo, con el símbolo como texto alternativo y un círculo con la inicial si la imagen no
   carga), `symbol` en grande y `name` en pequeño; `price_usd` como cifra protagonista (tamaño
   display, 2 decimales, separador de miles); `percent_change_24h` como insignia rellena verde o
   roja con flecha ▲/▼; y una mini-línea de 7 días (`sparkline: true`) construida con las tomas
   guardadas, coloreada según el signo del cambio de 7 días; si no se puede construir, omítela sin
   dejar hueco.
2. **Fila de 4 mosaicos de indicador**, del mismo alto:
   - **Fear & Greed**: componente `gauge` tipo **termómetro semicircular** (medidor de arco con
     aguja), bandas de color de rojo (0, miedo extremo) a verde (100, codicia extrema), el valor
     en grande en el centro y la etiqueta debajo («Miedo extremo / Miedo / Neutral / Codicia /
     Codicia extrema»).
   - **Altcoin Season**: componente `index`, barra horizontal 0–100 con marcador y los dos
     extremos rotulados «Bitcoin season» y «Altcoin season», valor en grande.
   - **Dominancia de Bitcoin**: componente `share`, tres cifras grandes (BTC %, ETH %, Otros %)
     con sus puntos de color y una barra apilada debajo.
   - **Open interest**: componente `value`, total en grande y debajo perpetuos / futuros; mosaico
     oculto si el dataset no trae el dato.

Estilo: alto impacto visual para usuarios no técnicos — cifras grandes, insignias rellenas,
mucho contraste entre tarjeta y fondo en modo oscuro, iconos/logos siempre visibles, nada de
texto pequeño salvo las etiquetas. Debe leerse bien a 375 px y en Modo TV a 3 m de distancia.

Bajo el título: «Datos actualizados <snapshot_at>»; aviso de datos obsoletos si la última toma
tiene más de 1 hora o la última corrida falló.

Layout PDF (`layout.pdf`): una página horizontal, encabezado con título y hora de la toma, los
mismos 12 mosaicos (logos incluidos si el renderizador puede descargarlos; si no, la inicial en
círculo), pie con fecha de generación. Paleta: la de la instalación (`impacto` si
existe). Títulos y etiquetas en español e inglés (`title_en`, `label_en`).

## Reglas

- No inventes campos: lo que la API no devuelva en este plan se omite y se anota en la spec.
- Un solo id por artefacto: `mercado-cripto` (integración) y `panorama-cripto` (reporte).
- Ejecuta en orden para cada spec: clarify → plan → tasks → implement → converge, valida, haz la
  vista previa, corrige lo que falle con los arreglos deterministas cuando existan, y para solo
  en «Listo para aplicar». Yo pulso Aplicar.

---

Si el modo Auto no está disponible todavía, lanza en este orden y pega el bloque de arriba como
argumento del primero: `/speckit-specify …` → `/speckit-plan 001-mercado-cripto` →
`/speckit-tasks 001-mercado-cripto` → `/speckit-implement 001-mercado-cripto` →
`/speckit-converge 001-mercado-cripto` → `/speckit-plan 002-panorama-cripto` →
`/speckit-tasks 002-panorama-cripto` → `/speckit-implement 002-panorama-cripto` →
`/speckit-converge 002-panorama-cripto` → vista previa → Aplicar.
