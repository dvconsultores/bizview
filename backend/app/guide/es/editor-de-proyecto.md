# Editor de proyecto

## Para qué sirve

Es el lugar de trabajo de un proyecto: sus archivos, sus problemas de validación y el chat del
agente, como un editor de código en la nube.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre un proyecto desde [Abrir Proyectos](app:/proyectos).
2. En el **Explorador de archivos** abre un archivo; se abre en una pestaña de
   **Archivos abiertos** (hasta 8 con cambios sin guardar).
3. Los archivos .md se muestran como documento: **Ver código** muestra el texto y
   **Ver documento** vuelve. YAML, SQL y JSON se editan con colores.
4. Pulsa **Guardar**. La validación corre al guardar y la barra de estado dice **Válido**, cuántos
   problemas hay o **Listo para aplicar**.
5. En **Problemas** toca un problema para ir al archivo y la línea.

## Opciones

- **Nuevo archivo**, **Nueva carpeta**, **Renombrar** y **Eliminar** funcionan solo dentro de las
  rutas permitidas del proyecto (ver Estructura de un proyecto). Con el teclado, en el explorador
  pulsa F2 para renombrar y Supr para eliminar el elemento seleccionado.
- El panel del chat trabaja con la **Spec actual** que elijas; **Nuevo chat en este proyecto**
  abre otra conversación.
- En el teléfono, las pestañas **Archivos**, **Editor** y **Chat** muestran un panel a la vez.
- Mientras el agente trabaja verás «El asistente está editando el proyecto…» y los archivos se
  actualizan solos.

## Problemas frecuentes

- Si alguien cambió un archivo mientras lo editabas, el editor te deja recargar, sobrescribir o
  descartar tus cambios.
