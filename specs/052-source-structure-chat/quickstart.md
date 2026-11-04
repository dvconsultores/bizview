# Quickstart — seeing the tab and proving it

## The fast loop (no database needed)

```bash
cd cli && uv run pytest tests/test_structure_pack.py -q
```

This exercises the generator alone: a PostgreSQL fixture with two schemas and a date column, a REST
fixture with one sample, and a SOAP fixture. It asserts the two files against the template's
headings and greps them for the seeded row values, the host and the credential — the same
"distinctive value" trick 014 used.

## The backend loop

```bash
cd backend && uv run pytest tests/test_source_structure.py tests/test_source_structure_chat.py -q
```

What it proves:

- `GET /api/sources/{name}/structure?format=md|json` matches the generator byte for byte and is
  audited as `source_described`;
- notes and the personal flag survive a round trip and appear in the pack;
- a sample request runs, stores its shape and never stores a value;
- the chat's provider payload contains the structure, the question and the last turns, and no
  credential, host or row value;
- "dame 5 filas", "¿cuánto vendimos ayer?", "borra la tabla" are refused **without** a provider
  call;
- an answer naming `ventas_fantasma` comes back with it in `unknown`;
- a user at the cap gets 429, and the next day gets an answer again.

## The frontend loop

```bash
cd frontend && npx vitest run tests/unit/source-structure.test.tsx
```

It renders the Estructura tab with a stubbed API: the tree lists schema → table → columns, the
search box filters, the personal chip shows, the two download buttons call the right URLs, and with
`ai_enabled: false` the chat panel shows the enable line instead of an input.

## See it in the browser

```bash
cd frontend && npm run dev      # and the backend, from the repository root
```

1. **Administración → Fuentes de datos → CoinMarketCap → Estructura.** The tab renders the REST
   block with the sample requests; add one (`v1/cryptocurrency/listings/latest`, `limit=100`),
   press **Ejecutar**, and the shape with `records`/`fields` appears.
2. **Descargar estructura (.md)** opens a file whose headings match
   `pack/bizview-starter-pack/bizview-starter/sources/<nombre>/structure.md`, and whose
   `## Observaciones` carries what you typed in **Notas**.
3. **Descargar estructura (.json)** is the same content with the `pack` header; feed it to
   `bizview validate --describe coinmarketcap=structure.json` and the validation uses it.
4. **Chat** (with `AI_PROVIDER` configured): ask *"¿qué campos trae el endpoint de listados y cuál
   es la fecha?"* — the answer names `last_updated` and `data`. Ask *"dame 5 filas"* — refused in
   one line. With `AI_PROVIDER=none` the panel shows how a super user enables it.
5. **375 px**: the tabs stay, the structure list stacks, and the chat opens as a bottom sheet that
   can be dismissed without losing the question.
