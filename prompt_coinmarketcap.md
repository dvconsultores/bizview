Cierra el proyecto «CoinmarketCap». Modo autónomo: decide lo que falte y anótalo en la spec;
no me preguntes.

Estado de partida (no lo toques si valida)
- Integración mercado-cripto: datasets `assets` (listings de CoinMarketCap, 100 filas) y
  `altcoin_season` (índice 0-100 calculado por captura sobre el mismo listado). Ambos extraen de
  `requests/listings.yaml` y las cargas programadas están en verde. No cambies la integración.
- Reporte panorama-cripto: KPIs + tabla, PDF habilitado. Es lo único que falla.

Lo que hay que arreglar
1. El tablero «Panorama cripto» responde «Conjuntos sin unión: altseason»: el reporte lee los dos
   datasets y no declara ningún join, y un reporte es una sola consulta. Añade el join por la
   captura, que es lo que comparten:

       joins: [{left: assets.snapshot_at, right: altseason.snapshot_at}]

   No cambies métricas, vistas, periodos ni filtros: solo el join (y la spec si explica el modelo
   de datos).
2. `integrations/mercado-cripto/requests/global.yaml`, si sigue ahí, es un sondeo que no alimenta
   ningún dataset y cuya comprobación falla («'$.data' no es una lista en la respuesta»). Bórralo
   con edit_draft; no lo arregles para que pase.
3. Vuelve a pasar check_query sobre `requests/listings.yaml` y confirma ok:true. No dejes archivos
   de sondeo ni temporales.

Cierre
- Valida: el reporte no puede quedar con `unjoined_sets` ni con errores.
- Ejecuta la vista previa y aplica con apply_draft; no me pidas que pulse Aplicar.
- Comprueba el tablero `/r/panorama-cripto`: sin el aviso rojo, con las tarjetas y la tabla.
- Resume al final: archivos que cambiaste, filas de cada dataset y versión aplicada.
