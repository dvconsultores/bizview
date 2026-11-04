# Data model — three tables, one column, two file shapes

Everything here is metadata about a source. No value read from a source row is ever stored: the
only aggregates kept are the ones the pack prints (estimated rows, `min`/`max` of a date column).

---

## `data_source.notes` (new column)

| Column | Type | Meaning |
|---|---|---|
| `notes` | `text not null default ''` | the super user's "Observaciones": what the source does not have, plan/budget notes. Printed in `structure.md` and carried in `structure.json` |

The chat may *draft* this text; only the person saving it writes it (US2/AC3).

---

## `source_sample_request`

One saved sample request of a REST or Supabase source (FR-002). Never holds secrets: the credential
is the source's own.

| Column | Type | Notes |
|---|---|---|
| `id` | `bigint identity` PK | |
| `source_id` | `bigint` FK `data_source(id)` on delete cascade | |
| `name` | `text` | 1–80 chars, unique per source ignoring case |
| `method` | `text` default `'GET'` | stored for US3; this delivery runs `GET` only (research R6) |
| `path` | `text` | relative to the source's base URL, no scheme, no host |
| `params` | `jsonb` default `'{}'` | query parameters, string→string, ≤ 50 entries |
| `notes` | `text` default `''` | what the sample is for |
| `last_shape` | `jsonb null` | keys and types only — the value `describe.shape()` builds |
| `last_suggestions` | `jsonb null` | `{records, fields, timestamp_units, pagination}` |
| `last_status` | `int null` | HTTP status of the last run |
| `last_error` | `text null` | the product's own line (no secrets, no host) |
| `last_run_at` | `timestamptz null` | |
| `created_at`, `updated_at` | `timestamptz` | |

Checks: `method IN ('GET')` for now, `path` has no `://`, `name` length 1–80.

## `source_structure_flag`

The super user's override of the personal-data heuristic, per column (US1/AC1).

| Column | Type | Notes |
|---|---|---|
| `source_id` | `bigint` FK `data_source(id)` on delete cascade | in the PK |
| `schema_name` | `text` | `''` for REST/Supabase/SOAP |
| `table_name` | `text` | |
| `column_name` | `text` | |
| `personal` | `boolean` | the chosen value, heuristic ignored |
| `updated_at` | `timestamptz` | |

PK `(source_id, schema_name, table_name, column_name)`. Only overrides are stored: absence means
"use the heuristic".

## `source_chat_message`

One row per turn of the structure chat, which is also the usage record the daily cap reads.

| Column | Type | Notes |
|---|---|---|
| `id` | `bigint identity` PK | |
| `source_id` | `bigint` FK `data_source(id)` on delete cascade | |
| `user_id` | `bigint` FK `app_user(id)` on delete cascade | |
| `role` | `text` | `question` \| `answer` |
| `text` | `text null` | stored only when `AI_STRUCTURE_CHAT_STORE_QUESTIONS=on` |
| `tokens_in` | `int` default 0 | provider usage for this turn |
| `tokens_out` | `int` default 0 | |
| `created_at` | `timestamptz` default `now()` | index `(source_id, user_id, created_at)` |

Retention: rows older than 30 days are deleted by the worker's hourly `housekeeping()`.

---

## `structure.json`

```json
{
  "pack": {
    "version": 1,
    "source": "coinmarketcap",
    "kind": "rest",
    "generated_at": "2026-11-03T12:00:00+00:00",
    "bi_ready": false,
    "notes": "Plan free: 333 llamadas/día.",
    "truncated": false
  },
  "structure": { "kind": "rest", "path": "/v1/cryptocurrency/listings/latest", "shape": { } }
}
```

`structure` is exactly what `GET /api/sources/{name}/describe` returned, with these additions:

- PostgreSQL tables gain `foreign_keys: [{"column": "order_id", "references": "orders.id"}]` and each
  date/timestamp column gains `"range": {"min": "2023-01-01", "max": "2026-11-02"}` (omitted when it
  could not be read);
- each PostgreSQL column gains `"personal": true` when the heuristic (or an override) says so;
- REST/Supabase samples are listed under `structure.samples` with their shape and suggestions;
- SOAP is what it is today.

`bizview validate --describe NAME=FILE` and `structure_from()` accept the wrapper and the bare
describe object: when `pack` is present they read `structure`.

## `structure.md`

Byte-for-byte the sections of `pack/bizview-starter-pack/bizview-starter/sources/<nombre>/structure.md`,
filled and without the template comments:

- header: `Tipo: postgresql | rest | soap · Zona horaria de los datos: … · Notas: …`
- `## PostgreSQL`: `### Esquema `<schema>`` then `#### Tabla `<tabla>` — ~<n> filas · fecha:
  `<columna>` (<min> → <max>)` and the `Columna | Tipo | Nulo | Clave | Personal | Nota` table
- `## REST`: `Base: configurada en Bizview (no se incluye) · Autenticación: gestionada por Bizview`,
  then one `### Petición `<nombre>` — GET `<ruta>`` block with params, pagination, `records` and the
  JSONPath table
- `## SOAP`: `Operación `<nombre>`: entrada … salida …`
- `## Observaciones`: the notes, one bullet each, plus the generated ones (truncated catalogue,
  columns flagged personal, BI-ready flag when set)

Sections that do not apply are omitted, as the template instructs.

---

## Chat request and answer

`POST /api/sources/{name}/chat` — `{"question": "…"}` →

```json
{
  "answer": "La tabla `orders`…",
  "refused": false,
  "unknown": [{"name": "ventas_fantasma", "kind": "table"}],
  "model": "claude-opus-5-5",
  "usage": {"tokens_in": 812, "tokens_out": 240, "spent_today": 1052, "cap": 100000},
  "created_at": "2026-11-03T12:00:03+00:00"
}
```

A refused question answers `{"answer": "<the standard line>", "refused": true, "unknown": [],
"usage": {…}}` with no provider call and no tokens counted. `unknown` is empty when the answer
mentions nothing the pack does not know.

`GET /api/sources/{name}/chat` → `{"turns": [{"role": "question", "text": "…", "at": "…"},
{"role": "answer", "text": "…", "unknown": [], "at": "…"}], "cap": 100000, "spent_today": 1052}`
(the `text` is `null` for stored-when-disabled turns).
