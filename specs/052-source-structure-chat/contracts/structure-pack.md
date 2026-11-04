# Contract — the structure pack

Two files, one generator (`cli/bizview_cli/structure.py`), three callers: `bizview describe
--pack`, `GET /api/sources/{name}/structure?format=md|json`, and (later) the authoring pack zip.

The reference is `pack/bizview-starter-pack/bizview-starter/sources/<nombre>/structure.md`: when
this feature and that template disagree, the template wins and this contract is wrong.

---

## What the pack must contain

| Source kind | Required | Forbidden |
|---|---|---|
| postgresql | schemas, tables and views, columns with type and nullability, primary and foreign keys, estimated row count, `min`/`max` of up to 3 date columns per table, the personal flag | any row value, the host, the database name, the user, the credential, the connection string |
| rest | one block per saved sample: method, relative path, query parameter **names** and non-secret values, response shape (keys and types), `records` JSONPath, `fields` JSONPath map, `timestamp_units`, pagination hint | the base URL, the credential, any response value (dates and enums are described by *format*, never by an example), array contents beyond their shape |
| supabase | tables and columns from the API's own description, plus the same REST blocks for samples | same as rest |
| soap | services, ports, operations, input/output signatures | the WSDL URL, the credential |

`structure.json` adds a `pack` header (see [data-model.md](../data-model.md#structurejson)) and
nothing else: the body is the describe output.

## Rules the generator enforces

1. **Absolute paths are refused**, never normalised: a sample `path` that is a URL or starts with
   `/` is a 422 at save time and an error line in the pack.
2. **Truncation is stated**: when the catalogue exceeded the caps, `pack.truncated` is `true` and
   `structure.md` says so under `## Observaciones` — a silent cut looks like a complete answer.
3. **Sections that do not apply are omitted**, per the template's instruction.
4. **The notes go in two places**: the header line and the `## Observaciones` bullets, because the
   template shows both.
5. **The BI-ready flag appears only when the source is declared** (`structure.bi_ready`), with the
   scopes it names — 048 says a declaration is the whole truth and the pack must say it.

## The markdown skeleton (filled, comments removed)

```markdown
# Fuente «coinmarketcap» — estructura

Tipo: rest · Zona horaria de los datos: UTC · Notas: Plan free: 333 llamadas al día.

## REST

Base: configurada en Bizview (no se incluye) · Autenticación: gestionada por Bizview

### Petición `listados` — GET `v1/cryptocurrency/listings/latest`

Params: `limit=100`. Paginación: none.
`records: "$.data"`. Campos por elemento:

| JSONPath | Tipo | Nota |
|---|---|---|
| `$.id` | integer | |
| `$.last_updated` | string (ISO 8601) | usar como fecha |

## Observaciones

- El catálogo se truncó: 300 de 1 240 tablas.
- Datos personales: `customer_email`.
```

## Parity test

`backend/tests/test_source_structure.py` runs the generator twice on the same fixture — once through
`bizview_cli.structure.build_pack()` and once through the API — and compares both files byte for
byte. That is the only thing that keeps "one generator" true over time.
