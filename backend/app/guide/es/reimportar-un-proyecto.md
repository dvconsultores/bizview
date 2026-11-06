# Reimportar un proyecto

## Para qué sirve

Volver a importar un proyecto que ya está en BizView. Cada corrección llega como un `.zip` nuevo del
mismo proyecto, y ese zip se convierte en una revisión del proyecto que ya existe —no en un
proyecto aparte—, con lo que sus enlaces, sus accesos, sus tableros y su historial siguen donde
estaban.

## Quién puede usarlo

Solo el **Superusuario**, y se pide confirmar la contraseña.

## Cómo se hace

1. Corrige la carpeta del proyecto y comprímela otra vez: `zip -r ventas.zip ventas/`.
2. Abre [Abrir Proyectos](app:/proyectos) y pulsa **Importar proyecto**.
3. Elige el `.zip`. BizView compara el archivo con la revisión que tiene el proyecto y muestra el
   resumen: archivos nuevos, cambiados y eliminados, specs e ids añadidos o quitados, y los dos
   límites de importación.
4. Pulsa **Importar ahora**. El zip se guarda como una revisión nueva en borrador y el proyecto no
   se aplica solo: los tableros siguen mostrando la revisión aplicada.
5. Cuando quieras publicar los cambios, abre el proyecto y pulsa **Aplicar proyecto**.

La reimportación reemplaza: lo que el zip no trae se quita del borrador, imágenes incluidas. No
se mezcla nada. La revisión 1 se compara con el zip; la 2 con la 1, y así.

## Opciones

- **Importar como copia**: crea un proyecto aparte con su propio identificador y sus propios ids
  (`cripto` pasa a `cripto-2`), para una variante que debe vivir por separado.
- **Reemplazar borrador**: si guardaste cambios en el editor desde la última importación, BizView
  pregunta antes de pisarlos. Lo guardado queda en el historial de archivos; el borrador se
  reemplaza.
- **Revisiones**: en la página del proyecto, cada importación y cada guardado del editor es una
  revisión, con su fecha, quién la hizo, de dónde vino y cuántos archivos cambió. Cada fila se puede
  **Descargar** como zip, con la misma forma que Exportar.
- Volver a la revisión anterior: escribe los archivos de la revisión anterior como una revisión
  nueva y la aplica. La auditoría registra la importación, la aplicación y la vuelta atrás.
- Se conservan las últimas 20 revisiones de cada proyecto, más la aplicada y la anterior. El número
  lo fija `PROJECT_REVISIONS_KEEP` en la instalación.
- `bizview import ventas.zip` muestra el modo (`created` o `reimported`) y el diff contra la carpeta
  del espacio de trabajo donde lo ejecutes, sin subir nada.

## Problemas frecuentes

- Cambié el identificador del proyecto en `project.yaml`: entonces es otro proyecto y se crea uno
  nuevo; el anterior no se toca. El identificador es la identidad del proyecto.
- El resumen dice que se eliminan archivos: el zip no los trae. Vuelve a comprimir la carpeta
  completa, no solo lo que cambió.
- Aplicar falla después de importar: la revisión está en borrador y el proyecto tiene problemas;
  ábrelo para verlos. Nada del borrador llega a los tableros hasta que se aplica.
- Una imagen no vuelve al revertir: las imágenes se guardan por su huella, no por su contenido,
  así que una que ya no está en la carpeta no se puede recuperar; BizView lo dice al revertir.

## Relacionados

- Importar un proyecto
- Aplicar un proyecto
- Editor de proyecto
