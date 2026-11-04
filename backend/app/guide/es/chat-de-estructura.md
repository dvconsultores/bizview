# Chat de estructura

## Para qué sirve

Responde preguntas sobre lo que contiene una fuente —tablas, columnas, tipos, claves, endpoints y
formas de respuesta— y puede redactar las observaciones de `structure.md` o un párrafo para tu
`REQUEST.md`. No lee datos: no devuelve filas, ni cifras de negocio, ni direcciones.

## Quién puede usarlo

Solo el **Superusuario**, y solo si la instalación tiene un proveedor de IA configurado.

## Cómo se hace

1. Abre la fuente y entra en la pestaña **Estructura** (ver Estructura de una fuente).
2. En el panel **Chat de estructura**, escribe la pregunta y pulsa **Preguntar**, o usa
   Ctrl+Intro.
3. Lee la respuesta: los nombres de tablas y columnas aparecen con el nombre exacto de la fuente.
4. Si quieres empezar de cero, pulsa **Borrar conversación**.

## Opciones

- Cada respuesta avisa cuando nombra objetos que no existen en la fuente: no los uses en un spec.
- El contador muestra los tokens usados hoy; la instalación fija un límite diario por persona y por
  fuente.
- Si el proveedor falla, el mensaje indica el motivo y enlaza a [Abrir Inteligencia artificial](app:/admin/ia).

## Problemas frecuentes

- «El chat de estructura necesita un proveedor de IA»: pídeselo al **Superusuario**; se configura
  en [Abrir Inteligencia artificial](app:/admin/ia) y el resto de la pestaña sigue funcionando.
- «El chat de estructura no lee datos»: la pregunta pedía filas o una acción; pregunta por la
  estructura (qué tabla o campo contiene ese dato).
- «Alcanzaste el límite diario»: vuelve mañana o pide que se suba el límite en
  [Abrir Inteligencia artificial](app:/admin/ia).
