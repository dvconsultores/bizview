🇪🇸 Español · 🇬🇧 [English](../THEMES.md)

# Temas

Un tema es un **archivo de datos**: colores y unas pocas decisiones de forma. Nunca CSS, nunca una
tipografía, nunca marcado. Cualquiera — una persona o cualquier IA — lo escribe fuera de Bizview, y
solo entra cuando lo acepta el mismo validador de `cli/bizview_cli/theme.py`, ya se suba desde
Apariencia o llegue dentro de un proyecto.

Un tema pinta los gráficos, las tarjetas de KPI y el PDF **y** — desde la funcionalidad 051 — la
propia aplicación: la banda de la cabecera, la barra lateral, el fondo de la página, las tarjetas,
los botones, los campos, las tablas, los diálogos y la navegación inferior. Ningún componente nombra
un color; una sola derivación convierte el tema en los tokens semánticos con los que ya pinta cada
pantalla.

El contrato publicado es [`cli/bizview_cli/schemas/theme.schema.json`](../../cli/bizview_cli/schemas/theme.schema.json);
la página que lee quien escribe un tema (o una IA) es `THEME.md` dentro del paquete de autoría.

## El archivo

```yaml
id: acme-azul                 # ^[a-z][a-z0-9-]{1,39}$, único por instalación
name: "Acme · azul"
name_en: "Acme · blue"
version: 1
strategy: categorical         # categorical | sequential
light:
  surface: "#FFFFFF"          # fondo de la página
  card: "#F8FAFC"             # fondo de la tarjeta
  text: "#0F172A"             # texto principal
  muted: "#64748B"            # texto secundario y etiquetas de los ejes
  grid: "#E2E8F0"             # líneas de la rejilla
  primary: "#0B5FFF"          # acento de la interfaz
  positive: "#16A34A"
  negative: "#DC2626"
  neutral: "#64748B"
  delta_positive: "#BBF7D0"   # fondo de la insignia de subida
  delta_negative: "#FECDD3"   # fondo de la insignia de bajada
  series: ["#0B5FFF", "#F59E0B", "#10B981", "#8B5CF6", "#EF4444", "#06B6D4", "#F97316", "#84CC16"]
  # opcional, funcionalidad 051: el cromo propio de la aplicación
  canvas: "#F7FAFF"           # fondo de la página detrás de las tarjetas
  chrome: "#0B5FFF"           # la banda de la cabecera y de la barra lateral
  chrome_text: "#FFFFFF"      # la tinta sobre esa banda
  field: "#F3F7FF"            # superficies de los campos
  line: "#DCE4F0"             # bordes
  accent: "#0B5FFF"           # enlaces, estados seleccionados, la barra inferior
  warning: "#B45309"
dark:
  … las mismas claves, sobre la superficie oscura …
shape:                        # todo opcional, cada valor de una lista cerrada
  radius: md                  # sm | md | lg
  density: normal             # compact | normal
  kpi_scale: lg               # md | lg | xl
  font: sans                  # sans | serif | mono
  badge: filled               # filled | outline
  elevation: soft             # flat | soft | strong
  button: rounded             # rounded | pill | square
  nav: gradient               # gradient | solid | bar | outline
  divider: soft               # soft | strong
  heading: normal             # normal | tight
  card_border: hairline       # none | hairline | strong
app:                          # opcional: fija cualquier token de cromo exacto, por modo
  light: { canvas: "#F4F7FA", ink: "#0F172A", primary: "#3A7393", … }
  dark: { … }
```

`light` y `dark` son obligatorios, con todos los tokens de **reporte**: el producto pinta en ambos
modos y un token ausente sería un hueco en uno de ellos. Los siete tokens de cromo son opcionales —
un tema escrito antes de la 051 no declara ninguno y la web los deriva de su paleta, así que una
subida antigua tematiza toda la aplicación en lugar de solo los gráficos. `series` lleva de 3 a 8
colores; cuando lleva menos de ocho, el último se repite, así que un tema de tres colores sigue
llenando un gráfico de ocho barras. Los tokens de `shape` se traducen a las propiedades
personalizadas que leen los componentes (`--radius-card`, `--radius-button`, `--shadow-card`,
`--card-border`, `--nav-mark`, `--heading-weight`, `--kpi-numeral*`, …), y ningún componente guarda
un color literal.

## Las reglas que se comprueban

El validador mide; no opina. Un tema se rechaza cuando:

| Regla | Valor |
|---|---|
| Claves | solo las de arriba; cualquier otra se rechaza (un tema es datos, no CSS) |
| Colores | `#RRGGBB`, sin alfa; `series` con 3 a 8 entradas |
| Tamaño | 20 KB como máximo |
| `text` sobre `surface` | contraste ≥ 4.5:1 |
| `primary` sobre `surface` | ≥ 3:1 |
| Cada serie sobre `surface` | ≥ 3:1 |
| Series adyacentes | ΔE ≥ 10 (un tema `sequential` se comprueba con pasos de luminosidad ≥ 5) |
| `positive` frente a `negative` | ΔE ≥ 25, para que nunca se confundan |
| `grid` sobre `surface` | < 1.8:1, para que la rejilla nunca compita con los datos |
| `chrome_text` sobre `chrome` | ≥ 4.5:1 (solo cuando el tema los declara) |
| `text` sobre `field`, `text` sobre `canvas` | ≥ 4.5:1 |
| `accent` sobre `surface` | ≥ 3:1 |
| cualquier token en `app` | debe ser un token de cromo conocido, y se comprueban los pares que completa |

Los dos modos se comprueban, cada uno contra su propia superficie. Cada rechazo nombra el par de
tokens y la medición, porque eso es lo que quien escribe puede corregir:
`light.text vs light.surface: 3.9:1 (needs 4.5:1)`.

Los seis temas que el producto incluye obedecen las mismas reglas, y la puerta de CI los vuelve a
comprobar: un cambio en un tema integrado que rompa su propio contrato hace fallar la compilación.

## Autoría, sin conexión

```sh
bizview theme validate themes/acme-azul.yaml        # 0 válido · 1 problemas · 2 ilegible
bizview theme preview themes/acme-azul.yaml --out preview.svg
```

`preview.svg` dibuja la misma tarjeta que dibuja Apariencia — un KPI con su insignia de delta, cuatro
barras y un minigráfico de dos series — en claro y en oscuro, con los colores del tema. Es SVG y no
PNG a propósito: rasterizar necesitaría un navegador sin interfaz o una biblioteca de imágenes, y
ninguna de las dos es dependencia de este proyecto (investigación R11).

`THEME.md` en el paquete de autoría tiene una página de instrucciones para entregar a una IA: genera
el YAML, respeta las claves, mantén el contraste y entrega solo el archivo.

## Dónde viven los temas

| Puerta | Qué ocurre |
|---|---|
| **Apariencia → Subir tema** | se valida y se guarda con `origin = upload`; un id existente pregunta antes de reemplazar y sube `version` |
| **El `themes/<id>.yaml` de un proyecto** | se valida al importar, se guarda con `origin = project` y el id del proyecto; sale de la biblioteca cuando se elimina el proyecto |
| **Los seis del propio producto** | los siembra la migración y se refrescan desde los archivos incluidos al arrancar; no se pueden reemplazar ni eliminar |

Un tema que un reporte nombra no se puede eliminar: el rechazo enumera los reportes. En Apariencia
cada tema muestra una vista previa clara y otra oscura **de su propio cromo** — la banda incluida —,
su identidad en una línea, su origen y su versión, y ofrece aplicar, descargar (el archivo tal como
se escribió), duplicar (como punto de partida de una edición) y eliminar. Las cuatro **identidades**
van primero (`clasico`, `impacto`, `elegante`, `contraste`); todo lo demás que la instalación aún
puede usar — Daltónico, Monocromo, una subida, el tema de un proyecto — viene después, en
**Compatibilidad**, y se aplica exactamente igual.

## Las cuatro identidades

| Tema | Identidad | Qué lo hace distinto |
|---|---|---|
| `clasico` | el aspecto propio del producto, sin cambios | banda verde azulado acero, elevación suave, navegación con degradado, tarjetas de 1.25 rem |
| `impacto` | Modern Executive | azul real y cian, lienzo azul pálido, escala de KPI grande, elevación fuerte, botones tipo píldora, navegación sólida |
| `elegante` | Premium Professional | lienzo crema cálido, banda grafito, acento bronce, elevación plana, tarjetas de línea fina, navegación de barra izquierda |
| `contraste` | Precision High Contrast | lienzo blanco, banda casi negra, acento dorado, bordes y separadores de 2 px, sin sombras, navegación con contorno |

## Aplicar un tema

Una persona con superusuario pulsa **Usar en la instalación**. Eso es una sola petición,
`PUT /api/admin/settings/theme` (solo superusuario, auditada como `theme_applied`). Cuando responde,
la página vuelve a leer `GET /api/config` y toda la aplicación se repinta — **sin recargar, sin cerrar
sesión**. Un rechazo no repinta nada e informa por qué.

El tema también se escribe en el dispositivo (`bizview.theme.tokens`) y `public/theme-init.js` lo
reproduce antes del primer pintado, así que una recarga nunca destella el tema anterior; `/api/config`
lo reconcilia después. La preferencia Sistema/Claro/Oscuro de quien usa el producto es una dimensión
aparte: cambiar el tema de la instalación nunca la reescribe, y cambiarla nunca cambia el tema.

## Qué garantiza la derivación

`frontend/src/theme/derive.ts` escribe cada `--c-*` con el que pinta el cromo y las variables de
geometría, a partir del tema y de nada más. Dos propiedades se imponen en lugar de esperarse:

- un **acento** se desplaza a lo largo de su propia luminosidad hasta que se lee a 4.5:1 sobre la
  superficie *y* sobre su propio fondo matizado, así que un tono pálido sigue sirviendo como enlace o
  como estado seleccionado;
- **`ink-soft`** — la etiqueta atenuada que usan el pie y la barra inferior — es el tono más claro de
  la tinta atenuada del tema que alcanza 4.5:1 tanto sobre la superficie como sobre el lienzo.

Ambas se comprueban para los seis temas × dos modos en `frontend/tests/unit/theme-derive.test.ts`, y
con axe en el navegador (`frontend/tests/e2e/theme-application.spec.ts`). Clásico además fija todo su
cromo en `app`, y esa prueba lo compara token por token con los literales que `index.css` llevaba
antes de la 051, así que la apariencia que la instalación tiene hoy no puede desviarse.

## Por reporte

```yaml
layout:
  theme:
    id: acme-azul     # cualquier tema de la instalación
    mode: auto        # auto | light | dark
```

La resolución es reporte → instalación → `impacto`, hecha una vez por página, a las propiedades
personalizadas que leen los componentes. `mode: dark` oscurece el área propia del reporte mientras el
cromo de la aplicación queda como lo eligió quien mira; una acción de sol/luna sobre el reporte lo
anula para esa sesión, y un enlace compartido se abre primero en el modo propio del reporte. El PDF
usa siempre la variante clara del tema.

`palette:` es el alias obsoleto de `id`, aceptado durante una versión para que un reporte escrito
antes de que los temas tuvieran id siga aplicándose.

## Dónde mirar en el código

| Asunto | Archivo |
|---|---|
| El contrato | `cli/bizview_cli/schemas/theme.schema.json` |
| El validador y la derivación | `cli/bizview_cli/theme.py` |
| La vista previa sin conexión | `cli/bizview_cli/theme_preview.py` |
| Los integrados (web + el espejo idéntico byte a byte del PDF) | `frontend/src/theme/themes/`, `backend/app/reports/themes/` |
| La derivación web (cromo + geometría) | `frontend/src/theme/derive.ts` |
| La escritura de las variables y la caché del dispositivo | `frontend/src/theme/palette.ts`, `frontend/public/theme-init.js` |
| La biblioteca | `backend/app/services/themes.py`, `backend/app/api/themes.py` |
| La página | `frontend/src/pages/admin/Appearance.tsx` |
| El área propia del reporte y su modo | `frontend/src/components/report/ReportArea.tsx` |
