-- The read the worker runs. One SELECT or WITH, read-only, no `;` chains.
-- La lectura que ejecuta el worker. Un SELECT o WITH, de solo lectura, sin cadenas con `;`.
-- :window_start and :window_end are declared in integration.yaml (extract.params).
-- :window_start y :window_end se declaran en integration.yaml (extract.params).
-- Dates: CAST(strftime(col, '%Y-%m-%d') AS DATE) whenever a transform needs a day.
SELECT
    c.id            AS comprobante_id,   -- REEMPLAZA: la columna real / the real column
    c.fecha::date   AS fecha,
    c.estado        AS estado,
    c.sucursal      AS sucursal,
    c.monto_total   AS monto_total
FROM public.comprobantes c               -- REEMPLAZA: tu tabla / your table
WHERE c.fecha >= :window_start AND c.fecha < :window_end
