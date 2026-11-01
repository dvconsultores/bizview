# Quickstart — proving 046 on a working tree

Prerequisites: the repository, `python3` (the gates use `sh` and, for the version step, `python3`),
and a dev venv at `.venv` if you want the backend half of the version check.

```bash
cd /home/andres/vsCodeProjects/bizview
```

## 1. The number is one truth

```bash
cat VERSION                      # 0.2.0
sh scripts/gates/07-version.sh   # prints every copy, exit 0
```

Expected: every copy prints `0.2.0`; then, with a backend running, `/api/health` reports `0.2.0`.

Refusal to prove the gate works:

```bash
cp frontend/package.json /tmp/pkg.bak
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("frontend/package.json"); d = json.loads(p.read_text())
d["version"] = "0.1.0"; p.write_text(json.dumps(d, indent=2) + "\n")
PY
sh scripts/gates/07-version.sh   # exit 1, naming frontend/package.json
cp /tmp/pkg.bak frontend/package.json
```

## 2. The documents say what the product is

```bash
sh scripts/gates/01-vocabulary.sh   # exit 0: no asistente / speckit- / run contract / token budget / AI Powered
sh scripts/gates/08-markdown.sh     # exit 0: fences balanced, tables consistent, links resolve, README parity
```

Read `README.md` top to bottom: a person who has never run the product installs it from that page
alone (SC-001), and the eight authoring steps name commands that exist:

```bash
bizview --help        # init · project new · validate · describe · version
```

Refusal to prove the vocabulary gate works:

```bash
echo '# asistente' > /tmp/bad.md && sh scripts/check_vocabulary.sh /tmp/bad.md   # exit 1
```

## 3. The authoring contract has one home

```bash
grep -n "^## " docs/AUTHORING.md      # layout, request, schemas, rules, lite specs, validate, images, example
grep -n "^## " docs/IMPORT.md         # upload, map, collisions, validate, preview, apply
head -3 docs/VIBE-REPORTING.md        # a redirect note, not a second contract
```

## 4. Governance documents

```bash
head -1 SECURITY.md CODE_OF_CONDUCT.md CONTRIBUTING.md
grep -n "2.0.0\|3.0.0\|Sync Impact Report" .specify/memory/constitution.md | head
grep -n "assistant" .specify/memory/constitution.md    # no hits
```

## 5. Everything at once

```bash
sh scripts/gates/all.sh        # 01–04, 06, 07, 08
cd backend && ../.venv/bin/python -m ruff check app tests && cd ..
cd frontend && npx tsc --noEmit && npx vitest run && cd ..
cd backend && ../.venv/bin/python -m pytest tests/test_guide.py tests/test_i18n_catalogue.py -q
```

## 6. Release artefacts

```bash
sed -n '/## \[0.2.0\]/,/## \[Unreleased\]/p' CHANGELOG.md | head -40
git tag -l v0.2.0
```
