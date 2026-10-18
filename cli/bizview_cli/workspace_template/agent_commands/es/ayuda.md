---
description: Muestra los comandos disponibles y cómo usar BizView.
argument_hint: "[tema]"
source: bizview
---
# /ayuda

## Comando

El usuario pide ayuda sobre un tema de BizView o del método Spec Kit (el texto después del
comando). En `## Comando` llega `Tema resuelto: <id>` con el texto del tema dentro de un bloque
`<datos … confianza="no">`, o la lista de temas cercanos cuando no hubo coincidencia.

Herramientas: `get_app_guide`, `get_project_overview`, `read_draft` y `finish_command`. Este
comando nunca cambia archivos.

## Pasos

1. Con un tema resuelto, responde solo con lo que dice ese tema, en pasos cortos, nombrando
   pantallas y botones exactamente como el tema los escribe en negrita, e incluye su enlace de la
   aplicación `[Abrir …](app:/ruta)` cuando aplique.
2. Si la pregunta toca otro tema, léelo con `get_app_guide` (id del índice) antes de responder.
3. Si la pregunta es sobre el proyecto actual («¿qué falta?», «¿por qué es directo?»), usa
   `get_project_overview` y cita las líneas de la spec (`archivo:línea`).
4. Sin tema resuelto: di que la guía no tiene ese tema y ofrece los temas cercanos por su título.
   Nunca inventes opciones ni rutas.
5. Si el rol del usuario no puede usar la opción, di quién puede.
6. Responde en el idioma del usuario y termina con `finish_command`.
