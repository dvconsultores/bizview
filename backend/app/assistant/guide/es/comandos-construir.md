# Comandos para construir

## Para qué sirve

Estos comandos escriben los artefactos de la spec (integración, reporte o distribución) y
comprueban que el proyecto cumple lo pedido.

## Quién puede usarlo

Solo el **Superusuario**, sobre la **Spec actual**.

## Cómo se hace

- `/speckit-implement`: sigue `tasks.md` y escribe los artefactos del tipo de la spec: para una
  integración, `integrations/<id>/integration.yaml` y sus consultas o peticiones; para un reporte,
  `reports/<id>/report.yaml`; para una distribución, `distributions/<id>.yaml`. Comprueba cada
  consulta, ejecuta la vista previa, marca las tareas hechas y al final cambia el estado de la
  spec a `Implemented`. Nunca aplica el proyecto.
- `/speckit-converge`: compara lo que piden spec, plan y tareas con los artefactos y, si falta
  algo, agrega una fase de tareas nuevas al final de `tasks.md`. No cambia nada más.

## Opciones

- `/speckit-implement <spec> --only T025,T026`: implementa y marca solo esas tareas. Es la
  acción honesta del panel de problemas cuando quedan tareas sin marcar («Implementar tareas
  pendientes»): una tarea se marca al implementarla, con su archivo escrito; ningún arreglo, ni
  ningún otro comando, cambia el estado de una tarea.
- Antes de implementar, el chat pregunta si hay listas de verificación con elementos sin marcar o
  si la spec aún no está aprobada; tu «sí» aprueba la spec.
- Si un comando se interrumpe (lo detienes o se acaba el presupuesto), lo hecho se conserva; al
  volver a ejecutar el mismo comando continúa desde ahí.

## Problemas frecuentes

- Si no está **Listo para aplicar** al terminar, mira **Pendiente para aplicar** o ejecuta
  `/speckit-converge`.
- `/fix <qué cambiar>`: corrige un artefacto que ya existe (un reporte, una consulta, una
  distribución) sin escribir una spec nueva. La validación y la vista previa siguen mandando.
