-- Facturas emitidas dentro de la ventana incremental.
-- El filtro usa :window_start y :window_end declarados en integration.yaml.
SELECT
    f.numero AS numero,
    f.fecha::date AS fecha_emision,
    f.creada_en AS emitida_en,
    f.cliente_id AS cliente_id,
    f.estado AS estado,
    f.moneda AS moneda,
    f.monto_neto AS monto_neto,
    f.impuesto AS impuesto,
    f.monto_total AS monto_total
FROM ventas.facturas f
WHERE f.creada_en >= :window_start AND f.creada_en < :window_end
