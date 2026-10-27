# Errores al pintar un tablero

Un reporte puede fallar **después** de validar: la vista previa que ya no existe, un conjunto que
desapareció, una unión que no se puede construir, una métrica que divide entre cero, un bloque que el
PDF no sabe dibujar. Antes todo eso terminaba en «Ocurrió un error inesperado (referencia …)», que no
dice nada y no se puede accionar. Ahora cada fallo tiene un **código** y **la pieza que falló**.

Nació de un incidente real (2026-10-26, proyecto `coinmarketcap`, versión 22 recién aplicada): la
sección **Vista previa** seguía ofreciendo `panorama-cripto` cuando la aplicación ya había borrado los
esquemas de la vista previa, así que al pulsarlo la consulta apuntaba a tablas inexistentes.

## Dónde se ve

- **Una tarjeta por pieza**: la tarjeta que no puede pintarse muestra el mensaje y, en «Detalles
  técnicos», el código, la referencia, el reporte y los identificadores que fallaron (conjunto,
  columna, uniones y clave, métrica, vista, componente, bloque, motivo). El resto del tablero sigue
  pintándose, y el PDF también.
- **Un estado, no un fallo**: un período sin datos pinta «Sin datos» y en los detalles aparece
  `empty_dataset` con los conjuntos que no tienen filas.
- **El enlace del registro**: la tarjeta trae el comando que encuentra la línea del servidor, con la
  misma referencia que se registró al construir la respuesta:
  `docker logs --tail 500 bizview-backend | grep -n "<referencia>" -A 60`.

## Códigos

| Código | Qué significa | Qué hacer |
|---|---|---|
| `preview_expired` | La vista previa ya no existe: se aplicó la versión (los esquemas se borraron) o pasó la limpieza. | Vuelve a ejecutar la vista previa. Si ya aplicaste, abre el tablero publicado (`/r/<id>`): la página deja de ofrecer los enlaces de vista previa y dice qué versión la reemplazó. |
| `dataset_missing` | Falta el conjunto (su tabla o una columna que el reporte usa). | Revisa la integración: el dataset y la columna viajan en la tarjeta. Vuelve a ejecutar la integración si la tabla se perdió. |
| `join_failed` | No se pudo unir los conjuntos: falta declarar la unión, dos uniones repiten los mismos conjuntos o la columna es ambigua. | Declara `joins` entre todos los conjuntos que el reporte usa, por la columna que comparten (por ejemplo `assets.snapshot_at = altseason.snapshot_at`). La validación lo marca como `unjoined_sets`. |
| `empty_dataset` | El período no tiene filas (o el conjunto no tiene ninguna). | No es un error de código: revisa la ventana del período y la carga de la integración. La tarjeta dice «Sin datos». |
| `metric_error` | La métrica no se pudo calcular: división entre cero, un valor que no entra en el tipo o una expresión inválida. | Protege la división en el spec (`nullif`/`case`) o corrige el tipo de la columna. Solo esa métrica falla: el resto de la fila y del tablero se pinta. |
| `format_unknown` | El `format` de una métrica no está en el catálogo (`number`, `integer`, `currency`, `percent`, `text`). | Cambia el `format` en `report.yaml`. La tarjeta nombra la métrica y el formato. |
| `layout_component_unknown` | Un componente de `layout.web` o un bloque de `layout.pdf` usa un tipo fuera del catálogo. | Usa un tipo del catálogo (026) o quita el componente. En el PDF el bloque se sustituye por su tarjeta; en la web, por la tarjeta del componente. |
| `pdf_render` | ReportLab no pudo dibujar un bloque del PDF. | El bloque y su tipo viajan en la tarjeta; el resto del documento se genera. El registro del servidor tiene la traza con la misma referencia. |

## Vista previa y versión aplicada

- Al **aplicar** un proyecto, su vista previa pasa a `replaced` con la versión aplicada: la página
  ya no ofrece los enlaces y muestra «Vista previa reemplazada por la versión N» junto al tablero
  publicado.
- Si los esquemas de la vista previa desaparecieron sin aplicar (limpieza de 24 h), la primera
  lectura responde `preview_expired` y **retira** la vista previa: los enlaces dejan de aparecer
  solos.
- Ninguna de las dos respuestas es un 500: siempre hay código, mensaje y referencia.

## Qué no se registra

Nunca viaja un valor de fila, ni en la tarjeta ni en el registro. El detalle se arma con
identificadores y motivos fijos (`division_by_zero`, `invalid_value`, `numeric_overflow`,
`ambiguous`, `disconnected`, `unjoined`, `repeated`), porque el texto de PostgreSQL puede citar el
valor que rompió una conversión.
