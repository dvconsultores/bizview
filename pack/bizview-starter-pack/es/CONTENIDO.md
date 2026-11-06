# Contenido del paquete, archivo por archivo

Este zip es una **plantilla de proyecto de BizView**. No es un proyecto terminado: los esqueletos
llevan valores de ejemplo que marcan con `REEMPLAZA`. Aquí tienes qué es cada archivo, quién lo
escribe, si es obligatorio y qué hace BizView con él al importar.

Leyenda: **Tú** = lo editas a mano · **Tu IA** = lo escribe la IA · **BizView** = viene hecho y no se
toca · **CLI** = lo genera `bizview`.

| Archivo | ¿Obligatorio? | Lo escribe | Qué hace BizView con él |
|---|---|---|---|
| `project.yaml` | Sí | Tú (el diálogo lo rellena) | Lee `name`, `slug` y `description`. El `slug` decide si el zip es un proyecto nuevo o una revisión del existente. |
| `bizview.yaml` | Sí, para validar | BizView | Manifiesto del espacio de trabajo. Solo lo usa `bizview validate` desde tu equipo; la importación lo ignora. |
| `REQUEST.md` | Para tu IA | Tú | Nunca se importa. Es el encargo que lee tu IA. |
| `REQUEST.*.md` | Para tu IA | Tú | Lo mismo, en el otro idioma. Ignorado al importar. |
| `PROMPT.md` | Para tu IA | BizView | Las reglas del proyecto. Ignorado al importar. |
| `PROMPT.*.md` | Para tu IA | BizView | Las mismas reglas en el otro idioma. Ignorado. |
| `CLAUDE.md`, `AGENTS.md` | Para tu IA | BizView | El mismo texto que `PROMPT.md`, para herramientas que leen una carpeta. Ignorados. |
| `CLAUDE.*.md`, `AGENTS.*.md` | Para tu IA | BizView | Las copias en el otro idioma. Ignoradas. |
| `README.md` | No | BizView | Los tres pasos. Ignorado al importar. |
| `README.*.md` | No | BizView | Los mismos tres pasos en el otro idioma. Ignorado. |
| `CONTENIDO.md` | No | BizView | Este documento. Ignorado al importar. |
| `CONTENTS.md` | No | BizView | El mismo documento en inglés. Ignorado. |
| `QUE-HACE-BIZVIEW.md` | No | BizView | Qué pasa al importar y al aplicar. Ignorado. |
| `WHAT-BIZVIEW-DOES.md` | No | BizView | Lo mismo en inglés. Ignorado. |
| `specs/001-<slug>/*` | Sí | Tu IA | `spec.md` es obligatorio: BizView lo muestra en el editor y lo exige para ejecutar. `plan.md` y `tasks.md` completan el expediente; si faltan, el proyecto queda marcado como incompleto. |
| `specs/001-<slug>/spec.md` | Sí | Tu IA | Declara el tipo (`integracion` o `reporte`) y `**Status**: Approved`. Sin spec aprobada, el proyecto no se puede aplicar, y la línea `**Datos personales**` se compara con las columnas del dataset. |
| `specs/002-<slug>-reporte/*` | Sí | Tu IA | La spec del reporte: tipo `reporte`, `**Status**: Approved` y las métricas que verá el lector. Sin ella el tablero no tiene dueño. |
| `integrations/<id>/integration.yaml` | Con integración | Tu IA | Declara qué se lee, cada cuánto, la clave, la ventana incremental y los chequeos. Al aplicar se convierte en una programación del worker. |
| `integrations/<id>/queries/*.sql` | Con integración | Tu IA | La lectura de solo lectura. Se valida sin conectarse (una sola instrucción `SELECT`/`WITH`) y la ejecuta el worker. |
| `integrations/<id>/requests/*.yaml` | Fuentes REST/SOAP | Tu IA | Sustituye al SQL cuando la fuente no es una base de datos. Misma validación estática. |
| `reports/<id>/report.yaml` | Sí | Tu IA | Métricas, dimensiones, vistas, períodos, filtros y el diseño web y PDF. Al aplicar se convierte en un tablero en `/r/<id>`. |
| `assets/**` | No | Tú | Imágenes de los bloques `asset` y de los iconos de cifras. Cuentan en su propio presupuesto. |
| `sources/<source>/*` | Para tu IA | BizView | La estructura de la fuente elegida (`structure.md` y `structure.json`). Nunca se importa. |
| `.bizview/schemas/*` | Para tu IA | BizView | Los esquemas JSON que valida BizView. Nunca se importan. |
| `.bizview/preset.yaml` | Para tu IA | BizView | El resumen del contrato: qué esquema aplica a cada archivo y las reglas. Nunca se importa. |
| `bizview.lock` | No | CLI | Huella de un árbol ya validado. Informativo; la importación lo ignora. |

## Reglas de nombres

- Las carpetas de spec son `NNN-<slug>`: tres dígitos, consecutivos **por proyecto**, y un número no
  se reutiliza nunca.
- Los `id` de integraciones, reportes y distribuciones van en minúsculas con guiones
  (`kebab-case`) y coinciden con el nombre de su carpeta.
- Un `id` de reporte es una URL: `/r/<id>`. Cambiarlo cambia el enlace que ya compartiste.
- El `slug` del proyecto es la identidad: la primera importación crea el proyecto y la segunda, con
  el mismo `slug`, propone una revisión.

## Qué ignora la importación

- Todo lo que no es del formato del proyecto: `PROMPT.md`, `REQUEST.md`, `README.md`,
  `CONTENIDO.md`, `CONTENTS.md`, `QUE-HACE-BIZVIEW.md`, `WHAT-BIZVIEW-DOES.md`, `CLAUDE.md`,
  `AGENTS.md`, `bizview.yaml`, `sources/`, `.bizview/`, `bizview.lock` y los archivos del sistema
  (`.DS_Store`).
- Los archivos repetidos que no son texto.
- Un archivo que parece un programa (`.js`, `.sh`, `.exe`…) **cancela** la importación: no es ruido.

## Presupuestos

| Límite | Qué cuenta | Archivos | Por archivo | Total |
|---|---|---|---|---|
| Artefactos | `project.yaml`, `specs/`, `integrations/`, `reports/`, `themes/`, `distributions/` | 400 | 2 MB | 20 MB |
| Imágenes | `assets/` | 2 000 | 300 KB | 25 MB |

Los dos límites se cuentan por separado y son ajustables por instalación. Un rechazo siempre nombra
el límite que se pasó.
