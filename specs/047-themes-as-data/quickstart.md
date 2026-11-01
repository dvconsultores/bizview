# Quickstart — proving 047 on a working tree

## 1. The contract, offline

```bash
cd /home/andres/vsCodeProjects/bizview
.venv/bin/python -m bizview_cli theme validate cli/bizview_cli/workspace_template/files/themes/impacto.yaml
# exit 0

cat > /tmp/bad.yaml <<'YML'
id: bad
name: Bad
name_en: Bad
version: 1
light: {surface: "#FFFFFF", card: "#F8FAFC", text: "#EEEEEE", muted: "#64748B", grid: "#E2E8F0",
        primary: "#0B5FFF", positive: "#16A34A", negative: "#DC2626", neutral: "#64748B",
        series: ["#0B5FFF", "#F59E0B", "#10B981"]}
dark: {…}
YML
.venv/bin/python -m bizview_cli theme validate /tmp/bad.yaml   # exit 1, names light.text vs light.surface and the ratio
```

## 2. The built-ins are themes

```bash
for f in frontend/src/theme/themes/*.json; do
  .venv/bin/python -c "import json,sys;from bizview_cli.theme import validate_theme; \
    print(sys.argv[1], validate_theme(json.load(open(sys.argv[1]))) or 'ok')" "$f"
done
```

## 3. Upload, apply, render

```bash
# backend on :8000 with the dev database
curl -fsS -b cookies -X POST localhost:8000/api/admin/themes \
  -H 'content-type: application/json' --data @<(python3 -c 'import json;print(json.dumps({"yaml":open("acme.yaml").read()}))')
curl -fsS -b cookies -X PUT localhost:8000/api/admin/settings/theme -H 'content-type: application/json' \
  -d '{"theme_id":"acme-dark-blue"}'
```

Then the appearance page shows it with its two preview cards, and a dashboard's `--c-surface` is the
theme's `card`:

```bash
curl -fsS localhost:8000/api/themes/acme-dark-blue | python3 -m json.tool | head -20
```

## 4. Per report

```yaml
# reports/<id>/report.yaml
layout:
  theme: {id: acme-dark-blue, mode: dark}
```

Open the report with the app in light mode: the report area is dark, the chrome is light; the
sun/moon toggle flips the area for the session; the PDF is the light variant.

## 5. In a project zip

```bash
zip -r acme.zip projects/acme     # carrying themes/acme-dark-blue.yaml
# Importar in Proyectos: the theme appears in Apariencia with origin "acme"
```

## 6. Gates

```bash
sh scripts/gates/all.sh
cd backend && ../.venv/bin/python -m pytest tests/test_themes.py tests/test_palette.py -q
cd frontend && npx tsc --noEmit && npx vitest run tests/unit/themes.test.ts tests/unit/palette-presets.test.ts
cd cli && ../.venv/bin/python -m pytest tests/test_theme.py -q
```
