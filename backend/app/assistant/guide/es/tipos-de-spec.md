# Tipos de spec

## Para qué sirve

Cada spec tiene un tipo en su línea `**Tipo**:` que dice qué produce.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

- **Fuente**: documenta una fuente de datos que se registra en
  [Abrir Fuentes de datos](app:/admin/fuentes). No produce archivos; se cumple cuando la fuente
  existe y su prueba es correcta.
- **Integración**: produce `integrations/<id>/`, una carga programada desde una fuente a la base
  BI (ver Definir una integración).
- **Reporte**: produce `reports/<id>/report.yaml`, un tablero. Puede leer datasets de
  integraciones o, en modo directo, una tabla existente sin ETL (ver Reportes directos).
- **Distribución**: produce `distributions/<id>.yaml`, envíos programados de un reporte por rol y
  su política de enlaces (ver Distribuciones).

## Opciones

- Un proyecto puede tener una sola spec: por ejemplo, un único reporte directo sobre una tabla que
  ya existe.
- Para un tablero nuevo con datos de un sistema operativo, el orden habitual es fuente,
  integración, reporte y, si hace falta, distribución.
