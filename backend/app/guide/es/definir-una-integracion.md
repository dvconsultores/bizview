# Definir una integración

## Para qué sirve

Explica qué lleva `integrations/<id>/integration.yaml`, el archivo que dice qué datos cargar, de
dónde, cada cuánto y cómo validarlos.

## Quién puede usarlo

Solo el **Superusuario**; normalmente lo escribe el agente con `/speckit-implement`.

## Cómo se hace

Campos principales:

- `source`: el nombre de la fuente registrada.
- `schedule`: la frecuencia (expresión cron, por ejemplo cada hora).
- `datasets`: uno o varios conjuntos de datos; cada uno se vuelve una tabla en `ds_<id>`. Por
  dataset:
  - `extract`: `query: queries/<nombre>.sql` (un solo SELECT de solo lectura que filtra con
    `:window_start` y `:window_end`) o `request: requests/<nombre>.yaml` para REST o SOAP.
  - `columns`: cada columna con su tipo.
  - `primary_key`: las columnas que identifican cada fila.
  - `incremental`: `window_days` (los últimos N días) o `mode: full` (todo cada vez).
  - `checks`: validaciones como `row_count`, `not_null` o `reconcile` (solo PostgreSQL).
  - `transform` (opcional): un SELECT sobre `input` que corre en Polars antes de guardar.

## Opciones

- La spec de la integración lista en `**Datos personales**:` las columnas personales que se
  incluyeron a pedido.
- Para ver un ejemplo completo, pide al agente la guía de autoría o descarga un proyecto aplicado.
