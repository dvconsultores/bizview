/speckit-specify Dashboard de facturación sobre la fuente artemisa (Supabase). Modo autónomo:
decide lo que falte y anótalo en la spec; no me preguntes.

Datos de origen
- Tabla invoices de la fuente artemisa. Confirma nombres reales con describe_source y
  profile_source antes de escribir. Columnas: número de factura, id de pedido, monto, estatus, fecha.
- Sin columnas personales (email, nombre, apellido, teléfono, documento, telegram, paypal_data).
- Verifica la extracción con check_query; no dejes archivos temporales ni de sondeo.

Integración
- Clave primaria: número de factura. Fecha: la de la factura; incremental con ventana de 7 días.
- schedule "0 * * * *". Checks: row_count >= 1 y not_null en número de factura, monto y fecha.

Reporte «Ventas y facturación»
- Métricas: Total facturado (suma del monto, moneda, mejor si sube), Número de facturas (conteo),
  Ticket promedio (total / número de facturas), % pagadas (estatus pagada = "paid").
- Dimensiones: estatus, año y mes de la fecha. Filtros: año, mes y estatus.
- Periodos: mes en curso (por defecto, comparado con el anterior), mes anterior, año en curso,
  últimos 12 meses.
- Vistas en orden: 1) KPIs, 2) tendencia diaria del total, 3) ranking por estatus,
  4) tabla año/mes/estatus con total y número de facturas.
- Título y descripción de negocio, icono de gráfico, KPIs primero, comparación con el periodo previo.
- PDF habilitado, horizontal, con las 4 vistas.