# Los cinco pasos

## Para qué sirve

Es el camino completo, de una fuente de datos a un tablero que se comparte. No hay atajos: los cinco
pasos son los mismos para quien empieza y para quien ya tiene cinco proyectos.

## Quién puede usarlo

Solo el **Superusuario**. Los pasos 1 y 2 tocan credenciales; del 3 al 5, el proyecto. Cuando el
tablero está aplicado, cada rol de su `access` lo ve sin hacer nada.

## Cómo se hace

1. Añade la fuente en [Abrir Fuentes de datos](app:/admin/fuentes) y pulsa **Probar**.
2. Genera su estructura en **Estructura**: es lo que tu IA leerá en lugar de conectarse.
3. Descarga el paquete inicial en **Proyectos** → **Nuevo proyecto**.
4. Rellena `REQUEST.md` y pásale la carpeta a tu IA (o pega `PROMPT.md` en el chat).
5. Importa el zip que te devuelva en **Importar proyecto** y pulsa **Aplicar**.

Abrir [Fuentes de datos](app:/admin/fuentes) · Abrir [Proyectos](app:/proyectos).

## Opciones

- Sin IA también se puede: los archivos son YAML y SQL, y se escriben a mano.
- Si la fuente ya tiene una tabla preparada por otro proceso, el paso 1 se salta y el paquete pide
  un reporte directo.

## Relacionados

- Descargar el paquete inicial
- Pasarlo a tu IA
- Importar un proyecto
