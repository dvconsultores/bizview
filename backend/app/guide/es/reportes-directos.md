# Reportes directos

## Para qué sirve

Un reporte directo lee una tabla en vivo, sin integración ni ETL: de una fuente PostgreSQL que lo
permite o de la base BI de esta instalación (la fuente `bi`).

## Quién puede usarlo

Lo configura el **Superusuario**. Quien ve el reporte (cualquier **Usuario** con acceso) nota que
es directo por la marca de datos en vivo.

## Cómo se hace

1. Si la tabla está en una fuente PostgreSQL, abre la fuente en
   [Abrir Fuentes de datos](app:/admin/fuentes), marca **Lista para BI** y declara los esquemas (y,
   si quieres, los objetos) que los reportes pueden leer, con su tiempo máximo, su caché y su tope
   de filas (se pide confirmar tu contraseña). Bizview comprueba entonces que la credencial no puede
   escribir, y lo vuelve a comprobar cada día. La base BI de la instalación ya está declarada.
2. Escribe una spec `reporte` en modo directo y que tu IA la implemente (ver Un reporte directo
   paso a paso).
3. Al verlo, el reporte dice «Datos en vivo · … · consultado …».

## Opciones

¿Directo o integración?

- Con `materialize: daily`, si la fuente tarda: el reporte guarda sus cifras una vez al día y
  todos lo leen de ahí, con el aviso de que son de ayer. No guarda filas ni crea tablas intermedias:
  es la misma consulta, una vez al día.
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

## Relacionados

- Definir un reporte
- Un reporte directo paso a paso
- Integraciones
