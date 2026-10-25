Cierra el proyecto «CoinmarketCap». Modo autónomo: decide lo que falte y anótalo en la spec;
no me preguntes.

Estado de partida (no lo toques si valida)
- Integración mercado-cripto: datasets `assets` (listings de CoinMarketCap, 100 filas) y
  `altcoin_season` (índice 0-100 calculado por captura sobre el mismo listado). Ambos extraen de
  `requests/listings.yaml`. La vista previa terminó bien y el proyecto está aplicado.
- Reporte panorama-cripto: KPIs + tabla, PDF habilitado. Déjalo como está salvo que falle al
  validar.

Lo que hay que arreglar
1. `integrations/mercado-cripto/requests/global.yaml` es un sondeo que no alimenta ningún dataset
   y cuya comprobación falla: check_query devuelve «'$.data' no es una lista en la respuesta»
   (las métricas globales de CoinMarketCap devuelven `data` como objeto, no como lista). Bórralo
   con edit_draft; no lo "arregles" para que pase, no hace falta.
2. Vuelve a pasar check_query sobre `requests/listings.yaml` y confirma ok:true con las columnas
   que usan los dos datasets (id, symbol, cmc_rank, price, pct_change_24h, pct_change_90d,
   market_cap, volume_24h, tags, last_updated).
3. No dejes archivos de sondeo ni temporales en el proyecto.

Cierre
- Ejecuta la vista previa y aplica con apply_draft; no me pidas que pulse Aplicar.
- Resume al final: archivos que cambiaste, filas de cada dataset y versión aplicada.
