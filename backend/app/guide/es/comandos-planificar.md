# Comandos para planificar

## Para qué sirve

Estos comandos convierten una spec en un plan técnico y una lista de tareas, y revisan su calidad.

## Quién puede usarlo

Solo el **Superusuario**. Todos trabajan sobre la **Spec actual**.

## Cómo se hace

- `/speckit-plan`: escribe `plan.md` y, cuando hace falta, `research.md`, `data-model.md` y
  `quickstart.md`. Usa la estructura real de las fuentes (tablas y columnas) para decidir el
  diseño. Necesita `spec.md`.
- `/speckit-tasks`: escribe `tasks.md` con tareas numeradas por fases. Necesita `plan.md`. Si la
  spec tiene dudas sin resolver, te pregunta antes si quieres seguir.
- `/speckit-analyze`: compara spec, plan y tareas y entrega un informe de inconsistencias. No
  cambia ningún archivo.
- `/speckit-checklist <tema>`: crea o amplía una lista `checklists/<tema>.md` que evalúa la
  calidad de lo escrito (no la implementación). Los elementos nuevos quedan sin marcar.

## Problemas frecuentes

- «Falta plan.md; ejecuta /speckit-plan primero.»: el chat ofrece un botón **Insertar** con el
  comando que falta.
