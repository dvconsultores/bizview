# Reportes directos

## Para qué sirve

Un reporte directo lee una tabla en vivo, sin integración ni ETL: de una fuente PostgreSQL que lo
permite o de la base BI de esta instalación (la fuente `bi`).

## Quién puede usarlo

Lo configura el **Superusuario**. Quien ve el reporte (cualquier **Usuario** con acceso) nota que
es directo por la marca de datos en vivo.

## Cómo se hace

1. Si la tabla está en una fuente PostgreSQL, abre la fuente en
   [Abrir Fuentes de datos](app:/admin/fuentes) y marca **Permitir reportes directos** (se pide
   confirmar tu contraseña). La base BI de la instalación ya lo permite.
2. Escribe una spec `reporte` en modo directo y deja que el agente la implemente (ver Un reporte
   directo paso a paso).
3. Al verlo, el reporte dice «Datos en vivo · … · consultado …».

## Opciones

¿Directo o integración?

- **Directo**: los datos ya los prepara otro proceso (por ejemplo, un cierre nocturno o una
  vista), la tabla tiene un índice por fecha, el volumen es moderado y quieres verlos al momento.
- **Integración**: necesitas guardar historia, cargar por partes desde sistemas operativos,
  transformar o unir datos, o la fuente es REST, SOAP o Supabase.

Además:

- Las tablas internas de BizView nunca se pueden leer en directo.
- Las respuestas se guardan en caché unos minutos (`cache_seconds` del reporte).

## Problemas frecuentes

- «Datos de …; la fuente no respondió»: se muestran los últimos datos guardados.
- «La fuente está ocupada»: hay demasiadas consultas en curso; vuelve a intentarlo.
- Si la estructura de la tabla cambió, el reporte muestra el error y la spec debe actualizarse.
