# Estructura de un proyecto

## Para qué sirve

Explica qué archivos tiene un proyecto y dónde va cada cosa. El editor y el agente solo aceptan
estas rutas.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

Un proyecto es una carpeta con:

- `project.yaml`: nombre, identificador y descripción.
- `.specify/memory/constitution.md`: los principios del proyecto, con el bloque fijo de reglas de
  la instalación.
- `specs/NNN-nombre/`: una carpeta por spec, numeradas sin repetir (`001`, `002`…), con
  `spec.md`, `plan.md` y `tasks.md`, y opcionales `research.md`, `data-model.md`,
  `quickstart.md` y `checklists/<nombre>.md`.
- `integrations/<id>/integration.yaml`, con sus consultas `queries/*.sql` o peticiones
  `requests/*.yaml`.
- `reports/<id>/report.yaml`.
- `distributions/<id>.yaml`.

## Opciones

- El chat del proyecto vive en el panel **Asistente** (el botón del encabezado del proyecto o el
  de la barra superior); en el teléfono es la pestaña **Chat**.
- **Pantalla completa** oculta el menú y la barra superior y pone el explorador, el editor y el
  chat a toda la pantalla; se sale con el mismo botón o con Esc.
- Cada artefacto apunta a su spec con el campo `spec:`, por ejemplo `spec: specs/002-ventas`.
- Los ids de integraciones, reportes y distribuciones son únicos en toda la instalación.
- Hay un tamaño máximo por archivo y por proyecto; el editor avisa al pasarlo.
- Nunca se guardan credenciales ni datos de filas en un proyecto: las fuentes se nombran, no se
  configuran aquí.
