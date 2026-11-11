# Quickstart — 064

1. Open any report; on a bar card use `⋯ → Ver como tabla` or the table icon beside **Ampliar**.
2. Search `vacuna`, sort by the metric, press **Copiar**, then **Descargar CSV**.
3. Open a truncated ranking and press **Ver todas las filas**; page through the 50-row pages.
4. Open `?ampliar=<id>&tabla=<id>` and move with ← →: the table stays selected.
5. Set `interactions: {data_table: false}` or component `data_table: false` and confirm the entry
   points disappear.

Backend check:

```bash
curl -s 'http://localhost:8000/api/reports/ventas/data?period=mtd&full=1' | jq '.views[] | select(.type=="ranking") | {n:(.items|length), truncated}'
```
