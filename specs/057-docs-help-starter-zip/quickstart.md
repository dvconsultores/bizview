# Quickstart — proving 057 works

## Prerequisites

```sh
cd /home/andres/vsCodeProjects/bizview
```

## 1. The pack validates, for every combination

```sh
cd cli && .venv/bin/python -m pytest tests/test_starter.py -q
```

Proves: eight combinations (source × kind × language) render, each validates with zero errors when
written into `projects/<slug>/`, every entry is documented, and the prompt is under 1,500 words.

## 2. The template is committed and current

```sh
cd /home/andres/vsCodeProjects/bizview
make starter-template
git status --short bizview-starter-template.zip   # empty: nothing changed
```

## 3. The server serves both

```sh
cd backend && .venv/bin/python -m pytest tests/test_starter_api.py -q
```

Proves: `GET /api/projects/starter?name=…&lang=es&kind=integration` answers a zip whose body the
validator accepts, the filename is `bizview-starter-<slug>.zip`, an over-limit render is refused with
`too_large`, and `GET /api/projects/starter-template` answers the committed bytes with
`application/zip` and the exact `Content-Length`.

## 4. The CLI writes the same bytes

```sh
cd cli && .venv/bin/python -m bizview_cli init project "Ventas de prueba" --dir /tmp/pack
.venv/bin/python -m bizview_cli validate /tmp/pack   # needs a bizview.yaml beside it
```

## 5. The guide and the documents

```sh
cd backend && .venv/bin/python -m pytest tests/test_guide.py -q
cd ../frontend && npm test -- guide-drift
cd .. && sh scripts/gates/01-vocabulary.sh && sh scripts/gates/08-markdown.sh
```

Proves: `crear-con-ia` exists in both languages, every topic ends with its related section, links
resolve, and no document mentions the removed agent.

## 6. In the app

`Proyectos` (empty installation) → **Descargar paquete inicial** → name, source, language, kind →
download → unzip → import the zip untouched → the only problems shown are the `REEMPLAZA`/`REPLACE`
placeholders.
