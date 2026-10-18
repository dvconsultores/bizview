# Definir un reporte

## Para qué sirve

Explica qué lleva `reports/<id>/report.yaml`, el archivo que define un tablero: de dónde lee,
qué mide y cómo se ve.

## Quién puede usarlo

Solo el **Superusuario**; normalmente lo escribe el agente con `/speckit-implement`.

## Cómo se hace

Campos:

- `title` y `description` (y opcionales `title_en`, `description_en` para inglés).
- Datos: `uses` (alias de datasets de integraciones) o `direct` (fuente y tablas de un reporte
  directo, con `cache_seconds`). La spec lo dice en su línea `**Modo**:`.
- `date`: la columna de fecha que usan los períodos.
- `metrics`: cada métrica con su `sql` exacto o una `formula` de otras métricas, su formato y si
  es mejor más alto o más bajo.
- `dimensions`: los campos para agrupar y filtrar.
- `views`: `kpis`, `trend`, `ranking` y `table`; cada vista puede declarar un `id`.
- `filters`, `periods` y `compare`: los controles del tablero y sus valores por defecto.
- `access`: los roles que lo ven.
- `pdf`: `enabled`, que habilita la exportación; `layout.pdf` define orientación y vistas.
- `layout` (opcional): `web` y `pdf`, la composición del tablero y del PDF; sin él nada cambia.
- `ai_narrative` (opcional): el resumen con IA a partir de totales.

El layout:

- `layout.web`: `gutter` (`sm`, `md` por defecto, o `lg`) y `components` (al menos uno). Cada
  componente lleva un `id` único y un `span` de 1 a 12 columnas de la rejilla de 12 del
  escritorio (12 por defecto); en el móvil se apilan en el mismo orden, que es el orden de
  lectura. Sin `layout.web` el tablero se compone solo.
- `layout.pdf`: `page` (`size` `a4` o `letter`, `orientation` `portrait` o `landscape`, y
  `margins` de 5 a 40 mm), `overflow` y `blocks`. `overflow: continue` sigue la tabla en la página
  siguiente con su cabecera; `overflow: truncate` la corta e imprime «y N más». Sin `layout.pdf`
  el PDF usa la plantilla fija de siempre.

El enlace es por `id`, nunca por posición ni por tipo; sin `id`, una vista no se puede referenciar.

```yaml
views:
  - {id: resumen, type: kpis, metrics: [total_facturado, facturas]}
layout:
  web:
    components:
      - {id: kpis, type: kpi, view: resumen, metric: total_facturado, span: 12}
```

Componentes web, uno de cada tipo (sin `view`: `text`, `spacer` y `filters`):

```yaml
components:
  - {id: k1, type: kpi, view: resumen, metric: total_facturado, delta: previous_period}
  - {id: c1, type: line, view: diaria, x: day, series: [total_facturado], colors: [series1], span: 8}
  - {id: c2, type: area, view: diaria, x: day, series: [total_facturado]}
  - {id: c3, type: bar, view: estados, x: estado, series: [total_facturado], orientation: horizontal, span: 4}
  - {id: c4, type: pie, view: estados, category: estado, value: total_facturado, top_n: 6}
  - {id: c5, type: donut, view: estados, category: estado, value: total_facturado}
  - {id: t1, type: table, view: detalle, columns: [estado, facturas], totals: true, sort: {by: facturas, dir: desc}, page_size: 25}
  - {id: n1, type: text, text: "Cifras provisionales.", style: caption, font_name: serif}
  - {id: f1, type: filters, only: [estado]}
  - {id: s1, type: spacer, size: md}
```

Campos por tipo:

- `kpi`: `metric`, `delta` (`previous_period` o `none`) y `sparkline`.
- `line` y `area`: `x` (dimensión ordenada o granularidad) y `series`.
- `bar`: como los anteriores, más `orientation` (`vertical` u `horizontal`) y `stacked`, que exige
  dos series.
- `pie` y `donut`: `category`, `value`, `top_n` de 2 a 12 (6 por defecto) y `other_label`.
- `table`: `columns`, `totals`, `sort` (`by` y `dir`) y `page_size` de 5 a 200.
- `text`: `text` de 1 a 500 caracteres, `text_en`, `style` (`heading`, `paragraph` o `caption`) y
  `font_name`.
- `filters`: `only`, con los `filters` que muestra.
- `spacer`: `size` (`sm`, `md` o `lg`).

Bloques del PDF, uno de cada tipo (sin `view`: `header`, `text`, `page_break` y `footer`):

```yaml
blocks:
  - {id: cabecera, type: header, title: true, subtitle: true, period: true, logo: true, logo_role: brand}
  - {id: kpis, type: kpi_row, view: resumen, items: [total_facturado, facturas], delta: true}
  - {id: grafico, type: chart, view: diaria, kind: line, x: day, series: [total_facturado], height_mm: 60}
  - {id: tabla, type: table, view: detalle, columns: [estado, facturas], widths: [3, 1], totals: true, overflow: truncate}
  - {id: nota, type: text, text: "Documento interno.", align: center, font_name: mono}
  - {id: salto, type: page_break}
  - {id: pie, type: footer, generated_at: true, page_numbers: true, legal: "Documento generado por BizView."}
```

Campos por tipo:

- `header`: `title`, `subtitle`, `period`, `logo` y `logo_role` (`brand` o `none`).
- `kpi_row`: `view`, `items` y `delta`.
- `chart`: `kind` (como los gráficos web) con `x` y `series` o con `category` y `value`, más
  `height_mm` de 30 a 200 (60 por defecto) y `top_n`.
- `table`: `view`, `columns`, `widths` (un peso por columna), `totals` y `overflow`.
- `text`: `text`, `text_en`, `style` y `font_name`, más `align` (`left`, `center` o `right`).
- `page_break`: nueva página.
- `footer`: `generated_at`, `page_numbers` y `legal` de hasta 200 caracteres.

## Opciones

- Las etiquetas pueden tener una versión en inglés (`label_en`) que se muestra a quien usa
  BizView en inglés.
- Para estar listo para aplicar, el reporte necesita `pdf.enabled: true`, dimensiones y filtros.
- Los colores son roles, nunca literales: `primary`, `positive`, `negative`, `neutral`, `muted` y
  `series1` a `series8`; los resuelven el tema y la marca de la instalación.
- Las tipografías van por nombre (`sans`, `sans_bold`, `serif` y `mono`), y `font_name` solo se
  admite en un componente o bloque de texto.
- Los textos con versión en inglés son `text_en`, `other_label_en` y `legal_en`.
- Un layout no lleva direcciones ni rutas: el logo usa el rol `logo_role`.
- `bizview validate` comprueba el layout con el mismo esquema del agente.
- El ejemplo completo: `reports/facturas-dia/report.yaml`.
