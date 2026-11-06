# Corregir los problemas

## Para qué sirve

Un problema dice qué archivo, qué línea o qué clave, qué está mal y, casi siempre, cómo arreglarlo.
Se corrige en el archivo y se vuelve a comprobar; no hay que empezar de nuevo.

## Quién puede usarlo

Solo el **Superusuario**, en el editor del proyecto o en su equipo.

## Cómo se hace

1. Abre [Proyectos](app:/proyectos) y entra al proyecto: los problemas aparecen bajo el editor.
2. Lee la fila entera: archivo, mensaje y la columna de cómo arreglarlo.
3. Corrige el archivo en el editor, o pide a tu IA que lo corrija con ese mensaje copiado.
4. Pulsa **Volver a comprobar** para ver la lista actualizada.
5. Cuando no queden errores, pulsa **Aplicar proyecto**.

Algunos problemas traen una corrección propuesta y se arreglan con un botón; otros, como una tarea
sin marcar, necesitan que alguien decida.

## Opciones

- Los avisos no impiden aplicar; los errores sí. Un reporte sin filtros es un error de la
  aplicación, no de la validación.
- Si el problema está en otro proyecto, el aviso lo nombra y no se arregla desde aquí.
- Puedes devolver el proyecto a una versión anterior desde su historial si una corrección empeora
  algo.

## Problemas frecuentes

- `unknown_column`: el reporte usa una columna que su dataset no declara. Añádela al dataset o usa
  otra.
- `open_tasks`: queda una tarea `- [ ]` en `tasks.md`. Márcala cuando esté hecha.
- `spec_not_approved`: el `spec.md` no dice `**Status**: Approved`.
- `personal_data_undeclared`: una columna parece un dato personal y la spec no la enumera.

## Relacionados

- Validar antes de importar
- Editor de proyecto
- Aplicar un proyecto
