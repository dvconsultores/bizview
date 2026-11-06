# Autoría de un proyecto de Bizview

Bizview ejecuta lo que escribes; no lo escribe. Este documento es el contrato: la carpeta, la
petición, los esquemas, las reglas, la validación y un ejemplo completo al final.

La versión completa, campo por campo, está en [AUTHORING.md](../AUTHORING.md); esta es la guía en
español con el mismo orden.

## 0. El paquete inicial

No empiezas de cero. **Proyectos → Nuevo proyecto → Descargar paquete inicial** construye
`bizview-starter-<identificador>.zip` en el servidor con el nombre que escribiste, el idioma que
elegiste y, si eliges una, la estructura de la fuente.

```text
PROMPT.md            las reglas para tu IA; funciona pegado en un chat
REQUEST.md           la petición que rellenas
project.yaml         nombre, identificador, fecha
specs/001-<id>/      spec, plan y tareas de la integración
specs/002-<id>-reporte/   la spec propia del reporte
integrations/<id>/   integration.yaml + queries/example.sql (no existe en un reporte directo)
reports/<id>/        report.yaml
sources/<nombre>/    structure.md + structure.json, si elegiste una fuente
.bizview/            schemas/*.json y preset.yaml: lo que valida Bizview
CONTENIDO.md / CONTENTS.md   qué es cada archivo, en español y en inglés
QUE-HACE-BIZVIEW.md / WHAT-BIZVIEW-DOES.md   qué hacen importar y aplicar
CLAUDE.md, AGENTS.md el mismo texto que PROMPT.md para herramientas que leen una carpeta
```

El proyecto renderizado valida sin errores: lo que falta se marca `REEMPLAZA`. `make starter-template`
publica el mismo paquete con marcadores como
[bizview-starter-template.zip](../../bizview-starter-template.zip), y `bizview init project "<nombre>"
[--source <s>]` lo escribe desde la terminal. Una sola fuente, tres salidas.

### Pegarlo en un chat

Pega `PROMPT.md`, pega `REQUEST.md` relleno, pega `sources/<nombre>/structure.md` si lo tienes y pide
el proyecto. La respuesta debe ser **un zip con los archivos en la raíz**. Con una herramienta de
código, abre la carpeta: `CLAUDE.md` y `AGENTS.md` llevan las mismas reglas.

## 1. Los cinco pasos

| # | Paso | Pantalla o comando |
|---|---|---|
| 1 | Añadir la fuente | **Fuentes de datos → Nueva**, luego **Probar** |
| 2 | Generar su estructura | **Estructura → Generar estructura**, o `bizview describe "<fuente>" --pack --out .` |
| 3 | Descargar el paquete inicial | **Proyectos → Nuevo proyecto → Descargar paquete inicial**, o `bizview init project "<nombre>"` |
| 4 | Rellenar `REQUEST.md` y dárselo a tu IA | cualquier chat o herramienta de código |
| 5 | Importar el zip y aplicar | **Proyectos → Importar proyecto**, luego **Aplicar** |

`bizview validate` es opcional y nunca sustituye a la importación: el servidor ejecuta el mismo
validador antes de escribir el borrador.

## 2. La carpeta

```text
miempresa/                      espacio de trabajo, uno por organización
├── bizview.yaml                manifiesto: el nombre
├── bizview.lock                escrito por `bizview validate --write-lock`
└── projects/<id>/              un proyecto BI por carpeta
    ├── project.yaml            nombre, identificador, descripción
    ├── specs/NNN-<nombre>/     spec.md (+ plan.md, tasks.md, checklists/)
    ├── integrations/<id>/      integration.yaml + queries/*.sql | requests/*.yaml
    ├── reports/<id>/           report.yaml
    ├── distributions/<id>.yaml envíos programados (destinatarios por rol)
    └── assets/                 imágenes del reporte (PNG/JPEG/WebP/SVG)
```

## 3. La petición

`REQUEST.md` es para ti y para tu IA; el producto nunca lo lee. Una página: la pregunta, quién lee,
las cifras, los cortes, el período, el estilo, lo que queda fuera y si hay datos personales.

## 4. La especificación

`spec.md` es obligatorio. Lleva la línea de tipo
(`**Tipo**: fuente | integracion | reporte | distribucion`, se acepta `**Type**`) y
`**Status**: Approved`. Sin spec aprobada no hay artefacto. `plan.md`, `tasks.md` y el resto del
expediente son opcionales para un proyecto importado; `tasks.md` con una tarea `- [ ]` impide aplicar.

Los números son de tres dígitos por proyecto, consecutivos y nunca se reutilizan. Un reporte necesita
su propia spec de tipo `reporte`; una integración, la suya de tipo `integracion`.

## 5. Los artefactos

`integrations/<id>/integration.yaml` — `id`, `spec`, `source`, `schedule`, `timezone`, `datasets` con
`primary_key`, `date_column`, `columns`, `extract` e `incremental`. Una sola instrucción de solo
lectura por archivo. En transformaciones, una fecha se convierte con
`CAST(strftime(columna, '%Y-%m-%d') AS DATE)`.

`reports/<id>/report.yaml` — `uses` (o `direct`), `date`, `metrics`, `dimensions`, `periods`,
`filters`, `access`, `views`, `pdf` y `layout`. En un ranking, `dimension` y `metric` van en singular;
un componente `bar` usa `x` y `series`. Usa nombres de negocio: `comprobante_id`, nunca
`document_id`.

`distributions/<id>.yaml` — `report`, `subscriptions` con `frequency`, `period` y `recipients: {roles}`.
Los destinatarios son roles, nunca direcciones.

Todos los campos, y el ejemplo completo, están en [../AUTHORING.md](../AUTHORING.md) y
[../REPORTS.md](../REPORTS.md).

## 6. Validar

```bash
bizview validate --write-lock
```

Es el mismo validador que ejecuta el servidor sobre los mismos esquemas de
`cli/bizview_cli/schemas/`. Las nueve comprobaciones son: esquema y formato, spec aprobada,
referencias, SQL de solo lectura, identificadores, imágenes, datos personales, al menos un filtro y
los dos presupuestos de importación (400 archivos / 2 MB / 20 MB para artefactos, 2 000 / 300 KB /
25 MB para imágenes).

## 7. Importar y aplicar

**Proyectos → Importar proyecto** toma el zip, mapea lo que encuentra, informa lo que ignora, valida
otra vez y guarda un borrador. **Aplicar** compone una versión nueva, registra las programaciones y
publica los tableros. Los detalles y las colisiones: [IMPORT.md](./IMPORT.md) y
[../IMPORT.md](../IMPORT.md).

## 8. Un ejemplo resuelto

El proyecto `coinmarketcap`: una integración con cuatro datasets unidos por `snapshot_at` y un reporte
con una fila de cifras, una tendencia, un ranking y una tabla. Está completo en
[../AUTHORING.md](../AUTHORING.md), sección 8, y es además un fixture del producto: se renderiza en
cada ejecución de las pruebas.
