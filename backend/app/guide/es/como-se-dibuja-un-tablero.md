# Cómo se dibuja un tablero

## Para qué sirve

Saber qué hace BizView con lo que escribiste, para no adivinar por qué una cifra cambia de período,
por qué una tarjeta está vacía o por qué el tablero no se parece al `report.yaml`. Aquí va el
recorrido, del aplicar al dibujo.

## Quién puede usarlo

Cualquiera que lea el tablero; el **Superusuario** es quien lo corrige.

## Cómo se hace

1. Aplicar. Al aplicar, BizView valida el proyecto otra vez y lo compone con los demás en una
   versión nueva. Cada `report.yaml` se vuelve un tablero y su `access.roles` decide quién lo abre.
2. Contexto. Los alias de `uses` se resuelven a `ds_<integración>.<conjunto>` y los tipos de
   columna salen del contrato de la integración. Todavía no corre ninguna consulta.
3. Petición. La pantalla envía el período, la comparación y los filtros de la URL. El período se
   convierte en dos fechas inclusivas de la zona horaria de la instalación, no del navegador.
4. Consultas. Cada vista se vuelve una agregación por período. La comparación es una segunda
   corrida sobre el rango anterior, emparejada por clave. Las `formula` se calculan después, y una
   base cero da nulo, no un error.
5. Caché. La selección y la última carga de las integraciones forman la clave: si nada cambió, la
   respuesta llega sin recalcular y la pantalla lo nota por el `ETag`.
6. Dibujo. Con `layout.web` cada componente se ata a una vista por su id; sin layout se dibuja una
   tarjeta por vista. Los números se formatean en el navegador, y el PDF usa el mismo payload.

## Opciones

- Ampliar abre una tarjeta a pantalla completa y la deja compartible como `?ampliar=<id>`.
- Auto-actualizar consulta la versión de datos y recarga cuando la integración trae algo nuevo.
- Un reporte con `materialize: daily` lee el resumen del día y lo dice en la tarjeta.

## Problemas frecuentes

- Una tarjeta dice "sin datos": el período no tiene filas para esa vista; el mensaje nombra el
  conjunto vacío cuando no hay ninguno con datos.
- Una tarjeta muestra un código y una referencia: esa vista falló y las demás no; la referencia
  sirve para buscar sus líneas en el registro del servidor.
- El tablero no se parece al YAML: la validación rebajó parte del layout y las notas sobre la
  rejilla dicen qué componente y por qué.
- Las cifras están viejas: mira la última corrida de la integración en Datos.

## Relacionados

- Definir un reporte
- Qué pasa al importar y aplicar
- Corregir los problemas
- [Abrir Proyectos](app:/proyectos)
