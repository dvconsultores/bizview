# Peticiones de muestra

## Para qué sirve

En una fuente REST o Supabase, guarda las rutas que quieres documentar. BizView las ejecuta con la
credencial guardada y muestra la forma de la respuesta: qué claves trae, de qué tipo, cuál es el
arreglo de registros y qué campos conviene declarar. No guarda los valores de la respuesta.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre la fuente y entra en la pestaña **Estructura**.
2. En **Peticiones de muestra**, escribe el **Nombre**, la **Ruta relativa** (por ejemplo
   `v1/cryptocurrency/listings/latest`) y los parámetros como `clave=valor` separados por coma.
3. Pulsa **Agregar petición**.
4. Pulsa **Ejecutar** en la petición: verás **Registros**, **Campos sugeridos**, **Fechas** y
   **Paginación**.
5. La misma información viaja en la descarga de la estructura.

## Opciones

- La ruta siempre es relativa a la dirección de la fuente: no se aceptan URLs completas.
- Solo se ejecutan peticiones GET, para que la credencial de la fuente no pueda escribir.
- **Quitar petición** la elimina de la fuente.

## Problemas frecuentes

- «La ruta debe ser relativa a la URL base de la fuente»: quita la parte `https://…` y la barra
  inicial.
- «La fuente respondió HTTP 403»: la credencial no tiene acceso a esa ruta.
- «La respuesta no es JSON»: la ruta devuelve otro formato; documenta la estructura a mano en las
  observaciones.

## Relacionados

- Estructura de una fuente
- Integraciones
- ETL y transformaciones
