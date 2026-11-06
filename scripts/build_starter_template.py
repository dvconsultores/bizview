#!/usr/bin/env python3
"""Render `bizview-starter-template.zip` at the repository root (feature 057).

The template is the pack with placeholders (`<slug>`, `<nombre>`) instead of a project. It is
committed so a reader without an installation can download it from the repository, and CI compares
it with what the pack renders today: change the pack without regenerating it and the test fails.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    sys.path.insert(0, str(ROOT / "cli"))
    from bizview_cli import starter

    files = starter.render(template=True, lang="es")
    target = ROOT / starter.TEMPLATE_NAME
    target.write_bytes(starter.zip_bytes(files))
    print(f"{target.relative_to(ROOT)}: {len(files)} files, {target.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
