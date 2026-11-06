# Cómo entra un proyecto en Bizview

La autoría ocurre fuera de Bizview ([AUTHORING.md](./AUTHORING.md)). Esta es la puerta de entrada: una
carpeta de archivos declarativos se convierte en un **proyecto** que el producto versiona, aplica y
ejecuta. La referencia completa está en [../IMPORT.md](../IMPORT.md).

**Importar es la única forma de entrar.** No hay un botón que cree un proyecto vacío. La carpeta de
partida es el **paquete inicial**: **Proyectos → Nuevo proyecto → Descargar paquete inicial**, o
[bizview-starter-template.zip](../../bizview-starter-template.zip), o `bizview init project "<nombre>"`.

## El camino

```text
autoría  →  validar  →  subir  →  mapear  →  colisiones  →  validar otra vez  →  vista previa  →  aplicar
```

1. **Autoría.** Escribe la carpeta con el contrato: `project.yaml`, `specs/NNN-<nombre>/spec.md` con
   `**Status**: Approved` y los artefactos de cada spec.
2. **Validar (opcional).** `bizview validate --write-lock` corre el mismo validador que el servidor.
3. **Subir.** **Proyectos → Importar proyecto**, con el zip. El navegador lee el índice del archivo
   antes de enviarlo y muestra lo que trae frente a cada presupuesto.
4. **Mapear.** Cada archivo va a su sitio del formato; lo que no es del proyecto se lista como
   `ignored` y no se guarda.
5. **Colisiones.** La tabla siguiente.
6. **Validar otra vez.** El servidor valida lo que escribió y muestra los problemas por archivo.
7. **Vista previa.** El editor muestra el árbol, cada archivo y el resultado de la validación.
8. **Aplicar.** Compone una versión nueva con los demás proyectos aplicados y arranca el horario.

## Colisiones

| Qué colisiona | Qué pasa |
|---|---|
| el `slug` ya existe | es el **mismo proyecto**: el zip se convierte en una revisión nueva, nunca `-2` |
| el mismo `slug` con **Importar como copia** | se crea una copia `<slug>-2` y sus identificadores se renombran con ella |
| un archivo que ya está en el proyecto | la reimportación reemplaza el borrador: lo que trae el zip se escribe, lo que omite se elimina |
| dos carpetas de spec con el mismo número | se rechaza la importación entera (422) y no queda nada a medias |
| un archivo fuera del formato | se lista en `ignored`, nunca se escribe |
| una imagen por encima de su presupuesto, o un SVG con script | rechazo (422) nombrando el archivo |
| demasiados archivos o demasiado tamaño en un presupuesto | rechazo (422) nombrando el presupuesto |
| un ejecutable en cualquier parte | rechazo (422) con `zip_disallowed` y la ruta |

La respuesta es `{project, mode, revision, diff, ignored, validation, budgets}`.

## Reimportar no duplica

Un proyecto se corrige fuera y llega otra vez. El `slug` de `project.yaml` es lo que lo identifica. Una
importación con un `slug` que ya existe es una **reimportación**:

- El zip se escribe sobre el **borrador** con reemplazo completo.
- El proyecto conserva su id, su `slug`, sus enlaces, sus permisos, sus tableros, su auditoría y los
  datos que su integración ya cargó.
- Antes de escribir se muestra un **diff**: archivos añadidos, cambiados y eliminados, specs e
  identificadores, y los dos presupuestos. `dry_run=true` lo responde sin escribir.
- No se aplica nada: la revisión aplicada sigue sirviendo los tableros hasta que pulses **Aplicar**.
- `copy=true` es la única forma de tener un segundo proyecto.

## Qué pasa al importar y al aplicar

**Importar** — 1 el zip se lee en memoria, se quita la carpeta que lo envuelve y se rechazan los
ejecutables y los scripts dentro de un SVG; 2 los archivos se mapean al formato y los desconocidos se
listan como `ignored`; 3 se comprueban los dos presupuestos (artefactos 400 archivos / 20 MB, imágenes
2 000 / 25 MB); 4 un `slug` repetido es una revisión nueva, o una copia `-2` si se pide; 5 se valida
todo el árbol con el mismo validador que la CLI y los problemas se muestran archivo por archivo con una
corrección; 6 el proyecto queda como **borrador**: nada corre y ningún usuario lo ve.

**Aplicar** — 1 el borrador se compone con los demás proyectos aplicados en una **versión** nueva y se
vuelve a comprobar; 2 cada integración se registra con el worker: la primera ejecución es una carga
completa y después corre el horario con la ventana incremental o una recarga completa; 3 los datasets
aterrizan en `ds_<integración>.<dataset>` con `_run_id` y `_loaded_at`; 4 cada reporte se convierte en
un tablero en `/r/<id>`, visible para los roles de `access`, con filtros, períodos, comparación,
PDF/CSV y enlaces para compartir; 5 la aplicación queda en la auditoría y **Volver a la versión
anterior** lo revierte todo; 6 lo primero que conviene mirar: **Integraciones** (última ejecución),
**Tableros** (el tablero nuevo) y **Proyectos** (problemas).

## Exportar

**Exportar** descarga el proyecto como zip con sus specs, artefactos y `assets/`: la misma forma que la
importación acepta.

## Presupuestos y archivos que no son el proyecto

Dos presupuestos separados, ajustables por instalación: artefactos (400 archivos, 2 MB cada uno,
20 MB) e imágenes (2 000 archivos, 300 KB cada una, 25 MB). Un rechazo nombra siempre el que se pasó.
Los archivos del paquete (`PROMPT.md`, `REQUEST.md`, `README.md`, `CONTENIDO.md`, `sources/`,
`.bizview/`, `bizview.lock`) se listan y se omiten.
