-- Pedidos de venta leídos de solo lectura por la ventana incremental.
-- Devuelve exactamente las columnas de `transform.input` en el mismo orden.
SELECT
  p.numero AS numero,
  p.creado_en AS creado_en,
  p.cliente_id AS cliente_id,
  p.moneda AS moneda,
  p.monto_neto AS monto_neto,
  p.impuesto AS impuesto
FROM ventas.pedidos p
WHERE p.creado_en >= :window_start AND p.creado_en < :window_end
