# Boceto con una imagen

## Para qué sirve

Adjuntar una imagen —un boceto o una captura de ejemplo— para pedir un reporte «como este» sin
describir la maqueta con palabras.

## Quién puede usarlo

Solo el **Superusuario**, y solo si el modelo configurado puede leer imágenes (`AI_VISION`).

## Cómo se hace

- En el compositor del chat pulsa el clip 📎 (**Adjuntar boceto**). También puedes arrastrar la imagen al cuadro de
  texto o pegarla con Ctrl+V. La miniatura aparece sobre el texto y puedes quitarla antes de
  enviar con la ✕.
- Formatos PNG, JPEG, WebP y GIF, hasta 5 MB por imagen (`ATTACHMENTS_MAX_MB`) y 4 imágenes
  esperando a enviarse en la conversación (`ATTACHMENTS_MAX_PER_MESSAGE`).
- La primera vez que envías una imagen, el chat muestra un aviso y espera tu confirmación: la
  imagen viaja al proveedor de IA configurado, así que usa bocetos o ejemplos y nunca capturas con
  datos de clientes.
- Escribe tu petición junto con la imagen, o envía solo la imagen, y el agente escribe las specs
  con el comando en el que estés, igual que con cualquier otro mensaje.
- Las imágenes quedan en la conversación: puedes abrirlas o quitarlas después. Quitar una imagen no
  cambia el proyecto ni el texto del mensaje.

## Opciones

- Las imágenes se guardan fuera de la carpeta del proyecto (`ATTACHMENTS_DIR`); no entran en la
  exportación del proyecto, ni en el espejo de Git, ni en la versión aplicada, y se borran cuando
  se depura el proyecto o cuando pasan 24 horas sin enviarse.
- La imagen es un boceto de estructura y etiquetas, nunca una fuente de datos: el agente no lee
  cifras de la imagen ni crea tablas a partir de ella.
- Si el modelo configurado no puede leer imágenes, el botón queda deshabilitado y el chat te lo
  explica; el resto del chat sigue funcionando igual.
