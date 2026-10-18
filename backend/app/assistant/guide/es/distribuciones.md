# Distribuciones

## Para qué sirve

Una spec de tipo distribución define cómo se reparte un reporte del proyecto: envíos programados
por correo y la política de enlaces compartidos. Se aplica junto con el proyecto.

## Quién puede usarlo

Solo el **Superusuario** la escribe; los envíos llegan a los usuarios de los roles elegidos.

## Cómo se hace

1. Escribe la spec con `/speckit-specify` (por ejemplo «envío semanal del reporte de ventas a
   los administradores») y sigue el método hasta `/speckit-implement`.
2. El agente escribe `distributions/<id>.yaml`:
   - `report`: el id del reporte que se envía.
   - `subscriptions`: cada envío con `frequency` (`daily`, `weekly` o `monthly`), `hour`,
     `weekday` o `monthday`, `period`, `recipients` por rol (`admin` o `user`), `attach_pdf` y
     `link_days`.
   - `share`: `allowed` (si se permiten enlaces compartidos del reporte) y `max_days`.
3. Aplica el proyecto.

## Opciones

- Los destinatarios son siempre roles, nunca direcciones de correo.
- En la pantalla del tablero, un envío de un proyecto aparece como
  **Gestionado por el proyecto** …: allí solo se puede pausar o reanudar.
- Los envíos hechos a mano en **Envíos programados** no dependen de ningún proyecto.
