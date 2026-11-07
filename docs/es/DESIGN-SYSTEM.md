🇪🇸 Español · 🇬🇧 [English](../DESIGN-SYSTEM.md)

# El sistema de diseño de BizView

Un solo lugar para las reglas que sigue cada pantalla. Existe porque cuatro pantallas no las seguían:
la biblioteca de temas se sentaba en una columna de 56 rem sobre una pantalla de 96 rem, las opciones
de apariencia se apilaban porque una lista de clases había perdido `grid`, y Ayuda no tenía un panel
acotado, así que la página se desplazaba en lugar del artículo.

Las reglas viven en el código como tokens (`frontend/src/lib/layout.ts`) y aquí en prosa. Una página
las compone; no responde por su cuenta una pregunta compartida.

**Mobile first.** Los estilos base son los del teléfono. Las mejoras vienen solo de las variantes de
`min-width` (`sm:`, `md:`, `lg:`, `xl:`) — nunca de un diseño de escritorio comprimido hacia abajo.

## Tokens

| Token | Valor | Qué decide |
|---|---|---|
| `APP_CONTAINER` | `mx-auto w-full max-w-screen-2xl` | la única anchura de contenido (96 rem) |
| `APP_GUTTER` | `px-4 sm:px-5 lg:px-4` | 16 → 20 → 16 px de relleno lateral |
| `APP_PAGE` | contenedor + gutter | la raíz de una página usa esto y nada más |
| `PAGE_STACK` | `space-y-4 sm:space-y-5` | el ritmo entre las secciones de una página |
| `CARD_PAD` | `p-4 sm:p-5` | el relleno interno de una tarjeta |
| `PANEL_MAX_H` | `lg:max-h-[calc(100dvh-var(--app-chrome,15rem))]` | el límite de un panel dividido — un `max-height`, nunca una altura fija |
| `PANEL_SCROLL` | `min-h-0 overflow-y-auto` | lo que hace que un hijo de la rejilla se desplace en lugar de estirar la página |
| `SPLIT_COLS` | `lg:grid lg:grid-cols-[minmax(18rem,24rem)_minmax(0,1fr)] lg:gap-6` | navegación + panel de lectura |
| `CARD_GRID_2` / `CARD_GRID_3` | 1 columna → 2 → 3 | las únicas progresiones de columnas del producto |

Los colores son tokens del tema (`text-ink`, `bg-surface`, `border-line`, `ring-focus`, `text-accent`,
`bg-chrome-gradient`, `text-on-chrome`, …), nunca literales: `tests/unit/no-raw-colors.test.ts` falla
la pantalla que fija uno, y cada tema instalado (047, 051) debe seguir funcionando.

La geometría también es un token (funcionalidad 051): `rounded-card`, `rounded-btn`, `rounded-field`,
`shadow-card`, `shadow-raised`, `card-surface` (ancho de borde) y `nav-active` vienen del bloque
`shape` del tema de la instalación, así que el mismo componente responde correctamente a Clásico,
Impacto, Elegante y Contraste sin una rama por tema. Una superficie nueva usa estos nombres, nunca un
valor en píxeles propio.

## Las reglas

### Una página
- Clase raíz: `APP_PAGE` más `PAGE_STACK`. **Sin `max-w-*` propia** — una columna estrecha dentro del
  contenedor es el defecto por el que existe este documento.
- Un `<h1>`; las secciones `<h2>`, las subsecciones `<h3>`, en orden.
- Sin desbordamiento horizontal a 320 px; alineada al mismo contenedor a 1920 px.

### Una tarjeta
- `Card` + `CARD_PAD`. El contenido se apila; las alturas iguales vienen de la rejilla (`h-full`), no
  del relleno. Nada de relleno para que una fila cuadre.

### Una cabecera de página
- `PageHeader`: un `<h1>` (compacto), un subtítulo opcional de una línea, las acciones en una fila que
  se envuelve — al lado del título desde `sm`, debajo en un teléfono. No debe comerse un quinto de un
  viewport de 375 × 740.

### Una elección (control segmentado)
- `SegmentedControl`. Su contenedor es **siempre** una rejilla con `grid-cols-N`; las opciones son
  hermanas.
- `radiogroup` + `radio` fuera de un menú, `group` + `menuitemradio` dentro de uno.
- Exactamente un `aria-checked`; una parada de tabulación; las flechas mueven y seleccionan.
- A 320 px las opciones siguen compartiendo la fila: se encogen, nunca envuelven la página.

### Un panel dividido (Ayuda)
- Padre: `SPLIT_COLS` + `PANEL_MAX_H`. Hijos: `PANEL_SCROLL`.
- Por debajo de `lg`: una columna, la lista primero, un Volver explícito (`aria-label` nombra el
  destino).
- Conserva la búsqueda y la posición de desplazamiento durante el viaje.

### Retroalimentación
- Cargando: `Spinner` con una etiqueta `sr-only`. Vacío: `EmptyState`. Error: `Alert tone="error"` con
  un reintento donde el reintento tenga sentido. Deshabilitado: los estilos compartidos `disabled:`,
  nunca un `opacity` pelado.

## Viewports para los que diseñamos y probamos

| Anchura | Qué es | Qué debe cumplirse |
|---|---|---|
| 320 px | la más estrecha admitida | sin desbordamiento horizontal, los controles comparten su fila |
| 375 px | teléfono de referencia | una columna, la barra inferior nunca tapa contenido |
| 768 px | tableta | dos columnas donde el contenido lo permita |
| 1024 px | portátil | aparecen los paneles divididos |
| 1440 px | escritorio | tres columnas; el contenedor se aprovecha |
| 1920 px | ancho | el contenedor se centra, no se estira |

El zoom del navegador al 200 % es una anchura de la mitad de la ventana: todo lo anterior debe
cumplirse en ese tamaño efectivo.

## Guardas

`frontend/tests/unit/design-guards.test.ts` lee el código fuente y verifica propiedades, no capturas
de pantalla:

- ninguna raíz de página declara un `max-w-*` estrecho;
- los conmutadores de tema e idioma no contienen `grid-cols-*` propios (delegan);
- el control segmentado siempre renderiza una rejilla;
- Ayuda usa los tokens acotados del panel dividido;
- el módulo de tokens exporta el vocabulario y está pensado primero para el móvil.

`tests/unit/no-raw-colors.test.ts` (006) mantiene los colores en tokens.

La funcionalidad 051 añade las guardas de tema: `theme-derive.test.ts` demuestra que el cromo de
Clásico sigue coincidiendo con los literales que `index.css` llevaba antes, que cada uno de los seis
temas × dos modos es legible, y que las cuatro identidades oficiales difieren en al menos cuatro
dimensiones y nunca solo en el color.

Una comparación de capturas de pantalla fallaría con una actualización de tipografía y pasaría con una
regresión estructural; una comprobación de propiedades hace lo contrario, y por eso las guardas están
escritas así.
