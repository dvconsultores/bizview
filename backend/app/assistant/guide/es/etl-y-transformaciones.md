# ETL y transformaciones

## Para qué sirve

Explica qué hace BizView cuando corre una integración, para entender sus tiempos y sus errores.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

Cada ejecución sigue estos pasos:

1. Extracción: de PostgreSQL se lee con COPY (rápido); de REST, SOAP y Supabase, con las
   peticiones definidas en `requests/*.yaml`.
2. Ventana: una carga incremental lee solo los últimos días (`window_days`, con
   `:window_start` y `:window_end` en la consulta); `mode: full` lee todo cada vez.
3. Transformación (opcional): si la integración define `transform`, los datos pasan por Polars
   (por lotes o completa) antes de guardarse. `TRANSFORM_MAX_ROWS` limita cuántas filas puede
   transformar de una vez.
4. Carga: los datos se guardan en el esquema `ds_<integración>` por su clave primaria, así que
   repetir una ejecución no duplica filas.
5. Chequeos: si un chequeo falla, la carga se descarta y se conservan los datos anteriores.

## Problemas frecuentes

- Una ejecución **Omitida** no encontró nada que hacer o la fuente no estaba disponible; revisa
  el **Historial** en [Abrir Integraciones](app:/admin/integraciones).
