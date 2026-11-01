#!/bin/sh
# Gate 8/8 (046): the documents are structurally sound and the two READMEs stay in step.
#
# A full markdown linter would add a dependency for a hand-written corpus; this checks what actually
# breaks a reader:
#   1. a fenced code block that is never closed;
#   2. a table row whose cell count differs from its header's;
#   3. a relative link or image whose target does not exist;
#   4. a heading written without a space after the `#`s, or repeated verbatim in the same file
#      (`CHANGELOG.md` is exempt: it repeats `### Added` under each version on purpose);
#   5. trailing whitespace after a heading;
#   6. `README.md` and `README.es.md` with a different number of sections.
#
# $1: an optional path to check instead of the whole corpus (used by the proof that it fails).
set -eu
cd "$(dirname "$0")/../.."

PY=${PY:-$(pwd)/.venv/bin/python}
[ -x "$PY" ] || PY=python3

PATHS=${1:-"README.md README.es.md SECURITY.md CONTRIBUTING.md CODE_OF_CONDUCT.md CHANGELOG.md docs backend/app/guide"}

# shellcheck disable=SC2086
"$PY" - $PATHS <<'PY'
import pathlib
import re
import sys

targets = []
for given in sys.argv[1:]:
    path = pathlib.Path(given)
    if path.is_dir():
        targets.extend(sorted(path.rglob("*.md")))
    elif path.exists():
        targets.append(path)
    else:
        print(f"{given}: no such file or directory", file=sys.stderr)
        raise SystemExit(1)

LINK = re.compile(r"!?\[[^\]]*]\(([^)\s]+)")
problems = []
sections: dict[str, int] = {}

for path in targets:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    fences = 0
    headings: dict[str, int] = {}
    table_header_cells = None
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            fences += 1
            table_header_cells = None
            continue
        if fences % 2:                    # inside a fenced block: nothing here is markdown
            continue
        if stripped.startswith("|"):
            cells = len([c for c in stripped.strip("|").split("|")])
            if table_header_cells is None:
                table_header_cells = cells
            elif cells != table_header_cells and not set(stripped) <= set("|-: "):
                problems.append(f"{path}:{number}: a table row has {cells} cells, "
                                f"its header has {table_header_cells}")
        elif stripped:
            table_header_cells = None
        if re.match(r"^#+[^#\s]", line):
            problems.append(f"{path}:{number}: heading without a space after the #s")
        m = re.match(r"^(#+) (.+?)\s*$", line)
        if m:
            if line.rstrip() != line:
                problems.append(f"{path}:{number}: trailing whitespace after a heading")
            heading = m.group(2).strip()
            repeats = len(m.group(1)) <= 2 and path.name != "CHANGELOG.md"
            if repeats and heading in headings:
                problems.append(f"{path}:{number}: heading repeated: {heading!r}")
            headings[heading] = number
            if m.group(1) == "##" and str(path) in ("README.md", "README.es.md"):
                sections[str(path)] = sections.get(str(path), 0) + 1
        for target in LINK.findall(line):
            if target.startswith(("http://", "https://", "mailto:", "#", "app:")):
                continue
            local = target.split("#", 1)[0]
            if not local:
                continue
            resolved = (path.parent / local).resolve()
            if not resolved.exists():
                problems.append(f"{path}:{number}: link target does not exist: {local}")
    if fences % 2:
        problems.append(f"{path}: a fenced code block is never closed")

if "README.md" in sections or "README.es.md" in sections:
    en, es = sections.get("README.md", 0), sections.get("README.es.md", 0)
    if en != es:
        problems.append(f"README.md has {en} sections and README.es.md has {es}: they must match")

for problem in problems:
    print(problem)
raise SystemExit(1 if problems else 0)
PY
printf 'ok\n'
