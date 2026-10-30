# App guide (feature 023)

The guide the chat and the **Ayuda** page answer from. It ships with each release, so answers
match the installed version. Spec: [specs/023-chat-app-guide](../../../../specs/023-chat-app-guide/spec.md).

| File | Holds |
|---|---|
| `index.yaml` | sections and the metadata of every topic (title, summary, roles, routes, tiles, commands, aliases, related) |
| `es/<topic>.md`, `en/<topic>.md` | one body per topic and language |
| `es/_ayuda.md`, `en/_ayuda.md` | the fixed `/ayuda` reply template |
| `labels-allow.txt` | bold terms that are not UI labels (product names, environment variables) |
| `__init__.py`, `ayuda.py` | loader, role filter, topic lookup, `/ayuda` reply (code) |

## Add or change a topic

1. Add the entry to `index.yaml` inside its section (order = display order):
   - `id`: lowercase words joined by `-`, unique, equal to the file names;
   - `title` and `summary` in `es` and `en` (summary ≤ 140 chars);
   - `roles`: who can use what the topic documents — `public`, `user`, `admin`, `superuser`;
   - `routes`, `tiles`, `commands`: the App.tsx route patterns, Administración tiles and chat
     commands the topic documents (every one must be covered by some topic);
   - `aliases` per language (words people use), `related` (existing ids, ≤ 5).
2. Write `es/<id>.md` and `en/<id>.md` with the body rules below.
3. Run the drift tests:

   ```bash
   cd backend  && uv run pytest tests/test_guide.py
   cd frontend && npm test -- guide-drift
   ```

   Each failure names the topic and the fix. The whole index must stay ≤ 8,000 characters per
   language: it is part of every chat prompt.

When a screen changes (new route, tile or command, renamed button), update the topic in the same
change; the drift tests fail until you do.

## Body rules

- Start with `# <title>`, the topic title of that language.
- Then these `##` sections, in this order (es / en):
  1. "Para qué sirve" / "What it is for";
  2. "Quién puede usarlo" / "Who can use it";
  3. "Cómo se hace" / "How to";
  4. optional "Opciones" / "Options";
  5. optional "Problemas frecuentes" / "Common problems".

  The es and en bodies have the same sections in the same order.
- ≤ 6,000 characters.
- UI labels in **bold**, exactly as that language's catalogue shows them
  (`frontend/src/i18n/`). A bold term that is not a label goes in `labels-allow.txt`.
- In-app links: `[Abrir Administración → Fuentes de datos](app:/admin/fuentes)`. A link must
  match a route, have no `:param`, and be openable by at least one of the topic's roles.
- Role names as the catalogue writes them: Usuario / Administrador / Superusuario, and
  "sin cuenta" for public pages. Say who can do something when the reader may not have the role
  ("Solo el **Superusuario** puede…").
- No credentials, hosts or customer names. Environment variable names only in topics whose
  roles are `[superuser]`.
- Short sentences and numbered steps; one action per step.
