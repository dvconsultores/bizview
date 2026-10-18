# Bizview workspace — {name}

Workspace Bizview generado el {date}.

## Estructura (layout v2)

```
bizview.yaml            manifest (name)
bizview.lock            generado por `bizview validate --write-lock`
projects/<slug>/        un proyecto BI por carpeta (slug: minúsculas, dígitos, guiones)
  project.yaml          name, slug, description, created
  .specify/memory/constitution.md   (principios opcionales del proyecto)
  specs/NNN-<nombre>/   spec.md plan.md tasks.md (+ research.md data-model.md quickstart.md checklists/*.md)
  integrations/<id>/    integration.yaml + queries/*.sql | requests/*.yaml
  reports/<id>/         report.yaml
  distributions/<id>.yaml   envíos programados de un reporte, destinatarios solo por rol
```

## Flujo de trabajo

0. Crea el proyecto con `bizview project new "<nombre>"` (carpeta `projects/<slug>/` con Spec Kit) y abre esa carpeta con tu agente.
1. Describe la fuente con `bizview describe` (estructura, tablas, columnas).
2. Usa `/speckit-specify` para crear una spec: primero `fuente` —o `integracion` cuando se requiera lectura incremental—, luego `reporte` y `distribucion` según aplique.
3. Genera el plan con `/speckit-plan` y las tareas con `/speckit-tasks`.
4. Implementa los artefactos declarativos (SQL, YAML) dentro del proyecto.
5. Ejecuta `bizview validate --write-lock` y corrige todos los errores.
6. Haz commit de spec, plan, tareas y artefactos.
7. Aplica la integración o reporte en Administración de Bizview.

## Reglas

- Cada spec vive en `projects/<slug>/specs/NNN-<nombre>/`; NNN es un número de tres dígitos, consecutivo por proyecto, y nunca se reutiliza (001, 002, …).
- Toda spec.md lleva la línea de tipo: `**Tipo**: fuente | integracion | reporte | distribucion` (se acepta `**Type**` en inglés).
- El campo `spec:` de un artefacto apunta a `specs/NNN-<nombre>` dentro de su propio proyecto.
- Los ids de integrations, reports y distributions son únicos en todo el workspace.
- Una spec `fuente` documenta una fuente de datos (`**Fuente**: <nombre en Bizview>`, propósito, tablas de interés, si los reportes la leen directo; nunca credenciales).
- Las distributions envían reportes solo a roles (`admin`/`user`), nunca a direcciones de correo.
- Sin spec aprobada no se implementa artefacto: los artefactos necesitan una spec en `specs/` de su propio proyecto.
- Declarativo únicamente: SQL de solo lectura, YAML descriptivo; sin secretos ni filas de datos en el repositorio.
- Reutiliza integraciones existentes antes de crear una nueva; si un reporte necesita datos que faltan, primero se crea la spec de `fuente` o `integracion`.
- `bizview validate --write-lock` debe pasar antes de cualquier commit.
