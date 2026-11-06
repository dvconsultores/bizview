# Ejemplo completo: ventas por marca

## Para qué sirve

Es el recorrido entero con un caso pequeño: una fuente con las ventas, un tablero que las agrupa por
marca y una persona que lo abre en el teléfono. Sirve para ver qué se escribe en cada paso.

## Quién puede usarlo

Solo el **Superusuario**, que es quien recorre los cinco pasos. Al final, el rol de `access` lo ve.

## Cómo se hace

1. Fuente: en [Abrir Fuentes de datos](app:/admin/fuentes), una conexión PostgreSQL de solo lectura a la base de
   ventas. Se prueba y queda registrada como `Origen ventas`.
2. Estructura: en **Estructura**, se genera el documento de la fuente. Muestra la tabla
   `reporting.ventas` con `fecha`, `marca`, `comprobante_id` y `monto_total`.
3. Paquete: en **Proyectos** → **Nuevo proyecto**, nombre «Ventas por marca», fuente `Origen ventas`,
   idioma español, primera spec «Integración y reporte».
4. Petición: `REQUEST.md` dice «cuánto vendemos por marca este mes, para el gerente comercial, en el
   teléfono, con filtro de marca y período de últimos 7 días».
5. Tu IA: se le pasa `PROMPT.md`, `REQUEST.md` y `structure.md`; devuelve un zip con `project.yaml`,
   `specs/001-ventas-por-marca`, `specs/002-ventas-por-marca-reporte`,
   `integrations/ventas-por-marca` y `reports/ventas-por-marca`.
6. Importar: **Importar proyecto** con ese zip. No hay problemas: el proyecto queda en borrador.
7. Aplicar: **Aplicar proyecto**. La integración corre una vez y el tablero aparece en `/r/ventas-por-marca`.
8. Compartir: se abre el tablero y se comparte un enlace, o se programa un envío por correo al rol.

Abrir [Proyectos](app:/proyectos) · Abrir [Fuentes de datos](app:/admin/fuentes).

## Opciones

- La misma historia con un reporte directo: si `reporting.v_ventas_dia` ya existe y la fuente admite
  reportes directos, el paso 3 elige «Reporte directo» y no hay integración.
- Se puede repetir todo con la CLI: `bizview init project "Ventas por marca" --source "Origen ventas"`
  y `bizview validate`.

## Problemas frecuentes

- Si el tablero muestra ceros, mira la última ejecución en **Integraciones**: puede que la consulta
  filtre por una fecha que no existe en los datos.
- Si la importación lista archivos ignorados, son los del paquete (`PROMPT.md`, `sources/`), no el
  proyecto.

## Relacionados

- Los cinco pasos
- Importar un proyecto
- Qué pasa al importar y aplicar
