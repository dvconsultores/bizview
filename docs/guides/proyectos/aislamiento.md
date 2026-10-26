# Aislamiento por proyecto

Este documento explica cómo BizView garantiza que un proyecto nunca muestre, corrija ni
previsualice los archivos de otro. Nació de un incidente real (2026-10-26): la página de `artemisa`
mostraba un problema de `coinmarketcap`, su botón «Aplicar arreglo» respondía «El archivo
projects/coinmarketcap/… ya no existe» y la vista previa decía que no veía ningún archivo del
proyecto.

## La regla

**Un proyecto es una configuración separada: su página, su validación, sus arreglos y su vista previa
hablan solo de los archivos de su carpeta.** Nadie lee ni escribe los archivos de otro proyecto.

La validación *compone* el espacio de trabajo (este proyecto + la copia aplicada de los demás)
porque un id duplicado o una referencia a otra integración son problemas reales. Lo que cambia es
**dónde se publica el hallazgo**: cada proyecto publica solo lo suyo.

## Dónde vive cada cosa

| Dato | Dónde | Alcance |
|---|---|---|
| Archivos del proyecto | `PROJECTS_DIR/<slug>/…` | la carpeta, resuelta desde `project_id` |
| Borrador | la carpeta (lectura) | el proyecto |
| Validación y «problemas» | `project.validation` | el proyecto |
| Vista previa | `project.preview` | el proyecto |
| Conversaciones | `assistant_session.project_id` | el proyecto (y su autor) |
| Historial de archivos | `project_file_revision.project_id` | el proyecto |
| Comandos `/speckit-…` | `assistant_command_run.project_id` | el proyecto |
| Contratos de ejecución | `assistant_auto_run.project_id` | el proyecto |
| Solicitudes de vista previa | `assistant_preview_request.project_id` | el proyecto |
| Perfiles de ejecución | `assistant_run_profile` | la instalación (formulario: etapas, límites y nombres de fuente; no son archivos de un proyecto) |

## Rutas

- Los archivos se nombran **relativos a la carpeta del proyecto**: `reports/panorama-cripto/report.yaml`.
- `projects/<slug>/…` es el prefijo de la *composición* (lo que ve el validador). Nunca es una ruta
  de un proyecto: se rechaza con `path_outside_project` («ruta fuera del proyecto»).
- Tampoco se aceptan rutas absolutas, `..` ni enlaces simbólicos que salgan de la carpeta.
- La única forma de pasar de un proyecto al disco es
  `fs.resolve_project_path(project_id, relative)`: resuelve la carpeta desde la fila del proyecto
  (`project_id → PROJECTS_DIR/<slug>`) y aplica las reglas anteriores.

## Qué ve el lector

- **Panel de problemas**: solo los problemas de este proyecto, con su archivo relativo y su botón
  «Aplicar arreglo». Si el espacio de trabajo tiene problemas en otros proyectos, aparece una nota
  con sus nombres — sin botón, porque no se corrigen desde aquí.
- **Estado**: `Válido` significa «los archivos de este proyecto son válidos». Aplicar exige además
  que la composición entera sea válida (`composed_valid`): si otro proyecto la rompe, «Listo para
  aplicar» queda pendiente y nombra a ese proyecto.
- **Chat**: el panel muestra el proyecto de la conversación; una conversación de otro proyecto no se
  abre desde esta página (el enlace `?chat=` se comprueba).
- **Vista previa**: la solicitud lleva su `project_id`; el worker resuelve la carpeta desde él y, si
  está vacía o no existe, falla diciendo el slug y la ruta montada, para distinguir un volumen que
  falta de un error de alcance. El registro anota la carpeta resuelta al empezar la validación, la
  vista previa y el aplicar.

## Qué hacer si aparece «ruta fuera del proyecto»

1. Vuelve a comprobar los problemas del proyecto (el panel se recalcula sobre la carpeta actual).
2. Si el problema sigue apareciendo, mira a qué proyecto pertenece: la nota del panel lo dice.
3. Un problema de otro proyecto se corrige en **su** página.

## Notas de implementación

- `compose.validate_project` publica `errors`/`warnings` (propios), `other_projects`
  (`{slug: {errors, warnings}}`), `workspace_errors`/`workspace_warnings` y `composed_valid`.
- `POST /api/projects/{slug}/fix` resuelve cada archivo con `resolve_project_path`; una ruta de otro
  proyecto es `422 path_outside_project` y un archivo válido que ya no está sigue siendo
  `409 fix_gone`. Un `problem_id` debe nombrar el mismo archivo que el arreglo.
- `PUT /api/projects/{slug}/apply` compone desde la carpeta del proyecto y se niega si esa carpeta no
  existe (una versión sin sus archivos sería una pérdida de datos).
- `backend/tests/test_project_scope.py` y `test_project_scope_guard.py` son la regresión: dos
  proyectos, un usuario, y ninguna consulta sobre una tabla con `project_id` sin filtrar por
  proyecto.
