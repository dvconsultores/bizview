🇪🇸 Español · 🇬🇧 [English](../IMPORT.md)

# Cómo entra un proyecto en Bizview

La autoría ocurre fuera de Bizview ([AUTHORING.md](AUTHORING.md)). Esta es la puerta de entrada:
una carpeta de archivos declarativos se convierte en un **proyecto** que el producto versiona, aplica
y ejecuta.

**Importar es la única forma de entrar.** No hay ningún botón que cree un proyecto vacío: un proyecto
se escribe con la herramienta que prefieras — Claude Code, Codex, DeepSeek, un editor o a mano — y
llega como un zip. La carpeta de la que se parte es el **paquete inicial**:
**Proyectos → Nuevo proyecto → Descargar paquete inicial** (o
[bizview-starter-template.zip](../../bizview-starter-template.zip), o
`bizview init project "<nombre>"`). La CLI valida la carpeta en la que trabajas y la mide exactamente
como lo hará el servidor, así que un proyecto que pasa en tu máquina se importa en el servidor.

## El camino

```text
autoría  →  validar  →  subir  →  mapear  →  colisiones  →  validar otra vez  →  vista previa  →  aplicar
```

### 1. Autoría

Escribe la carpeta del proyecto con el contrato de [AUTHORING.md](AUTHORING.md): `project.yaml`,
`specs/NNN-<nombre>/spec.md` con `**Status**: Approved`, y los artefactos que posee cada spec.

### 2. Validar antes de subir

```bash
bizview validate --write-lock      # en la carpeta del proyecto, o en la raíz del espacio de trabajo
```

`problems.json` lista cada problema con su archivo, la ruta JSON, el código y, cuando puede, la
corrección. Corrígelos aquí, no en la aplicación: la aplicación mostrará la misma lista y no
rechazará nada más.

### 3. Subir

- **En la aplicación**: **Proyectos → Importar proyecto**, elige el zip de la carpeta del proyecto.
  Antes de que se suba nada, la página lee el índice del archivo y muestra los dos presupuestos; por
  encima de un presupuesto la importación se rechaza ahí mismo, nombrando cuál. El servidor lo
  vuelve a comprobar.
- **CLI**: no hay comando de subida; la aplicación es dueña del árbol de archivos del proyecto.
  `bizview import --dry-run <zip|carpeta>` imprime los mismos dos números que daría el servidor
  (`--json` para una máquina).

```bash
zip -r panorama.zip projects/panorama -x '*.DS_Store'   # lo que espera la aplicación: un proyecto
```

### 4. Mapear

La carpeta superior del zip se descarta cuando no es una carpeta del formato, así que `panorama/`,
`projects/panorama/` y un zip de los archivos mismos producen el mismo proyecto. El `name` del
proyecto viene de `project.yaml`, luego del parámetro de la consulta y luego del nombre de la
carpeta.

### 5. Colisiones

| Qué colisiona | Qué pasa |
|---|---|
| el `slug` ya está tomado | es el **mismo proyecto**: el zip se convierte en una revisión nueva de él (ver abajo), nunca `-2` |
| el mismo `slug`, con **Importar como copia** | se crea una copia como `<slug>-2`, y sus identificadores de artefacto se renombran con ella |
| un archivo que ya está en el proyecto | la reimportación reemplaza el borrador: lo que trae el zip se escribe, lo que omite se elimina |
| dos carpetas de spec con el mismo número | se rechaza la importación entera (422) y no queda nada a medias |
| un archivo fuera del formato | se lista en `ignored`, nunca se escribe |
| una imagen por encima de su presupuesto, o un SVG con un script | se rechaza (422) nombrando el archivo |
| demasiados archivos, o demasiado tamaño, en un presupuesto | se rechaza (422) nombrando ese presupuesto |
| un archivo ejecutable en cualquier parte | se rechaza (422) con `zip_disallowed` y la ruta |

La respuesta es `{project, mode, revision, diff, ignored, validation, budgets}`: `ignored` es lo que
dejaste en el zip y el producto nunca guardará; `mode` es `created` o `reimported`.

### 5b. El segundo zip es una revisión, no un duplicado

Un proyecto se escribe fuera de Bizview y se corrige allí, así que el mismo proyecto llega una y otra
vez. El `slug` de `project.yaml` es lo que lo identifica, y cuando el manifiesto no tiene ninguno, el
`slug` al que deriva el nombre del proyecto. Una importación cuyo `slug` ya existe es una
**reimportación**, nunca `<slug>-2`.

- El zip se escribe sobre la **revisión borrador** del proyecto con semántica de reemplazo completo:
  los archivos e imágenes que el zip no trae salen de la carpeta. Nada se fusiona.
- El proyecto conserva su id, su `slug`, sus enlaces para compartir, sus permisos, sus tableros, su
  historial de auditoría y los datos que su integración ya cargó.
- Antes de escribir nada se muestra un **diff** (archivos añadidos, cambiados y eliminados, specs e
  identificadores, los dos presupuestos). `POST /api/projects/import?dry_run=true` lo responde y no
  escribe nada.
- No se aplica nada: la revisión aplicada anteriormente sigue sirviendo los tableros hasta que pulses
  **Aplicar**.
- Si guardaste archivos en el editor desde la última importación, la importación pregunta primero
  (`needs_confirmation`); envía `replace_draft=true` para aceptar.
- `copy=true` es la única forma de tener un segundo proyecto, y la copia renombra sus identificadores
  de artefacto (`ventas` → `ventas-2`, y sus referencias con ellos) para que pueda aplicarse.
- `PROJECT_REVISIONS_KEEP` (20 por defecto) acota el historial; la revisión aplicada y la anterior
  nunca se podan.

### 6. Validar otra vez

La importación valida lo que escribió y devuelve el resultado. Un proyecto que valida se puede
aplicar; uno que no, muestra sus problemas en el editor, y **Aplicar** se niega con la misma lista.

### 7. Vista previa

**Editor** muestra el árbol del proyecto, cada archivo y sus problemas. En 0.2.0 no hay vista previa
del borrador: lo que ves antes de aplicar es el resultado de la validación y los archivos. Después de
**Aplicar**, el reporte se renderiza en `/api/reports/<id>`, con el mismo renderizado que usan un
enlace para compartir y el PDF.

### 8. Aplicar

**Aplicar** compone el proyecto con los demás proyectos aplicados en una **versión** nueva, comprueba
la composición otra vez (un identificador duplicado o una referencia a otro proyecto son reales) y
arranca el horario de la integración. **Volver a la versión anterior** revierte. Las dos cosas son
eventos de auditoría.

Una aplicación también marca la **revisión** del proyecto: el borrador pasa a `aplicada` y el que se
aplicó antes pasa a `anterior`. **Volver a la revisión anterior** (en la página del proyecto) escribe
los archivos de esa revisión anterior como una revisión nueva y la aplica — los tableros vuelven a
ese diseño — y el cambio se audita como `project_reverted`. Cada revisión se puede descargar como un
zip con la misma forma que produce **Exportar**.

Una imagen se guarda por hash, nunca por contenido (044), así que una reversión puede recuperar el
texto exacto y una imagen solo mientras el archivo siga en disco; la respuesta nombra las que no pudo
devolver.

## Qué hacen importar y aplicar, en palabras llanas

*Importar* — 1 el zip se lee en memoria, se descarta la carpeta superior y se rechazan los
ejecutables y los scripts dentro de un SVG; 2 los archivos se mapean al formato y los desconocidos se
listan como `ignored`; 3 se comprueban los dos presupuestos (artefactos 400 archivos / 20 MB,
imágenes 2 000 / 25 MB); 4 una colisión de `slug` se convierte en una revisión nueva (055) o en una
copia `-2` si se pide; 5 se valida todo el árbol con el mismo validador que la CLI (esquemas, SQL de
forma estática, referencias entre archivos, datos personales contra la spec, completitud de la spec)
y los problemas se muestran por archivo con una corrección; 6 el proyecto se guarda como **borrador**:
nada corre y ningún usuario lo ve todavía.

*Aplicar* — 1 el borrador se compone con los demás proyectos aplicados en una **versión** nueva de
la instalación y se comprueba otra vez (los identificadores duplicados entre proyectos son errores
reales); 2 cada integración se registra con el worker: la primera ejecución es una carga completa,
después el horario (`cron`) ejecuta la ventana incremental (`:window_start`/`:window_end`) o una
recarga completa según `incremental.mode`; 3 los conjuntos de datos aterrizan en el esquema del
almacén `ds_<integración>.<conjunto>` con `_run_id` y `_loaded_at`; 4 cada reporte se convierte en un
tablero en `/r/<id>`, visible para los roles de `access`, con filtros, períodos, comparación, PDF/CSV
y enlaces para compartir; 5 la aplicación es un evento de auditoría y **Volver a la versión anterior**
lo revierte todo; 6 lo primero que conviene mirar: **Integraciones** → última ejecución, **Tableros**
→ el tablero nuevo, **Proyectos** → problemas.

El mismo texto viaja dentro de cada zip inicial (`QUE-HACE-BIZVIEW.md` / `WHAT-BIZVIEW-DOES.md`) y es
el tema de ayuda *Qué pasa al importar y aplicar*.

## Exportar

**Exportar** descarga el proyecto como un zip con sus specs, artefactos y `assets/`, la misma forma
que acepta **Importar**. Es la forma de llevar un proyecto a un repositorio Git, o de moverlo a otra
instalación.

## Equivalencias de la CLI

| Paso | Comando |
|---|---|
| Crear un espacio de trabajo (una vez) | `bizview init workspace --name mycompany` |
| Empezar una carpeta de proyecto en la que escribir | `bizview project new "Panorama cripto"` |
| Describir una fuente | `bizview describe <source>` |
| Validar | `bizview validate [--write-lock] [--live]` |
| Medir un zip o una carpeta | `bizview import --dry-run <zip> [--json]` |
| Ver qué cambiaría una reimportación | `bizview import <zip>` (modo + diff contra `projects/<slug>/`) |
| Versión | `bizview version` |

`bizview project new` escribe una carpeta donde escribir; no crea nada dentro de Bizview.
`bizview import --dry-run` sale con `0` cuando el proyecto cabe, con `1` cuando no (imprimiendo qué
presupuesto y por cuánto) y con `2` cuando la entrada no se puede leer.

La CLI nunca habla con un Bizview en marcha: lee y escribe archivos y habla con las fuentes de datos.
Subir, aplicar y revertir son cosas de la aplicación.

## Los dos presupuestos

Un proyecto se imputa a dos presupuestos, contados por separado. Antes de 049 compartían uno, así que
un proyecto que traía un juego de logos se rechazaba con «el proyecto supera el límite», un mensaje
sobre un presupuesto que el autor no podía arreglar.

| Presupuesto | Qué paga | Archivos | Por archivo | Total |
|---|---|---|---|---|
| **artefactos** | `project.yaml`, `specs/**`, `integrations/**`, `reports/**`, `themes/**`, `distributions/**` | 400 | 2 MB | 20 MB |
| **imágenes** | `assets/**` (`.png`, `.jpg`, `.webp`, `.svg`) | 2 000 | 300 KB | 25 MB |

El zip puede pesar la suma de los dos (45 MB). Cada rechazo nombra **un** presupuesto, las carpetas
que contó y los números, nunca una cifra combinada.

Los seis números son ajustes. Un superusuario los cambia en **Administración → Proyectos → Límites de
importación** (un campo vacío = el valor por defecto del despliegue, de `PROJECT_MAX_FILES`,
`PROJECT_MAX_KB`, `PROJECT_MAX_MB`, `PROJECT_ASSET_MAX_FILES`, `PROJECT_ASSET_MAX_KB`,
`PROJECT_ASSET_MAX_MB`). El cambio se audita (`project_limits_changed`).

## Archivos que no son el proyecto

Un paquete de autoría y el proyecto que construye viven en la misma carpeta (043), así que un zip a
menudo trae `PROMPT.md`, `REQUEST.md`, `request/`, `sources/`, `.bizview/`, `README.md`, `.DS_Store` o
`__MACOSX/`. Esos se listan bajo **Archivos ignorados** y la importación continúa: nada de ellos
llega al disco.

El contenido ejecutable es la excepción: un archivo cuya extensión es la de un programa (`.js`,
`.sh`, `.exe`, `.py`, `.dll`, …) o cuyos bytes empiezan como los de uno (`ELF`, `MZ`, `#!`, Mach-O)
rechaza la importación entera con `zip_disallowed` y la ruta. El ruido inofensivo se salta; un
programa no es ruido.

## Qué necesita una instalación

- `PROJECTS_DIR` escribible por el uid 10001 (el usuario de los contenedores).
- Los dos presupuestos suficientemente grandes para el proyecto (ver arriba).
- Las fuentes que el proyecto nombra, con las credenciales introducidas en **Fuentes de datos**,
  nunca en el proyecto.
