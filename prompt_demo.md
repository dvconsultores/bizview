Hola. Necesito un dashboard de facturación sobre la fuente «Cliente C».

Datos de origen
- Tabla: invoices (o invoice; confírmalo con describe_source). Columnas que quiero: número de factura (invoice number), id de pedido (order id), monto, estatus y fecha. Confirma los nombres reales con describe_source y profile_source antes de escribir nada.
- No incluyas columnas con datos personales (email, nombre, teléfono, documento) aunque existan.
- Comprueba la extracción con check_query. No agregues archivos temporales ni de sondeo al borrador.

Integración
- Clave primaria: el número de factura.
- Columna de fecha: la fecha de la factura. Carga incremental con ventana de 7 días.
- Actualización cada hora: schedule "0 * * * *".
- Checks: row_count mínimo 1 y not_null en número de factura, monto y fecha.

Reporte «Ventas y facturación»
- Métricas:
  - Total facturado (suma del monto, formato moneda, mejor si sube).
  - Número de facturas (conteo).
  - Ticket promedio (total / número de facturas).
  - % pagadas (facturas con estatus pagada sobre el total; antes confirma los valores posibles de estatus con profile_source).
- Dimensiones: estatus, año y mes de la fecha.
- Filtros: año, mes y estatus.
- Periodos permitidos: mes en curso, mes anterior, año en curso y últimos 12 meses; por defecto el mes en curso, comparado con el periodo anterior.
- Vistas, en este orden:
  1. KPIs con las 4 métricas.
  2. Tendencia diaria del total facturado.
  3. Ranking del total por estatus.
  4. Tabla por año, mes y estatus con total y número de facturas.
- Que se vea atractivo para vender: título y descripción claros orientados al negocio, icono de gráfico, KPIs primero y comparación con el periodo anterior.
- PDF habilitado, orientación horizontal, con todas las vistas.

Proceso
Lee get_authoring_guide('example-supabase') una sola vez. Haz un único borrador completo con specs (spec, plan, tasks) de integración y de reporte, corrige con edit_draft y ejecuta run_preview. Pregúntame solo lo que no puedas inferir. Avísame cuando esté «Listo para aplicar».
4244010467