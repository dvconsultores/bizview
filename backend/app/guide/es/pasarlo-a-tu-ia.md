# Pasarlo a tu IA

## Para qué sirve

Cualquier IA puede escribir el proyecto: ChatGPT, Claude, Gemini, DeepSeek, Copilot o una herramienta
de código con la carpeta abierta. BizView no necesita ninguna clave ni conexión: tu IA trabaja fuera y
tú traes el resultado.

## Quién puede usarlo

Solo el **Superusuario**, con su propio acceso a la IA que prefiera.

## Cómo se hace

1. Abre una conversación nueva.
2. Pega `PROMPT.md` completo.
3. Pega `REQUEST.md` ya relleno.
4. Si hay fuente, pega también `sources/<fuente>/structure.md`.
5. Pide: «Escribe el proyecto siguiendo las reglas y devuélveme un solo zip con los archivos en la
   raíz».
6. Descarga el zip y guárdalo sin descomprimir.

Con una herramienta de código es más corto: abre la carpeta del paquete y pide «lee PROMPT.md y REQUEST.md
y escribe el proyecto». `CLAUDE.md` y `AGENTS.md` llevan el mismo texto.

## Opciones

- Si la IA no puede devolver un zip, pide los archivos uno por uno y móntalos tú con esas rutas; el zip
  es cómodo, no obligatorio.
- A mano: los archivos son YAML y SQL; `CONTENIDO.md` dice qué es cada uno.

## Problemas frecuentes

- Respuestas con datos de ejemplo dentro del SQL: pídele que quite las filas, el proyecto describe la
  lectura.
- Un zip con una carpeta que envuelve todo: BizView la quita si es una sola, pero pide los archivos
  en la raíz.
- La IA inventa tablas: pásale la estructura otra vez y pídele que solo use lo que aparece en ella.

## Relacionados

- Escribir la petición
- Validar antes de importar
- Corregir los problemas
