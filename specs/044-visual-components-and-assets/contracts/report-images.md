# Contract — `images:` in a report and `image:` on a component

Additions to `cli/bizview_cli/schemas/report.schema.json`, which is the single source: the CLI
validator, the importer and the backend all read it.

## `images` (new, top level of `report.yaml`)

```json
"images": {
  "description": "Conjuntos de imágenes del reporte: cada uno resuelve una clave a un archivo del proyecto, a una URL cacheada o al relleno declarado.",
  "type": "object",
  "additionalProperties": { "$ref": "#/$defs/imageSet" },
  "maxProperties": 20
}
```

With `imageSet`:

```json
"imageSet": {
  "type": "object",
  "additionalProperties": false,
  "required": ["key"],
  "properties": {
    "folder":   { "type": "string", "pattern": "^assets/[a-z0-9][a-z0-9._/-]*$" },
    "column":   { "type": "string", "pattern": "^[a-z][a-z0-9_]{0,40}\\.[a-z][a-z0-9_]{0,40}$" },
    "key":      { "type": "string", "pattern": "^[a-z][a-z0-9_]{0,40}$" },
    "fallback": { "enum": ["initial", "none"], "default": "initial" }
  },
  "oneOf": [{ "required": ["folder"] }, { "required": ["column"] }]
}
```

Rules the schema cannot express, enforced by `bizview validate`:

1. `folder`, when present, exists in the project and contains at least one allowed image.
2. `column`, when present, names a declared dataset column the report uses.
3. `key` names a declared dimension, a column of a dataset the report uses, or a metric id — the
   last one because a `kpi` tile has no row, so its only stable identity is the metric it shows
   (`images: {coins: {folder: assets/coins, key: precio_btc}}`).
4. A set with neither `folder` nor `column` is an error (schema's `oneOf`); a set with `column` only
   is valid but warns that nothing is cached until the integration runs.

## `image` on a component

```json
"image": {
  "description": "Conjunto de imágenes (clave de `images`) usado por el componente: en table, la imagen de la celda de la columna clave; en kpi y asset, junto a la etiqueta.",
  "type": "string",
  "pattern": "^[a-z][a-z0-9_]{0,40}$"
}
```

Allowed on `table`, `kpi` and `asset`. On any other component type the validator refuses it with a
message that names the types that accept it — the alternative, silently ignoring it, is how an author
loses an afternoon.

## Interaction with the asset tile's positional `columns` (research R5)

```yaml
views:
  - type: asset
    columns: [logo_url, name, symbol, price, change]   # positional, already documented
    image: coins                                       # new: where the pictures come from
```

- `columns[0]` (the image slot) names the **column whose value is the key**.
- `image` names the **set** that turns that key into a picture.
- With `image` absent, `columns[0]` keeps today's behaviour (a URL rendered as-is), so every report
  written since 042 keeps working.
- With `image` present, the set's own `key` wins over `columns[0]`: the picture comes from the
  project, not from the row.

## What the client receives (T017)

The report payload gains one `images` entry per declared set. It never carries a file name: the
browser appends the row key and the server resolves the file.

```json
"images": {
  "coins": {
    "key": "symbol",
    "fallback": "initial",
    "url": "/api/reports/cripto-panorama/assets/coins/"
  },
  "logos": { "key": "symbol", "fallback": "initial", "column": "l.logo_url" }
}
```

- `url` is present for a folder set and names the door the client came through:
  `/api/reports/<id>/assets/<set>/` for a signed-in reader, `/api/shared/<token>/assets/<set>/` for
  a share link. A column set has no `url` until the image cache serves one.
- `GET <url><key>` answers with the bytes, an `ETag` and `private, max-age=31536000, immutable`.
  The lookup is exact case, then case-insensitive, then `png`, `svg`, `webp`, `jpg`, `jpeg`
  (research R3), so `BTC.png`, `btc.svg` and `btc.webp` all answer for `BTC`.
- The key is normalised the same way on both sides (`app/projects/assets.normalise_key`): `/` and
  spaces become `_`, so the row value `HYPE/USD` is requested as `HYPE_USD`.
- A key with no file answers `404`; the client draws the declared fallback and never retries a
  guess.

## PDF

The four component kinds are also block kinds in a PDF layout:

```yaml
pdf:
  blocks:
    - { kind: gauge, metric: fear_greed, min: 0, max: 100, bands: [...], label_metric: fear_label }
    - { kind: index, metric: btc_season, min: 0, max: 100, left_label: Bitcoin, right_label: Altcoin }
    - { kind: share, parts: [{metric: btc_dominance, label: BTC}], rest_label: Otros }
    - { kind: asset, metric: btc_price, change_metric: btc_change, image: coins }
```

Figures must equal the screen's, digit for digit; images are embedded as raster (R3), and an
SVG-only set draws the same initial-circle the screen would draw for a missing file.

## Compatibility

- Reports without `images` and without `image` validate and render exactly as before.
- A report using `image` on a component type that does not accept it fails validation with the list
  of types that do.
- An installation older than this feature refuses a project that declares `images` at import, with
  the schema error it already produces for unknown keys — which is the intended "no silent drop".
