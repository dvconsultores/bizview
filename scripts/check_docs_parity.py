#!/usr/bin/env python3
"""Every document the product ships exists in Spanish and in English, in step (feature 057b).

The rule is in `.specify/memory/constitution`'s shadow — `specs/046-release-docs-governance` — and in
CONTRIBUTING.md: English at the canonical path, Spanish beside it (`docs/es/`, or `NAME.es.md` at the
repository root), with the same shape. "Same shape" is what this script measures, because a
translation that drops a section is how a reader of one language learns something the other cannot:

  * the heading skeleton — the level of every heading, in order (titles are translated);
  * the number of fenced code blocks, their languages and how many lines each has;
  * the number of tables;
  * the relative links and images, resolved to repository paths.

A missing counterpart or a drifted pair fails, and the message names what to fix.

    python3 scripts/check_docs_parity.py            # the repository
    python3 scripts/check_docs_parity.py --root X   # a fixture (used by the proof that it fails)
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: The tree being checked: the repository, or the fixture `--root` names.
BASE = ROOT

#: Root documents: English at the repository root, Spanish as `NAME.es.md` beside it.
ROOT_PAIRS = (
    ("README.md", "README.es.md"),
    ("CONTRIBUTING.md", "CONTRIBUTING.es.md"),
    ("SECURITY.md", "SECURITY.es.md"),
    ("CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT.es.md"),
    ("DIAGNOSIS.md", "DIAGNOSIS.es.md"),
)
#: `docs/<name>.md` ↔ `docs/es/<name>.md`.
DOCS_PAIRS = ("AUTHORING", "IMPORT", "REPORTS", "RENDERING", "INSTALL", "THEMES", "DESIGN-SYSTEM")
#: The starter pack: the two languages use their own file names, so the pairs are explicit.
PACK_DIR = Path("pack/bizview-starter-pack")
PACK_PAIRS = (
    ("PROMPT.md", "PROMPT.md"),
    ("REQUEST.md", "REQUEST.md"),
    ("README.md", "README.md"),
    ("CONTENTS.md", "CONTENIDO.md"),
    ("WHAT-BIZVIEW-DOES.md", "QUE-HACE-BIZVIEW.md"),
    ("HOW-IT-RENDERS.md", "COMO-SE-DIBUJA.md"),
)
HEADING = re.compile(r"^(#+) (.+?)\s*$")
FENCE = re.compile(r"^```(\S*)\s*$")
LINK = re.compile(r"!?\[[^\]]*]\(([^)\s]+)")
TABLE_ROW = re.compile(r"^\|")


@dataclass
class Shape:
    """What has to match between a document and its translation."""

    headings: list[int] = field(default_factory=list)
    blocks: list[tuple[str, int]] = field(default_factory=list)
    tables: int = 0
    links: set[str] = field(default_factory=set)


def shape(path: Path) -> Shape:
    text = path.read_text(encoding="utf-8")
    out = Shape()
    language, lines, in_code, rows = "", 0, False, 0
    for line in text.split("\n"):
        fence = FENCE.match(line.strip())
        if fence and not in_code:
            in_code, language, lines = True, fence.group(1), 0
            continue
        if fence and in_code:
            out.blocks.append((language, lines))
            in_code = False
            continue
        if in_code:
            lines += 1
            continue
        heading = HEADING.match(line)
        if heading:
            out.headings.append(len(heading.group(1)))
        if TABLE_ROW.match(line.strip()):
            rows += 1
        elif rows:
            # A table is a header row plus its separator plus body rows; count the blocks.
            out.tables += 1
            rows = 0
        for target in LINK.findall(line):
            if target.startswith(("http://", "https://", "mailto:", "#", "app:")):
                continue
            local = target.split("#", 1)[0]
            if not local:
                continue
            out.links.add(_normalise(path, local))
    if rows:
        out.tables += 1
    if in_code:                       # an unclosed fence is gate 8's problem; count it anyway
        out.blocks.append((language, lines))
    return out


#: The two languages name the pack's documents differently; a link to one is a link to its pair.
PACK_NAMES = {"CONTENIDO.md": "CONTENTS.md", "QUE-HACE-BIZVIEW.md": "WHAT-BIZVIEW-DOES.md",
              "COMO-SE-DIBUJA.md": "HOW-IT-RENDERS.md"}


def _canonical(rel: str) -> str:
    """A link's English path, so `docs/es/x.md` and `x.es.md` compare with their counterparts."""
    for spanish, english in PACK_NAMES.items():
        rel = rel.replace(f"/{spanish}", f"/{english}")
    for folder in ("docs/es/", "backend/app/guide/es/", "pack/bizview-starter-pack/es/"):
        if rel.startswith(folder):
            return folder.replace("/es/", "/") + rel[len(folder):]
    if rel.endswith(".es.md"):
        return rel[:-len(".es.md")] + ".md"
    return rel


def _normalise(path: Path, local: str) -> str:
    """A link as a repository-relative English path, so a document and its translation compare."""
    resolved = (path.parent / local).resolve()
    try:
        rel = str(resolved.relative_to(BASE)).replace("\\", "/")
    except ValueError:
        return str(resolved).replace("\\", "/")
    return _canonical(rel)


def pairs(root: Path) -> list[tuple[Path, Path]]:
    out = [(root / en, root / es) for en, es in ROOT_PAIRS]
    out += [(root / "docs" / f"{name}.md", root / "docs" / "es" / f"{name}.md")
            for name in DOCS_PAIRS]
    # `docs/guides/…` are reader documents too: English there, Spanish under `docs/es/guides/`.
    out += [(path, root / "docs" / "es" / "guides" / path.relative_to(root / "docs" / "guides"))
            for path in sorted((root / "docs" / "guides").rglob("*.md"))]
    guide = root / "backend" / "app" / "guide"
    out += [(guide / "en" / f"{p.stem}.md", p) for p in sorted((guide / "es").glob("*.md"))]
    pack = root / PACK_DIR
    out += [(pack / "en" / en, pack / "es" / es) for en, es in PACK_PAIRS]
    return out


def describe(shape_: Shape) -> str:
    return (f"{len(shape_.headings)} headings, {len(shape_.blocks)} code blocks, "
            f"{shape_.tables} tables, {len(shape_.links)} links")


def compare(english: Path, spanish: Path) -> list[str]:
    problems: list[str] = []
    if not english.exists():
        return [f"{english}: the English document is missing"]
    if not spanish.exists():
        return [f"{spanish}: missing; the Spanish counterpart of {english.name} has to exist"]
    one, other = shape(english), shape(spanish)
    if one.headings != other.headings:
        problems.append(
            f"{spanish}: heading skeleton differs — {english.name} has {one.headings}, "
            f"this has {other.headings}")
    if [language for language, _ in one.blocks] != [language for language, _ in other.blocks]:
        problems.append(
            f"{spanish}: code blocks differ — {english.name} has "
            f"{[language or '(none)' for language, _ in one.blocks]}, this has "
            f"{[language or '(none)' for language, _ in other.blocks]}")
    elif [lines for _, lines in one.blocks] != [lines for _, lines in other.blocks]:
        problems.append(
            f"{spanish}: the code blocks have different sizes — {english.name} has "
            f"{[lines for _, lines in one.blocks]}, this has {[lines for _, lines in other.blocks]}")
    if one.tables != other.tables:
        problems.append(
            f"{spanish}: {other.tables} tables against {one.tables} in {english.name}")
    if one.links != other.links:
        missing = sorted(one.links - other.links)
        extra = sorted(other.links - one.links)
        problems.append(f"{spanish}: links differ — missing {missing}, unexpected {extra}")
    return problems


def check(root: Path) -> list[str]:
    problems: list[str] = []
    for english, spanish in pairs(root):
        problems.extend(compare(english, spanish))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="English/Spanish documentation parity.")
    parser.add_argument("--root", default=str(ROOT), help="the repository or a fixture")
    parser.add_argument("--quiet", action="store_true", help="only report problems")
    args = parser.parse_args()
    global BASE
    root = Path(args.root).resolve()
    BASE = root
    problems = check(root)
    if not args.quiet:
        total = len(pairs(root))
        print(f"{total} document pairs checked")
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} parity problem(s): a missing or drifted document is a build failure")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
