# El método Spec Kit

## Para qué sirve

En BizView nada corre sin una spec: cada fuente, integración, reporte y distribución es una
especificación numerada del proyecto que pasa por etapas fijas.

## Quién puede usarlo

Solo el **Superusuario** trabaja en proyectos.

## Cómo se hace

El flujo de una spec, con el comando de cada paso:

1. `/speckit-specify <descripción>`: crea la spec `NNN-nombre` con su **Tipo**.
2. `/speckit-clarify`: resuelve las dudas abiertas.
3. `/speckit-plan`: escribe el plan técnico.
4. `/speckit-tasks`: divide el plan en tareas.
5. `/speckit-analyze` y `/speckit-checklist` (opcionales): revisan la coherencia y la calidad.
6. `/speckit-implement`: escribe los artefactos hasta dejar el proyecto **Listo para aplicar**.
7. `/speckit-converge`: compara lo pedido con lo hecho y agrega tareas si falta algo.
8. **Aplicar proyecto**: lo haces tú.

## Opciones

- Las etapas que verás en el explorador son **Especificada**, **Aclarada**, **Planificada**,
  **Tareas**, **Implementada** y **Aplicada**, y **Convergida** cuando converge no encontró
  nada pendiente.
- `/speckit-constitution` fija los principios del proyecto; las reglas de la instalación no se
  pueden quitar.
- ¿Qué sigue? Escribe `/ayuda` en el chat: muestra el siguiente comando de cada spec.
