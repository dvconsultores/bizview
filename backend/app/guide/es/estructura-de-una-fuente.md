# Estructura de una fuente

## Para qué sirve

Muestra qué contiene una conexión para que puedas escribir su spec: esquemas, tablas y vistas con
sus columnas, tipos, claves, número aproximado de filas y el rango de fechas; en una fuente REST o
Supabase, las peticiones de muestra con la forma de su respuesta; en SOAP, las operaciones. Nunca
muestra datos de las filas.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Abre [Abrir Fuentes de datos](app:/admin/fuentes) y entra en la fuente.
2. Pulsa la pestaña **Estructura**: BizView lee la fuente (solo la estructura) y la muestra.
3. Usa **Buscar tabla o columna** para encontrar un objeto en un catálogo grande.
4. Pulsa **Descargar estructura (.md)** o **Descargar estructura (.json)** para llevarla al paquete
   de autoría: son los archivos `sources/<nombre>/structure.md` y `structure.json`. Si generaste el
   paquete con IA (ver Generar estructura con IA), lo que se descarga es ese paquete; si no, el
   escaneo.
5. Escribe lo que falte en **Observaciones** y pulsa **Guardar observaciones**: ese texto viaja en
   la sección «Observaciones» de la descarga.
6. Con una fuente que cambió, pulsa **Actualizar** para volver a leerla.

## Opciones

- La etiqueta **personal** marca las columnas que parecen datos personales (correo, nombre,
  teléfono, documento, identificadores de chat). Púlsala para cambiarla: la elección se guarda y se
  mantiene en la descarga.
- El rango de **Fechas** sale del mínimo y el máximo de hasta tres columnas de fecha por tabla.
- El botón **Generar estructura con IA** completa esta lectura con tablas lógicas, relaciones y
  notas; el resultado es lo que se descarga.
- Si el catálogo es muy grande, la estructura se trunca y la descarga lo dice en sus observaciones.

## Problemas frecuentes

- «La fuente respondió HTTP…» o un error de red: revisa la conexión en la pestaña **Conexión** y
  pulsa **Probar conexión**.
- Una tabla que esperabas no aparece: la credencial quizá no tiene permiso de lectura sobre ella.
