# Tokens de acceso

## Para qué sirve

Un token permite que la línea de comandos `bizview describe` lea la estructura de las fuentes
(tablas y columnas, nunca datos) mientras escribes specs en tu equipo.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre [Abrir Tokens de acceso](app:/admin/tokens).
2. Pulsa **Nuevo token**, escribe un **Nombre** (por ejemplo, tu portátil) y elige
   **Vence en (días)**.
3. Pulsa **Crear token** y cópialo: no se volverá a mostrar.
4. En tu equipo, úsalo con `bizview describe`.

## Opciones

- La lista muestra cuándo vence cada token y su último uso.
- Revoca un token que ya no uses; los tokens revocados o vencidos dejan de funcionar al momento.
- Crear y revocar tokens queda en la auditoría.
