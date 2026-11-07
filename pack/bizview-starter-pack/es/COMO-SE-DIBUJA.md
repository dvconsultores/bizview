# Qué hace BizView con tu `report.yaml`

Cuando aplicas el proyecto, BizView no convierte tu YAML en código: lo ejecuta. Este documento
cuenta **qué hace con cada archivo que escribiste**, del aplicar al tablero que ve el lector. Léelo
antes de decidir períodos, comparaciones o un `layout`, porque cada clave termina en una consulta o
en una tarjeta.

## 1. Aplicar: el YAML entra en una versión

La importación guarda el zip como **borrador**; **Aplicar** lo valida otra vez con el mismo
validador que usa `bizview validate` y lo compone con los demás proyectos en una nueva **versión**
de la instalación. Cada `reports/<id>/report.yaml` se vuelve una fila de tablero (`available`) y su
`access.roles` empieza a decidir quién lo abre. Una versión activa no cambia: por eso todo lo demás
puede cachear contra ella. **Volver a la versión anterior** deshace todo, permisos incluidos.

## 2. Contexto: los alias se vuelven tablas

`uses` no son nombres libres. Cada alias se resuelve a `ds_<integración>.<conjunto>` y los tipos de
columna salen del contrato de la integración, así que una columna que no existe se detecta antes de
construir SQL. `date` marca la columna del rango y el alias base de los `joins`. Todavía no corrió
nada.

## 3. Petición: período, comparación, filtros

La pantalla pide los datos con lo que está en la URL:

```text
period=mtd&compare=previous_period&filter.<dimensión>=<valor>
```

Solo se aceptan los presets de `periods.allowed` y las comparaciones de `compare.allowed`. El preset
se convierte en dos fechas inclusivas de la zona horaria de la instalación, no del navegador. El
**hash de la selección** más la **última carga exitosa** de las integraciones forman la clave de
caché: si nada cambió, la respuesta llega sin recalcular.

## 4. Las vistas se vuelven SQL

Cada vista es **una agregación por período**: FROM con los alias y sus joins, WHERE con el rango de
fechas y los filtros, SELECT con el fragmento `sql` de cada métrica, y el GROUP BY / ORDER BY /
LIMIT que pide el tipo de vista. Las `formula` se calculan después, sobre los agregados; una base
cero da nulo, no un error.

La comparación es una **segunda corrida** sobre el rango anterior, emparejada por clave; de ahí
salen `previous` y `change`. Con `materialize: daily` se lee el resumen diario en vez del conjunto
—más rápido y sin tocar la fuente— y la tarjeta dice de qué día son las cifras.

Una vista que falla es **solo esa tarjeta**: las demás se dibujan. Una vista vacía lo dice en lugar
de verse rota.

## 5. Dibujar: layout, tarjetas, formatos

Con `layout.web`, cada componente se ata a una vista **por id** (`view`), y `metric`, `x`/`series`,
`category`/`value` eligen qué lee. La rejilla es de 12 columnas y `span` decide cuántas toma. Sin
layout, se dibuja una tarjeta por vista en el orden del payload.

Los números se formatean en el navegador con `format:` y la moneda de la instalación; el PDF usa las
mismas reglas sobre el mismo payload, así que papel y pantalla coinciden.

## 6. Frescura: cuándo cambian los números

| Lo que ves | Qué pasó |
|---|---|
| "Datos actualizados …" | la última carga exitosa de las integraciones que lee |
| la página se refrescó sola | el auto-refresco encontró otra versión de datos |
| cifras de ayer, con etiqueta | `materialize: daily` leyó la foto de ese día |
| aviso de datos viejos | un reporte directo no llegó a su fuente |

## Qué controla cada clave

| Clave | Qué decide |
|---|---|
| `date` | la columna del rango y el alias base de los joins |
| `periods` | qué presets se aceptan y con cuál abre |
| `compare` | si corre un segundo rango, y cuál |
| `filters` | qué `filter.<dimensión>` se leen y el `IN` |
| `metrics.sql` / `metrics.formula` | qué se agrega y qué se calcula después |
| `views.limit` | cuántas filas devuelve un ranking o una tabla |
| `layout.web.span` | cuántas de las doce columnas toma la tarjeta |
| `materialize` | si se lee el resumen diario o el conjunto |
| `access` | quién puede abrir el tablero |

## Dónde mirar cuando no dibuja

- **"Sin datos"**: el rango está vacío para esa vista; el mensaje nombra los conjuntos vacíos cuando
  no hay ninguno con filas.
- **Una tarjeta con un código y una referencia**: esa vista falló; la referencia la ata a las líneas
  del registro del servidor.
- **El tablero no se parece al YAML**: la validación rebajó parte del layout; las notas sobre la
  rejilla dicen qué componente y por qué.
- **Los números están viejos**: mira la última corrida de la integración.

La versión completa, con el código detrás de cada paso, está en `docs/RENDERING.md` del producto y en
la ayuda de la app (**Crear con tu IA → Cómo se dibuja un tablero**).

## Relacionados

- `QUE-HACE-BIZVIEW.md` — qué pasa al importar y al aplicar.
- `CONTENIDO.md` — qué es cada archivo del zip.
- `PROMPT.md` — las reglas que tu IA debe cumplir.
