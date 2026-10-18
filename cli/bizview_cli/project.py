"""`bizview project new`: a BI project folder inside a v2 workspace (feature 020)."""
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

from bizview_cli import layout
from bizview_cli.i18n import t
from bizview_cli.init import _template, speckit

FOLDERS = ("specs", "integrations", "reports", "distributions")


def slug_for(name: str) -> str:
    """Slug of a project name: ascii, lowercase, dashes, starting with a letter, ≤ 50."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"^[^a-z]+", "", slug)
    return slug[:50].rstrip("-")


def new_project(root: Path, name: str, *, slug: str | None = None, agent: str = "claude",
                speckit_init: bool = True) -> int:
    root = root.resolve()
    if not (root / "bizview.yaml").is_file():
        print(t("project.not_workspace", path=root), file=sys.stderr)
        return 2
    name = name.strip()
    if not 1 <= len(name) <= 80:
        print(t("project.bad_name"), file=sys.stderr)
        return 2
    slug = slug or slug_for(name)
    if not layout.ID_RE.match(slug):
        print(t("project.bad_slug", slug=slug), file=sys.stderr)
        return 2
    base = root / "projects" / slug
    if base.exists():
        print(t("project.exists", slug=slug), file=sys.stderr)
        return 2
    base.mkdir(parents=True)
    if speckit_init:
        speckit(base, agent)
    # After Spec Kit, so the Bizview constitution replaces its template.
    files = _template() / "files"
    values = {"name": json.dumps(name, ensure_ascii=False), "slug": slug,
              "date": date.today().isoformat()}
    (base / "project.yaml").write_text(
        (files / "project.yaml").read_text(encoding="utf-8").format(**values), encoding="utf-8")
    constitution = base / ".specify" / "memory" / "constitution.md"
    constitution.parent.mkdir(parents=True, exist_ok=True)
    constitution.write_text((files / "constitution.md").read_text(encoding="utf-8").format(
        name=name, date=values["date"]), encoding="utf-8")
    for folder in FOLDERS:
        (base / folder).mkdir(exist_ok=True)
        (base / folder / ".gitkeep").touch()
    print(t("project.created", slug=slug, path=base))
    return 0
