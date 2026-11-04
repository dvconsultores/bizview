# Research — 052, the eight questions that decide the shape

Each entry is the decision, the alternative rejected, and the evidence in the repository that made
one of them cheap and the other expensive.

---

## R1 — Where the generator lives

**Decision**: `cli/bizview_cli/structure.py`.

**Evidence**: `backend/app/projects/zip.py` already does `from bizview_cli import budgets as
shared_budgets` and reads package data with `importlib.resources.files("bizview_cli")`; the backend
image copies `cli/` next to `backend/` (`backend/Dockerfile`, `COPY cli /app/cli`). The constitution
states that "the validator schemas in `cli/bizview_cli/schemas/` and the SQL rules beside them are
the single source of the authoring contract. The CLI, the backend and the authoring pack MUST read
them from that one place; a duplicated copy is a defect".

**Rejected**: a backend module plus a CLI copy — two generators, guaranteed to drift; a backend
module fetched by the CLI over HTTP — the CLI must work with only `BIZVIEW_URL`/`BIZVIEW_TOKEN` and
offline for `--json` input.

## R2 — How faithful `structure.md` must be

**Decision**: fill `pack/bizview-starter-pack/bizview-starter/sources/<nombre>/structure.md` section
by section, in the same order and with the same headings, dropping only the sections that do not
apply (the template says so: "Borra la sección que no aplique").

The template's headings are the contract: `Tipo: … · Zona horaria … · Notas: …`, `## PostgreSQL`,
`### Esquema`, `#### Tabla … — ~n filas · fecha: … (<min> → <max>)`, the column table with
`Columna | Tipo | Nulo | Clave | Personal | Nota`, `## REST` with `### Petición <nombre> — GET
<ruta>`, `## SOAP`, `## Observaciones`.

**Rejected**: a richer markdown of our own — an author's AI is told to read this file, and 043
WS-B promised the pack "en el formato del pack".

## R3 — Date ranges without reading rows

**Decision**: `SELECT min(col), max(col)` per date/timestamp column, at most 3 per table, inside
the same connection the describe already opens; only the two aggregates leave the source.

**Why it is allowed**: 043 WS-B names "min/max of date columns (counts only)" and the pack template
prints `<min> → <max>` in the table heading. A `min`/`max` is an aggregate — the same class of data
as the row counts `reltuples` already provides — and no row is returned, stored or shown.

**Rejected**: counting rows with `count(*)` (slow on customer tables, and `reltuples` is enough);
skipping date ranges (then the pack's heading cannot be filled).

Failure mode: a column whose type cannot be aggregated (arrays, JSON) is skipped; a query that
fails is skipped silently — a structure read must never fail because one range did not.

## R4 — Refusing "dame 5 filas" in code, not only in the prompt

**Decision**: `chat.refusal(question)` runs before the provider is called. It matches, in ES and
EN, requests for rows (`filas`, `registros`, `rows`, `records`), requests to show data
(`dame`, `muéstrame`, `show me`, `give me`), write verbs (`ejecuta`, `borra`, `elimina`, `inserta`,
`update`, `delete`, `drop`, `truncate`) and business-number questions (`¿cuánto vendimos…?`,
`how much did we sell…`).

**Why**: SC-005 asks for 100 % on the fixture cases; a prompt cannot promise that. Counting
questions (`¿cuántas tablas hay?`) must still be answered, so the data patterns are noun-bound
(`filas`/`registros`/`rows`), never the bare interrogative. The system prompt repeats the rule so a
draft the user copies never contains a data question either.

**Rejected**: prompt-only refusal (SC-005 unprovable, and one model change reopens the hole).

## R5 — What the daily cap counts

**Decision**: `source_chat_message` holds one row per turn with `tokens_in`, `tokens_out` (and the
text only when `AI_STRUCTURE_CHAT_STORE_QUESTIONS=on`). The cap is `SUM(tokens_in + tokens_out)` for the
user, the source and the current UTC day against `AI_STRUCTURE_CHAT_DAILY_TOKENS` (default 100 000). A
refused question writes no row: nothing was spent.

**Rejected**: a separate `source_chat_usage` table — the messages already carry the counts, and a
second table is a second thing to keep in step. Purge rides the worker's existing hourly
`housekeeping()` (30 days), like `direct.prune_log` does.

## R6 — The sample request's method

**Decision**: the sample stores `method` (default `GET`) but this delivery runs `GET` only; any
other method is refused with one line naming the reason.

**Why**: a REST sample is executed with the *catalogue's* credential, and the constitution says
"Origin database credentials are read-only. The dashboard MUST NEVER write to the origin." A `POST`
to an unknown endpoint may write. US3 needs the field; the field is stored now so no migration
follows it later, and the refusal is honest.

**Rejected**: allowing `POST` with params only — no way to prove the endpoint is a read.

## R7 — Keeping the chat inside the context window

**Decision**: build the context from the pack, capped at 60 000 characters (~15 k tokens). Under
the cap: the whole structure as JSON. Over the cap: an index (schemas → tables → column counts, or
for REST the sample names and top-level keys) plus the full detail of every schema/table/endpoint
whose name appears in the question, and a line stating the rest was omitted.

**Rejected**: a second provider round to "fetch the schema" — the provider has no tools by design
(IX, VIII) and a round trip costs as much as the truncation saves.

## R8 — The personal-data heuristic

**Decision**: a column is flagged when its lowercased name contains `email`, `correo`, `mail`,
`nombre`, `name`, `apellido`, `surname`, `phone`, `telefono`, `celular`, `movil`, `documento`,
`cedula`, `dni`, `rut`, `pasaporte`, `address`, `direccion`, `chat_id`, `chatid`, `telegram` or
`whatsapp`. The super user may override any column; the override lives in
`source_structure_flag` and wins over the heuristic, and travels in the pack.

**Rejected**: a configurable dictionary per installation (nobody asked, and it is a setting to keep
in sync); no flags at all (the pack template's `Personal` column would always be empty, and 043
WS-B promises the flag).
